import pygame
from render import draw_fighter, get_depth_scale

SHADOW_BASE_SCALE = 1.0
SHADOW_MAX_REDUCTION = 0.5
SHADOW_JUMP_DIVISOR = 120.0
SHADOW_OUTER_INFLATE_X = 12
SHADOW_OUTER_INFLATE_Y = 4
SHADOW_OUTER_COLOR = (30, 30, 30)
POST_ATTACK_FRAMES = 2
CHARACTER_SCALE = 2
PRIMARY_ATTACK_HITBOX_COLOR = (255, 220, 0)
SECONDARY_ATTACK_HITBOX_COLOR = (255, 150, 64)

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
        self.facing = 1
        self.max_health = 100
        self.health = self.max_health
        self.weapon_name = None
        self.weapon_hits_remaining = 0
        self.weapon_damage_bonus = 0
        self.weapon_range_bonus = 0

    def update(self):
        keys = pygame.key.get_pressed()
        primary_pressed = keys[pygame.K_z]
        secondary_pressed = keys[pygame.K_x]
        if self.hurt_anim_timer > 0:
            self.hurt_anim_timer -= 1
        if self.hurt_flash_timer > 0:
            self.hurt_flash_timer -= 1
        self.vel_x = 0.0
        lane_delta = 0.0
        if self.hit_stun_timer > 0:
            self.hit_stun_timer -= 1
        else:
            if keys[pygame.K_LEFT]:
                self.vel_x = -self.speed
                self.facing = -1
            elif keys[pygame.K_RIGHT]:
                self.vel_x = self.speed
                self.facing = 1
            if self.on_ground:
                if keys[pygame.K_UP]:
                    lane_delta -= self.lane_speed
                elif keys[pygame.K_DOWN]:
                    lane_delta += self.lane_speed

            if keys[pygame.K_SPACE] and self.on_ground:
                self.vel_y = self.jump_power
                self.on_ground = False

            triggered_attack = None
            if (
                secondary_pressed
                and not self.prev_secondary_pressed
                and self.attack_cooldown_timer <= 0
                and not self.is_attacking()
            ):
                triggered_attack = "secondary"
            elif (
                primary_pressed
                and not self.prev_primary_pressed
                and self.attack_cooldown_timer <= 0
                and not self.is_attacking()
            ):
                triggered_attack = "primary"
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
        self.prev_primary_pressed = primary_pressed
        self.prev_secondary_pressed = secondary_pressed

        prev_attack_timer = self.attack_timer
        if self.attack_timer > 0:
            self.attack_timer -= 1
        elif self.post_attack_timer > 0:
            self.post_attack_timer -= 1
        if prev_attack_timer > 0 and self.attack_timer == 0:
            self.post_attack_timer = self.post_attack_frames

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
        # Secondary (kick) hitbox sits at lower body/leg level
        y_ratio = 0.55 if self.current_attack_type == "secondary" else 0.30
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

    def draw(self, screen, camera_x=0):
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
        if self.hurt_anim_timer > 0:
            pose = "hurt"
        elif not self.on_ground:
            pose = "jump"
        elif self.is_attacking():
            pose = "kick" if self.current_attack_type == "secondary" else "attack"
        elif abs(self.vel_x) > 0.05:
            pose = "walk"
        else:
            pose = "idle"

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
        draw_fighter(
            screen,
            body_rect=body_rect,
            facing=self.facing,
            palette={
                "chest": (236, 236, 240) if self.hurt_flash_timer <= 0 else (248, 212, 212),
                "torso": (248, 248, 252) if self.hurt_flash_timer <= 0 else (255, 220, 220),
                "pelvis": (238, 238, 242) if self.hurt_flash_timer <= 0 else (246, 206, 206),
                "belt": (28, 28, 30),
                "head": (216, 196, 172) if self.hurt_flash_timer <= 0 else (238, 210, 188),
                "face": (188, 168, 145),
                "hair": (28, 24, 20),
                "front_arm_upper": (248, 248, 252) if self.hurt_flash_timer <= 0 else (255, 222, 222),
                "front_arm_lower": (242, 242, 246) if self.hurt_flash_timer <= 0 else (250, 214, 214),
                "rear_arm_upper": (232, 232, 238) if self.hurt_flash_timer <= 0 else (244, 206, 206),
                "rear_arm_lower": (228, 228, 234) if self.hurt_flash_timer <= 0 else (240, 198, 198),
                "front_leg_upper": (246, 246, 250) if self.hurt_flash_timer <= 0 else (252, 220, 220),
                "front_leg_lower": (240, 240, 246) if self.hurt_flash_timer <= 0 else (248, 214, 214),
                "rear_leg_upper": (228, 228, 234) if self.hurt_flash_timer <= 0 else (240, 202, 202),
                "rear_leg_lower": (222, 222, 228) if self.hurt_flash_timer <= 0 else (236, 196, 196),
                "hands": (212, 190, 162),
                "feet": (202, 180, 154),
                "head_scale": 0.93,
                "shoulder_ratio": 0.26,
                "hip_ratio": 0.2,
                "arm_width": 0.19,
                "leg_width": 0.22,
                "idle_tilt": 0.01,
            },
            pose=pose,
            move_ratio=move_ratio,
            attack_ratio=attack_ratio,
            attack_anticipation_end=attack_anticipation_end,
            attack_strike_end=attack_strike_end,
        )

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
            hitbox_color = (
                PRIMARY_ATTACK_HITBOX_COLOR
                if self.current_attack_type == "primary"
                else SECONDARY_ATTACK_HITBOX_COLOR
            )
            pygame.draw.rect(screen, hitbox_color, draw_attack_rect, 2)
