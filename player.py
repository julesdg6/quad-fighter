import pygame
from render import draw_fighter, get_depth_scale
from combat import KNOCKDOWN_STUN_FRAMES, HIT_STUN_FRAMES as HURT_ANIM_FRAMES
from theme import build_palette

SHADOW_BASE_SCALE = 1.0
SHADOW_MAX_REDUCTION = 0.5
SHADOW_JUMP_DIVISOR = 120.0
SHADOW_OUTER_INFLATE_X = 12
SHADOW_OUTER_INFLATE_Y = 4
SHADOW_OUTER_COLOR = (30, 30, 30)
POST_ATTACK_FRAMES = 2
CHARACTER_SCALE = 2
COMBO_WINDOW_FRAMES = 24
GROUND_PRIMARY_COMBO = ("primary", "combo2", "combo3")
PRIMARY_ATTACK_HITBOX_COLOR = (255, 220, 0)
SECONDARY_ATTACK_HITBOX_COLOR = (255, 150, 64)
AERIAL_ATTACK_HITBOX_COLOR = (64, 220, 255)

AERIAL_HEAVY_FORWARD_VEL = 5.0
DASH_PUNCH_VEL = 6.5  # forward velocity applied during dash_punch strike

# Special moves triggered by simultaneous button combinations
SPECIAL_MOVES = ("spin_attack", "dash_punch", "dive_kick")
SPECIAL_ATTACK_HITBOX_COLOR = (200, 64, 255)  # purple

# Invincibility frames granted at the moment the player leaves the ground (jump).
# Classic beat-em-up escape: tapping jump gives a brief window to pass through attacks.
JUMP_INVINCIBLE_FRAMES = 8

# Damage multiplier applied to hits absorbed while crouching.
# Crouching acts as a guard stance that halves incoming damage.
CROUCH_DEFENSE_RATIO = 0.5

GRAB_RANGE = 72           # max pixel distance (by rect inflation) to latch onto an enemy
GRAB_MAX_FRAMES = 110     # frames before the enemy wriggles free
GRAB_COOLDOWN_FRAMES = 40  # cooldown after releasing a grab
GRAB_SNAP_GAP = 4         # gap in pixels between player and grabbed enemy

ATTACK_PROFILES = {
    "primary": {
        "anticipation": 2,
        "strike": 3,
        "recovery": 4,
        "cooldown": 14,
        "damage": 10,
        "attack_width": 60,
        "attack_height": 48,
        "attack_offset": 6,
        "knockback": 56,
    },
    "secondary": {
        "anticipation": 7,
        "strike": 5,
        "recovery": 10,
        "cooldown": 30,
        "damage": 22,
        "attack_width": 92,
        "attack_height": 56,
        "attack_offset": 8,
        "knockback": 74,
    },
    "aerial_light": {
        "anticipation": 2,
        "strike": 4,
        "recovery": 5,
        "cooldown": 16,
        "damage": 12,
        "attack_width": 55,
        "attack_height": 44,
        "attack_offset": 6,
        "knockback": 62,
    },
    "aerial_heavy": {
        "anticipation": 3,
        "strike": 6,
        "recovery": 8,
        "cooldown": 24,
        "damage": 20,
        "attack_width": 80,
        "attack_height": 52,
        "attack_offset": 8,
        "knockback": 88,
    },
    "crouch_punch": {
        "anticipation": 2,
        "strike": 3,
        "recovery": 4,
        "cooldown": 12,
        "damage": 8,
        "attack_width": 48,
        "attack_height": 36,
        "attack_offset": 4,
        "knockback": 44,
    },
    "crouch_kick": {
        "anticipation": 4,
        "strike": 4,
        "recovery": 8,
        "cooldown": 20,
        "damage": 14,
        "attack_width": 72,
        "attack_height": 28,
        "attack_offset": 6,
        "knockback": 60,
    },
    "combo2": {
        "anticipation": 2,
        "strike": 3,
        "recovery": 5,
        "cooldown": 12,
        "damage": 12,
        "attack_width": 64,
        "attack_height": 50,
        "attack_offset": 8,
        "knockback": 62,
    },
    "combo3": {
        "anticipation": 3,
        "strike": 4,
        "recovery": 7,
        "cooldown": 18,
        "damage": 18,
        "attack_width": 76,
        "attack_height": 56,
        "attack_offset": 10,
        "knockback": 80,
    },
    # ── Special moves ────────────────────────────────────────────────────────
    # Spin Attack  (punch + kick simultaneously on ground)
    # Wide AoE that hits both sides of the player.
    "spin_attack": {
        "anticipation": 5,
        "strike": 8,
        "recovery": 10,
        "cooldown": 45,
        "damage": 28,
        "attack_width": 120,
        "attack_height": 80,
        "attack_offset": 0,
        "knockback": 90,
    },
    # Dash Punch  (forward direction + punch while running at full speed)
    # Quick lunge that propels the player forward through the strike.
    "dash_punch": {
        "anticipation": 2,
        "strike": 4,
        "recovery": 6,
        "cooldown": 28,
        "damage": 22,
        "attack_width": 88,
        "attack_height": 52,
        "attack_offset": 12,
        "knockback": 82,
    },
    # Dive Kick  (down + kick while airborne)
    # Powerful downward aerial kick; counts as an aerial attack.
    "dive_kick": {
        "anticipation": 3,
        "strike": 5,
        "recovery": 8,
        "cooldown": 32,
        "damage": 26,
        "attack_width": 68,
        "attack_height": 60,
        "attack_offset": 8,
        "knockback": 86,
    },
}


class Player:
    def __init__(self, x, y, screen_width, screen_height):
        self.x = float(x)
        self.y = float(y)
        self.width = 48 * CHARACTER_SCALE
        self.height = 96 * CHARACTER_SCALE
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ground_y = screen_height - self.height - 40
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.speed = 4.2
        self.lane_speed = 3.4
        self.jump_power = -18.0
        self.gravity = 0.9
        self.on_ground = True
        self.attack = False
        self.attack_timer = 0
        self.attack_damage = ATTACK_PROFILES["primary"]["damage"]
        self.attack_knockback = ATTACK_PROFILES["primary"]["knockback"]
        self.attack_width = ATTACK_PROFILES["primary"]["attack_width"]
        self.attack_height = ATTACK_PROFILES["primary"]["attack_height"]
        self.attack_offset = ATTACK_PROFILES["primary"]["attack_offset"]
        self.attack_anticipation_frames = ATTACK_PROFILES["primary"]["anticipation"]
        self.attack_strike_frames = ATTACK_PROFILES["primary"]["strike"]
        self.attack_recovery_frames = ATTACK_PROFILES["primary"]["recovery"]
        self.attack_duration_frames = (
            self.attack_anticipation_frames
            + self.attack_strike_frames
            + self.attack_recovery_frames
        )
        self.attack_cooldown_timer = 0
        self.post_attack_frames = POST_ATTACK_FRAMES
        self.post_attack_timer = 0
        self.attack_cooldown_frames = ATTACK_PROFILES["primary"]["cooldown"]
        self.current_attack_type = "primary"
        self.prev_primary_pressed = False
        self.prev_secondary_pressed = False
        self.attack_id = 0
        self.hit_stun_timer = 0
        self.hurt_flash_timer = 0
        self.hurt_anim_timer = 0
        self.hit_region = "torso"
        self.knockdown_timer = 0
        self.facing = 1
        self.max_health = 100
        self.health = self.max_health
        self.weapon_name = None
        self.weapon_hits_remaining = 0
        self.weapon_damage_bonus = 0
        self.weapon_range_bonus = 0
        self.aerial_attack_used = False
        self.held_object = None  # EnvironmentObject currently being carried
        self.crouching = False
        self.grab_timer = 0
        self.grab_cooldown_timer = 0
        self.grabbed_enemy = None
        self.grab_triggered = False  # single-frame signal: grab key just pressed
        self.throw_triggered = False  # single-frame signal: throw requested this frame
        self.prev_grab_pressed = False
        self.combo_step = 0
        self.combo_window_timer = 0
        self.invincible_timer = 0
        self.palette_variant = "player"  # set to "player2" for the second player
        self.suit_colour_idx = 0  # 0 = theme default; see theme.SUIT_COLOURS
        self.hair_colour_idx = 0  # 0 = theme default; see theme.HAIR_COLOURS

    def update(self, extra_input=None, keyboard_map=None):
        """Update player state.

        Parameters
        ----------
        extra_input : dict or None
            Boolean action flags from an external source (e.g., controller).
            Keys: ``move_left``, ``move_right``, ``move_up``, ``move_down``,
            ``jump``, ``punch``, ``kick``, ``crouch``, ``grab``.
            Each value is OR-ed with the corresponding keyboard input.
        keyboard_map : dict or None
            Mapping of action name → pygame key constant used for remapping.
            Falls back to the hardcoded defaults when None.
        """
        if extra_input is None:
            extra_input = {}
        kb = keyboard_map or {}

        keys = pygame.key.get_pressed()

        def _key(action, default):
            return keys[kb.get(action, default)] or bool(extra_input.get(action, False))

        primary_pressed   = _key("punch",  pygame.K_z)
        secondary_pressed = _key("kick",   pygame.K_x)
        crouch_key        = _key("crouch", pygame.K_c)
        grab_key          = _key("grab",   pygame.K_g)
        if self.hurt_anim_timer > 0:
            self.hurt_anim_timer -= 1
        if self.hurt_flash_timer > 0:
            self.hurt_flash_timer -= 1
        if self.knockdown_timer > 0:
            self.knockdown_timer -= 1
            # Keep character frozen in knockdown until timer expires
            self.hit_stun_timer = max(self.hit_stun_timer, 1)
            self.hurt_anim_timer = max(self.hurt_anim_timer, 1)
        if self.grab_cooldown_timer > 0:
            self.grab_cooldown_timer -= 1
        if self.invincible_timer > 0:
            self.invincible_timer -= 1

        # Grab trigger: signal for the main loop to attempt a grab this frame
        self.grab_triggered = (
            grab_key
            and not self.prev_grab_pressed
            and not self.is_grabbing()
            and not self.is_attacking()
            and self.on_ground
            and not self.crouching
            and self.hit_stun_timer <= 0
            and self.grab_cooldown_timer <= 0
        )

        # Clear throw signal; it will be re-set below if triggered
        self.throw_triggered = False

        # Release grab if player is knocked into hit-stun
        if self.grabbed_enemy is not None and self.hit_stun_timer > 0:
            self.release_grab()

        # Drop dead grabbed enemy (health already depleted externally)
        if self.grabbed_enemy is not None and self.grabbed_enemy.health <= 0:
            self.release_grab()

        self.vel_x = 0.0
        lane_delta = 0.0
        if self.combo_window_timer > 0:
            self.combo_window_timer -= 1
            if self.combo_window_timer == 0:
                self.combo_step = 0
        if self.hit_stun_timer > 0:
            self.hit_stun_timer -= 1
        else:
            self.crouching = (
                (crouch_key and self.on_ground)
                or (
                    self.on_ground
                    and self.is_attacking()
                    and self.current_attack_type in ("crouch_punch", "crouch_kick")
                )
            )
            if not self.crouching:
                if _key("move_left", pygame.K_LEFT):
                    self.vel_x = -self.speed
                    self.facing = -1
                elif _key("move_right", pygame.K_RIGHT):
                    self.vel_x = self.speed
                    self.facing = 1
                if self.on_ground:
                    if _key("move_up", pygame.K_UP):
                        lane_delta -= self.lane_speed
                    elif _key("move_down", pygame.K_DOWN):
                        lane_delta += self.lane_speed

            if _key("jump", pygame.K_SPACE) and self.on_ground and not self.crouching and not self.is_grabbing():
                self.vel_y = self.jump_power
                self.on_ground = False
                self.invincible_timer = JUMP_INVINCIBLE_FRAMES

            # Manage grab state while holding an enemy
            if self.grabbed_enemy is not None:
                self.grab_timer -= 1
                if self.grab_timer <= 0:
                    # Enemy wriggles free
                    self.release_grab()
                else:
                    # Snap grabbed enemy to player's side
                    if self.facing > 0:
                        self.grabbed_enemy.x = self.x + self.width + GRAB_SNAP_GAP
                    else:
                        self.grabbed_enemy.x = self.x - self.grabbed_enemy.width - GRAB_SNAP_GAP
                    self.grabbed_enemy.ground_y = self.ground_y
                    self.grabbed_enemy.y = self.ground_y
                    self.grabbed_enemy.on_ground = True
                    self.grabbed_enemy.vel_x = 0.0
                    self.grabbed_enemy.vel_y = 0.0
                    # Throw on primary attack press
                    if primary_pressed and not self.prev_primary_pressed:
                        self.throw_triggered = True

            triggered_attack = None
            if not self.is_grabbing():
                if not self.on_ground:
                    can_aerial = (
                        self.attack_cooldown_timer <= 0
                        and not self.is_attacking()
                        and not self.aerial_attack_used
                    )
                    if (
                        _key("move_down", pygame.K_DOWN)
                        and secondary_pressed
                        and not self.prev_secondary_pressed
                        and can_aerial
                    ):
                        triggered_attack = "dive_kick"
                    elif (
                        secondary_pressed
                        and not self.prev_secondary_pressed
                        and can_aerial
                    ):
                        triggered_attack = "aerial_heavy"
                    elif (
                        primary_pressed
                        and not self.prev_primary_pressed
                        and can_aerial
                    ):
                        triggered_attack = "aerial_light"
                elif self.crouching:
                    if (
                        secondary_pressed
                        and not self.prev_secondary_pressed
                        and self.attack_cooldown_timer <= 0
                        and not self.is_attacking()
                    ):
                        triggered_attack = "crouch_kick"
                    elif (
                        primary_pressed
                        and not self.prev_primary_pressed
                        and self.attack_cooldown_timer <= 0
                        and not self.is_attacking()
                    ):
                        triggered_attack = "crouch_punch"
                else:
                    # Special: Spin Attack (punch + kick pressed simultaneously)
                    if (
                        primary_pressed
                        and secondary_pressed
                        and not self.prev_primary_pressed
                        and not self.prev_secondary_pressed
                        and self.attack_cooldown_timer <= 0
                        and not self.is_attacking()
                    ):
                        triggered_attack = "spin_attack"
                    # Special: Dash Punch (punch while running forward at full speed)
                    elif (
                        primary_pressed
                        and not self.prev_primary_pressed
                        and abs(self.vel_x) >= self.speed * 0.9
                        and ((self.vel_x > 0 and self.facing > 0) or (self.vel_x < 0 and self.facing < 0))
                        and self.attack_cooldown_timer <= 0
                        and not self.is_attacking()
                    ):
                        triggered_attack = "dash_punch"
                    elif (
                        secondary_pressed
                        and not self.prev_secondary_pressed
                        and self.attack_cooldown_timer <= 0
                        and (not self.is_attacking() or self.combo_window_timer > 0)
                    ):
                        triggered_attack = "secondary"
                    elif (
                        primary_pressed
                        and not self.prev_primary_pressed
                        and self.attack_cooldown_timer <= 0
                        and (not self.is_attacking() or self.combo_window_timer > 0)
                    ):
                        triggered_attack = GROUND_PRIMARY_COMBO[
                            min(self.combo_step, len(GROUND_PRIMARY_COMBO) - 1)
                        ]
            if triggered_attack is not None:
                profile = ATTACK_PROFILES[triggered_attack]
                self.current_attack_type = triggered_attack
                self.attack_anticipation_frames = profile["anticipation"]
                self.attack_strike_frames = profile["strike"]
                self.attack_recovery_frames = profile["recovery"]
                self.attack_duration_frames = (
                    self.attack_anticipation_frames
                    + self.attack_strike_frames
                    + self.attack_recovery_frames
                )
                self.attack_timer = self.attack_duration_frames
                self.attack_cooldown_frames = profile["cooldown"]
                self.attack_cooldown_timer = self.attack_cooldown_frames
                self.attack_damage = profile["damage"]
                self.attack_width = profile["attack_width"]
                self.attack_height = profile["attack_height"]
                self.attack_offset = profile["attack_offset"]
                self.attack_knockback = profile["knockback"]
                self.post_attack_timer = 0
                self.attack_id += 1
                if triggered_attack in ("aerial_light", "aerial_heavy", "dive_kick"):
                    self.aerial_attack_used = True
                if triggered_attack in GROUND_PRIMARY_COMBO:
                    self.combo_step += 1
                    if self.combo_step >= len(GROUND_PRIMARY_COMBO):
                        self.combo_step = 0
                    self.combo_window_timer = 0
                else:
                    self.combo_step = 0
                    self.combo_window_timer = 0

            # Flying kick: lock forward velocity during strike for committed lunge
            # Allow steering backwards to brake; otherwise maintain forward momentum
            if (
                not self.on_ground
                and self.current_attack_type == "aerial_heavy"
                and self.attack_timer > 0
            ):
                elapsed = self.attack_duration_frames - self.attack_timer
                strike_start = self.attack_anticipation_frames
                strike_end = strike_start + self.attack_strike_frames
                if strike_start <= elapsed < strike_end:
                    opposite_dir = "move_left" if self.facing > 0 else "move_right"
                    opposite_key = pygame.K_LEFT if self.facing > 0 else pygame.K_RIGHT
                    if not _key(opposite_dir, opposite_key):
                        self.vel_x = self.facing * AERIAL_HEAVY_FORWARD_VEL

            # Dash punch: player lunges forward through the strike
            if (
                self.on_ground
                and self.current_attack_type == "dash_punch"
                and self.attack_timer > 0
            ):
                elapsed = self.attack_duration_frames - self.attack_timer
                strike_start = self.attack_anticipation_frames
                strike_end = strike_start + self.attack_strike_frames
                if strike_start <= elapsed < strike_end:
                    self.vel_x = self.facing * DASH_PUNCH_VEL
        self.prev_primary_pressed = primary_pressed
        self.prev_secondary_pressed = secondary_pressed
        self.prev_grab_pressed = grab_key

        prev_attack_timer = self.attack_timer
        if self.attack_timer > 0:
            self.attack_timer -= 1
        elif self.post_attack_timer > 0:
            self.post_attack_timer -= 1
        if prev_attack_timer > 0 and self.attack_timer == 0:
            self.post_attack_timer = self.post_attack_frames
            if self.current_attack_type in GROUND_PRIMARY_COMBO[:-1] and self.combo_step > 0:
                self.combo_window_timer = COMBO_WINDOW_FRAMES

        self.attack = self.get_attack_rect() is not None

        if self.attack_cooldown_timer > 0:
            self.attack_cooldown_timer -= 1

        self.vel_y += self.gravity
        self.x += self.vel_x
        self.ground_y += lane_delta
        self.y += self.vel_y

        self.x = max(0, min(self.x, self.screen_width - self.width))
        lane_min = self.screen_height * 0.5
        lane_max = self.screen_height - self.height - 20
        self.ground_y = max(lane_min, min(self.ground_y, lane_max))

        if self.y >= self.ground_y:
            self.y = self.ground_y
            self.vel_y = 0.0
            self.on_ground = True
            self.aerial_attack_used = False

    def get_rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def is_attacking(self):
        return self.attack_timer > 0 or self.post_attack_timer > 0

    def get_attack_rect(self):
        if self.attack_timer <= 0:
            return None
        elapsed = self.attack_duration_frames - self.attack_timer
        strike_start = self.attack_anticipation_frames
        strike_end = strike_start + self.attack_strike_frames
        if elapsed < strike_start or elapsed >= strike_end:
            return None
        attack_width = self.attack_width + self.weapon_range_bonus
        attack_height = self.attack_height
        # Spin attack: centered hitbox that covers both sides of the player
        if self.current_attack_type == "spin_attack":
            center_x = int(self.x + self.width // 2 - attack_width // 2)
            return pygame.Rect(
                center_x,
                int(self.y + self.height * 0.15),
                attack_width,
                attack_height,
            )
        # Choose y_ratio based on attack type (relative to player's current y)
        if self.current_attack_type == "secondary":
            y_ratio = 0.55
        elif self.current_attack_type == "aerial_heavy":
            y_ratio = 0.35
        elif self.current_attack_type == "aerial_light":
            y_ratio = 0.25
        elif self.current_attack_type == "crouch_punch":
            y_ratio = 0.55
        elif self.current_attack_type == "crouch_kick":
            y_ratio = 0.72
        elif self.current_attack_type == "combo2":
            y_ratio = 0.35
        elif self.current_attack_type == "combo3":
            y_ratio = 0.50
        elif self.current_attack_type == "dash_punch":
            y_ratio = 0.20
        elif self.current_attack_type == "dive_kick":
            y_ratio = 0.50
        else:
            y_ratio = 0.30
        if self.facing > 0:
            attack_x = int(self.x + self.width + self.attack_offset)
        else:
            attack_x = int(self.x - attack_width - self.attack_offset)
        return pygame.Rect(
            attack_x,
            int(self.y + self.height * y_ratio),
            attack_width,
            attack_height,
        )

    def get_attack_damage(self):
        return self.attack_damage + self.weapon_damage_bonus

    def get_attack_knockback(self):
        return self.attack_knockback

    def is_grabbing(self):
        return self.grabbed_enemy is not None

    def start_grab(self, enemy):
        """Latch onto an enemy and begin the grab hold."""
        self.grabbed_enemy = enemy
        self.grab_timer = GRAB_MAX_FRAMES
        enemy.grabbed = True
        enemy.vel_x = 0.0
        enemy.vel_y = 0.0
        enemy.attack_timer = 0

    def release_grab(self):
        """Release the grabbed enemy without throwing."""
        if self.grabbed_enemy is not None:
            self.grabbed_enemy.grabbed = False
            self.grabbed_enemy = None
        self.grab_timer = 0
        self.grab_cooldown_timer = GRAB_COOLDOWN_FRAMES

    def equip_weapon(self, name, hits, damage_bonus, range_bonus):
        self.weapon_name = name
        self.weapon_hits_remaining = hits
        self.weapon_damage_bonus = damage_bonus
        self.weapon_range_bonus = range_bonus

    def consume_weapon_hit(self):
        if self.weapon_name is None:
            return
        self.weapon_hits_remaining -= 1
        if self.weapon_hits_remaining <= 0:
            self.weapon_name = None
            self.weapon_hits_remaining = 0
            self.weapon_damage_bonus = 0
            self.weapon_range_bonus = 0

    def draw(self, screen, camera_x=0, theme=None):
        draw_x = self.x - camera_x
        shadow_scale = SHADOW_BASE_SCALE - min(
            SHADOW_MAX_REDUCTION,
            max(0.0, (self.ground_y - self.y) / SHADOW_JUMP_DIVISOR),
        )
        lane_min = self.screen_height * 0.5
        lane_max = self.screen_height - self.height - 20
        depth_scale = get_depth_scale(self.ground_y, lane_min, lane_max)
        shadow_width = int(self.width * shadow_scale * depth_scale)
        shadow_width = max(10, shadow_width)
        shadow_height = max(4, int(shadow_width * 0.42))
        shadow_rect = pygame.Rect(
            int(draw_x + self.width / 2 - shadow_width / 2),
            int(self.ground_y + self.height + 3 - shadow_height / 2),
            shadow_width,
            shadow_height,
        )
        outer_shadow = shadow_rect.inflate(SHADOW_OUTER_INFLATE_X, SHADOW_OUTER_INFLATE_Y)
        pygame.draw.ellipse(screen, SHADOW_OUTER_COLOR, outer_shadow)
        pygame.draw.ellipse(screen, (45, 45, 45), shadow_rect)

        body_rect = pygame.Rect(int(draw_x), int(self.y), self.width, self.height)
        if self.knockdown_timer > 0:
            pose = "knockdown"
            hurt_ratio = min(1.0, self.knockdown_timer / KNOCKDOWN_STUN_FRAMES)
        elif self.hurt_anim_timer > 0:
            pose = "hurt"
            hurt_ratio = min(1.0, self.hurt_anim_timer / HURT_ANIM_FRAMES)
        elif not self.on_ground:
            if self.is_attacking() and self.current_attack_type in ("aerial_heavy", "dive_kick"):
                pose = "aerial_kick"
            elif self.is_attacking() and self.current_attack_type == "aerial_light":
                pose = "aerial_attack"
            else:
                pose = "jump"
            hurt_ratio = 0.0
        elif self.is_attacking():
            if self.current_attack_type == "crouch_punch":
                pose = "crouch_punch"
            elif self.current_attack_type == "crouch_kick":
                pose = "crouch_kick"
            elif self.current_attack_type in ("secondary", "combo3", "spin_attack"):
                pose = "kick"
            elif self.current_attack_type == "dash_punch":
                pose = "attack"
            else:
                pose = "attack"
            hurt_ratio = 0.0
        elif self.crouching:
            pose = "crouch"
            hurt_ratio = 0.0
        elif abs(self.vel_x) > 0.05:
            pose = "walk"
            hurt_ratio = 0.0
        else:
            pose = "idle"
            hurt_ratio = 0.0

        move_ratio = min(1.0, abs(self.vel_x) / self.speed) if self.speed else 0.0
        if self.attack_duration_frames <= 0:
            attack_ratio = 0.0
        else:
            attack_ratio = max(
                0.0,
                min(1.0, 1.0 - (self.attack_timer / self.attack_duration_frames)),
            )
        attack_anticipation_end = self.attack_anticipation_frames / self.attack_duration_frames
        attack_strike_end = (
            self.attack_anticipation_frames + self.attack_strike_frames
        ) / self.attack_duration_frames
        if theme is not None:
            palette = build_palette(theme, self.palette_variant, hurt=self.hurt_flash_timer > 0,
                                    suit_colour_idx=self.suit_colour_idx,
                                    hair_colour_idx=self.hair_colour_idx)
        else:
            hurt_flash = self.hurt_flash_timer > 0
            palette = {
                "chest": (236, 236, 240) if not hurt_flash else (248, 212, 212),
                "torso": (248, 248, 252) if not hurt_flash else (255, 220, 220),
                "pelvis": (238, 238, 242) if not hurt_flash else (246, 206, 206),
                "belt": (28, 28, 30),
                "head": (216, 196, 172) if not hurt_flash else (238, 210, 188),
                "face": (188, 168, 145),
                "hair": (28, 24, 20),
                "front_arm_upper": (248, 248, 252) if not hurt_flash else (255, 222, 222),
                "front_arm_lower": (242, 242, 246) if not hurt_flash else (250, 214, 214),
                "rear_arm_upper": (232, 232, 238) if not hurt_flash else (244, 206, 206),
                "rear_arm_lower": (228, 228, 234) if not hurt_flash else (240, 198, 198),
                "front_leg_upper": (246, 246, 250) if not hurt_flash else (252, 220, 220),
                "front_leg_lower": (240, 240, 246) if not hurt_flash else (248, 214, 214),
                "rear_leg_upper": (228, 228, 234) if not hurt_flash else (240, 202, 202),
                "rear_leg_lower": (222, 222, 228) if not hurt_flash else (236, 196, 196),
                "hands": (212, 190, 162),
                "feet": (202, 180, 154),
                "head_scale": 0.93,
                "shoulder_ratio": 0.26,
                "hip_ratio": 0.14,
                "arm_width": 0.19,
                "leg_width": 0.22,
                "idle_tilt": 0.01,
            }
        # Flash every other frame while jump-invincible (timer counts down every frame at 60 FPS,
        # so odd/even alternation gives a consistent 2-frame flicker).
        if self.invincible_timer > 0 and (self.invincible_timer % 2 == 0):
            return
        draw_fighter(
            screen,
            body_rect=body_rect,
            facing=self.facing,
            palette=palette,
            pose=pose,
            move_ratio=move_ratio,
            attack_ratio=attack_ratio,
            attack_anticipation_end=attack_anticipation_end,
            attack_strike_end=attack_strike_end,
            hurt_ratio=hurt_ratio,
            hit_region=self.hit_region,
            weapon_name=self.weapon_name,
        )

        # Draw held object above head (crate/barrel being carried)
        if self.held_object is not None:
            obj = self.held_object
            overhead_x = int(draw_x + self.width / 2 - obj.width / 2)
            overhead_y = int(self.y - obj.height - 6)
            obj.x = overhead_x + camera_x
            obj.y = float(overhead_y)
            obj.draw(screen, camera_x)

        pygame.draw.line(
            screen,
            (60, 60, 60),
            (int(draw_x), int(self.y + self.height)),
            (int(draw_x + self.width), int(self.y + self.height)),
            2,
        )

        attack_rect = self.get_attack_rect()
        if attack_rect is not None:
            draw_attack_rect = attack_rect.move(-int(camera_x), 0)
            if self.current_attack_type in ("aerial_light", "aerial_heavy", "dive_kick"):
                hitbox_color = AERIAL_ATTACK_HITBOX_COLOR
            elif self.current_attack_type in ("secondary", "crouch_kick", "combo3"):
                hitbox_color = SECONDARY_ATTACK_HITBOX_COLOR
            elif self.current_attack_type in SPECIAL_MOVES:
                hitbox_color = SPECIAL_ATTACK_HITBOX_COLOR
            else:
                hitbox_color = PRIMARY_ATTACK_HITBOX_COLOR
            pygame.draw.rect(screen, hitbox_color, draw_attack_rect, 2)
