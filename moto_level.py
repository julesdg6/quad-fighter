"""moto_level.py

Motorcycle combat level with forward-perspective (pseudo-3D) road.

The player rides into the screen; enemies and obstacles approach from
the distance, scale up as they get closer, and must be fought or avoided.

Controls during this level:
  LEFT / RIGHT  – steer bike (lateral movement)
  UP            – accelerate
  DOWN          – brake
  Z / punch     – left swipe attack
  X / kick      – right swipe attack
  ESC / Return  – exit back to menu

The level ends when the player travels TARGET_DISTANCE world units,
defeats the boss, or the player's health reaches zero.
"""

import math
import random

import pygame

from render import draw_fighter

# ── Pseudo-3D projection constants ────────────────────────────────────────────
_HORIZON_Y  = 190      # screen-y of the vanishing horizon
_FOCAL      = 300.0    # focal length  (world units ≈ pixels at scale 1)
_CAM_H      = 120.0    # camera height above road (world units)
_Z_NEAR     = 100.0    # player's fixed z-depth
_Z_FAR      = 2000.0   # far clip / enemy spawn depth
_ROAD_HALF  = 100.0    # road half-width (world units)
_PLR_ROAD   = 82.0     # player lateral boundary (± world units from centre)

# ── Gameplay tuning ───────────────────────────────────────────────────────────
_TARGET_DIST     = 6000    # world units to clear the level
_BASE_SPEED      = 320.0   # forward speed (world units / second)
_MAX_SPEED       = 560.0
_MIN_SPEED       = 80.0
_ACCEL_RATE      = 80.0    # speed change per-second when accelerating/braking
_LATERAL_SPEED   = 230.0   # lateral steering speed (world units / second)
_PLAYER_MAX_HP   = 100
_PLAYER_INVULN   = 90      # invincibility frames after taking a hit

# Enemy behaviour
_ENEMY_SPEED_BASE   = 200.0   # z-closure speed (world units / second)
_ENEMY_SPEED_RAND   = 80.0
_ENEMY_ATK_Z_RANGE  = 140.0   # z-distance from player that triggers attack
_ENEMY_ATK_X_RANGE  = 55.0    # lateral half-width of enemy attack zone
_ENEMY_ATK_DAMAGE   = 12
_ENEMY_ATK_COOLDOWN = 80      # frames between enemy attacks
_ENEMY_BASE_HP      = 30
_ENEMY_BOSS_HP      = 120
_ENEMY_KNOCKBACK_Z  = 240.0   # how far a hit knocks an enemy back (z)

# Player attack
_ATK_DURATION  = 18    # frames the attack arc is active
_ATK_COOLDOWN  = 22    # frames before another attack
_ATK_X_RANGE   = 65.0  # lateral reach (world units) of each swipe
_ATK_Z_RANGE   = 150.0 # z tolerance for a swipe to land
_ATK_DAMAGE    = 25

# Obstacles
_OBS_HALF_W    = 38.0   # obstacle half-width (world units) for collision
_OBS_DAMAGE    = 20

# Road rendering
_ROAD_BAND_Z   = 300.0   # z-period of alternating road bands
_STRIPE_Z_GAP  = 200.0   # world units between centre dashes

# Road curve animation
_CURVE_FREQ      = 0.20   # sinusoidal bend frequency (radians / second)
_CURVE_AMP       = 0.85   # maximum curve strength (fraction of full bend)
_CURVE_SMOOTHING = 1.8    # low-pass smoothing rate (higher = snappier)

# Scenery
_POST_SCROLL_FACTOR = 0.96  # lamp posts scroll slightly slower than road (parallax)

# Colours
_SKY_TOP     = (10,  14,  26)
_SKY_BOT     = (28,  22,  52)
_ROAD_COL    = (42,  42,  48)
_ROAD_COL2   = (50,  50,  58)   # alternating band
_EDGE_COL    = (200, 190, 160)  # road edge / kerb
_STRIPE_COL  = (230, 220, 170)  # centre dashes

_PLR_COL     = (70,  150, 240)
_ENM_COL     = (190,  55,  55)
_ENM_HIT_COL = (255, 200, 200)
_BOSS_COL    = (200,  80, 180)
_OBS_COL     = (90,  180,  60)
_HIT_COL     = (255, 230,  50)

# Palette matching the main game's player character (karate fighter)
_PLAYER_PALETTE = {
    "chest":           (236, 236, 240),
    "torso":           (248, 248, 252),
    "pelvis":          (238, 238, 242),
    "belt":            (28,  28,  30),
    "head":            (216, 196, 172),
    "face":            (188, 168, 145),
    "hair":            (28,  24,  20),
    "front_arm_upper": (248, 248, 252),
    "front_arm_lower": (242, 242, 246),
    "rear_arm_upper":  (232, 232, 238),
    "rear_arm_lower":  (228, 228, 234),
    "front_leg_upper": (246, 246, 250),
    "front_leg_lower": (240, 240, 246),
    "rear_leg_upper":  (228, 228, 234),
    "rear_leg_lower":  (222, 222, 228),
    "hands":           (212, 190, 162),
    "feet":            (202, 180, 154),
    "head_scale":      0.93,
    "shoulder_ratio":  0.26,
    "hip_ratio":       0.14,
    "arm_width":       0.19,
    "leg_width":       0.22,
    "idle_tilt":       0.01,
}


# ── Projection helper ─────────────────────────────────────────────────────────

def _proj(wx, wz, cx):
    """Project world (wx, wz) → screen (sx, sy, scale)."""
    z = max(1.0, float(wz))
    s = _FOCAL / z
    return int(cx + wx * s), int(_HORIZON_Y + _CAM_H * s), s


# ── Internal game-object classes ──────────────────────────────────────────────

class _Enemy:
    def __init__(self, wx, wz, speed, hp=_ENEMY_BASE_HP, is_boss=False):
        self.wx        = float(wx)
        self.wz        = float(wz)
        self.speed     = float(speed)
        self.hp        = hp
        self.max_hp    = hp
        self.is_boss   = is_boss
        self.atk_timer = 0      # counts up to _ENEMY_ATK_COOLDOWN
        self.attacking = False
        self.atk_frame = 0
        self.hit_flash = 0      # flash-colour frames remaining
        self.defeated  = False
        self.passed    = False  # went behind the player

    def update(self, dt, fwd_speed, player_wx, player_wz):
        # Close the distance
        self.wz -= (self.speed + fwd_speed) * dt

        # Drift laterally toward player when close
        if self.wz < _Z_NEAR * 5:
            side_offset = 32.0 if self.wx >= player_wx else -32.0
            target_wx   = player_wx + side_offset
            diff        = target_wx - self.wx
            step        = min(abs(diff), 55.0 * dt)
            self.wx    += step * (1.0 if diff > 0 else -1.0)

        if self.hit_flash > 0:
            self.hit_flash -= 1

        # Attack window
        near_z = abs(self.wz - player_wz) < _ENEMY_ATK_Z_RANGE
        near_x = abs(self.wx - player_wx) < _ENEMY_ATK_X_RANGE
        if near_z and near_x:
            if self.atk_timer <= 0:
                self.attacking  = True
                self.atk_frame  = 0
                self.atk_timer  = _ENEMY_ATK_COOLDOWN
            else:
                self.atk_timer -= 1
        else:
            if self.atk_timer > 0:
                self.atk_timer -= 1

        if self.attacking:
            self.atk_frame += 1
            if self.atk_frame > 18:
                self.attacking = False
                self.atk_frame = 0

        if self.wz < _Z_NEAR - 90:
            self.passed = True


class _Obstacle:
    def __init__(self, wx, wz, kind="barrier"):
        self.wx   = float(wx)
        self.wz   = float(wz)
        self.kind = kind

    def update(self, dt, fwd_speed):
        self.wz -= fwd_speed * dt


# ── Road drawing helpers ──────────────────────────────────────────────────────

def _draw_sky(screen, width, horizon_y):
    """Gradient sky: dark blue-purple at top fading to warm purple near horizon."""
    for y in range(0, horizon_y, 2):
        t = y / max(1, horizon_y)
        r = int(_SKY_TOP[0] + (_SKY_BOT[0] - _SKY_TOP[0]) * t)
        g = int(_SKY_TOP[1] + (_SKY_BOT[1] - _SKY_TOP[1]) * t)
        b = int(_SKY_TOP[2] + (_SKY_BOT[2] - _SKY_TOP[2]) * t)
        pygame.draw.rect(screen, (r, g, b), (0, y, width, 2))
    # Glow strip just above horizon
    for y in range(max(0, horizon_y - 8), horizon_y, 1):
        t = (y - (horizon_y - 8)) / 8
        pygame.draw.rect(screen, (int(60 * t), int(30 * t), int(80 * t)), (0, y, width, 1))


def _draw_buildings(screen, width, horizon_y, road_offset):
    """Draw a procedural city silhouette above the horizon (slow parallax)."""
    # Fixed building layout – deterministic without Random state
    layout = [
        (40,  55, 65, (18, 20, 40)),
        (115, 38, 45, (22, 18, 42)),
        (185, 58, 85, (14, 22, 44)),
        (268, 34, 58, (20, 20, 38)),
        (330, 68, 72, (17, 24, 46)),
        (420, 44, 52, (22, 18, 40)),
        (492, 56, 95, (13, 18, 42)),
        (565, 40, 62, (20, 22, 44)),
        (628, 64, 78, (16, 20, 40)),
        (710, 50, 58, (22, 20, 46)),
        (778, 54, 68, (18, 18, 38)),
        (840, 42, 50, (20, 22, 42)),
    ]
    total_span = 900
    scroll = int(road_offset * 0.03) % total_span

    for bx_base, bw, bh, col in layout:
        for wrap in (0, total_span):
            bx = bx_base - scroll + wrap
            if bx + bw < 0 or bx - bw > width:
                continue
            top = horizon_y - bh
            pygame.draw.rect(screen, col, (bx - bw // 2, top, bw, bh))
            # Rooftop antenna
            pygame.draw.line(screen,
                             (col[0] + 12, col[1] + 12, col[2] + 18),
                             (bx, top), (bx, top - 10), 1)
            # Windows (deterministic: combine bx_base + grid offsets for varied lit/dark)
            wc = (min(255, col[0] + 130), min(255, col[1] + 120),
                  min(255, col[2] + 80))
            for wy in range(top + 5, horizon_y - 4, 8):
                for wxi in range(5, bw - 4, 8):
                    if (bx_base + wxi * 3 + wy) % 4 != 0:  # ~75% of windows lit
                        pygame.draw.rect(screen, wc,
                                         (bx - bw // 2 + wxi, wy, 3, 4))


def _draw_road(screen, width, height, cx, road_offset, curve=0.0):
    """Draw pseudo-3D road with perspective bands, curves, edge kerbs,
    centre dashes and roadside lamp posts.

    curve: lateral bend strength (-1 = hard left, +1 = hard right).
    """

    def _road_cx(wz):
        """Screen x of the road centre at depth wz, shifted by curve."""
        t = max(0.0, float(wz) - _Z_NEAR) / (_Z_FAR - _Z_NEAR)
        return cx + curve * 160.0 * t * t

    def _sy(wz):
        _, sy, _ = _proj(0, wz, cx)
        return min(sy, height - 4)

    def _x(wx, wz):
        z = max(1.0, float(wz))
        sc = _FOCAL / z
        return int(_road_cx(wz) + wx * sc)

    # --- Base road surface ---
    lxn = _x(-_ROAD_HALF, _Z_NEAR)
    rxn = _x( _ROAD_HALF, _Z_NEAR)
    syn = _sy(_Z_NEAR)
    lxf = _x(-_ROAD_HALF, _Z_FAR)
    rxf = _x( _ROAD_HALF, _Z_FAR)
    syf = _sy(_Z_FAR)
    pygame.draw.polygon(screen, _ROAD_COL,
                        [(lxf, syf), (rxf, syf), (rxn, syn), (lxn, syn)])
    # Fill the strip between the near edge and the screen bottom (no gaps)
    syn_c = min(syn, height)
    if syn_c < height:
        pygame.draw.rect(screen, _ROAD_COL,
                         (lxn, syn_c, rxn - lxn, height - syn_c))

    # --- Alternating perspective bands ---
    num_slices = 20
    z_slices = [_Z_NEAR + (_Z_FAR - _Z_NEAR) * (i / num_slices) ** 0.5
                for i in range(num_slices + 1)]

    for i in range(num_slices):
        z0 = z_slices[i]
        z1 = z_slices[i + 1]
        if int((z0 + road_offset) / _ROAD_BAND_Z) % 2 == 0:
            continue
        sy0, sy1 = _sy(z0), _sy(z1)
        if sy0 <= sy1:
            continue
        lx0, rx0 = _x(-_ROAD_HALF, z0), _x(_ROAD_HALF, z0)
        lx1, rx1 = _x(-_ROAD_HALF, z1), _x(_ROAD_HALF, z1)
        pygame.draw.polygon(screen, _ROAD_COL2,
                            [(lx1, sy1), (rx1, sy1), (rx0, sy0), (lx0, sy0)])

    # --- Road edge lines ---
    num_edge = 24
    edge_zs = [_Z_NEAR + (_Z_FAR - _Z_NEAR) * (i / (num_edge - 1)) ** 0.5
               for i in range(num_edge)]
    left_pts, right_pts = [], []
    for z in edge_zs:
        sy = _sy(z)
        if _HORIZON_Y <= sy <= height:
            left_pts.append( (_x(-_ROAD_HALF, z), sy))
            right_pts.append((_x( _ROAD_HALF, z), sy))
    if len(left_pts)  >= 2:
        pygame.draw.lines(screen, _EDGE_COL, False, left_pts,  2)
    if len(right_pts) >= 2:
        pygame.draw.lines(screen, _EDGE_COL, False, right_pts, 2)

    # --- Kerb stripes (red / white alternating) ---
    kerb_period = 150.0
    z_range = _Z_FAR - _Z_NEAR
    for side in (-1, 1):
        for i in range(14):
            z0 = _Z_NEAR + ((i * kerb_period - road_offset) % z_range)
            z1 = min(z0 + kerb_period * 0.5, _Z_FAR)
            if z0 <= 0 or z0 >= _Z_FAR:
                continue
            sy0, sy1 = _sy(z0), _sy(z1)
            if sy0 <= sy1 or sy0 > height:
                continue
            mid_z = (z0 + z1) * 0.5
            kx    = _x(side * _ROAD_HALF, mid_z)
            kw    = max(2, int(abs(_x(side * _ROAD_HALF, z0) -
                                   _x(side * _ROAD_HALF, z1)) * 0.5))
            kh    = max(1, sy0 - sy1)
            col   = (210, 60, 60) if (i % 2 == 0) else (230, 230, 230)
            pygame.draw.rect(screen, col, (kx - kw // 2, sy1, kw, kh))

    # --- Centre dashes ---
    num_dashes = int(z_range / _STRIPE_Z_GAP) + 3
    for i in range(num_dashes):
        z = _Z_NEAR + ((i * _STRIPE_Z_GAP - road_offset) % z_range)
        if z <= 1.0 or z > _Z_FAR:
            continue
        _, sy, sc = _proj(0, z, cx)
        if sy < _HORIZON_Y or sy > height - 2:
            continue
        rcx = int(_road_cx(z))
        dw  = max(1, int(4 * sc))
        dh  = max(1, int(24 * sc))
        pygame.draw.rect(screen, _STRIPE_COL, (rcx - dw // 2, sy - dh, dw, dh))

    # --- Roadside lamp posts ---
    post_period = 210.0
    num_posts   = int(z_range / post_period) + 3
    for side in (-1, 1):
        post_wx = side * (_ROAD_HALF + 28.0)
        for i in range(num_posts):
            z = _Z_NEAR + ((i * post_period - road_offset * _POST_SCROLL_FACTOR) % z_range)
            if z <= _Z_NEAR or z > _Z_FAR * 0.97:
                continue
            _, post_sy, sc = _proj(0, z, cx)
            if post_sy < _HORIZON_Y or post_sy > height:
                continue
            post_sx = _x(post_wx, z)
            ph = max(3, int(55 * sc))
            pw = max(1, int(4 * sc))
            # Shaft
            pygame.draw.rect(screen, (52, 58, 78),
                             (post_sx - pw // 2, post_sy - ph, pw, ph))
            # Arm pointing inward over road
            arm_len = max(2, int(14 * sc)) * (-side)
            arm_y   = post_sy - ph
            arm_dy  = max(1, int(4 * sc))
            pygame.draw.line(screen, (52, 58, 78),
                             (post_sx, arm_y),
                             (post_sx + arm_len, arm_y - arm_dy),
                             max(1, pw // 2))
            # Lamp globe
            lamp_x = post_sx + arm_len
            lamp_y = arm_y - arm_dy
            lr = max(1, int(5 * sc))
            pygame.draw.circle(screen, (220, 210, 145), (lamp_x, lamp_y), lr)
            pygame.draw.circle(screen, (255, 248, 200), (lamp_x, lamp_y),
                               max(1, lr - 1))


# ── Bike / rider rendering ────────────────────────────────────────────────────

def _draw_bike(screen, sx, sy, scale, color, facing, lean=0, draw_rider=True):
    """Draw a polygon motorcycle + rider.

    facing:  1 = front-on (enemy approaching),  -1 = rear view (player)
    lean:   -1 / 0 / 1  – steering lean direction
    """

    def s(v):
        return max(1, int(v * scale))

    lx     = lean * s(4)             # lateral lean offset (pixels)
    dark   = tuple(max(0, c - 55) for c in color)
    metal  = (82, 88, 102)
    chrome = (168, 174, 186)
    w_col  = (25, 25, 30)            # tyre rubber
    r_col  = (138, 144, 158)         # wheel rim

    if facing == -1:
        # ── Rear view (player) ───────────────────────────────────────────────
        bx = sx + lx   # bike lateral centre

        # Rear wheel
        wr, wh = s(15), s(6)
        pygame.draw.ellipse(screen, w_col, (bx - wr, sy - wh, wr * 2, wh * 2))
        pygame.draw.ellipse(screen, r_col, (bx - wr, sy - wh, wr * 2, wh * 2),
                            max(1, s(2)))
        pygame.draw.circle(screen, metal, (bx, sy - wh + s(1)), s(3))

        # Swing arm / rear shock
        frame_base = sy - wh - s(2)
        seat_y     = sy - s(25)
        pygame.draw.line(screen, metal, (bx, frame_base), (bx, seat_y + s(4)),
                         max(1, s(3)))

        # Rear frame / sub-frame
        fw = s(10)
        pygame.draw.polygon(screen, dark, [
            (bx - fw, frame_base),
            (bx + fw, frame_base),
            (bx + s(7), seat_y),
            (bx - s(7), seat_y),
        ])

        # Exhaust pipes (both sides)
        for side in (-1, 1):
            ex0 = (bx + side * s(9),  seat_y + s(2))
            ex1 = (bx + side * s(14), sy - s(2))
            pygame.draw.line(screen, (128, 104, 68), ex0, ex1, max(1, s(2)))
            pygame.draw.circle(screen, (98, 78, 52), ex1, max(1, s(2)))

        # Seat pad
        pygame.draw.ellipse(screen, (14, 14, 18),
                            (bx - s(9), seat_y - s(2), s(18), s(5)))

        # Tail lights
        for tx_off in (-s(5), s(2)):
            pygame.draw.rect(screen, (200, 34, 34),
                             (bx + tx_off, frame_base - s(1), s(4), s(2)))

        # ── Rider ────────────────────────────────────────────────────────────
        if draw_rider:
            hip_y = seat_y + s(1)
            fwd   = s(8)            # forward lean of the torso

            # Torso
            t_top_x = bx - fwd
            t_top_y = hip_y - s(17)
            pygame.draw.polygon(screen, color, [
                (bx - s(6),       hip_y),
                (bx + s(6),       hip_y),
                (bx + s(4) - fwd, t_top_y),
                (bx - s(4) - fwd, t_top_y),
            ])

            # Helmet
            hr = s(5)
            hx = t_top_x - s(1)
            hy = t_top_y - s(1)
            pygame.draw.circle(screen, dark, (hx, hy), hr)
            pygame.draw.arc(screen, chrome,
                            (hx - hr, hy - hr, hr * 2, hr * 2),
                            0.2, 2.8, max(1, s(1)))

            # Handlebars
            bar_x  = bx - fwd - s(4)
            bar_y  = hip_y - s(11)
            bar_hw = s(11)
            pygame.draw.line(screen, metal,
                             (bar_x - bar_hw, bar_y),
                             (bar_x + bar_hw, bar_y), max(1, s(2)))

            # Arms
            arm_root_x = bx - s(3) - fwd // 2
            arm_root_y = t_top_y + s(4)
            pygame.draw.line(screen, color,
                             (arm_root_x, arm_root_y),
                             (bar_x - bar_hw // 2, bar_y), max(1, s(2)))
            pygame.draw.line(screen, color,
                             (arm_root_x + s(6), arm_root_y),
                             (bar_x + bar_hw // 2, bar_y), max(1, s(2)))

            # Legs (pegs on either side)
            for side in (-1, 1):
                knee = (bx + side * s(14), sy - s(7))
                pygame.draw.line(screen, color,
                                 (bx + side * s(5), hip_y), knee,
                                 max(1, s(2)))

    else:
        # ── Front view (enemy) ───────────────────────────────────────────────
        fx = sx + lx   # bike lateral centre

        # Front wheel
        wr, wh = s(13), s(5)
        pygame.draw.ellipse(screen, w_col, (fx - wr, sy - wh, wr * 2, wh * 2))
        pygame.draw.ellipse(screen, r_col, (fx - wr, sy - wh, wr * 2, wh * 2),
                            max(1, s(2)))
        pygame.draw.circle(screen, metal, (fx, sy), s(3))

        # Front forks
        fork_top = sy - s(21)
        pygame.draw.line(screen, chrome,
                         (fx - s(3), fork_top), (fx - s(2), sy - wh),
                         max(1, s(2)))
        pygame.draw.line(screen, chrome,
                         (fx + s(3), fork_top), (fx + s(2), sy - wh),
                         max(1, s(2)))

        # Headlight
        hl_y = fork_top - s(2)
        hl_r = s(4)
        pygame.draw.circle(screen, (40, 40, 62), (fx, hl_y), hl_r)
        pygame.draw.circle(screen, (245, 235, 162), (fx, hl_y), max(1, s(2)))

        # Handlebars
        bar_y  = fork_top - s(5)
        bar_hw = s(13)
        pygame.draw.line(screen, metal,
                         (fx - bar_hw, bar_y), (fx + bar_hw, bar_y),
                         max(1, s(2)))
        # Bar ends angle down
        pygame.draw.line(screen, metal,
                         (fx - bar_hw, bar_y),
                         (fx - bar_hw + s(2), bar_y + s(3)), max(1, s(1)))
        pygame.draw.line(screen, metal,
                         (fx + bar_hw, bar_y),
                         (fx + bar_hw - s(2), bar_y + s(3)), max(1, s(1)))

        # Rider torso (front-facing, enemy)
        if draw_rider:
            t_top = bar_y - s(15)
            pygame.draw.polygon(screen, color, [
                (fx - s(7), bar_y),
                (fx + s(7), bar_y),
                (fx + s(4), t_top),
                (fx - s(4), t_top),
            ])

            # Helmet
            hr    = s(5)
            helm_y = t_top - hr
            pygame.draw.circle(screen, dark, (fx, helm_y), hr)
            pygame.draw.arc(screen, chrome,
                            (fx - hr, helm_y - hr, hr * 2, hr * 2),
                            0.2, 2.8, max(1, s(1)))

            # Arms reaching to handlebars
            arm_y = t_top + s(5)
            pygame.draw.line(screen, color,
                             (fx - s(4), arm_y), (fx - bar_hw, bar_y),
                             max(1, s(2)))
            pygame.draw.line(screen, color,
                             (fx + s(4), arm_y), (fx + bar_hw, bar_y),
                             max(1, s(2)))

            # Legs
            for side in (-1, 1):
                knee = (fx + side * s(11), bar_y + s(5))
                pygame.draw.line(screen, color,
                                 (fx + side * s(5), bar_y), knee,
                                 max(1, s(2)))


def _draw_obstacle(screen, sx, sy, scale, kind):
    """Draw a road obstacle at (sx, sy) with depth scale."""

    def s(v):
        return max(1, int(v * scale))

    if kind == "car":
        w = s(14)
        h = s(7)
        pygame.draw.rect(screen, _OBS_COL, (sx - w, sy - h, w * 2, h))
        # Windshield
        pygame.draw.rect(screen, (50, 140, 200),
                         (sx - s(5), sy - h - s(3), s(10), s(3)))
        # Wheels
        for ox in (-w - s(1), w - s(6)):
            pygame.draw.ellipse(screen, (70, 70, 70),
                                (sx + ox, sy - s(3), s(7), s(3)))
    elif kind == "cone":
        pts = [
            (sx,        sy - s(9)),
            (sx - s(5), sy),
            (sx + s(5), sy),
        ]
        pygame.draw.polygon(screen, (220, 75, 30), pts)
        # Reflective band
        pygame.draw.line(screen, (240, 220, 0),
                         (sx - s(3), sy - s(4)), (sx + s(3), sy - s(4)),
                         max(1, s(1)))
    else:   # barrier / default
        w = s(14)
        h = s(5)
        # Base beam
        pygame.draw.rect(screen, (195, 195, 30), (sx - w, sy - h, w * 2, h))
        # Red stripe above
        pygame.draw.rect(screen, (190, 40, 40),  (sx - w, sy - h * 3, w * 2, h))


# ── Main level class ──────────────────────────────────────────────────────────

class MotoLevel:
    """Self-contained motorcycle combat level.

    Call ``run()`` to play.  Returns ``"complete"``, ``"dead"``, or
    ``"exit"`` (player pressed ESC / Return to abort).
    """

    def __init__(self, screen, width, height, fps, settings, font, acid, sfx,
                 joystick=None):
        self.screen   = screen
        self.width    = width
        self.height   = height
        self.fps      = fps
        self.settings = settings
        self.font     = font
        self.acid     = acid
        self.sfx      = sfx
        self.joystick = joystick
        self.cx       = width // 2
        self._clock   = pygame.time.Clock()

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self):
        """Play the moto level.  Returns ``"complete"``, ``"dead"``, or
        ``"exit"``."""
        self._reset()
        while True:
            dt = min(self._clock.tick(self.fps) / 1000.0, 0.05)
            result = self._handle_events()
            if result:
                return result
            self._update(dt)
            self._draw()
            pygame.display.flip()
            self._frame += 1

            if self.player_hp <= 0:
                self._show_overlay("YOU CRASHED", (230, 60, 60), (100, 0, 0, 160))
                return "dead"

            if self._distance >= _TARGET_DIST and not self._boss_alive:
                self._show_overlay("ROAD CLEAR!", (80, 240, 120), (0, 80, 0, 140))
                return "complete"

    # ── State initialisation ──────────────────────────────────────────────────

    def _reset(self):
        self._frame         = 0
        self._distance      = 0.0
        self._fwd_speed     = _BASE_SPEED
        self._road_offset   = 0.0

        self.player_wx      = 0.0
        self.player_wz      = _Z_NEAR
        self.player_hp      = _PLAYER_MAX_HP
        self._invuln        = 0
        self._lean          = 0

        self._atk_l_timer   = 0    # frames left on left-attack arc
        self._atk_r_timer   = 0
        self._atk_l_cd      = 0    # cooldown
        self._atk_r_cd      = 0

        self._enemies       = []
        self._obstacles     = []
        self._hit_flashes   = []   # list of (sx, sy, timer)

        self._spawn_idx     = 0
        self._boss_alive    = False
        self._schedule      = self._build_schedule()

        # Road curve state
        self._curve        = 0.0   # current lateral curvature (-1 to 1)
        self._curve_timer  = 0.0   # time accumulator driving sinusoidal bends

    def _build_schedule(self):
        sched = []
        # Regular enemy waves every ~350 world units
        for d in range(400, _TARGET_DIST, 340):
            wx = random.uniform(-50.0, 50.0)
            sched.append({"dist": d, "type": "enemy", "wx": wx})
        # Some grouped waves (two enemies close together)
        for d in range(700, _TARGET_DIST, 520):
            sched.append({"dist": d,      "type": "enemy", "wx":  45.0})
            sched.append({"dist": d + 20, "type": "enemy", "wx": -45.0})
        # Obstacles
        obs_kinds = ["cone", "cone", "barrier", "car"]
        for d in range(500, _TARGET_DIST, 200):
            wx   = random.choice([-48.0, 0.0, 48.0])
            kind = random.choice(obs_kinds)
            sched.append({"dist": d, "type": "obstacle", "wx": wx, "kind": kind})
        # Boss near the end
        sched.append({"dist": _TARGET_DIST - 300, "type": "boss", "wx": 0.0})
        sched.sort(key=lambda e: e["dist"])
        return sched

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE,):
                    return "exit"
        return None

    def _read_input(self):
        keys = pygame.key.get_pressed()
        kb   = self.settings.keyboard
        ctrl = self.settings.read_controller(self.joystick)
        return {
            "left":      keys[kb.get("move_left",  pygame.K_LEFT)]  or ctrl.get("move_left",  False),
            "right":     keys[kb.get("move_right", pygame.K_RIGHT)] or ctrl.get("move_right", False),
            "up":        keys[kb.get("move_up",    pygame.K_UP)]    or ctrl.get("move_up",    False),
            "down":      keys[kb.get("move_down",  pygame.K_DOWN)]  or ctrl.get("move_down",  False),
            "atk_left":  keys[kb.get("punch",      pygame.K_z)]     or ctrl.get("punch",      False),
            "atk_right": keys[kb.get("kick",       pygame.K_x)]     or ctrl.get("kick",       False),
        }

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self, dt):
        inp = self._read_input()
        self.acid.tick(dt)

        # Forward speed
        if inp["up"]:
            self._fwd_speed = min(_MAX_SPEED, self._fwd_speed + _ACCEL_RATE * dt * 60)
        elif inp["down"]:
            self._fwd_speed = max(_MIN_SPEED, self._fwd_speed - _ACCEL_RATE * dt * 60)

        # Distance progress
        self._distance    += self._fwd_speed * dt
        self._road_offset += self._fwd_speed * dt

        # Sinusoidal road curve
        self._curve_timer += dt
        target_curve = math.sin(self._curve_timer * _CURVE_FREQ) * _CURVE_AMP
        self._curve += (target_curve - self._curve) * _CURVE_SMOOTHING * dt

        # Lateral steering
        if inp["left"]:
            self.player_wx -= _LATERAL_SPEED * dt
            self._lean      = -1
        elif inp["right"]:
            self.player_wx += _LATERAL_SPEED * dt
            self._lean      = 1
        else:
            self._lean = 0
        self.player_wx = max(-_PLR_ROAD, min(_PLR_ROAD, self.player_wx))

        # Attacks
        if inp["atk_left"] and self._atk_l_cd <= 0 and self._atk_l_timer <= 0:
            self._atk_l_timer = _ATK_DURATION
            self._atk_l_cd    = _ATK_COOLDOWN
            self.sfx.play("punch")
        if inp["atk_right"] and self._atk_r_cd <= 0 and self._atk_r_timer <= 0:
            self._atk_r_timer = _ATK_DURATION
            self._atk_r_cd    = _ATK_COOLDOWN
            self.sfx.play("kick")

        if self._atk_l_timer > 0: self._atk_l_timer -= 1
        if self._atk_r_timer > 0: self._atk_r_timer -= 1
        if self._atk_l_cd    > 0: self._atk_l_cd    -= 1
        if self._atk_r_cd    > 0: self._atk_r_cd    -= 1

        if self._invuln > 0:
            self._invuln -= 1

        # Spawn scheduled entities
        self._process_spawns()

        # Update + resolve enemies
        surviving = []
        for e in self._enemies:
            e.update(dt, self._fwd_speed, self.player_wx, self.player_wz)
            self._check_player_hits_enemy(e)
            if not e.defeated and not e.passed:
                self._check_enemy_hits_player(e)
            if not e.defeated and not e.passed:
                surviving.append(e)
        self._enemies = surviving

        # Update + resolve obstacles
        remaining = []
        for obs in self._obstacles:
            obs.update(dt, self._fwd_speed)
            if obs.wz < _Z_NEAR - 60:
                continue                   # passed behind
            # Collision
            if abs(obs.wz - self.player_wz) < 60.0:
                if abs(obs.wx - self.player_wx) < _OBS_HALF_W + 20.0:
                    if self._invuln <= 0:
                        self.player_hp -= _OBS_DAMAGE
                        self._invuln    = _PLAYER_INVULN
                        self.sfx.play("player_hurt")
                    continue  # remove obstacle on contact
            remaining.append(obs)
        self._obstacles = remaining

        # Decay hit flashes
        self._hit_flashes = [(x, y, t - 1) for x, y, t in self._hit_flashes if t > 1]

        # Boss defeat check
        if self._boss_alive and not any(e.is_boss for e in self._enemies):
            self._boss_alive = False
            # Small health reward
            self.player_hp = min(_PLAYER_MAX_HP, self.player_hp + 15)

    def _process_spawns(self):
        while self._spawn_idx < len(self._schedule):
            entry = self._schedule[self._spawn_idx]
            if self._distance < entry["dist"]:
                break
            self._spawn_idx += 1

            if entry["type"] in ("enemy", "boss"):
                is_boss = entry["type"] == "boss"
                speed   = (_ENEMY_SPEED_BASE * 0.7) if is_boss else (
                    _ENEMY_SPEED_BASE + random.uniform(0, _ENEMY_SPEED_RAND)
                )
                hp = _ENEMY_BOSS_HP if is_boss else _ENEMY_BASE_HP
                # Spawn at 75-85% of Z_FAR
                spawn_z = _Z_FAR * random.uniform(0.72, 0.86)
                e = _Enemy(entry["wx"], spawn_z, speed, hp=hp, is_boss=is_boss)
                self._enemies.append(e)
                if is_boss:
                    self._boss_alive = True
            elif entry["type"] == "obstacle":
                spawn_z = _Z_FAR * 0.75
                obs = _Obstacle(entry["wx"], spawn_z, entry.get("kind", "cone"))
                self._obstacles.append(obs)

    def _check_player_hits_enemy(self, enemy):
        if enemy.hp <= 0 or enemy.defeated:
            return
        z_ok = abs(enemy.wz - self.player_wz) < _ATK_Z_RANGE

        # Left swipe: hits enemies to the player's left
        if self._atk_l_timer > 0 and z_ok:
            if self.player_wx - _ATK_X_RANGE < enemy.wx < self.player_wx + 12.0:
                self._land_hit(enemy, is_left=True)

        # Right swipe: hits enemies to the player's right
        if self._atk_r_timer > 0 and z_ok:
            if self.player_wx - 12.0 < enemy.wx < self.player_wx + _ATK_X_RANGE:
                self._land_hit(enemy, is_left=False)

    def _land_hit(self, enemy, is_left):
        enemy.hp       -= _ATK_DAMAGE
        enemy.hit_flash = 10
        enemy.wz       += _ENEMY_KNOCKBACK_Z      # knocked back (deeper)
        sx, sy, _       = _proj(enemy.wx, max(enemy.wz, _Z_NEAR), self.cx)
        self._hit_flashes.append((sx, sy, 10))
        self.sfx.play("impact")
        self.sfx.play("enemy_hurt")
        if is_left:
            self._atk_l_timer = 0   # consume this swing
        else:
            self._atk_r_timer = 0
        if enemy.hp <= 0:
            enemy.defeated = True

    def _check_enemy_hits_player(self, enemy):
        if not enemy.attacking or self._invuln > 0:
            return
        if enemy.atk_frame != 8:   # only the "mid-swing" frame deals damage
            return
        z_ok = abs(enemy.wz - self.player_wz) < _ENEMY_ATK_Z_RANGE
        x_ok = abs(enemy.wx - self.player_wx) < _ENEMY_ATK_X_RANGE
        if z_ok and x_ok:
            self.player_hp -= _ENEMY_ATK_DAMAGE
            self._invuln    = _PLAYER_INVULN
            self.sfx.play("player_hurt")
            self.sfx.play("impact")

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw(self):
        # Clear every pixel to prevent ghosting artifacts from previous frames
        self.screen.fill(_SKY_TOP)
        _draw_sky(self.screen, self.width, _HORIZON_Y)
        _draw_buildings(self.screen, self.width, _HORIZON_Y, self._road_offset)
        _draw_road(self.screen, self.width, self.height, self.cx,
                   self._road_offset, self._curve)
        self._draw_entities()
        self._draw_player()
        self._draw_hit_flashes()
        self._draw_hud()

    def _draw_entities(self):
        # Gather all visible entities and sort far → near for painter's order
        all_ents = (
            [("enemy", e.wx, e.wz, e) for e in self._enemies]
            + [("obs",  o.wx, o.wz, o) for o in self._obstacles]
        )
        all_ents.sort(key=lambda t: t[2], reverse=True)

        for kind, wx, wz, ent in all_ents:
            if wz < _Z_NEAR - 40 or wz > _Z_FAR:
                continue
            sx, sy, sc = _proj(wx, max(float(wz), 1.0), self.cx)
            if kind == "enemy":
                if ent.hit_flash > 0:
                    color = _ENM_HIT_COL
                elif ent.is_boss:
                    color = _BOSS_COL
                else:
                    color = _ENM_COL
                lunge = 0
                if ent.attacking:
                    lunge = int(6 * sc * (1 if ent.wx >= self.player_wx else -1))
                _draw_bike(self.screen, sx + lunge, sy, sc, color, 1)

                # Boss HP bar
                if ent.is_boss:
                    bw = max(6, int(52 * sc))
                    bh = max(2, int(5 * sc))
                    bx = sx - bw // 2
                    by = sy - int(22 * sc)
                    ratio = max(0.0, ent.hp / ent.max_hp)
                    pygame.draw.rect(self.screen, (60, 0, 0), (bx, by, bw, bh))
                    pygame.draw.rect(self.screen, (220, 40, 40),
                                     (bx, by, int(bw * ratio), bh))
            elif kind == "obs":
                _draw_obstacle(self.screen, sx, sy, sc, ent.kind)

    def _draw_player(self):
        sx, sy, sc = _proj(self.player_wx, self.player_wz, self.cx)
        # Flicker when invulnerable
        if self._invuln > 0 and (self._frame // 4) % 2 == 0:
            return
        # Attack arm indicators
        if self._atk_l_timer > 0:
            arm_x = sx - int(24 * sc)
            arm_y = sy - int(9 * sc)
            pygame.draw.line(self.screen, _HIT_COL,
                             (sx, arm_y), (arm_x, arm_y),
                             max(1, int(3 * sc)))
        if self._atk_r_timer > 0:
            arm_x = sx + int(24 * sc)
            arm_y = sy - int(9 * sc)
            pygame.draw.line(self.screen, _HIT_COL,
                             (sx, arm_y), (arm_x, arm_y),
                             max(1, int(3 * sc)))
        _draw_bike(self.screen, sx, sy, sc, _PLR_COL, -1, self._lean,
                   draw_rider=False)

        # Draw the karate fighter (same character as the main game) on the bike seat.
        # The fighter is shown in side-view, seated in a crouched riding stance.
        s_val = float(sc)
        char_w = max(16, int(22 * s_val))
        char_h = max(32, int(48 * s_val))
        seat_y = sy - max(1, int(25 * s_val))
        hip_y_rider = seat_y + max(1, int(1 * s_val))
        fwd_off = max(1, int(8 * s_val))
        cx_char = sx - fwd_off + self._lean * max(1, int(4 * s_val))
        body_rect = pygame.Rect(
            cx_char - char_w // 2,
            hip_y_rider - char_h,
            char_w,
            char_h,
        )
        draw_fighter(
            self.screen,
            body_rect=body_rect,
            facing=1,
            palette=_PLAYER_PALETTE,
            pose="crouch",
        )

    def _draw_hit_flashes(self):
        for x, y, t in self._hit_flashes:
            r = max(2, t * 3)
            pygame.draw.circle(self.screen, _HIT_COL, (x, y), r, 2)

    def _draw_hud(self):
        # Distance progress bar (top centre)
        progress = min(1.0, self._distance / max(1, _TARGET_DIST))
        bw, bh = 220, 12
        bx = self.cx - bw // 2
        by = 14
        pygame.draw.rect(self.screen, (30, 35, 55), (bx, by, bw, bh))
        pygame.draw.rect(self.screen, (55, 175, 85), (bx, by, int(bw * progress), bh))
        pygame.draw.rect(self.screen, (130, 130, 185), (bx, by, bw, bh), 1)
        dist_lbl = self.font.render(
            f"{int(self._distance)}/{_TARGET_DIST}", True, (180, 210, 190))
        self.screen.blit(dist_lbl, (bx + bw + 8, by - 1))

        # HP bar (top left)
        hp_ratio = max(0.0, self.player_hp / _PLAYER_MAX_HP)
        if hp_ratio > 0.6:
            hp_col = (55, 195, 80)
        elif hp_ratio > 0.3:
            hp_col = (215, 175, 40)
        else:
            hp_col = (215, 55, 55)
        hp_lbl = self.font.render("HP", True, (200, 200, 205))
        self.screen.blit(hp_lbl, (14, 14))
        pygame.draw.rect(self.screen, (30, 35, 55), (44, 17, 120, 10))
        pygame.draw.rect(self.screen, hp_col,       (44, 17, int(120 * hp_ratio), 10))
        pygame.draw.rect(self.screen, (130, 130, 175), (44, 17, 120, 10), 1)

        # Speed readout
        spd_txt = self.font.render(f"SPD {int(self._fwd_speed)}", True, (160, 190, 230))
        self.screen.blit(spd_txt, (14, 32))

        # Boss warning
        if self._boss_alive and self._enemies:
            boss = next((e for e in self._enemies if e.is_boss), None)
            if boss:
                warn = self.font.render("!  BOSS INCOMING  !", True, (255, 70, 70))
                self.screen.blit(warn, (self.cx - warn.get_width() // 2, 50))

        # Attack feedback labels (screen sides)
        if self._atk_l_timer > 0:
            atk_txt = self.font.render("◄ LEFT SWIPE", True, _HIT_COL)
            self.screen.blit(atk_txt, (14, self.height // 2 - 12))
        if self._atk_r_timer > 0:
            atk_txt = self.font.render("RIGHT SWIPE ►", True, _HIT_COL)
            self.screen.blit(atk_txt,
                             (self.width - atk_txt.get_width() - 14,
                              self.height // 2 - 12))

        # Controls hint (bottom centre)
        hint = self.font.render(
            "←→ STEER   ↑↓ SPEED   Z LEFT ATTACK   X RIGHT ATTACK   ESC EXIT",
            True, (100, 105, 145),
        )
        self.screen.blit(hint, (self.cx - hint.get_width() // 2, self.height - 20))

    # ── End-of-level overlays ─────────────────────────────────────────────────

    def _show_overlay(self, message, text_color, bg_rgba):
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill(bg_rgba)
        self.screen.blit(overlay, (0, 0))
        txt = self.font.render(message, True, text_color)
        self.screen.blit(
            txt, (self.cx - txt.get_width() // 2, self.height // 2 - 14))
        pygame.display.flip()
        pygame.time.wait(2200)
