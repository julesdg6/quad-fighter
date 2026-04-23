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
HIT_PAUSE_FRAMES = 3
IMPACT_FLASH_FRAMES = 5
LANE_BAND_COUNT = 5
LANE_GUIDE_RATIO = 0.56
LANE_DASH_SPACING = 52
LANE_DASH_LENGTH = 28
IMPACT_FLASH_INFLATE_X = 26
IMPACT_FLASH_INFLATE_Y = 20

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
hit_pause_timer = 0
impact_timer = 0

# Main loop
running = True
while running:
    clock.tick(FPS)
    screen.fill((32, 32, 32))  # Greybox background

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Update / hit-stop
    if hit_pause_timer > 0:
        hit_pause_timer -= 1
    else:
        player.update()
        if enemy is not None and enemy.health > 0:
            enemy.update(player)

        # Combat
        if enemy is not None and check_attack_collision(player, enemy) and enemy.health > 0:
            enemy.health = max(0, enemy.health - 10)
            apply_knockback(enemy, player)
            hit_pause_timer = HIT_PAUSE_FRAMES
            impact_timer = IMPACT_FLASH_FRAMES

    if impact_timer > 0:
        impact_timer -= 1

    if enemy is not None and enemy.health <= 0 and not enemy.defeat_handled:
        enemy.defeat_handled = True
        enemies_beaten += 1
        if enemies_beaten == 1:
            enemy_index = 2
            enemy = Enemy(610, HEIGHT - 112, WIDTH, HEIGHT)
        else:
            enemy = None
            clear_shown = True

    # Draw
    lane_height = LANE_BOTTOM - LANE_TOP
    for i in range(LANE_BAND_COUNT):
        band_top = LANE_TOP + int(i * lane_height / LANE_BAND_COUNT)
        band_bottom = LANE_TOP + int((i + 1) * lane_height / LANE_BAND_COUNT)
        shade = 38 + i * 4
        pygame.draw.rect(screen, (shade, shade, shade), (0, band_top, WIDTH, band_bottom - band_top))
        if i > 0:
            guide = 55 + i * 4
            pygame.draw.line(screen, (guide, guide, guide), (0, band_top), (WIDTH, band_top), 1)
    pygame.draw.line(screen, (72, 72, 72), (0, LANE_TOP), (WIDTH, LANE_TOP), 2)
    pygame.draw.line(screen, (86, 86, 86), (0, LANE_BOTTOM), (WIDTH, LANE_BOTTOM), 2)
    center_lane_y = LANE_TOP + int(lane_height * LANE_GUIDE_RATIO)
    for x in range(0, WIDTH, LANE_DASH_SPACING):
        pygame.draw.line(
            screen,
            (78, 78, 78),
            (x, center_lane_y),
            (x + LANE_DASH_LENGTH, center_lane_y),
            1,
        )
    player.draw(screen)
    if enemy is not None and enemy.health > 0:
        enemy.draw(screen)
        if impact_timer > 0:
            impact_rect = enemy.get_rect().inflate(IMPACT_FLASH_INFLATE_X, IMPACT_FLASH_INFLATE_Y)
            pulse_color = (230, 230, 230) if impact_timer % 2 == 0 else (200, 200, 200)
            pygame.draw.rect(screen, pulse_color, impact_rect, 2)

    if enemy is not None:
        enemy_status = f"Enemy {enemy_index} HP: {enemy.health}"
    elif clear_shown:
        enemy_status = "Enemies: CLEARED"
    else:
        enemy_status = "Enemy HP: --"

    hud_text = f"Player HP: {player.health}   {enemy_status}"
    screen.blit(font.render(hud_text, True, (220, 220, 220)), (16, 16))
    if clear_shown:
        clear_text = font.render("AREA CLEAR", True, (240, 240, 240))
        screen.blit(clear_text, (WIDTH // 2 - clear_text.get_width() // 2, 70))

    pygame.display.flip()

pygame.quit()
sys.exit()
