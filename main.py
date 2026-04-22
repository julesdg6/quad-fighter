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
font = pygame.font.SysFont(None, 24)

# Game objects
player = Player(140, HEIGHT - 112, WIDTH, HEIGHT)
enemy = Enemy(520, HEIGHT - 112, WIDTH, HEIGHT)

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
    if check_attack_collision(player, enemy) and enemy.health > 0:
        enemy.health = max(0, enemy.health - 10)
        apply_knockback(enemy, player)

    # Draw
    pygame.draw.line(screen, (55, 55, 55), (0, int(HEIGHT * 0.5)), (WIDTH, int(HEIGHT * 0.5)), 1)
    player.draw(screen)
    if enemy.health > 0:
        enemy.draw(screen)

    hud_text = f"Player HP: {player.health}   Enemy HP: {enemy.health}"
    screen.blit(font.render(hud_text, True, (220, 220, 220)), (16, 16))

    pygame.display.flip()

pygame.quit()
sys.exit()
