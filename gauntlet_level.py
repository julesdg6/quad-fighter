"""gauntlet_level.py

Top-down Gauntlet-style arena combat mode for Quad Fighter.

GauntletLevel.run() returns "complete" | "dead" | "exit".

Gameplay
--------
- Bird's-eye top-down view
- Free 2D movement in all directions (arrow keys or left stick)
- 360° combat: Z = light attack, X = heavy attack
- Attacks hit in a forward arc
- 3 enemy types: basic (slow swarm), fast (pressure), tank (high HP)
- Wave-based spawning across 5 escalating waves
- Simple room with circular pillar obstacles
- Health + wave HUD
"""

import math
import random

import pygame

from settings import AXIS_DEADZONE

# ── Tuning constants ──────────────────────────────────────────────────────────

_PLAYER_SPEED        = 3.5
_PLAYER_MAX_HP       = 100
_PLAYER_INVULN_FRAMES = 24
_PLAYER_RADIUS       = 14

# Light attack
_LIGHT_RANGE         = 56
_LIGHT_ARC           = math.radians(80)
_LIGHT_DAMAGE        = 12
_LIGHT_ANTICIPATION  = 4
_LIGHT_STRIKE        = 5
_LIGHT_RECOVERY      = 8
_LIGHT_COOLDOWN      = 16
_LIGHT_KNOCKBACK     = 60

# Heavy attack
_HEAVY_RANGE         = 68
_HEAVY_ARC           = math.radians(110)
_HEAVY_DAMAGE        = 28
_HEAVY_ANTICIPATION  = 10
_HEAVY_STRIKE        = 6
_HEAVY_RECOVERY      = 14
_HEAVY_COOLDOWN      = 36
_HEAVY_KNOCKBACK     = 130

# ── Enemy type profiles ───────────────────────────────────────────────────────

_ENEMY_TYPES = {
    "basic": {
        "speed":            1.4,
        "max_hp":           30,
        "radius":           13,
        "damage":           8,
        "attack_range":     26,
        "attack_cooldown":  50,
        "attack_wind":      12,
        "knockback_resist": 0.6,
        "color":            (180, 60,  60),
        "dark_color":       (120, 30,  30),
    },
    "fast": {
        "speed":            2.8,
        "max_hp":           18,
        "radius":           11,
        "damage":           6,
        "attack_range":     22,
        "attack_cooldown":  35,
        "attack_wind":      8,
        "knockback_resist": 0.4,
        "color":            (60,  180, 220),
        "dark_color":       (30,  100, 140),
    },
    "tank": {
        "speed":            0.8,
        "max_hp":           80,
        "radius":           18,
        "damage":           15,
        "attack_range":     32,
        "attack_cooldown":  80,
        "attack_wind":      18,
        "knockback_resist": 0.85,
        "color":            (100, 100, 220),
        "dark_color":       (50,  50,  150),
    },
}

# ── Wave definitions ──────────────────────────────────────────────────────────

# Each wave is a list of enemy type strings to spawn.
_WAVES = [
    ["basic",  "basic",  "basic",  "fast"],
    ["basic",  "fast",   "fast",   "basic",  "tank"],
    ["basic",  "fast",   "tank",   "basic",  "fast",  "fast"],
    ["basic",  "tank",   "fast",   "basic",  "tank",  "fast",  "basic"],
    ["fast",   "tank",   "fast",   "tank",   "basic", "fast",  "basic", "tank"],
]

# ── Map constants ─────────────────────────────────────────────────────────────

_ROOM_MARGIN     = 60
_WALL_COLOR      = (80,  80,  100)
_WALL_INNER_COL  = (50,  50,  65)
_FLOOR_COLOR     = (35,  35,  45)
_FLOOR_TILE_COL  = (40,  40,  52)
_TILE_SIZE       = 48
_PILLAR_COLOR    = (90,  90,  110)
_SPAWN_MARGIN    = 30   # min gap from room edge when spawning enemies

# Obstacle positions as (rx, ry, radius) where rx/ry are fractions of room size
_OBSTACLE_DEFS = [
    (0.25, 0.35, 22),
    (0.75, 0.35, 22),
    (0.50, 0.65, 22),
    (0.25, 0.72, 18),
    (0.75, 0.72, 18),
]

# ── HUD constants ─────────────────────────────────────────────────────────────

_HP_BAR_W           = 180
_HP_BAR_H           = 16
_HP_COLOR           = (60,  220, 80)
_HP_BG_COLOR        = (40,  40,  40)
_HUD_TEXT_COLOR     = (220, 220, 220)
_HINT_DISPLAY_FRAMES = 180   # 3 seconds at 60 FPS

# ── Controller button indices (standard Xbox / SDL layout) ────────────────────

_BTN_LIGHT_ATK = 2   # X button
_BTN_HEAVY_ATK = 1   # B button


# ── Data classes ──────────────────────────────────────────────────────────────

class _Obstacle:
    """Circular solid obstacle that blocks movement."""

    def __init__(self, cx: float, cy: float, r: float) -> None:
        self.cx = cx
        self.cy = cy
        self.r  = r


class _Enemy:
    """A single gauntlet-mode enemy."""

    def __init__(self, x: float, y: float, etype: str) -> None:
        cfg = _ENEMY_TYPES[etype]
        self.x     = x
        self.y     = y
        self.etype = etype
        self.speed = cfg["speed"]
        self.hp    = cfg["max_hp"]
        self.max_hp = cfg["max_hp"]
        self.radius = cfg["radius"]
        self.damage = cfg["damage"]
        self.attack_range    = cfg["attack_range"]
        self.attack_cooldown = cfg["attack_cooldown"]
        self.attack_wind     = cfg["attack_wind"]
        self.knockback_resist = cfg["knockback_resist"]
        self.color      = cfg["color"]
        self.dark_color = cfg["dark_color"]
        # Runtime state
        self.alive      = True
        self.vx         = 0.0
        self.vy         = 0.0
        self.facing     = 0.0      # angle (radians) toward player
        self.atk_timer  = 0        # frames until attack lands (wind-up)
        self.atk_cd     = random.randint(0, cfg["attack_cooldown"])
        self.hurt_timer = 0


# ── Main class ────────────────────────────────────────────────────────────────

class GauntletLevel:
    """Self-contained top-down Gauntlet arena level.

    Call ``run()`` to play.  Returns ``"complete"``, ``"dead"``, or
    ``"exit"`` (player pressed ESC).
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
        self._clock   = pygame.time.Clock()

        m = _ROOM_MARGIN
        self._room = pygame.Rect(m, m, width - 2 * m, height - 2 * m)

        # Build obstacle list in world coordinates
        self._obstacles = []
        for rx, ry, r in _OBSTACLE_DEFS:
            cx = self._room.x + int(rx * self._room.width)
            cy = self._room.y + int(ry * self._room.height)
            self._obstacles.append(_Obstacle(cx, cy, r))

        # Fonts for HUD / overlays
        self._hud_font = pygame.font.SysFont(None, 28, bold=True)
        self._big_font = pygame.font.SysFont(None, 64, bold=True)

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> str:
        """Play the gauntlet level.  Returns ``"complete"``, ``"dead"``, or
        ``"exit"``."""
        self._reset()
        while True:
            dt = min(self._clock.tick(self.fps) / 1000.0, 0.05)
            result = self._handle_events()
            if result:
                return result

            self._update()
            self._draw()
            pygame.display.flip()
            self._frame += 1

            if self._player_hp <= 0:
                self._show_overlay("YOU DIED", (230, 60, 60), (100, 0, 0, 180))
                return "dead"

            if not self._enemies:
                if self._wave_idx + 1 >= len(_WAVES):
                    self._show_overlay("ARENA CLEAR!", (80, 240, 120), (0, 80, 0, 160))
                    return "complete"
                self._next_wave()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _reset(self) -> None:
        cx = self._room.centerx
        cy = self._room.centery
        self._px           = float(cx)
        self._py           = float(cy)
        self._player_hp    = _PLAYER_MAX_HP
        self._player_facing = 0.0   # angle in radians (0 = right)
        self._last_dir      = 0.0   # last non-zero movement angle
        self._invuln        = 0
        self._frame         = 0

        # Attack state
        self._atk_timer    = 0
        self._atk_cd       = 0
        self._atk_heavy    = False
        self._atk_phase    = ""     # "anticipation" | "strike" | "recovery" | ""
        self._atk_hit_ids: set = set()

        # Progress
        self._enemies: list[_Enemy] = []
        self._wave_idx  = 0
        self._kills     = 0
        self._wave_banner = 0   # countdown frames for wave announcement

        # Visual effects
        self._hit_flashes: list[tuple] = []   # (x, y, timer, color)

        self._spawn_wave()

    def _spawn_wave(self) -> None:
        types = _WAVES[self._wave_idx]   # caller ensures index is in-bounds
        for etype in types:
            x, y = self._random_spawn()
            self._enemies.append(_Enemy(x, y, etype))
        self._wave_banner = 90

    def _next_wave(self) -> None:
        self._wave_idx += 1
        wave_num = self._wave_idx + 1
        self._show_overlay(f"WAVE {wave_num}!", (240, 200, 60), (60, 60, 0, 150))
        self._spawn_wave()

    def _random_spawn(self) -> tuple[float, float]:
        """Return a spawn position on a random room edge, away from the player."""
        room = self._room
        m = _SPAWN_MARGIN
        for _ in range(24):
            edge = random.randint(0, 3)
            if edge == 0:
                x = random.uniform(room.left + m, room.right - m)
                y = float(room.top + m)
            elif edge == 1:
                x = random.uniform(room.left + m, room.right - m)
                y = float(room.bottom - m)
            elif edge == 2:
                x = float(room.left + m)
                y = random.uniform(room.top + m, room.bottom - m)
            else:
                x = float(room.right - m)
                y = random.uniform(room.top + m, room.bottom - m)
            if math.hypot(x - self._px, y - self._py) > 100:
                return x, y
        return float(room.left + 40), float(room.top + 40)

    # ── Event handling ────────────────────────────────────────────────────────

    def _handle_events(self) -> str | None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "exit"
        return None

    def _read_input(self) -> tuple[float, float, bool, bool]:
        """Return (dx, dy, attack_light, attack_heavy).

        dx/dy are already normalised to length <= 1.
        """
        keys = pygame.key.get_pressed()
        dx, dy = 0.0, 0.0
        if keys[pygame.K_LEFT]:
            dx -= 1.0
        if keys[pygame.K_RIGHT]:
            dx += 1.0
        if keys[pygame.K_UP]:
            dy -= 1.0
        if keys[pygame.K_DOWN]:
            dy += 1.0

        # Normalise diagonal
        mag = math.hypot(dx, dy)
        if mag > 0:
            dx /= mag
            dy /= mag

        # Joystick left-stick movement (override keyboard if beyond deadzone)
        if self.joystick:
            ax = self.joystick.get_axis(0)
            ay = self.joystick.get_axis(1)
            if abs(ax) > AXIS_DEADZONE or abs(ay) > AXIS_DEADZONE:
                jmag = math.hypot(ax, ay)
                dx = ax / max(jmag, 1.0)
                dy = ay / max(jmag, 1.0)

        # Record last movement direction
        if math.hypot(dx, dy) > 0:
            self._last_dir = math.atan2(dy, dx)

        # Attack buttons
        atk_light = bool(keys[pygame.K_z])
        atk_heavy = bool(keys[pygame.K_x])
        if self.joystick and self.joystick.get_numbuttons() > max(_BTN_LIGHT_ATK, _BTN_HEAVY_ATK):
            if self.joystick.get_button(_BTN_LIGHT_ATK):
                atk_light = True
            if self.joystick.get_button(_BTN_HEAVY_ATK):
                atk_heavy = True

        return dx, dy, atk_light, atk_heavy

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self) -> None:
        dx, dy, atk_light, atk_heavy = self._read_input()

        # Move player
        nx = self._px + dx * _PLAYER_SPEED
        ny = self._py + dy * _PLAYER_SPEED
        nx, ny = self._clamp_room(nx, ny, _PLAYER_RADIUS)
        nx, ny = self._push_obstacles(nx, ny, _PLAYER_RADIUS)
        self._px, self._py = nx, ny

        # Update facing toward last movement direction
        if math.hypot(dx, dy) > 0:
            self._player_facing = self._last_dir

        # Attack cooldown tick
        if self._atk_cd > 0:
            self._atk_cd -= 1

        # Attack timer / phase
        if self._atk_timer > 0:
            self._atk_timer -= 1
            if self._atk_heavy:
                total  = _HEAVY_ANTICIPATION + _HEAVY_STRIKE + _HEAVY_RECOVERY
                s_start = _HEAVY_ANTICIPATION
                s_end   = _HEAVY_ANTICIPATION + _HEAVY_STRIKE
            else:
                total  = _LIGHT_ANTICIPATION + _LIGHT_STRIKE + _LIGHT_RECOVERY
                s_start = _LIGHT_ANTICIPATION
                s_end   = _LIGHT_ANTICIPATION + _LIGHT_STRIKE

            elapsed = total - self._atk_timer
            if elapsed < s_start:
                self._atk_phase = "anticipation"
            elif elapsed < s_end:
                self._atk_phase = "strike"
                self._apply_hits()
            else:
                self._atk_phase = "recovery"

            if self._atk_timer == 0:
                self._atk_phase = ""

        elif self._atk_cd == 0:
            if atk_heavy:
                self._start_attack(heavy=True)
            elif atk_light:
                self._start_attack(heavy=False)

        # Invulnerability countdown
        if self._invuln > 0:
            self._invuln -= 1

        # Update enemies
        surviving = []
        for e in self._enemies:
            if e.alive:
                self._update_enemy(e)
                surviving.append(e)
        self._enemies = surviving

        # Hit flash decay
        self._hit_flashes = [(x, y, t - 1, c)
                             for x, y, t, c in self._hit_flashes if t > 1]

        # Wave banner countdown
        if self._wave_banner > 0:
            self._wave_banner -= 1

    def _start_attack(self, heavy: bool) -> None:
        self._atk_heavy = heavy
        if heavy:
            self._atk_timer = _HEAVY_ANTICIPATION + _HEAVY_STRIKE + _HEAVY_RECOVERY
            self._atk_cd    = _HEAVY_COOLDOWN
        else:
            self._atk_timer = _LIGHT_ANTICIPATION + _LIGHT_STRIKE + _LIGHT_RECOVERY
            self._atk_cd    = _LIGHT_COOLDOWN
        self._atk_phase   = "anticipation"
        self._atk_hit_ids = set()

    def _apply_hits(self) -> None:
        """Damage all enemies inside the current attack arc (once per swing)."""
        if self._atk_heavy:
            atk_range = _HEAVY_RANGE
            arc       = _HEAVY_ARC
            damage    = _HEAVY_DAMAGE
            knockback = _HEAVY_KNOCKBACK
        else:
            atk_range = _LIGHT_RANGE
            arc       = _LIGHT_ARC
            damage    = _LIGHT_DAMAGE
            knockback = _LIGHT_KNOCKBACK

        angle = self._player_facing
        half_arc = arc * 0.5

        for e in self._enemies:
            if id(e) in self._atk_hit_ids:
                continue
            ex = e.x - self._px
            ey = e.y - self._py
            dist = math.hypot(ex, ey)

            # Range check (include enemy radius)
            if dist > atk_range + e.radius:
                continue

            # Arc check: normalise angle difference to [0, π] then compare half-arc
            if dist < 0.001:
                in_arc = True
            else:
                ea   = math.atan2(ey, ex)
                # Wrap (ea - angle) into [-π, π] to get the shortest angular distance
                diff = abs(((ea - angle + math.pi) % (2 * math.pi)) - math.pi)
                in_arc = diff <= half_arc

            if not in_arc:
                continue

            self._atk_hit_ids.add(id(e))
            e.hp -= damage
            e.hurt_timer = 10

            if e.hp <= 0:
                e.alive = False
                self._kills += 1
            else:
                # Apply knockback velocity
                if dist > 0.001:
                    kbx = (ex / dist) * knockback * (1.0 - e.knockback_resist)
                    kby = (ey / dist) * knockback * (1.0 - e.knockback_resist)
                else:
                    kbx, kby = knockback * (1.0 - e.knockback_resist), 0.0
                e.vx += kbx
                e.vy += kby

            self._hit_flashes.append((e.x, e.y, 8, (255, 220, 60)))

            try:
                self.sfx.play("enemy_hurt")
            except pygame.error:
                pass

    def _update_enemy(self, e: _Enemy) -> None:
        pdx = self._px - e.x
        pdy = self._py - e.y
        dist = math.hypot(pdx, pdy)
        if dist > 0.001:
            e.facing = math.atan2(pdy, pdx)

        # Decay knockback velocity
        e.vx *= 0.75
        e.vy *= 0.75
        if abs(e.vx) < 0.1:
            e.vx = 0.0
        if abs(e.vy) < 0.1:
            e.vy = 0.0

        # Chase or stay in attack range
        engage_dist = e.attack_range + _PLAYER_RADIUS
        if dist > engage_dist:
            e.x += (pdx / dist) * e.speed + e.vx
            e.y += (pdy / dist) * e.speed + e.vy
        else:
            e.x += e.vx
            e.y += e.vy

        # Confine to room + push out of obstacles
        e.x, e.y = self._clamp_room(e.x, e.y, e.radius)
        e.x, e.y = self._push_obstacles(e.x, e.y, e.radius)

        # Hurt timer
        if e.hurt_timer > 0:
            e.hurt_timer -= 1

        # Attack logic
        if e.atk_cd > 0:
            e.atk_cd -= 1

        if e.atk_timer > 0:
            e.atk_timer -= 1
            if e.atk_timer == 0:
                # Strike resolves: check still in range and player is hittable
                check = math.hypot(self._px - e.x, self._py - e.y)
                if check <= engage_dist and self._invuln == 0:
                    self._player_hp -= e.damage
                    self._invuln = _PLAYER_INVULN_FRAMES
                    self._hit_flashes.append((self._px, self._py, 12, (255, 80, 80)))
                    try:
                        self.sfx.play("player_hurt")
                    except pygame.error:
                        pass
        elif e.atk_cd == 0 and dist <= engage_dist:
            e.atk_timer = e.attack_wind
            e.atk_cd    = e.attack_cooldown

    # ── Collision helpers ─────────────────────────────────────────────────────

    def _clamp_room(self, x: float, y: float, r: float) -> tuple[float, float]:
        room = self._room
        x = max(room.left  + r, min(room.right  - r, x))
        y = max(room.top   + r, min(room.bottom - r, y))
        return x, y

    def _push_obstacles(self, x: float, y: float, r: float) -> tuple[float, float]:
        for obs in self._obstacles:
            dx = x - obs.cx
            dy = y - obs.cy
            dist = math.hypot(dx, dy)
            min_d = r + obs.r
            if 0 < dist < min_d:
                x = obs.cx + (dx / dist) * min_d
                y = obs.cy + (dy / dist) * min_d
        return x, y

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.screen.fill(_FLOOR_COLOR)
        self._draw_floor_tiles()
        self._draw_walls()
        self._draw_obstacles()
        self._draw_enemies()
        self._draw_attack_arc()
        self._draw_player()
        self._draw_hit_flashes()
        self._draw_hud()
        if self._wave_banner > 0:
            self._draw_wave_banner()

    def _draw_floor_tiles(self) -> None:
        room = self._room
        for tx in range(room.left, room.right, _TILE_SIZE):
            for ty in range(room.top, room.bottom, _TILE_SIZE):
                if (tx // _TILE_SIZE + ty // _TILE_SIZE) % 2 == 0:
                    w = min(_TILE_SIZE, room.right  - tx)
                    h = min(_TILE_SIZE, room.bottom - ty)
                    pygame.draw.rect(self.screen, _FLOOR_TILE_COL, (tx, ty, w, h))

    def _draw_walls(self) -> None:
        room = self._room
        # Fill four wall borders
        pygame.draw.rect(self.screen, _WALL_COLOR,
                         (0, 0, self.width, room.top))
        pygame.draw.rect(self.screen, _WALL_COLOR,
                         (0, room.bottom, self.width, self.height - room.bottom))
        pygame.draw.rect(self.screen, _WALL_COLOR,
                         (0, room.top, room.left, room.height))
        pygame.draw.rect(self.screen, _WALL_COLOR,
                         (room.right, room.top, self.width - room.right, room.height))
        # Inner edge highlight
        pygame.draw.rect(self.screen, _WALL_INNER_COL, room, 4)

    def _draw_obstacles(self) -> None:
        for obs in self._obstacles:
            ox, oy, r = int(obs.cx), int(obs.cy), int(obs.r)
            # Drop shadow
            pygame.draw.ellipse(self.screen, (20, 20, 25),
                                (ox - r - 2, oy + r // 2, (r + 2) * 2, r // 2 + 4))
            # Pillar body
            pygame.draw.circle(self.screen, _PILLAR_COLOR, (ox, oy), r)
            pygame.draw.circle(self.screen, (110, 110, 130), (ox, oy), r, 2)
            # Top-light highlight
            hl_x = ox - r // 4
            hl_y = oy - r // 4
            pygame.draw.circle(self.screen, (130, 130, 150), (hl_x, hl_y), max(2, r // 3))

    def _draw_enemies(self) -> None:
        for e in self._enemies:
            self._draw_enemy(e)

    def _draw_enemy(self, e: _Enemy) -> None:
        ix, iy = int(e.x), int(e.y)
        r = e.radius
        color = e.color
        dark  = e.dark_color

        # Hurt flash: tint toward white
        if e.hurt_timer > 0:
            blend = min(1.0, e.hurt_timer / 6.0)
            color = tuple(int(color[i] + (255 - color[i]) * blend * 0.8)
                          for i in range(3))

        # Drop shadow
        pygame.draw.ellipse(self.screen, (20, 20, 25),
                            (ix - r, iy + r - 4, r * 2, r // 2 + 3))
        # Body
        pygame.draw.circle(self.screen, color, (ix, iy), r)
        pygame.draw.circle(self.screen, dark,  (ix, iy), r, 2)

        # Facing dot
        fa    = e.facing
        dot_x = int(ix + math.cos(fa) * (r - 4))
        dot_y = int(iy + math.sin(fa) * (r - 4))
        pygame.draw.circle(self.screen, dark, (dot_x, dot_y), max(3, r // 4))

        # Attack wind-up ring
        if e.atk_timer > 0:
            pygame.draw.circle(self.screen, (255, 160, 40), (ix, iy), r + 3, 2)

        # HP pip bar (only when damaged)
        if e.hp < e.max_hp:
            bw, bh = r * 2, 4
            bx, by = ix - r, iy - r - 9
            pygame.draw.rect(self.screen, (40, 40, 40),    (bx, by, bw, bh))
            filled = max(0, int(bw * e.hp / e.max_hp))
            pygame.draw.rect(self.screen, (220, 60,  60),  (bx, by, filled, bh))

    def _draw_attack_arc(self) -> None:
        if self._atk_phase not in ("anticipation", "strike"):
            return

        angle = self._player_facing
        if self._atk_heavy:
            atk_range = _HEAVY_RANGE
            arc       = _HEAVY_ARC
            if self._atk_phase == "strike":
                color = (255, 200, 60, 160)
            else:
                color = (240, 140, 40, 80)
        else:
            atk_range = _LIGHT_RANGE
            arc       = _LIGHT_ARC
            if self._atk_phase == "strike":
                color = (255, 240, 80, 140)
            else:
                color = (200, 220, 60, 60)

        pts   = [(int(self._px), int(self._py))]
        steps = 14
        for i in range(steps + 1):
            a = angle - arc * 0.5 + arc * i / steps
            pts.append((
                int(self._px + math.cos(a) * atk_range),
                int(self._py + math.sin(a) * atk_range),
            ))

        arc_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.polygon(arc_surf, color, pts)
        self.screen.blit(arc_surf, (0, 0))

    def _draw_player(self) -> None:
        ix, iy = int(self._px), int(self._py)
        r = _PLAYER_RADIUS

        # Flicker when invulnerable
        if self._invuln > 0 and (self._frame // 3) % 2 == 0:
            return

        # Drop shadow
        pygame.draw.ellipse(self.screen, (20, 20, 25),
                            (ix - r, iy + r - 3, r * 2, r // 2 + 2))

        body_color = (80,  160, 255)
        dark_color = (40,  80,  160)

        # Body circle
        pygame.draw.circle(self.screen, body_color, (ix, iy), r)
        pygame.draw.circle(self.screen, dark_color, (ix, iy), r, 2)

        # Facing indicator (bright nose)
        fa     = self._player_facing
        nose_x = int(ix + math.cos(fa) * (r - 2))
        nose_y = int(iy + math.sin(fa) * (r - 2))
        pygame.draw.circle(self.screen, (200, 240, 255), (nose_x, nose_y),
                           max(3, r // 4))

        # Arms
        arm_len = r + 7
        for side in (-1, 1):
            aa   = fa + side * math.radians(50)
            ax   = int(ix + math.cos(aa) * arm_len)
            ay   = int(iy + math.sin(aa) * arm_len)
            pygame.draw.line(self.screen, dark_color, (ix, iy), (ax, ay), 3)
            pygame.draw.circle(self.screen, (160, 200, 255), (ax, ay), 3)

    def _draw_hit_flashes(self) -> None:
        for x, y, t, color in self._hit_flashes:
            r     = max(4, int(8 + (8 - t) * 1.5))
            alpha = min(255, t * 30)
            surf  = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*color, alpha), (r, r), r)
            self.screen.blit(surf, (int(x) - r, int(y) - r))

    def _draw_hud(self) -> None:
        # Health bar
        hx, hy = 20, 12
        pygame.draw.rect(self.screen, _HP_BG_COLOR,
                         (hx, hy, _HP_BAR_W, _HP_BAR_H))
        filled = max(0, int(_HP_BAR_W * self._player_hp / _PLAYER_MAX_HP))
        pygame.draw.rect(self.screen, _HP_COLOR,
                         (hx, hy, filled, _HP_BAR_H))
        pygame.draw.rect(self.screen, (180, 180, 180),
                         (hx, hy, _HP_BAR_W, _HP_BAR_H), 1)
        hp_lbl = self._hud_font.render("HP", True, _HUD_TEXT_COLOR)
        self.screen.blit(hp_lbl, (hx + _HP_BAR_W + 6, hy - 1))

        # Wave / kills (top-right)
        wave_num = self._wave_idx + 1
        total    = len(_WAVES)
        wave_txt = self._hud_font.render(
            f"Wave {wave_num}/{total}  Kills: {self._kills}",
            True, _HUD_TEXT_COLOR)
        self.screen.blit(wave_txt,
                         (self.width - wave_txt.get_width() - 14, 12))

        # Enemy counter (top-centre)
        alive = len(self._enemies)
        if alive > 0:
            ec = self._hud_font.render(f"Enemies: {alive}", True, (220, 160, 60))
            self.screen.blit(ec,
                             (self.width // 2 - ec.get_width() // 2, 12))

        # Controls hint during first few seconds
        if self._frame < _HINT_DISPLAY_FRAMES:
            hint = "Arrows: Move   Z: Light Attack   X: Heavy Attack   ESC: Exit"
            hs   = self._hud_font.render(hint, True, (140, 140, 160))
            self.screen.blit(hs,
                             (self.width // 2 - hs.get_width() // 2,
                              self.height - 24))

    def _draw_wave_banner(self) -> None:
        alpha = min(255, self._wave_banner * 4)
        wave_num = self._wave_idx + 1
        txt  = f"WAVE {wave_num}"
        surf = self._big_font.render(txt, True, (255, 230, 60))
        surf.set_alpha(alpha)
        self.screen.blit(surf, (
            self.width  // 2 - surf.get_width()  // 2,
            self.height // 2 - surf.get_height() // 2,
        ))

    # ── End-of-level overlay ──────────────────────────────────────────────────

    def _show_overlay(self, message: str, text_color: tuple,
                      bg_rgba: tuple) -> None:
        """Freeze-frame overlay shown for ~2 seconds.  ESC / Enter skips."""
        for _ in range(120):
            self._clock.tick(self.fps)
            self._draw()
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill(bg_rgba)
            self.screen.blit(overlay, (0, 0))
            txt  = self._big_font.render(message, True, text_color)
            sub  = self._hud_font.render("Press ESC or wait ...",
                                         True, (200, 200, 200))
            self.screen.blit(txt, (
                self.width  // 2 - txt.get_width()  // 2,
                self.height // 2 - txt.get_height() // 2,
            ))
            self.screen.blit(sub, (
                self.width  // 2 - sub.get_width()  // 2,
                self.height // 2 + txt.get_height() // 2 + 8,
            ))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit
                if event.type == pygame.KEYDOWN and event.key in (
                        pygame.K_ESCAPE, pygame.K_RETURN):
                    return
