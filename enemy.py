import pygame
class Enemy:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.vel_x = 0
        self.vel_y = 0
        self.speed = 3
        self.gravity = 1
        self.on_ground = False
        
    def update(self, player):
        # Simple chase logic
        if player.x > self.x:
            self.vel_x = self.speed
        elif player.x < self.x:
            self.vel_x = -self.speed
        else:
            self.vel_x = 0
        
        # Physics
        self.vel_y += self.gravity
        self.x += self.vel_x
        self.y += self.vel_y
        
        # Boundary checking
        self.x = max(0, min(self.x, 760))
        
        # Ground check
        if self.y >= self.height - self.height:
            self.y = HEIGHT - self.height
            self.vel_y = 0
            self.on_ground = True
        
    def draw(self, screen):
        # Draw enemy silhouette (polygon)
        pygame.draw.polygon(screen, (128, 128, 128), [
            (self.x, self.y),
            (self.x + self.width, self.y),
            (self.x + self.width//2, self.y - self.height)
        ])
        
        # Draw hitbox
        pygame.draw.rect(screen, (0, 0, 255), (self.x, self.y, self.width, self.height), 2)