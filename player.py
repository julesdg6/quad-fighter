import pygame

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
        self.health = 100

    def update(self):
        keys = pygame.key.get_pressed()
        self.vel_x = 0.0
        lane_delta = 0.0
        if keys[pygame.K_LEFT]:
            self.vel_x = -self.speed
        if keys[pygame.K_RIGHT]:
            self.vel_x = self.speed
        if keys[pygame.K_UP]:
            lane_delta -= self.lane_speed
        if keys[pygame.K_DOWN]:
            lane_delta += self.lane_speed

        if keys[pygame.K_SPACE] and self.on_ground:
            self.vel_y = self.jump_power
            self.on_ground = False

        if keys[pygame.K_z]:
            self.attack = True
            self.attack_timer = 10
        else:
            self.attack = False

        if self.attack_timer > 0:
            self.attack_timer -= 1

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
        return pygame.Rect(
            int(self.x + self.width),
            int(self.y + self.height // 3),
            20,
            14,
        )

    def draw(self, screen):
        pygame.draw.rect(screen, (192, 192, 192), self.get_rect())
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
