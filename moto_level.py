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
    """Gradient sky above the horizon."""
    for y in range(0, horizon_y, 2):
        t = y / max(1, horizon_y)
        r = int(_SKY_TOP[0] + (_SKY_BOT[0] - _SKY_TOP[0]) * t)
        g = int(_SKY_TOP[1] + (_SKY_BOT[1] - _SKY_TOP[1]) * t)
        b = int(_SKY_TOP[2] + (_SKY_BOT[2] - _SKY_TOP[2]) * t)
        pygame.draw.rect(screen, (r, g, b), (0, y, width, 2))


def _draw_road(screen, width, height, cx, road_offset):
    """Draw pseudo-3D road: base + perspective bands + edge lines + centre dashes."""

    def _sy(wz):
        _, sy, _ = _proj(0, wz, cx)
        return min(sy, height - 4)

    def _x(wx, wz):
        sx, _, _ = _proj(wx, wz, cx)
        return sx

    # --- Base road trapezoid ---
    lxn = _x(-_ROAD_HALF, _Z_NEAR)
    rxn = _x( _ROAD_HALF, _Z_NEAR)
    syn = _sy(_Z_NEAR)
    lxf = _x(-_ROAD_HALF, _Z_FAR)
    rxf = _x( _ROAD_HALF, _Z_FAR)
    syf = _sy(_Z_FAR)
    pygame.draw.polygon(
        screen, _ROAD_COL,
        [(lxf, syf), (rxf, syf), (rxn, syn), (lxn, syn)],
    )

    # --- Alternating perspective bands ---
    # Build z slice points: more slices near camera for smoother perspective
    num_slices = 14
    z_slices = []
    for i in range(num_slices + 1):
        t = i / num_slices
        z = _Z_NEAR + (_Z_FAR - _Z_NEAR) * (t ** 0.55)
        z_slices.append(z)

    for i in range(num_slices):
        z0 = z_slices[i]      # near side of this band (larger screen y)
        z1 = z_slices[i + 1]  # far side
        band_idx = int((z0 + road_offset) / _ROAD_BAND_Z) % 2
        if band_idx == 0:
            continue
        sy0 = _sy(z0)
        sy1 = _sy(z1)
        lx0 = _x(-_ROAD_HALF, z0)
        rx0 = _x( _ROAD_HALF, z0)
        lx1 = _x(-_ROAD_HALF, z1)
        rx1 = _x( _ROAD_HALF, z1)
        if sy0 > sy1:
            pygame.draw.polygon(
                screen, _ROAD_COL2,
                [(lx1, sy1), (rx1, sy1), (rx0, sy0), (lx0, sy0)],
            )

    # --- Road edge lines ---
    edge_zs = [_Z_NEAR + (_Z_FAR - _Z_NEAR) * (i / 18) ** 0.5
               for i in range(19)]
    left_pts  = []
    right_pts = []
    for z in edge_zs:
        sy = _sy(z)
        if _HORIZON_Y <= sy <= height:
            left_pts.append((_x(-_ROAD_HALF, z), sy))
            right_pts.append((_x( _ROAD_HALF, z), sy))
    if len(left_pts)  >= 2:
        pygame.draw.lines(screen, _EDGE_COL, False, left_pts,  2)
    if len(right_pts) >= 2:
        pygame.draw.lines(screen, _EDGE_COL, False, right_pts, 2)

    # --- Kerb stripes (red/white alternating on edges) ---
    kerb_period = 150.0
    for side in (-1, 1):
        for i in range(12):
            z0 = _Z_NEAR + ((i * kerb_period - road_offset) % (_Z_FAR - _Z_NEAR))
            z1 = z0 + kerb_period * 0.5
            if z0 <= 0 or z0 >= _Z_FAR:
                continue
            z1 = min(z1, _Z_FAR)
            sy0 = _sy(z0)
            sy1 = _sy(z1)
            if sy0 <= sy1 or sy0 > height:
                continue
            kerb_x = _x(side * _ROAD_HALF, (z0 + z1) * 0.5)
            kerb_w = max(2, int(abs(_x(side * _ROAD_HALF, z0) - _x(side * _ROAD_HALF, z1)) * 0.4))
            kerb_h = max(1, sy0 - sy1)
            col = (210, 60, 60) if (i % 2 == 0) else (230, 230, 230)
            pygame.draw.rect(screen, col, (kerb_x - kerb_w // 2, sy1, kerb_w, kerb_h))

    # --- Centre dashes ---
    z_range = _Z_FAR - _Z_NEAR
    num_dashes = int(z_range / _STRIPE_Z_GAP) + 3
    for i in range(num_dashes):
        z = _Z_NEAR + ((i * _STRIPE_Z_GAP - road_offset) % z_range)
        if z <= 1.0 or z > _Z_FAR:
            continue
        _, sy, sc = _proj(0, z, cx)
        if sy < _HORIZON_Y or sy > height - 2:
            continue
        dw = max(1, int(4 * sc))
        dh = max(1, int(24 * sc))
        pygame.draw.rect(screen, _STRIPE_COL, (cx - dw // 2, sy - dh, dw, dh))


# ── Bike / rider rendering ────────────────────────────────────────────────────

def _draw_bike(screen, sx, sy, scale, color, facing, lean=0):
    """Draw a schematic motorcycle + rider.

    facing:  1 = front-on (enemy approaching),  -1 = rear view (player)
    lean:   -1 / 0 / 1  – steering lean direction
    """

    def s(v):
        return max(1, int(v * scale))

    lean_off = lean * s(3)

    # Wheels
    wr = s(6)
    wf = max(1, wr // 2)          # flattened vertically for perspective
    if facing == -1:              # rear view: rear wheel centred, front above
        rw = (sx + lean_off, sy)
        fw = (sx + lean_off, sy - s(1))
    else:                         # front view: two wheels side by side
        rw = (sx - s(6) + lean_off, sy)
        fw = (sx + s(6) + lean_off, sy)
    pygame.draw.ellipse(screen, color, (rw[0] - wr, rw[1] - wf, wr * 2, wf * 2))
    pygame.draw.ellipse(screen, color, (fw[0] - wr, fw[1] - wf, wr * 2, wf * 2))

    # Bike body (fuel tank / seat)
    bw = s(8)
    bh = s(3)
    by = sy - s(4)
    pygame.draw.rect(screen, color, (sx + lean_off - bw, by - bh, bw * 2, bh))

    # Rider torso
    tx = sx + lean_off
    th = s(9)
    tw = s(4)
    torso_bottom = by - bh
    pygame.draw.rect(screen, color, (tx - tw, torso_bottom - th, tw * 2, th))

    # Rider head
    hr = max(1, s(4))
    pygame.draw.circle(screen, color, (tx, torso_bottom - th - hr), hr)

    # Handlebars
    bar_y = torso_bottom - s(3)
    pygame.draw.line(screen, color,
                     (sx + lean_off - s(8), bar_y),
                     (sx + lean_off + s(8), bar_y),
                     max(1, s(1)))


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
        _draw_sky(self.screen, self.width, _HORIZON_Y)
        _draw_road(self.screen, self.width, self.height, self.cx, self._road_offset)
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
        _draw_bike(self.screen, sx, sy, sc, _PLR_COL, -1, self._lean)

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
