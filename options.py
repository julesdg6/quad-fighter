"""options.py: Options / settings screen for Quad Fighter."""

import pygame

from settings import Settings, CONTROLLER_BUTTON_NAMES, AXIS_DEADZONE
from version import GAME_VERSION, PROTOCOL_VERSION, BUILD_NUMBER

# ── Layout constants ──────────────────────────────────────────────────────────

FONT_SIZE_HEADER  = 52
FONT_SIZE_SECTION = 22
FONT_SIZE_ITEM    = 20
FONT_SIZE_HINT    = 18

ITEM_HEIGHT    = 28        # px per row
VIEWPORT_TOP   = 60        # y where the scrollable list starts
VIEWPORT_BOT   = 560       # y where it ends
VIEWPORT_H     = VIEWPORT_BOT - VIEWPORT_TOP
MAX_VISIBLE    = VIEWPORT_H // ITEM_HEIGHT   # ~18

SLIDER_WIDTH   = 140
SLIDER_HEIGHT  = 10
VOLUME_STEP    = 5         # change per left/right press

# Network text-input limits
MAX_IP_LENGTH   = 39       # max IPv6 address string length
MAX_PORT_DIGITS = 5        # max digits in a port number (0–65535)

# ── Colours ───────────────────────────────────────────────────────────────────

BG_TOP    = (6, 6, 20)
BG_BOT    = (18, 12, 36)
COL_HDR   = (230, 220, 255)
COL_SEC   = (130, 110, 180)
COL_ITEM  = (200, 200, 220)
COL_SEL   = (255, 240, 80)
COL_DIM   = (100, 90, 130)
COL_TRACK = (50, 40, 80)
COL_FILL  = (140, 80, 220)
COL_HINT  = (110, 100, 140)
COL_WAIT  = (255, 160, 60)

# ── Item definitions ──────────────────────────────────────────────────────────

def _build_items() -> list:
    return [
        {"type": "section", "label": "AUDIO"},
        {"type": "audio",   "key": "music_volume", "label": "Music Volume"},
        {"type": "audio",   "key": "sfx_volume",   "label": "SFX Volume"},
        {"type": "section", "label": "KEYBOARD CONTROLS"},
        {"type": "kb_bind", "action": "move_left",   "label": "Move Left"},
        {"type": "kb_bind", "action": "move_right",  "label": "Move Right"},
        {"type": "kb_bind", "action": "move_up",     "label": "Move Up (Lane)"},
        {"type": "kb_bind", "action": "move_down",   "label": "Move Down (Lane)"},
        {"type": "kb_bind", "action": "jump",        "label": "Jump"},
        {"type": "kb_bind", "action": "punch",       "label": "Punch"},
        {"type": "kb_bind", "action": "kick",        "label": "Kick"},
        {"type": "kb_bind", "action": "crouch",      "label": "Crouch"},
        {"type": "kb_bind", "action": "grab",        "label": "Grab"},
        {"type": "kb_bind", "action": "start_pause", "label": "Start / Pause"},
        {"type": "section", "label": "CONTROLLER"},
        {"type": "ctrl_bind", "action": "jump",        "label": "Jump"},
        {"type": "ctrl_bind", "action": "punch",       "label": "Punch"},
        {"type": "ctrl_bind", "action": "kick",        "label": "Kick"},
        {"type": "ctrl_bind", "action": "crouch",      "label": "Crouch"},
        {"type": "ctrl_bind", "action": "grab",        "label": "Grab"},
        {"type": "ctrl_bind", "action": "start_pause", "label": "Start / Pause"},
        {"type": "section",    "label": "NETWORK"},
        {"type": "net_text",   "key": "server_ip",   "label": "Server IP"},
        {"type": "net_port",   "key": "server_port", "label": "Server Port"},
        {"type": "net_action", "action": "connect",  "label": "Connect"},
        {"type": "net_status", "label": "Status"},
        {"type": "net_info",   "label": "Version"},
        {"type": "back", "label": "Back"},
    ]


def _is_selectable(item: dict) -> bool:
    return item["type"] not in ("section", "net_status", "net_info")


# ── Helper: draw gradient background ─────────────────────────────────────────

def _draw_bg(surface: pygame.Surface) -> None:
    w, h = surface.get_size()
    for y in range(h):
        t = y / h
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (w, y))


def _key_name(key_const: int) -> str:
    """Return a human-readable name for a pygame key constant."""
    name = pygame.key.name(key_const)
    return name.upper() if name else f"KEY{key_const}"


def _btn_name(btn_idx: int) -> str:
    return CONTROLLER_BUTTON_NAMES.get(btn_idx, f"Btn {btn_idx}")


# ── OptionsScreen ─────────────────────────────────────────────────────────────

class OptionsScreen:
    """Blocking options/settings screen.

    Call ``run(acid_machine)`` to show the screen.  The method modifies
    *settings* in-place.  *acid_machine* may be None; when provided its
    volume is updated live as the user adjusts the slider.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
        fps: int,
        settings: Settings,
        joystick,          # pygame.joystick.Joystick or None
        net_client=None,   # net_client.NetClient or None
    ):
        self.screen   = screen
        self.width    = width
        self.height   = height
        self.fps      = fps
        self.settings = settings
        self.joystick = joystick
        self.net_client = net_client
        self.clock    = pygame.time.Clock()

        self._bg = pygame.Surface((width, height))
        _draw_bg(self._bg)

        self._font_hdr  = pygame.font.SysFont(None, FONT_SIZE_HEADER,  bold=True)
        self._font_sec  = pygame.font.SysFont(None, FONT_SIZE_SECTION, bold=True)
        self._font_item = pygame.font.SysFont(None, FONT_SIZE_ITEM)
        self._font_hint = pygame.font.SysFont(None, FONT_SIZE_HINT)

        self._items     = _build_items()
        # Indices of selectable items (for cursor navigation)
        self._sel_idx   = [i for i, it in enumerate(self._items) if _is_selectable(it)]
        self._cursor    = 0          # index into self._sel_idx
        self._scroll    = 0          # first item index shown in viewport

        # Remapping state
        self._waiting   = None       # None | "key" | "button" | "net_text" | "net_port"
        self._wait_action = None     # action name being rebound
        self._text_buf   = ""        # buffer for net_text / net_port input

        # Controller repeat: (action, frames_held) for held D-pad / stick
        self._ctrl_held: dict = {}
        self._prev_hat  = (0, 0)
        self._prev_stick = (0.0, 0.0)
        self._sfx = None  # set by run()

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self, acid_machine=None, sfx=None) -> None:
        """Block until the user leaves options.  Saves settings on exit."""
        self._sfx = sfx
        while True:
            self.clock.tick(self.fps)
            for event in pygame.event.get():
                result = self._handle_event(event, acid_machine)
                if result == "back":
                    self.settings.save()
                    return
            self._draw()
            pygame.display.flip()

    # ── Event handling ────────────────────────────────────────────────────────

    def _handle_event(self, event, acid_machine) -> str | None:
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit

        # ---- Waiting for a key rebind ----------------------------------------
        if self._waiting == "key":
            if event.type == pygame.KEYDOWN:
                if event.key != pygame.K_ESCAPE:
                    self.settings.keyboard[self._wait_action] = event.key
                self._waiting = None
                self._wait_action = None
            return None

        # ---- Waiting for a controller button rebind --------------------------
        if self._waiting == "button":
            if event.type == pygame.JOYBUTTONDOWN:
                self.settings.controller[self._wait_action] = event.button
                self._waiting = None
                self._wait_action = None
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._waiting = None
                self._wait_action = None
            return None

        # ---- Waiting for network text/port input ----------------------------
        if self._waiting in ("net_text", "net_port"):
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Cancel – discard buffer
                    self._waiting = None
                    self._wait_action = None
                    self._text_buf = ""
                elif event.key == pygame.K_RETURN:
                    # Commit
                    if self._waiting == "net_text":
                        if self._text_buf:
                            self.settings.server_ip = self._text_buf
                    elif self._waiting == "net_port":
                        try:
                            port = int(self._text_buf)
                            if 1 <= port <= 65535:
                                self.settings.server_port = port
                        except ValueError:
                            pass
                    self._waiting = None
                    self._wait_action = None
                    self._text_buf = ""
                elif event.key == pygame.K_BACKSPACE:
                    self._text_buf = self._text_buf[:-1]
                else:
                    ch = event.unicode
                    if self._waiting == "net_port":
                        if ch.isdigit() and len(self._text_buf) < MAX_PORT_DIGITS:
                            self._text_buf += ch
                    else:
                        if ch and ch.isprintable() and len(self._text_buf) < MAX_IP_LENGTH:
                            self._text_buf += ch
            return None

        # ---- Normal navigation -----------------------------------------------
        if event.type == pygame.KEYDOWN:
            return self._handle_key(event.key, acid_machine)

        if event.type == pygame.JOYBUTTONDOWN:
            return self._handle_joy_button(event.button, acid_machine)

        if event.type == pygame.JOYHATMOTION:
            hx, hy = event.value
            ph, py_ = self._prev_hat
            self._prev_hat = (hx, hy)
            if hy > 0 and py_ <= 0:
                self._move_cursor(-1)
            elif hy < 0 and py_ >= 0:
                self._move_cursor(1)
            if hx < 0 and ph >= 0:
                return self._adjust_left(acid_machine)
            elif hx > 0 and ph <= 0:
                return self._adjust_right(acid_machine)

        if event.type == pygame.JOYAXISMOTION:
            if event.axis == 1:
                prev = self._prev_stick[1]
                self._prev_stick = (self._prev_stick[0], event.value)
                if event.value < -AXIS_DEADZONE and prev >= -AXIS_DEADZONE:
                    self._move_cursor(-1)
                elif event.value > AXIS_DEADZONE and prev <= AXIS_DEADZONE:
                    self._move_cursor(1)
            elif event.axis == 0:
                prev = self._prev_stick[0]
                self._prev_stick = (event.value, self._prev_stick[1])
                if event.value < -AXIS_DEADZONE and prev >= -AXIS_DEADZONE:
                    return self._adjust_left(acid_machine)
                elif event.value > AXIS_DEADZONE and prev <= AXIS_DEADZONE:
                    return self._adjust_right(acid_machine)

        return None

    def _handle_key(self, key: int, acid_machine) -> str | None:
        if key == pygame.K_ESCAPE:
            return "back"
        if key == pygame.K_UP:
            self._move_cursor(-1)
        elif key == pygame.K_DOWN:
            self._move_cursor(1)
        elif key == pygame.K_LEFT:
            return self._adjust_left(acid_machine)
        elif key == pygame.K_RIGHT:
            return self._adjust_right(acid_machine)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            return self._activate(acid_machine)
        return None

    def _handle_joy_button(self, button: int, acid_machine) -> str | None:
        back_btn = self.settings.controller.get("back", 6)
        if button == back_btn:
            return "back"
        a_btn = self.settings.controller.get("jump", 0)  # A = confirm
        if button == a_btn:
            return self._activate(acid_machine)
        return None

    # ── Cursor movement ───────────────────────────────────────────────────────

    def _move_cursor(self, direction: int) -> None:
        self._cursor = (self._cursor + direction) % len(self._sel_idx)
        self._ensure_visible()

    def _ensure_visible(self) -> None:
        item_idx = self._sel_idx[self._cursor]
        if item_idx < self._scroll:
            self._scroll = item_idx
        elif item_idx >= self._scroll + MAX_VISIBLE:
            self._scroll = item_idx - MAX_VISIBLE + 1
        self._scroll = max(0, min(self._scroll, len(self._items) - MAX_VISIBLE))

    # ── Value adjustment ──────────────────────────────────────────────────────

    def _current_item(self) -> dict:
        return self._items[self._sel_idx[self._cursor]]

    def _adjust_left(self, acid_machine) -> str | None:
        item = self._current_item()
        if item["type"] == "audio":
            val = getattr(self.settings, item["key"])
            setattr(self.settings, item["key"], max(0, val - VOLUME_STEP))
            self._apply_volume(acid_machine)
        return None

    def _adjust_right(self, acid_machine) -> str | None:
        item = self._current_item()
        if item["type"] == "audio":
            val = getattr(self.settings, item["key"])
            setattr(self.settings, item["key"], min(100, val + VOLUME_STEP))
            self._apply_volume(acid_machine)
        return None

    def _activate(self, acid_machine) -> str | None:
        item = self._current_item()
        if item["type"] == "back":
            return "back"
        if item["type"] == "kb_bind":
            self._waiting = "key"
            self._wait_action = item["action"]
        elif item["type"] == "ctrl_bind":
            self._waiting = "button"
            self._wait_action = item["action"]
        elif item["type"] == "net_text":
            self._waiting = "net_text"
            self._wait_action = item["key"]
            self._text_buf = self.settings.server_ip
        elif item["type"] == "net_port":
            self._waiting = "net_port"
            self._wait_action = item["key"]
            self._text_buf = str(self.settings.server_port)
        elif item["type"] == "net_action":
            self._handle_net_action(item["action"])
        return None

    def _handle_net_action(self, action: str) -> None:
        """Connect or disconnect from the server."""
        if self.net_client is None:
            return
        if action == "connect":
            if self.net_client.is_connected():
                self.net_client.disconnect()
            else:
                self.net_client.connect(
                    self.settings.server_ip,
                    self.settings.server_port,
                )

    def _apply_volume(self, acid_machine) -> None:
        if acid_machine is not None:
            acid_machine.set_volume(self.settings.music_volume / 100.0)
        if self._sfx is not None:
            self._sfx.set_volume(self.settings.sfx_volume / 100.0)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.screen.blit(self._bg, (0, 0))

        # Header
        hdr = self._font_hdr.render("OPTIONS", True, COL_HDR)
        self.screen.blit(hdr, (self.width // 2 - hdr.get_width() // 2, 12))

        # Scrollable item list
        cx = self.width // 2
        end = min(self._scroll + MAX_VISIBLE, len(self._items))
        for rank, idx in enumerate(range(self._scroll, end)):
            item   = self._items[idx]
            screen_y = VIEWPORT_TOP + rank * ITEM_HEIGHT
            selected = (
                _is_selectable(item)
                and self._sel_idx[self._cursor] == idx
            )
            self._draw_item(item, screen_y, cx, selected)

        # Scroll indicators
        if self._scroll > 0:
            arrow = self._font_hint.render("▲  scroll up", True, COL_HINT)
            self.screen.blit(arrow, (cx - arrow.get_width() // 2, VIEWPORT_TOP - 18))
        if self._scroll + MAX_VISIBLE < len(self._items):
            arrow = self._font_hint.render("▼  scroll down", True, COL_HINT)
            self.screen.blit(arrow, (cx - arrow.get_width() // 2, VIEWPORT_BOT + 2))

        # Bottom navigation hint
        if self._waiting == "key":
            msg = f"Press a key for  [{self._wait_action.replace('_', ' ').upper()}]  (Esc to cancel)"
            surf = self._font_hint.render(msg, True, COL_WAIT)
            self.screen.blit(surf, (cx - surf.get_width() // 2, self.height - 28))
        elif self._waiting == "button":
            msg = f"Press a button for  [{self._wait_action.replace('_', ' ').upper()}]  (Esc to cancel)"
            surf = self._font_hint.render(msg, True, COL_WAIT)
            self.screen.blit(surf, (cx - surf.get_width() // 2, self.height - 28))
        elif self._waiting in ("net_text", "net_port"):
            label = "IP" if self._waiting == "net_text" else "Port"
            msg = f"Enter {label}: {self._text_buf}_  (Enter confirm  Esc cancel)"
            surf = self._font_hint.render(msg, True, COL_WAIT)
            self.screen.blit(surf, (cx - surf.get_width() // 2, self.height - 28))
        else:
            hint = "↑↓ Navigate   ←→ Adjust   Enter/A Select   Esc/Back Return"
            surf = self._font_hint.render(hint, True, COL_HINT)
            self.screen.blit(surf, (cx - surf.get_width() // 2, self.height - 28))

    def _draw_item(self, item: dict, y: int, cx: int, selected: bool) -> None:
        itype = item["type"]

        if itype == "section":
            label = f"── {item['label']} ──"
            surf = self._font_sec.render(label, True, COL_SEC)
            self.screen.blit(surf, (cx - surf.get_width() // 2, y + 4))
            return

        col = COL_SEL if selected else COL_ITEM

        if itype == "audio":
            val = getattr(self.settings, item["key"])
            label_surf = self._font_item.render(item["label"], True, col)
            # Left-align label
            label_x = cx - 200
            self.screen.blit(label_surf, (label_x, y + 2))
            # Slider
            track_x = cx - 20
            track_y = y + ITEM_HEIGHT // 2 - SLIDER_HEIGHT // 2
            pygame.draw.rect(self.screen, COL_TRACK, (track_x, track_y, SLIDER_WIDTH, SLIDER_HEIGHT), border_radius=4)
            fill_w = int(SLIDER_WIDTH * val / 100)
            if fill_w > 0:
                pygame.draw.rect(self.screen, COL_FILL, (track_x, track_y, fill_w, SLIDER_HEIGHT), border_radius=4)
            # Percentage text
            pct_surf = self._font_item.render(f"{val}%", True, col)
            self.screen.blit(pct_surf, (track_x + SLIDER_WIDTH + 8, y + 2))

        elif itype == "kb_bind":
            label_surf = self._font_item.render(item["label"], True, col)
            label_x = cx - 200
            self.screen.blit(label_surf, (label_x, y + 2))
            key_name = _key_name(self.settings.keyboard.get(item["action"], 0))
            remapping_this = self._waiting == "key" and self._wait_action == item["action"]
            if remapping_this:
                key_name = "..."
            val_col = COL_WAIT if remapping_this else col
            val_surf = self._font_item.render(key_name, True, val_col)
            self.screen.blit(val_surf, (cx + 60, y + 2))

        elif itype == "ctrl_bind":
            label_surf = self._font_item.render(item["label"], True, col)
            label_x = cx - 200
            self.screen.blit(label_surf, (label_x, y + 2))
            btn_idx = self.settings.controller.get(item["action"], -1)
            btn_name = _btn_name(btn_idx) if btn_idx >= 0 else "—"
            remapping_this = self._waiting == "button" and self._wait_action == item["action"]
            if remapping_this:
                btn_name = "..."
            val_col = COL_WAIT if remapping_this else col
            val_surf = self._font_item.render(btn_name, True, val_col)
            self.screen.blit(val_surf, (cx + 60, y + 2))

        elif itype == "back":
            surf = self._font_item.render(item["label"], True, col)
            self.screen.blit(surf, (cx - surf.get_width() // 2, y + 2))
            if selected:
                # Simple left arrow indicator
                arrow = self._font_item.render("◄", True, COL_SEL)
                self.screen.blit(arrow, (cx - surf.get_width() // 2 - 22, y + 2))

        elif itype == "net_text":
            label_surf = self._font_item.render(item["label"], True, col)
            self.screen.blit(label_surf, (cx - 200, y + 2))
            editing = self._waiting == "net_text" and self._wait_action == item["key"]
            display = (self._text_buf + "_") if editing else self.settings.server_ip
            val_col = COL_WAIT if editing else col
            val_surf = self._font_item.render(display, True, val_col)
            self.screen.blit(val_surf, (cx + 60, y + 2))

        elif itype == "net_port":
            label_surf = self._font_item.render(item["label"], True, col)
            self.screen.blit(label_surf, (cx - 200, y + 2))
            editing = self._waiting == "net_port" and self._wait_action == item["key"]
            display = (self._text_buf + "_") if editing else str(self.settings.server_port)
            val_col = COL_WAIT if editing else col
            val_surf = self._font_item.render(display, True, val_col)
            self.screen.blit(val_surf, (cx + 60, y + 2))

        elif itype == "net_action":
            action = item.get("action", "")
            if self.net_client is not None and self.net_client.is_connected():
                label_text = "Disconnect"
            else:
                label_text = "Connect"
            surf = self._font_item.render(label_text, True, col)
            self.screen.blit(surf, (cx - 200, y + 2))
            if selected:
                arrow = self._font_item.render("►", True, COL_SEL)
                self.screen.blit(arrow, (cx - 200 - 22, y + 2))

        elif itype == "net_status":
            label_surf = self._font_sec.render("Status:", True, COL_SEC)
            self.screen.blit(label_surf, (cx - 200, y + 4))
            if self.net_client is not None:
                status = self.net_client.status
                reject = self.net_client.reject_message
            else:
                status = "Offline (no client)"
                reject = ""
            # Colour-code the status
            if status == "Connected":
                status_col = (80, 220, 80)
            elif "mismatch" in status.lower() or status in ("Rejected", "Error"):
                status_col = (220, 80, 80)
            elif "connect" in status.lower():
                status_col = (220, 180, 60)
            else:
                status_col = COL_DIM
            status_surf = self._font_item.render(status, True, status_col)
            self.screen.blit(status_surf, (cx + 60, y + 4))
            # Show rejection message on the next pixel row if present
            if reject:
                reject_short = reject[:60] + ("…" if len(reject) > 60 else "")
                rej_surf = self._font_hint.render(reject_short, True, (220, 80, 80))
                self.screen.blit(rej_surf, (cx - 200, y + ITEM_HEIGHT + 2))

        elif itype == "net_info":
            label_surf = self._font_sec.render("Client:", True, COL_SEC)
            self.screen.blit(label_surf, (cx - 200, y + 4))
            info = f"v{GAME_VERSION}  build {BUILD_NUMBER}  protocol {PROTOCOL_VERSION}"
            info_surf = self._font_hint.render(info, True, COL_DIM)
            self.screen.blit(info_surf, (cx + 60, y + 4))
