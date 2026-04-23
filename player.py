import pygame
from render import draw_fighter, get_depth_scale

SHADOW_BASE_SCALE = 1.0
SHADOW_MAX_REDUCTION = 0.5
SHADOW_JUMP_DIVISOR = 120.0
SHADOW_OUTER_INFLATE_X = 6
SHADOW_OUTER_INFLATE_Y = 2
SHADOW_OUTER_COLOR = (30, 30, 30)
ATTACK_ANTICIPATION_FRAMES = 3
ATTACK_STRIKE_FRAMES = 3
ATTACK_RECOVERY_FRAMES = 5
POST_ATTACK_FRAMES = 2
ATTACK_COOLDOWN_FRAMES = 20


class Player:
    def __init__(self, x, y, screen_width, screen_height):
        self.x = float(x)
        self.y = float(y)
        self.width = 36
        self.height = 72
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ground_y = screen_height - self.height - 40
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.speed = 4
        self.lane_speed = 3
        self.jump_power = -15.0
        self.gravity = 0.8
        self.on_ground = True
        self.attack = False
        self.attack_timer = 0
        self.attack_cooldown_timer = 0
        self.attack_anticipation_frames = ATTACK_ANTICIPATION_FRAMES
        self.attack_strike_frames = ATTACK_STRIKE_FRAMES
        self.attack_recovery_frames = ATTACK_RECOVERY_FRAMES
        self.attack_duration_frames = (
            self.attack_anticipation_frames
            + self.attack_strike_frames
            + self.attack_recovery_frames
        )
        self.post_attack_frames = POST_ATTACK_FRAMES
        self.post_attack_timer = 0
        self.attack_cooldown_frames = ATTACK_COOLDOWN_FRAMES
        self.prev_attack_pressed = False
        self.attack_id = 0
        self.facing = 1
        self.health = 100

    def update(self):
        keys = pygame.key.get_pressed()
        self.vel_x = 0.0
        lane_delta = 0.0
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

        attack_pressed = keys[pygame.K_z]
        if attack_pressed and not self.prev_attack_pressed and self.attack_cooldown_timer <= 0:
            self.attack_timer = self.attack_duration_frames
            self.attack_cooldown_timer = self.attack_cooldown_frames
            self.post_attack_timer = 0
            self.attack_id += 1
        self.prev_attack_pressed = attack_pressed

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
        attack_width = 24
        attack_height = 18
        if self.facing > 0:
            attack_x = int(self.x + self.width + 2)
        else:
            attack_x = int(self.x - attack_width - 2)
        return pygame.Rect(
            attack_x,
            int(self.y + self.height // 3),
            attack_width,
            attack_height,
        )

    def draw(self, screen):
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
            int(self.x + self.width / 2 - shadow_width / 2),
            int(self.ground_y + self.height + 3 - shadow_height / 2),
            shadow_width,
            shadow_height,
        )
        outer_shadow = shadow_rect.inflate(SHADOW_OUTER_INFLATE_X, SHADOW_OUTER_INFLATE_Y)
        pygame.draw.ellipse(screen, SHADOW_OUTER_COLOR, outer_shadow)
        pygame.draw.ellipse(screen, (45, 45, 45), shadow_rect)

        body_rect = self.get_rect()
        if not self.on_ground:
            pose = "jump"
        elif self.is_attacking():
            pose = "attack"
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
                "chest": (236, 236, 240),
                "torso": (248, 248, 252),
                "pelvis": (238, 238, 242),
                "belt": (28, 28, 30),
                "head": (216, 196, 172),
                "face": (188, 168, 145),
                "hair": (28, 24, 20),
                "front_arm_upper": (248, 248, 252),
                "front_arm_lower": (242, 242, 246),
                "rear_arm_upper": (232, 232, 238),
                "rear_arm_lower": (228, 228, 234),
                "front_leg_upper": (246, 246, 250),
                "front_leg_lower": (240, 240, 246),
                "rear_leg_upper": (228, 228, 234),
                "rear_leg_lower": (222, 222, 228),
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
            (int(self.x), int(self.y + self.height)),
            (int(self.x + self.width), int(self.y + self.height)),
            2,
        )

        attack_rect = self.get_attack_rect()
        if attack_rect is not None:
            pygame.draw.rect(screen, (255, 220, 0), attack_rect, 2)
