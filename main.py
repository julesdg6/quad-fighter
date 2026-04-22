import pygame
import sys
from player import Player
from enemy import Enemy
from combat import check_attack_collision, apply_knockback

pygame.init()

# Configuration
WIDTH, HEIGHT = 800, 600
FPS = 60

# Setup
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('Quad Fighter Prototype')
clock = pygame.time.Clock()

# Game objects
    player = Player(WIDTH//2, HEIGHT//2, WIDTH, HEIGHT, HEIGHT)
    enemy = Enemy(WIDTH//2, 50, WIDTH, HEIGHT)

# Main loop
running = True
while running:
    clock.tick(FPS)
    screen.fill((32, 32, 32))  # Greybox background

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Update
    player.update()
    enemy.update(player)

    # Combat
    if check_attack_collision(player, enemy):
        apply_knockback(enemy, player)

    # Draw
    player.draw(screen)
    enemy.draw(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()