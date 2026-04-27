"""version.py: Shared version and build constants for Quad Fighter client and server."""

# Human-readable game version shown in menus and logs
GAME_VERSION = "0.4.0"

# Server build version (may lag behind GAME_VERSION between releases)
SERVER_VERSION = "0.4.0"

# Wire-protocol version.  Increment whenever the JSON message schema changes
# in a backwards-incompatible way.  Both client and server must agree.
PROTOCOL_VERSION = 1

# Monotonic build counter incremented on each release
BUILD_NUMBER = 1
