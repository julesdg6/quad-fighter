import pygame
from render import draw_fighter, get_depth_scale

LANE_CHASE_THRESHOLD = 4
LANE_CHASE_SPEED = 1.5
SHADOW_BASE_SCALE = 1.0
SHADOW_MAX_REDUCTION = 0.5
SHADOW_JUMP_DIVISOR = 120.0
HURT_ANIMATION_DURATION_FRAMES = 14.0
SHADOW_OUTER_INFLATE_X = 6
SHADOW_OUTER_INFLATE_Y = 2
SHADOW_OUTER_COLOR = (30, 30, 30)

class Enemy:
    def __init__(self, x, y, screen_width, screen_height):
        self.x = float(x)
        self.y = float(y)
        self.width = 36
        self.height = 72
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ground_y = y
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.speed = 3
        self.gravity = 0.8
        self.on_ground = True
        self.health = 100
        self.hit_stun_timer = 0
        self.hurt_flash_timer = 0
        self.hurt_anim_timer = 0
        self.last_hit_attack_id = -1
        self.defeat_handled = False
        self.facing = -1

    def update(self, player):
        if self.hurt_flash_timer > 0:
            self.hurt_flash_timer -= 1
        if self.hurt_anim_timer > 0:
            self.hurt_anim_timer -= 1

        if self.health <= 0:
            return

        if self.hit_stun_timer > 0:
            self.hit_stun_timer -= 1
            self.hurt_anim_timer = max(self.hurt_anim_timer, int(HURT_ANIMATION_DURATION_FRAMES))
            self.vel_x = 0
        else:
            if player.x > self.x + 4:
                self.vel_x = self.speed
            elif player.x < self.x - 4:
                self.vel_x = -self.speed
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
        pygame.draw.ellipse(screen, (38, 38, 38), shadow_rect)

        hurt_flash = self.hurt_flash_timer > 0
        body_rect = self.get_rect()
        if self.hurt_anim_timer > 0:
            pose = "hurt"
        elif abs(self.vel_x) > 0.05:
            pose = "walk"
        else:
            pose = "idle"

        move_ratio = min(1.0, abs(self.vel_x) / self.speed) if self.speed else 0.0
        hurt_ratio = min(1.0, self.hurt_anim_timer / HURT_ANIMATION_DURATION_FRAMES)
        draw_fighter(
            screen,
            body_rect=body_rect,
            facing=self.facing,
            palette={
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
                "hip_ratio": 0.19,
                "arm_width": 0.21,
                "leg_width": 0.2,
                "idle_tilt": -0.06,
                "idle_shift": 0.03,
            },
            pose=pose,
            move_ratio=move_ratio,
            hurt_ratio=hurt_ratio,
            phase_offset=self.x * 0.01,
        )

        pygame.draw.line(
            screen,
            (20, 20, 20),
            (int(self.x), int(self.y + self.height)),
            (int(self.x + self.width), int(self.y + self.height)),
            2,
        )
