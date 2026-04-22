import pygame
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

    def update(self, player):
        if self.hit_stun_timer > 0:
            self.hit_stun_timer -= 1
            self.vel_x = 0
        elif player.x > self.x + 4:
            self.vel_x = self.speed
        elif player.x < self.x - 4:
            self.vel_x = -self.speed
        else:
            self.vel_x = 0

        if player.ground_y > self.ground_y + 4:
            self.ground_y += 1.5
        elif player.ground_y < self.ground_y - 4:
            self.ground_y -= 1.5

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
        pygame.draw.rect(screen, (100, 100, 100), self.get_rect())
        pygame.draw.line(
            screen,
            (20, 20, 20),
            (int(self.x), int(self.y + self.height)),
            (int(self.x + self.width), int(self.y + self.height)),
            2,
        )
