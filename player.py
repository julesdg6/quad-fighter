import pygame
from render import draw_fighter

SHADOW_BASE_SCALE = 0.9
SHADOW_MAX_REDUCTION = 0.5
SHADOW_JUMP_DIVISOR = 120.0


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
        self.attack_cooldown_frames = 18
        self.attack_duration_frames = 8
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
            self.attack_id += 1
        self.prev_attack_pressed = attack_pressed

        if self.attack_timer > 0:
            self.attack_timer -= 1
        self.attack = self.attack_timer > 0

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

    def get_attack_rect(self):
        if self.attack_timer <= 0:
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
        shadow_width = int(self.width * shadow_scale)
        shadow_width = max(10, shadow_width)
        shadow_height = max(4, int(shadow_width * 0.35))
        shadow_rect = pygame.Rect(
            int(self.x + self.width / 2 - shadow_width / 2),
            int(self.ground_y + self.height + 3 - shadow_height / 2),
            shadow_width,
            shadow_height,
        )
        pygame.draw.ellipse(screen, (45, 45, 45), shadow_rect)

        body_rect = self.get_rect()
        if not self.on_ground:
            pose = "jump"
        elif self.attack_timer > 0:
            pose = "attack"
        elif abs(self.vel_x) > 0.05:
            pose = "walk"
        else:
            pose = "idle"

        move_ratio = min(1.0, abs(self.vel_x) / self.speed) if self.speed else 0.0
        if self.attack_duration_frames <= 0:
            attack_ratio = 0.0
        else:
            attack_ratio = max(0.0, min(1.0, 1.0 - (self.attack_timer / self.attack_duration_frames)))
        draw_fighter(
            screen,
            body_rect=body_rect,
            facing=self.facing,
            palette={
                "torso": (172, 172, 172),
                "head": (205, 205, 205),
                "face": (145, 145, 145),
                "front_arm": (160, 160, 160),
                "rear_arm": (152, 152, 152),
                "leg": (152, 152, 152),
            },
            pose=pose,
            move_ratio=move_ratio,
            attack_ratio=attack_ratio,
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
