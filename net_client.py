"""net_client.py: Non-blocking TCP client for Quad Fighter network multiplayer.

Runs the socket I/O on a background daemon thread so the game loop stays at
60 FPS regardless of network latency.

Usage::

    client = NetClient()
    client.connect("192.168.1.64", 7777)   # non-blocking
    client.send_input({"punch": True})
    state = client.latest_state()           # may be None if nothing received yet
    client.disconnect()
"""

import json
import logging
import queue
import socket
import threading
import uuid

from version import GAME_VERSION, PROTOCOL_VERSION

log = logging.getLogger(__name__)

# ── Status strings ────────────────────────────────────────────────────────────

STATUS_DISCONNECTED  = "Disconnected"
STATUS_CONNECTING    = "Connecting…"
STATUS_CONNECTED     = "Connected"
STATUS_VERSION_ERROR = "Version mismatch"
STATUS_REJECTED      = "Rejected"
STATUS_ERROR         = "Error"

# How many bytes to read per recv() call
_RECV_CHUNK = 4096


class NetClient:
    """Thread-safe, non-blocking TCP client.

    All public methods are safe to call from the main game thread.
    """

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Latest decoded game-state snapshot (replaced atomically via lock)
        self._state_lock = threading.Lock()
        self._latest_state: dict | None = None

        # Status string (written by background thread, read by game thread)
        self._status_lock = threading.Lock()
        self._status: str = STATUS_DISCONNECTED

        # Queued outbound messages (main thread enqueues, bg thread drains)
        self._send_queue: queue.SimpleQueue = queue.SimpleQueue()

        # Assigned server-side player ID (set after welcome message)
        self._player_id: int | None = None

        # Rejection / error message from the server
        self._reject_message: str = ""

        # Unique client identifier (stays the same for the lifetime of this object)
        self._client_id = str(uuid.uuid4())

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    @property
    def player_id(self) -> int | None:
        return self._player_id

    @property
    def reject_message(self) -> str:
        return self._reject_message

    def is_connected(self) -> bool:
        return self.status == STATUS_CONNECTED

    def connect(self, host: str, port: int) -> None:
        """Start a background connection attempt.  Returns immediately."""
        if self._thread and self._thread.is_alive():
            self.disconnect()

        self._stop_event.clear()
        self._set_status(STATUS_CONNECTING)
        self._player_id = None
        self._reject_message = ""

        self._thread = threading.Thread(
            target=self._run,
            args=(host, port),
            daemon=True,
            name="net-client",
        )
        self._thread.start()

    def disconnect(self) -> None:
        """Request the background thread to close the connection."""
        self._stop_event.set()
        if self._sock:
            try:
                self._send_queue.put({"type": "disconnect"})
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
        self._set_status(STATUS_DISCONNECTED)

    def send_input(self, inputs: dict) -> None:
        """Enqueue an input snapshot to be sent to the server."""
        if self.is_connected():
            self._send_queue.put({"type": "input", "inputs": inputs})

    def send_voice_state(self, voice_status: str, channel_id: str = "") -> None:
        """Notify the server of a Discord voice-state change.

        *voice_status* should be one of the STATUS_* strings from
        discord_voice.py (e.g. ``"In Channel"``, ``"Disconnected"``).
        The server broadcasts a ``voice_event`` to all connected players.
        """
        if self.is_connected():
            self._send_queue.put({
                "type":         "voice_state",
                "voice_status": voice_status,
                "channel_id":   channel_id,
            })

    def latest_state(self) -> dict | None:
        """Return the most recent state snapshot from the server, or None."""
        with self._state_lock:
            return self._latest_state

    # ── Background thread ─────────────────────────────────────────────────────

    def _set_status(self, status: str) -> None:
        with self._status_lock:
            self._status = status

    def _run(self, host: str, port: int) -> None:
        """Main background loop: connect → handshake → send/receive."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((host, port))
            sock.settimeout(0.1)  # non-blocking reads from here on
            self._sock = sock
        except OSError as exc:
            log.warning("connect failed: %s", exc)
            self._set_status(STATUS_ERROR)
            self._reject_message = str(exc)
            return

        # Send hello / handshake
        self._send_raw(sock, {
            "type": "hello",
            "game_version": GAME_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "client_id": self._client_id,
        })

        buf = ""
        while not self._stop_event.is_set():
            # --- Receive ---
            try:
                chunk = sock.recv(_RECV_CHUNK)
                if not chunk:
                    break  # server closed connection
                buf += chunk.decode("utf-8", errors="replace")
                # Messages are newline-delimited JSON
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._handle_message(json.loads(line))
            except socket.timeout:
                pass  # normal; just means no data right now
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("recv error: %s", exc)
                break

            # --- Send queued messages ---
            while not self._send_queue.empty():
                msg = self._send_queue.get_nowait()
                try:
                    self._send_raw(sock, msg)
                except OSError as exc:
                    log.warning("send error: %s", exc)
                    self._stop_event.set()
                    break

        # Cleanup
        try:
            sock.close()
        except OSError:
            pass
        self._sock = None
        if self.status not in (STATUS_VERSION_ERROR, STATUS_REJECTED):
            self._set_status(STATUS_DISCONNECTED)

    def _send_raw(self, sock: socket.socket, msg: dict) -> None:
        data = (json.dumps(msg) + "\n").encode("utf-8")
        sock.sendall(data)

    def _handle_message(self, msg: dict) -> None:
        mtype = msg.get("type")

        if mtype == "welcome":
            self._set_status(STATUS_CONNECTED)
            log.info(
                "welcomed by server  server_version=%s  protocol=%s",
                msg.get("server_version"),
                msg.get("protocol_version"),
            )
            # Auto-send join immediately after handshake is confirmed
            self._send_queue.put({"type": "join", "player_name": "Player"})

        elif mtype == "reject":
            reason  = msg.get("reason", "")
            message = msg.get("message", "Connection rejected.")
            self._reject_message = message
            if reason == "version_mismatch":
                self._set_status(STATUS_VERSION_ERROR)
            else:
                self._set_status(STATUS_REJECTED)
            log.warning("rejected by server: %s – %s", reason, message)
            self._stop_event.set()

        elif mtype == "state":
            with self._state_lock:
                self._latest_state = msg

        elif mtype == "event":
            if msg.get("name") == "joined":
                self._player_id = msg.get("player_id")
                log.info("joined game as player_id=%s", self._player_id)
            else:
                log.debug("server event: %s", msg)

        elif mtype == "voice_event":
            log.info(
                "player %s voice_state: status=%r channel=%r",
                msg.get("player_id"),
                msg.get("voice_status"),
                msg.get("channel_id"),
            )

        elif mtype == "ping":
            # Respond immediately with a pong
            if self._sock:
                try:
                    self._send_raw(self._sock, {"type": "pong"})
                except OSError:
                    pass
