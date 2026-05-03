"""server.py: Headless authoritative game server for Quad Fighter network multiplayer.

Can run standalone or inside Docker::

    python server.py                         # defaults: port 9046, max 4 players
    QUAD_SERVER_PORT=9046 python server.py
    docker run -p 9046:9046 quad-fighter-server

Protocol: newline-delimited JSON over TCP.

Client → Server message types
-------------------------------
hello       – version handshake (must be first message)
join        – request to join the session as a player
input       – per-frame input snapshot
voice_state – Discord voice-chat status update
disconnect  – graceful goodbye
pong        – reply to a server ping

Server → Client message types
-------------------------------
welcome     – handshake accepted; carries player_id
reject      – handshake or join denied; carries reason + message
state       – authoritative game-state snapshot (broadcast every tick)
event       – discrete game event (hit, death, pickup …)
voice_event – broadcast when a player's Discord voice state changes
ping        – keepalive probe
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time

from version import GAME_VERSION, PROTOCOL_VERSION, SERVER_VERSION

# ── Configuration (environment variables) ────────────────────────────────────

SERVER_HOST      = os.environ.get("QUAD_SERVER_HOST", "0.0.0.0")
SERVER_PORT      = int(os.environ.get("QUAD_SERVER_PORT", "9046"))
MAX_PLAYERS      = int(os.environ.get("QUAD_MAX_PLAYERS", "4"))
TICK_RATE        = int(os.environ.get("QUAD_TICK_RATE", "30"))   # state broadcasts / second
PING_INTERVAL    = 10.0   # seconds between keepalive pings
PING_TIMEOUT     = 30.0   # disconnect client if no pong within this many seconds
PLAYER_MOVE_SPEED = 3.0   # units per tick for authoritative movement simulation

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s – %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("quad-server")


# ── Game state ────────────────────────────────────────────────────────────────

class PlayerState:
    """Minimal server-side representation of one connected player."""

    def __init__(self, player_id: int, client_id: str) -> None:
        self.player_id  = player_id
        self.client_id  = client_id
        self.name       = f"Player{player_id}"

        # Authoritative position / state (updated from inputs each tick)
        self.x: float = 140.0 + (player_id - 1) * 60
        self.y: float = 368.0
        self.facing: int = 1   # +1 right, -1 left
        self.health: int = 100
        self.alive: bool = True

        # Latest raw inputs from this client
        self.inputs: dict = {}

        # Discord voice state
        self.voice_status:  str = ""
        self.voice_channel: str = ""

        # Last time we received any message from this client
        self.last_seen: float = time.monotonic()

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "name":       self.name,
            "x":          self.x,
            "y":          self.y,
            "facing":     self.facing,
            "health":     self.health,
            "alive":      self.alive,
            "voice_status":  self.voice_status,
            "voice_channel": self.voice_channel,
        }


class ServerGameState:
    """Authoritative world state owned by the server."""

    def __init__(self) -> None:
        self.players:   dict[int, PlayerState] = {}   # player_id → PlayerState
        self._next_id   = 1
        self.tick: int  = 0

    def add_player(self, client_id: str) -> PlayerState:
        pid    = self._next_id
        self._next_id += 1
        player = PlayerState(pid, client_id)
        self.players[pid] = player
        return player

    def remove_player(self, player_id: int) -> None:
        self.players.pop(player_id, None)

    def player_count(self) -> int:
        return len(self.players)

    def apply_inputs(self) -> None:
        """Advance game state by one tick based on queued inputs.

        This is a minimal physics stub – extend for full authoritative
        simulation once all clients send inputs reliably.
        """
        SPEED = PLAYER_MOVE_SPEED
        for ps in self.players.values():
            inp = ps.inputs
            if inp.get("move_right"):
                ps.x     += SPEED
                ps.facing = 1
            elif inp.get("move_left"):
                ps.x     -= SPEED
                ps.facing = -1
            if inp.get("move_down"):
                ps.y += SPEED
            elif inp.get("move_up"):
                ps.y -= SPEED

        self.tick += 1

    def snapshot(self) -> dict:
        return {
            "type":    "state",
            "tick":    self.tick,
            "players": [p.to_dict() for p in self.players.values()],
            "enemies": [],   # placeholder – full enemy simulation to follow
        }


# ── Client connection handler ─────────────────────────────────────────────────

class ClientConnection:
    """Manages one connected TCP client."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        game_state: ServerGameState,
        server: "GameServer",
    ) -> None:
        self._reader     = reader
        self._writer     = writer
        self._game_state = game_state
        self._server     = server

        peer = writer.get_extra_info("peername")
        self.addr        = f"{peer[0]}:{peer[1]}" if peer else "unknown"
        self.client_id:  str | None = None
        self.player:     PlayerState | None = None
        self.handshook:  bool = False

        self._last_ping_sent: float = time.monotonic()
        self._last_pong_recv: float = time.monotonic()

    async def handle(self) -> None:
        log.info("connection from %s", self.addr)
        try:
            buf = ""
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self._reader.read(4096), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    await self._check_keepalive()
                    continue

                if not chunk:
                    break  # client disconnected

                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        log.warning("%s sent invalid JSON", self.addr)
                        continue
                    should_continue = await self._dispatch(msg)
                    if not should_continue:
                        return

        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            self._cleanup()
            log.info("disconnected: %s (player_id=%s)", self.addr, self.player and self.player.player_id)

    async def send(self, msg: dict) -> None:
        try:
            data = (json.dumps(msg) + "\n").encode("utf-8")
            self._writer.write(data)
            await self._writer.drain()
        except (OSError, BrokenPipeError):
            pass

    # ── Message dispatch ──────────────────────────────────────────────────────

    async def _dispatch(self, msg: dict) -> bool:
        """Route an incoming message.  Returns False to close the connection."""
        mtype = msg.get("type")

        if self.player:
            self.player.last_seen = time.monotonic()

        if mtype == "hello":
            return await self._handle_hello(msg)
        if not self.handshook:
            log.warning("%s sent %s before hello – ignoring", self.addr, mtype)
            return True
        if mtype == "join":
            return await self._handle_join(msg)
        if mtype == "input":
            self._handle_input(msg)
        elif mtype == "voice_state":
            await self._handle_voice_state(msg)
        elif mtype == "pong":
            self._last_pong_recv = time.monotonic()
        elif mtype == "disconnect":
            return False
        return True

    async def _handle_hello(self, msg: dict) -> bool:
        client_version   = msg.get("game_version",    "")
        client_protocol  = int(msg.get("protocol_version", 0))
        self.client_id   = msg.get("client_id", self.addr)

        log.info(
            "hello from %s  game_version=%s  protocol=%s",
            self.addr, client_version, client_protocol,
        )

        # ── Protocol mismatch (hard reject) ──────────────────────────────────
        if client_protocol != PROTOCOL_VERSION:
            reason  = "version_mismatch"
            message = (
                f"Network protocol mismatch.  "
                f"Server uses protocol {PROTOCOL_VERSION}, "
                f"client sent protocol {client_protocol}.  "
                f"Please update your client or server."
            )
            log.warning("rejected %s – %s", self.addr, message)
            await self.send({"type": "reject", "reason": reason, "message": message})
            return False

        # ── Client version too old (soft reject – inform to upgrade) ─────────
        if client_version != GAME_VERSION:
            reason  = "version_mismatch"
            message = (
                f"Server is running build {GAME_VERSION}.  "
                f"Your game is build {client_version}.  "
                f"Please update your game client."
            )
            log.warning("rejected %s – %s", self.addr, message)
            await self.send({"type": "reject", "reason": reason, "message": message})
            return False

        self.handshook = True
        # Immediately acknowledge the handshake so the client knows the
        # version is accepted.  player_id is assigned when the client sends
        # 'join' next.
        await self.send({
            "type":             "welcome",
            "server_version":   SERVER_VERSION,
            "protocol_version": PROTOCOL_VERSION,
        })
        return True

    async def _handle_join(self, msg: dict) -> bool:
        if self.player is not None:
            return True  # already joined

        if self._game_state.player_count() >= MAX_PLAYERS:
            await self.send({
                "type":    "reject",
                "reason":  "server_full",
                "message": f"Server is full ({MAX_PLAYERS} players max).",
            })
            log.info("refused %s – server full", self.addr)
            return False

        self.player       = self._game_state.add_player(self.client_id or self.addr)
        self.player.name  = msg.get("player_name", self.player.name)
        self._server.register_connection(self.player.player_id, self)

        log.info(
            "player %s joined as '%s' from %s  (total %d)",
            self.player.player_id,
            self.player.name,
            self.addr,
            self._game_state.player_count(),
        )

        # Notify the client of their assigned player_id
        await self.send({
            "type":      "event",
            "name":      "joined",
            "player_id": self.player.player_id,
        })
        return True

    def _handle_input(self, msg: dict) -> None:
        if self.player:
            self.player.inputs      = msg.get("inputs", {})
            self.player.last_seen   = time.monotonic()

    async def _handle_voice_state(self, msg: dict) -> None:
        """Update this player's Discord voice state and broadcast to others."""
        if not self.player:
            return
        voice_status  = str(msg.get("voice_status", ""))
        voice_channel = str(msg.get("channel_id",   ""))
        self.player.voice_status  = voice_status
        self.player.voice_channel = voice_channel
        self.player.last_seen     = time.monotonic()
        log.info(
            "player %s voice_state: status=%r channel=%r",
            self.player.player_id, voice_status, voice_channel,
        )
        await self._server.broadcast({
            "type":         "voice_event",
            "player_id":    self.player.player_id,
            "player_name":  self.player.name,
            "voice_status": voice_status,
            "channel_id":   voice_channel,
        })

    # ── Keepalive ─────────────────────────────────────────────────────────────

    async def _check_keepalive(self) -> None:
        now = time.monotonic()
        if now - self._last_ping_sent >= PING_INTERVAL:
            await self.send({"type": "ping"})
            self._last_ping_sent = now
        if now - self._last_pong_recv > PING_TIMEOUT and self.handshook:
            log.warning("%s timed out", self.addr)
            raise ConnectionResetError("ping timeout")

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def _cleanup(self) -> None:
        if self.player:
            self._game_state.remove_player(self.player.player_id)
            self._server.unregister_connection(self.player.player_id)
        try:
            self._writer.close()
        except Exception:
            pass


# ── Game server ───────────────────────────────────────────────────────────────

class GameServer:
    """Manages all connected clients and the shared game state."""

    def __init__(self) -> None:
        self._game_state = ServerGameState()
        # player_id → ClientConnection (only players who have sent 'join')
        self._connections: dict[int, ClientConnection] = {}
        self._lock = asyncio.Lock()

    def register_connection(self, player_id: int, conn: ClientConnection) -> None:
        self._connections[player_id] = conn

    def unregister_connection(self, player_id: int) -> None:
        self._connections.pop(player_id, None)

    async def broadcast(self, msg: dict) -> None:
        """Send *msg* to every connected, joined player."""
        data = (json.dumps(msg) + "\n").encode("utf-8")
        dead = []
        for pid, conn in list(self._connections.items()):
            try:
                conn._writer.write(data)
                await conn._writer.drain()
            except (OSError, BrokenPipeError):
                dead.append(pid)
        for pid in dead:
            self._connections.pop(pid, None)

    async def _tick_loop(self) -> None:
        """Run the authoritative game-state loop at TICK_RATE Hz."""
        interval = 1.0 / TICK_RATE
        while True:
            await asyncio.sleep(interval)
            if self._game_state.player_count() == 0:
                continue
            self._game_state.apply_inputs()
            snapshot = self._game_state.snapshot()
            await self.broadcast(snapshot)

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        conn = ClientConnection(reader, writer, self._game_state, self)
        await conn.handle()

    async def run(self) -> None:
        server = await asyncio.start_server(
            self.handle_client,
            SERVER_HOST,
            SERVER_PORT,
        )
        addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
        log.info(
            "Quad Fighter server  version=%s  protocol=%s  build=%s",
            SERVER_VERSION,
            PROTOCOL_VERSION,
            __import__("version").BUILD_NUMBER,
        )
        log.info("listening on %s  max_players=%d  tick_rate=%d Hz", addrs, MAX_PLAYERS, TICK_RATE)

        asyncio.ensure_future(self._tick_loop())

        async with server:
            await server.serve_forever()


# ── Entry point ───────────────────────────────────────────────────────────────

def _handle_signal(sig, frame):  # noqa: ANN001
    log.info("received signal %s – shutting down", sig)
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    try:
        asyncio.run(GameServer().run())
    except KeyboardInterrupt:
        log.info("server stopped")
