"""
background.py

Procedural layered background environments for Quad Fighter.
Provides far / mid / near parallax rendering of an urban street scene.
All elements are drawn with simple pygame primitives – no bitmaps.
"""

import math
import random

import pygame

# Parallax factors: fraction of camera_x movement applied per layer.
FAR_PARALLAX = 0.12
MID_PARALLAX = 0.38
NEAR_PARALLAX = 0.65

# ── Colour palettes ───────────────────────────────────────────────────────────

_SKY_TOP = (16, 18, 30)
_SKY_HORIZ = (36, 32, 50)

_FAR_BLDG = [
    (26, 28, 42), (30, 32, 46), (24, 30, 40), (32, 28, 44), (28, 26, 40),
]
_MID_BLDG = [
    (40, 44, 54), (46, 42, 52), (48, 48, 60), (44, 50, 56), (50, 46, 58),
]
_ACCENT = [
    (56, 40, 32), (46, 52, 40), (38, 42, 58), (52, 40, 46), (46, 40, 52),
]
_AWNING = [
    (124, 46, 46), (124, 90, 38), (46, 90, 124), (66, 106, 66),
    (84, 48, 116), (134, 74, 38),
]
_VEHICLE = [
    (48, 52, 62), (54, 38, 38), (38, 50, 58), (54, 54, 40),
    (46, 48, 60), (60, 50, 38),
]
_BGCHAR = [
    (30, 32, 44), (36, 30, 40), (32, 38, 44),
]

_WIN_LIT = (168, 156, 86)
_WIN_DIM = (50, 54, 64)
_LAMP_COL = (80, 80, 88)
_LAMP_GLO = (168, 156, 68)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _pick(rng, lst):
    return lst[rng.randint(0, len(lst) - 1)]


def _cull(sx, w, screen_w):
    """Return True when the element is fully off-screen."""
    return sx + w < -12 or sx > screen_w + 12


def _dim(color, amount=14):
    return tuple(max(0, c - amount) for c in color)


# ── Generators ────────────────────────────────────────────────────────────────

def _gen_far_buildings(rng, world_w):
    bldgs = []
    x = -60
    while x < world_w + 200:
        w = rng.randint(60, 150)
        h = rng.randint(50, 115)
        color = _pick(rng, _FAR_BLDG)
        cols = max(1, w // 18)
        rows = max(1, (h - 15) // 20)
        windows = [
            (c * 18 + 8, r * 20 + 8, rng.random() < 0.45)
            for r in range(rows)
            for c in range(cols)
        ]
        bldgs.append({"x": float(x), "w": w, "h": h, "color": color, "windows": windows})
        x += w + rng.randint(10, 55)
    return bldgs


def _gen_mid_buildings(rng, world_w):
    bldgs = []
    x = -30
    while x < world_w + 150:
        w = rng.randint(48, 115)
        h = rng.randint(75, 165)
        color = _pick(rng, _MID_BLDG)
        accent = _pick(rng, _ACCENT)
        has_shop = rng.random() < 0.45
        awning = _pick(rng, _AWNING) if has_shop else None
        cols = max(1, (w - 16) // 22)
        rows = max(1, (h - 32) // 26)
        windows = [
            (c * 22 + 9, r * 26 + 14, rng.random() < 0.55)
            for r in range(rows)
            for c in range(cols)
        ]
        bldgs.append({
            "x": float(x), "w": w, "h": h,
            "color": color, "accent": accent,
            "has_shop": has_shop, "awning": awning,
            "windows": windows,
        })
        x += w + rng.randint(5, 28)
    return bldgs


def _gen_lamps(rng, world_w):
    lamps = []
    x = 200
    while x < world_w:
        lamps.append({"x": float(x)})
        x += rng.randint(200, 350)
    return lamps


def _gen_vehicles(rng, world_w):
    vehs = []
    x = 400
    while x < world_w - 100:
        kind = "car" if rng.random() < 0.72 else "motorbike"
        color = _pick(rng, _VEHICLE)
        facing = 1 if rng.random() < 0.5 else -1
        vehs.append({"x": float(x), "kind": kind, "color": color, "facing": facing})
        x += rng.randint(280, 560)
    return vehs


def _gen_bg_chars(rng, world_w):
    chars = []
    x = 300
    while x < world_w - 50:
        color = _pick(rng, _BGCHAR)
        facing = 1 if rng.random() < 0.5 else -1
        phase = rng.uniform(0.0, math.pi * 2)
        chars.append({"x": float(x), "color": color, "facing": facing, "phase": phase})
        x += rng.randint(260, 480)
    return chars


# ── Public: generate ──────────────────────────────────────────────────────────

def generate_background(world_w, height, lane_top, seed=42):
    """
    Generate all background data.
    Call once per level; pass the result to the draw functions each frame.
    """
    rng = random.Random(seed)
    return {
        "far":   _gen_far_buildings(rng, world_w),
        "mid":   _gen_mid_buildings(rng, world_w),
        "lamps": _gen_lamps(rng, world_w),
        "vehs":  _gen_vehicles(rng, world_w),
        "chars": _gen_bg_chars(rng, world_w),
    }


# ── Draw helpers ──────────────────────────────────────────────────────────────

def _draw_sky(screen, width, lane_top):
    """Vertical gradient sky filling the area above the gameplay lane."""
    bands = 8
    for i in range(bands):
        t = (i + 0.5) / bands
        r = int(_SKY_TOP[0] + (_SKY_HORIZ[0] - _SKY_TOP[0]) * t)
        g = int(_SKY_TOP[1] + (_SKY_HORIZ[1] - _SKY_TOP[1]) * t)
        b = int(_SKY_TOP[2] + (_SKY_HORIZ[2] - _SKY_TOP[2]) * t)
        band_y = int(i * lane_top / bands)
        band_h = int((i + 1) * lane_top / bands) - band_y + 1
        pygame.draw.rect(screen, (r, g, b), (0, band_y, width, band_h))


def _draw_far_layer(screen, camera_x, bldgs, screen_w, lane_top):
    off = int(camera_x * FAR_PARALLAX)
    for b in bldgs:
        sx = int(b["x"]) - off
        if _cull(sx, b["w"], screen_w):
            continue
        sy = lane_top - b["h"]
        pygame.draw.rect(screen, b["color"], (sx, sy, b["w"], b["h"]))
        for (rx, ry, lit) in b["windows"]:
            pygame.draw.rect(screen, _WIN_LIT if lit else _WIN_DIM,
                             (sx + rx, sy + ry, 5, 4))


def _draw_mid_layer(screen, camera_x, bldgs, screen_w, lane_top):
    off = int(camera_x * MID_PARALLAX)
    for b in bldgs:
        sx = int(b["x"]) - off
        if _cull(sx, b["w"], screen_w):
            continue
        sy = lane_top - b["h"]
        rect = pygame.Rect(sx, sy, b["w"], b["h"])
        pygame.draw.rect(screen, b["color"], rect)
        pygame.draw.rect(screen, _dim(b["color"]), rect, 1)
        for (rx, ry, lit) in b["windows"]:
            pygame.draw.rect(screen, _WIN_LIT if lit else _WIN_DIM,
                             (sx + rx, sy + ry, 8, 7))
        if b["has_shop"]:
            sh = max(18, min(35, b["h"] // 3))
            shop_r = pygame.Rect(sx, lane_top - sh, b["w"], sh)
            pygame.draw.rect(screen, b["accent"], shop_r)
            if b["awning"] is not None:
                aw = pygame.Rect(sx - 5, lane_top - sh - 9, b["w"] + 10, 11)
                pygame.draw.rect(screen, b["awning"], aw)
                stripe = _dim(b["awning"], 22)
                for i in range(0, aw.w, 16):
                    pygame.draw.rect(screen, stripe, (aw.x + i, aw.y, 8, aw.h))


def _draw_lamp(screen, sx, lane_top, lane_bottom):
    """Draw a single street lamp post with arm and glowing head."""
    pygame.draw.line(screen, _LAMP_COL, (sx, lane_bottom), (sx, lane_top - 22), 3)
    arm_x = sx + 20
    pygame.draw.line(screen, _LAMP_COL, (sx, lane_top - 22), (arm_x, lane_top - 22), 2)
    pygame.draw.circle(screen, _LAMP_GLO, (arm_x, lane_top - 22), 5)
    pygame.draw.circle(screen, (228, 212, 130), (arm_x, lane_top - 22), 3)


def _draw_car(screen, sx, base_y, color):
    w, h = 56, 22
    pygame.draw.rect(screen, color, (sx, base_y - h // 2, w, h // 2))
    ci = w // 5
    cw = w - ci * 2
    ch = h // 2 - 2
    cabin_col = tuple(min(255, c + 8) for c in color)
    pygame.draw.rect(screen, cabin_col, (sx + ci, base_y - h + 2, cw, ch))
    pygame.draw.rect(screen, (34, 40, 50), (sx + ci + 3, base_y - h + 4, cw - 6, ch - 4))
    wr = max(4, h // 4)
    pygame.draw.circle(screen, (22, 22, 26), (sx + w // 4, base_y - wr // 2), wr)
    pygame.draw.circle(screen, (22, 22, 26), (sx + w * 3 // 4, base_y - wr // 2), wr)
    pygame.draw.rect(screen, _dim(color), (sx, base_y - h, w, h), 1)


def _draw_motorbike(screen, sx, base_y, color):
    w, wr = 34, 7
    pygame.draw.circle(screen, (22, 22, 26), (sx + wr, base_y), wr)
    pygame.draw.circle(screen, (22, 22, 26), (sx + w - wr, base_y), wr)
    pts = [
        (sx + wr, base_y - wr // 2),
        (sx + w // 2, base_y - 16),
        (sx + w - wr, base_y - wr // 2),
    ]
    pygame.draw.polygon(screen, color, pts)
    pygame.draw.rect(screen, _dim(color, 10), (sx + w // 4, base_y - 16, w // 2, 6))


def _draw_bg_char(screen, sx, base_y, color, facing, idle_phase):
    """Draw a simple background pedestrian silhouette with a gentle idle animation."""
    bob = int(math.sin(idle_phase) * 1.5)
    head_y = base_y - 28 + bob
    hr = 5
    pygame.draw.line(screen, color, (sx, head_y + hr), (sx, base_y - 8), 3)
    pygame.draw.circle(screen, color, (sx, head_y), hr)
    a_bob = math.sin(idle_phase) * 2
    pygame.draw.line(screen, color, (sx, base_y - 18), (sx - 6 * facing, int(base_y - 12 + a_bob)), 2)
    pygame.draw.line(screen, color, (sx, base_y - 18), (sx + 6 * facing, int(base_y - 12 - a_bob)), 2)
    pygame.draw.line(screen, color, (sx, base_y - 8), (sx - 4, base_y), 2)
    pygame.draw.line(screen, color, (sx, base_y - 8), (sx + 4, base_y), 2)


# ── Public: draw ──────────────────────────────────────────────────────────────

def draw_background_pre_lane(screen, camera_x, bg_data, width, height, lane_top):
    """
    Draw sky gradient and far/mid building layers.
    Call this before drawing the lane floor bands so buildings appear behind the lane.
    """
    _draw_sky(screen, width, lane_top)
    _draw_far_layer(screen, camera_x, bg_data["far"], width, lane_top)
    _draw_mid_layer(screen, camera_x, bg_data["mid"], width, lane_top)


def draw_background_post_lane(screen, camera_x, frame_count, bg_data,
                               width, height, lane_top, lane_bottom):
    """
    Draw near-layer elements: street lamps, vehicles, and background characters.
    Call after the lane floor bands, before gameplay entities, so near-background
    elements appear behind the player and enemies but in front of the buildings.
    """
    off = int(camera_x * NEAR_PARALLAX)
    t = frame_count / 60.0

    for lamp in bg_data["lamps"]:
        sx = int(lamp["x"]) - off
        if not _cull(sx, 30, width):
            _draw_lamp(screen, sx, lane_top, lane_bottom)

    # Vehicles are parked at the back of the scene, base just at the horizon line.
    veh_y = lane_top
    for v in bg_data["vehs"]:
        sx = int(v["x"]) - off
        if v["kind"] == "car":
            if not _cull(sx, 56, width):
                _draw_car(screen, sx, veh_y, v["color"])
        else:
            if not _cull(sx, 34, width):
                _draw_motorbike(screen, sx, veh_y, v["color"])

    # Background pedestrians stand just behind the lane, near the horizon.
    char_y = lane_top + 5
    for ch in bg_data["chars"]:
        sx = int(ch["x"]) - off
        if not _cull(sx, 16, width):
            phase = ch["phase"] + t * 1.6
            _draw_bg_char(screen, sx, char_y, ch["color"], ch["facing"], phase)
