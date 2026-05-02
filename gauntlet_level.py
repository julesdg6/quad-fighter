"""gauntlet_level.py

Expanded Gauntlet co-op dungeon mode for Quad Fighter.

Features
--------
* 1–4 players co-op  (P1: keyboard, P2–P4: gamepad controllers)
* Multi-room dungeon with corridors and a locked door
* Enemy generators that continuously spawn enemies (core mechanic) –
  destroy all generators to open the exit
* Key unlocks the door between Room 2 and Room 3
* Food pickups restore health; health drains slowly over time
* Scrolling camera tracks the alive-player centroid
* Per-player HP bars and "NEEDS FOOD BADLY" warnings
* Wide attack arcs suited to crowd control

GauntletLevel.run() returns "complete" | "dead" | "exit".
"""

import math
import random

import pygame

from base_level import BaseLevel
from settings import AXIS_DEADZONE

# ── World ─────────────────────────────────────────────────────────────────────

_WORLD_W = 1400
_WORLD_H = 750

# ── Player tuning ─────────────────────────────────────────────────────────────

_PLAYER_SPEED         = 3.5
_PLAYER_MAX_HP        = 100
_PLAYER_INVULN_FRAMES = 24
_PLAYER_RADIUS        = 14
_HEALTH_DRAIN_FRAMES  = 180   # 1 HP lost every N frames  (≈ 3 s at 60 fps)

# ── Light attack ──────────────────────────────────────────────────────────────

_LIGHT_RANGE        = 62
_LIGHT_ARC          = math.radians(90)   # wider for crowd control
_LIGHT_DAMAGE       = 12
_LIGHT_ANTICIPATION = 4
_LIGHT_STRIKE       = 5
_LIGHT_RECOVERY     = 7
_LIGHT_COOLDOWN     = 14
_LIGHT_KNOCKBACK    = 60

# ── Heavy attack ──────────────────────────────────────────────────────────────

_HEAVY_RANGE        = 74
_HEAVY_ARC          = math.radians(120)
_HEAVY_DAMAGE       = 28
_HEAVY_ANTICIPATION = 10
_HEAVY_STRIKE       = 6
_HEAVY_RECOVERY     = 12
_HEAVY_COOLDOWN     = 34
_HEAVY_KNOCKBACK    = 130

# ── Generator ────────────────────────────────────────────────────────────────

_GEN_HP          = 60
_GEN_RADIUS      = 24
_GEN_SPAWN_BASE  = 300   # frames between spawns at start (≈ 5 s at 60 fps)
_GEN_SPAWN_MIN   = 80    # minimum interval under pressure
_GEN_MAX_ENEMIES = 14    # generator pauses when total enemy count ≥ this

# ── Enemy types ───────────────────────────────────────────────────────────────

_ENEMY_TYPES: dict[str, dict] = {
    "basic": {
        "speed": 1.4, "max_hp": 30, "radius": 13, "damage": 8,
        "attack_range": 26, "attack_cooldown": 50, "attack_wind": 12,
        "knockback_resist": 0.6,
        "color": (180, 60, 60), "dark_color": (120, 30, 30),
    },
    "fast": {
        "speed": 2.8, "max_hp": 18, "radius": 11, "damage": 6,
        "attack_range": 22, "attack_cooldown": 35, "attack_wind": 8,
        "knockback_resist": 0.4,
        "color": (60, 180, 220), "dark_color": (30, 100, 140),
    },
    "tank": {
        "speed": 0.8, "max_hp": 80, "radius": 18, "damage": 15,
        "attack_range": 32, "attack_cooldown": 80, "attack_wind": 18,
        "knockback_resist": 0.85,
        "color": (100, 100, 220), "dark_color": (50, 50, 150),
    },
}

# Spawn tables used by each generator (cycles through enemy types)
_GEN_SPAWN_TABLES: list = [
    ["basic", "basic", "fast",  "basic"],
    ["fast",  "basic", "tank",  "fast"],
    ["basic", "tank",  "fast",  "tank"],
]

# ── Dungeon layout ────────────────────────────────────────────────────────────
#
#  [  START  ]────────[  ROOM 2  ]────(door)────[  ROOM 3 / EXIT  ]
#                          │
#                     [  ROOM 4  ]    ← key + generator
#
# Floor rects are the union of walkable areas.  Everything outside
# these rects is solid wall.

_ROOM_START = pygame.Rect(50,   150, 280, 220)   # start room (safe zone)
_ROOM_2     = pygame.Rect(560,  150, 280, 220)   # hub room   (Gen 0)
_ROOM_3     = pygame.Rect(1070, 150, 280, 220)   # exit room  (Gen 2)
_ROOM_4     = pygame.Rect(560,  500, 280, 220)   # branch room (Key + Gen 1)

_CORR_S2    = pygame.Rect(290, 220, 310, 80)     # START ↔ ROOM 2  (horizontal)
_CORR_23    = pygame.Rect(800, 220, 310, 80)     # ROOM 2 ↔ ROOM 3 (has door)
_CORR_24    = pygame.Rect(640, 330,  80, 210)    # ROOM 2 ↔ ROOM 4 (vertical)

_FLOOR_RECTS: list = [
    _ROOM_START, _ROOM_2, _ROOM_3, _ROOM_4,
    _CORR_S2, _CORR_23, _CORR_24,
]

# Door: blocks the ROOM-2→ROOM-3 corridor near the ROOM-3 entrance.
# Positioned in the right portion of _CORR_23 (x 985–1065) so the
# corridor centre (x≈955) remains navigable from the ROOM-2 side.
_DOOR_RECT = pygame.Rect(985, 220, 80, 80)

# Exit trigger zone (inside ROOM_3, top-right corner)
_EXIT_RECT = pygame.Rect(1270, 165, 70, 80)

# Generator definitions: (world_x, world_y, table_index)
_GEN_DEFS: list = [
    (700, 260, 0),    # Gen 0 – ROOM 2, table 0
    (700, 610, 1),    # Gen 1 – ROOM 4, table 1
    (1210, 260, 2),   # Gen 2 – ROOM 3, table 2
]

# Item definitions: (world_x, world_y, item_type)
_ITEM_DEFS: list = [
    (190, 260, "food"),   # food in START
    (640, 575, "key"),    # key  in ROOM 4  (near corridor entrance)
    (1100, 260, "food"),  # food in ROOM 3
]

# ── Colours ───────────────────────────────────────────────────────────────────

_WALL_COLOR     = (70,  70,  90)
_WALL_INNER_COL = (50,  50,  65)
_FLOOR_COLOR    = (35,  35,  45)
_FLOOR_TILE_COL = (40,  40,  52)
_TILE_SIZE      = 48
_GEN_COLOR      = (200, 120,  30)
_GEN_DARK       = (120,  60,  10)
_GEN_DEAD_COL   = (60,   60,  60)
_DOOR_COLOR     = (140, 100,  30)
_DOOR_OPEN_COL  = (50,   80,  30)
_EXIT_COLOR     = (200, 200,  40)
_KEY_COLOR      = (220, 180,  40)
_FOOD_COLOR     = (60,  200,  60)

_HP_BAR_W        = 160
_HP_BAR_H        = 14
_HP_COLOR        = (60,  220,  80)
_HP_BG_COLOR     = (40,   40,  40)
_HP_LOW_COLOR    = (220,  60,  60)
_HP_WARN_THRESH  = 25           # "needs food" warning below this value
_HUD_TEXT_COLOR  = (220, 220, 220)
_HINT_FRAMES     = 300          # show controls hint for 5 seconds

# Controller buttons (standard Xbox/SDL layout)
_BTN_LIGHT = 2   # X button
_BTN_HEAVY = 1   # B button

# ── Data classes ──────────────────────────────────────────────────────────────


class _GPlayer:
    """One co-op player in Gauntlet mode."""

    _COLORS      = [(80, 160, 255), (255, 100,  80), (80, 220,  80), (220, 180,  40)]
    _DARK_COLORS = [(40,  80, 160), (160,  50,  40), (40, 140,  40), (140, 110,  20)]
    _LABELS      = ["P1", "P2", "P3", "P4"]

    def __init__(self, x: float, y: float, p_index: int,
                 joystick=None) -> None:
        self.x, self.y   = float(x), float(y)
        self.p_index     = p_index
        self.joystick    = joystick
        self.hp          = _PLAYER_MAX_HP
        self.max_hp      = _PLAYER_MAX_HP
        self.facing      = 0.0
        self.last_dir    = 0.0
        self.invuln      = 0
        self.atk_timer   = 0
        self.atk_cd      = 0
        self.atk_heavy   = False
        self.atk_phase   = ""
        self.atk_hit_ids: set = set()
        self.gen_hit_ids: set = set()
        self.keys_held   = 0
        self.alive       = True
        self.color       = self._COLORS[p_index % 4]
        self.dark_color  = self._DARK_COLORS[p_index % 4]
        self.label       = self._LABELS[p_index % 4]
        self.score       = 0


class _Generator:
    """Continuously spawns enemies; destroyed by player attacks."""

    def __init__(self, x: float, y: float, table_index: int = 0) -> None:
        self.x, self.y   = float(x), float(y)
        self.hp          = _GEN_HP
        self.max_hp      = _GEN_HP
        # Stagger initial spawn timers so generators don't all fire at once
        self.spawn_timer = random.randint(120, _GEN_SPAWN_BASE)
        self.table       = _GEN_SPAWN_TABLES[table_index % len(_GEN_SPAWN_TABLES)]
        self.spawn_idx   = 0
        self.alive       = True
        self.hurt_timer  = 0


class _GEnemy:
    """A single enemy in Gauntlet mode."""

    def __init__(self, x: float, y: float, etype: str) -> None:
        cfg = _ENEMY_TYPES[etype]
        self.x, self.y        = float(x), float(y)
        self.etype            = etype
        self.speed            = cfg["speed"]
        self.hp               = cfg["max_hp"]
        self.max_hp           = cfg["max_hp"]
        self.radius           = cfg["radius"]
        self.damage           = cfg["damage"]
        self.attack_range     = cfg["attack_range"]
        self.attack_cooldown  = cfg["attack_cooldown"]
        self.attack_wind      = cfg["attack_wind"]
        self.knockback_resist = cfg["knockback_resist"]
        self.color            = cfg["color"]
        self.dark_color       = cfg["dark_color"]
        self.alive            = True
        self.vx, self.vy      = 0.0, 0.0
        self.facing           = 0.0
        self.atk_timer        = 0
        self.atk_cd           = random.randint(0, cfg["attack_cooldown"])
        self.hurt_timer       = 0


class _Item:
    """Collectible pickup: "key" or "food"."""

    def __init__(self, x: float, y: float, item_type: str) -> None:
        self.x, self.y = float(x), float(y)
        self.item_type = item_type
        self.collected = False
        self.bob       = random.uniform(0, math.tau)   # phase for bobbing anim


class _Door:
    """Locked corridor door; unlocked when a key-bearing player touches it."""

    def __init__(self, rect: pygame.Rect) -> None:
        self.rect         = pygame.Rect(rect)
        self.locked       = True
        self.unlock_flash = 0   # visual feedback frames


# ── Main class ────────────────────────────────────────────────────────────────


class GauntletLevel(BaseLevel):
    """Expanded Gauntlet co-op dungeon mode.

    Call ``run()`` to play.  Returns ``"complete"``, ``"dead"``, or
    ``"exit"`` (player pressed ESC).
    """

    def __init__(self, screen, width: int, height: int, fps: int,
                 settings, font, acid, sfx, joystick=None, joystick2=None) -> None:
        super().__init__(screen, width, height, fps, settings, font, acid, sfx,
                         joystick=joystick, joystick2=joystick2)
        self._clock = pygame.time.Clock()

        # Detect joysticks for up to 4-player support
        n_joy = pygame.joystick.get_count()
        self._joysticks: list = []
        for i in range(min(4, n_joy)):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            self._joysticks.append(joy)

        # Fonts
        self._hud_font = pygame.font.SysFont(None, 26, bold=True)
        self._big_font = pygame.font.SysFont(None, 64, bold=True)
        self._med_font = pygame.font.SysFont(None, 36, bold=True)

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> str:
        """Play the dungeon.  Returns ``"complete"``, ``"dead"``, or
        ``"exit"``."""
        self._reset()
        self._show_banner("DUNGEON START!", (80, 200, 255), frames=90)

        while True:
            self._clock.tick(self.fps)
            result = self._handle_events()
            if result:
                return result

            self._update()
            self._update_camera()
            self._draw()
            pygame.display.flip()
            self._frame += 1

            # All players dead
            if all(not p.alive for p in self._players):
                self._show_overlay("ALL DEAD", (230, 60, 60), (100, 0, 0, 180))
                return "dead"

            # Victory: all generators gone + alive player on exit
            if self._check_victory():
                self._show_overlay("DUNGEON CLEARED!", (80, 240, 120),
                                   (0, 80, 0, 160))
                return "complete"

    # ── Initialisation ────────────────────────────────────────────────────────

    def _reset(self) -> None:
        # Player spawn positions (staggered inside START room)
        spawn_offsets = [(-20, -15), (20, -15), (-20, 15), (20, 15)]
        sx, sy = _ROOM_START.centerx, _ROOM_START.centery

        # P1 always uses keyboard (+joystick[0] if present)
        j0 = self._joysticks[0] if self._joysticks else None
        self._players: list[_GPlayer] = [
            _GPlayer(sx + spawn_offsets[0][0], sy + spawn_offsets[0][1],
                     0, joystick=j0)
        ]
        # P2–P4: one player per additional joystick
        for i in range(1, min(4, len(self._joysticks))):
            ox, oy = spawn_offsets[i]
            self._players.append(
                _GPlayer(sx + ox, sy + oy, i, joystick=self._joysticks[i])
            )

        # Generators
        self._generators: list[_Generator] = [
            _Generator(gx, gy, ti) for gx, gy, ti in _GEN_DEFS
        ]

        # Enemies (start empty; generators fill them)
        self._enemies: list[_GEnemy] = []

        # Items
        self._items: list[_Item] = [
            _Item(ix, iy, it) for ix, iy, it in _ITEM_DEFS
        ]

        # Door
        self._door = _Door(_DOOR_RECT)
        self._update_wall_rects()

        # Counters
        self._frame          = 0
        self._drain_counter  = 0
        self._kills          = 0
        self._gen_destroyed  = 0

        # HUD message
        self._msg_timer = 0
        self._msg_text  = ""
        self._msg_color = (255, 255, 255)

        # Hit flashes: list of (world_x, world_y, timer, colour)
        self._hit_flashes: list[tuple] = []

        # Camera (world-space top-left corner of the viewport)
        self._cam_x = 0.0
        self._cam_y = 0.0
        self._update_camera()

    def _update_wall_rects(self) -> None:
        """Rebuild the dynamic wall list (locked door acts as wall)."""
        self._wall_rects: list[pygame.Rect] = []
        if self._door.locked:
            self._wall_rects.append(self._door.rect)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sfx(self, name: str) -> None:
        try:
            self.sfx.play(name)
        except Exception:
            pass

    def _show_msg(self, text: str, color: tuple, frames: int = 180) -> None:
        self._msg_text  = text
        self._msg_color = color
        self._msg_timer = frames

    # ── Event handling ────────────────────────────────────────────────────────

    def _handle_events(self) -> str | None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "exit"
        return None

    # ── Input ─────────────────────────────────────────────────────────────────

    def _read_player_input(self, p: _GPlayer
                           ) -> tuple[float, float, bool, bool]:
        """Return (dx, dy, atk_light, atk_heavy) for player *p*."""
        keys = pygame.key.get_pressed()
        kb1  = self.settings.keyboard

        dx, dy, atk_light, atk_heavy = 0.0, 0.0, False, False

        # P1 always gets keyboard
        if p.p_index == 0:
            if keys[kb1["move_left"]]:  dx -= 1.0
            if keys[kb1["move_right"]]: dx += 1.0
            if keys[kb1["move_up"]]:    dy -= 1.0
            if keys[kb1["move_down"]]:  dy += 1.0
            atk_light = bool(keys[kb1["punch"]])
            atk_heavy = bool(keys[kb1["kick"]])

        # Normalise diagonal keyboard input
        mag = math.hypot(dx, dy)
        if mag > 0:
            dx /= mag
            dy /= mag

        # Controller input (overrides / supplements keyboard)
        if p.joystick:
            joy = p.joystick
            # Left stick
            if joy.get_numaxes() >= 2:
                ax = joy.get_axis(0)
                ay = joy.get_axis(1)
                if abs(ax) > AXIS_DEADZONE or abs(ay) > AXIS_DEADZONE:
                    jmag = math.hypot(ax, ay)
                    dx = ax / max(jmag, 1.0)
                    dy = ay / max(jmag, 1.0)
            # D-pad
            if joy.get_numhats() > 0:
                hx, hy = joy.get_hat(0)
                if hx or hy:
                    dx, dy = float(hx), float(-hy)
            # Buttons
            n_btn = joy.get_numbuttons()
            if n_btn > _BTN_LIGHT and joy.get_button(_BTN_LIGHT):
                atk_light = True
            if n_btn > _BTN_HEAVY and joy.get_button(_BTN_HEAVY):
                atk_heavy = True

        if math.hypot(dx, dy) > 0:
            p.last_dir = math.atan2(dy, dx)

        return dx, dy, atk_light, atk_heavy

    # ── Walkability ───────────────────────────────────────────────────────────

    def _can_place(self, x: float, y: float, r: float) -> bool:
        """True if a circle of radius *r* centred at (*x*, *y*) fits in the
        walkable floor without overlapping a wall block."""
        for px, py in ((x, y),
                       (x - r, y), (x + r, y),
                       (x, y - r), (x, y + r)):
            in_floor = any(rect.collidepoint(px, py) for rect in _FLOOR_RECTS)
            in_wall  = any(rect.collidepoint(px, py) for rect in self._wall_rects)
            if not in_floor or in_wall:
                return False
        return True

    def _move_entity(self, x: float, y: float,
                     dx: float, dy: float,
                     r: float, speed: float) -> tuple[float, float]:
        """Attempt to move; fall back to axis-aligned sliding if blocked."""
        nx = x + dx * speed
        ny = y + dy * speed
        if self._can_place(nx, ny, r):
            return nx, ny
        if self._can_place(nx, y, r):
            return nx, y
        if self._can_place(x, ny, r):
            return x, ny
        return x, y

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self) -> None:
        # Health drain: all alive players lose 1 HP every _HEALTH_DRAIN_FRAMES
        self._drain_counter += 1
        if self._drain_counter >= _HEALTH_DRAIN_FRAMES:
            self._drain_counter = 0
            for p in self._players:
                if p.alive:
                    p.hp = max(0, p.hp - 1)
                    if p.hp <= 0:
                        p.alive = False

        # Players
        for p in self._players:
            if p.alive:
                self._update_player(p)

        # Enemies
        surviving = []
        for e in self._enemies:
            if e.alive:
                self._update_enemy(e)
                surviving.append(e)
        self._enemies = surviving

        # Generators
        self._update_generators()

        # Items
        self._update_items()

        # Door
        self._update_door()

        # Decay hit flashes
        self._hit_flashes = [
            (x, y, t - 1, c) for x, y, t, c in self._hit_flashes if t > 1
        ]

        # Message countdown
        if self._msg_timer > 0:
            self._msg_timer -= 1

    def _update_player(self, p: _GPlayer) -> None:
        dx, dy, atk_light, atk_heavy = self._read_player_input(p)

        # Movement
        p.x, p.y = self._move_entity(
            p.x, p.y, dx, dy, _PLAYER_RADIUS, _PLAYER_SPEED
        )
        if math.hypot(dx, dy) > 0:
            p.facing = p.last_dir

        # Attack cooldown
        if p.atk_cd > 0:
            p.atk_cd -= 1

        # Attack phase
        if p.atk_timer > 0:
            p.atk_timer -= 1
            if p.atk_heavy:
                total   = _HEAVY_ANTICIPATION + _HEAVY_STRIKE + _HEAVY_RECOVERY
                s_start = _HEAVY_ANTICIPATION
                s_end   = _HEAVY_ANTICIPATION + _HEAVY_STRIKE
            else:
                total   = _LIGHT_ANTICIPATION + _LIGHT_STRIKE + _LIGHT_RECOVERY
                s_start = _LIGHT_ANTICIPATION
                s_end   = _LIGHT_ANTICIPATION + _LIGHT_STRIKE

            elapsed = total - p.atk_timer
            if elapsed < s_start:
                p.atk_phase = "anticipation"
            elif elapsed < s_end:
                p.atk_phase = "strike"
                self._apply_player_hits(p)
            else:
                p.atk_phase = "recovery"

            if p.atk_timer == 0:
                p.atk_phase = ""

        elif p.atk_cd == 0:
            if atk_heavy:
                self._start_attack(p, heavy=True)
            elif atk_light:
                self._start_attack(p, heavy=False)

        # Invulnerability countdown
        if p.invuln > 0:
            p.invuln -= 1

    def _start_attack(self, p: _GPlayer, heavy: bool) -> None:
        p.atk_heavy   = heavy
        p.atk_timer   = (
            _HEAVY_ANTICIPATION + _HEAVY_STRIKE + _HEAVY_RECOVERY
            if heavy else
            _LIGHT_ANTICIPATION + _LIGHT_STRIKE + _LIGHT_RECOVERY
        )
        p.atk_cd      = _HEAVY_COOLDOWN if heavy else _LIGHT_COOLDOWN
        p.atk_phase   = "anticipation"
        p.atk_hit_ids = set()
        p.gen_hit_ids = set()

    def _apply_player_hits(self, p: _GPlayer) -> None:
        """Deal damage to enemies and generators inside this player's attack arc."""
        if p.atk_heavy:
            atk_range, arc, damage, knockback = (
                _HEAVY_RANGE, _HEAVY_ARC, _HEAVY_DAMAGE, _HEAVY_KNOCKBACK)
        else:
            atk_range, arc, damage, knockback = (
                _LIGHT_RANGE, _LIGHT_ARC, _LIGHT_DAMAGE, _LIGHT_KNOCKBACK)

        angle    = p.facing
        half_arc = arc * 0.5

        def _in_arc(tx: float, ty: float, target_r: float) -> tuple[bool, float]:
            ex, ey = tx - p.x, ty - p.y
            dist   = math.hypot(ex, ey)
            if dist > atk_range + target_r:
                return False, dist
            if dist < 0.001:
                return True, 0.0
            ea   = math.atan2(ey, ex)
            diff = abs(((ea - angle + math.pi) % math.tau) - math.pi)
            return diff <= half_arc, dist

        # ── Hit enemies ──────────────────────────────────────────────────────
        for e in self._enemies:
            if id(e) in p.atk_hit_ids:
                continue
            hit, dist = _in_arc(e.x, e.y, e.radius)
            if not hit:
                continue
            p.atk_hit_ids.add(id(e))
            e.hp -= damage
            e.hurt_timer = 10
            if e.hp <= 0:
                e.alive = False
                self._kills += 1
                p.score  += 10
            else:
                ex, ey = e.x - p.x, e.y - p.y
                if dist > 0.001:
                    kbx = (ex / dist) * knockback * (1.0 - e.knockback_resist)
                    kby = (ey / dist) * knockback * (1.0 - e.knockback_resist)
                else:
                    kbx, kby = knockback * (1.0 - e.knockback_resist), 0.0
                e.vx += kbx
                e.vy += kby
            self._hit_flashes.append((e.x, e.y, 8, (255, 220, 60)))
            self._sfx("enemy_hurt")

        # ── Hit generators ────────────────────────────────────────────────────
        for gen in self._generators:
            if not gen.alive or id(gen) in p.gen_hit_ids:
                continue
            hit, _ = _in_arc(gen.x, gen.y, _GEN_RADIUS)
            if not hit:
                continue
            p.gen_hit_ids.add(id(gen))
            gen.hp -= damage
            gen.hurt_timer = 10
            if gen.hp <= 0:
                gen.alive = False
                self._gen_destroyed += 1
                p.score += 50
                self._hit_flashes.append((gen.x, gen.y, 20, (255, 140, 20)))
                self._sfx("break")
                remaining = sum(1 for g in self._generators if g.alive)
                if remaining == 0:
                    self._show_msg(
                        "ALL GENERATORS DOWN!  Find the exit!", (80, 240, 120), 300
                    )
                else:
                    self._show_msg(
                        f"Generator destroyed!  {remaining} remaining.", (220, 160, 40), 150
                    )
            else:
                self._hit_flashes.append((gen.x, gen.y, 10, (255, 180, 40)))
                self._sfx("impact")

    def _nearest_player(self, x: float, y: float) -> "_GPlayer | None":
        """Return the nearest alive player to (*x*, *y*)."""
        best, best_d = None, 1e18
        for p in self._players:
            if not p.alive:
                continue
            d = math.hypot(p.x - x, p.y - y)
            if d < best_d:
                best_d = d
                best   = p
        return best

    def _update_enemy(self, e: _GEnemy) -> None:
        target = self._nearest_player(e.x, e.y)
        if target is None:
            return  # no alive players; enemy idles

        pdx  = target.x - e.x
        pdy  = target.y - e.y
        dist = math.hypot(pdx, pdy)
        if dist > 0.001:
            e.facing = math.atan2(pdy, pdx)

        # Decay knockback
        e.vx *= 0.75
        e.vy *= 0.75
        if abs(e.vx) < 0.1:
            e.vx = 0.0
        if abs(e.vy) < 0.1:
            e.vy = 0.0

        # Chase
        engage_dist = e.attack_range + _PLAYER_RADIUS
        if dist > engage_dist:
            nx = e.x + (pdx / dist) * e.speed + e.vx
            ny = e.y + (pdy / dist) * e.speed + e.vy
        else:
            nx = e.x + e.vx
            ny = e.y + e.vy
        e.x, e.y = self._move_entity(e.x, e.y,
                                     nx - e.x, ny - e.y,
                                     e.radius, 1.0)

        # Hurt timer
        if e.hurt_timer > 0:
            e.hurt_timer -= 1

        # Attack logic
        if e.atk_cd > 0:
            e.atk_cd -= 1

        if e.atk_timer > 0:
            e.atk_timer -= 1
            if e.atk_timer == 0:
                # Attack resolves
                check = math.hypot(target.x - e.x, target.y - e.y)
                if check <= engage_dist and target.invuln == 0 and target.alive:
                    target.hp    -= e.damage
                    target.invuln = _PLAYER_INVULN_FRAMES
                    if target.hp <= 0:
                        target.alive = False
                    self._hit_flashes.append(
                        (target.x, target.y, 12, (255, 80, 80))
                    )
                    self._sfx("player_hurt")
        elif e.atk_cd == 0 and dist <= engage_dist:
            e.atk_timer = e.attack_wind
            e.atk_cd    = e.attack_cooldown

    def _update_generators(self) -> None:
        """Tick each generator; spawn an enemy if the timer fires."""
        total_enemies = len(self._enemies)
        for gen in self._generators:
            if not gen.alive:
                continue
            # Pause while enemy cap is reached
            if total_enemies >= _GEN_MAX_ENEMIES:
                continue
            gen.spawn_timer -= 1
            if gen.spawn_timer <= 0:
                self._spawn_from_generator(gen)
                # Spawn rate gradually increases (pressure loop)
                elapsed_waves = self._kills // max(1, len(self._players))
                interval = max(
                    _GEN_SPAWN_MIN,
                    _GEN_SPAWN_BASE - elapsed_waves * 4
                )
                gen.spawn_timer = interval + random.randint(-20, 20)
                total_enemies  += 1   # update local count

    def _spawn_from_generator(self, gen: _Generator) -> None:
        """Spawn a single enemy near *gen*."""
        etype = gen.table[gen.spawn_idx % len(gen.table)]
        gen.spawn_idx += 1

        # Pick a spawn point offset from the generator centre
        for _ in range(12):
            angle = random.uniform(0, math.tau)
            dist  = _GEN_RADIUS + 20 + random.uniform(0, 30)
            sx    = gen.x + math.cos(angle) * dist
            sy    = gen.y + math.sin(angle) * dist
            if self._can_place(sx, sy, _ENEMY_TYPES[etype]["radius"]):
                self._enemies.append(_GEnemy(sx, sy, etype))
                return
        # Fallback: spawn directly on the generator
        self._enemies.append(_GEnemy(gen.x, gen.y, etype))

    def _update_items(self) -> None:
        """Collect items when an alive player walks close enough."""
        for item in self._items:
            if item.collected:
                continue
            item.bob += 0.07
            for p in self._players:
                if not p.alive:
                    continue
                if math.hypot(p.x - item.x, p.y - item.y) < _PLAYER_RADIUS + 14:
                    item.collected = True
                    if item.item_type == "key":
                        p.keys_held += 1
                        self._show_msg(
                            f"{p.label} picked up the KEY!", _KEY_COLOR, 200
                        )
                        self._sfx("punch")  # positive feedback sound
                    else:  # food
                        healed = min(40, p.max_hp - p.hp)
                        p.hp   = min(p.max_hp, p.hp + 40)
                        self._show_msg(
                            f"{p.label} ate food  (+{healed} HP)", _FOOD_COLOR, 120
                        )
                        self._sfx("punch")
                    break

    def _update_door(self) -> None:
        """Unlock the door when a key-holding player is close enough."""
        if not self._door.locked:
            if self._door.unlock_flash > 0:
                self._door.unlock_flash -= 1
            return
        cx = self._door.rect.centerx
        cy = self._door.rect.centery
        for p in self._players:
            if p.alive and p.keys_held > 0:
                if math.hypot(p.x - cx, p.y - cy) < 60:
                    p.keys_held -= 1
                    self._door.locked       = False
                    self._door.unlock_flash = 90
                    self._update_wall_rects()
                    self._show_msg("Door unlocked!", (180, 220, 80), 180)
                    self._sfx("break")
                    break

    def _update_camera(self) -> None:
        """Smooth camera tracking the centroid of all alive players."""
        alive = [p for p in self._players if p.alive]
        if not alive:
            return
        avg_x = sum(p.x for p in alive) / len(alive)
        avg_y = sum(p.y for p in alive) / len(alive)
        target_cx = avg_x - self.width  / 2
        target_cy = avg_y - self.height / 2
        target_cx = max(0.0, min(float(_WORLD_W - self.width),  target_cx))
        target_cy = max(0.0, min(float(_WORLD_H - self.height), target_cy))
        # Lerp for smooth scroll
        self._cam_x += (target_cx - self._cam_x) * 0.12
        self._cam_y += (target_cy - self._cam_y) * 0.12

    def _check_victory(self) -> bool:
        """True when all generators are destroyed and a player reaches the exit."""
        if any(g.alive for g in self._generators):
            return False
        for p in self._players:
            if p.alive and _EXIT_RECT.collidepoint(int(p.x), int(p.y)):
                return True
        return False

    # ── Draw helpers (world → screen) ─────────────────────────────────────────

    def _wx(self, world_x: float) -> int:
        return int(world_x - self._cam_x)

    def _wy(self, world_y: float) -> int:
        return int(world_y - self._cam_y)

    def _wrect(self, world_rect: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(
            world_rect.x - int(self._cam_x),
            world_rect.y - int(self._cam_y),
            world_rect.width,
            world_rect.height,
        )

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.screen.fill(_WALL_COLOR)
        self._draw_dungeon()
        self._draw_exit_zone()
        self._draw_door()
        self._draw_items()
        self._draw_generators()
        self._draw_enemies()
        self._draw_attack_arcs()
        self._draw_players()
        self._draw_hit_flashes()
        self._draw_hud()
        if self._msg_timer > 0:
            self._draw_msg()

    def _draw_dungeon(self) -> None:
        """Draw the tiled floor for every room and corridor rect."""
        cx, cy = int(self._cam_x), int(self._cam_y)
        for room in _FLOOR_RECTS:
            sr = self._wrect(room)
            # Base floor fill
            pygame.draw.rect(self.screen, _FLOOR_COLOR, sr)
            # Checker tiles
            for tx in range(room.left, room.right, _TILE_SIZE):
                for ty in range(room.top, room.bottom, _TILE_SIZE):
                    if (tx // _TILE_SIZE + ty // _TILE_SIZE) % 2 == 0:
                        w  = min(_TILE_SIZE, room.right  - tx)
                        h  = min(_TILE_SIZE, room.bottom - ty)
                        tr = pygame.Rect(tx - cx, ty - cy, w, h)
                        pygame.draw.rect(self.screen, _FLOOR_TILE_COL, tr)
            # Inner edge highlight
            pygame.draw.rect(self.screen, _WALL_INNER_COL, sr, 3)

        # Room labels (small, for navigation aid)
        labels = [
            (_ROOM_START, "START"),
            (_ROOM_2,     "ROOM 2"),
            (_ROOM_3,     "ROOM 3"),
            (_ROOM_4,     "ROOM 4"),
        ]
        for rect, lbl in labels:
            tx = rect.x + 6 - int(self._cam_x)
            ty = rect.y + 5 - int(self._cam_y)
            surf = self._hud_font.render(lbl, True, (70, 70, 88))
            self.screen.blit(surf, (tx, ty))

    def _draw_exit_zone(self) -> None:
        """Draw the exit zone marker in ROOM 3."""
        all_gens_dead = not any(g.alive for g in self._generators)
        color = _EXIT_COLOR if all_gens_dead else (100, 100, 40)
        sr    = self._wrect(_EXIT_RECT)
        # Pulsing fill
        pulse = int(30 * math.sin(self._frame * 0.08)) if all_gens_dead else 0
        fill  = pygame.Surface((sr.width, sr.height), pygame.SRCALPHA)
        fill.fill((*color[:3], 60 + pulse))
        self.screen.blit(fill, sr.topleft)
        pygame.draw.rect(self.screen, color, sr, 3)
        lbl = self._hud_font.render("EXIT", True, color)
        self.screen.blit(lbl, (sr.centerx - lbl.get_width() // 2,
                                sr.centery - lbl.get_height() // 2))

    def _draw_door(self) -> None:
        if self._door.unlock_flash > 0:
            color = _DOOR_OPEN_COL
        elif self._door.locked:
            color = _DOOR_COLOR
        else:
            return  # open door – no obstacle to draw
        sr = self._wrect(self._door.rect)
        pygame.draw.rect(self.screen, color, sr)
        pygame.draw.rect(self.screen, (200, 160, 60), sr, 3)
        if self._door.locked:
            lbl = self._hud_font.render("🔒", True, (220, 180, 40))
            # Fallback if emoji not rendered
            lbl2 = self._hud_font.render("KEY", True, (220, 180, 40))
            surf = lbl if lbl.get_width() < 40 else lbl2
            self.screen.blit(surf, (sr.centerx - surf.get_width() // 2,
                                    sr.centery - surf.get_height() // 2))

    def _draw_items(self) -> None:
        for item in self._items:
            if item.collected:
                continue
            sx = self._wx(item.x)
            sy = self._wy(item.y) + int(math.sin(item.bob) * 3)
            if item.item_type == "key":
                self._draw_key(sx, sy)
            else:
                self._draw_food(sx, sy)

    def _draw_key(self, sx: int, sy: int) -> None:
        r = 9
        pygame.draw.circle(self.screen, _KEY_COLOR, (sx, sy), r, 3)
        pygame.draw.line(self.screen, _KEY_COLOR, (sx + r, sy), (sx + r + 14, sy), 3)
        pygame.draw.line(self.screen, _KEY_COLOR,
                         (sx + r + 8, sy), (sx + r + 8, sy + 5), 2)
        pygame.draw.line(self.screen, _KEY_COLOR,
                         (sx + r + 13, sy), (sx + r + 13, sy + 5), 2)

    def _draw_food(self, sx: int, sy: int) -> None:
        r = 10
        # Drumstick shape: circle + small elongated stub
        pygame.draw.circle(self.screen, _FOOD_COLOR, (sx, sy), r)
        pygame.draw.ellipse(self.screen, (40, 160, 40),
                            (sx + r - 4, sy - 4, 12, 8))
        pygame.draw.circle(self.screen, (180, 255, 180), (sx, sy), r, 2)

    def _draw_generators(self) -> None:
        for gen in self._generators:
            self._draw_generator(gen)

    def _draw_generator(self, gen: _Generator) -> None:
        sx = self._wx(gen.x)
        sy = self._wy(gen.y)
        r  = _GEN_RADIUS

        if not gen.alive:
            # Rubble
            pygame.draw.circle(self.screen, _GEN_DEAD_COL, (sx, sy), r // 2)
            return

        color = _GEN_COLOR
        dark  = _GEN_DARK
        if gen.hurt_timer > 0:
            gen.hurt_timer -= 1
            blend = min(1.0, gen.hurt_timer / 6.0)
            color = tuple(int(color[i] + (255 - color[i]) * blend * 0.8)
                          for i in range(3))

        # Drop shadow
        pygame.draw.ellipse(self.screen, (20, 20, 25),
                            (sx - r, sy + r - 4, r * 2, r // 2 + 4))

        # Rotating outer polygon (6-sided)
        rot = (self._frame * 0.018) % math.tau
        pts = [
            (sx + int(math.cos(rot + i * math.tau / 6) * r),
             sy + int(math.sin(rot + i * math.tau / 6) * r))
            for i in range(6)
        ]
        pygame.draw.polygon(self.screen, dark, pts)
        pygame.draw.polygon(self.screen, color, pts, 3)

        # Inner pulsing core
        pulse_r = max(4, int(r * 0.45 + math.sin(self._frame * 0.12) * 3))
        pygame.draw.circle(self.screen, (255, 200, 40), (sx, sy), pulse_r)

        # HP bar
        if gen.hp < gen.max_hp:
            bw, bh = r * 2, 5
            bx, by = sx - r, sy - r - 10
            pygame.draw.rect(self.screen, (40, 40, 40), (bx, by, bw, bh))
            filled = max(0, int(bw * gen.hp / gen.max_hp))
            pygame.draw.rect(self.screen, (220, 120, 30), (bx, by, filled, bh))

        # Label
        lbl = self._hud_font.render("GEN", True, (255, 180, 40))
        self.screen.blit(lbl, (sx - lbl.get_width() // 2, sy + r + 4))

    def _draw_enemies(self) -> None:
        for e in self._enemies:
            self._draw_enemy(e)

    def _draw_enemy(self, e: _GEnemy) -> None:
        sx = self._wx(e.x)
        sy = self._wy(e.y)
        r  = e.radius
        color = e.color
        dark  = e.dark_color

        if e.hurt_timer > 0:
            blend = min(1.0, e.hurt_timer / 6.0)
            color = tuple(int(color[i] + (255 - color[i]) * blend * 0.8)
                          for i in range(3))

        pygame.draw.ellipse(self.screen, (20, 20, 25),
                            (sx - r, sy + r - 4, r * 2, r // 2 + 3))
        pygame.draw.circle(self.screen, color, (sx, sy), r)
        pygame.draw.circle(self.screen, dark,  (sx, sy), r, 2)

        fa    = e.facing
        dot_x = int(sx + math.cos(fa) * (r - 4))
        dot_y = int(sy + math.sin(fa) * (r - 4))
        pygame.draw.circle(self.screen, dark, (dot_x, dot_y), max(3, r // 4))

        if e.atk_timer > 0:
            pygame.draw.circle(self.screen, (255, 160, 40), (sx, sy), r + 3, 2)

        if e.hp < e.max_hp:
            bw, bh = r * 2, 4
            bx, by = sx - r, sy - r - 9
            pygame.draw.rect(self.screen, (40, 40, 40), (bx, by, bw, bh))
            filled = max(0, int(bw * e.hp / e.max_hp))
            pygame.draw.rect(self.screen, (220, 60, 60), (bx, by, filled, bh))

    def _draw_attack_arcs(self) -> None:
        """Draw attack arcs for all attacking players."""
        for p in self._players:
            if not p.alive or p.atk_phase not in ("anticipation", "strike"):
                continue
            angle = p.facing
            if p.atk_heavy:
                atk_range, arc = _HEAVY_RANGE, _HEAVY_ARC
                c_strike  = (255, 200, 60, 160)
                c_antic   = (240, 140, 40, 80)
            else:
                atk_range, arc = _LIGHT_RANGE, _LIGHT_ARC
                c_strike  = (255, 240, 80, 140)
                c_antic   = (200, 220, 60, 60)

            color = c_strike if p.atk_phase == "strike" else c_antic
            pts   = [(self._wx(p.x), self._wy(p.y))]
            for i in range(15):
                a = angle - arc * 0.5 + arc * i / 14
                pts.append((
                    self._wx(p.x + math.cos(a) * atk_range),
                    self._wy(p.y + math.sin(a) * atk_range),
                ))
            arc_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.polygon(arc_surf, color, pts)
            self.screen.blit(arc_surf, (0, 0))

    def _draw_players(self) -> None:
        for p in self._players:
            self._draw_player(p)

    def _draw_player(self, p: _GPlayer) -> None:
        if not p.alive:
            return
        # Flicker when invulnerable
        if p.invuln > 0 and (self._frame // 3) % 2 == 0:
            return

        sx = self._wx(p.x)
        sy = self._wy(p.y)
        r  = _PLAYER_RADIUS

        pygame.draw.ellipse(self.screen, (20, 20, 25),
                            (sx - r, sy + r - 3, r * 2, r // 2 + 2))
        pygame.draw.circle(self.screen, p.color, (sx, sy), r)
        pygame.draw.circle(self.screen, p.dark_color, (sx, sy), r, 2)

        # Facing nose
        fa     = p.facing
        nose_x = int(sx + math.cos(fa) * (r - 2))
        nose_y = int(sy + math.sin(fa) * (r - 2))
        pygame.draw.circle(self.screen, (220, 240, 255), (nose_x, nose_y),
                           max(3, r // 4))

        # Arms
        arm_len = r + 7
        for side in (-1, 1):
            aa = fa + side * math.radians(50)
            ax = int(sx + math.cos(aa) * arm_len)
            ay = int(sy + math.sin(aa) * arm_len)
            pygame.draw.line(self.screen, p.dark_color, (sx, sy), (ax, ay), 3)
            pygame.draw.circle(self.screen, p.color, (ax, ay), 3)

        # Player label above head
        lbl = self._hud_font.render(p.label, True, p.color)
        self.screen.blit(lbl, (sx - lbl.get_width() // 2, sy - r - 16))

        # Key icon
        if p.keys_held > 0:
            ki = self._hud_font.render(f"🔑×{p.keys_held}", True, _KEY_COLOR)
            if ki.get_width() > 30:
                ki = self._hud_font.render(f"KEY×{p.keys_held}", True, _KEY_COLOR)
            self.screen.blit(ki, (sx - ki.get_width() // 2, sy + r + 3))

    def _draw_hit_flashes(self) -> None:
        for wx, wy, t, color in self._hit_flashes:
            sx, sy = self._wx(wx), self._wy(wy)
            r      = max(4, int(8 + (8 - t) * 1.5))
            alpha  = min(255, t * 30)
            surf   = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*color[:3], alpha), (r, r), r)
            self.screen.blit(surf, (sx - r, sy - r))

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hud(self) -> None:
        self._draw_player_bars()
        self._draw_gen_counter()
        self._draw_kill_count()
        if self._frame < _HINT_FRAMES:
            self._draw_controls_hint()
        self._draw_minimap()

    def _draw_player_bars(self) -> None:
        """Draw one HP bar per player in the top-left corner."""
        for i, p in enumerate(self._players):
            by = 12 + i * (_HP_BAR_H + 20)
            bx = 14
            # Background
            pygame.draw.rect(self.screen, _HP_BG_COLOR,
                             (bx, by, _HP_BAR_W, _HP_BAR_H))
            # Fill
            ratio  = max(0, p.hp / p.max_hp)
            filled = int(_HP_BAR_W * ratio)
            bar_color = _HP_LOW_COLOR if p.hp <= _HP_WARN_THRESH else _HP_COLOR
            if p.alive:
                pygame.draw.rect(self.screen, bar_color,
                                 (bx, by, filled, _HP_BAR_H))
            # Border
            pygame.draw.rect(self.screen, (180, 180, 180),
                             (bx, by, _HP_BAR_W, _HP_BAR_H), 1)
            # Label
            lbl = self._hud_font.render(
                p.label + (f"  {p.hp}" if p.alive else "  DEAD"),
                True, p.color
            )
            self.screen.blit(lbl, (bx + _HP_BAR_W + 6, by - 1))
            # "NEEDS FOOD BADLY" warning
            if p.alive and p.hp <= _HP_WARN_THRESH:
                warn = self._hud_font.render(
                    f"{p.label} NEEDS FOOD BADLY!", True, (255, 60, 60)
                )
                wx_pos = self.width // 2 - warn.get_width() // 2
                wy_pos = self.height - 56 - i * 24
                self.screen.blit(warn, (wx_pos, wy_pos))

    def _draw_gen_counter(self) -> None:
        """Show remaining generator count top-right."""
        alive = sum(1 for g in self._generators if g.alive)
        total = len(self._generators)
        color = (80, 220, 80) if alive == 0 else (220, 120, 40)
        txt   = self._hud_font.render(
            f"Generators: {alive}/{total}  Kills: {self._kills}",
            True, color
        )
        self.screen.blit(txt, (self.width - txt.get_width() - 12, 12))

    def _draw_kill_count(self) -> None:
        """Centre top: enemy count currently alive."""
        alive = len(self._enemies)
        if alive > 0:
            ec = self._hud_font.render(f"Enemies: {alive}", True, (220, 160, 60))
            self.screen.blit(ec, (self.width // 2 - ec.get_width() // 2, 12))

    def _draw_controls_hint(self) -> None:
        hint = ("Arrows: Move   Z: Light   X: Heavy   "
                "Approach door with KEY to unlock   ESC: Exit")
        hs   = self._hud_font.render(hint, True, (140, 140, 160))
        self.screen.blit(hs, (self.width // 2 - hs.get_width() // 2,
                               self.height - 22))

    def _draw_minimap(self) -> None:
        """Tiny top-right minimap showing room layout and player positions."""
        MAP_W, MAP_H = 120, 72
        SCALE_X = MAP_W / _WORLD_W
        SCALE_Y = MAP_H / _WORLD_H
        ox = self.width  - MAP_W - 12
        oy = self.height - MAP_H - 12

        bg = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        self.screen.blit(bg, (ox, oy))

        for rect in _FLOOR_RECTS:
            mr = pygame.Rect(
                ox + int(rect.x * SCALE_X),
                oy + int(rect.y * SCALE_Y),
                max(2, int(rect.width  * SCALE_X)),
                max(2, int(rect.height * SCALE_Y)),
            )
            pygame.draw.rect(self.screen, (70, 70, 85), mr)

        # Door on minimap
        if self._door.locked:
            dr = self._door.rect
            mm_dr = pygame.Rect(
                ox + int(dr.x * SCALE_X),
                oy + int(dr.y * SCALE_Y),
                max(2, int(dr.width  * SCALE_X)),
                max(2, int(dr.height * SCALE_Y)),
            )
            pygame.draw.rect(self.screen, _DOOR_COLOR, mm_dr)

        # Generators on minimap
        for gen in self._generators:
            gx = ox + int(gen.x * SCALE_X)
            gy = oy + int(gen.y * SCALE_Y)
            gc = (200, 120, 30) if gen.alive else (60, 60, 60)
            pygame.draw.circle(self.screen, gc, (gx, gy), 3)

        # Players on minimap
        for p in self._players:
            if p.alive:
                mx = ox + int(p.x * SCALE_X)
                my = oy + int(p.y * SCALE_Y)
                pygame.draw.circle(self.screen, p.color, (mx, my), 3)

        # Exit on minimap
        ex = _EXIT_RECT
        pygame.draw.rect(self.screen, _EXIT_COLOR, pygame.Rect(
            ox + int(ex.x * SCALE_X), oy + int(ex.y * SCALE_Y),
            max(2, int(ex.width * SCALE_X)), max(2, int(ex.height * SCALE_Y))
        ))

        pygame.draw.rect(self.screen, (100, 100, 120), (ox, oy, MAP_W, MAP_H), 1)

    def _draw_msg(self) -> None:
        """Centre-screen floating message."""
        alpha = min(255, self._msg_timer * 3)
        surf  = self._med_font.render(self._msg_text, True, self._msg_color)
        surf.set_alpha(alpha)
        self.screen.blit(surf, (
            self.width  // 2 - surf.get_width()  // 2,
            self.height // 2 - surf.get_height() // 2 - 60,
        ))

    # ── Overlays / banners ────────────────────────────────────────────────────

    def _show_banner(self, message: str, color: tuple, frames: int = 90) -> None:
        """Brief top-of-screen text shown at level start."""
        for f in range(frames):
            self._clock.tick(self.fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
            alpha = min(255, min(f * 10, (frames - f) * 6))
            self._draw()
            surf  = self._big_font.render(message, True, color)
            surf.set_alpha(alpha)
            self.screen.blit(surf, (
                self.width  // 2 - surf.get_width()  // 2,
                self.height // 2 - surf.get_height() // 2,
            ))
            pygame.display.flip()

    def _show_overlay(self, message: str, text_color: tuple,
                      bg_rgba: tuple) -> None:
        """Freeze-frame overlay shown for ~2 seconds.  ESC / Enter skips."""
        for _ in range(120):
            self._clock.tick(self.fps)
            self._draw()
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill(bg_rgba)
            self.screen.blit(overlay, (0, 0))
            txt = self._big_font.render(message, True, text_color)
            sub = self._hud_font.render("Press ESC or wait …",
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
