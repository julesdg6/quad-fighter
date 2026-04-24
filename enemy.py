import pygame
from render import draw_fighter, get_depth_scale
from combat import KNOCKDOWN_STUN_FRAMES

LANE_CHASE_THRESHOLD = 4
LANE_CHASE_SPEED = 1.5
GROUND_Y_ATTACK_THRESHOLD = 18
SHADOW_BASE_SCALE = 1.0
SHADOW_MAX_REDUCTION = 0.5
SHADOW_JUMP_DIVISOR = 120.0
HURT_ANIMATION_DURATION_FRAMES = 14.0
SHADOW_OUTER_INFLATE_X = 12
SHADOW_OUTER_INFLATE_Y = 4
SHADOW_OUTER_COLOR = (30, 30, 30)
TELEGRAPH_PULSE_BASE = 90
TELEGRAPH_PULSE_RANGE = 70
TELEGRAPH_PULSE_FREQUENCY = 8
CHARACTER_SCALE = 2
ENEMY_SEPARATION_DIST = 48  # minimum extra gap between enemy centre-points beyond combined half-widths


ENEMY_ATTACK_PROFILE = {
    "anticipation": 5,
    "strike": 4,
    "recovery": 8,
    "cooldown": 28,
    "damage": 10,
    "attack_width": 68,
    "attack_height": 52,
    "attack_offset": 8,
    "attack_knockback": 52,
    "engage_distance": 68,
}

BRAWLER_ATTACK_PROFILE = {
    "anticipation": 7,
    "strike": 5,
    "recovery": 10,
    "cooldown": 30,
    "damage": 14,
    "attack_width": 88,
    "attack_height": 60,
    "attack_offset": 8,
    "attack_knockback": 68,
    "engage_distance": 80,
}

BOSS_ATTACK_PROFILE = {
    "anticipation": 10,
    "strike": 6,
    "recovery": 12,
    "cooldown": 42,
    "damage": 16,
    "attack_width": 112,
    "attack_height": 68,
    "attack_offset": 10,
    "attack_knockback": 92,
    "engage_distance": 96,
}
BOSS_MAX_HEALTH = 280
BOSS_CHARGE_SPEED = 5.2
BOSS_CHARGE_DURATION = 20
BOSS_CHARGE_COOLDOWN = 90
BOSS_CHARGE_TRIGGER_DIST = 280
BOSS_PHASE2_HEALTH_RATIO = 0.5
BOSS_PHASE2_MIN_COOLDOWN = 22


class Enemy:
    def __init__(self, x, y, screen_width, screen_height, is_boss=False, variant="raider"):
        self.is_boss = is_boss
        self.variant = variant
        self.x = float(x)
        self.y = float(y)
        if self.is_boss:
            self.width = int(66 * CHARACTER_SCALE)
            self.height = int(124 * CHARACTER_SCALE)
            self.speed = 2.1
            self.health = BOSS_MAX_HEALTH
            profile = BOSS_ATTACK_PROFILE
        else:
            if self.variant == "brawler":
                self.width = int(56 * CHARACTER_SCALE)
                self.height = int(104 * CHARACTER_SCALE)
                self.speed = 2.2
                self.health = 150
                profile = BRAWLER_ATTACK_PROFILE
            else:
                self.width = int(48 * CHARACTER_SCALE)
                self.height = int(96 * CHARACTER_SCALE)
                self.speed = 2.8
                self.health = 120
                profile = ENEMY_ATTACK_PROFILE
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ground_y = y
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.gravity = 0.8
        self.on_ground = True
        self.hit_stun_timer = 0
        self.hurt_flash_timer = 0
        self.hurt_anim_timer = 0
        self.attack_timer = 0
        self.attack_cooldown_timer = 0
        self.attack_id = 0
        self.attack_anticipation_frames = profile["anticipation"]
        self.attack_strike_frames = profile["strike"]
        self.attack_recovery_frames = profile["recovery"]
        self.attack_duration_frames = (
            self.attack_anticipation_frames
            + self.attack_strike_frames
            + self.attack_recovery_frames
        )
        self.attack_cooldown_frames = profile["cooldown"]
        self.attack_damage = profile["damage"]
        self.attack_width = profile["attack_width"]
        self.attack_height = profile["attack_height"]
        self.attack_offset = profile["attack_offset"]
        self.attack_knockback = profile["attack_knockback"]
        self.engage_distance = profile["engage_distance"]
        self.last_hit_attack_id = -1
        self.last_hit_player_attack_id = -1
        self.defeat_handled = False
        self.facing = -1
        self.charge_timer = 0
        self.charge_cooldown_timer = 0
        self.hit_region = "torso"
        self.knockdown_timer = 0

    def update(self, player, enemies=None):
        if self.hurt_flash_timer > 0:
            self.hurt_flash_timer -= 1
        if self.hurt_anim_timer > 0:
            self.hurt_anim_timer -= 1
        if self.knockdown_timer > 0:
            self.knockdown_timer -= 1
            # Keep character frozen until knockdown timer expires
            self.hit_stun_timer = max(self.hit_stun_timer, 1)
            self.hurt_anim_timer = max(self.hurt_anim_timer, 1)
        if self.attack_cooldown_timer > 0:
            self.attack_cooldown_timer -= 1

        if self.health <= 0:
            return

        if self.hit_stun_timer > 0:
            self.hit_stun_timer -= 1
            self.hurt_anim_timer = max(self.hurt_anim_timer, int(HURT_ANIMATION_DURATION_FRAMES))
            self.vel_x = 0
            self.attack_timer = 0
            self.charge_timer = 0
        elif self.attack_timer > 0:
            self.attack_timer -= 1
            self.vel_x = 0
        else:
            player_center_x = player.x + player.width * 0.5
            enemy_center_x = self.x + self.width * 0.5

            # Boss charge behaviour
            effective_speed = self.speed
            if self.is_boss:
                if self.charge_timer > 0:
                    self.charge_timer -= 1
                    effective_speed = BOSS_CHARGE_SPEED
                elif self.charge_cooldown_timer > 0:
                    self.charge_cooldown_timer -= 1
                else:
                    dist = abs(player_center_x - enemy_center_x)
                    if dist > BOSS_CHARGE_TRIGGER_DIST and not self.should_attack(player):
                        self.charge_timer = BOSS_CHARGE_DURATION
                        self.charge_cooldown_timer = BOSS_CHARGE_COOLDOWN

            # Attack stagger: non-boss enemies wait if a peer is already mid-attack
            peer_is_attacking = (
                not self.is_boss
                and enemies is not None
                and any(
                    e is not self and e.health > 0 and not e.is_boss and e.is_attacking()
                    for e in enemies
                )
            )

            if not peer_is_attacking and self.should_attack(player):
                self.attack_timer = self.attack_duration_frames
                # Phase-2 enrage: boss attacks faster below 50% health
                cooldown = self.attack_cooldown_frames
                if self.is_boss and self.health < BOSS_MAX_HEALTH * BOSS_PHASE2_HEALTH_RATIO:
                    cooldown = max(BOSS_PHASE2_MIN_COOLDOWN, cooldown // 2)
                self.attack_cooldown_timer = cooldown
                self.attack_id += 1
                self.vel_x = 0
            elif player_center_x > enemy_center_x + 4:
                self.vel_x = effective_speed
            elif player_center_x < enemy_center_x - 4:
                self.vel_x = -effective_speed
            else:
                self.vel_x = 0

            if player.ground_y > self.ground_y + LANE_CHASE_THRESHOLD:
                self.ground_y += LANE_CHASE_SPEED
            elif player.ground_y < self.ground_y - LANE_CHASE_THRESHOLD:
                self.ground_y -= LANE_CHASE_SPEED

        if player.x > self.x + 1:
            self.facing = 1
        elif player.x < self.x - 1:
            self.facing = -1
        elif self.vel_x > 0:
            self.facing = 1
        elif self.vel_x < 0:
            self.facing = -1

        self.vel_y += self.gravity
        self.x += self.vel_x
        self.y += self.vel_y

        # Separate from overlapping peer enemies to prevent unnatural stacking
        if enemies:
            for other in enemies:
                if other is self or other.health <= 0:
                    continue
                dx = (self.x + self.width / 2) - (other.x + other.width / 2)
                min_sep = (self.width + other.width) / 2 + ENEMY_SEPARATION_DIST
                if abs(dx) < min_sep:
                    push = (min_sep - abs(dx)) * 0.25
                    if dx > 0:
                        self.x += push
                    elif dx < 0:
                        self.x -= push
                    else:
                        self.x += push  # tied: nudge right

        self.x = max(0, min(self.x, self.screen_width - self.width))
        lane_min = self.screen_height * 0.5
        lane_max = self.screen_height - self.height - 20
        self.ground_y = max(lane_min, min(self.ground_y, lane_max))
        if self.y >= self.ground_y:
            self.y = self.ground_y
            self.vel_y = 0.0
            self.on_ground = True

    def should_attack(self, player):
        if self.attack_cooldown_timer > 0:
            return False
        if abs(player.ground_y - self.ground_y) > GROUND_Y_ATTACK_THRESHOLD:
            return False
        hitbox_separation = max(
            0.0,
            max(self.x, player.x) - min(self.x + self.width, player.x + player.width),
        )
        return hitbox_separation <= self.engage_distance

    def is_attacking(self):
        return self.attack_timer > 0

    def get_attack_rect(self):
        if self.attack_timer <= 0:
            return None
        elapsed = self.attack_duration_frames - self.attack_timer
        strike_start = self.attack_anticipation_frames
        strike_end = strike_start + self.attack_strike_frames
        if elapsed < strike_start or elapsed >= strike_end:
            return None
        if self.facing > 0:
            attack_x = int(self.x + self.width + self.attack_offset)
        else:
            attack_x = int(self.x - self.attack_width - self.attack_offset)
        return pygame.Rect(
            attack_x,
            int(self.y + self.height * 0.3),
            self.attack_width,
            self.attack_height,
        )

    def get_rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def is_attack_windup(self):
        if self.attack_timer <= 0:
            return False
        elapsed = self.attack_duration_frames - self.attack_timer
        return elapsed < self.attack_anticipation_frames

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
        pygame.draw.ellipse(screen, (38, 38, 38), shadow_rect)

        hurt_flash = self.hurt_flash_timer > 0
        body_rect = pygame.Rect(int(draw_x), int(self.y), self.width, self.height)
        if self.knockdown_timer > 0:
            pose = "knockdown"
            hurt_ratio = min(1.0, self.knockdown_timer / KNOCKDOWN_STUN_FRAMES)
        elif self.hurt_anim_timer > 0:
            pose = "hurt"
            hurt_ratio = min(1.0, self.hurt_anim_timer / HURT_ANIMATION_DURATION_FRAMES)
        elif self.attack_timer > 0:
            pose = "attack"
            hurt_ratio = 0.0
        elif abs(self.vel_x) > 0.05:
            pose = "walk"
            hurt_ratio = 0.0
        else:
            pose = "idle"
            hurt_ratio = 0.0

        move_ratio = min(1.0, abs(self.vel_x) / self.speed) if self.speed else 0.0
        attack_ratio = max(
            0.0,
            min(1.0, 1.0 - (self.attack_timer / self.attack_duration_frames)),
        )
        attack_anticipation_end = self.attack_anticipation_frames / self.attack_duration_frames
        attack_strike_end = (
            self.attack_anticipation_frames + self.attack_strike_frames
        ) / self.attack_duration_frames
        if self.is_boss:
            palette = {
                "chest": (128, 54, 48) if not hurt_flash else (210, 126, 120),
                "torso": (58, 58, 62) if not hurt_flash else (204, 204, 210),
                "pelvis": (84, 64, 124) if not hurt_flash else (174, 158, 226),
                "head": (176, 142, 112) if not hurt_flash else (238, 216, 196),
                "face": (130, 102, 82),
                "hair": (24, 20, 20),
                "front_arm_upper": (72, 72, 76) if not hurt_flash else (204, 204, 210),
                "front_arm_lower": (124, 84, 72) if not hurt_flash else (206, 178, 170),
                "rear_arm_upper": (56, 56, 60) if not hurt_flash else (190, 190, 198),
                "rear_arm_lower": (112, 76, 66) if not hurt_flash else (194, 168, 160),
                "front_leg_upper": (78, 70, 142) if not hurt_flash else (174, 166, 238),
                "front_leg_lower": (62, 56, 118) if not hurt_flash else (162, 154, 224),
                "rear_leg_upper": (56, 50, 102) if not hurt_flash else (154, 146, 212),
                "rear_leg_lower": (46, 42, 86) if not hurt_flash else (146, 138, 202),
                "hands": (176, 140, 112),
                "feet": (48, 48, 52),
                "head_scale": 0.92,
                "shoulder_ratio": 0.31,
                "hip_ratio": 0.14,
                "leg_width": 0.22,
                "idle_tilt": -0.08,
                "idle_shift": 0.04,
            }
        else:
            if self.variant == "brawler":
                palette = {
                    "chest": (72, 72, 46) if not hurt_flash else (186, 186, 126),
                    "torso": (48, 54, 52) if not hurt_flash else (180, 192, 186),
                    "pelvis": (84, 74, 44) if not hurt_flash else (206, 182, 132),
                    "head": (176, 146, 118) if not hurt_flash else (234, 214, 196),
                    "face": (130, 104, 84),
                    "hair": (34, 32, 24),
                    "front_arm_upper": (84, 86, 62) if not hurt_flash else (198, 204, 170),
                    "front_arm_lower": (118, 88, 66) if not hurt_flash else (206, 182, 166),
                    "rear_arm_upper": (70, 72, 52) if not hurt_flash else (184, 188, 160),
                    "rear_arm_lower": (106, 78, 60) if not hurt_flash else (194, 172, 154),
                    "front_leg_upper": (88, 80, 46) if not hurt_flash else (212, 194, 132),
                    "front_leg_lower": (70, 64, 38) if not hurt_flash else (196, 178, 124),
                    "rear_leg_upper": (78, 70, 40) if not hurt_flash else (198, 182, 128),
                    "rear_leg_lower": (62, 56, 34) if not hurt_flash else (184, 170, 120),
                    "hands": (172, 138, 112),
                    "feet": (50, 48, 42),
                    "head_scale": 0.88,
                    "shoulder_ratio": 0.33,
                    "hip_ratio": 0.15,
                    "arm_width": 0.24,
                    "leg_width": 0.24,
                    "idle_tilt": -0.04,
                    "idle_shift": 0.02,
                }
            else:
                palette = {
                    "chest": (88, 44, 38) if not hurt_flash else (180, 126, 120),
                    "torso": (52, 52, 56) if not hurt_flash else (186, 186, 192),
                    "pelvis": (44, 56, 88) if not hurt_flash else (146, 162, 200),
                    "head": (170, 138, 112) if not hurt_flash else (224, 208, 188),
                    "face": (126, 100, 82),
                    "hair": (24, 24, 24),
                    "front_arm_upper": (58, 58, 62) if not hurt_flash else (196, 196, 202),
                    "front_arm_lower": (102, 70, 62) if not hurt_flash else (196, 170, 162),
                    "rear_arm_upper": (44, 44, 48) if not hurt_flash else (182, 182, 188),
                    "rear_arm_lower": (90, 62, 56) if not hurt_flash else (184, 160, 152),
                    "front_leg_upper": (50, 66, 104) if not hurt_flash else (158, 176, 214),
                    "front_leg_lower": (38, 50, 84) if not hurt_flash else (148, 166, 202),
                    "rear_leg_upper": (36, 48, 76) if not hurt_flash else (140, 158, 192),
                    "rear_leg_lower": (30, 38, 62) if not hurt_flash else (130, 148, 184),
                    "hands": (168, 134, 108),
                    "feet": (44, 44, 48),
                    "head_scale": 0.9,
                    "shoulder_ratio": 0.29,
                    "hip_ratio": 0.13,
                    "arm_width": 0.21,
                    "leg_width": 0.2,
                    "idle_tilt": -0.06,
                    "idle_shift": 0.03,
                }
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
            phase_offset=self.x * 0.01,
            hit_region=self.hit_region,
        )

        if self.is_attack_windup():
            windup_ratio = 1.0 - (self.attack_timer / self.attack_duration_frames)
            pulse = TELEGRAPH_PULSE_BASE + int(
                TELEGRAPH_PULSE_RANGE * abs((windup_ratio * TELEGRAPH_PULSE_FREQUENCY) % 2 - 1)
            )
            intent_width = self.attack_width + 10
            if self.facing > 0:
                intent_x = int(draw_x + self.width + self.attack_offset - 3)
            else:
                intent_x = int(draw_x - intent_width - self.attack_offset + 3)
            intent_rect = pygame.Rect(intent_x, int(self.y + self.height * 0.33), intent_width, self.attack_height)
            pygame.draw.rect(screen, (pulse, 66, 66), intent_rect, 2)

        pygame.draw.line(
            screen,
            (12, 12, 12) if self.is_boss else (20, 20, 20),
            (int(draw_x), int(self.y + self.height)),
            (int(draw_x + self.width), int(self.y + self.height)),
            2,
        )
