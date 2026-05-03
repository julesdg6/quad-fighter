"""discord_voice.py: Discord voice-chat integration for Quad Fighter.

Connects to the Discord desktop application running on the local machine
via Discord's IPC socket (the same mechanism used by Rich Presence) and
joins / leaves a voice channel on behalf of the player.

No extra Python dependencies are required – the IPC protocol is implemented
here using only the standard library (socket, struct, json, threading).

Platforms
---------
macOS / Linux:  Unix-domain socket at ``$XDG_RUNTIME_DIR/discord-ipc-{n}``
                or ``/tmp/discord-ipc-{n}`` (indices 0-9 are tried).
Windows:        Named-pipe at ``\\\\.\\pipe\\discord-ipc-{n}``; requires
                Python 3.9+ on Windows 10 build 17063+ (AF_UNIX support).

Usage::

    voice = DiscordVoice()
    voice.connect(client_id="123456789012345678", channel_id="987654321")
    # … in game loop:
    print(voice.status)   # e.g. "In Channel"
    voice.disconnect()

The Discord application must be running on the player's machine and the
Application ID (client_id) must match a registered Discord application.
"""

import json
import logging
import os
import socket
import struct
import sys
import threading
import uuid

log = logging.getLogger(__name__)

# ── IPC opcodes ───────────────────────────────────────────────────────────────

_OP_HANDSHAKE = 0
_OP_FRAME     = 1
_OP_CLOSE     = 2
_OP_PING      = 3
_OP_PONG      = 4

# ── Status strings ────────────────────────────────────────────────────────────

STATUS_DISCONNECTED       = "Disconnected"
STATUS_CONNECTING         = "Connecting…"
STATUS_READY              = "Discord Connected"
STATUS_IN_CHANNEL         = "In Channel"
STATUS_DISCORD_NOT_FOUND  = "Discord not running"
STATUS_ERROR              = "Error"


# ── IPC socket path helpers ───────────────────────────────────────────────────

def _ipc_paths() -> list[str]:
    """Return candidate IPC socket / pipe paths for indices 0-9."""
    paths: list[str] = []
    if sys.platform == "win32":
        for n in range(10):
            paths.append(f"\\\\.\\pipe\\discord-ipc-{n}")
    else:
        # Unix: check several candidate base directories
        bases = [
            os.environ.get("XDG_RUNTIME_DIR"),
            os.environ.get("TMPDIR"),
            os.environ.get("TMP"),
            os.environ.get("TEMP"),
            "/run/user/" + str(os.getuid()) if hasattr(os, "getuid") else None,
            "/tmp",
        ]
        for base in bases:
            if base:
                for n in range(10):
                    paths.append(os.path.join(base, f"discord-ipc-{n}"))
    return paths


def _open_ipc_socket() -> socket.socket | None:
    """Try each candidate path and return the first socket that connects."""
    for path in _ipc_paths():
        try:
            if sys.platform == "win32":
                # AF_UNIX works on modern Windows (build 17063+)
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            else:
                if not os.path.exists(path):
                    continue
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(path)
            return sock
        except (OSError, AttributeError):
            pass
    return None


# ── Wire format helpers ───────────────────────────────────────────────────────

def _encode(opcode: int, payload: dict) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return struct.pack("<II", opcode, len(body)) + body


def _recv_msg(sock: socket.socket) -> dict | None:
    """Read one framed IPC message; returns None on EOF / error."""
    header = b""
    while len(header) < 8:
        try:
            chunk = sock.recv(8 - len(header))
        except socket.timeout:
            return None
        if not chunk:
            return None
        header += chunk
    opcode, length = struct.unpack("<II", header)

    body = b""
    while len(body) < length:
        try:
            chunk = sock.recv(length - len(body))
        except socket.timeout:
            return None
        if not chunk:
            return None
        body += chunk

    try:
        msg = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    msg["__opcode"] = opcode
    return msg


# ── DiscordVoice ──────────────────────────────────────────────────────────────

class DiscordVoice:
    """Thread-safe Discord IPC voice-chat controller.

    All public methods are safe to call from the main game thread.
    The IPC I/O runs on a daemon background thread.
    """

    def __init__(self) -> None:
        self._client_id:  str = ""
        self._channel_id: str = ""

        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._status_lock = threading.Lock()
        self._status: str = STATUS_DISCONNECTED

        self._error_message: str = ""
        self._discord_username: str = ""

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    @property
    def error_message(self) -> str:
        return self._error_message

    @property
    def discord_username(self) -> str:
        return self._discord_username

    def is_connected(self) -> bool:
        """True when the IPC handshake with Discord has completed."""
        return self.status in (STATUS_READY, STATUS_IN_CHANNEL)

    def connect(self, client_id: str, channel_id: str = "") -> None:
        """Connect to the local Discord application.

        Starts a background thread – returns immediately.
        If already connected, the old connection is closed first.
        """
        self.disconnect()
        self._client_id  = client_id.strip()
        self._channel_id = channel_id.strip()
        if not self._client_id:
            self._error_message = "No Application ID configured."
            self._set_status(STATUS_ERROR)
            return

        self._stop_event.clear()
        self._error_message = ""
        self._discord_username = ""
        self._set_status(STATUS_CONNECTING)

        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="discord-voice",
        )
        self._thread.start()

    def disconnect(self) -> None:
        """Close the IPC connection and stop the background thread."""
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._set_status(STATUS_DISCONNECTED)

    def join_channel(self, channel_id: str) -> None:
        """Ask Discord to move the user into *channel_id*."""
        self._channel_id = channel_id.strip()
        if self.is_connected() and self._sock and self._channel_id:
            self._cmd_voice_channel_select(self._sock, self._channel_id)

    def leave_channel(self) -> None:
        """Ask Discord to remove the user from the current voice channel."""
        if self.is_connected() and self._sock:
            self._cmd_voice_channel_select(self._sock, None)

    # ── Background thread ─────────────────────────────────────────────────────

    def _set_status(self, status: str) -> None:
        with self._status_lock:
            self._status = status

    def _run(self) -> None:
        sock = _open_ipc_socket()
        if sock is None:
            self._error_message = "Discord desktop app not found."
            self._set_status(STATUS_DISCORD_NOT_FOUND)
            return

        self._sock = sock
        try:
            self._handshake(sock)
            self._event_loop(sock)
        except OSError as exc:
            log.warning("discord voice: socket error: %s", exc)
            self._error_message = str(exc)
            self._set_status(STATUS_ERROR)
        finally:
            try:
                sock.close()
            except OSError:
                pass
            self._sock = None
            if self.status not in (
                STATUS_DISCONNECTED, STATUS_ERROR, STATUS_DISCORD_NOT_FOUND,
            ):
                self._set_status(STATUS_DISCONNECTED)

    def _handshake(self, sock: socket.socket) -> None:
        """Send the IPC handshake and wait for the READY dispatch."""
        sock.sendall(_encode(_OP_HANDSHAKE, {
            "v": 1,
            "client_id": self._client_id,
        }))
        # Wait for READY
        sock.settimeout(5.0)
        while not self._stop_event.is_set():
            msg = _recv_msg(sock)
            if msg is None:
                raise OSError("Connection lost waiting for READY")
            evt = msg.get("evt")
            if evt == "READY":
                user = msg.get("data", {}).get("user", {})
                self._discord_username = user.get("username", "")
                log.info(
                    "discord voice: READY  user=%s#%s",
                    user.get("username"), user.get("discriminator"),
                )
                self._set_status(STATUS_READY)
                # Restore non-blocking timeout for the event loop
                sock.settimeout(1.0)
                return
            elif evt == "ERROR":
                err = msg.get("data", {}).get("message", "Unknown error")
                self._error_message = err
                raise OSError(f"Discord IPC error: {err}")

    def _event_loop(self, sock: socket.socket) -> None:
        """Join channel (if configured) and process events until stopped."""
        if self._channel_id:
            self._cmd_voice_channel_select(sock, self._channel_id)

        sock.settimeout(1.0)
        while not self._stop_event.is_set():
            msg = _recv_msg(sock)
            if msg is None:
                continue
            self._handle_dispatch(msg)

    # ── Discord RPC commands ──────────────────────────────────────────────────

    def _send_frame(self, sock: socket.socket, payload: dict) -> None:
        sock.sendall(_encode(_OP_FRAME, payload))

    def _cmd_voice_channel_select(
        self,
        sock: socket.socket,
        channel_id: str | None,
    ) -> None:
        """Send SELECT_VOICE_CHANNEL to join or leave a channel."""
        self._send_frame(sock, {
            "cmd":   "SELECT_VOICE_CHANNEL",
            "args":  {"channel_id": channel_id, "force": True},
            "nonce": str(uuid.uuid4()),
        })
        log.info("discord voice: SELECT_VOICE_CHANNEL  channel_id=%s", channel_id)

    # ── Event / response handling ─────────────────────────────────────────────

    def _handle_dispatch(self, msg: dict) -> None:
        evt = msg.get("evt")
        cmd = msg.get("cmd")
        data = msg.get("data") or {}

        if evt == "ERROR":
            self._error_message = data.get("message", "Unknown error")
            log.warning("discord voice: error event: %s", self._error_message)

        elif evt == "VOICE_CHANNEL_SELECT" or cmd == "SELECT_VOICE_CHANNEL":
            channel_id = data.get("channel_id") or data.get("id")
            if channel_id:
                self._set_status(STATUS_IN_CHANNEL)
                log.info("discord voice: joined channel %s", channel_id)
            else:
                self._set_status(STATUS_READY)
                log.info("discord voice: left voice channel")

        else:
            log.debug("discord voice: unhandled dispatch  evt=%s cmd=%s", evt, cmd)
