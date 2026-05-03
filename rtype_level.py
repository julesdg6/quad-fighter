"""rtype_level.py

R-Type-style side-scrolling shoot-em-up mode for Quad Fighter.

Features
--------
* 1–4 local players (P1: keyboard, P2: keyboard_p2, P3/P4: gamepads)
* Polygon spacecraft with unique colours
* Rapid-fire (Z) and charge shot (hold X, release to fire)
* Force pod satellite that follows the player's ship
* Horizontally scrolling level with parallax starfield background
* Five enemy types: drone, sine-wave flyer, turret, kamikaze, armoured
* Data-driven wave spawner
* Asteroid / station terrain that damages on contact
* Power-up drops (speed, spread, shield, health, laser)
* Boss fight at end of level (multi-part polygon cruiser)
* Compact 4-player HUD with per-player HP, charge meters and score

RTypeLevel.run() returns "complete" | "dead" | "exit".
"""

from __future__ import annotations

import math
import random

import pygame

from base_level import BaseLevel
from settings import AXIS_DEADZONE

# ── Display constants ─────────────────────────────────────────────────────────

_SCROLL_SPEED      = 1.8    # world pixels per frame auto-scroll
_LEVEL_LENGTH      = 12000  # total world width before boss

# ── Player tuning ─────────────────────────────────────────────────────────────

_P_SPEED           = 3.6
_P_MAX_HP          = 100
_P_INVULN_FRAMES   = 60
_P_RAPID_CD        = 7      # frames between rapid-fire shots
_P_CHARGE_MAX      = 120    # frames to reach full charge
_P_CHARGE_MIN      = 30     # minimum hold for any charge effect
_P_BULLET_SPEED    = 9.0
_P_CHARGE_SPEED    = 6.5
_P_CHARGE_DMGBASE  = 15     # damage multiplier base for charge
_P_RADIUS          = 14     # collision radius

# Force-pod tuning
_POD_OFFSET_X      = 32     # horizontal distance behind the ship
_POD_BULLET_CD     = 18
_POD_BULLET_SPD    = 7.0

# ── Enemy tuning ──────────────────────────────────────────────────────────────

_ENEMY_BULLET_SPD  = 5.0
_ENEMY_BULLET_DMG  = 10

_ENEMY_TYPES: dict[str, dict] = {
    "drone": {
        "hp": 20, "speed": 2.0, "radius": 13, "damage": 15, "score": 100,
        "fire_cd": 90, "color": (60, 200, 200), "dark": (30, 120, 120),
        "sides": 4,
    },
    "sine": {
        "hp": 18, "speed": 2.5, "radius": 12, "damage": 15, "score": 120,
        "fire_cd": 0, "color": (200, 200, 60), "dark": (120, 120, 30),
        "sides": 3,
    },
    "turret": {
        "hp": 40, "speed": 0.0, "radius": 16, "damage": 12, "score": 150,
        "fire_cd": 60, "color": (160, 60, 60), "dark": (100, 30, 30),
        "sides": 6,
    },
    "kamikaze": {
        "hp": 12, "speed": 4.5, "radius": 10, "damage": 25, "score": 80,
        "fire_cd": 0, "color": (220, 100, 40), "dark": (140, 50, 20),
        "sides": 3,
    },
    "armoured": {
        "hp": 80, "speed": 1.2, "radius": 20, "damage": 20, "score": 200,
        "fire_cd": 70, "color": (120, 120, 200), "dark": (60, 60, 140),
        "sides": 5,
    },
}

# ── Power-up types ────────────────────────────────────────────────────────────

_POWERUP_TYPES = ["speed", "spread", "laser", "shield", "health"]
_POWERUP_COLORS = {
    "speed":  (80,  255, 180),
    "spread": (255, 200, 80),
    "laser":  (80,  180, 255),
    "shield": (80,  80,  255),
    "health": (80,  220, 80),
}
_POWERUP_DURATION  = 600    # frames that timed power-ups last
_POWERUP_DRIFT_SPD = 1.2    # leftward drift speed
_POWERUP_RADIUS    = 12     # visual and collision radius of power-up capsule
_ENEMY_RECOIL_DMG  = 5      # damage applied to enemy on player contact

# ── Boss tuning ───────────────────────────────────────────────────────────────

_BOSS_HP           = 600
_BOSS_PHASE2_HP    = 300
_BOSS_SPEED        = 1.0
_BOSS_RADIUS       = 55
_BOSS_CORE_RADIUS  = 22
_BOSS_CORE_FUZZ    = 4      # extra collision tolerance for boss core hits
_BOSS_FIRE_CD      = 45

# ── Terrain ───────────────────────────────────────────────────────────────────

_TERRAIN_DAMAGE    = 25     # damage on collision with obstacle
_TERRAIN_COLS      = [(90, 90, 100), (70, 80, 90), (100, 90, 80)]

# ── Player colours ────────────────────────────────────────────────────────────

_SHIP_COLORS = [
    (80,  180, 255),   # P1 cyan-blue
    (255, 100, 80),    # P2 red-orange
    (80,  255, 140),   # P3 green
    (220, 100, 255),   # P4 purple
]
_SHIP_DARK = [
    (40,  90,  160),
    (160, 50,  40),
    (40,  160, 80),
    (130, 50,  180),
]
_SHIP_LABELS = ["P1", "P2", "P3", "P4"]

# ── HUD colours ───────────────────────────────────────────────────────────────

_HUD_BG        = (0, 0, 0, 160)
_HP_COL        = (60,  220, 80)
_HP_LOW_COL    = (220, 60,  60)
_HP_BG_COL     = (40,  40,  40)
_CHARGE_COL    = (80,  200, 255)
_CHARGE_FULL   = (255, 220, 80)
_SCORE_COL     = (220, 220, 220)
_BOSS_BAR_COL  = (220, 60,  60)
_BOSS_BAR_BG   = (60,  20,  20)

# ── Background parallax layers ────────────────────────────────────────────────

_BG_STAR_COUNT  = 200
_PLANET_SEED    = 42

# ── Button mappings ───────────────────────────────────────────────────────────

_BTN_FIRE   = 0   # A  – rapid fire
_BTN_CHARGE = 1   # B  – charge shot (hold+release)


# ═══════════════════════════════════════════════════════════════════════════════
# Helper draw functions
# ═══════════════════════════════════════════════════════════════════════════════

def _poly(pts: list[tuple[int, int]], color: tuple, surf: pygame.Surface,
          width: int = 0) -> None:
    if len(pts) >= 3:
        pygame.draw.polygon(surf, color, pts, width)


def _ship_pts(cx: float, cy: float, r: float,
              facing: float = 1.0) -> list[tuple[int, int]]:
    """Return polygon vertices for a small arrowhead ship."""
    tip_x  = cx + facing * r * 1.1
    tip_y  = cy
    back_x = cx - facing * r * 0.8
    wl_x   = cx - facing * r * 0.3
    return [
        (int(tip_x), int(tip_y)),
        (int(wl_x), int(cy - r * 0.75)),
        (int(back_x), int(cy - r * 0.45)),
        (int(back_x), int(cy + r * 0.45)),
        (int(wl_x), int(cy + r * 0.75)),
    ]


def _draw_ship(surf: pygame.Surface, cx: float, cy: float, r: float,
               color: tuple, dark: tuple, facing: float = 1.0,
               hurt: bool = False, shield: bool = False) -> None:
    """Draw a polygon ship at (cx, cy)."""
    if hurt:
        color = (255, 255, 255)
        dark  = (200, 200, 200)

    pts = _ship_pts(cx, cy, r, facing)
    _poly(pts, dark, surf)
    _poly(pts, color, surf, 2)

    # Cockpit dome
    pygame.draw.circle(surf, (200, 240, 255),
                       (int(cx + facing * r * 0.2), int(cy)), max(1, int(r * 0.32)))

    # Engine glow
    glow_x = int(cx - facing * r * 0.7)
    glow_r = max(2, int(r * 0.28))
    pygame.draw.circle(surf, (255, 180, 80), (glow_x, int(cy)), glow_r)

    # Shield ring
    if shield:
        pygame.draw.circle(surf, (80, 180, 255),
                           (int(cx), int(cy)), int(r * 1.4), 2)


def _draw_enemy_ship(surf: pygame.Surface, cx: float, cy: float, r: float,
                     color: tuple, dark: tuple, sides: int,
                     angle: float = 0.0, hurt: bool = False) -> None:
    """Draw a polygon enemy at (cx, cy)."""
    if hurt:
        color = (255, 255, 255)
    pts = []
    for i in range(sides):
        a = angle + i * math.tau / sides
        pts.append((int(cx + r * math.cos(a)), int(cy + r * math.sin(a))))
    _poly(pts, dark, surf)
    _poly(pts, color, surf, 2)


def _draw_boss(surf: pygame.Surface, cx: float, cy: float,
               frame: int, hp: float, max_hp: float,
               hurt: bool = False) -> None:
    """Draw the large boss cruiser."""
    f = frame * 0.04
    base_col  = (180, 60, 60)  if not hurt else (255, 255, 255)
    dark_col  = (100, 30, 30)
    arm_col   = (200, 80, 40)  if not hurt else (255, 200, 200)

    # Main hull – large hexagon
    hull_pts = []
    for i in range(6):
        a = f * 0.2 + i * math.tau / 6
        hull_pts.append((int(cx + _BOSS_RADIUS * math.cos(a)),
                         int(cy + _BOSS_RADIUS * math.sin(a))))
    _poly(hull_pts, dark_col, surf)
    _poly(hull_pts, base_col, surf, 3)

    # Rotating cannon arms
    for arm_i in range(3):
        arm_a = f + arm_i * math.tau / 3
        arm_len = _BOSS_RADIUS * 1.3
        ax = cx + math.cos(arm_a) * arm_len
        ay = cy + math.sin(arm_a) * arm_len
        pygame.draw.line(surf, arm_col,
                         (int(cx), int(cy)), (int(ax), int(ay)), 3)
        pygame.draw.circle(surf, arm_col, (int(ax), int(ay)), 7)

    # Weak point core
    frac = hp / max_hp
    core_col = (
        int(60 + (1 - frac) * 200),
        int(200 * frac),
        80,
    )
    pygame.draw.circle(surf, core_col,
                       (int(cx), int(cy)), _BOSS_CORE_RADIUS)
    pygame.draw.circle(surf, (255, 255, 255),
                       (int(cx), int(cy)), _BOSS_CORE_RADIUS, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════════

class _Projectile:
    """A single bullet or charged beam."""

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 owner: int,          # player index, -1 = enemy
                 damage: int,
                 radius: float = 4.0,
                 color: tuple = (255, 255, 160),
                 is_charge: bool = False,
                 pierce: bool = False) -> None:
        self.x, self.y   = x, y
        self.vx, self.vy = vx, vy
        self.owner       = owner
        self.damage      = damage
        self.radius      = radius
        self.color       = color
        self.alive       = True
        self.is_charge   = is_charge
        self.pierce      = pierce   # charged laser passes through enemies

    def update(self, scroll_dx: float) -> None:
        self.x += self.vx - scroll_dx
        self.y += self.vy


class _ForcePod:
    """Detachable satellite pod that follows the player and fires small shots."""

    def __init__(self, owner_idx: int) -> None:
        self.owner_idx = owner_idx
        self.x = 0.0
        self.y = 0.0
        self.fire_cd   = 0
        self.attached  = True   # follows behind ship when True

    def update(self, ship_x: float, ship_y: float, facing: float) -> None:
        # Lerp toward behind-the-ship position
        target_x = ship_x - facing * _POD_OFFSET_X
        target_y = ship_y
        self.x += (target_x - self.x) * 0.25
        self.y += (target_y - self.y) * 0.25
        if self.fire_cd > 0:
            self.fire_cd -= 1

    def try_fire(self, facing: float) -> "_Projectile | None":
        if self.fire_cd > 0:
            return None
        self.fire_cd = _POD_BULLET_CD
        return _Projectile(
            self.x, self.y,
            facing * _POD_BULLET_SPD, 0.0,
            self.owner_idx, 8,
            radius=3.0,
            color=(180, 255, 180),
        )


class _PlayerShip:
    """One player's ship in R-Type mode."""

    def __init__(self, x: float, y: float, p_index: int,
                 joystick=None) -> None:
        self.x, self.y   = float(x), float(y)
        self.p_index     = p_index
        self.joystick    = joystick
        self.hp          = _P_MAX_HP
        self.max_hp      = _P_MAX_HP
        self.invuln      = 0
        self.alive       = True
        self.score       = 0
        self.facing      = 1.0     # always face right in a shmup

        # Weapons
        self.fire_cd     = 0
        self.charge_held = 0       # frames charge button held (0 = not held)
        self.charging    = False

        # Power-up states
        self.speed_boost = 0       # remaining frames
        self.spread_shot = 0
        self.laser_shot  = 0
        self.shield      = 0

        # Force pod
        self.pod = _ForcePod(p_index)
        self.pod.x = x - _POD_OFFSET_X
        self.pod.y = y

        # Visual
        self.hurt_timer  = 0
        self.color       = _SHIP_COLORS[p_index % 4]
        self.dark        = _SHIP_DARK[p_index % 4]
        self.label       = _SHIP_LABELS[p_index % 4]
        self.radius      = _P_RADIUS

    @property
    def speed(self) -> float:
        return _P_SPEED * (1.5 if self.speed_boost > 0 else 1.0)

    def tick_powerups(self) -> None:
        for attr in ("speed_boost", "spread_shot", "laser_shot", "shield"):
            v = getattr(self, attr)
            if v > 0:
                setattr(self, attr, v - 1)

    def damage(self, dmg: int) -> bool:
        """Apply damage.  Returns True if player just died."""
        if self.invuln > 0 or self.shield > 0:
            return False
        self.hp -= dmg
        self.hurt_timer = 12
        self.invuln = _P_INVULN_FRAMES
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
            return True
        return False

    def apply_powerup(self, kind: str) -> None:
        if kind == "speed":
            self.speed_boost = _POWERUP_DURATION
        elif kind == "spread":
            self.spread_shot = _POWERUP_DURATION
        elif kind == "laser":
            self.laser_shot  = _POWERUP_DURATION
        elif kind == "shield":
            self.shield      = _POWERUP_DURATION
        elif kind == "health":
            self.hp = min(self.max_hp, self.hp + 40)


class _EnemyShip:
    """One enemy in R-Type mode."""

    _id_counter = 0

    def __init__(self, x: float, y: float, etype: str,
                 wave_dx: float = 0.0, wave_dy: float = 0.0) -> None:
        _EnemyShip._id_counter += 1
        self.eid     = _EnemyShip._id_counter
        self.x, self.y = float(x), float(y)
        self.etype   = etype
        cfg          = _ENEMY_TYPES[etype]
        self.hp      = cfg["hp"]
        self.max_hp  = cfg["hp"]
        self.speed   = cfg["speed"]
        self.radius  = cfg["radius"]
        self.contact_dmg = cfg["damage"]
        self.score   = cfg["score"]
        self.fire_cd = cfg["fire_cd"] + random.randint(0, 30)
        self.color   = cfg["color"]
        self.dark    = cfg["dark"]
        self.sides   = cfg["sides"]
        self.alive   = True
        self.angle   = random.uniform(0, math.tau)
        self.hurt_timer = 0

        # Sine-wave specific
        self.t           = random.uniform(0, math.tau)
        self.wave_amp    = wave_dy if wave_dy != 0 else 0.0
        self.wave_freq   = 0.05

        # Formation offset (used by wave spawner)
        self.form_dx = wave_dx
        self.form_dy = wave_dy

    def update(self, scroll_dx: float, target_x: float = 0.0,
               target_y: float = 0.0) -> None:
        self.angle += 0.06
        self.x     -= scroll_dx
        if self.hurt_timer > 0:
            self.hurt_timer -= 1
        if self.fire_cd > 0:
            self.fire_cd -= 1

        etype = self.etype
        if etype == "drone":
            self.x -= self.speed
        elif etype == "sine":
            self.t += self.wave_freq
            self.x -= self.speed
            self.y += math.sin(self.t) * 2.0
        elif etype == "turret":
            pass   # stationary; rotate only
        elif etype == "kamikaze":
            # Rush toward nearest player
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.hypot(dx, dy) or 1.0
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed
        elif etype == "armoured":
            self.x -= self.speed

    def try_fire(self, target_x: float, target_y: float,
                 screen_w: float) -> "_Projectile | None":
        """Return an enemy bullet aimed at the given target, or None."""
        if self.fire_cd > 0 or self.etype in ("sine", "kamikaze"):
            return None
        if self.x > screen_w + 100 or self.x < -200:
            return None
        self.fire_cd = _ENEMY_TYPES[self.etype]["fire_cd"]
        dx = target_x - self.x
        dy = target_y - self.y
        dist = math.hypot(dx, dy) or 1.0
        vx = (dx / dist) * _ENEMY_BULLET_SPD
        vy = (dy / dist) * _ENEMY_BULLET_SPD
        return _Projectile(
            self.x, self.y, vx, vy,
            -1, _ENEMY_BULLET_DMG,
            radius=4.0, color=(255, 80, 80),
        )

    def hit(self, dmg: int) -> bool:
        """Apply damage; returns True if destroyed."""
        self.hp -= dmg
        self.hurt_timer = 8
        if self.hp <= 0:
            self.alive = False
            return True
        return False


class _PowerUp:
    """A drifting power-up capsule."""

    def __init__(self, x: float, y: float, kind: str) -> None:
        self.x, self.y = float(x), float(y)
        self.kind      = kind
        self.alive     = True
        self.bob       = random.uniform(0, math.tau)

    def update(self, scroll_dx: float) -> None:
        self.x    -= _POWERUP_DRIFT_SPD + scroll_dx
        self.bob  += 0.07

    def draw(self, surf: pygame.Surface) -> None:
        cx = int(self.x)
        cy = int(self.y + math.sin(self.bob) * 5)
        col = _POWERUP_COLORS.get(self.kind, (255, 255, 255))
        pygame.draw.circle(surf, col, (cx, cy), _POWERUP_RADIUS)
        pygame.draw.circle(surf, (255, 255, 255), (cx, cy), _POWERUP_RADIUS, 2)
        # Letter label
        lbl = self.kind[0].upper()
        try:
            font = pygame.font.SysFont(None, 20, bold=True)
            s = font.render(lbl, True, (0, 0, 0))
            surf.blit(s, (cx - s.get_width() // 2, cy - s.get_height() // 2))
        except Exception:
            pass


class _TerrainSegment:
    """A static polygon obstacle that scrolls with the level."""

    def __init__(self, world_x: float, y: float, w: float, h: float,
                 shape: str = "rect") -> None:
        self.world_x = world_x
        self.y       = y
        self.w       = w
        self.h       = h
        self.shape   = shape   # "rect" | "asteroid"
        self.color   = random.choice(_TERRAIN_COLS)
        self.angle   = random.uniform(0, math.tau)
        self.spin    = random.uniform(-0.02, 0.02)

    @property
    def screen_x(self) -> float:
        return self.world_x

    def update(self, scroll_dx: float) -> None:
        self.world_x -= scroll_dx
        self.angle   += self.spin

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.world_x), int(self.y),
                           int(self.w), int(self.h))

    def draw(self, surf: pygame.Surface) -> None:
        cx = int(self.world_x + self.w / 2)
        cy = int(self.y + self.h / 2)
        if self.shape == "asteroid":
            r = self.w / 2
            sides = 7
            pts = []
            for i in range(sides):
                a = self.angle + i * math.tau / sides
                vary = 0.7 + 0.3 * math.sin(a * 3.7 + self.angle)
                pts.append((int(cx + r * vary * math.cos(a)),
                             int(cy + r * vary * math.sin(a))))
            _poly(pts, self.color, surf)
            _poly(pts, (min(255, self.color[0] + 40),
                        min(255, self.color[1] + 40),
                        min(255, self.color[2] + 40)), surf, 2)
        else:
            pygame.draw.rect(surf, self.color,
                             (int(self.world_x), int(self.y),
                              int(self.w), int(self.h)))
            pygame.draw.rect(surf, (min(255, self.color[0] + 40),
                                    min(255, self.color[1] + 40),
                                    min(255, self.color[2] + 40)),
                             (int(self.world_x), int(self.y),
                              int(self.w), int(self.h)), 2)


class _Boss:
    """End-of-level boss."""

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y  = float(x), float(y)
        self.hp         = _BOSS_HP
        self.max_hp     = _BOSS_HP
        self.alive      = True
        self.hurt_timer = 0
        self.fire_cd    = _BOSS_FIRE_CD
        self.phase      = 1    # 1 = normal, 2 = enraged
        self.vy         = _BOSS_SPEED   # vertical drift
        self.radius     = _BOSS_RADIUS

    def update(self, height: int) -> None:
        if self.hurt_timer > 0:
            self.hurt_timer -= 1
        if self.fire_cd > 0:
            self.fire_cd -= 1

        # Vertical bounce
        self.y += self.vy
        top_bound    = _BOSS_RADIUS + 60
        bottom_bound = height - _BOSS_RADIUS - 60
        if self.y < top_bound:
            self.y  = top_bound
            self.vy = abs(self.vy)
        elif self.y > bottom_bound:
            self.y  = bottom_bound
            self.vy = -abs(self.vy)

        # Enrage at half HP
        if self.hp <= _BOSS_PHASE2_HP and self.phase == 1:
            self.phase = 2
            self.vy    = self.vy * 1.5 if self.vy != 0 else _BOSS_SPEED * 1.5

    def hit(self, dmg: int) -> bool:
        self.hp -= dmg
        self.hurt_timer = 10
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
            return True
        return False

    def try_fire(self, target_x: float, target_y: float,
                 frame: int) -> list["_Projectile"]:
        """Return a list of boss projectiles (may be empty)."""
        if self.fire_cd > 0:
            return []
        self.fire_cd = _BOSS_FIRE_CD // (2 if self.phase == 2 else 1)
        bullets = []
        # Fan of 3 aimed shots
        dx = target_x - self.x
        dy = target_y - self.y
        dist = math.hypot(dx, dy) or 1.0
        base_angle = math.atan2(dy, dx)
        for spread in (-0.25, 0.0, 0.25):
            a  = base_angle + spread
            vx = math.cos(a) * _ENEMY_BULLET_SPD
            vy = math.sin(a) * _ENEMY_BULLET_SPD
            bullets.append(_Projectile(
                self.x, self.y, vx, vy,
                -1, _ENEMY_BULLET_DMG * 2,
                radius=6.0, color=(255, 60, 60),
            ))
        # Phase-2 extra ring burst
        if self.phase == 2 and (frame % 180) < 2:
            for i in range(8):
                a  = i * math.tau / 8
                vx = math.cos(a) * _ENEMY_BULLET_SPD * 0.8
                vy = math.sin(a) * _ENEMY_BULLET_SPD * 0.8
                bullets.append(_Projectile(
                    self.x, self.y, vx, vy,
                    -1, _ENEMY_BULLET_DMG,
                    radius=5.0, color=(255, 120, 60),
                ))
        return bullets


# ═══════════════════════════════════════════════════════════════════════════════
# Wave spawner
# ═══════════════════════════════════════════════════════════════════════════════

# Each entry: (trigger_scroll_px, wave_list)
# wave_list: list of (etype, rel_x, rel_y)  (rel_y relative to screen_h/2)
_WAVE_DEFS: list[tuple[int, list]] = [
    (400,  [("drone",    60,  -80), ("drone",    60,    0), ("drone",    60,   80)]),
    (900,  [("sine",    100,  -60), ("sine",    100,   60)]),
    (1400, [("drone",    80,  -100), ("drone",    80,    -40),
            ("drone",    80,    40), ("drone",    80,   100)]),
    (1900, [("kamikaze", 50,   0),  ("kamikaze", 80, -40), ("kamikaze", 80, 40)]),
    (2400, [("armoured", 60,   0)]),
    (2900, [("drone",    60,  -80), ("drone",    60,    0), ("drone",    60,   80),
            ("sine",    100,  -40), ("sine",    100,   40)]),
    (3500, [("turret",   80, -120), ("turret",   80,  120)]),
    (4200, [("armoured", 60, -50),  ("armoured", 60,   50)]),
    (5000, [("kamikaze", 50, -60),  ("kamikaze", 50,    0), ("kamikaze", 50,  60),
            ("drone",    80, -100), ("drone",    80,  100)]),
    (6000, [("armoured", 60,  -70), ("armoured", 60,    70),
            ("sine",    100, -120), ("sine",    100,  120)]),
    (7500, [("drone",    60, -100), ("drone",    60,  -50), ("drone",    60,    0),
            ("drone",    60,   50), ("drone",    60,  100)]),
    (9000, [("armoured", 60,  -80), ("turret",   80,  -40),
            ("turret",   80,   40), ("armoured", 60,   80)]),
]

# Terrain spawn table: (trigger_scroll_px, x_right_of_screen, y, w, h, shape)
_TERRAIN_DEFS: list[tuple] = [
    (600,  80, 60,  70, 60, "asteroid"),
    (600,  80, 620, 70, 60, "asteroid"),
    (1100, 80, 200, 50, 50, "asteroid"),
    (1100, 80, 450, 50, 50, "asteroid"),
    (1600, 80, 100, 120, 30, "rect"),
    (1600, 80, 600, 120, 30, "rect"),
    (2200, 80, 50,  60, 60, "asteroid"),
    (2200, 80, 300, 50, 50, "asteroid"),
    (2200, 80, 550, 60, 60, "asteroid"),
    (2800, 80, 150, 90, 25, "rect"),
    (2800, 80, 500, 90, 25, "rect"),
    (3300, 80, 250, 70, 70, "asteroid"),
    (4000, 80, 80,  80, 25, "rect"),
    (4000, 80, 570, 80, 25, "rect"),
    (4700, 80, 200, 60, 60, "asteroid"),
    (4700, 80, 420, 60, 60, "asteroid"),
    (5500, 80, 120, 100,30, "rect"),
    (5500, 80, 520, 100,30, "rect"),
    (6500, 80, 330, 80, 80, "asteroid"),
    (7000, 80, 60,  60, 60, "asteroid"),
    (7000, 80, 600, 60, 60, "asteroid"),
    (8000, 80, 200, 70, 70, "asteroid"),
    (8000, 80, 460, 70, 70, "asteroid"),
    (9500, 80, 100, 110,28, "rect"),
    (9500, 80, 540, 110,28, "rect"),
]


def _nearest_player(players: list[_PlayerShip],
                    x: float, y: float) -> tuple[float, float]:
    """Return the world position of the nearest alive player."""
    best_dist = float("inf")
    bx, by    = x, y
    for p in players:
        if not p.alive:
            continue
        d = math.hypot(p.x - x, p.y - y)
        if d < best_dist:
            best_dist = d
            bx, by    = p.x, p.y
    return bx, by


# ═══════════════════════════════════════════════════════════════════════════════
# Background
# ═══════════════════════════════════════════════════════════════════════════════

class _Starfield:
    """Multi-layer parallax starfield."""

    def __init__(self, width: int, height: int, seed: int = 1) -> None:
        rng = random.Random(seed)
        self._w = width
        self._h = height
        # Three layers at different speeds
        self._layers: list[list] = []
        for layer_i, (count, speed, r) in enumerate(
                [(80, 0.3, 1), (80, 0.6, 1), (40, 1.0, 2)]):
            stars = []
            for _ in range(count):
                sx = rng.uniform(0, width)
                sy = rng.uniform(0, height)
                brightness = rng.randint(140, 255)
                stars.append([sx, sy, speed, r, brightness])
            self._layers.append(stars)

        # A few distant "planets"
        rng2 = random.Random(_PLANET_SEED)
        self._planets: list[tuple] = []
        for _ in range(3):
            px = rng2.uniform(0, width)
            py = rng2.uniform(height * 0.1, height * 0.9)
            pr = rng2.uniform(22, 50)
            pc = (rng2.randint(40, 120), rng2.randint(20, 80), rng2.randint(40, 160))
            self._planets.append((px, py, pr, pc))

    def update(self, scroll_speed: float) -> None:
        for layer in self._layers:
            for star in layer:
                star[0] -= star[2] * scroll_speed
                if star[0] < 0:
                    star[0] += self._w

    def draw(self, surf: pygame.Surface) -> None:
        # Space gradient background
        for y in range(self._h):
            t = y / self._h
            r = int(4  + t * 8)
            g = int(2  + t * 4)
            b = int(18 + t * 22)
            pygame.draw.line(surf, (r, g, b), (0, y), (self._w, y))

        # Distant planets
        for px, py, pr, pc in self._planets:
            pygame.draw.circle(surf, pc, (int(px), int(py)), int(pr))
            pygame.draw.circle(surf, (min(255, pc[0] + 40),
                                      min(255, pc[1] + 40),
                                      min(255, pc[2] + 40)),
                               (int(px), int(py)), int(pr), 2)

        # Stars
        for layer in self._layers:
            for star in layer:
                b = star[4]
                c = (b, b, b)
                pygame.draw.circle(surf, c, (int(star[0]), int(star[1])), star[3])


# ═══════════════════════════════════════════════════════════════════════════════
# Main level class
# ═══════════════════════════════════════════════════════════════════════════════

class RTypeLevel(BaseLevel):
    """R-Type-style horizontal shoot-em-up mode.

    Call ``run()`` to play.  Returns ``"complete"``, ``"dead"``, or
    ``"exit"`` (player pressed ESC).
    """

    def __init__(self, screen, width: int, height: int, fps: int,
                 settings, font, acid, sfx,
                 joystick=None, joystick2=None) -> None:
        super().__init__(screen, width, height, fps, settings, font, acid, sfx,
                         joystick=joystick, joystick2=joystick2)
        self._clock = pygame.time.Clock()

        # Collect all available joysticks
        n_joy = pygame.joystick.get_count()
        self._joysticks: list = []
        for i in range(min(4, n_joy)):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            self._joysticks.append(joy)

        # Fonts
        self._hud_font = pygame.font.SysFont(None, 24, bold=True)
        self._big_font = pygame.font.SysFont(None, 72, bold=True)
        self._med_font = pygame.font.SysFont(None, 40, bold=True)
        self._sml_font = pygame.font.SysFont(None, 20)

        # Starfield (baked once, scrolled each frame)
        self._stars = _Starfield(width, height)

    # ── Public entry-point ────────────────────────────────────────────────────

    def run(self) -> str:
        """Play the level.  Returns ``"complete"``, ``"dead"``, or
        ``"exit"``."""
        self._reset()
        self._show_banner("LAUNCH!", (80, 200, 255), frames=80)

        while True:
            self._clock.tick(self.fps)

            result = self._handle_events()
            if result:
                return result

            self._update()
            self._draw()
            pygame.display.flip()
            self._frame += 1

            # All players dead
            if all(not p.alive for p in self._players):
                self._show_overlay("ALL SHIPS DESTROYED", (230, 60, 60),
                                   (100, 0, 0, 180))
                return "dead"

            # Boss defeated
            if self._boss is not None and not self._boss.alive:
                self._show_overlay("STAGE CLEAR!", (80, 240, 120),
                                   (0, 80, 0, 160))
                return "complete"

    # ── Initialisation ────────────────────────────────────────────────────────

    def _reset(self) -> None:
        self._frame   = 0
        self._scroll  = 0.0      # total pixels scrolled
        self._boss: _Boss | None = None
        self._boss_spawned = False
        self._boss_warning = 0

        # Player spawn positions (stacked vertically in left third)
        cy = self.height // 2
        spawn_ys = [cy - 90, cy - 30, cy + 30, cy + 90]
        spawn_x  = 100.0

        num_local = self.settings.num_players

        j0 = self._joysticks[0] if self._joysticks else None
        self._players: list[_PlayerShip] = [
            _PlayerShip(spawn_x, spawn_ys[0], 0, joystick=j0)
        ]
        if num_local >= 2:
            j1 = self._joysticks[1] if len(self._joysticks) > 1 else None
            self._players.append(
                _PlayerShip(spawn_x, spawn_ys[1], 1, joystick=j1)
            )
        for i in range(2, min(num_local, 4)):
            jn = self._joysticks[i] if len(self._joysticks) > i else None
            self._players.append(
                _PlayerShip(spawn_x, spawn_ys[i], i, joystick=jn)
            )

        self._enemies:    list[_EnemyShip]    = []
        self._projectiles:list[_Projectile]   = []
        self._powerups:   list[_PowerUp]      = []
        self._terrain:    list[_TerrainSegment] = []

        # Wave spawn tracking (index into _WAVE_DEFS / _TERRAIN_DEFS)
        self._wave_idx   = 0
        self._terr_idx   = 0

        # Score (total)
        self._total_score = 0

        # HUD message
        self._msg_text  = ""
        self._msg_color = (255, 255, 255)
        self._msg_timer = 0

        # Explosion particles: [(x, y, vx, vy, life, color), ...]
        self._particles: list[list] = []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sfx(self, name: str) -> None:
        try:
            self.sfx.play(name)
        except Exception:
            pass

    def _show_msg(self, text: str, color: tuple, frames: int = 150) -> None:
        self._msg_text  = text
        self._msg_color = color
        self._msg_timer = frames

    def _spawn_explosion(self, x: float, y: float, count: int = 8,
                         color: tuple = (255, 180, 60)) -> None:
        for _ in range(count):
            a   = random.uniform(0, math.tau)
            spd = random.uniform(1.5, 4.0)
            self._particles.append([
                x, y,
                math.cos(a) * spd, math.sin(a) * spd,
                random.randint(20, 40),
                color,
            ])

    def _maybe_drop_powerup(self, x: float, y: float) -> None:
        if random.random() < 0.18:
            kind = random.choice(_POWERUP_TYPES)
            self._powerups.append(_PowerUp(x, y, kind))

    # ── Event handling ────────────────────────────────────────────────────────

    def _handle_events(self) -> str | None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "exit"
        return None

    # ── Input ─────────────────────────────────────────────────────────────────

    def _read_input(self, p: _PlayerShip) -> tuple[float, float, bool, bool]:
        """Return (dx, dy, fire, charge_held)."""
        keys    = pygame.key.get_pressed()
        kb1     = self.settings.keyboard
        kb2     = self.settings.keyboard_p2
        dx = dy = 0.0
        fire = charge_held = False

        if p.p_index == 0:
            if keys[kb1.get("move_left",  pygame.K_LEFT)]:  dx -= 1.0
            if keys[kb1.get("move_right", pygame.K_RIGHT)]: dx += 1.0
            if keys[kb1.get("move_up",    pygame.K_UP)]:    dy -= 1.0
            if keys[kb1.get("move_down",  pygame.K_DOWN)]:  dy += 1.0
            fire        = bool(keys[kb1.get("punch", pygame.K_z)])
            charge_held = bool(keys[kb1.get("kick",  pygame.K_x)])

        elif p.p_index == 1 and not p.joystick:
            if keys[kb2.get("move_left",  pygame.K_a)]:  dx -= 1.0
            if keys[kb2.get("move_right", pygame.K_d)]:  dx += 1.0
            if keys[kb2.get("move_up",    pygame.K_w)]:  dy -= 1.0
            if keys[kb2.get("move_down",  pygame.K_s)]:  dy += 1.0
            fire        = bool(keys[kb2.get("punch", pygame.K_r)])
            charge_held = bool(keys[kb2.get("kick",  pygame.K_f)])

        if p.joystick is not None:
            joy = p.joystick
            try:
                ax = joy.get_axis(0)
                ay = joy.get_axis(1)
                if abs(ax) > AXIS_DEADZONE:
                    dx = ax
                if abs(ay) > AXIS_DEADZONE:
                    dy = ay
                fire        = bool(joy.get_button(_BTN_FIRE))
                charge_held = bool(joy.get_button(_BTN_CHARGE))
                # D-pad
                if joy.get_numhats() > 0:
                    hx, hy = joy.get_hat(0)
                    if hx:
                        dx = float(hx)
                    if hy:
                        dy = float(-hy)
            except Exception:
                pass

        return dx, dy, fire, charge_held

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self) -> None:
        frame  = self._frame
        width  = self.width
        height = self.height

        # ── Scroll ────────────────────────────────────────────────────────────
        # Pause scroll when boss is active
        if self._boss is not None and self._boss.alive:
            scroll_dx = 0.0
        else:
            scroll_dx = _SCROLL_SPEED
        self._scroll += scroll_dx

        # ── Stars ─────────────────────────────────────────────────────────────
        self._stars.update(scroll_dx / _SCROLL_SPEED)

        # ── Wave spawner ──────────────────────────────────────────────────────
        while (self._wave_idx < len(_WAVE_DEFS) and
               self._scroll >= _WAVE_DEFS[self._wave_idx][0]):
            _, wave = _WAVE_DEFS[self._wave_idx]
            cy = height // 2
            for etype, rx, ry in wave:
                ex = width + rx
                ey = cy + ry
                ey = max(40.0, min(float(height - 40), float(ey)))
                self._enemies.append(_EnemyShip(ex, ey, etype))
            self._wave_idx += 1

        # ── Terrain spawner ───────────────────────────────────────────────────
        while (self._terr_idx < len(_TERRAIN_DEFS) and
               self._scroll >= _TERRAIN_DEFS[self._terr_idx][0]):
            _, rx, ty, tw, th, shape = _TERRAIN_DEFS[self._terr_idx]
            self._terrain.append(
                _TerrainSegment(float(width + rx), float(ty),
                                float(tw), float(th), shape))
            self._terr_idx += 1

        # ── Boss spawn ────────────────────────────────────────────────────────
        if not self._boss_spawned and self._scroll >= _LEVEL_LENGTH:
            self._boss_spawned = True
            self._boss = _Boss(float(width - 80), float(height // 2))
            self._show_msg("!! BOSS !!", (255, 60, 60), frames=180)
            self._sfx("boss_attack")

        # ── Boss warning ──────────────────────────────────────────────────────
        if not self._boss_spawned and self._scroll >= _LEVEL_LENGTH - 800:
            self._boss_warning = max(self._boss_warning, 1)

        # ── Update terrain ────────────────────────────────────────────────────
        for seg in self._terrain:
            seg.update(scroll_dx)
        self._terrain = [s for s in self._terrain if s.world_x > -200]

        # ── Update enemies ────────────────────────────────────────────────────
        tx, ty = _nearest_player(self._players, width / 2, height / 2)
        for en in self._enemies:
            en.update(scroll_dx, tx, ty)
            bullet = en.try_fire(tx, ty, float(width))
            if bullet:
                self._projectiles.append(bullet)
        self._enemies = [e for e in self._enemies
                         if e.alive and e.x > -80 and e.x < width + 200]

        # ── Update boss ───────────────────────────────────────────────────────
        if self._boss is not None and self._boss.alive:
            self._boss.update(height)
            boss_bullets = self._boss.try_fire(tx, ty, frame)
            self._projectiles.extend(boss_bullets)
            # Ease boss into screen from right
            target_bx = width - 140.0
            if self._boss.x > target_bx:
                self._boss.x -= 1.5

        # ── Update players ────────────────────────────────────────────────────
        for p in self._players:
            if not p.alive:
                continue
            dx, dy, fire, charge_held = self._read_input(p)

            # Movement
            spd = p.speed
            p.x = max(20.0, min(float(width - 20),  p.x + dx * spd))
            p.y = max(20.0, min(float(height - 20), p.y + dy * spd))

            # Hurt timer
            if p.hurt_timer > 0:
                p.hurt_timer -= 1
            if p.invuln > 0:
                p.invuln -= 1

            # Power-up countdown
            p.tick_powerups()

            # ── Rapid fire ────────────────────────────────────────────────────
            if p.fire_cd > 0:
                p.fire_cd -= 1

            if fire and not p.charging and p.fire_cd == 0:
                p.fire_cd = _P_RAPID_CD
                self._fire_rapid(p)

            # ── Charge shot ───────────────────────────────────────────────────
            if charge_held:
                p.charge_held += 1
                p.charging     = True
            else:
                if p.charging and p.charge_held >= _P_CHARGE_MIN:
                    self._fire_charge(p)
                p.charge_held  = 0
                p.charging     = False

            # ── Force pod ─────────────────────────────────────────────────────
            p.pod.update(p.x, p.y, p.facing)
            pod_bullet = p.pod.try_fire(p.facing)
            if pod_bullet:
                self._projectiles.append(pod_bullet)

            # ── Boundary clamp ────────────────────────────────────────────────
            p.x = max(20.0, min(float(width - 20),  p.x))
            p.y = max(20.0, min(float(height - 20), p.y))

        # ── Update projectiles ────────────────────────────────────────────────
        for proj in self._projectiles:
            proj.update(0.0)   # bullets do not scroll (world-independent)
        self._projectiles = [
            b for b in self._projectiles
            if b.alive and 0 <= b.x <= width + 60 and -40 <= b.y <= height + 40
        ]

        # ── Update power-ups ──────────────────────────────────────────────────
        for pu in self._powerups:
            pu.update(scroll_dx)
        self._powerups = [pu for pu in self._powerups if pu.alive and pu.x > -40]

        # ── Update particles ──────────────────────────────────────────────────
        for pt in self._particles:
            pt[0] += pt[2]
            pt[1] += pt[3]
            pt[4] -= 1
        self._particles = [pt for pt in self._particles if pt[4] > 0]

        # ── Message timer ─────────────────────────────────────────────────────
        if self._msg_timer > 0:
            self._msg_timer -= 1

        # ── Collision detection ───────────────────────────────────────────────
        self._check_collisions()

    def _fire_rapid(self, p: _PlayerShip) -> None:
        """Fire one (or spread) rapid shot."""
        color = p.color
        if p.laser_shot > 0:
            # Laser: long thin beam projectile
            self._projectiles.append(_Projectile(
                p.x + 16, p.y, _P_BULLET_SPEED * 1.5, 0.0,
                p.p_index, 20, radius=3.0,
                color=(180, 230, 255), pierce=True,
            ))
        elif p.spread_shot > 0:
            for vy_off in (-2.0, 0.0, 2.0):
                self._projectiles.append(_Projectile(
                    p.x + 16, p.y, _P_BULLET_SPEED, vy_off,
                    p.p_index, 10, radius=3.5, color=color,
                ))
        else:
            self._projectiles.append(_Projectile(
                p.x + 16, p.y, _P_BULLET_SPEED, 0.0,
                p.p_index, 12, radius=4.0, color=color,
            ))
        self._sfx("punch")

    def _fire_charge(self, p: _PlayerShip) -> None:
        """Fire a charged shot; power scales with charge_held duration."""
        charge = min(p.charge_held, _P_CHARGE_MAX)
        frac   = charge / _P_CHARGE_MAX
        dmg    = int(_P_CHARGE_DMGBASE + frac * 55)
        radius = 6.0 + frac * 10.0
        speed  = _P_CHARGE_SPEED

        # Full charge = piercing beam
        pierce = (frac >= 0.99)
        r_c = int(255 * (1.0 - frac * 0.4))
        g_c = int(200 + frac * 55)
        b_c = int(100 + frac * 155)
        color = (r_c, g_c, b_c)

        self._projectiles.append(_Projectile(
            p.x + 18, p.y, speed, 0.0,
            p.p_index, dmg, radius=radius,
            color=color, is_charge=True, pierce=pierce,
        ))
        self._sfx("kick")

    def _check_collisions(self) -> None:
        width  = self.width
        height = self.height

        # ── Player bullets vs enemies / boss ──────────────────────────────────
        for proj in self._projectiles:
            if proj.owner < 0:
                continue    # enemy bullet – skip

            # vs enemies
            for en in self._enemies:
                if not en.alive:
                    continue
                if math.hypot(proj.x - en.x, proj.y - en.y) < proj.radius + en.radius:
                    killed = en.hit(proj.damage)
                    if not proj.pierce:
                        proj.alive = False
                    if killed:
                        self._spawn_explosion(en.x, en.y, 10, en.color)
                        self._maybe_drop_powerup(en.x, en.y)
                        pts = en.score
                        for p in self._players:
                            if p.p_index == proj.owner:
                                p.score += pts
                        self._total_score += pts
                        self._sfx("impact")
                    else:
                        self._sfx("enemy_hurt")
                    if not proj.alive:
                        break

            # vs boss core
            if self._boss is not None and self._boss.alive and proj.alive:
                dist = math.hypot(proj.x - self._boss.x, proj.y - self._boss.y)
                if dist < proj.radius + _BOSS_CORE_RADIUS + _BOSS_CORE_FUZZ:
                    killed = self._boss.hit(proj.damage)
                    if not proj.pierce:
                        proj.alive = False
                    self._spawn_explosion(proj.x, proj.y, 5, (255, 200, 100))
                    if killed:
                        self._spawn_explosion(self._boss.x, self._boss.y,
                                              30, (255, 120, 40))
                        self._sfx("impact")
                    else:
                        self._sfx("boss_attack")

        # ── Enemy bullets / contact vs players ────────────────────────────────
        for p in self._players:
            if not p.alive:
                continue

            # Enemy bullets
            for proj in self._projectiles:
                if proj.owner >= 0:
                    continue
                if math.hypot(proj.x - p.x, proj.y - p.y) < proj.radius + p.radius:
                    proj.alive = False
                    dead = p.damage(proj.damage)
                    self._spawn_explosion(p.x, p.y, 6, (255, 100, 60))
                    self._sfx("player_hurt")
                    if dead:
                        self._sfx("impact")

            # Enemy contact
            for en in self._enemies:
                if not en.alive:
                    continue
                if math.hypot(p.x - en.x, p.y - en.y) < p.radius + en.radius:
                    dead = p.damage(en.contact_dmg)
                    en.hit(_ENEMY_RECOIL_DMG)   # slight recoil damage to enemy
                    self._spawn_explosion(
                        (p.x + en.x) / 2, (p.y + en.y) / 2, 8)
                    self._sfx("player_hurt")

            # Terrain contact
            for seg in self._terrain:
                if seg.rect().collidepoint(int(p.x), int(p.y)):
                    dead = p.damage(_TERRAIN_DAMAGE)
                    self._spawn_explosion(p.x, p.y, 6, (200, 200, 60))
                    self._sfx("player_hurt")

            # Boss contact
            if self._boss is not None and self._boss.alive:
                if math.hypot(p.x - self._boss.x, p.y - self._boss.y) < (
                        p.radius + self._boss.radius):
                    dead = p.damage(30)
                    self._spawn_explosion(p.x, p.y, 8)
                    self._sfx("player_hurt")

            # Power-up collection
            for pu in self._powerups:
                if math.hypot(p.x - pu.x, p.y - pu.y) < p.radius + _POWERUP_RADIUS:
                    p.apply_powerup(pu.kind)
                    pu.alive = False
                    self._show_msg(pu.kind.upper() + "!", (80, 255, 200), 90)
                    self._sfx("punch")

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        surf = self.screen

        # Background
        self._stars.draw(surf)

        # Terrain
        for seg in self._terrain:
            seg.draw(surf)

        # Power-ups
        for pu in self._powerups:
            pu.draw(surf)

        # Enemies
        for en in self._enemies:
            if not en.alive:
                continue
            hurt = en.hurt_timer > 0
            _draw_enemy_ship(surf, en.x, en.y, en.radius,
                             en.color, en.dark, en.sides, en.angle, hurt)

        # Boss
        if self._boss is not None and self._boss.alive:
            _draw_boss(surf, self._boss.x, self._boss.y,
                       self._frame, self._boss.hp, self._boss.max_hp,
                       hurt=self._boss.hurt_timer > 0)

        # Projectiles
        for proj in self._projectiles:
            if not proj.alive:
                continue
            r = max(1, int(proj.radius))
            if proj.is_charge or proj.pierce:
                # Draw elongated beam
                dx = -int(proj.vx * 3)
                tail_x = int(proj.x) + dx
                pygame.draw.line(surf, proj.color,
                                 (int(proj.x), int(proj.y)),
                                 (tail_x, int(proj.y)), max(2, r))
                pygame.draw.circle(surf, (255, 255, 255),
                                   (int(proj.x), int(proj.y)), max(1, r - 1))
            else:
                pygame.draw.circle(surf, proj.color,
                                   (int(proj.x), int(proj.y)), r)

        # Players
        for p in self._players:
            if not p.alive:
                continue
            blink = (p.invuln > 0 and (self._frame // 4) % 2 == 0)
            if not blink:
                _draw_ship(surf, p.x, p.y, p.radius,
                           p.color, p.dark, p.facing,
                           hurt=p.hurt_timer > 0,
                           shield=p.shield > 0)
                # Force pod
                _draw_ship(surf, p.pod.x, p.pod.y, p.radius * 0.65,
                           p.dark, p.color, p.facing)
                # Charge glow
                if p.charging and p.charge_held >= _P_CHARGE_MIN:
                    frac = min(p.charge_held / _P_CHARGE_MAX, 1.0)
                    gr   = int(4 + frac * 18)
                    gc   = (int(80 + frac * 175),
                            int(200 + frac * 55),
                            int(100 + frac * 155))
                    pygame.draw.circle(surf, gc,
                                       (int(p.x + 10), int(p.y)),
                                       max(2, gr), 2)

        # Exhaust trails
        for p in self._players:
            if not p.alive:
                continue
            if (self._frame // 3) % 2 == 0:
                tx = int(p.x - p.facing * p.radius * 0.9)
                ty = int(p.y)
                pygame.draw.circle(surf, (255, 140, 40), (tx, ty), 4)

        # Particles
        for pt in self._particles:
            alpha = int(255 * pt[4] / 40)
            col   = (min(255, pt[5][0]), min(255, pt[5][1]), min(255, pt[5][2]))
            pygame.draw.circle(surf, col, (int(pt[0]), int(pt[1])), 3)

        # HUD
        self._draw_hud(surf)

        # Centre messages
        if self._msg_timer > 0:
            alpha = min(255, self._msg_timer * 8)
            s = self._med_font.render(self._msg_text, True, self._msg_color)
            s.set_alpha(alpha)
            surf.blit(s, (self.width // 2 - s.get_width() // 2,
                          self.height // 2 - s.get_height() // 2))

        # Boss-incoming warning
        if self._boss_warning and not self._boss_spawned:
            if (self._frame // 20) % 2 == 0:
                ws = self._sml_font.render("!! WARNING: BOSS INCOMING !!",
                                           True, (255, 60, 60))
                surf.blit(ws, (self.width // 2 - ws.get_width() // 2, 8))

    def _draw_hud(self, surf: pygame.Surface) -> None:
        n = len(self._players)
        bar_w   = 120
        bar_h   = 10
        pad     = 8
        col_gap = (self.width - n * (bar_w + pad)) // (n + 1)
        y_base  = self.height - 38

        for i, p in enumerate(self._players):
            x_off = col_gap + i * (bar_w + pad + col_gap)

            # Player label
            label_col = p.color if p.alive else (80, 80, 80)
            ls = self._hud_font.render(p.label, True, label_col)
            surf.blit(ls, (x_off, y_base - 14))

            # HP bar
            hp_frac = p.hp / p.max_hp if p.alive else 0.0
            hp_col  = _HP_COL if hp_frac > 0.3 else _HP_LOW_COL
            pygame.draw.rect(surf, _HP_BG_COL,
                             (x_off, y_base, bar_w, bar_h))
            pygame.draw.rect(surf, hp_col,
                             (x_off, y_base, int(bar_w * hp_frac), bar_h))
            pygame.draw.rect(surf, (180, 180, 180),
                             (x_off, y_base, bar_w, bar_h), 1)

            # Charge meter
            c_frac = min(p.charge_held / _P_CHARGE_MAX, 1.0) if p.alive else 0.0
            c_col  = _CHARGE_FULL if c_frac >= 1.0 else _CHARGE_COL
            cm_y   = y_base + bar_h + 3
            pygame.draw.rect(surf, _HP_BG_COL,
                             (x_off, cm_y, bar_w, 5))
            if c_frac > 0:
                pygame.draw.rect(surf, c_col,
                                 (x_off, cm_y, int(bar_w * c_frac), 5))
            pygame.draw.rect(surf, (100, 100, 100),
                             (x_off, cm_y, bar_w, 5), 1)

            # Score
            ss = self._sml_font.render(f"{p.score}", True, _SCORE_COL)
            surf.blit(ss, (x_off + bar_w - ss.get_width(), y_base - 14))

        # Boss health bar
        if self._boss is not None and self._boss.alive:
            bw = self.width // 2
            bx = self.width // 4
            by = 8
            bh = 14
            frac = self._boss.hp / self._boss.max_hp
            pygame.draw.rect(surf, _BOSS_BAR_BG, (bx, by, bw, bh))
            pygame.draw.rect(surf, _BOSS_BAR_COL,
                             (bx, by, int(bw * frac), bh))
            pygame.draw.rect(surf, (255, 80, 80), (bx, by, bw, bh), 2)
            bs = self._sml_font.render("BOSS", True, (255, 120, 120))
            surf.blit(bs, (bx - bs.get_width() - 6, by))

        # Scroll progress bar (thin line at very top)
        if not self._boss_spawned:
            prog = min(self._scroll / _LEVEL_LENGTH, 1.0)
            pygame.draw.rect(surf, (40, 40, 40), (0, 0, self.width, 3))
            pygame.draw.rect(surf, (80, 180, 255),
                             (0, 0, int(self.width * prog), 3))

    # ── Overlay helpers ───────────────────────────────────────────────────────

    def _show_banner(self, text: str, color: tuple, frames: int = 90) -> None:
        """Briefly display a centred banner before gameplay begins."""
        clock = pygame.time.Clock()
        for f in range(frames):
            clock.tick(self.fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
            self._stars.draw(self.screen)
            alpha = min(255, (frames - f) * 6)
            s = self._big_font.render(text, True, color)
            s.set_alpha(alpha)
            self.screen.blit(
                s,
                (self.width // 2 - s.get_width() // 2,
                 self.height // 2 - s.get_height() // 2),
            )
            pygame.display.flip()

    def _show_overlay(self, text: str, color: tuple,
                      bg_color: tuple = (0, 0, 0, 160),
                      wait_frames: int = 120) -> None:
        """Display a full-screen overlay with *text*, then pause."""
        clock = pygame.time.Clock()
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill(bg_color)
        for f in range(wait_frames):
            clock.tick(self.fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    return
            self.screen.blit(overlay, (0, 0))
            s = self._big_font.render(text, True, color)
            self.screen.blit(
                s,
                (self.width // 2 - s.get_width() // 2,
                 self.height // 2 - s.get_height() // 2),
            )
            pygame.display.flip()
