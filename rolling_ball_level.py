"""rolling_ball_level.py

Rolling Ball Assault Course mode for Quad Fighter.

Up to 4 players each control a character inside a rolling ball, racing
through a timed assault course.  First to the finish line, or the player
furthest along when the 3-minute timer expires, wins.

RollingBallLevel.run() returns "complete" | "dead" | "exit".

Controls
--------
Player 1 : Arrow keys = roll,  ESC = quit
Player 2 : WASD = roll
Player 3 : Joystick 0  (Left-stick / D-pad)
Player 4 : Joystick 1  (Left-stick / D-pad)
"""

from __future__ import annotations

import math
import random

import pygame

from settings import AXIS_DEADZONE

# ── Physics ───────────────────────────────────────────────────────────────────

_BALL_R         = 18        # ball collision radius in pixels
_ACCEL          = 0.50      # rolling acceleration per frame
_FRICTION       = 0.88      # velocity damping per frame
_MAX_SPEED      = 8.0       # maximum ball speed (pixels/frame)
_WALL_BOUNCE    = 0.55      # speed retained after wall reflection
_BALL_BOUNCE    = 0.65      # speed retained after ball–ball collision

# ── Race ──────────────────────────────────────────────────────────────────────

_RACE_SECS      = 180       # 3-minute time limit
_FINISH_X       = 4560      # world-x of the finish line
_RESPAWN_FRAMES = 60        # frames to wait before respawning after a fall
_FALL_FRAMES    = 35        # frames for the shrink-fall animation
_INVULN_FRAMES  = 90        # invulnerability frames after respawn

# ── Course geometry ───────────────────────────────────────────────────────────

# World dimensions (pixels)
_WORLD_W        = 4800
# Height is passed in at runtime; _WORLD_H is used only for wall control points
_WORLD_H        = 600

# Wall control points: list of (world_x, top_y, bot_y).
# Between consecutive points the walls are linearly interpolated.
_WALL_CTRL: list[tuple[int, int, int]] = [
    (0,    110, 490),   # wide starting straight
    (550,  110, 490),
    (720,  185, 415),   # first narrow section
    (1050, 185, 415),
    (1200, 110, 490),   # bumper field – wide
    (1850, 110, 490),
    (2000, 150, 450),   # moving-wall crossing
    (2450, 150, 450),
    (2600, 110, 490),   # spin-bar hazard zone
    (3300, 130, 470),
    (3500, 110, 490),   # final sprint
    (4800, 110, 490),
]

# Checkpoint x positions (from left to right)
_CHECKPOINTS: list[int] = [1000, 2000, 3000, 4000]

# ── Static bumpers: (cx, cy, radius) ─────────────────────────────────────────

_BUMPER_DEFS: list[tuple[int, int, int]] = [
    (1280, 190, 22),
    (1280, 410, 22),
    (1420, 300, 28),
    (1560, 185, 20),
    (1560, 415, 20),
    (1700, 270, 24),
    (1700, 330, 24),
    (1800, 300, 18),
]

# ── Spinning bars: (pivot_x, pivot_y, length, angular_speed_rad, start_angle) ─

_SPINBAR_DEFS: list[tuple[int, int, int, float, float]] = [
    (2680, 300, 85,  0.040, 0.0),
    (2860, 260, 70, -0.050, 1.0),
    (3040, 340, 75,  0.035, 2.1),
    (3220, 300, 90, -0.038, 0.8),
]

# ── Moving walls: (cx, cy, w, h, axis, amplitude, speed_rad, phase) ──────────
# axis: 'x' moves left-right, 'y' moves up-down

_MWALL_DEFS: list[tuple[int, int, int, int, str, int, float, float]] = [
    (2080, 300, 28, 90, 'y',  85, 0.030, 0.0),
    (2200, 300, 28, 90, 'y',  85, 0.030, math.pi),
    (2320, 300, 28, 90, 'y',  85, 0.025, 0.6),
    (2420, 300, 28, 80, 'y',  70, 0.028, 1.5),
]

# ── Bounce pads: (cx, cy, radius, boost_angle_rad, boost_magnitude) ──────────

_BOUNCEPAD_DEFS: list[tuple[int, int, int, float, float]] = [
    (1950, 300, 30,  0.0,          5.5),   # fires rightward
    (2550, 200, 26, -math.pi / 4,  5.0),   # fires up-right
    (2550, 400, 26,  math.pi / 4,  5.0),   # fires down-right
    (3600, 300, 34,  0.0,          6.0),   # final speed boost
]

# ── Hazard pits: (x1, x2) – regions where track floor is absent (a narrow
#    gap the full track height).  A ball whose centre enters this x band while
#    below the track centre line triggers a fall.  We keep these partial so one
#    side of the track always has solid ground to dodge onto. ─────────────────

_PIT_DEFS: list[tuple[int, int, int, int]] = [
    # (x1, x2, y1, y2) – ball centre inside ⟹ falls
    (3420, 3480, 220, 480),   # right-side pit near final sprint
    (3900, 3960, 110, 380),   # left-side pit
]

# ── Colours ───────────────────────────────────────────────────────────────────

_BG_TOP         = (10, 8,  22)
_BG_BOT         = (20, 16, 38)
_TRACK_COL      = (26, 22, 44)
_TRACK_LINE_COL = (46, 40, 72)
_WALL_COL       = (40, 160, 220)
_WALL_RIM_COL   = (20, 80,  140)
_FINISH_COL     = (255, 220, 60)
_FINISH_ALT_COL = (30,  30,  30)
_CHKPT_COL      = (60, 220, 180)
_BUMPER_COL     = (255, 180, 40)
_BUMPER_DARK    = (140,  90, 20)
_SPINBAR_COL    = (255,  80, 80)
_SPINBAR_PIVOT  = (200,  40, 40)
_MWALL_COL      = (120,  80, 220)
_MWALL_DARK     = ( 60,  40, 140)
_BOUNCEPAD_COL  = ( 80, 255, 200)
_BOUNCEPAD_RING = ( 30, 160, 120)
_PIT_COL        = (  8,   4,  16)
_PIT_RIM_COL    = ( 40,  20,  60)
_HUD_COL        = (220, 220, 240)
_TIMER_OK_COL   = ( 80, 220, 120)
_TIMER_LOW_COL  = (255,  80,  80)
_COUNTDOWN_COL  = (255, 240,  80)

# Per-player: (rim_colour, fill_colour, highlight_colour, label_colour)
_PLAYER_COLS: list[tuple] = [
    ((100, 180, 255), ( 30,  80, 160), (200, 230, 255), (120, 200, 255)),  # P1 blue
    ((255, 100, 100), (160,  30,  30), (255, 210, 210), (255, 140, 140)),  # P2 red
    (( 80, 220, 120), ( 30, 120,  60), (180, 255, 200), (100, 255, 160)),  # P3 green
    ((200, 100, 255), (100,  30, 180), (230, 190, 255), (220, 130, 255)),  # P4 purple
]

_PLACE_LABELS  = ["1ST", "2ND", "3RD", "4TH"]

# ── Helpers ───────────────────────────────────────────────────────────────────


def _wall_ys(wx: float) -> tuple[float, float]:
    """Return (top_y, bot_y) of the track at world-x ``wx``."""
    pts = _WALL_CTRL
    if wx <= pts[0][0]:
        return float(pts[0][1]), float(pts[0][2])
    if wx >= pts[-1][0]:
        return float(pts[-1][1]), float(pts[-1][2])
    for i in range(len(pts) - 1):
        x0, t0, b0 = pts[i]
        x1, t1, b1 = pts[i + 1]
        if x0 <= wx <= x1:
            f = (wx - x0) / (x1 - x0)
            return (t0 + (t1 - t0) * f), (b0 + (b1 - b0) * f)
    return float(pts[-1][1]), float(pts[-1][2])


def _segment_closest(px: float, py: float,
                     ax: float, ay: float,
                     bx: float, by: float) -> tuple[float, float]:
    """Closest point on line segment A→B to point P."""
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-9:
        return ax, ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    return ax + t * dx, ay + t * dy


# ── Data classes ──────────────────────────────────────────────────────────────


class _Ball:
    """One player's rolling ball."""

    def __init__(self, idx: int, x: float, y: float) -> None:
        self.idx         = idx
        self.x           = x
        self.y           = y
        self.vx          = 0.0
        self.vy          = 0.0
        self.roll_angle  = 0.0   # visual rotation (radians, grows with movement)
        self.alive       = True
        self.finished    = False
        self.finish_time: float | None = None
        self.checkpoint  = -1    # index of last checkpoint reached (-1 = none)
        self.spawn_x     = x
        self.spawn_y     = y
        # Fall state
        self._falling     = False
        self._fall_timer  = 0
        self._respawn_cd  = 0
        self.invuln       = 0
        self.time_penalty = 0.0  # accumulated time penalty (seconds)

    @property
    def progress(self) -> float:
        """0–1 normalised progress along the course."""
        return min(1.0, self.x / _FINISH_X)

    def respawn(self) -> None:
        """Teleport back to last checkpoint with a brief invulnerability."""
        if self.checkpoint >= 0:
            self.x = float(_CHECKPOINTS[self.checkpoint])
        else:
            self.x = self.spawn_x
        top, bot = _wall_ys(self.x)
        self.y = (top + bot) / 2.0
        self.vx = 0.0
        self.vy = 0.0
        self._falling    = False
        self._fall_timer = 0
        self._respawn_cd = 0
        self.invuln      = _INVULN_FRAMES
        self.time_penalty += _RESPAWN_FRAMES / 60.0


class _Bumper:
    """Static bouncy obstacle."""

    def __init__(self, cx: int, cy: int, r: int) -> None:
        self.cx    = float(cx)
        self.cy    = float(cy)
        self.r     = float(r)
        self.flash = 0

    def update(self) -> None:
        if self.flash > 0:
            self.flash -= 1

    def collide(self, ball: _Ball) -> bool:
        dx   = ball.x - self.cx
        dy   = ball.y - self.cy
        dist = math.hypot(dx, dy)
        min_d = _BALL_R + self.r
        if dist < min_d and dist > 1e-9:
            nx, ny = dx / dist, dy / dist
            # Push ball out of overlap
            ball.x = self.cx + nx * min_d
            ball.y = self.cy + ny * min_d
            # Reflect and boost slightly
            dot = ball.vx * nx + ball.vy * ny
            spd = math.hypot(ball.vx, ball.vy)
            ball.vx -= 2.0 * dot * nx
            ball.vy -= 2.0 * dot * ny
            # Bumpers give a small extra kick so you can't just sit on them
            if spd < 3.5:
                ball.vx += nx * 3.5
                ball.vy += ny * 3.5
            self.flash = 10
            return True
        return False


class _SpinBar:
    """A rotating bar that sweeps around a pivot point."""

    _BAR_HALF_W = 7   # half-width of the bar for collision

    def __init__(self, pivot_x: int, pivot_y: int, length: int,
                 ang_speed: float, phase: float) -> None:
        self.px        = float(pivot_x)
        self.py        = float(pivot_y)
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
                self.py + math.sin(self.angle) * self.length)

    def collide(self, ball: _Ball) -> bool:
        ex, ey = self.tip()
        cx, cy = _segment_closest(ball.x, ball.y, self.px, self.py, ex, ey)
        dx = ball.x - cx
        dy = ball.y - cy
        dist = math.hypot(dx, dy)
        min_d = _BALL_R + self._BAR_HALF_W
        if dist < min_d:
            if dist < 1e-9:
                nx, ny = 1.0, 0.0
            else:
                nx, ny = dx / dist, dy / dist
            overlap = min_d - dist
            ball.x += nx * overlap
            ball.y += ny * overlap
            dot = ball.vx * nx + ball.vy * ny
            ball.vx = (ball.vx - 2.0 * dot * nx) * _WALL_BOUNCE
            ball.vy = (ball.vy - 2.0 * dot * ny) * _WALL_BOUNCE
            self.flash = 8
            return True
        return False


class _MovingWall:
    """A rectangular wall that oscillates back and forth."""

    def __init__(self, cx: int, cy: int, w: int, h: int,
                 axis: str, amplitude: int,
                 speed: float, phase: float) -> None:
        self.base_x   = float(cx)
        self.base_y   = float(cy)
        self.w        = float(w)
        self.h        = float(h)
        self.axis     = axis
        self.amp      = float(amplitude)
        self.speed    = speed
        self.t        = phase
        self.cx       = float(cx)
        self.cy       = float(cy)

    def update(self) -> None:
        self.t += self.speed
        if self.axis == 'y':
            self.cy = self.base_y + math.sin(self.t) * self.amp
        else:
            self.cx = self.base_x + math.sin(self.t) * self.amp

    def rect(self) -> tuple[float, float, float, float]:
        """Returns (left, top, right, bottom) in world coords."""
        return (self.cx - self.w / 2, self.cy - self.h / 2,
                self.cx + self.w / 2, self.cy + self.h / 2)

    def collide(self, ball: _Ball) -> bool:
        left, top, right, bottom = self.rect()
        # Nearest point on rect to ball centre
        nx_c = max(left, min(right,  ball.x))
        ny_c = max(top,  min(bottom, ball.y))
        dx   = ball.x - nx_c
        dy   = ball.y - ny_c
        dist = math.hypot(dx, dy)
        if dist < _BALL_R:
            if dist < 1e-9:
                nx, ny = 1.0, 0.0
                dist   = 1.0
            else:
                nx, ny = dx / dist, dy / dist
            overlap = _BALL_R - dist
            ball.x += nx * overlap
            ball.y += ny * overlap
            dot = ball.vx * nx + ball.vy * ny
            ball.vx = (ball.vx - 2.0 * dot * nx) * _WALL_BOUNCE
            ball.vy = (ball.vy - 2.0 * dot * ny) * _WALL_BOUNCE
            return True
        return False


class _BouncePad:
    """A pad that fires the ball in a fixed direction."""

    def __init__(self, cx: int, cy: int, r: int,
                 boost_angle: float, boost_mag: float) -> None:
        self.cx          = float(cx)
        self.cy          = float(cy)
        self.r           = float(r)
        self.boost_angle = boost_angle
        self.boost_mag   = boost_mag
        self.flash       = 0

    def update(self) -> None:
        if self.flash > 0:
            self.flash -= 1

    def check(self, ball: _Ball) -> bool:
        if math.hypot(ball.x - self.cx, ball.y - self.cy) < self.r + _BALL_R:
            ball.vx += math.cos(self.boost_angle) * self.boost_mag
            ball.vy += math.sin(self.boost_angle) * self.boost_mag
            spd = math.hypot(ball.vx, ball.vy)
            cap = _MAX_SPEED * 1.6
            if spd > cap:
                ball.vx = ball.vx / spd * cap
                ball.vy = ball.vy / spd * cap
            self.flash = 14
            return True
        return False


# ── Main level class ──────────────────────────────────────────────────────────


class RollingBallLevel:
    """Self-contained rolling ball assault course.

    Call ``run()`` to play.  Returns ``"complete"``, ``"dead"``, or
    ``"exit"`` (player pressed ESC).

    Parameters
    ----------
    joystick  : pygame.joystick.Joystick | None
        Controller for Player 3.
    joystick2 : pygame.joystick.Joystick | None
        Controller for Player 4.
    """

    def __init__(self, screen: pygame.Surface,
                 width: int, height: int, fps: int,
                 settings, font,
                 acid, sfx,
                 joystick=None, joystick2=None) -> None:
        self.screen   = screen
        self.width    = width
        self.height   = height
        self.fps      = fps
        self.settings = settings
        self.font     = font
        self.acid     = acid
        self.sfx      = sfx

        self._joys: list = []
        if joystick is not None:
            self._joys.append(joystick)
        if joystick2 is not None:
            self._joys.append(joystick2)

        self._clock = pygame.time.Clock()

        # Fonts
        self._hud_font  = pygame.font.SysFont(None, 26, bold=True)
        self._big_font  = pygame.font.SysFont(None, 72, bold=True)
        self._med_font  = pygame.font.SysFont(None, 44, bold=True)
        self._sml_font  = pygame.font.SysFont(None, 32, bold=True)

        # State populated by _reset()
        self._balls   : list[_Ball]       = []
        self._bumpers : list[_Bumper]     = []
        self._spinbars: list[_SpinBar]    = []
        self._mwalls  : list[_MovingWall] = []
        self._bpads   : list[_BouncePad]  = []
        self._cam_x   = 0.0
        self._timer   = 0.0    # elapsed race time (seconds)
        self._frame   = 0
        self._finished_order: list[int] = []  # ball indices in finish order
        self._race_over = False

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> str:
        """Play the rolling ball level.  Returns ``"complete"`` / ``"exit"``."""
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

            # Check finish / time-up
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
        self._frame        = 0
        self._timer        = 0.0
        self._race_over    = False
        self._finished_order = []
        self._cam_x        = 0.0

        # Scale world Y control points to actual screen height
        scale = self.height / _WORLD_H

        # Determine player count: always P1+P2 keyboard, plus one per joystick
        num_players = min(4, 2 + len(self._joys))

        # Spawn positions – spread vertically in start zone
        start_ys = [
            int(self.height * 0.30),
            int(self.height * 0.70),
            int(self.height * 0.45),
            int(self.height * 0.55),
        ]
        self._balls = [
            _Ball(i, 80.0, float(start_ys[i]))
            for i in range(num_players)
        ]
        for b in self._balls:
            b.spawn_y = b.y

        # Build obstacles (scale world-Y coords to screen height)
        def scale_y(y: int) -> float:
            return float(y) * scale

        self._bumpers = [
            _Bumper(cx, int(scale_y(cy)), r)
            for cx, cy, r in _BUMPER_DEFS
        ]
        self._spinbars = [
            _SpinBar(px, int(scale_y(py)), length, spd, phase)
            for px, py, length, spd, phase in _SPINBAR_DEFS
        ]
        self._mwalls = [
            _MovingWall(cx, int(scale_y(cy)), w, int(h * scale), axis,
                        int(amp * scale), spd, phase)
            for cx, cy, w, h, axis, amp, spd, phase in _MWALL_DEFS
        ]
        self._bpads = [
            _BouncePad(cx, int(scale_y(cy)), r, angle, mag)
            for cx, cy, r, angle, mag in _BOUNCEPAD_DEFS
        ]

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_events(self) -> str | None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "exit"
        return None

    def _read_inputs(self) -> list[tuple[float, float]]:
        """Return list of (ax, ay) in [-1, 1] for each active ball."""
        keys   = pygame.key.get_pressed()
        inputs: list[tuple[float, float]] = []

        # P1 – arrow keys
        ax1 = ((1.0 if keys[self.settings.keyboard.get("move_right", pygame.K_RIGHT)] else 0.0) -
               (1.0 if keys[self.settings.keyboard.get("move_left",  pygame.K_LEFT)]  else 0.0))
        ay1 = ((1.0 if keys[self.settings.keyboard.get("move_down",  pygame.K_DOWN)]  else 0.0) -
               (1.0 if keys[self.settings.keyboard.get("move_up",    pygame.K_UP)]    else 0.0))
        inputs.append((ax1, ay1))

        # P2 – WASD
        if len(self._balls) >= 2:
            ax2 = ((1.0 if keys[self.settings.keyboard_p2.get("move_right", pygame.K_d)] else 0.0) -
                   (1.0 if keys[self.settings.keyboard_p2.get("move_left",  pygame.K_a)] else 0.0))
            ay2 = ((1.0 if keys[self.settings.keyboard_p2.get("move_down",  pygame.K_s)] else 0.0) -
                   (1.0 if keys[self.settings.keyboard_p2.get("move_up",    pygame.K_w)] else 0.0))
            inputs.append((ax2, ay2))

        # P3 / P4 – joysticks
        for joy in self._joys:
            if len(inputs) >= len(self._balls):
                break
            ax, ay = 0.0, 0.0
            if joy.get_numaxes() >= 1:
                raw = joy.get_axis(0)
                if abs(raw) > AXIS_DEADZONE:
                    ax = raw
            if joy.get_numaxes() >= 2:
                raw = joy.get_axis(1)
                if abs(raw) > AXIS_DEADZONE:
                    ay = raw
            if joy.get_numhats() > 0:
                hx, hy = joy.get_hat(0)
                if hx != 0:
                    ax = float(hx)
                if hy != 0:
                    ay = float(-hy)   # hat y is inverted
            inputs.append((ax, ay))

        return inputs

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self, dt: float) -> None:
        scale = self.height / _WORLD_H

        inputs = self._read_inputs()

        # Update obstacle animations
        for b in self._bumpers:
            b.update()
        for sb in self._spinbars:
            sb.update()
        for mw in self._mwalls:
            mw.update()
        for bp in self._bpads:
            bp.update()

        for ball, (ax, ay) in zip(self._balls, inputs):
            if ball.finished:
                continue

            # --- Respawn countdown ---
            if ball._respawn_cd > 0:
                ball._respawn_cd -= 1
                if ball._respawn_cd == 0:
                    ball.respawn()
                continue

            # --- Fall animation ---
            if ball._falling:
                ball._fall_timer += 1
                if ball._fall_timer >= _FALL_FRAMES:
                    ball._respawn_cd = _RESPAWN_FRAMES
                continue

            if ball.invuln > 0:
                ball.invuln -= 1

            # --- Apply player input ---
            ball.vx += ax * _ACCEL
            ball.vy += ay * _ACCEL

            # --- Friction ---
            ball.vx *= _FRICTION
            ball.vy *= _FRICTION

            # --- Speed cap ---
            spd = math.hypot(ball.vx, ball.vy)
            if spd > _MAX_SPEED:
                ball.vx = ball.vx / spd * _MAX_SPEED
                ball.vy = ball.vy / spd * _MAX_SPEED

            # --- Move ---
            ball.x += ball.vx
            ball.y += ball.vy

            # --- Update visual roll angle ---
            ball.roll_angle += spd * 0.06

            # --- Clamp to world bounds ---
            ball.x = max(float(_BALL_R), min(float(_WORLD_W - _BALL_R), ball.x))

            # --- Wall collision (top/bottom) ---
            top_y, bot_y = _wall_ys(ball.x)
            top_y *= scale
            bot_y *= scale
            if ball.y - _BALL_R < top_y:
                ball.y  = top_y + _BALL_R
                ball.vy = abs(ball.vy) * _WALL_BOUNCE
            if ball.y + _BALL_R > bot_y:
                ball.y  = bot_y - _BALL_R
                ball.vy = -abs(ball.vy) * _WALL_BOUNCE

            # --- Obstacle collisions ---
            for bumper in self._bumpers:
                bumper.collide(ball)
            for sb in self._spinbars:
                sb.collide(ball)
            for mw in self._mwalls:
                mw.collide(ball)

            # --- Bounce pads ---
            for bp in self._bpads:
                bp.check(ball)

            # --- Pit check ---
            if ball.invuln == 0:
                for x1, x2, y1, y2 in _PIT_DEFS:
                    py1 = y1 * scale
                    py2 = y2 * scale
                    if x1 <= ball.x <= x2 and py1 <= ball.y <= py2:
                        ball._falling    = True
                        ball._fall_timer = 0
                        ball.vx = 0.0
                        ball.vy = 0.0
                        break

            # --- Checkpoint ---
            for ci, cx in enumerate(_CHECKPOINTS):
                if ci > ball.checkpoint and ball.x >= cx:
                    ball.checkpoint = ci

            # --- Finish line ---
            if ball.x >= _FINISH_X:
                ball.finished    = True
                ball.finish_time = self._timer
                self._finished_order.append(ball.idx)

        # --- Ball–ball collisions ---
        active = [b for b in self._balls
                  if not b.finished and not b._falling and b._respawn_cd == 0]
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                a, b = active[i], active[j]
                dx   = b.x - a.x
                dy   = b.y - a.y
                dist = math.hypot(dx, dy)
                min_d = _BALL_R * 2
                if dist < min_d and dist > 1e-9:
                    nx, ny  = dx / dist, dy / dist
                    overlap = (min_d - dist) / 2.0
                    a.x -= nx * overlap
                    a.y -= ny * overlap
                    b.x += nx * overlap
                    b.y += ny * overlap
                    # Exchange velocity components along normal
                    da = a.vx * nx + a.vy * ny
                    db = b.vx * nx + b.vy * ny
                    a.vx += (db - da) * nx * _BALL_BOUNCE
                    a.vy += (db - da) * ny * _BALL_BOUNCE
                    b.vx += (da - db) * nx * _BALL_BOUNCE
                    b.vy += (da - db) * ny * _BALL_BOUNCE

        # --- Camera ---
        visible = [b for b in self._balls
                   if not b.finished and b._respawn_cd == 0]
        if not visible:
            visible = self._balls
        if visible:
            cx = sum(b.x for b in visible) / len(visible)
            target = cx - self.width / 2.0
            self._cam_x += (target - self._cam_x) * 0.08
            self._cam_x  = max(0.0, min(float(_WORLD_W - self.width), self._cam_x))

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self._draw_background()
        self._draw_track()
        self._draw_pits()
        self._draw_finish()
        self._draw_checkpoints()
        self._draw_bpads()
        self._draw_mwalls()
        self._draw_bumpers()
        self._draw_spinbars()
        self._draw_balls()
        self._draw_hud()

    def _sx(self, wx: float) -> int:
        """World-x → screen-x."""
        return int(wx - self._cam_x)

    def _draw_background(self) -> None:
        """Gradient sky/bg, drawn every frame (cheap)."""
        for y in range(self.height):
            t = y / self.height
            r = int(_BG_TOP[0] + (_BG_BOT[0] - _BG_TOP[0]) * t)
            g = int(_BG_TOP[1] + (_BG_BOT[1] - _BG_TOP[1]) * t)
            b = int(_BG_TOP[2] + (_BG_BOT[2] - _BG_TOP[2]) * t)
            pygame.draw.line(self.screen, (r, g, b),
                             (0, y), (self.width, y))

    def _draw_track(self) -> None:
        """Draw the visible section of the track floor + walls."""
        scale = self.height / _WORLD_H
        cam   = self._cam_x

        # Build a polygon for the track floor (top and bottom edges)
        step   = 8
        x_left  = int(cam)
        x_right = int(cam + self.width)

        top_pts: list[tuple[int, int]] = []
        bot_pts: list[tuple[int, int]] = []

        x = x_left
        while x <= x_right + step:
            ty, by = _wall_ys(float(x))
            ty *= scale
            by *= scale
            sx = x - int(cam)
            top_pts.append((sx, int(ty)))
            bot_pts.append((sx, int(by)))
            x += step

        # Fill track
        if len(top_pts) >= 2:
            floor_poly = top_pts + list(reversed(bot_pts))
            pygame.draw.polygon(self.screen, _TRACK_COL, floor_poly)

            # Lane markings (dashed centre line)
            prev_top = top_pts[0]
            prev_bot = bot_pts[0]
            for i in range(1, len(top_pts)):
                cur_top = top_pts[i]
                cur_bot = bot_pts[i]
                mid_y_prev = (prev_top[1] + prev_bot[1]) // 2
                mid_y_cur  = (cur_top[1]  + cur_bot[1])  // 2
                if (prev_top[0] // 48) != (cur_top[0] // 48):
                    pygame.draw.line(self.screen, _TRACK_LINE_COL,
                                     (prev_top[0], mid_y_prev),
                                     (cur_top[0],  mid_y_cur), 2)
                prev_top, prev_bot = cur_top, cur_bot

            # Top wall
            wall_top_pts = [(p[0], 0) for p in top_pts] + list(reversed(top_pts))
            pygame.draw.polygon(self.screen, _WALL_RIM_COL, wall_top_pts)
            pygame.draw.lines(self.screen, _WALL_COL, False, top_pts, 3)

            # Bottom wall
            wall_bot_pts = bot_pts + [(p[0], self.height) for p in reversed(bot_pts)]
            pygame.draw.polygon(self.screen, _WALL_RIM_COL, wall_bot_pts)
            pygame.draw.lines(self.screen, _WALL_COL, False, bot_pts, 3)

    def _draw_pits(self) -> None:
        scale = self.height / _WORLD_H
        for x1, x2, y1, y2 in _PIT_DEFS:
            sx1 = self._sx(x1)
            sx2 = self._sx(x2)
            if sx2 < 0 or sx1 > self.width:
                continue
            py1 = int(y1 * scale)
            py2 = int(y2 * scale)
            rect = pygame.Rect(sx1, py1, sx2 - sx1, py2 - py1)
            pygame.draw.rect(self.screen, _PIT_COL, rect)
            pygame.draw.rect(self.screen, _PIT_RIM_COL, rect, 3)

    def _draw_finish(self) -> None:
        sx = self._sx(_FINISH_X)
        if not (-40 <= sx <= self.width + 40):
            return
        scale = self.height / _WORLD_H
        ty, by = _wall_ys(_FINISH_X)
        ty = int(ty * scale)
        by = int(by * scale)
        # Checkerboard finish line
        tile = 14
        for row_start in range(ty, by, tile):
            for col in range(0, 4):
                if (row_start // tile + col) % 2 == 0:
                    col_x = sx - tile * 2 + col * tile
                    pygame.draw.rect(self.screen, _FINISH_COL,
                                     (col_x, row_start, tile, min(tile, by - row_start)))
                else:
                    col_x = sx - tile * 2 + col * tile
                    pygame.draw.rect(self.screen, _FINISH_ALT_COL,
                                     (col_x, row_start, tile, min(tile, by - row_start)))
        # "FINISH" label
        lbl = self._sml_font.render("FINISH", True, _FINISH_COL)
        self.screen.blit(lbl, (sx - lbl.get_width() // 2, ty - 26))

    def _draw_checkpoints(self) -> None:
        scale = self.height / _WORLD_H
        for ci, cx in enumerate(_CHECKPOINTS):
            sx = self._sx(cx)
            if not (-20 <= sx <= self.width + 20):
                continue
            ty, by = _wall_ys(float(cx))
            ty = int(ty * scale)
            by = int(by * scale)
            alpha = 180 if (self._frame // 20) % 2 == 0 else 120
            col   = tuple(int(c * alpha / 255) for c in _CHKPT_COL)
            pygame.draw.line(self.screen, col, (sx, ty), (sx, by), 3)
            lbl = self._hud_font.render(f"CP{ci + 1}", True, _CHKPT_COL)
            self.screen.blit(lbl, (sx - lbl.get_width() // 2, ty - 18))

    def _draw_bumpers(self) -> None:
        for bmp in self._bumpers:
            sx = self._sx(bmp.cx)
            sy = int(bmp.cy)
            if not (-bmp.r - 4 <= sx <= self.width + bmp.r + 4):
                continue
            r  = int(bmp.r)
            # Filled circle
            col = _BUMPER_COL if bmp.flash else _BUMPER_DARK
            pygame.draw.circle(self.screen, _BUMPER_DARK, (sx, sy), r)
            pygame.draw.circle(self.screen, col, (sx, sy), r, 4)
            # Inner ring
            if r > 8:
                pygame.draw.circle(self.screen, col, (sx, sy), r // 2, 2)

    def _draw_spinbars(self) -> None:
        for sb in self._spinbars:
            sx_p = self._sx(sb.px)
            sy_p = int(sb.py)
            if not (-sb.length - 20 <= sx_p <= self.width + sb.length + 20):
                continue
            ex, ey = sb.tip()
            sx_e   = self._sx(ex)
            col    = _SPINBAR_COL if sb.flash else tuple(c // 2 for c in _SPINBAR_COL)
            # Draw bar as thick line
            pygame.draw.line(self.screen, col, (sx_p, sy_p), (int(sx_e), int(ey)), 10)
            pygame.draw.line(self.screen, (255, 255, 255), (sx_p, sy_p), (int(sx_e), int(ey)), 3)
            # Pivot
            pygame.draw.circle(self.screen, _SPINBAR_PIVOT, (sx_p, sy_p), 10)
            pygame.draw.circle(self.screen, (220, 100, 100), (sx_p, sy_p), 6)

    def _draw_mwalls(self) -> None:
        for mw in self._mwalls:
            sx = self._sx(mw.cx)
            if not (-mw.w - 10 <= sx <= self.width + mw.w + 10):
                continue
            rect = pygame.Rect(
                int(sx - mw.w / 2), int(mw.cy - mw.h / 2),
                int(mw.w), int(mw.h),
            )
            pygame.draw.rect(self.screen, _MWALL_DARK, rect)
            pygame.draw.rect(self.screen, _MWALL_COL,  rect, 4)
            # Speed-stripe highlight
            stripe_y = int(mw.cy)
            pygame.draw.line(self.screen, (180, 140, 255),
                             (rect.left + 4, stripe_y),
                             (rect.right - 4, stripe_y), 2)

    def _draw_bpads(self) -> None:
        for bp in self._bpads:
            sx = self._sx(bp.cx)
            sy = int(bp.cy)
            if not (-bp.r - 10 <= sx <= self.width + bp.r + 10):
                continue
            r    = int(bp.r)
            col  = _BOUNCEPAD_COL if bp.flash else _BOUNCEPAD_RING
            pygame.draw.circle(self.screen, _BOUNCEPAD_RING, (sx, sy), r)
            pygame.draw.circle(self.screen, col, (sx, sy), r, 4)
            # Arrow indicating boost direction
            angle  = bp.boost_angle
            tip_x  = sx + int(math.cos(angle) * (r - 4))
            tip_y  = sy + int(math.sin(angle) * (r - 4))
            base_x = sx - int(math.cos(angle) * (r // 2))
            base_y = sy - int(math.sin(angle) * (r // 2))
            pygame.draw.line(self.screen, col, (base_x, base_y), (tip_x, tip_y), 3)

    def _draw_balls(self) -> None:
        for ball in self._balls:
            if ball.finished:
                continue
            if ball._respawn_cd > 0:
                # Brief respawn flash
                if (self._frame // 4) % 2 == 0:
                    sx = self._sx(ball.x)
                    sy = int(ball.y)
                    pygame.draw.circle(self.screen, _PLAYER_COLS[ball.idx][0],
                                       (sx, sy), _BALL_R // 2, 2)
                continue

            # Blink during invulnerability
            if ball.invuln > 0 and (self._frame // 4) % 2 == 0:
                continue

            # Fall animation: shrink the ball
            draw_r = _BALL_R
            if ball._falling:
                shrink = ball._fall_timer / _FALL_FRAMES
                draw_r = max(2, int(_BALL_R * (1.0 - shrink * 0.85)))

            sx = self._sx(ball.x)
            sy = int(ball.y)
            rim_col, fill_col, hi_col, _ = _PLAYER_COLS[ball.idx]

            # Outer shadow
            pygame.draw.circle(self.screen, (0, 0, 0), (sx + 3, sy + 3), draw_r)
            # Fill
            pygame.draw.circle(self.screen, fill_col, (sx, sy), draw_r)
            # Rim
            pygame.draw.circle(self.screen, rim_col, (sx, sy), draw_r, 3)
            # Highlight (static white gleam, top-left)
            if draw_r >= 6:
                pygame.draw.circle(self.screen, hi_col,
                                   (sx - draw_r // 3, sy - draw_r // 3),
                                   max(2, draw_r // 3))

            # Rolling indicator – two lines through ball at roll_angle
            if draw_r >= 8:
                angle  = ball.roll_angle
                cos_a  = math.cos(angle)
                sin_a  = math.sin(angle)
                r2     = draw_r - 3
                pygame.draw.line(self.screen, rim_col,
                                 (sx + int(cos_a * r2), sy + int(sin_a * r2)),
                                 (sx - int(cos_a * r2), sy - int(sin_a * r2)), 2)
                # Perpendicular
                pygame.draw.line(self.screen, rim_col,
                                 (sx + int(-sin_a * r2), sy + int(cos_a * r2)),
                                 (sx - int(-sin_a * r2), sy - int(cos_a * r2)), 2)

            # Inner character silhouette (tiny stick figure inside ball)
            if draw_r >= 10 and not ball._falling:
                head_r = max(2, draw_r // 4)
                head_y = sy - draw_r // 3
                # Head
                pygame.draw.circle(self.screen, hi_col, (sx, head_y), head_r)
                # Body
                pygame.draw.line(self.screen, hi_col,
                                 (sx, head_y + head_r),
                                 (sx, sy + draw_r // 4), 2)

            # Player label above ball
            if not ball._falling:
                lbl = self._hud_font.render(f"P{ball.idx + 1}", True,
                                            _PLAYER_COLS[ball.idx][3])
                self.screen.blit(lbl, (sx - lbl.get_width() // 2,
                                       sy - draw_r - 18))

    def _draw_hud(self) -> None:
        scale = self.height / _WORLD_H

        # ── Timer (top centre) ────────────────────────────────────────────────
        remaining = max(0.0, _RACE_SECS - self._timer)
        mins = int(remaining) // 60
        secs = int(remaining) % 60
        timer_str = f"{mins}:{secs:02d}"
        t_col = _TIMER_LOW_COL if remaining < 30 else _TIMER_OK_COL
        t_surf = self._med_font.render(timer_str, True, t_col)
        self.screen.blit(t_surf,
                         (self.width // 2 - t_surf.get_width() // 2, 6))

        # ── Player progress bars (bottom strip) ───────────────────────────────
        bar_h   = 16
        bar_y   = self.height - bar_h - 6
        bar_w   = self.width // 4 - 12
        for i, ball in enumerate(self._balls):
            bar_x  = 6 + i * (bar_w + 12)
            # Background
            pygame.draw.rect(self.screen, (40, 35, 60),
                             (bar_x, bar_y, bar_w, bar_h))
            # Fill
            fill_w = int(bar_w * ball.progress)
            if fill_w > 0:
                pygame.draw.rect(self.screen, _PLAYER_COLS[i][0],
                                 (bar_x, bar_y, fill_w, bar_h))
            pygame.draw.rect(self.screen, _PLAYER_COLS[i][3],
                             (bar_x, bar_y, bar_w, bar_h), 2)
            # Label
            status = "DONE" if ball.finished else f"P{i + 1}"
            lbl = self._hud_font.render(status, True, _PLAYER_COLS[i][3])
            self.screen.blit(lbl, (bar_x + 2, bar_y - 18))

        # ── Position labels (left panel) ──────────────────────────────────────
        # Sort players by progress for live position display
        sorted_balls = sorted(self._balls, key=lambda b: -b.progress)
        for rank, ball in enumerate(sorted_balls):
            pos_str = f"{_PLACE_LABELS[rank]} P{ball.idx + 1}"
            pos_surf = self._hud_font.render(pos_str, True,
                                             _PLAYER_COLS[ball.idx][3])
            self.screen.blit(pos_surf, (6, 8 + rank * 20))

        # ── Checkpoint status ─────────────────────────────────────────────────
        for i, ball in enumerate(self._balls):
            cp_str = f"CP {ball.checkpoint + 1}/{len(_CHECKPOINTS)}"
            cp_surf = self._hud_font.render(cp_str, True, (160, 160, 180))
            bar_x = 6 + i * (bar_w + 12)
            self.screen.blit(cp_surf, (bar_x + 2, bar_y + bar_h + 2))

    # ── Overlays ──────────────────────────────────────────────────────────────

    def _show_title(self) -> None:
        self.screen.fill(_BG_TOP)
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        title = self._big_font.render("ROLLING BALL", True, (255, 240, 80))
        sub   = self._med_font.render("Assault Course Race!", True, (200, 200, 220))
        hint  = self._sml_font.render(
            "P1: Arrow keys   P2: WASD   P3/P4: Gamepad", True, (140, 130, 170))
        cx = self.width // 2
        cy = self.height // 2
        self.screen.blit(title, (cx - title.get_width() // 2, cy - 60))
        self.screen.blit(sub,   (cx - sub.get_width()   // 2, cy + 20))
        self.screen.blit(hint,  (cx - hint.get_width()  // 2, cy + 68))
        pygame.display.flip()
        pygame.time.wait(2000)

    def _do_countdown(self) -> None:
        """Show 3 – 2 – 1 – GO! countdown before rolling begins."""
        for label in ("3", "2", "1", "GO!"):
            self._draw()
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 90))
            self.screen.blit(overlay, (0, 0))
            col  = (255, 80, 80) if label != "GO!" else (80, 255, 120)
            surf = self._big_font.render(label, True, col)
            self.screen.blit(surf, (self.width  // 2 - surf.get_width()  // 2,
                                    self.height // 2 - surf.get_height() // 2))
            pygame.display.flip()
            pygame.time.wait(700)

    def _show_results(self, headline: str) -> None:
        """Display final race results overlay."""
        # Sort by progress / finish time
        def sort_key(b: _Ball) -> tuple:
            if b.finished and b.finish_time is not None:
                return (0, b.finish_time + b.time_penalty)
            return (1, -b.progress)

        sorted_balls = sorted(self._balls, key=sort_key)

        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 30, 200))
        self.screen.blit(overlay, (0, 0))

        title = self._big_font.render(headline, True, (255, 240, 80))
        self.screen.blit(title, (self.width  // 2 - title.get_width()  // 2, 60))

        for rank, ball in enumerate(sorted_balls):
            place = _PLACE_LABELS[rank]
            if ball.finished and ball.finish_time is not None:
                t     = ball.finish_time + ball.time_penalty
                mins  = int(t) // 60
                secs  = int(t) % 60
                entry = f"{place}  P{ball.idx + 1}  –  {mins}:{secs:02d}"
            else:
                pct = int(ball.progress * 100)
                entry = f"{place}  P{ball.idx + 1}  –  {pct}% complete"
            col  = _PLAYER_COLS[ball.idx][0]
            surf = self._med_font.render(entry, True, col)
            self.screen.blit(surf,
                             (self.width // 2 - surf.get_width() // 2,
                              150 + rank * 56))

        pygame.display.flip()
        pygame.time.wait(3500)
