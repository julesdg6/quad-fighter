"""rampage_level.py

KAIJU MODE – a Rampage-style side-scrolling destruction level.

The player pilots a giant exoskeleton suit across a 2400px cityscape,
smashing buildings and battling helicopters, tanks, and planes.

Controls:
  LEFT / RIGHT  – move along ground
  UP            – climb building (when adjacent) / climb higher
  DOWN          – descend building
  Z             – punch (ground) or strike floor segment (climbing)
  X             – heavy smash (wider ground attack)
  ESC / Return  – exit

Win  : destroy 80%+ of all building floor segments
Lose : player HP reaches 0
"""

import math
import random

import pygame

# ── World / screen constants ──────────────────────────────────────────────────
_WORLD_W   = 2400
_GROUND_Y  = 520      # screen-space y of the ground line (world-fixed)
_WIN_DESTR = 0.80     # destruction fraction required to win

# ── Player ────────────────────────────────────────────────────────────────────
_PLR_H          = 120     # mech height (px)
_PLR_W          = 44      # mech width  (px)
_PLR_SPEED      = 180     # ground move speed (px/s)
_PLR_CLIMB_SPD  = 90      # vertical climb speed (px/s)
_PLR_MAX_HP     = 100
_PLR_INVULN     = 90      # invincibility frames after hit

# Attack geometry (world coords)
_PUNCH_RANGE_X  = 80      # horizontal reach of punch
_PUNCH_RANGE_Y  = 60      # vertical reach of punch
_SMASH_RANGE_X  = 140     # heavy smash horizontal reach
_SMASH_RANGE_Y  = 50
_ATK_DURATION   = 16      # frames attack box is active
_ATK_COOLDOWN   = 24

_PUNCH_DMG_ENEMY  = 30
_SMASH_DMG_ENEMY  = 50
_PUNCH_DMG_FLOOR  = 20
_SMASH_DMG_FLOOR  = 40

# ── Buildings ─────────────────────────────────────────────────────────────────
_FLOOR_HP       = 40
_FLOOR_H        = 60      # px per floor
_DEBRIS_LIFE    = 90      # frames

# ── Enemies ───────────────────────────────────────────────────────────────────
_HELI_HP        = 30
_TANK_HP        = 50
_PLANE_HP       = 20

_HELI_BULLET_DMG  = 8
_TANK_SHELL_DMG   = 15
_PLANE_BOMB_DMG   = 12

_HELI_SPAWN_FRAMES  = 480    # ~8s at 60fps
_TANK_SPAWN_FRAMES  = 720    # ~12s
_PLANE_SPAWN_FRAMES = 900    # ~15s
_MAX_HELIS  = 3
_MAX_TANKS  = 2
_MAX_PLANES = 2

# ── Physics ───────────────────────────────────────────────────────────────────
_DEBRIS_GRAVITY       = 300.0   # px/s² downward acceleration for debris chunks
_SHELL_GRAVITY        = 260.0   # px/s² downward acceleration for tank shells

# ── Projectile speeds ─────────────────────────────────────────────────────────
_HELI_BULLET_SPEED    = 220.0   # downward speed of helicopter bullets (px/s)
_TANK_SHELL_SPEED_H   = 160.0   # initial horizontal speed of tank shells (px/s)
_BOMB_FALL_SPEED      = 180.0   # initial downward speed of plane bombs (px/s)

# ── Camera ────────────────────────────────────────────────────────────────────
_CAM_SMOOTHING        = 6.0     # camera lerp rate (higher = snappier follow)
_BG_PARALLAX_FACTOR   = 0.3     # background scrolls at this fraction of camera speed

# ── Visual ────────────────────────────────────────────────────────────────────
_HELI_BLADE_ROT_SPEED = 720.0   # blade rotation speed (degrees/s)

# ── Colours ───────────────────────────────────────────────────────────────────
_SKY_TOP    = (8,  10, 24)
_SKY_BOT    = (20, 14, 44)
_GROUND_COL = (28, 26, 32)
_SILH_COL   = (14, 12, 20)   # background skyline silhouette

_PLR_BODY   = (60,  110, 200)
_PLR_ARMOR  = (40,   80, 160)
_PLR_VISOR  = (80,  220, 255)
_PLR_HURT   = (220,  60,  60)
_PLR_JOINT  = (30,   50, 100)

_BLDG_COLORS   = [(55, 55, 70), (48, 52, 68), (62, 58, 72), (44, 48, 62)]
_BLDG_WIN_COL  = (80, 70, 90)
_BLDG_DAMAGE   = (90, 45, 30)
_BLDG_DARK     = (28, 28, 36)

_HELI_COL   = (180,  55,  40)
_HELI_BLADE = (220, 120,  50)
_TANK_COL   = (60,  100,  40)
_TANK_DARK  = (40,   70,  25)
_PLANE_COL  = (160,  40,  40)

_BULLET_COL = (255, 220,  50)
_SHELL_COL  = (220, 160,  40)
_BOMB_COL   = (200,  60,  20)

_HUD_HP_FULL  = (60, 220, 80)
_HUD_HP_LOW   = (220, 60, 60)
_HUD_BG       = (0, 0, 0, 160)


# ── Utility ───────────────────────────────────────────────────────────────────

def _rnd(lo, hi):
    return random.uniform(lo, hi)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ── Internal game-object classes ──────────────────────────────────────────────

class _FloorSegment:
    def __init__(self, x, y, w, h, floor_idx):
        self.rect      = pygame.Rect(x, y, w, h)
        self.hp        = _FLOOR_HP
        self.max_hp    = _FLOOR_HP
        self.floor_idx = floor_idx
        self.alive     = True
        self.hit_flash = 0

    @property
    def destroyed(self):
        return not self.alive


class _Building:
    def __init__(self, wx, w, floors):
        """wx = world-x left edge, w = width, floors = number of floors."""
        self.wx     = wx
        self.w      = w
        self.floors = []
        self.color  = random.choice(_BLDG_COLORS)
        top_y = _GROUND_Y - floors * _FLOOR_H
        for i in range(floors):
            fy = top_y + i * _FLOOR_H
            self.floors.append(_FloorSegment(wx, fy, w, _FLOOR_H, i))

    @property
    def alive(self):
        return any(f.alive for f in self.floors)

    @property
    def top_world_y(self):
        return _GROUND_Y - len(self.floors) * _FLOOR_H

    def floor_at_y(self, world_y):
        """Return the _FloorSegment whose y-range contains world_y, or None."""
        for f in self.floors:
            if f.alive and f.rect.y <= world_y < f.rect.y + f.rect.h:
                return f
        return None

    def screen_rect(self, cam_x):
        """Bounding rect on screen."""
        sx = self.wx - cam_x
        return pygame.Rect(sx, self.top_world_y, self.w,
                           len(self.floors) * _FLOOR_H)


class _Debris:
    def __init__(self, wx, wy):
        self.wx  = float(wx)
        self.wy  = float(wy)
        self.vx  = _rnd(-60, 60)
        self.vy  = _rnd(-120, -40)
        self.w   = random.randint(6, 18)
        self.h   = random.randint(4, 10)
        self.life = _DEBRIS_LIFE
        self.col  = random.choice([_BLDG_DAMAGE, (110, 60, 40), (80, 70, 60)])

    def update(self, dt):
        self.vy  += _DEBRIS_GRAVITY * dt
        self.wx  += self.vx * dt
        self.wy  += self.vy * dt
        self.life -= 1


class _Helicopter:
    def __init__(self, wx, wy):
        self.wx        = float(wx)
        self.wy        = float(wy)
        self.vx        = _rnd(-60, 60)
        self.hp        = _HELI_HP
        self.max_hp    = _HELI_HP
        self.alive     = True
        self.hit_flash = 0
        self.fire_cd   = random.randint(90, 160)
        self.blade_rot = 0.0

    def update(self, dt, player_wx, cam_x):
        self.blade_rot += dt * _HELI_BLADE_ROT_SPEED
        self.wx += self.vx * dt
        # Gentle bob
        self.wy += math.sin(self.wx * 0.01) * _BG_PARALLAX_FACTOR
        # Reverse at screen edges (world coords)
        if self.wx < 80 or self.wx > _WORLD_W - 80:
            self.vx = -self.vx
        self.wx = _clamp(self.wx, 80, _WORLD_W - 80)
        if self.hit_flash > 0:
            self.hit_flash -= 1
        self.fire_cd -= 1

    @property
    def fire_ready(self):
        return self.fire_cd <= 0

    def reset_fire(self, interval):
        self.fire_cd = interval


class _Tank:
    def __init__(self, wx, facing):
        self.wx        = float(wx)
        self.wy        = _GROUND_Y - 30
        self.vx        = facing * _rnd(30, 55)
        self.facing    = facing
        self.hp        = _TANK_HP
        self.max_hp    = _TANK_HP
        self.alive     = True
        self.hit_flash = 0
        self.fire_cd   = random.randint(120, 200)

    def update(self, dt):
        self.wx += self.vx * dt
        if self.wx < 50 or self.wx > _WORLD_W - 50:
            self.vx   = -self.vx
            self.facing = 1 if self.vx > 0 else -1
        self.wx = _clamp(self.wx, 50, _WORLD_W - 50)
        if self.hit_flash > 0:
            self.hit_flash -= 1
        self.fire_cd -= 1

    @property
    def fire_ready(self):
        return self.fire_cd <= 0

    def reset_fire(self, interval):
        self.fire_cd = interval


class _Plane:
    def __init__(self, from_left):
        self.from_left = from_left
        if from_left:
            self.wx = -80.0
            self.vx = _rnd(340, 480)
        else:
            self.wx = _WORLD_W + 80.0
            self.vx = -_rnd(340, 480)
        self.wy        = _rnd(120, 200)
        self.hp        = _PLANE_HP
        self.max_hp    = _PLANE_HP
        self.alive     = True
        self.hit_flash = 0
        self.dropped   = False

    def update(self, dt):
        self.wx += self.vx * dt
        if self.hit_flash > 0:
            self.hit_flash -= 1

    @property
    def off_screen(self):
        return self.wx < -200 or self.wx > _WORLD_W + 200


class _Projectile:
    """Generic projectile: bullet / tank shell / bomb."""
    def __init__(self, kind, wx, wy, vx, vy, dmg):
        self.kind  = kind   # "bullet" | "shell" | "bomb"
        self.wx    = float(wx)
        self.wy    = float(wy)
        self.vx    = float(vx)
        self.vy    = float(vy)
        self.dmg   = dmg
        self.alive = True

    def update(self, dt):
        if self.kind == "shell":
            self.vy += _SHELL_GRAVITY * dt
        self.wx += self.vx * dt
        self.wy += self.vy * dt
        if self.wy > _GROUND_Y + 40 or self.wx < -100 or self.wx > _WORLD_W + 100:
            self.alive = False


# ── Main level class ──────────────────────────────────────────────────────────

class RampageLevel:
    """Self-contained Kaiju destruction level.

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
        self._clock   = pygame.time.Clock()

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self):
        """Play the rampage level.  Returns ``"complete"``, ``"dead"``, or
        ``"exit"``."""
        self._reset()
        self._show_title()
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
                self._show_overlay("YOU WERE DESTROYED",
                                   (230, 60, 60), (100, 0, 0, 160))
                return "dead"

            destr = self._destruction_pct()
            if destr >= _WIN_DESTR:
                self._show_overlay("CITY LEVELLED!",
                                   (80, 240, 120), (0, 80, 0, 140))
                return "complete"

    # ── State initialisation ──────────────────────────────────────────────────

    def _reset(self):
        self._frame = 0

        # Camera
        self._cam_x     = 0.0   # world-x of left screen edge

        # Player state
        self.player_wx   = 120.0
        self.player_wy   = float(_GROUND_Y - _PLR_H)
        self.player_hp   = _PLR_MAX_HP
        self._invuln     = 0
        self._facing     = 1    # +1 right, -1 left
        self._state      = "ground"   # "ground" | "climbing" | "jumping"

        # Climbing context
        self._climb_bldg  = None   # current _Building being climbed
        self._climb_wx    = 0.0    # player world-x while on building face

        # Attack state
        self._atk_type    = None   # "punch" | "smash" | None
        self._atk_timer   = 0
        self._atk_cd      = 0

        # Key-edge tracking (to avoid held-key repeat)
        self._key_z_prev  = False
        self._key_x_prev  = False
        self._key_up_prev = False

        # Buildings
        self._buildings = self._make_buildings()
        self._total_floors = sum(len(b.floors) for b in self._buildings)

        # Enemies
        self._helis  = []
        self._tanks  = []
        self._planes = []

        # Projectiles + debris
        self._projectiles = []
        self._debris      = []

        # Spawn timers (count-down frames)
        self._heli_spawn_cd  = _HELI_SPAWN_FRAMES // 2
        self._tank_spawn_cd  = _TANK_SPAWN_FRAMES
        self._plane_spawn_cd = _PLANE_SPAWN_FRAMES

    def _make_buildings(self):
        specs = [
            (200,  160, 4),
            (500,  180, 5),
            (900,  140, 3),
            (1200, 200, 5),
            (1600, 150, 4),
            (1950, 170, 4),
            (2200, 130, 3),
        ]
        buildings = []
        for wx, w, floors in specs:
            buildings.append(_Building(wx, w, floors))
        return buildings

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                    return "exit"
        return None

    def _read_input(self):
        keys = pygame.key.get_pressed()
        return {
            "left":  keys[pygame.K_LEFT],
            "right": keys[pygame.K_RIGHT],
            "up":    keys[pygame.K_UP],
            "down":  keys[pygame.K_DOWN],
            "z":     keys[pygame.K_z],
            "x":     keys[pygame.K_x],
        }

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self, dt):
        inp = self._read_input()
        if hasattr(self.acid, "tick"):
            self.acid.tick(dt)

        # Timers
        if self._invuln  > 0: self._invuln  -= 1
        if self._atk_cd  > 0: self._atk_cd  -= 1
        if self._atk_timer > 0:
            self._atk_timer -= 1
        else:
            self._atk_type = None

        # Player state machine
        if self._state == "ground":
            self._update_ground(inp, dt)
        elif self._state == "climbing":
            self._update_climbing(inp, dt)

        # Clamp player to world
        self.player_wx = _clamp(self.player_wx, 0, _WORLD_W - _PLR_W)

        # Smooth camera follow
        target_cam = self.player_wx - self.width // 2 + _PLR_W // 2
        target_cam = _clamp(target_cam, 0, _WORLD_W - self.width)
        self._cam_x += (target_cam - self._cam_x) * _CAM_SMOOTHING * dt

        # Spawn enemies
        self._spawn_enemies()

        # Update enemies
        self._update_helis(dt, inp)
        self._update_tanks(dt, inp)
        self._update_planes(dt, inp)

        # Update projectiles
        self._update_projectiles(dt)

        # Update debris
        for d in self._debris:
            d.update(dt)
        self._debris = [d for d in self._debris if d.life > 0]

        # Attack hits: vs buildings (ground / climbing)
        if self._atk_timer > 0:
            self._resolve_attack_hits()

        # Edge state tracking
        self._key_z_prev  = inp["z"]
        self._key_x_prev  = inp["x"]
        self._key_up_prev = inp["up"]

    def _update_ground(self, inp, dt):
        # Movement
        if inp["left"]:
            self.player_wx -= _PLR_SPEED * dt
            self._facing = -1
        if inp["right"]:
            self.player_wx += _PLR_SPEED * dt
            self._facing = 1
        # Keep on ground
        self.player_wy = _GROUND_Y - _PLR_H

        # Try to start climbing
        if inp["up"] and not self._key_up_prev:
            bldg = self._adjacent_building()
            if bldg:
                self._state      = "climbing"
                self._climb_bldg = bldg
                # Snap player to building face
                if self._facing > 0:
                    self._climb_wx = bldg.wx - _PLR_W
                else:
                    self._climb_wx = bldg.wx + bldg.w
                self.player_wx   = self._climb_wx

        # Attacks
        if inp["z"] and not self._key_z_prev and self._atk_cd <= 0:
            self._atk_type  = "punch"
            self._atk_timer = _ATK_DURATION
            self._atk_cd    = _ATK_COOLDOWN
            self.sfx.play("punch")
        if inp["x"] and not self._key_x_prev and self._atk_cd <= 0:
            self._atk_type  = "smash"
            self._atk_timer = _ATK_DURATION
            self._atk_cd    = _ATK_COOLDOWN
            self.sfx.play("kick")

    def _update_climbing(self, inp, dt):
        # Vertical movement
        if inp["up"]:
            self.player_wy -= _PLR_CLIMB_SPD * dt
        if inp["down"]:
            self.player_wy += _PLR_CLIMB_SPD * dt

        # Descend to ground
        if self.player_wy >= _GROUND_Y - _PLR_H:
            self.player_wy = _GROUND_Y - _PLR_H
            self._state    = "ground"
            self._climb_bldg = None
            return

        bldg = self._climb_bldg
        if bldg is None or not bldg.alive:
            self._state = "ground"
            self.player_wy = _GROUND_Y - _PLR_H
            return

        # Keep player pinned to building face
        self.player_wx = self._climb_wx

        # Clamp above building top
        top_y = bldg.top_world_y
        self.player_wy = max(top_y - _PLR_H // 2, self.player_wy)

        # Punch to damage floor while climbing
        if inp["z"] and not self._key_z_prev and self._atk_cd <= 0:
            self._atk_type  = "punch"
            self._atk_timer = _ATK_DURATION
            self._atk_cd    = _ATK_COOLDOWN
            self.sfx.play("punch")
            self._damage_adjacent_floor(bldg, _PUNCH_DMG_FLOOR)

    def _adjacent_building(self):
        """Return the first building the player is standing directly next to."""
        px     = self.player_wx
        pw     = _PLR_W
        margin = 20
        for b in self._buildings:
            if not b.alive:
                continue
            # Player right edge near building left edge
            if abs((px + pw) - b.wx) < margin:
                return b
            # Player left edge near building right edge
            if abs(px - (b.wx + b.w)) < margin:
                return b
        return None

    def _damage_adjacent_floor(self, bldg, damage):
        """Damage the floor segment aligned with the player's vertical centre."""
        mid_y = self.player_wy + _PLR_H // 2
        seg = bldg.floor_at_y(mid_y)
        if seg is None:
            # Nearest alive floor
            nearest = None
            best = 9999
            for f in bldg.floors:
                if f.alive:
                    dist = abs((f.rect.y + f.rect.h // 2) - mid_y)
                    if dist < best:
                        best, nearest = dist, f
            seg = nearest
        if seg:
            self._hit_floor(seg, damage)

    def _hit_floor(self, seg, damage):
        seg.hp      -= damage
        seg.hit_flash = 8
        self.sfx.play("impact")
        if seg.hp <= 0:
            seg.alive = False
            self.sfx.play("break")
            self._spawn_debris(seg.rect)
            # If entire building down, player falls
            if self._climb_bldg and not self._climb_bldg.alive:
                self._state    = "ground"
                self.player_wy = _GROUND_Y - _PLR_H
                self._climb_bldg = None

    def _spawn_debris(self, rect):
        cx = rect.x + rect.w // 2
        cy = rect.y + rect.h // 2
        for _ in range(random.randint(3, 5)):
            self._debris.append(_Debris(cx + _rnd(-rect.w//2, rect.w//2),
                                        cy + _rnd(-rect.h//2, rect.h//2)))

    def _resolve_attack_hits(self):
        """Apply attack damage to enemies currently in range."""
        if self._atk_type == "punch":
            rx = _PUNCH_RANGE_X
            ry = _PUNCH_RANGE_Y
            dmg = _PUNCH_DMG_ENEMY
        else:
            rx = _SMASH_RANGE_X
            ry = _SMASH_RANGE_Y
            dmg = _SMASH_DMG_ENEMY

        px = self.player_wx + _PLR_W // 2
        py = self.player_wy + _PLR_H // 2

        hit_any = False
        for h in self._helis:
            if not h.alive: continue
            if abs(h.wx - px) < rx and abs(h.wy - py) < ry + 60:
                h.hp -= dmg
                h.hit_flash = 8
                self.sfx.play("enemy_hurt")
                if h.hp <= 0:
                    h.alive = False
                hit_any = True

        for t in self._tanks:
            if not t.alive: continue
            if self._state == "ground":
                if abs(t.wx - px) < rx and abs(t.wy - py) < ry + 40:
                    t.hp -= dmg
                    t.hit_flash = 8
                    self.sfx.play("enemy_hurt")
                    if t.hp <= 0:
                        t.alive = False
                    hit_any = True

        for p in self._planes:
            if not p.alive: continue
            if abs(p.wx - px) < rx + 40 and abs(p.wy - py) < ry + 60:
                p.hp -= dmg
                p.hit_flash = 8
                self.sfx.play("enemy_hurt")
                if p.hp <= 0:
                    p.alive = False
                hit_any = True

        if hit_any and self._atk_type == "smash":
            # Also damage buildings in smash radius
            if self._state == "ground":
                for b in self._buildings:
                    if not b.alive: continue
                    bmid = b.wx + b.w // 2
                    if abs(bmid - px) < _SMASH_RANGE_X:
                        # Hit lowest alive floor
                        for f in reversed(b.floors):
                            if f.alive:
                                self._hit_floor(f, _SMASH_DMG_FLOOR)
                                break

    # ── Enemy spawning ────────────────────────────────────────────────────────

    def _spawn_enemies(self):
        destr = self._destruction_pct()
        # Escalate spawn rate with destruction
        scale = max(0.4, 1.0 - destr)

        self._heli_spawn_cd  -= 1
        self._tank_spawn_cd  -= 1
        self._plane_spawn_cd -= 1

        alive_helis  = sum(1 for h in self._helis  if h.alive)
        alive_tanks  = sum(1 for t in self._tanks  if t.alive)
        alive_planes = sum(1 for p in self._planes if p.alive)

        heli_interval  = int(_HELI_SPAWN_FRAMES  * scale)
        tank_interval  = int(_TANK_SPAWN_FRAMES  * scale)
        plane_interval = int(_PLANE_SPAWN_FRAMES * scale)

        if self._heli_spawn_cd <= 0 and alive_helis < _MAX_HELIS:
            side = random.choice([-1, 1])
            wx   = _WORLD_W + 60 if side > 0 else -60
            wy   = _rnd(60, 160)
            h    = _Helicopter(wx, wy)
            h.vx = -side * _rnd(40, 80)
            self._helis.append(h)
            self._heli_spawn_cd = heli_interval

        if self._tank_spawn_cd <= 0 and alive_tanks < _MAX_TANKS:
            side = random.choice([-1, 1])
            wx   = _WORLD_W - 60 if side < 0 else 60
            self._tanks.append(_Tank(wx, -side))
            self._tank_spawn_cd = tank_interval

        if self._plane_spawn_cd <= 0 and alive_planes < _MAX_PLANES:
            self._planes.append(_Plane(from_left=random.choice([True, False])))
            self._plane_spawn_cd = plane_interval

        # Prune dead
        self._helis  = [h for h in self._helis  if h.alive]
        self._tanks  = [t for t in self._tanks  if t.alive]
        self._planes = [p for p in self._planes if p.alive and not p.off_screen]

    # ── Enemy updates + firing ────────────────────────────────────────────────

    def _update_helis(self, dt, inp):
        px = self.player_wx + _PLR_W // 2
        for h in self._helis:
            h.update(dt, px, self._cam_x)
            if h.fire_ready:
                # Fire bullet toward player
                dx   = px - h.wx
                dy   = (self.player_wy + _PLR_H // 2) - h.wy
                dist = math.hypot(dx, dy) or 1
                spd  = _HELI_BULLET_SPEED
                self._projectiles.append(
                    _Projectile("bullet", h.wx, h.wy,
                                dx / dist * spd, dy / dist * spd,
                                _HELI_BULLET_DMG))
                self.sfx.play("enemy_attack")
                h.reset_fire(random.randint(100, 180))

    def _update_tanks(self, dt, inp):
        px = self.player_wx + _PLR_W // 2
        py = self.player_wy + _PLR_H // 2
        for t in self._tanks:
            t.update(dt)
            if t.fire_ready:
                # Arcing shell toward player
                dx   = px - t.wx
                dy   = py - t.wy
                # Choose vy so the shell arcs and reaches target
                travel  = abs(dx) or 1
                vx      = (dx / abs(dx)) * _TANK_SHELL_SPEED_H
                time_to = travel / abs(vx)
                vy      = (dy - 0.5 * _SHELL_GRAVITY * time_to * time_to) / max(time_to, 0.01)
                vy      = _clamp(vy, -400, -80)
                self._projectiles.append(
                    _Projectile("shell", t.wx, t.wy - 20, vx, vy,
                                _TANK_SHELL_DMG))
                self.sfx.play("boss_attack")
                t.reset_fire(random.randint(150, 240))

    def _update_planes(self, dt, inp):
        px = self.player_wx + _PLR_W // 2
        for p in self._planes:
            p.update(dt)
            # Drop bomb when roughly overhead
            if not p.dropped and abs(p.wx - px) < 120:
                self._projectiles.append(
                _Projectile("bomb", p.wx, p.wy, 0, _BOMB_FALL_SPEED, _PLANE_BOMB_DMG))
                self.sfx.play("boss_attack")
                p.dropped = True

    def _update_projectiles(self, dt):
        px = self.player_wx
        py = self.player_wy
        pw, ph = _PLR_W, _PLR_H
        surviving = []
        for proj in self._projectiles:
            proj.update(dt)
            if not proj.alive:
                continue
            # Player hit check
            if (self._invuln <= 0
                    and px < proj.wx < px + pw
                    and py < proj.wy < py + ph):
                self.player_hp = max(0, self.player_hp - proj.dmg)
                self._invuln   = _PLR_INVULN
                self.sfx.play("player_hurt")
                proj.alive = False
                continue
            surviving.append(proj)
        self._projectiles = surviving

    # ── Destruction metric ────────────────────────────────────────────────────

    def _destruction_pct(self):
        if self._total_floors == 0:
            return 1.0
        destroyed = sum(1 for b in self._buildings
                        for f in b.floors if not f.alive)
        return destroyed / self._total_floors

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        s  = self.screen
        cx = int(self._cam_x)

        self._draw_sky(s)
        self._draw_bg_silhouette(s, cx)
        self._draw_ground(s)
        self._draw_buildings(s, cx)
        self._draw_debris(s, cx)
        self._draw_projectiles(s, cx)
        self._draw_helis(s, cx)
        self._draw_tanks(s, cx)
        self._draw_planes(s, cx)
        self._draw_player(s, cx)
        self._draw_hud(s)

    def _draw_sky(self, s):
        for y in range(0, _GROUND_Y, 3):
            t = y / _GROUND_Y
            r = int(_SKY_TOP[0] + (_SKY_BOT[0] - _SKY_TOP[0]) * t)
            g = int(_SKY_TOP[1] + (_SKY_BOT[1] - _SKY_TOP[1]) * t)
            b = int(_SKY_TOP[2] + (_SKY_BOT[2] - _SKY_TOP[2]) * t)
            pygame.draw.rect(s, (r, g, b), (0, y, self.width, 3))

    def _draw_bg_silhouette(self, s, cam_x):
        """Distant city silhouette – scrolls at half speed (parallax)."""
        parallax = cam_x * _BG_PARALLAX_FACTOR
        widths  = [80, 60, 110, 70, 90, 65, 100, 55, 85, 75, 95, 50]
        heights = [160, 200, 180, 220, 140, 190, 170, 210, 150, 185, 165, 200]
        x = 0
        for i, (w, h) in enumerate(zip(widths, heights)):
            sx = x - int(parallax) % (sum(widths))
            pygame.draw.rect(s, _SILH_COL, (sx, _GROUND_Y - h, w - 4, h))
            # Windows
            win_col = (22, 22, 36)
            for wy_ in range(_GROUND_Y - h + 8, _GROUND_Y - 8, 18):
                for wx_ in range(sx + 6, sx + w - 8, 14):
                    if (i + wy_ + wx_) % 3 != 0:
                        pygame.draw.rect(s, win_col, (wx_, wy_, 6, 8))
            x += w + 10

    def _draw_ground(self, s):
        pygame.draw.rect(s, _GROUND_COL,
                         (0, _GROUND_Y, self.width, self.height - _GROUND_Y))
        # Ground line
        pygame.draw.line(s, (50, 48, 58), (0, _GROUND_Y), (self.width, _GROUND_Y), 2)

    def _draw_buildings(self, s, cam_x):
        for b in self._buildings:
            sx = b.wx - cam_x
            if sx > self.width + 20 or sx + b.w < -20:
                continue
            for seg in b.floors:
                if not seg.alive:
                    continue
                fy = seg.rect.y
                fw = seg.rect.w
                fh = seg.rect.h
                fsx = sx
                hp_ratio = seg.hp / seg.max_hp

                col = b.color
                if seg.hit_flash > 0:
                    col = _BLDG_DAMAGE
                    seg.hit_flash -= 1
                elif hp_ratio < 0.5:
                    # Blend toward damaged color
                    t   = 1.0 - hp_ratio * 2
                    col = (int(col[0] + (_BLDG_DAMAGE[0] - col[0]) * t),
                           int(col[1] + (_BLDG_DAMAGE[1] - col[1]) * t),
                           int(col[2] + (_BLDG_DAMAGE[2] - col[2]) * t))

                # Main floor rect
                pygame.draw.rect(s, col, (fsx, fy, fw, fh))
                # Floor divider line
                pygame.draw.line(s, _BLDG_DARK,
                                 (fsx, fy + fh - 1), (fsx + fw, fy + fh - 1), 1)
                # Structural outline
                pygame.draw.rect(s, _BLDG_DARK, (fsx, fy, fw, fh), 1)

                # Windows (visible when healthy enough)
                if hp_ratio > 0.3:
                    win_lit = (220, 210, 120) if (seg.floor_idx % 3 != 1) else (60, 60, 80)
                    for wx_ in range(int(fsx) + 8, int(fsx + fw) - 8, 18):
                        pygame.draw.rect(s, win_lit, (wx_, fy + 10, 8, 10))
                else:
                    # Cracked appearance – draw jagged lines
                    cx_ = int(fsx + fw // 2)
                    pygame.draw.line(s, _BLDG_DARK,
                                     (cx_, fy + 4), (cx_ + 6, fy + fh - 4), 2)
                    pygame.draw.line(s, _BLDG_DARK,
                                     (cx_ - 8, fy + 8), (cx_, fy + fh - 8), 2)

    def _draw_debris(self, s, cam_x):
        for d in self._debris:
            sx = int(d.wx - cam_x)
            sy = int(d.wy)
            alpha = int(255 * d.life / _DEBRIS_LIFE)
            col   = tuple(min(255, max(0, c)) for c in d.col)
            pygame.draw.rect(s, col, (sx, sy, d.w, d.h))

    def _draw_projectiles(self, s, cam_x):
        for proj in self._projectiles:
            sx = int(proj.wx - cam_x)
            sy = int(proj.wy)
            if proj.kind == "bullet":
                pygame.draw.circle(s, _BULLET_COL, (sx, sy), 4)
            elif proj.kind == "shell":
                pygame.draw.circle(s, _SHELL_COL, (sx, sy), 5)
                pygame.draw.circle(s, (255, 200, 80), (sx, sy), 3)
            elif proj.kind == "bomb":
                pygame.draw.circle(s, _BOMB_COL, (sx, sy), 6)
                pygame.draw.circle(s, (240, 120, 40), (sx, sy), 3)

    def _draw_helis(self, s, cam_x):
        for h in self._helis:
            sx = int(h.wx - cam_x)
            sy = int(h.wy)
            col = _PLR_HURT if h.hit_flash > 0 else _HELI_COL

            # Body – oval fuselage
            pygame.draw.ellipse(s, col, (sx - 28, sy - 10, 56, 22))
            # Cockpit bubble
            pygame.draw.ellipse(s, (40, 150, 200), (sx - 14, sy - 14, 28, 20))
            # Tail boom
            pygame.draw.rect(s, col, (sx + 24, sy - 4, 20, 6))
            # Tail rotor
            pygame.draw.line(s, _HELI_BLADE,
                             (sx + 43, sy - 10), (sx + 43, sy + 6), 2)
            # Main rotor blades (spin animation)
            ang = math.radians(h.blade_rot % 360)
            for a in (ang, ang + math.pi):
                ex = sx + int(math.cos(a) * 36)
                ey = sy - 14 + int(math.sin(a) * 5)
                pygame.draw.line(s, _HELI_BLADE, (sx, sy - 14), (ex, ey), 2)

            # HP bar
            self._draw_hp_bar(s, sx - 20, sy - 22, 40, 4, h.hp, h.max_hp)

    def _draw_tanks(self, s, cam_x):
        for t in self._tanks:
            sx = int(t.wx - cam_x)
            sy = int(t.wy)
            col = _PLR_HURT if t.hit_flash > 0 else _TANK_COL
            f   = t.facing

            # Treads
            pygame.draw.rect(s, _TANK_DARK, (sx - 28, sy - 8, 56, 12))
            # Hull
            pygame.draw.rect(s, col, (sx - 22, sy - 20, 44, 16))
            # Turret
            pygame.draw.ellipse(s, col, (sx - 14, sy - 30, 28, 16))
            # Barrel
            pygame.draw.line(s, _TANK_DARK,
                             (sx, sy - 22), (sx + f * 26, sy - 24), 3)

            self._draw_hp_bar(s, sx - 22, sy - 38, 44, 4, t.hp, t.max_hp)

    def _draw_planes(self, s, cam_x):
        for p in self._planes:
            sx = int(p.wx - cam_x)
            sy = int(p.wy)
            col = _PLR_HURT if p.hit_flash > 0 else _PLANE_COL
            f   = 1 if p.vx > 0 else -1

            # Fuselage
            pygame.draw.ellipse(s, col, (sx - 30, sy - 8, 60, 16))
            # Wing
            pygame.draw.polygon(s, col, [
                (sx - 10, sy),
                (sx + 10, sy),
                (sx + f * 5, sy + 16),
                (sx - f * 20, sy + 16),
            ])
            # Tail fins
            pygame.draw.polygon(s, col, [
                (sx - f * 22, sy - 8),
                (sx - f * 30, sy - 18),
                (sx - f * 18, sy - 8),
            ])
            # Cockpit
            pygame.draw.ellipse(s, (80, 200, 230), (sx - 6, sy - 10, 14, 10))

    def _draw_player(self, s, cam_x):
        sx  = int(self.player_wx - cam_x)
        sy  = int(self.player_wy)
        f   = self._facing

        hurt = self._invuln > 0 and (self._frame // 4) % 2 == 0
        body = _PLR_HURT if hurt else _PLR_BODY
        arm  = _PLR_HURT if hurt else _PLR_ARMOR
        jnt  = _PLR_JOINT

        # Shadow
        pygame.draw.ellipse(s, (20, 18, 28),
                            (sx - 4, _GROUND_Y - 6, _PLR_W + 8, 10))

        # Legs (lower frame)
        leg_top  = sy + 80
        leg_bot  = sy + _PLR_H
        for side in (-1, 1):
            lx = sx + _PLR_W // 2 + side * 10
            pygame.draw.polygon(s, arm, [
                (lx - 7, leg_top),
                (lx + 7, leg_top),
                (lx + 5, leg_bot),
                (lx - 5, leg_bot),
            ])
            # Knee joint
            pygame.draw.circle(s, jnt, (lx, leg_top + 18), 5)
            # Foot thruster
            pygame.draw.rect(s, jnt, (lx - 8, leg_bot - 6, 16, 8))

        # Torso
        pygame.draw.polygon(s, body, [
            (sx + 4,         sy + 80),
            (sx + _PLR_W - 4, sy + 80),
            (sx + _PLR_W,     sy + 40),
            (sx,              sy + 40),
        ])
        # Chest plate detail
        pygame.draw.polygon(s, arm, [
            (sx + 8,          sy + 56),
            (sx + _PLR_W - 8, sy + 56),
            (sx + _PLR_W - 6, sy + 42),
            (sx + 6,          sy + 42),
        ])

        # Arms
        atk_extend = self._atk_timer > 0
        for side in (-1, 1):
            ax  = sx + (_PLR_W if side > 0 else 0)
            ay  = sy + 46
            if atk_extend and side == f:
                ext = f * 28
            else:
                ext = side * 6
            # Upper arm
            pygame.draw.polygon(s, arm, [
                (ax,        ay - 6),
                (ax,        ay + 6),
                (ax + ext,  ay + 8),
                (ax + ext,  ay - 8),
            ])
            # Fist / hand
            fist_col = _BULLET_COL if atk_extend and side == f else jnt
            pygame.draw.rect(s, fist_col, (ax + ext - 6, ay - 8, 14, 14))

        # Head / cockpit dome
        hx  = sx + _PLR_W // 2
        hy  = sy + 18
        pygame.draw.ellipse(s, arm, (sx + 6, sy + 4, _PLR_W - 12, 36))
        # Visor
        pygame.draw.ellipse(s, _PLR_VISOR, (hx - 12, hy - 8, 24, 14))
        # Visor glow
        pygame.draw.ellipse(s, (160, 240, 255), (hx - 6, hy - 4, 12, 7))

        # Shoulder pads
        for side in (-1, 1):
            spx = sx + (_PLR_W - 4 if side > 0 else 4)
            pygame.draw.polygon(s, arm, [
                (spx,           sy + 36),
                (spx + side*12, sy + 30),
                (spx + side*14, sy + 52),
                (spx,           sy + 52),
            ])

    def _draw_hp_bar(self, s, x, y, w, h, hp, max_hp):
        ratio = _clamp(hp / max_hp, 0, 1)
        pygame.draw.rect(s, (30, 30, 30), (x, y, w, h))
        col = _HUD_HP_FULL if ratio > 0.4 else _HUD_HP_LOW
        pygame.draw.rect(s, col, (x, y, int(w * ratio), h))

    def _draw_hud(self, s):
        # HP bar background panel
        pygame.draw.rect(s, (0, 0, 0), (8, 8, 164, 28))
        pygame.draw.rect(s, (40, 40, 50), (8, 8, 164, 28), 1)

        # HP label
        hp_surf = self.font.render("HP", True, (180, 180, 200))
        s.blit(hp_surf, (12, 12))

        # HP bar
        ratio = _clamp(self.player_hp / _PLR_MAX_HP, 0, 1)
        pygame.draw.rect(s, (20, 20, 20), (36, 14, 130, 14))
        bar_col = _HUD_HP_FULL if ratio > 0.4 else _HUD_HP_LOW
        pygame.draw.rect(s, bar_col, (36, 14, int(130 * ratio), 14))

        # Destruction %
        destr = self._destruction_pct()
        destr_surf = self.font.render(
            f"DEST  {int(destr * 100):3d}%  (80% to win)", True, (200, 200, 120))
        s.blit(destr_surf, (8, 40))

        # Destruction bar
        pygame.draw.rect(s, (20, 20, 20), (8, 56, 200, 8))
        dbar_col = (200, 80, 40) if destr < 0.8 else (80, 240, 120)
        pygame.draw.rect(s, dbar_col, (8, 56, int(200 * destr), 8))
        # Win threshold marker
        pygame.draw.line(s, (240, 220, 50), (8 + 160, 56), (8 + 160, 64), 2)

        # Enemy count
        n_enemies = (sum(1 for h in self._helis if h.alive) +
                     sum(1 for t in self._tanks if t.alive) +
                     sum(1 for p in self._planes if p.alive))
        if n_enemies > 0:
            en_surf = self.font.render(f"ENEMIES: {n_enemies}", True, (220, 100, 80))
            s.blit(en_surf, (self.width - 130, 8))

        # State debug (climbing indicator)
        if self._state == "climbing":
            cl_surf = self.font.render("CLIMBING", True, (100, 200, 255))
            s.blit(cl_surf, (self.width // 2 - 40, 8))

    # ── Title card + overlay ──────────────────────────────────────────────────

    def _show_title(self):
        """Flash 'KAIJU MODE' at the start of the level."""
        frames = self.fps * 2   # 2 seconds
        clock  = pygame.time.Clock()
        for i in range(frames):
            for event in pygame.event.get():
                if event.type in (pygame.QUIT, pygame.KEYDOWN):
                    return
            self._draw()
            # Overlay
            alpha = int(255 * min(1.0, (frames - i) / (frames * 0.4)))
            surf  = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            surf.fill((0, 0, 0, max(0, 140 - i * 2)))
            self.screen.blit(surf, (0, 0))

            title = self.font.render("KAIJU MODE", True, (80, 220, 255))
            sub   = self.font.render("DESTROY 80% OF THE CITY TO WIN",
                                     True, (200, 200, 120))
            tw = title.get_width()
            sw = sub.get_width()
            self.screen.blit(title, (self.width // 2 - tw // 2,
                                     self.height // 2 - 30))
            self.screen.blit(sub,   (self.width // 2 - sw // 2,
                                     self.height // 2 + 10))
            pygame.display.flip()
            clock.tick(self.fps)

    def _show_overlay(self, message, text_color, bg_rgba):
        """Display a result overlay for ~2.5 seconds."""
        surf  = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        surf.fill(bg_rgba)
        self.screen.blit(surf, (0, 0))
        msg_surf = self.font.render(message, True, text_color)
        mw = msg_surf.get_width()
        self.screen.blit(msg_surf, (self.width // 2 - mw // 2,
                                    self.height // 2 - 16))
        pygame.display.flip()
        pygame.time.wait(2500)
