"""pang_level.py

Pang / Buster-Bros inspired multiplayer mode for Quad Fighter.

Up to 4 players cooperate on a single screen.  Players fire vertical shots
upward to split and destroy bouncing objects before they collide with players.

PangLevel.run() returns "complete" | "dead" | "exit".

Controls
--------
Player 1 : Arrow Left/Right = move, Space = jump, Z = shoot
Player 2 : A/D = move, Q = jump, R = shoot
Player 3 : Joystick 0 (Left-stick / D-pad, A button = shoot / jump)
Player 4 : Joystick 1 (Left-stick / D-pad, A button = shoot / jump)
ESC      : quit to splash
"""

from __future__ import annotations

import math
import random

import pygame

from settings import AXIS_DEADZONE

# ── Layout ────────────────────────────────────────────────────────────────────

_GROUND_H       = 36        # ground strip height (pixels)
_WALL_W         = 28        # side wall width
_CEILING_H      = 24        # ceiling strip height

# ── Player tuning ─────────────────────────────────────────────────────────────

_P_SPEED        = 3.8       # horizontal pixels per frame
_P_JUMP_VY      = -13.0     # initial upward velocity on jump
_GRAVITY        = 0.52      # downward acceleration per frame
_MAX_LIVES      = 3         # lives each player starts with
_INVULN_FRAMES  = 90        # invulnerability after being hit
_P_RADIUS       = 14        # collision half-width for player
_P_HEIGHT       = 32        # visual height of player figure
_P_SHOOT_CD     = 14        # minimum frames between shots

# ── Shot tuning ───────────────────────────────────────────────────────────────

_SHOT_SPEED     = 9         # pixels per frame upward
_SHOT_W         = 6         # shot visual half-width

# ── Object tuning ─────────────────────────────────────────────────────────────

# Size tier: 0 = large, 1 = medium, 2 = small, 3 = tiny (destroys on hit)
_OBJ_RADII      = [34, 22, 14, 9]
_OBJ_SPEEDS     = [1.5, 2.2, 3.0, 4.0]   # base horizontal speeds per tier
_OBJ_BOUNCE_VY  = [-9.0, -10.5, -12.0, -13.5]   # upward bounce on floor hit
_OBJ_COLORS     = [
    (180, 80,  40),    # large  – warm dark orange
    (200, 140, 40),    # medium – amber
    (100, 200, 180),   # small  – teal
    (220, 220, 80),    # tiny   – bright yellow
]
_OBJ_DARK       = [
    (100, 40,  20),
    (120, 80,  20),
    (50,  120, 100),
    (140, 140, 40),
]
_OBJ_SIDES      = [8, 7, 6, 5]   # polygon sides per tier

# Initial objects spawned at level start
_INITIAL_OBJECTS = 2

# ── Visual / HUD ──────────────────────────────────────────────────────────────

_FLOOR_COL      = (60,  55,  80)
_FLOOR_LINE_COL = (80,  75,  110)
_WALL_COL       = (50,  48,  70)
_CEILING_COL    = (45,  42,  65)
_BG_TOP         = (12,  10,  28)
_BG_BOT         = (22,  18,  45)
_SHOT_COL       = (200, 255, 180)
_SHOT_GLOW      = (100, 255, 80)
_HUD_COL        = (220, 220, 220)
_LIFE_COL       = (80,  200, 120)
_LIFE_EMPTY_COL = (60,  60,  60)
_OBJ_COUNT_COL  = (220, 180, 80)

# Player palette (body, head, accent)
_PLAYER_PALETTES = [
    ((80,  160, 255), (230, 200, 170), (255, 220, 80)),   # P1 blue
    ((220, 80,  80),  (230, 200, 170), (255, 140, 40)),   # P2 red
    ((80,  220, 120), (230, 200, 170), (80,  220, 255)),  # P3 green
    ((180, 80,  220), (230, 200, 170), (255, 80,  180)),  # P4 purple
]

_LABEL_COLORS = [
    (100, 180, 255),
    (255, 120, 120),
    (100, 255, 160),
    (220, 120, 255),
]

# Controller button indices (standard Xbox / SDL)
_BTN_SHOOT = 0   # A button – also jump
_BTN_JUMP  = 3   # Y button – dedicated jump


# ── Helper: polygon drawing ───────────────────────────────────────────────────

def _polygon_pts(cx: float, cy: float, r: float, sides: int,
                 angle_offset: float = 0.0) -> list[tuple[int, int]]:
    pts = []
    for i in range(sides):
        a = angle_offset + i * 2 * math.pi / sides
        pts.append((int(cx + r * math.cos(a)), int(cy + r * math.sin(a))))
    return pts


# ── Data classes ──────────────────────────────────────────────────────────────

class _Shot:
    """A vertical shot fired upward by a player."""

    def __init__(self, x: float, y: float, owner: int) -> None:
        self.x     = x
        self.y     = y
        self.owner = owner   # player index 0-3
        self.alive = True

    def update(self) -> None:
        self.y -= _SHOT_SPEED


class _BallObject:
    """A bouncing object that splits on hit."""

    _id_counter = 0

    def __init__(self, x: float, y: float, tier: int,
                 vx: float, vy: float) -> None:
        _BallObject._id_counter += 1
        self.oid   = _BallObject._id_counter
        self.x     = x
        self.y     = y
        self.tier  = tier
        self.vx    = vx
        self.vy    = vy
        self.r     = _OBJ_RADII[tier]
        self.alive = True
        self.angle = random.uniform(0, 2 * math.pi)   # visual spin angle

    def update(self, ground_y: float, left_x: float, right_x: float,
               ceiling_y: float) -> None:
        self.vy += _GRAVITY
        self.x  += self.vx
        self.y  += self.vy
        self.angle += 0.03

        # Floor bounce
        if self.y + self.r >= ground_y:
            self.y  = ground_y - self.r
            self.vy = _OBJ_BOUNCE_VY[self.tier]

        # Left wall
        if self.x - self.r <= left_x:
            self.x  = left_x + self.r
            self.vx = abs(self.vx)

        # Right wall
        if self.x + self.r >= right_x:
            self.x  = right_x - self.r
            self.vx = -abs(self.vx)

        # Ceiling
        if self.y - self.r <= ceiling_y:
            self.y  = ceiling_y + self.r
            self.vy = abs(self.vy)


class _PangPlayer:
    """One player in pang mode."""

    def __init__(self, player_idx: int, x: float, ground_y: float) -> None:
        self.idx      = player_idx
        self.x        = x
        self.y        = ground_y
        self.ground_y = ground_y
        self.vy       = 0.0
        self.vx       = 0.0
        self.lives    = _MAX_LIVES
        self.alive    = True
        self.invuln   = 0
        self.shoot_cd = 0
        self.facing   = 1   # +1 right / -1 left
        # Cached input state for edge detection
        self._prev_shoot = False
        self._prev_jump  = False

    @property
    def on_ground(self) -> bool:
        return self.y >= self.ground_y - 1

    def update(self, dx: float, do_jump: bool, do_shoot: bool,
               left_x: float, right_x: float) -> _Shot | None:
        """Apply one frame of physics and input.  Returns a new _Shot or None."""
        # Horizontal movement
        self.x  = max(left_x + _P_RADIUS,
                      min(right_x - _P_RADIUS, self.x + dx * _P_SPEED))
        if dx != 0:
            self.facing = 1 if dx > 0 else -1

        # Jump
        if do_jump and self.on_ground:
            self.vy = _P_JUMP_VY

        # Gravity
        self.vy = min(self.vy + _GRAVITY, 24.0)
        self.y  = min(self.y + self.vy, self.ground_y)
        if self.y >= self.ground_y:
            self.y  = self.ground_y
            self.vy = 0.0

        # Invulnerability countdown
        if self.invuln > 0:
            self.invuln -= 1

        # Shoot
        shot = None
        new_shoot = do_shoot
        if new_shoot and not self._prev_shoot and self.shoot_cd == 0:
            shot = _Shot(self.x, self.y - _P_HEIGHT * 0.5, self.idx)
            self.shoot_cd = _P_SHOOT_CD
        self._prev_shoot = new_shoot

        if self.shoot_cd > 0:
            self.shoot_cd -= 1

        return shot

    def hit(self) -> bool:
        """Called when struck by an object.  Returns True if player dies."""
        if self.invuln > 0:
            return False
        self.invuln = _INVULN_FRAMES
        self.lives -= 1
        if self.lives <= 0:
            self.alive = False
            return True
        return False


# ── Main level class ──────────────────────────────────────────────────────────

class PangLevel:
    """Self-contained Pang-style multiplayer level.

    Call ``run()`` to play.  Returns ``"complete"``, ``"dead"``, or
    ``"exit"`` (player pressed ESC).

    Parameters
    ----------
    joystick : pygame.joystick.Joystick or None
        Joystick for P3 (third player).
    joystick2 : pygame.joystick.Joystick or None
        Joystick for P4 (fourth player).
    """

    def __init__(self, screen, width: int, height: int, fps: int,
                 settings, font, acid, sfx,
                 joystick=None, joystick2=None) -> None:
        self.screen    = screen
        self.width     = width
        self.height    = height
        self.fps       = fps
        self.settings  = settings
        self.font      = font
        self.acid      = acid
        self.sfx       = sfx
        # Joysticks for P3 / P4
        self._joys: list = []
        if joystick is not None:
            self._joys.append(joystick)
        if joystick2 is not None:
            self._joys.append(joystick2)

        self._clock = pygame.time.Clock()

        # Arena geometry (computed once)
        self._left_x    = float(_WALL_W)
        self._right_x   = float(width - _WALL_W)
        self._ground_y  = float(height - _GROUND_H)
        self._ceiling_y = float(_CEILING_H)

        # Pre-bake background surface
        self._bg = pygame.Surface((width, height))
        self._bake_background()

        # Fonts
        self._hud_font = pygame.font.SysFont(None, 26, bold=True)
        self._big_font = pygame.font.SysFont(None, 68, bold=True)
        self._med_font = pygame.font.SysFont(None, 42, bold=True)

        # State (populated by _reset)
        self._players:  list[_PangPlayer] = []
        self._objects:  list[_BallObject] = []
        self._shots:    list[_Shot]       = []
        self._split_fx: list              = []   # (x, y, r, timer, color)
        self._frame     = 0

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> str:
        """Play the pang level.  Returns ``"complete"``, ``"dead"``, or
        ``"exit"``."""
        self._reset()
        self._show_title()
        while True:
            self._clock.tick(self.fps)
            result = self._handle_events()
            if result:
                return result

            self._update()
            self._draw()
            pygame.display.flip()
            self._frame += 1

            # All players dead → game over
            if all(not p.alive for p in self._players):
                self._show_overlay("GAME OVER", (230, 60, 60), (100, 0, 0, 170))
                return "dead"

            # All objects cleared → victory
            if not self._objects:
                self._show_overlay("STAGE CLEAR!", (80, 240, 120), (0, 80, 0, 150))
                return "complete"

    # ── Initialisation ────────────────────────────────────────────────────────

    def _reset(self) -> None:
        self._frame    = 0
        self._shots    = []
        self._split_fx = []

        # Spawn up to 4 players
        spawn_xs = [
            self._left_x  + 80,
            self._right_x - 80,
            self._left_x  + 200,
            self._right_x - 200,
        ]
        # Determine actual player count: always P1+P2 (keyboard), plus one per joystick
        num_players = min(4, 2 + len(self._joys))
        self._players = [
            _PangPlayer(i, spawn_xs[i], self._ground_y)
            for i in range(num_players)
        ]

        # Spawn initial bouncing objects
        self._objects = []
        for _ in range(_INITIAL_OBJECTS):
            x  = random.uniform(self._left_x + 80, self._right_x - 80)
            vx = random.choice([-1, 1]) * _OBJ_SPEEDS[0]
            obj = _BallObject(x, self._ceiling_y + _OBJ_RADII[0] + 10,
                              tier=0, vx=vx, vy=0.0)
            self._objects.append(obj)

    def _bake_background(self) -> None:
        """Draw gradient background + static arena geometry into self._bg."""
        surf = self._bg
        w, h = self.width, self.height
        # Gradient
        for y in range(h):
            t = y / h
            r = int(_BG_TOP[0] + (_BG_BOT[0] - _BG_TOP[0]) * t)
            g = int(_BG_TOP[1] + (_BG_BOT[1] - _BG_TOP[1]) * t)
            b = int(_BG_TOP[2] + (_BG_BOT[2] - _BG_TOP[2]) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (w, y))
        # Ceiling
        pygame.draw.rect(surf, _CEILING_COL, (0, 0, w, _CEILING_H))
        pygame.draw.line(surf, _FLOOR_LINE_COL, (0, _CEILING_H), (w, _CEILING_H), 2)
        # Ground
        pygame.draw.rect(surf, _FLOOR_COL, (0, int(self._ground_y), w, _GROUND_H))
        pygame.draw.line(surf, _FLOOR_LINE_COL,
                         (0, int(self._ground_y)), (w, int(self._ground_y)), 2)
        # Left wall
        pygame.draw.rect(surf, _WALL_COL, (0, 0, _WALL_W, h))
        pygame.draw.line(surf, _FLOOR_LINE_COL, (_WALL_W, 0), (_WALL_W, h), 2)
        # Right wall
        pygame.draw.rect(surf, _WALL_COL, (int(self._right_x), 0, _WALL_W, h))
        pygame.draw.line(surf, _FLOOR_LINE_COL,
                         (int(self._right_x), 0), (int(self._right_x), h), 2)

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_events(self) -> str | None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "exit"
        return None

    def _read_player_inputs(self) -> list[tuple[float, bool, bool]]:
        """Return list of (dx, do_jump, do_shoot) for each active player."""
        keys = pygame.key.get_pressed()
        inputs: list[tuple[float, bool, bool]] = []

        # P1 – arrow keys
        dx1 = (1.0 if keys[self.settings.keyboard.get("move_right", pygame.K_RIGHT)] else 0.0) - \
              (1.0 if keys[self.settings.keyboard.get("move_left",  pygame.K_LEFT)]  else 0.0)
        j1  = bool(keys[self.settings.keyboard.get("jump",  pygame.K_SPACE)])
        sh1 = bool(keys[self.settings.keyboard.get("punch", pygame.K_z)])
        inputs.append((dx1, j1, sh1))

        # P2 – WASD / Q/R keys
        if len(self._players) >= 2:
            dx2 = (1.0 if keys[self.settings.keyboard_p2.get("move_right", pygame.K_d)] else 0.0) - \
                  (1.0 if keys[self.settings.keyboard_p2.get("move_left",  pygame.K_a)] else 0.0)
            j2  = bool(keys[self.settings.keyboard_p2.get("jump",  pygame.K_q)])
            sh2 = bool(keys[self.settings.keyboard_p2.get("punch", pygame.K_r)])
            inputs.append((dx2, j2, sh2))

        # P3 / P4 – joystick 0 / 1
        for joy in self._joys:
            if len(inputs) >= len(self._players):
                break
            dx  = 0.0
            jmp = False
            sht = False
            # Left stick / D-pad
            if joy.get_numaxes() >= 1:
                ax = joy.get_axis(0)
                if ax < -AXIS_DEADZONE:
                    dx = -1.0
                elif ax > AXIS_DEADZONE:
                    dx = 1.0
            if joy.get_numhats() > 0:
                hx, _ = joy.get_hat(0)
                if hx != 0:
                    dx = float(hx)
            n_btn = joy.get_numbuttons()
            if n_btn > _BTN_SHOOT and joy.get_button(_BTN_SHOOT):
                sht = True
            if n_btn > _BTN_JUMP  and joy.get_button(_BTN_JUMP):
                jmp = True
            # Also allow Y-axis for jump (stick up)
            if joy.get_numaxes() >= 2:
                ay = joy.get_axis(1)
                if ay < -AXIS_DEADZONE:
                    jmp = True
            inputs.append((dx, jmp, sht))

        return inputs

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self) -> None:
        inputs = self._read_player_inputs()

        # Update players and collect new shots
        for p, (dx, jmp, sht) in zip(self._players, inputs):
            if not p.alive:
                continue
            shot = p.update(dx, jmp, sht, self._left_x, self._right_x)
            if shot:
                self._shots.append(shot)

        # Update shots
        surviving_shots = []
        for s in self._shots:
            s.update()
            if s.y - _SHOT_W < self._ceiling_y:
                s.alive = False   # hit ceiling
            if s.alive:
                surviving_shots.append(s)
        self._shots = surviving_shots

        # Update objects
        for obj in self._objects:
            if obj.alive:
                obj.update(self._ground_y, self._left_x, self._right_x,
                           self._ceiling_y)

        # Shot–object collisions
        new_objects: list[_BallObject] = []
        for obj in self._objects:
            if not obj.alive:
                continue
            hit = False
            for s in self._shots:
                if not s.alive:
                    continue
                if abs(s.x - obj.x) < obj.r + _SHOT_W and abs(s.y - obj.y) < obj.r + _SHOT_W:
                    s.alive = False
                    hit = True
                    break
            if hit:
                obj.alive = False
                self._split_fx.append((obj.x, obj.y, obj.r, 18, _OBJ_COLORS[obj.tier]))
                if obj.tier < len(_OBJ_RADII) - 1:
                    # Split into two smaller objects
                    spd = _OBJ_SPEEDS[obj.tier + 1]
                    for sign in (-1, +1):
                        child = _BallObject(
                            obj.x, obj.y,
                            tier=obj.tier + 1,
                            vx=sign * spd,
                            vy=_OBJ_BOUNCE_VY[obj.tier + 1] * 0.6,
                        )
                        new_objects.append(child)
                # If tier == last, it's destroyed (no children)
            else:
                new_objects.append(obj)

        self._objects = new_objects

        # Object–player collisions
        for obj in self._objects:
            for p in self._players:
                if not p.alive:
                    continue
                if p.invuln > 0:
                    continue
                dx = abs(p.x - obj.x)
                dy = abs(p.y - _P_HEIGHT * 0.5 - obj.y)
                # Treat player as a small rectangle for hit
                if dx < obj.r + _P_RADIUS and dy < obj.r + _P_HEIGHT * 0.5:
                    p.hit()

        # Clean up dead shots / fx
        self._shots    = [s for s in self._shots if s.alive]
        self._split_fx = [(x, y, r, t - 1, c) for x, y, r, t, c in self._split_fx if t > 1]

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.screen.blit(self._bg, (0, 0))
        self._draw_shots()
        self._draw_objects()
        self._draw_players()
        self._draw_split_fx()
        self._draw_hud()

    def _draw_shots(self) -> None:
        for s in self._shots:
            # Vertical beam from shot position to ceiling
            x = int(s.x)
            y_top = int(s.y)
            y_bot = int(s.y + _P_HEIGHT * 0.3)
            if y_bot - y_top < 4:
                y_bot = y_top + 4
            # Glow line (wider, dimmer)
            pygame.draw.line(self.screen, _SHOT_GLOW, (x, y_top), (x, y_bot), 6)
            # Core line
            pygame.draw.line(self.screen, _SHOT_COL, (x, y_top), (x, y_bot), 2)

    def _draw_objects(self) -> None:
        for obj in self._objects:
            pts = _polygon_pts(obj.x, obj.y, obj.r, _OBJ_SIDES[obj.tier], obj.angle)
            pygame.draw.polygon(self.screen, _OBJ_DARK[obj.tier], pts)
            pygame.draw.polygon(self.screen, _OBJ_COLORS[obj.tier], pts, 3)
            # Inner highlight
            inner_r = max(3, int(obj.r * 0.45))
            hi_pts  = _polygon_pts(obj.x - obj.r * 0.18, obj.y - obj.r * 0.18,
                                   inner_r, _OBJ_SIDES[obj.tier], obj.angle + 0.4)
            hi_col  = tuple(min(255, c + 60) for c in _OBJ_COLORS[obj.tier])
            pygame.draw.polygon(self.screen, hi_col, hi_pts, 2)

    def _draw_players(self) -> None:
        for p in self._players:
            if not p.alive:
                continue
            # Blink while invulnerable
            if p.invuln > 0 and (self._frame // 4) % 2 == 0:
                continue
            body_col, head_col, accent = _PLAYER_PALETTES[p.idx]
            cx = int(p.x)
            foot_y = int(p.y)
            head_y = foot_y - _P_HEIGHT

            # Legs
            mid_y = foot_y - int(_P_HEIGHT * 0.35)
            leg_w = 5
            # Left leg
            pygame.draw.line(self.screen, body_col,
                             (cx - 5, mid_y), (cx - 7, foot_y), leg_w)
            # Right leg
            pygame.draw.line(self.screen, body_col,
                             (cx + 5, mid_y), (cx + 7, foot_y), leg_w)

            # Torso
            torso_top = head_y + int(_P_HEIGHT * 0.28)
            pygame.draw.rect(self.screen, body_col,
                             (cx - 8, torso_top, 16, mid_y - torso_top))

            # Arm holding up (shoot side based on facing)
            arm_x_shoot = cx + p.facing * 8
            pygame.draw.line(self.screen, accent,
                             (cx, torso_top + 4),
                             (arm_x_shoot, torso_top - 10), 4)

            # Head
            pygame.draw.circle(self.screen, head_col,
                                (cx, head_y + int(_P_HEIGHT * 0.14)), int(_P_HEIGHT * 0.18))

            # Player label
            lbl = self._hud_font.render(f"P{p.idx + 1}", True, _LABEL_COLORS[p.idx])
            self.screen.blit(lbl, (cx - lbl.get_width() // 2, head_y - 20))

    def _draw_split_fx(self) -> None:
        for x, y, r, t, c in self._split_fx:
            age_ratio = 1.0 - t / 18.0
            cur_r = int(r + r * age_ratio * 1.2)
            alpha = int(255 * (t / 18.0))
            col   = tuple(min(255, int(v * (0.5 + 0.5 * (t / 18.0)))) for v in c)
            pygame.draw.circle(self.screen, col, (int(x), int(y)), cur_r, 3)

    def _draw_hud(self) -> None:
        # Lives per player (top-left area, spaced across)
        for i, p in enumerate(self._players):
            px_base = _WALL_W + 8 + i * 140
            label = self._hud_font.render(f"P{i + 1}", True, _LABEL_COLORS[i])
            self.screen.blit(label, (px_base, 3))
            for li in range(_MAX_LIVES):
                col = _LIFE_COL if li < p.lives else _LIFE_EMPTY_COL
                pygame.draw.circle(self.screen, col,
                                   (px_base + 28 + li * 18, 10), 6)

        # Remaining objects (top-right)
        remaining = len(self._objects)
        obj_label = self._hud_font.render(f"Objects: {remaining}", True, _OBJ_COUNT_COL)
        self.screen.blit(obj_label,
                         (self.width - _WALL_W - obj_label.get_width() - 8, 3))

    # ── Overlays ──────────────────────────────────────────────────────────────

    def _show_title(self) -> None:
        """Flash the level title briefly before gameplay starts."""
        self._draw()
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        title = self._big_font.render("PANG MODE", True, (255, 240, 80))
        sub   = self._med_font.render("Shoot the bouncing objects!", True, (200, 200, 220))
        cx    = self.width // 2
        cy    = self.height // 2
        self.screen.blit(title, (cx - title.get_width() // 2, cy - 50))
        self.screen.blit(sub,   (cx - sub.get_width()   // 2, cy + 20))
        pygame.display.flip()
        pygame.time.wait(1800)

    def _show_overlay(self, message: str, text_col: tuple,
                      bg_rgba: tuple) -> None:
        """Pause and show a full-screen result overlay for ~2 seconds."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill(bg_rgba)
        self.screen.blit(overlay, (0, 0))
        surf = self._big_font.render(message, True, text_col)
        self.screen.blit(surf, (self.width // 2  - surf.get_width() // 2,
                                self.height // 2 - surf.get_height() // 2))
        pygame.display.flip()
        pygame.time.wait(2200)
