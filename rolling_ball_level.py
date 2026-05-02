"""rolling_ball_level.py

Rolling Ball Assault Course – 3D behind-the-ball camera mode.

Up to 4 players race through a timed 3D assault course.
Camera sits behind and above each player's ball, giving a Super Monkey Ball /
Marble Madness-style perspective view.  Split-screen for 2–4 players.

RollingBallLevel.run() returns "complete" | "exit".

Controls
--------
Player 1 : Arrow keys  (left/right = steer, up = accelerate, down = brake)
Player 2 : WASD
Player 3 : Joystick 0  (Left-stick / D-pad)
Player 4 : Joystick 1  (Left-stick / D-pad)
"""

from __future__ import annotations

import math
import random

import pygame

from base_level import BaseLevel
from settings import AXIS_DEADZONE

# ── Projection ────────────────────────────────────────────────────────────────

_FOCAL_BASE = 290.0    # base focal length (scales proportionally with vp height)
_CAM_H      = 70.0     # camera height above the track floor
_CAM_DIST   = 140.0    # camera sits this many units BEHIND the ball
_Z_NEAR     = 22.0     # near-clip distance (relative to camera)
_Z_FAR      = 2600.0   # far-clip distance (relative to camera)
_HORIZON    = 0.35     # horizon position as fraction of viewport height

# ── Track ─────────────────────────────────────────────────────────────────────

_FINISH_Z = 7200       # Z position of the finish line

# Control points: (z, left_x, right_x, height)
# Values are linearly interpolated between adjacent points.
# height = track floor elevation above the global ground plane.
_TRACK_CTRL: list[tuple] = [
    (   0, -120,  120,   0),   # wide starting straight
    ( 600, -120,  120,   0),
    ( 900,  -68,   68,   0),   # narrows – first challenge
    (1200,  -68,   68,   0),
    (1400, -115,  115,   0),   # opens for bumper field
    (1900, -115,  115,   0),
    (2100,  -88,   88,   0),   # narrows – moving-wall zone
    (2500,  -88,   88,   0),
    (2700,  -78,   78,   0),   # barrier slalom
    (3300,  -78,   78,   0),
    (3500, -102,  102,  36),   # ramp begins to rise
    (3900, -102,  102,  68),   # elevated plateau
    (4300,  -88,   88,  68),   # plateau continues – spin bars
    (4700,  -82,   82,  32),   # ramp descends
    (5100,  -82,   82,   0),   # back to ground
    (5300, -108,  108,   0),   # bounce-pad corridor
    (5800, -108,  108,   0),
    (6000, -130,  130,   0),   # final sprint
    (7200, -130,  130,   0),   # finish line
]

_CHECKPOINTS = [1200, 2500, 3800, 5200]   # Z positions of checkpoint gates

# ── Bumpers: (z, x, r) ────────────────────────────────────────────────────────

_BUMPER_DEFS: list[tuple] = [
    (1500,  32, 22),
    (1500, -46, 22),
    (1600,   0, 28),
    (1700,  58, 20),
    (1700, -58, 20),
    (1780,  28, 24),
    (1780, -28, 24),
    (1860,   0, 18),
]

# ── Barriers: (z, x, half_w, depth_z) ────────────────────────────────────────

_BARRIER_DEFS: list[tuple] = [
    ( 960,  32, 10, 14),
    (1010, -26, 10, 14),
    (1090,  44, 10, 14),
    (2760, -22, 12, 16),
    (2840,  48, 12, 16),
    (2930, -42, 10, 14),
    (3030,  16, 10, 14),
    (3110, -32, 10, 14),
    (3200,  52, 10, 14),
]

# ── Moving walls: (z, base_x, half_w, height_wld, amplitude, speed_rad, phase)
# Oscillate laterally at a fixed Z position.

_MWALL_DEFS: list[tuple] = [
    (2200, 0, 12, 80, 54, 0.030, 0.00),
    (2300, 0, 12, 80, 54, 0.030, math.pi),
    (2400, 0, 12, 80, 44, 0.025, 0.60),
    (2480, 0, 12, 78, 40, 0.028, 1.50),
]

# ── Spin bars: (z, pivot_x, length, ang_speed_rad, phase_rad) ─────────────────
# Rotate in the XZ plane (horizontal sweep).

_SPINBAR_DEFS: list[tuple] = [
    (4400,   0, 82,  0.040, 0.00),
    (4540,  22, 72, -0.050, 1.00),
    (4680,   0, 78,  0.035, 2.10),
    (4830, -16, 88, -0.038, 0.80),
]

# ── Bounce pads: (z, x, r, boost_vz, boost_vh) ────────────────────────────────

_BOUNCEPAD_DEFS: list[tuple] = [
    (5390, -44, 28, 190,  90),
    (5460,  44, 28, 190,  90),
    (5570,   0, 32, 240, 115),
    (5700, -52, 26, 170,  80),
    (5810,  52, 26, 170,  80),
]

# ── Gaps/pits: (z_start, z_end, x_left, x_right) ─────────────────────────────

_GAP_DEFS: list[tuple] = [
    (4760, 4840,  18,  80),   # right-side gap on the descent
    (4920, 5000, -80, -18),   # left-side gap
]

# ── Physics ───────────────────────────────────────────────────────────────────

_BALL_COLL_R  = 16.0   # collision radius (world units)
_FWD_ACCEL    = 190.0  # forward acceleration (world-units / s²)
_FWD_DECEL    = 270.0  # braking deceleration
_LAT_ACCEL    = 320.0  # lateral steering acceleration
_LAT_FRIC_FPS = 0.82   # per-frame lateral damping at 60 fps
_MAX_FWD      = 520.0  # max forward speed
_GRAVITY      = 740.0  # downward acceleration when airborne
_WALL_DAMP    = 0.42   # lateral speed kept after wall bounce
_BUMP_DAMP    = 0.60   # speed kept after bumper hit
_BALL_BOUNCE  = 0.65   # speed kept after ball–ball collision
_AUTO_SPEED   = 120.0  # initial / idle forward speed

# ── Race ──────────────────────────────────────────────────────────────────────

_RACE_SECS      = 180
_RESPAWN_FRAMES = 90
_FALL_FRAMES    = 38
_INVULN_FRAMES  = 90

# ── Colours ───────────────────────────────────────────────────────────────────

_SKY_TOP     = (8,  10,  22)
_SKY_BOT     = (26, 20,  50)
_FLOOR_COL   = (30, 26,  48)
_FLOOR_ALT   = (36, 30,  58)
_EDGE_COL    = (50, 160, 225)
_EDGE_DARK   = (22,  80, 145)
_BARRIER_COL = (90, 185,  62)
_BARRIER_DRK = (42,  94,  26)
_BUMPER_COL  = (255, 182,  42)
_BUMPER_DRK  = (145,  92,  22)
_MWALL_COL   = (125,  82, 225)
_MWALL_DRK   = ( 62,  42, 145)
_SPINBAR_COL = (255,  82,  82)
_SPINBAR_PIV = (205,  42,  42)
_BPAD_COL    = ( 82, 255, 202)
_BPAD_RING   = ( 32, 162, 125)
_CHKPT_COL   = ( 62, 225, 182)
_FINISH_COL  = (255, 222,  62)
_FINISH_ALT  = ( 32,  32,  32)
_GAP_COL     = (  6,   4,  14)
_GAP_RIM     = ( 42,  22,  62)
_HUD_BG      = ( 16,  14,  32)
_TIMER_OK    = ( 82, 222, 125)
_TIMER_LOW   = (255,  82,  82)
_SPLIT_LINE  = ( 62,  62,  82)
_VOID_COL    = ( 12,   8,  24)   # colour outside the track bounds

_PLAYER_COLS: list[tuple] = [
    ((100, 180, 255), ( 30,  80, 160), (200, 230, 255), (120, 200, 255)),  # P1 blue
    ((255, 100, 100), (160,  30,  30), (255, 210, 210), (255, 140, 140)),  # P2 red
    (( 80, 220, 120), ( 30, 120,  60), (180, 255, 200), (100, 255, 160)),  # P3 green
    ((200, 100, 255), (100,  30, 180), (230, 190, 255), (220, 130, 255)),  # P4 purple
]

_PLACE_LABELS = ["1ST", "2ND", "3RD", "4TH"]

# ── Track geometry helper ─────────────────────────────────────────────────────


def _track_at_z(z: float) -> tuple[float, float, float]:
    """Return (left_x, right_x, height) at world-Z by linear interpolation."""
    pts = _TRACK_CTRL
    if z <= pts[0][0]:
        return float(pts[0][1]), float(pts[0][2]), float(pts[0][3])
    if z >= pts[-1][0]:
        return float(pts[-1][1]), float(pts[-1][2]), float(pts[-1][3])
    for i in range(len(pts) - 1):
        z0, l0, r0, h0 = pts[i]
        z1, l1, r1, h1 = pts[i + 1]
        if z0 <= z <= z1:
            f = (z - z0) / (z1 - z0)
            return (l0 + (l1 - l0) * f,
                    r0 + (r1 - r0) * f,
                    h0 + (h1 - h0) * f)
    return float(pts[-1][1]), float(pts[-1][2]), float(pts[-1][3])


def _proj(wx: float, wz: float, wh: float,
          cam_x: float, cam_z: float, cam_h: float,
          focal: float, horizon_y: int, vcx: int) -> tuple | None:
    """Project world (wx, wz, wh) → viewport (sx, sy, scale).

    Returns None if the point is behind the camera.
    """
    dz = wz - cam_z
    if dz <= 0.5:
        return None
    sc = focal / dz
    sx = int(vcx + (wx - cam_x) * sc)
    sy = int(horizon_y + (cam_h - wh) * sc)
    return sx, sy, sc


# ── Data classes ──────────────────────────────────────────────────────────────


class _Ball3D:
    """One player's rolling ball in 3D world space."""

    def __init__(self, idx: int, start_x: float = 0.0) -> None:
        self.idx  = idx
        self.x    = start_x    # lateral world position
        self.z    = 0.0        # forward progress (world Z)
        self.h    = 0.0        # height above the track floor
        self.vx   = 0.0        # lateral velocity
        self.vz   = _AUTO_SPEED
        self.vh   = 0.0        # vertical velocity (for ramps / jumps)

        self.roll_angle   = 0.0   # visual roll (radians, grows with forward speed)
        self.lean         = 0     # -1 / 0 / +1 for visual steering lean

        self.finished     = False
        self.finish_time: float | None = None
        self.checkpoint   = -1    # index of last reached checkpoint
        self.invuln       = 0     # invulnerability frames
        self.time_penalty = 0.0   # accumulated penalty seconds

        self._falling     = False
        self._fall_timer  = 0
        self._respawn_cd  = 0
        self._spawn_x     = start_x

    @property
    def progress(self) -> float:
        """0–1 normalised progress along the course."""
        return min(1.0, self.z / _FINISH_Z)

    def respawn(self, track_h: float) -> None:
        if self.checkpoint >= 0:
            self.z = float(_CHECKPOINTS[self.checkpoint])
        else:
            self.z = 0.0
        self.x           = 0.0
        self.h           = track_h
        self.vx          = 0.0
        self.vz          = _AUTO_SPEED
        self.vh          = 0.0
        self._falling    = False
        self._fall_timer = 0
        self._respawn_cd = 0
        self.invuln      = _INVULN_FRAMES
        self.time_penalty += _RESPAWN_FRAMES / 60.0


class _Bumper3D:
    """Static circular bumper in the XZ plane."""

    def __init__(self, z: int, x: int, r: int) -> None:
        self.z     = float(z)
        self.x     = float(x)
        self.r     = float(r)
        self.flash = 0

    def update(self) -> None:
        if self.flash > 0:
            self.flash -= 1

    def collide(self, ball: _Ball3D) -> bool:
        dx   = ball.x - self.x
        dz   = ball.z - self.z
        dist = math.hypot(dx, dz)
        min_d = _BALL_COLL_R + self.r
        if dist < min_d and dist > 1e-9:
            nx, nz   = dx / dist, dz / dist
            ball.x   = self.x + nx * min_d
            ball.z   = self.z + nz * min_d
            dot      = ball.vx * nx + ball.vz * nz
            spd      = math.hypot(ball.vx, ball.vz)
            ball.vx  -= 2.0 * dot * nx
            ball.vz  -= 2.0 * dot * nz
            # Minimum bounce speed so ball doesn't get stuck
            if spd < 3.5:
                ball.vx += nx * 60.0
                ball.vz += nz * 60.0
            ball.vx  *= _BUMP_DAMP
            ball.vz   = max(_AUTO_SPEED * 0.4, ball.vz * _BUMP_DAMP)
            self.flash = 10
            return True
        return False


class _Barrier3D:
    """A thin rectangular barrier in the XZ plane."""

    def __init__(self, z: int, x: int, half_w: int, depth_z: int) -> None:
        self.z      = float(z)
        self.x      = float(x)
        self.half_w = float(half_w)
        self.depth  = float(depth_z)
        self.flash  = 0

    def update(self) -> None:
        if self.flash > 0:
            self.flash -= 1

    def collide(self, ball: _Ball3D) -> bool:
        # AABB check in XZ plane
        left_edge  = self.x - self.half_w - _BALL_COLL_R
        right_edge = self.x + self.half_w + _BALL_COLL_R
        z_front    = self.z - self.depth  - _BALL_COLL_R
        z_back     = self.z + self.depth  + _BALL_COLL_R
        if not (left_edge <= ball.x <= right_edge and
                z_front   <= ball.z <= z_back):
            return False
        # Resolve laterally only – this is a forward-scrolling race so barriers
        # act as objects to dodge around, not walls that stop forward progress.
        if ball.x < self.x:
            ball.x  = left_edge
            ball.vx = -abs(ball.vx) * _WALL_DAMP - 20.0
        else:
            ball.x  = right_edge
            ball.vx =  abs(ball.vx) * _WALL_DAMP + 20.0
        # Small speed penalty for grazing
        ball.vz = max(_AUTO_SPEED * 0.7, ball.vz * 0.88)
        self.flash = 8
        return True


class _MovingWall3D:
    """A column/slab that oscillates laterally at a fixed Z."""

    def __init__(self, z: int, base_x: int, half_w: int, height_wld: int,
                 amp: int, speed: float, phase: float) -> None:
        self.z        = float(z)
        self.base_x   = float(base_x)
        self.half_w   = float(half_w)
        self.height   = float(height_wld)
        self.amp      = float(amp)
        self.speed    = speed
        self.t        = phase
        self.cx       = float(base_x)

    def update(self) -> None:
        self.t  += self.speed
        self.cx  = self.base_x + math.sin(self.t) * self.amp

    def collide(self, ball: _Ball3D) -> bool:
        depth = self.half_w + _BALL_COLL_R
        z_tol = 18.0 + _BALL_COLL_R
        if abs(ball.z - self.z) > z_tol:
            return False
        if abs(ball.x - self.cx) < depth:
            if ball.x < self.cx:
                ball.x   = self.cx - depth
                ball.vx  = -abs(ball.vx) * _WALL_DAMP
            else:
                ball.x   = self.cx + depth
                ball.vx  =  abs(ball.vx) * _WALL_DAMP
            return True
        return False


class _SpinBar3D:
    """A bar that rotates in the XZ plane around a pivot point."""

    _BAR_HALF_W = 8.0   # collision half-width of the bar

    def __init__(self, z: int, pivot_x: int, length: int,
                 ang_speed: float, phase: float) -> None:
        self.z         = float(z)
        self.px        = float(pivot_x)
        self.length    = float(length)
        self.ang_speed = ang_speed
        self.angle     = phase
        self.flash     = 0

    def update(self) -> None:
        self.angle += self.ang_speed
        if self.flash > 0:
            self.flash -= 1

    def tip(self) -> tuple[float, float]:
        return (self.px + math.cos(self.angle) * self.length,
                self.z  + math.sin(self.angle) * self.length)

    def collide(self, ball: _Ball3D) -> bool:
        tx, tz = self.tip()
        # Closest point on segment pivot→tip to ball (XZ plane)
        dx, dz = tx - self.px, tz - self.z
        len_sq = dx * dx + dz * dz
        if len_sq < 1e-9:
            cx, cz = self.px, self.z
        else:
            t = max(0.0, min(1.0, ((ball.x - self.px) * dx +
                                    (ball.z - self.z)  * dz) / len_sq))
            cx = self.px + t * dx
            cz = self.z  + t * dz
        dx2  = ball.x - cx
        dz2  = ball.z - cz
        dist = math.hypot(dx2, dz2)
        min_d = _BALL_COLL_R + self._BAR_HALF_W
        if dist < min_d:
            if dist < 1e-9:
                nx, nz = 1.0, 0.0
            else:
                nx, nz = dx2 / dist, dz2 / dist
            overlap  = min_d - dist
            ball.x  += nx * overlap
            ball.z  += nz * overlap
            dot      = ball.vx * nx + ball.vz * nz
            ball.vx  = (ball.vx - 2.0 * dot * nx) * _WALL_DAMP
            ball.vz  = max(_AUTO_SPEED * 0.4,
                           (ball.vz - 2.0 * dot * nz) * _WALL_DAMP)
            self.flash = 8
            return True
        return False


class _BouncePad3D:
    """A pad that fires the ball forward and upward."""

    def __init__(self, z: int, x: int, r: int,
                 boost_vz: float, boost_vh: float) -> None:
        self.z        = float(z)
        self.x        = float(x)
        self.r        = float(r)
        self.boost_vz = boost_vz
        self.boost_vh = boost_vh
        self.flash    = 0

    def update(self) -> None:
        if self.flash > 0:
            self.flash -= 1

    def check(self, ball: _Ball3D) -> bool:
        if math.hypot(ball.x - self.x, ball.z - self.z) < self.r + _BALL_COLL_R:
            ball.vz   = max(ball.vz, self.boost_vz)
            ball.vh   = max(ball.vh, self.boost_vh)
            self.flash = 16
            return True
        return False


# ── Viewport helpers ──────────────────────────────────────────────────────────


def _viewports(n: int, w: int, h: int) -> list[pygame.Rect]:
    """Return screen Rects for n players."""
    if n == 1:
        return [pygame.Rect(0, 0, w, h)]
    elif n == 2:
        hw = w // 2
        return [pygame.Rect(0, 0, hw, h), pygame.Rect(hw, 0, hw, h)]
    else:
        hw, hh = w // 2, h // 2
        return [
            pygame.Rect(0,  0,  hw, hh),
            pygame.Rect(hw, 0,  hw, hh),
            pygame.Rect(0,  hh, hw, hh),
            pygame.Rect(hw, hh, hw, hh),
        ]


# ── Main level class ──────────────────────────────────────────────────────────


class RollingBallLevel(BaseLevel):
    """Self-contained 3D rolling ball assault course.

    Call ``run()`` to play.  Returns ``"complete"`` or ``"exit"``.
    """

    def __init__(self, screen: pygame.Surface,
                 width: int, height: int, fps: int,
                 settings, font,
                 acid, sfx,
                 joystick=None, joystick2=None) -> None:
        super().__init__(screen, width, height, fps, settings, font, acid, sfx,
                         joystick=joystick, joystick2=joystick2)

        self._joys: list = []
        if joystick is not None:
            self._joys.append(joystick)
        if joystick2 is not None:
            self._joys.append(joystick2)

        self._clock   = pygame.time.Clock()
        self._hud_font = pygame.font.SysFont(None, 24, bold=True)
        self._big_font = pygame.font.SysFont(None, 72, bold=True)
        self._med_font = pygame.font.SysFont(None, 44, bold=True)
        self._sml_font = pygame.font.SysFont(None, 32, bold=True)

        # State – populated by _reset()
        self._balls:    list[_Ball3D]       = []
        self._bumpers:  list[_Bumper3D]     = []
        self._barriers: list[_Barrier3D]    = []
        self._mwalls:   list[_MovingWall3D] = []
        self._spinbars: list[_SpinBar3D]    = []
        self._bpads:    list[_BouncePad3D]  = []

        self._timer          = 0.0
        self._frame          = 0
        self._finished_order: list[int] = []
        self._race_over      = False

        # Per-player surfaces (pre-created, reused every frame)
        self._vp_surfaces: list[pygame.Surface] = []

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> str:
        """Play the level.  Returns ``"complete"`` or ``"exit"``."""
        self._reset()
        self._show_title()
        self._do_countdown()
        while True:
            dt = min(self._clock.tick(self.fps) / 1000.0, 0.05)

            result = self._handle_events()
            if result:
                return result

            if not self._race_over:
                self._timer += dt

            self._update(dt)
            self._draw()
            pygame.display.flip()
            self._frame += 1

            if not self._race_over:
                if self._timer >= _RACE_SECS:
                    self._race_over = True
                    self._show_results("TIME'S UP!")
                    return "complete"
                if all(b.finished for b in self._balls):
                    self._race_over = True
                    self._show_results("RACE COMPLETE!")
                    return "complete"

    # ── Initialisation ────────────────────────────────────────────────────────

    def _reset(self) -> None:
        self._frame          = 0
        self._timer          = 0.0
        self._race_over      = False
        self._finished_order = []

        num_players = min(4, 2 + len(self._joys))

        # Stagger start X positions so balls don't overlap
        start_xs = [-28.0, 28.0, -56.0, 56.0]
        self._balls = [
            _Ball3D(i, start_xs[i])
            for i in range(num_players)
        ]

        self._bumpers  = [_Bumper3D(*d)  for d in _BUMPER_DEFS]
        self._barriers = [_Barrier3D(*d) for d in _BARRIER_DEFS]
        self._mwalls   = [_MovingWall3D(*d) for d in _MWALL_DEFS]
        self._spinbars = [_SpinBar3D(*d)  for d in _SPINBAR_DEFS]
        self._bpads    = [_BouncePad3D(*d) for d in _BOUNCEPAD_DEFS]

        # Pre-create per-player viewport surfaces
        vp_rects = _viewports(num_players, self.width, self.height)
        self._vp_surfaces = [
            pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            for r in vp_rects
        ]
        self._vp_rects = vp_rects

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_events(self) -> str | None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "exit"
        return None

    def _read_inputs(self) -> list[tuple[float, float]]:
        """Return list of (ax, az) in [-1..1] for each active ball.

        ax: lateral steer   az: forward/brake  (+1 = forward, -1 = brake)
        """
        keys = pygame.key.get_pressed()
        inputs: list[tuple[float, float]] = []

        # P1 – arrow keys
        ax1 = ((1.0 if keys[self.settings.keyboard.get("move_right", pygame.K_RIGHT)] else 0.0) -
               (1.0 if keys[self.settings.keyboard.get("move_left",  pygame.K_LEFT)]  else 0.0))
        az1 = ((1.0 if keys[self.settings.keyboard.get("move_up",    pygame.K_UP)]    else 0.0) -
               (1.0 if keys[self.settings.keyboard.get("move_down",  pygame.K_DOWN)]  else 0.0))
        inputs.append((ax1, az1))

        # P2 – WASD
        if len(self._balls) >= 2:
            ax2 = ((1.0 if keys[self.settings.keyboard_p2.get("move_right", pygame.K_d)] else 0.0) -
                   (1.0 if keys[self.settings.keyboard_p2.get("move_left",  pygame.K_a)] else 0.0))
            az2 = ((1.0 if keys[self.settings.keyboard_p2.get("move_up",    pygame.K_w)] else 0.0) -
                   (1.0 if keys[self.settings.keyboard_p2.get("move_down",  pygame.K_s)] else 0.0))
            inputs.append((ax2, az2))

        # P3 / P4 – joysticks
        for joy in self._joys:
            if len(inputs) >= len(self._balls):
                break
            ax, az = 0.0, 0.0
            if joy.get_numaxes() >= 1:
                raw = joy.get_axis(0)
                if abs(raw) > AXIS_DEADZONE:
                    ax = raw
            if joy.get_numaxes() >= 2:
                raw = joy.get_axis(1)
                if abs(raw) > AXIS_DEADZONE:
                    az = -raw   # push stick forward = accelerate
            if joy.get_numhats() > 0:
                hx, hy = joy.get_hat(0)
                if hx != 0:
                    ax = float(hx)
                if hy != 0:
                    az = float(hy)
            inputs.append((ax, az))

        return inputs

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self, dt: float) -> None:
        inputs = self._read_inputs()

        # ── Animate obstacles ─────────────────────────────────────────────────
        for b in self._bumpers:
            b.update()
        for bk in self._barriers:
            bk.update()
        for mw in self._mwalls:
            mw.update()
        for sb in self._spinbars:
            sb.update()
        for bp in self._bpads:
            bp.update()

        # ── Update each ball ──────────────────────────────────────────────────
        for ball, (ax, az) in zip(self._balls, inputs):
            if ball.finished:
                continue

            # Respawn countdown
            if ball._respawn_cd > 0:
                ball._respawn_cd -= 1
                if ball._respawn_cd == 0:
                    _, _, th = _track_at_z(ball.z)
                    ball.respawn(th)
                continue

            # Fall animation (shrink-fall effect)
            if ball._falling:
                ball._fall_timer += 1
                if ball._fall_timer >= _FALL_FRAMES:
                    ball._respawn_cd = _RESPAWN_FRAMES
                continue

            if ball.invuln > 0:
                ball.invuln -= 1

            # ── Forward velocity ──────────────────────────────────────────────
            if az > 0:
                ball.vz += az * _FWD_ACCEL * dt
            elif az < 0:
                ball.vz += az * _FWD_DECEL * dt

            # Friction: damp only excess speed above AUTO_SPEED to keep base
            # rolling feel; below AUTO_SPEED gradually recover (unless braking)
            if az < 0:
                ball.vz  = max(0.0, ball.vz)
            else:
                if ball.vz > _AUTO_SPEED:
                    excess   = ball.vz - _AUTO_SPEED
                    excess  *= (1.0 - (1.0 - 0.985) * dt * 60.0)
                    ball.vz  = _AUTO_SPEED + excess
                else:
                    ball.vz += (_AUTO_SPEED - ball.vz) * min(1.0, dt * 3.0)
            ball.vz  = min(_MAX_FWD, ball.vz)

            # ── Lateral velocity ──────────────────────────────────────────────
            ball.vx += ax * _LAT_ACCEL * dt
            ball.vx *= _LAT_FRIC_FPS   # per-frame damping
            ball.lean = (1 if ax > 0.1 else (-1 if ax < -0.1 else 0))

            # ── Move ──────────────────────────────────────────────────────────
            ball.z += ball.vz * dt
            ball.x += ball.vx * dt

            # ── Rolling visual angle ──────────────────────────────────────────
            ball.roll_angle += ball.vz * dt * 0.04

            # ── Track height and gravity ──────────────────────────────────────
            _, _, floor_h = _track_at_z(ball.z)
            ball.vh -= _GRAVITY * dt
            ball.h  += ball.vh * dt

            if ball.h <= floor_h:
                ball.h  = floor_h
                ball.vh = 0.0  # land (no bounce for simplicity)

            # ── Lateral wall collision ────────────────────────────────────────
            left_x, right_x, _ = _track_at_z(ball.z)
            if ball.x - _BALL_COLL_R < left_x:
                ball.x   = left_x + _BALL_COLL_R
                ball.vx  = abs(ball.vx) * _WALL_DAMP
            if ball.x + _BALL_COLL_R > right_x:
                ball.x   = right_x - _BALL_COLL_R
                ball.vx  = -abs(ball.vx) * _WALL_DAMP

            # ── Obstacle collisions ───────────────────────────────────────────
            for bmp in self._bumpers:
                bmp.collide(ball)
            for bk in self._barriers:
                bk.collide(ball)
            for mw in self._mwalls:
                mw.collide(ball)
            for sb in self._spinbars:
                sb.collide(ball)
            for bp in self._bpads:
                bp.check(ball)

            # ── Pit / gap check ───────────────────────────────────────────────
            if ball.invuln == 0 and not ball._falling:
                for gz0, gz1, gx0, gx1 in _GAP_DEFS:
                    if gz0 <= ball.z <= gz1 and gx0 <= ball.x <= gx1:
                        ball._falling    = True
                        ball._fall_timer = 0
                        ball.vx = 0.0
                        ball.vz = 0.0
                        break

            # ── Checkpoints ───────────────────────────────────────────────────
            for ci, cz in enumerate(_CHECKPOINTS):
                if ci > ball.checkpoint and ball.z >= cz:
                    ball.checkpoint = ci

            # ── Finish line ───────────────────────────────────────────────────
            if not ball.finished and ball.z >= _FINISH_Z:
                ball.finished    = True
                ball.finish_time = self._timer
                self._finished_order.append(ball.idx)

        # ── Ball–ball collisions ───────────────────────────────────────────────
        active = [b for b in self._balls
                  if not b.finished and not b._falling and b._respawn_cd == 0]
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                a, b   = active[i], active[j]
                dx     = b.x - a.x
                dz     = b.z - a.z
                dist   = math.hypot(dx, dz)
                min_d  = _BALL_COLL_R * 2
                if dist < min_d and dist > 1e-9:
                    nx, nz   = dx / dist, dz / dist
                    overlap  = (min_d - dist) / 2.0
                    a.x -= nx * overlap;  a.z -= nz * overlap
                    b.x += nx * overlap;  b.z += nz * overlap
                    dax = a.vx * nx + a.vz * nz
                    dbx = b.vx * nx + b.vz * nz
                    a.vx += (dbx - dax) * nx * _BALL_BOUNCE
                    a.vz += (dbx - dax) * nz * _BALL_BOUNCE
                    b.vx += (dax - dbx) * nx * _BALL_BOUNCE
                    b.vz += (dax - dbx) * nz * _BALL_BOUNCE

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.screen.fill(_VOID_COL)

        # Rank sort (for HUD labels)
        ranked = sorted(self._balls,
                        key=lambda b: -(b.finish_time if b.finished
                                        else b.progress - 0.0001))

        for pi, (ball, vp_rect, surf) in enumerate(
                zip(self._balls, self._vp_rects, self._vp_surfaces)):
            rank = next(r for r, rb in enumerate(ranked) if rb.idx == ball.idx)
            self._render_viewport(surf, ball, self._balls,
                                  rank, len(self._balls))
            self.screen.blit(surf, vp_rect)

        # Split-screen dividers
        n = len(self._balls)
        if n >= 2:
            hw = self.width // 2
            pygame.draw.line(self.screen, _SPLIT_LINE,
                             (hw, 0), (hw, self.height), 2)
        if n >= 3:
            hh = self.height // 2
            pygame.draw.line(self.screen, _SPLIT_LINE,
                             (0, hh), (self.width, hh), 2)

    # ── Per-viewport rendering ────────────────────────────────────────────────

    def _render_viewport(self, surf: pygame.Surface, hero: _Ball3D,
                         all_balls: list[_Ball3D],
                         rank: int, num_players: int) -> None:
        vw, vh = surf.get_width(), surf.get_height()
        vcx      = vw // 2
        horizon_y = int(vh * _HORIZON)
        focal     = _FOCAL_BASE * vh / 600.0

        # Camera follows the hero ball
        cam_x = hero.x
        cam_z = hero.z - _CAM_DIST
        cam_h = _CAM_H + hero.h   # camera rises with track

        def proj(wx, wz, wh=0.0):
            return _proj(wx, wz, wh, cam_x, cam_z, cam_h, focal, horizon_y, vcx)

        # ── Sky ───────────────────────────────────────────────────────────────
        for y in range(0, horizon_y, 2):
            t = y / max(1, horizon_y)
            r = int(_SKY_TOP[0] + (_SKY_BOT[0] - _SKY_TOP[0]) * t)
            g = int(_SKY_TOP[1] + (_SKY_BOT[1] - _SKY_TOP[1]) * t)
            b = int(_SKY_TOP[2] + (_SKY_BOT[2] - _SKY_TOP[2]) * t)
            pygame.draw.rect(surf, (r, g, b), (0, y, vw, 2))

        # ── Fill screen bottom (void below near edge) ─────────────────────────
        surf.fill(_VOID_COL, pygame.Rect(0, horizon_y, vw, vh - horizon_y))

        # ── Track floor ───────────────────────────────────────────────────────
        self._draw_track_3d(surf, proj, cam_z, focal, horizon_y, vcx, vw, vh)

        # ── Collect visible obstacles sorted far→near for painter's alg ───────
        self._draw_obstacles_3d(surf, proj, hero, cam_z)

        # ── Other players' balls ──────────────────────────────────────────────
        for ball in all_balls:
            if ball.idx == hero.idx:
                continue
            if ball._respawn_cd > 0 and (self._frame // 4) % 2 == 0:
                continue
            p = proj(ball.x, ball.z, ball.h)
            if p is None:
                continue
            sx, sy, sc = p
            r = max(3, int(_BALL_COLL_R * sc))
            if not (-r <= sx <= vw + r and -r <= sy <= vh + r):
                continue
            rim_col, fill_col, hi_col, _ = _PLAYER_COLS[ball.idx]
            self._draw_ball_sphere(surf, sx, sy, r, rim_col, fill_col,
                                   hi_col, ball.roll_angle,
                                   ball._falling, ball._fall_timer)
            # Player label
            lbl = self._hud_font.render(f"P{ball.idx + 1}", True,
                                        _PLAYER_COLS[ball.idx][3])
            surf.blit(lbl, (sx - lbl.get_width() // 2, sy - r - 14))

        # ── Hero ball (projected from near-cam position) ──────────────────────
        if not hero.finished:
            if hero._respawn_cd > 0 and (self._frame // 4) % 2 == 1:
                pass  # blinking during respawn
            elif hero.invuln > 0 and (self._frame // 4) % 2 == 0:
                pass  # blinking during invulnerability
            else:
                p = proj(hero.x, hero.z, hero.h)
                if p is not None:
                    sx, sy, sc = p
                    draw_r = max(5, int(_BALL_COLL_R * sc * 1.1))
                    # Fall shrink animation
                    if hero._falling:
                        shrink = hero._fall_timer / _FALL_FRAMES
                        draw_r = max(3, int(draw_r * (1.0 - shrink * 0.85)))
                    rim_col, fill_col, hi_col, _ = _PLAYER_COLS[hero.idx]
                    self._draw_ball_sphere(surf, sx, sy, draw_r, rim_col,
                                           fill_col, hi_col,
                                           hero.roll_angle,
                                           hero._falling, hero._fall_timer)
                    # Speed lines when fast
                    if hero.vz > _MAX_FWD * 0.7 and not hero._falling:
                        self._draw_speed_lines(surf, sx, sy, draw_r, rim_col,
                                               hero.vz / _MAX_FWD)

        # ── HUD ───────────────────────────────────────────────────────────────
        self._draw_hud_vp(surf, hero, rank, num_players, vw, vh)

    def _draw_track_3d(self, surf, proj, cam_z, focal, horizon_y, vcx,
                       vw, vh) -> None:
        """Draw the track corridor as Z-slices (far→near, painter's algorithm)."""
        NUM_SLICES = 28
        z_start = cam_z + _Z_NEAR
        z_end   = cam_z + _Z_FAR
        # Power distribution puts more slices near the camera
        zs = [z_start + (z_end - z_start) * (i / NUM_SLICES) ** 0.65
              for i in range(NUM_SLICES + 1)]

        for i in range(NUM_SLICES - 1, -1, -1):
            z0 = zs[i]
            z1 = zs[i + 1]

            l0, r0, h0 = _track_at_z(z0)
            l1, r1, h1 = _track_at_z(z1)

            # Only draw sections that are on the course
            on_course_0 = 0.0 <= z0 <= _FINISH_Z + 50
            on_course_1 = 0.0 <= z1 <= _FINISH_Z + 50

            p_ll = proj(l0, z0, h0)
            p_lr = proj(r0, z0, h0)
            p_fl = proj(l1, z1, h1)
            p_fr = proj(r1, z1, h1)

            if p_ll is None or p_lr is None or p_fl is None or p_fr is None:
                continue

            sx_ll, sy_ll, _ = p_ll
            sx_lr, sy_lr, _ = p_lr
            sx_fl, sy_fl, _ = p_fl
            sx_fr, sy_fr, _ = p_fr

            # Skip if entire slice is above horizon
            if sy_ll < horizon_y and sy_lr < horizon_y and \
               sy_fl < horizon_y and sy_fr < horizon_y:
                continue

            if on_course_0 or on_course_1:
                # Alternating floor bands for speed sensation
                col = _FLOOR_COL if (i % 2 == 0) else _FLOOR_ALT
                floor_poly = [(sx_fl, sy_fl), (sx_fr, sy_fr),
                              (sx_lr, sy_lr), (sx_ll, sy_ll)]
                pygame.draw.polygon(surf, col, floor_poly)

        # ── Edge/wall lines drawn as thick boundary lines ─────────────────────
        NUM_EDGE = 32
        ze = [cam_z + _Z_NEAR + (_Z_FAR - _Z_NEAR) * (i / (NUM_EDGE - 1)) ** 0.6
              for i in range(NUM_EDGE)]

        left_pts:  list[tuple] = []
        right_pts: list[tuple] = []
        for z in ze:
            if not (0.0 <= z <= _FINISH_Z + 50):
                continue
            l, r, h = _track_at_z(z)
            p_l = proj(l, z, h)
            p_r = proj(r, z, h)
            if p_l:
                left_pts.append((p_l[0], p_l[1]))
            if p_r:
                right_pts.append((p_r[0], p_r[1]))

        if len(left_pts)  >= 2:
            pygame.draw.lines(surf, _EDGE_COL,  False, left_pts,  3)
            pygame.draw.lines(surf, _EDGE_DARK, False, left_pts,  1)
        if len(right_pts) >= 2:
            pygame.draw.lines(surf, _EDGE_COL,  False, right_pts, 3)
            pygame.draw.lines(surf, _EDGE_DARK, False, right_pts, 1)

        # ── Centre dashes ─────────────────────────────────────────────────────
        DASH_Z_GAP = 220.0
        num_dashes = int(_Z_FAR / DASH_Z_GAP) + 4
        for i in range(num_dashes):
            z = cam_z + _Z_NEAR + (i * DASH_Z_GAP - (cam_z % DASH_Z_GAP))
            if not (0.0 <= z <= _FINISH_Z):
                continue
            _, _, h = _track_at_z(z)
            p = proj(0, z, h)
            if p is None:
                continue
            sx, sy, sc = p
            if sy < horizon_y or sy > vh:
                continue
            dw = max(1, int(3 * sc))
            dh = max(1, int(18 * sc))
            pygame.draw.rect(surf, (80, 70, 120),
                             (sx - dw // 2, sy - dh, dw, dh))

        # ── Checkpoint gates ──────────────────────────────────────────────────
        for ci, cz in enumerate(_CHECKPOINTS):
            self._draw_gate(surf, proj, cz, _CHKPT_COL, f"CP{ci + 1}", 0)

        # ── Finish line arch ──────────────────────────────────────────────────
        self._draw_gate(surf, proj, _FINISH_Z, _FINISH_COL, "FINISH",
                        self._frame, checkerboard=True)

    def _draw_gate(self, surf, proj, z: float, col: tuple, label: str,
                   frame: int, checkerboard: bool = False) -> None:
        """Draw a spanning gate arch at world Z."""
        l, r, h = _track_at_z(z)
        gate_h  = 60.0   # gate height (world units)
        p_bl    = proj(l, z, h)
        p_br    = proj(r, z, h)
        p_tl    = proj(l, z, h + gate_h)
        p_tr    = proj(r, z, h + gate_h)
        if None in (p_bl, p_br, p_tl, p_tr):
            return

        bx_l, by_l, sc_l = p_bl
        bx_r, by_r, sc_r = p_br
        tx_l, ty_l, _    = p_tl
        tx_r, ty_r, _    = p_tr

        bar_w = max(1, int(6 * sc_l))

        if checkerboard:
            # Draw a checkerboard pattern between the two gate posts
            num_tiles = 8
            for ti in range(num_tiles):
                f0 = ti / num_tiles
                f1 = (ti + 1) / num_tiles
                # interpolate between l and r at ground level
                wx0 = l + (r - l) * f0
                wx1 = l + (r - l) * f1
                p0b = proj(wx0, z, h)
                p1b = proj(wx1, z, h)
                p0t = proj(wx0, z, h + gate_h)
                p1t = proj(wx1, z, h + gate_h)
                if None in (p0b, p1b, p0t, p1t):
                    continue
                tile_col = _FINISH_COL if (ti + (frame // 20) % 2) % 2 == 0 \
                           else _FINISH_ALT
                pygame.draw.polygon(surf, tile_col, [
                    (p0b[0], p0b[1]), (p1b[0], p1b[1]),
                    (p1t[0], p1t[1]), (p0t[0], p0t[1]),
                ])
        else:
            # Horizontal bar across top of gate
            alpha = 180 if (frame // 20) % 2 == 0 else 120
            gated_col = tuple(int(c * alpha / 255) for c in col)
            if len(col) == 3:
                gated_col = col
            pygame.draw.polygon(surf, col, [
                (tx_l, ty_l), (tx_r, ty_r), (bx_r, by_r), (bx_l, by_l)
            ])

        # Vertical gate posts
        pygame.draw.line(surf, col, (bx_l, by_l), (tx_l, ty_l), bar_w)
        pygame.draw.line(surf, col, (bx_r, by_r), (tx_r, ty_r), bar_w)

        # Label above gate
        lbl = self._hud_font.render(label, True, col)
        mid_x = (tx_l + tx_r) // 2
        surf.blit(lbl, (mid_x - lbl.get_width() // 2, ty_l - 18))

    def _draw_obstacles_3d(self, surf, proj, hero: _Ball3D,
                           cam_z: float) -> None:
        """Draw all obstacles in the camera's view, far→near."""

        # ── Bumpers ───────────────────────────────────────────────────────────
        for bmp in self._bumpers:
            if not (cam_z - 50 < bmp.z < cam_z + _Z_FAR):
                continue
            _, _, h = _track_at_z(bmp.z)
            p = proj(bmp.x, bmp.z, h)
            if p is None:
                continue
            sx, sy, sc = p
            r = max(3, int(bmp.r * sc))
            col = _BUMPER_COL if bmp.flash else _BUMPER_DRK
            pygame.draw.circle(surf, _BUMPER_DRK, (sx, sy), r)
            pygame.draw.circle(surf, col, (sx, sy), r, max(1, r // 3))
            if r > 6:
                pygame.draw.circle(surf, col, (sx, sy), r // 2, max(1, r // 5))
            # Top gleam
            if r >= 5:
                pygame.draw.circle(surf, (255, 255, 200),
                                   (sx - r // 3, sy - r // 3),
                                   max(1, r // 4))

        # ── Barriers ──────────────────────────────────────────────────────────
        for bk in self._barriers:
            if not (cam_z - 50 < bk.z < cam_z + _Z_FAR):
                continue
            _, _, h = _track_at_z(bk.z)
            bar_h_wld = 55.0   # visual height of barrier in world units
            # Draw as a 3D box (front face + top face)
            for dz_off, is_front in ((0, True), (bk.depth * 2, False)):
                z_face = bk.z - bk.depth + dz_off
                p_bl = proj(bk.x - bk.half_w, z_face, h)
                p_br = proj(bk.x + bk.half_w, z_face, h)
                p_tl = proj(bk.x - bk.half_w, z_face, h + bar_h_wld)
                p_tr = proj(bk.x + bk.half_w, z_face, h + bar_h_wld)
                if None in (p_bl, p_br, p_tl, p_tr):
                    continue
                col = (_BARRIER_COL if bk.flash else _BARRIER_DRK) \
                      if is_front else _BARRIER_DRK
                pygame.draw.polygon(surf, col, [
                    (p_bl[0], p_bl[1]), (p_br[0], p_br[1]),
                    (p_tr[0], p_tr[1]), (p_tl[0], p_tl[1]),
                ])
                if is_front:
                    pygame.draw.polygon(surf, _BARRIER_COL, [
                        (p_bl[0], p_bl[1]), (p_br[0], p_br[1]),
                        (p_tr[0], p_tr[1]), (p_tl[0], p_tl[1]),
                    ], max(1, int(p_bl[2] * 2)))

        # ── Moving walls ──────────────────────────────────────────────────────
        for mw in self._mwalls:
            if not (cam_z - 50 < mw.z < cam_z + _Z_FAR):
                continue
            _, _, h = _track_at_z(mw.z)
            depth = 14.0
            p_bl = proj(mw.cx - mw.half_w, mw.z - depth, h)
            p_br = proj(mw.cx + mw.half_w, mw.z - depth, h)
            p_tl = proj(mw.cx - mw.half_w, mw.z - depth, h + mw.height)
            p_tr = proj(mw.cx + mw.half_w, mw.z - depth, h + mw.height)
            if None in (p_bl, p_br, p_tl, p_tr):
                continue
            pygame.draw.polygon(surf, _MWALL_DRK, [
                (p_bl[0], p_bl[1]), (p_br[0], p_br[1]),
                (p_tr[0], p_tr[1]), (p_tl[0], p_tl[1]),
            ])
            thick = max(1, int(p_bl[2] * 3))
            pygame.draw.polygon(surf, _MWALL_COL, [
                (p_bl[0], p_bl[1]), (p_br[0], p_br[1]),
                (p_tr[0], p_tr[1]), (p_tl[0], p_tl[1]),
            ], thick)
            # Speed stripe
            mid_t = (p_tl[1] + p_bl[1]) // 2
            mid_br = (p_tr[1] + p_br[1]) // 2
            pygame.draw.line(surf, (180, 145, 255),
                             (p_tl[0], mid_t), (p_tr[0], mid_br),
                             max(1, thick // 2))

        # ── Spin bars ─────────────────────────────────────────────────────────
        for sb in self._spinbars:
            if not (cam_z - 100 < sb.z < cam_z + _Z_FAR):
                continue
            _, _, h = _track_at_z(sb.z)
            bar_h_wld = 28.0   # height of the bar centre above track
            tx, tz = sb.tip()
            p_piv = proj(sb.px, sb.z, h + bar_h_wld)
            p_tip = proj(tx,   tz,   h + bar_h_wld)
            if p_piv is None or p_tip is None:
                continue
            col = _SPINBAR_COL if sb.flash else tuple(c // 2 for c in _SPINBAR_COL)
            thick = max(2, int(p_piv[2] * 12))
            pygame.draw.line(surf, col,
                             (p_piv[0], p_piv[1]),
                             (p_tip[0], p_tip[1]), thick)
            pygame.draw.line(surf, (255, 255, 255),
                             (p_piv[0], p_piv[1]),
                             (p_tip[0], p_tip[1]),
                             max(1, thick // 4))
            # Pivot hub
            piv_r = max(3, int(p_piv[2] * 10))
            pygame.draw.circle(surf, _SPINBAR_PIV,
                               (p_piv[0], p_piv[1]), piv_r)
            pygame.draw.circle(surf, (220, 100, 100),
                               (p_piv[0], p_piv[1]),
                               max(2, piv_r - 2))

        # ── Bounce pads ───────────────────────────────────────────────────────
        for bp in self._bpads:
            if not (cam_z - 50 < bp.z < cam_z + _Z_FAR):
                continue
            _, _, h = _track_at_z(bp.z)
            p = proj(bp.x, bp.z, h)
            if p is None:
                continue
            sx, sy, sc = p
            r  = max(3, int(bp.r * sc))
            col = _BPAD_COL if bp.flash else _BPAD_RING
            pygame.draw.circle(surf, _BPAD_RING, (sx, sy), r)
            pygame.draw.circle(surf, col, (sx, sy), r, max(1, r // 3))
            # Arrow pointing forward/up
            if r >= 4:
                tip_x, tip_y = sx, sy - r + 2
                bas_x, bas_y = sx, sy + r // 2
                pygame.draw.line(surf, col, (bas_x, bas_y), (tip_x, tip_y), max(1, r // 4))
                # Arrowhead
                ah = max(2, r // 4)
                pygame.draw.polygon(surf, col, [
                    (tip_x,      tip_y),
                    (tip_x - ah, tip_y + ah * 2),
                    (tip_x + ah, tip_y + ah * 2),
                ])

        # ── Gap markers on track floor ────────────────────────────────────────
        for gz0, gz1, gx0, gx1 in _GAP_DEFS:
            for z_sample in (gz0, (gz0 + gz1) / 2, gz1):
                if not (cam_z - 20 < z_sample < cam_z + _Z_FAR):
                    continue
                _, _, h = _track_at_z(z_sample)
                p_l = proj(gx0, z_sample, h - 2)
                p_r = proj(gx1, z_sample, h - 2)
                if p_l is None or p_r is None:
                    continue
                pygame.draw.line(surf, _GAP_RIM,
                                 (p_l[0], p_l[1]), (p_r[0], p_r[1]),
                                 max(1, int(p_l[2] * 3)))

    # ── Ball rendering ────────────────────────────────────────────────────────

    @staticmethod
    def _draw_ball_sphere(surf: pygame.Surface,
                          sx: int, sy: int, r: int,
                          rim_col: tuple, fill_col: tuple, hi_col: tuple,
                          roll_angle: float,
                          falling: bool = False,
                          fall_timer: int = 0) -> None:
        """Draw a glass-like sphere with a karate fighter silhouette inside."""
        if r < 2:
            return

        # Shadow
        pygame.draw.circle(surf, (0, 0, 0),
                           (sx + max(1, r // 4), sy + max(1, r // 4)), r)

        # Dark outer ring (gives depth to sphere edge)
        dark_fill = tuple(max(0, c - 60) for c in fill_col)
        pygame.draw.circle(surf, dark_fill, (sx, sy), r)

        # Main fill (slightly smaller inner sphere)
        inner_r = max(2, int(r * 0.80))
        pygame.draw.circle(surf, fill_col, (sx, sy), inner_r)

        # Specular / glass highlight (upper-left)
        hi_r = max(2, r // 3)
        pygame.draw.circle(surf, hi_col,
                           (sx - r // 3, sy - r // 3), hi_r)
        # Small bright centre of highlight
        if r >= 8:
            pygame.draw.circle(surf, (255, 255, 255),
                               (sx - r // 3, sy - r // 3),
                               max(1, hi_r // 2))

        # Rim
        rim_thick = max(1, r // 7)
        pygame.draw.circle(surf, rim_col, (sx, sy), r, rim_thick)

        # Rolling indicator lines
        if r >= 6 and not falling:
            cos_a = math.cos(roll_angle)
            sin_a = math.sin(roll_angle)
            r2    = r - 2
            pygame.draw.line(surf, rim_col,
                             (sx + int(cos_a * r2), sy + int(sin_a * r2)),
                             (sx - int(cos_a * r2), sy - int(sin_a * r2)),
                             max(1, r // 9))
            pygame.draw.line(surf, rim_col,
                             (sx + int(-sin_a * r2), sy + int(cos_a * r2)),
                             (sx - int(-sin_a * r2), sy - int(cos_a * r2)),
                             max(1, r // 9))

        # Inner karate fighter silhouette
        if r >= 10 and not falling:
            head_r = max(2, r // 4)
            head_y = sy - r // 3
            # Head
            pygame.draw.circle(surf, hi_col, (sx, head_y), head_r)
            # Body
            body_bot = sy + r // 4
            pygame.draw.line(surf, hi_col,
                             (sx, head_y + head_r), (sx, body_bot),
                             max(1, r // 9))
            # Arms (spread wide)
            arm_y = head_y + head_r + r // 5
            arm_w = r // 2
            pygame.draw.line(surf, hi_col,
                             (sx - arm_w, arm_y), (sx + arm_w, arm_y),
                             max(1, r // 9))
            # Legs
            leg_y = body_bot
            pygame.draw.line(surf, hi_col,
                             (sx, leg_y), (sx - r // 4, sy + r // 2),
                             max(1, r // 9))
            pygame.draw.line(surf, hi_col,
                             (sx, leg_y), (sx + r // 4, sy + r // 2),
                             max(1, r // 9))

    @staticmethod
    def _draw_speed_lines(surf: pygame.Surface,
                          sx: int, sy: int, r: int,
                          col: tuple, speed_frac: float) -> None:
        """Radial speed lines emanating from behind the ball."""
        n_lines = 6
        length  = int(r * 1.2 * speed_frac)
        for i in range(n_lines):
            angle = math.pi + (i / n_lines) * math.pi * 0.6 - math.pi * 0.3
            ex = sx + int(math.cos(angle) * (r + length))
            ey = sy + int(math.sin(angle) * (r + length))
            sx2 = sx + int(math.cos(angle) * r)
            sy2 = sy + int(math.sin(angle) * r)
            alpha_col = tuple(int(c * 0.55) for c in col)
            pygame.draw.line(surf, alpha_col, (sx2, sy2), (ex, ey),
                             max(1, r // 8))

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hud_vp(self, surf: pygame.Surface, ball: _Ball3D,
                     rank: int, num_players: int,
                     vw: int, vh: int) -> None:
        """Draw HUD elements inside one player's viewport."""

        # ── Timer (top centre) ────────────────────────────────────────────────
        remaining = max(0.0, _RACE_SECS - self._timer)
        mins = int(remaining) // 60
        secs = int(remaining) % 60
        t_str  = f"{mins}:{secs:02d}"
        t_col  = _TIMER_LOW if remaining < 30 else _TIMER_OK
        t_surf = self._hud_font.render(t_str, True, t_col)
        tx     = vw // 2 - t_surf.get_width() // 2
        _draw_hud_badge(surf, tx - 4, 4,
                        t_surf.get_width() + 8, t_surf.get_height() + 4)
        surf.blit(t_surf, (tx, 6))

        # ── Position label (top left) ─────────────────────────────────────────
        pos_str = f"{_PLACE_LABELS[rank]}"
        pos_surf = self._hud_font.render(pos_str, True,
                                         _PLAYER_COLS[ball.idx][3])
        _draw_hud_badge(surf, 4, 4,
                        pos_surf.get_width() + 8, pos_surf.get_height() + 4)
        surf.blit(pos_surf, (8, 6))

        # ── Speed indicator (top right) ───────────────────────────────────────
        spd_str  = f"{int(ball.vz)} u/s"
        spd_surf = self._hud_font.render(spd_str, True, (180, 180, 210))
        sx_pos   = vw - spd_surf.get_width() - 8
        _draw_hud_badge(surf, sx_pos - 4, 4,
                        spd_surf.get_width() + 8, spd_surf.get_height() + 4)
        surf.blit(spd_surf, (sx_pos, 6))

        # ── Progress bar (bottom) ─────────────────────────────────────────────
        bar_h  = 10
        bar_y  = vh - bar_h - 6
        bar_x  = 6
        bar_w  = vw - 12
        pygame.draw.rect(surf, (38, 34, 58), (bar_x, bar_y, bar_w, bar_h))
        fill_w = int(bar_w * ball.progress)
        if fill_w > 0:
            pygame.draw.rect(surf, _PLAYER_COLS[ball.idx][0],
                             (bar_x, bar_y, fill_w, bar_h))
        # Checkpoint markers on bar
        for cz in _CHECKPOINTS:
            mx = int(bar_x + bar_w * cz / _FINISH_Z)
            pygame.draw.line(surf, _CHKPT_COL,
                             (mx, bar_y), (mx, bar_y + bar_h), 1)
        pygame.draw.rect(surf, _PLAYER_COLS[ball.idx][3],
                         (bar_x, bar_y, bar_w, bar_h), 2)

        # ── Player label + checkpoint status (bottom left) ────────────────────
        cp_str  = f"P{ball.idx + 1}  CP {ball.checkpoint + 1}/{len(_CHECKPOINTS)}"
        cp_surf = self._hud_font.render(cp_str, True, (155, 155, 178))
        surf.blit(cp_surf, (8, bar_y - 16))

    # ── Overlays ──────────────────────────────────────────────────────────────

    def _show_title(self) -> None:
        self.screen.fill(_SKY_TOP)
        ov = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        self.screen.blit(ov, (0, 0))
        cx, cy = self.width // 2, self.height // 2
        t1 = self._big_font.render("ROLLING BALL", True, (255, 240, 80))
        t2 = self._med_font.render("3D Assault Course Race!", True, (200, 200, 225))
        t3 = self._sml_font.render(
            "P1: Arrow keys   P2: WASD   P3/P4: Gamepad", True, (140, 130, 175))
        self.screen.blit(t1, (cx - t1.get_width() // 2, cy - 70))
        self.screen.blit(t2, (cx - t2.get_width() // 2, cy + 12))
        self.screen.blit(t3, (cx - t3.get_width() // 2, cy + 64))
        pygame.display.flip()
        pygame.time.wait(2000)

    def _do_countdown(self) -> None:
        for label in ("3", "2", "1", "GO!"):
            self._draw()
            ov = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 90))
            self.screen.blit(ov, (0, 0))
            col  = (255, 80, 80) if label != "GO!" else (80, 255, 120)
            surf = self._big_font.render(label, True, col)
            self.screen.blit(surf,
                             (self.width  // 2 - surf.get_width()  // 2,
                              self.height // 2 - surf.get_height() // 2))
            pygame.display.flip()
            pygame.time.wait(700)

    def _show_results(self, headline: str) -> None:
        def _sort_key(b: _Ball3D) -> tuple:
            if b.finished and b.finish_time is not None:
                return (0, b.finish_time + b.time_penalty)
            return (1, -b.progress)

        ranked = sorted(self._balls, key=_sort_key)

        ov = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        ov.fill((0, 0, 30, 210))
        self.screen.blit(ov, (0, 0))

        title = self._big_font.render(headline, True, (255, 240, 80))
        self.screen.blit(title,
                         (self.width // 2 - title.get_width() // 2, 60))

        for rank, ball in enumerate(ranked):
            place = _PLACE_LABELS[rank]
            if ball.finished and ball.finish_time is not None:
                t    = ball.finish_time + ball.time_penalty
                mins = int(t) // 60
                secs = int(t) % 60
                entry = f"{place}  P{ball.idx + 1}  –  {mins}:{secs:02d}"
            else:
                pct   = int(ball.progress * 100)
                entry = f"{place}  P{ball.idx + 1}  –  {pct}% complete"
            col  = _PLAYER_COLS[ball.idx][0]
            surf = self._med_font.render(entry, True, col)
            self.screen.blit(surf,
                             (self.width // 2 - surf.get_width() // 2,
                              148 + rank * 58))

        pygame.display.flip()
        pygame.time.wait(3500)


# ── HUD utility ───────────────────────────────────────────────────────────────


def _draw_hud_badge(surf: pygame.Surface, x: int, y: int,
                    w: int, h: int) -> None:
    """Draw a semi-transparent dark badge behind HUD text."""
    badge = pygame.Surface((w, h), pygame.SRCALPHA)
    badge.fill((14, 12, 28, 175))
    surf.blit(badge, (x, y))
