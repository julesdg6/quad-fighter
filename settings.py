"""settings.py: Game settings with keyboard/controller mappings and persistence."""

import json
import os

import pygame

# ── Default mappings ──────────────────────────────────────────────────────────

# Keyboard: action name → pygame key constant
DEFAULT_KEYBOARD = {
    "move_left":   pygame.K_LEFT,
    "move_right":  pygame.K_RIGHT,
    "move_up":     pygame.K_UP,
    "move_down":   pygame.K_DOWN,
    "jump":        pygame.K_SPACE,
    "punch":       pygame.K_z,
    "kick":        pygame.K_x,
    "crouch":      pygame.K_c,
    "grab":        pygame.K_g,
    "start_pause": pygame.K_RETURN,
}

# Player 2 keyboard defaults (WASD-based, does not conflict with P1)
DEFAULT_KEYBOARD_P2 = {
    "move_left":   pygame.K_a,
    "move_right":  pygame.K_d,
    "move_up":     pygame.K_w,
    "move_down":   pygame.K_s,
    "jump":        pygame.K_q,
    "punch":       pygame.K_r,
    "kick":        pygame.K_f,
    "crouch":      pygame.K_e,
    "grab":        pygame.K_t,
}

# Controller: action name → button index (standard Xbox layout via pygame)
DEFAULT_CONTROLLER = {
    "jump":        0,   # A
    "punch":       2,   # X
    "kick":        1,   # B
    "crouch":      3,   # Y
    "grab":        5,   # RB
    "start_pause": 7,   # Start / Menu
    "back":        6,   # Back / View
}

# Human-readable names for common controller buttons
CONTROLLER_BUTTON_NAMES = {
    0: "A",
    1: "B",
    2: "X",
    3: "Y",
    4: "LB",
    5: "RB",
    6: "Back",
    7: "Start",
    8: "L-Stick",
    9: "R-Stick",
}

# Joystick axis dead-zone threshold
AXIS_DEADZONE = 0.3

SETTINGS_FILE = "settings.json"

# Default network settings
DEFAULT_SERVER_IP   = "127.0.0.1"
DEFAULT_SERVER_PORT = 7777


# ── Settings class ────────────────────────────────────────────────────────────

class Settings:
    """Holds all user-configurable settings.  Call load() after pygame.init()."""

    def __init__(self):
        self.music_volume: int = 70   # 0–100
        self.sfx_volume:   int = 80   # 0–100
        self.keyboard:    dict = dict(DEFAULT_KEYBOARD)
        self.keyboard_p2: dict = dict(DEFAULT_KEYBOARD_P2)
        self.controller:  dict = dict(DEFAULT_CONTROLLER)
        # Network
        self.server_ip:   str = DEFAULT_SERVER_IP
        self.server_port: int = DEFAULT_SERVER_PORT
        # Appearance: indices into SUIT_COLOURS / HAIR_COLOURS (0 = theme default)
        self.suit_colour_idx: int = 0
        self.hair_colour_idx: int = 0
        # Number of local players (1–4); additional players must join explicitly
        self.num_players: int = 1

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self, path: str = SETTINGS_FILE) -> None:
        """Load settings from *path*.  Silently ignores missing or corrupt files."""
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.music_volume = int(data.get("music_volume", self.music_volume))
            self.sfx_volume   = int(data.get("sfx_volume",   self.sfx_volume))
            if "keyboard" in data:
                for action, key_val in data["keyboard"].items():
                    if action in self.keyboard:
                        self.keyboard[action] = int(key_val)
            if "keyboard_p2" in data:
                for action, key_val in data["keyboard_p2"].items():
                    if action in self.keyboard_p2:
                        self.keyboard_p2[action] = int(key_val)
            if "controller" in data:
                for action, btn_val in data["controller"].items():
                    if action in self.controller:
                        self.controller[action] = int(btn_val)
            self.server_ip   = str(data.get("server_ip",   self.server_ip))
            self.server_port = int(data.get("server_port", self.server_port))
            self.suit_colour_idx = int(data.get("suit_colour_idx", self.suit_colour_idx))
            self.hair_colour_idx = int(data.get("hair_colour_idx", self.hair_colour_idx))
            self.num_players = max(1, min(4, int(data.get("num_players", self.num_players))))
        except Exception:
            pass  # corrupt file – use defaults

    def save(self, path: str = SETTINGS_FILE) -> None:
        """Write current settings to *path* as JSON."""
        data = {
            "music_volume": self.music_volume,
            "sfx_volume":   self.sfx_volume,
            "keyboard":     dict(self.keyboard),
            "keyboard_p2":  dict(self.keyboard_p2),
            "controller":   dict(self.controller),
            "server_ip":    self.server_ip,
            "server_port":  self.server_port,
            "suit_colour_idx": self.suit_colour_idx,
            "hair_colour_idx": self.hair_colour_idx,
            "num_players":  self.num_players,
        }
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception:
            pass

    # ── Controller helpers ────────────────────────────────────────────────────

    def read_controller(self, joystick) -> dict:
        """Return a dict of action → bool for the current joystick state.

        Handles D-pad (hat), left stick, and configured buttons.
        Returns an empty dict if *joystick* is None.
        """
        if joystick is None:
            return {}

        result: dict = {}

        # Mapped buttons
        n_buttons = joystick.get_numbuttons()
        for action, btn_idx in self.controller.items():
            if btn_idx < n_buttons:
                result[action] = bool(joystick.get_button(btn_idx))

        # D-pad via hat 0
        if joystick.get_numhats() > 0:
            hat_x, hat_y = joystick.get_hat(0)
            if hat_x < 0:
                result["move_left"]  = True
            elif hat_x > 0:
                result["move_right"] = True
            if hat_y > 0:
                result["move_up"]    = True
            elif hat_y < 0:
                result["move_down"]  = True

        # Left analogue stick (axes 0 and 1)
        if joystick.get_numaxes() >= 2:
            ax = joystick.get_axis(0)
            ay = joystick.get_axis(1)
            if ax < -AXIS_DEADZONE:
                result["move_left"]  = True
            elif ax > AXIS_DEADZONE:
                result["move_right"] = True
            if ay < -AXIS_DEADZONE:
                result["move_up"]    = True
            elif ay > AXIS_DEADZONE:
                result["move_down"]  = True

        return result
