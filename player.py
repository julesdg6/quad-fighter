import pygame

class Player:
    def __init__(self, x, y, width, height, screen_height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.screen_height = screen_height
        self.vel_x = 0
        self.vel_y = 0
        self.speed = 5
        self.jump_power = -15
        self.gravity = 1
        self.on_ground = False
        self.attack = False
        self.attack_timer = 0
        
    def update(self):
        # Movement
        keys = pygame.key.get_pressed()
        self.vel_x = 0
        if keys[pygame.K_LEFT]:
            self.vel_x = -self.speed
        if keys[pygame.K_RIGHT]:
            self.vel_x = self.speed
        
        # Jump
        if keys[pygame.K_SPACE] and self.on_ground:
            self.vel_y = self.jump_power
            self.on_ground = False
        
        # Attack
        if keys[pygame.K_a]:
            self.attack = True
            self.attack_timer = 10  # 10 frames attack window
        else:
            self.attack = False
        
        # Attack timer
        if self.attack_timer > 0:
            self.attack_timer -= 1
        
        # Physics
        self.vel_y += self.gravity
        self.x += self.vel_x
        self.y += self.vel_y
        
        # Boundary checking
        self.x = max(0, min(self.x, 760))
        
        # Ground check
        if self.y >= self.HEIGHT - self.height:
            self.y = HEIGHT - self.height
            self.vel_y = 0
            self.on_ground = True
        
    def draw(self, screen):
        # Draw player silhouette (polygon)
        pygame.draw.polygon(screen, (192, 192, 192), [
            (self.x, self.y),
            (self.x + self.width, self.y),
            (self.x + self.width//2, self.y - self.height)
        ])
        
        # Draw hitbox
        pygame.draw.rect(screen, (255, 0, 0), (self.x, self.y, self.width, self.height), 2)
        
        # Draw attack indicator
        if self.attack and self.attack_timer > 0:
            pygame.draw.rect(screen, (255, 255, 0), (self.x + self.width//2 - 5, self.y - 10, 10, 10), 2)