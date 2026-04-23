import pygame
import sys
from player import Player
from enemy import Enemy
from combat import check_attack_collision, apply_knockback

pygame.init()

# Configuration
WIDTH, HEIGHT = 800, 600
FPS = 60
LANE_TOP = int(HEIGHT * 0.5)
LANE_BOTTOM = HEIGHT - 92

# Setup
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('Quad Fighter Prototype')
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

# Game objects
player = Player(140, HEIGHT - 112, WIDTH, HEIGHT)
enemy_index = 1
enemy = Enemy(520, HEIGHT - 112, WIDTH, HEIGHT)
enemies_beaten = 0
clear_shown = False

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
    if enemy is not None and enemy.health > 0:
        enemy.update(player)

    # Combat
    if enemy is not None and check_attack_collision(player, enemy) and enemy.health > 0:
        enemy.health = max(0, enemy.health - 10)
        apply_knockback(enemy, player)

    if enemy is not None and enemy.health <= 0:
        enemies_beaten += 1
        if enemies_beaten == 1:
            enemy_index = 2
            enemy = Enemy(610, HEIGHT - 112, WIDTH, HEIGHT)
        else:
            enemy = None
            clear_shown = True

    # Draw
    pygame.draw.rect(screen, (40, 40, 40), (0, LANE_TOP, WIDTH, LANE_BOTTOM - LANE_TOP))
    pygame.draw.line(screen, (68, 68, 68), (0, LANE_TOP), (WIDTH, LANE_TOP), 2)
    pygame.draw.line(screen, (78, 78, 78), (0, LANE_BOTTOM), (WIDTH, LANE_BOTTOM), 2)
    player.draw(screen)
    if enemy is not None and enemy.health > 0:
        enemy.draw(screen)

    if enemy is not None:
        enemy_status = f"Enemy {enemy_index} HP: {enemy.health}"
    elif clear_shown:
        enemy_status = "Enemies: CLEARED"
    else:
        enemy_status = "Enemy HP: --"

    hud_text = f"Player HP: {player.health}   {enemy_status}"
    screen.blit(font.render(hud_text, True, (220, 220, 220)), (16, 16))
    cooldown_text = f"Attack CD: {player.attack_cooldown_timer}"
    screen.blit(font.render(cooldown_text, True, (190, 190, 190)), (16, 40))

    if clear_shown:
        clear_text = font.render("AREA CLEAR", True, (240, 240, 240))
        screen.blit(clear_text, (WIDTH // 2 - clear_text.get_width() // 2, 70))

    pygame.display.flip()

pygame.quit()
sys.exit()
