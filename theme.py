"""
theme.py

Visual theme definitions for Quad Fighter.
Each theme provides colour palettes for the background, characters,
lane floor, and HUD.  Themes are swapped between levels for strong
visual variety without any asset changes.

Usage
-----
    from theme import get_theme, next_theme_name, THEME_CYCLE, build_palette

    current_theme = get_theme("street")          # pick by name
    current_theme = get_theme(next_theme_name(current_theme["name"]))  # cycle

    palette = build_palette(current_theme, "player", hurt=False)
"""

# ── Hurt-flash helper ─────────────────────────────────────────────────────────

# Keys whose colours should NOT be tinted during hurt flash (remain constant).
_HURT_SKIP = {"belt"}


def _hurt(normal, tint=(255, 200, 200), blend=0.45):
    """
    Derive a hurt-flash colour dict from a normal palette dict by blending
    each RGB tuple toward *tint* by *blend* factor.
    Non-colour values (numbers, None) and keys in _HURT_SKIP pass through
    unchanged.
    """
    out = {}
    for k, v in normal.items():
        if k in _HURT_SKIP or not (isinstance(v, tuple) and len(v) == 3):
            out[k] = v
        else:
            out[k] = tuple(int(v[i] + (tint[i] - v[i]) * blend) for i in range(3))
    return out


# ── Player colour customisation ───────────────────────────────────────────────

# Available karate suit base colours.  Index 0 = "use theme default".
SUIT_COLOURS = [
    {"name": "Default"},
    {"name": "White",  "base": (230, 225, 215)},
    {"name": "Blue",   "base": (48,  62,  140)},
    {"name": "Red",    "base": (160, 32,  32)},
    {"name": "Black",  "base": (28,  28,  32)},
    {"name": "Green",  "base": (36,  100, 40)},
    {"name": "Purple", "base": (80,  32,  128)},
    {"name": "Orange", "base": (200, 90,  20)},
    {"name": "Gold",   "base": (180, 148, 20)},
]

# Available hair colours.  Index 0 = "use theme default".
HAIR_COLOURS = [
    {"name": "Default"},
    {"name": "Auburn",  "colour": (156, 44,  16)},
    {"name": "Black",   "colour": (20,  18,  16)},
    {"name": "Brown",   "colour": (90,  54,  28)},
    {"name": "Blonde",  "colour": (196, 160, 48)},
    {"name": "Silver",  "colour": (200, 198, 192)},
    {"name": "Red",     "colour": (180, 40,  20)},
    {"name": "Blue",    "colour": (30,  60,  160)},
]


def _shade(rgb, factor):
    """Scale an RGB tuple by *factor*, clamped to 0–255."""
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)


def _apply_suit_colour(palette, base_rgb):
    """Override the suit-related palette keys with shaded variants of *base_rgb*."""
    palette["chest"]           = _shade(base_rgb, 1.00)
    palette["torso"]           = _shade(base_rgb, 0.88)
    palette["pelvis"]          = _shade(base_rgb, 1.20)
    palette["front_leg_upper"] = _shade(base_rgb, 1.12)
    palette["front_leg_lower"] = _shade(base_rgb, 0.90)
    palette["rear_leg_upper"]  = _shade(base_rgb, 0.80)
    palette["rear_leg_lower"]  = _shade(base_rgb, 0.70)


def build_palette(theme, variant, hurt=False, suit_colour_idx=0, hair_colour_idx=0):
    """
    Build a draw_fighter palette dict for *variant* ('player', 'raider',
    'brawler', 'boss') using the given theme.

    Merges normal/hurt colour dict with the per-variant props (belt colour,
    body proportions, etc.) that never change with hurt state.

    Optional *suit_colour_idx* and *hair_colour_idx* override the theme's
    default suit and hair colours before the hurt-flash tint is applied.
    """
    chars = theme["characters"][variant]
    normal = dict(chars["normal"])
    # Apply custom colour overrides before hurt tinting so the flash works correctly.
    if 0 < suit_colour_idx < len(SUIT_COLOURS):
        _apply_suit_colour(normal, SUIT_COLOURS[suit_colour_idx]["base"])
    if 0 < hair_colour_idx < len(HAIR_COLOURS):
        normal["hair"] = HAIR_COLOURS[hair_colour_idx]["colour"]
    tint = theme.get("hurt_tint", (255, 200, 200))
    blend = theme.get("hurt_blend", 0.45)
    colours = _hurt(normal, tint, blend) if hurt else normal
    colours.update(chars.get("props", {}))
    return colours


# ── Theme cycle helpers ────────────────────────────────────────────────────────

THEME_CYCLE = ["street", "neon", "acid"]


def next_theme_name(current_name):
    """Return the name of the theme that follows *current_name* in the cycle."""
    idx = THEME_CYCLE.index(current_name) if current_name in THEME_CYCLE else -1
    return THEME_CYCLE[(idx + 1) % len(THEME_CYCLE)]


def get_theme(name):
    """Return the theme dict for *name* (one of THEME_CYCLE)."""
    return THEMES[name]


# ── Theme 1: Street (urban night – default) ───────────────────────────────────

_STREET = {
    "name": "street",

    # Sky gradient
    "sky_top":   (16, 18, 30),
    "sky_horiz": (36, 32, 50),

    # Background building colour pools (used by the procedural generator)
    "far_bldg": [
        (26, 28, 42), (30, 32, 46), (24, 30, 40), (32, 28, 44), (28, 26, 40),
    ],
    "mid_bldg": [
        (40, 44, 54), (46, 42, 52), (48, 48, 60), (44, 50, 56), (50, 46, 58),
    ],
    "accent": [
        (56, 40, 32), (46, 52, 40), (38, 42, 58), (52, 40, 46), (46, 40, 52),
    ],
    "awning": [
        (124, 46, 46), (124, 90, 38), (46, 90, 124), (66, 106, 66),
        (84, 48, 116), (134, 74, 38),
    ],
    "vehicle": [
        (48, 52, 62), (54, 38, 38), (38, 50, 58), (54, 54, 40),
        (46, 48, 60), (60, 50, 38),
    ],
    "bgchar": [
        (30, 32, 44), (36, 30, 40), (32, 38, 44),
    ],

    # Window and lamp colours (used at draw time)
    "win_lit":  (168, 156, 86),
    "win_dim":  (50, 54, 64),
    "lamp_col": (80, 80, 88),
    "lamp_glo": (168, 156, 68),
    "lamp_inner": (228, 212, 130),

    # Lane / floor colours
    "floor_fg":      (28, 28, 28),
    "lane_bands":    [(38 + i * 4,) * 3 for i in range(5)],
    "lane_guides":   [(55 + i * 4,) * 3 for i in range(1, 5)],
    "lane_top_line": (72, 72, 72),
    "lane_bot_line": (86, 86, 86),
    "lane_dash":     (78, 78, 78),

    # HUD colours
    "hud_text":          (220, 220, 220),
    "hud_bar_bg":        (40, 40, 40),
    "hud_bar_outline":   (180, 180, 180),
    "hud_hp_good":       (72, 200, 80),
    "hud_hp_mid":        (220, 190, 50),
    "hud_hp_low":        (210, 60, 60),
    "hud_boss_bg":       (70, 22, 22),
    "hud_boss_bar":      (190, 62, 62),
    "hud_section":       (235, 235, 235),
    "hud_combo":         (255, 215, 0),
    "hud_grab":          (80, 220, 220),
    "hud_level_pulse":   (220, 220, 220),
    "impact_flash":      (230, 230, 230),
    "camera_lock_bar":   (100, 32, 32),
    "grab_outline":      (80, 220, 220),
    "break_effect":      (210, 210, 210),

    # Hurt-flash blend parameters
    "hurt_tint":  (255, 200, 200),
    "hurt_blend": 0.45,

    # Character palettes
    "characters": {
        "player": {
            "normal": {
                # Double Dragon (Billy) inspired palette: warm skin, blue vest, blue pants, auburn hair, dark red-brown boots
                "chest":           (48, 62, 140),   # dark blue sleeveless vest
                "torso":           (42, 56, 124),
                "pelvis":          (60, 90, 168),   # blue pants
                "head":            (202, 152, 100), # warm skin
                "face":            (182, 132, 84),
                "hair":            (156, 44, 16),   # auburn/dark red hair
                "front_arm_upper": (198, 148, 96),  # bare skin (sleeveless vest)
                "front_arm_lower": (188, 138, 86),
                "rear_arm_upper":  (178, 128, 80),
                "rear_arm_lower":  (168, 118, 72),
                "front_leg_upper": (56, 84, 158),   # blue pants
                "front_leg_lower": (46, 70, 136),
                "rear_leg_upper":  (40, 64, 122),
                "rear_leg_lower":  (34, 54, 106),
                "hands":           (198, 148, 96),  # skin-tone fists
                "feet":            (106, 38, 24),   # dark red-brown boots
            },
            "props": {
                "belt":           (14, 14, 16),
                "head_scale":     0.82,
                "shoulder_ratio": 0.35,
                "hip_ratio":      0.12,
                "arm_width":      0.24,
                "leg_width":      0.27,
                "idle_tilt":      0.01,
            },
        },
        "player2": {
            "normal": {
                "chest":           (38, 82, 156),
                "torso":           (44, 92, 166),
                "pelvis":          (32, 66, 122),
                "head":            (216, 196, 172),
                "face":            (188, 168, 145),
                "hair":            (62, 48, 34),
                "front_arm_upper": (200, 156, 110),
                "front_arm_lower": (190, 146, 100),
                "rear_arm_upper":  (178, 138, 96),
                "rear_arm_lower":  (168, 128, 88),
                "front_leg_upper": (28, 48, 92),
                "front_leg_lower": (24, 42, 80),
                "rear_leg_upper":  (22, 38, 74),
                "rear_leg_lower":  (18, 32, 64),
                "hands":           (212, 162, 110),
                "feet":            (42, 42, 48),
            },
            "props": {
                "belt":           (22, 22, 24),
                "head_scale":     0.82,
                "shoulder_ratio": 0.35,
                "hip_ratio":      0.12,
                "arm_width":      0.24,
                "leg_width":      0.27,
                "idle_tilt":      0.01,
            },
        },
        "raider": {
            "normal": {
                "chest":           (88, 44, 38),
                "torso":           (52, 52, 56),
                "pelvis":          (44, 56, 88),
                "head":            (170, 138, 112),
                "face":            (126, 100, 82),
                "hair":            (24, 24, 24),
                "front_arm_upper": (58, 58, 62),
                "front_arm_lower": (102, 70, 62),
                "rear_arm_upper":  (44, 44, 48),
                "rear_arm_lower":  (90, 62, 56),
                "front_leg_upper": (50, 66, 104),
                "front_leg_lower": (38, 50, 84),
                "rear_leg_upper":  (36, 48, 76),
                "rear_leg_lower":  (30, 38, 62),
                "hands":           (168, 134, 108),
                "feet":            (44, 44, 48),
            },
            "props": {
                "head_scale":     0.88,
                "shoulder_ratio": 0.31,
                "hip_ratio":      0.12,
                "arm_width":      0.23,
                "leg_width":      0.22,
                "idle_tilt":      -0.06,
                "idle_shift":     0.03,
            },
        },
        "brawler": {
            "normal": {
                "chest":           (72, 72, 46),
                "torso":           (48, 54, 52),
                "pelvis":          (84, 74, 44),
                "head":            (176, 146, 118),
                "face":            (130, 104, 84),
                "hair":            (34, 32, 24),
                "front_arm_upper": (84, 86, 62),
                "front_arm_lower": (118, 88, 66),
                "rear_arm_upper":  (70, 72, 52),
                "rear_arm_lower":  (106, 78, 60),
                "front_leg_upper": (88, 80, 46),
                "front_leg_lower": (70, 64, 38),
                "rear_leg_upper":  (78, 70, 40),
                "rear_leg_lower":  (62, 56, 34),
                "hands":           (172, 138, 112),
                "feet":            (50, 48, 42),
            },
            "props": {
                "head_scale":     0.86,
                "shoulder_ratio": 0.35,
                "hip_ratio":      0.14,
                "arm_width":      0.26,
                "leg_width":      0.26,
                "idle_tilt":      -0.04,
                "idle_shift":     0.02,
            },
        },
        "boss": {
            "normal": {
                "chest":           (128, 54, 48),
                "torso":           (58, 58, 62),
                "pelvis":          (84, 64, 124),
                "head":            (176, 142, 112),
                "face":            (130, 102, 82),
                "hair":            (24, 20, 20),
                "front_arm_upper": (72, 72, 76),
                "front_arm_lower": (124, 84, 72),
                "rear_arm_upper":  (56, 56, 60),
                "rear_arm_lower":  (112, 76, 66),
                "front_leg_upper": (78, 70, 142),
                "front_leg_lower": (62, 56, 118),
                "rear_leg_upper":  (56, 50, 102),
                "rear_leg_lower":  (46, 42, 86),
                "hands":           (176, 140, 112),
                "feet":            (48, 48, 52),
            },
            "props": {
                "head_scale":     0.90,
                "shoulder_ratio": 0.33,
                "hip_ratio":      0.13,
                "arm_width":      0.26,
                "leg_width":      0.24,
                "idle_tilt":      -0.08,
                "idle_shift":     0.04,
            },
        },
    },
}


# ── Theme 2: Neon (cyberpunk) ─────────────────────────────────────────────────

_NEON = {
    "name": "neon",

    # Deep near-black sky with a hint of indigo
    "sky_top":   (2, 2, 10),
    "sky_horiz": (8, 4, 22),

    "far_bldg": [
        (10, 10, 18), (12, 8, 20), (8, 10, 16), (14, 10, 22), (10, 8, 18),
    ],
    "mid_bldg": [
        (16, 14, 28), (18, 12, 30), (20, 16, 34), (14, 16, 26), (18, 18, 32),
    ],
    "accent": [
        (140, 0, 100), (0, 140, 180), (160, 20, 0), (0, 120, 160), (120, 0, 160),
    ],
    "awning": [
        (180, 0, 110), (0, 160, 200), (200, 60, 0), (0, 180, 130),
        (160, 0, 200), (200, 120, 0),
    ],
    "vehicle": [
        (20, 20, 32), (30, 10, 20), (10, 24, 34), (24, 10, 36),
        (18, 18, 28), (28, 14, 14),
    ],
    "bgchar": [
        (14, 10, 28), (18, 8, 24), (12, 14, 26),
    ],

    # Cyan lit windows, deep purple dim, electric-blue lamps
    "win_lit":    (0, 220, 220),
    "win_dim":    (20, 12, 44),
    "lamp_col":   (40, 40, 56),
    "lamp_glo":   (0, 180, 255),
    "lamp_inner": (120, 220, 255),

    # Lane / floor – very dark with a blue-purple tint
    "floor_fg":      (8, 8, 18),
    "lane_bands":    [
        (16, 14, 26), (18, 16, 30), (20, 18, 34), (22, 20, 38), (24, 22, 42),
    ],
    "lane_guides":   [
        (0, 40, 80), (0, 44, 88), (0, 48, 96), (0, 52, 104),
    ],
    "lane_top_line": (0, 160, 220),
    "lane_bot_line": (0, 100, 180),
    "lane_dash":     (0, 80, 140),

    # HUD – cyan/magenta tones
    "hud_text":          (180, 240, 255),
    "hud_bar_bg":        (10, 10, 24),
    "hud_bar_outline":   (0, 160, 200),
    "hud_hp_good":       (0, 220, 180),
    "hud_hp_mid":        (200, 180, 0),
    "hud_hp_low":        (220, 0, 80),
    "hud_boss_bg":       (30, 0, 50),
    "hud_boss_bar":      (180, 0, 200),
    "hud_section":       (0, 220, 220),
    "hud_combo":         (0, 255, 200),
    "hud_grab":          (0, 220, 220),
    "hud_level_pulse":   (0, 220, 255),
    "impact_flash":      (0, 220, 255),
    "camera_lock_bar":   (140, 0, 100),
    "grab_outline":      (0, 220, 220),
    "break_effect":      (0, 200, 255),

    "hurt_tint":  (220, 220, 255),
    "hurt_blend": 0.50,

    "characters": {
        "player": {
            "normal": {
                "chest":           (18, 18, 28),
                "torso":           (14, 14, 22),
                "pelvis":          (22, 20, 34),
                "head":            (176, 156, 132),
                "face":            (148, 124, 102),
                "hair":            (0, 180, 220),
                "front_arm_upper": (16, 20, 32),
                "front_arm_lower": (14, 18, 28),
                "rear_arm_upper":  (12, 16, 26),
                "rear_arm_lower":  (10, 14, 22),
                "front_leg_upper": (18, 16, 30),
                "front_leg_lower": (14, 12, 26),
                "rear_leg_upper":  (14, 12, 24),
                "rear_leg_lower":  (10, 10, 20),
                "hands":           (168, 144, 118),
                "feet":            (24, 22, 36),
            },
            "props": {
                "belt":           (0, 160, 200),
                "head_scale":     0.82,
                "shoulder_ratio": 0.35,
                "hip_ratio":      0.12,
                "arm_width":      0.24,
                "leg_width":      0.27,
                "idle_tilt":      0.01,
            },
        },
        "player2": {
            "normal": {
                "chest":           (200, 0, 160),
                "torso":           (180, 0, 140),
                "pelvis":          (220, 0, 180),
                "head":            (176, 156, 132),
                "face":            (148, 124, 102),
                "hair":            (255, 60, 180),
                "front_arm_upper": (168, 134, 106),
                "front_arm_lower": (156, 122, 96),
                "rear_arm_upper":  (148, 116, 90),
                "rear_arm_lower":  (138, 108, 82),
                "front_leg_upper": (160, 0, 120),
                "front_leg_lower": (130, 0, 100),
                "rear_leg_upper":  (120, 0, 90),
                "rear_leg_lower":  (100, 0, 74),
                "hands":           (168, 144, 118),
                "feet":            (34, 14, 30),
            },
            "props": {
                "belt":           (0, 200, 200),
                "head_scale":     0.82,
                "shoulder_ratio": 0.35,
                "hip_ratio":      0.12,
                "arm_width":      0.24,
                "leg_width":      0.27,
                "idle_tilt":      0.01,
            },
        },
        "raider": {
            "normal": {
                "chest":           (160, 10, 10),
                "torso":           (14, 12, 18),
                "pelvis":          (120, 8, 8),
                "head":            (162, 130, 106),
                "face":            (124, 98, 78),
                "hair":            (200, 0, 80),
                "front_arm_upper": (18, 14, 14),
                "front_arm_lower": (120, 16, 14),
                "rear_arm_upper":  (14, 10, 12),
                "rear_arm_lower":  (100, 12, 12),
                "front_leg_upper": (16, 12, 20),
                "front_leg_lower": (12, 10, 18),
                "rear_leg_upper":  (12, 10, 16),
                "rear_leg_lower":  (10, 8, 14),
                "hands":           (160, 128, 104),
                "feet":            (18, 14, 20),
            },
            "props": {
                "head_scale":     0.9,
                "shoulder_ratio": 0.31,
                "hip_ratio":      0.12,
                "arm_width":      0.23,
                "leg_width":      0.22,
                "idle_tilt":      -0.06,
                "idle_shift":     0.03,
            },
        },
        "brawler": {
            "normal": {
                "chest":           (20, 140, 60),
                "torso":           (12, 22, 14),
                "pelvis":          (16, 110, 48),
                "head":            (164, 134, 108),
                "face":            (126, 100, 80),
                "hair":            (0, 200, 80),
                "front_arm_upper": (14, 22, 16),
                "front_arm_lower": (18, 130, 58),
                "rear_arm_upper":  (12, 18, 12),
                "rear_arm_lower":  (14, 110, 46),
                "front_leg_upper": (12, 20, 14),
                "front_leg_lower": (10, 16, 12),
                "rear_leg_upper":  (10, 16, 12),
                "rear_leg_lower":  (8, 14, 10),
                "hands":           (160, 130, 104),
                "feet":            (16, 22, 16),
            },
            "props": {
                "head_scale":     0.86,
                "shoulder_ratio": 0.35,
                "hip_ratio":      0.14,
                "arm_width":      0.26,
                "leg_width":      0.26,
                "idle_tilt":      -0.04,
                "idle_shift":     0.02,
            },
        },
        "boss": {
            "normal": {
                "chest":           (100, 0, 160),
                "torso":           (22, 18, 36),
                "pelvis":          (80, 0, 130),
                "head":            (170, 138, 110),
                "face":            (128, 100, 80),
                "hair":            (0, 200, 200),
                "front_arm_upper": (22, 18, 36),
                "front_arm_lower": (90, 0, 150),
                "rear_arm_upper":  (18, 14, 30),
                "rear_arm_lower":  (74, 0, 124),
                "front_leg_upper": (80, 0, 130),
                "front_leg_lower": (64, 0, 106),
                "rear_leg_upper":  (56, 0, 92),
                "rear_leg_lower":  (44, 0, 74),
                "hands":           (170, 136, 110),
                "feet":            (24, 18, 40),
            },
            "props": {
                "head_scale":     0.90,
                "shoulder_ratio": 0.33,
                "hip_ratio":      0.13,
                "arm_width":      0.26,
                "leg_width":      0.24,
                "idle_tilt":      -0.08,
                "idle_shift":     0.04,
            },
        },
    },
}


# ── Theme 3: Acid (rave / acid house) ─────────────────────────────────────────

_ACID = {
    "name": "acid",

    # Vivid deep purple sky blending toward fiery orange at the horizon
    "sky_top":   (46, 0, 80),
    "sky_horiz": (180, 50, 10),

    "far_bldg": [
        (160, 100, 0), (0, 100, 160), (120, 0, 160), (0, 140, 100), (160, 60, 0),
    ],
    "mid_bldg": [
        (200, 130, 0), (0, 130, 200), (160, 0, 200), (0, 180, 130), (200, 80, 0),
    ],
    "accent": [
        (240, 180, 0), (0, 200, 240), (220, 0, 180), (60, 240, 80), (240, 100, 0),
    ],
    "awning": [
        (255, 60, 0), (255, 200, 0), (0, 220, 220), (220, 0, 200),
        (60, 255, 60), (255, 130, 0),
    ],
    "vehicle": [
        (220, 120, 0), (0, 180, 220), (180, 0, 220), (220, 200, 0),
        (0, 220, 140), (220, 60, 0),
    ],
    "bgchar": [
        (180, 60, 0), (0, 140, 180), (140, 0, 160),
    ],

    # Vivid yellow windows, purple dim, orange lamps
    "win_lit":    (255, 240, 60),
    "win_dim":    (60, 20, 80),
    "lamp_col":   (200, 100, 0),
    "lamp_glo":   (255, 180, 0),
    "lamp_inner": (255, 240, 120),

    # Lane / floor – warm purple-magenta gradient
    "floor_fg":      (60, 20, 60),
    "lane_bands":    [
        (50, 24, 50), (60, 28, 58), (70, 32, 66), (80, 36, 74), (90, 40, 82),
    ],
    "lane_guides":   [
        (180, 60, 0), (200, 80, 0), (220, 100, 0), (240, 120, 0),
    ],
    "lane_top_line": (240, 120, 0),
    "lane_bot_line": (255, 160, 0),
    "lane_dash":     (220, 80, 180),

    # HUD – vivid yellow/orange accents
    "hud_text":          (255, 240, 60),
    "hud_bar_bg":        (30, 10, 30),
    "hud_bar_outline":   (240, 140, 0),
    "hud_hp_good":       (60, 240, 60),
    "hud_hp_mid":        (255, 200, 0),
    "hud_hp_low":        (255, 40, 40),
    "hud_boss_bg":       (80, 0, 80),
    "hud_boss_bar":      (220, 0, 180),
    "hud_section":       (255, 240, 60),
    "hud_combo":         (255, 80, 0),
    "hud_grab":          (255, 240, 0),
    "hud_level_pulse":   (255, 200, 0),
    "impact_flash":      (255, 240, 0),
    "camera_lock_bar":   (180, 0, 120),
    "grab_outline":      (255, 220, 0),
    "break_effect":      (255, 180, 0),

    "hurt_tint":  (255, 220, 100),
    "hurt_blend": 0.50,

    "characters": {
        "player": {
            "normal": {
                "chest":           (220, 200, 20),
                "torso":           (240, 220, 40),
                "pelvis":          (200, 180, 18),
                "head":            (220, 190, 158),
                "face":            (196, 164, 132),
                "hair":            (180, 20, 220),
                "front_arm_upper": (240, 220, 40),
                "front_arm_lower": (228, 208, 32),
                "rear_arm_upper":  (220, 200, 28),
                "rear_arm_lower":  (208, 188, 24),
                "front_leg_upper": (180, 160, 18),
                "front_leg_lower": (160, 142, 14),
                "rear_leg_upper":  (160, 140, 14),
                "rear_leg_lower":  (140, 122, 12),
                "hands":           (210, 178, 144),
                "feet":            (160, 80, 0),
            },
            "props": {
                "belt":           (180, 20, 180),
                "head_scale":     0.82,
                "shoulder_ratio": 0.35,
                "hip_ratio":      0.12,
                "arm_width":      0.24,
                "leg_width":      0.27,
                "idle_tilt":      0.01,
            },
        },
        "player2": {
            "normal": {
                "chest":           (0, 200, 220),
                "torso":           (0, 220, 240),
                "pelvis":          (0, 176, 196),
                "head":            (220, 190, 158),
                "face":            (196, 164, 132),
                "hair":            (0, 255, 180),
                "front_arm_upper": (200, 166, 128),
                "front_arm_lower": (188, 154, 118),
                "rear_arm_upper":  (178, 144, 110),
                "rear_arm_lower":  (166, 134, 100),
                "front_leg_upper": (0, 160, 176),
                "front_leg_lower": (0, 138, 152),
                "rear_leg_upper":  (0, 130, 144),
                "rear_leg_lower":  (0, 110, 122),
                "hands":           (210, 178, 144),
                "feet":            (0, 80, 100),
            },
            "props": {
                "belt":           (255, 60, 0),
                "head_scale":     0.82,
                "shoulder_ratio": 0.35,
                "hip_ratio":      0.12,
                "arm_width":      0.24,
                "leg_width":      0.27,
                "idle_tilt":      0.01,
            },
        },
        "raider": {
            "normal": {
                "chest":           (220, 80, 10),
                "torso":           (180, 60, 8),
                "pelvis":          (200, 70, 12),
                "head":            (200, 160, 122),
                "face":            (164, 128, 96),
                "hair":            (220, 40, 10),
                "front_arm_upper": (200, 70, 10),
                "front_arm_lower": (180, 58, 8),
                "rear_arm_upper":  (180, 60, 8),
                "rear_arm_lower":  (160, 50, 6),
                "front_leg_upper": (170, 50, 8),
                "front_leg_lower": (150, 40, 6),
                "rear_leg_upper":  (150, 40, 6),
                "rear_leg_lower":  (130, 32, 4),
                "hands":           (196, 156, 118),
                "feet":            (80, 40, 0),
            },
            "props": {
                "head_scale":     0.88,
                "shoulder_ratio": 0.31,
                "hip_ratio":      0.12,
                "arm_width":      0.23,
                "leg_width":      0.22,
                "idle_tilt":      -0.06,
                "idle_shift":     0.03,
            },
        },
        "brawler": {
            "normal": {
                "chest":           (60, 200, 20),
                "torso":           (50, 170, 16),
                "pelvis":          (80, 220, 24),
                "head":            (190, 156, 118),
                "face":            (156, 124, 94),
                "hair":            (20, 220, 80),
                "front_arm_upper": (60, 190, 18),
                "front_arm_lower": (52, 170, 14),
                "rear_arm_upper":  (52, 170, 14),
                "rear_arm_lower":  (44, 150, 12),
                "front_leg_upper": (50, 160, 16),
                "front_leg_lower": (42, 140, 12),
                "rear_leg_upper":  (42, 140, 12),
                "rear_leg_lower":  (36, 120, 10),
                "hands":           (186, 150, 114),
                "feet":            (0, 80, 40),
            },
            "props": {
                "head_scale":     0.86,
                "shoulder_ratio": 0.35,
                "hip_ratio":      0.14,
                "arm_width":      0.26,
                "leg_width":      0.26,
                "idle_tilt":      -0.04,
                "idle_shift":     0.02,
            },
        },
        "boss": {
            "normal": {
                "chest":           (200, 0, 180),
                "torso":           (160, 0, 140),
                "pelvis":          (220, 0, 200),
                "head":            (200, 160, 120),
                "face":            (164, 128, 96),
                "hair":            (40, 0, 220),
                "front_arm_upper": (170, 0, 160),
                "front_arm_lower": (190, 0, 170),
                "rear_arm_upper":  (150, 0, 140),
                "rear_arm_lower":  (170, 0, 150),
                "front_leg_upper": (140, 0, 120),
                "front_leg_lower": (120, 0, 100),
                "rear_leg_upper":  (110, 0, 90),
                "rear_leg_lower":  (90, 0, 74),
                "hands":           (196, 158, 118),
                "feet":            (60, 0, 100),
            },
            "props": {
                "head_scale":     0.90,
                "shoulder_ratio": 0.33,
                "hip_ratio":      0.13,
                "arm_width":      0.26,
                "leg_width":      0.24,
                "idle_tilt":      -0.08,
                "idle_shift":     0.04,
            },
        },
    },
}


# ── Theme registry ─────────────────────────────────────────────────────────────

THEMES = {
    "street": _STREET,
    "neon":   _NEON,
    "acid":   _ACID,
}
