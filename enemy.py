import pygame

LANE_CHASE_THRESHOLD = 4
LANE_CHASE_SPEED = 1.5
SHADOW_BASE_SCALE = 0.9
SHADOW_MAX_REDUCTION = 0.5
SHADOW_JUMP_DIVISOR = 120.0

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
        self.last_hit_attack_id = -1
        self.defeat_handled = False

    def update(self, player):
        if self.hurt_flash_timer > 0:
            self.hurt_flash_timer -= 1

        if self.health <= 0:
            return

        if self.hit_stun_timer > 0:
            self.hit_stun_timer -= 1
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
        shadow_width = int(self.width * shadow_scale)
        shadow_width = max(10, shadow_width)
        shadow_height = max(4, int(shadow_width * 0.35))
        shadow_rect = pygame.Rect(
            int(self.x + self.width / 2 - shadow_width / 2),
            int(self.ground_y + self.height + 3 - shadow_height / 2),
            shadow_width,
            shadow_height,
        )
        pygame.draw.ellipse(screen, (35, 35, 35), shadow_rect)

        body_color = (220, 220, 220) if self.hurt_flash_timer > 0 else (100, 100, 100)
        pygame.draw.rect(screen, body_color, self.get_rect())
        pygame.draw.line(
            screen,
            (20, 20, 20),
            (int(self.x), int(self.y + self.height)),
            (int(self.x + self.width), int(self.y + self.height)),
            2,
        )
