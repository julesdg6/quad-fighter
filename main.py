import pygame
import sys
import os
from player import Player
from enemy import Enemy
from combat import check_attack_collision, apply_knockback
from objects import EnvironmentObject

pygame.init()

# Configuration
WIDTH, HEIGHT = 800, 600
WORLD_WIDTH = 3200
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
CAMERA_FOLLOW_RATIO = 0.45
STAGE_CLEAR_X = WORLD_WIDTH - 360
AUTO_EXIT_FRAMES = int(os.environ.get("QUAD_FIGHTER_AUTO_EXIT_FRAMES", "0"))
SCREENSHOT_PATH = os.environ.get("QUAD_FIGHTER_SCREENSHOT_PATH")

# Setup
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('Quad Fighter Prototype')
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

# Game objects
player = Player(140, HEIGHT - 112, WORLD_WIDTH, HEIGHT)
enemies_beaten = 0
last_attack_id = player.attack_id
hit_pause_timer = 0
impact_timer = 0
impact_rect = None
camera_x = 0
spawn_cursor = 0
stage_complete = False

enemy_spawn_zones = [
    {"trigger_x": 260, "count": 1},
    {"trigger_x": 760, "count": 2},
    {"trigger_x": 1280, "count": 1},
    {"trigger_x": 1800, "count": 2},
    {"trigger_x": 2360, "count": 1},
]
enemies = []
environment_objects = [
    EnvironmentObject("crate", 520, HEIGHT - 96, 44, 44, health=35, solid=True),
    EnvironmentObject("barrel", 980, HEIGHT - 108, 38, 56, health=45, solid=True),
    EnvironmentObject("pipe", 1150, HEIGHT - 72, 28, 10),
    EnvironmentObject("crate", 1540, HEIGHT - 96, 44, 44, health=35, solid=True),
    EnvironmentObject("barrel", 2120, HEIGHT - 108, 38, 56, health=45, solid=True),
    EnvironmentObject("crate", 2620, HEIGHT - 96, 44, 44, health=35, solid=True),
]
break_effects = []


def spawn_enemies(player_x, trigger_x, count):
    spawned = []
    lane_offsets = (-28, 0, 30)
    for i in range(count):
        spawn_x = max(player_x + WIDTH + 60 + i * 36, trigger_x + 420 + i * 28)
        spawn_x = min(WORLD_WIDTH - 80, spawn_x)
        enemy = Enemy(spawn_x, HEIGHT - 112, WORLD_WIDTH, HEIGHT)
        enemy.ground_y = max(
            LANE_TOP,
            min(LANE_BOTTOM - enemy.height + 20, (HEIGHT - 112) + lane_offsets[i % len(lane_offsets)]),
        )
        enemy.y = enemy.ground_y
        spawned.append(enemy)
    return spawned

# Main loop
running = True
frame_count = 0
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
        prev_player_x = player.x
        player.update()
        player_rect = player.get_rect()
        for obj in environment_objects:
            if not obj.solid or obj.health <= 0:
                continue
            obj_rect = obj.get_rect()
            if not player_rect.colliderect(obj_rect):
                continue
            if player.x > prev_player_x:
                player.x = obj.x - player.width
            elif player.x < prev_player_x:
                player.x = obj.x + obj.width
            player_rect = player.get_rect()

        while spawn_cursor < len(enemy_spawn_zones) and player.x >= enemy_spawn_zones[spawn_cursor]["trigger_x"]:
            zone = enemy_spawn_zones[spawn_cursor]
            enemies.extend(spawn_enemies(player.x, zone["trigger_x"], zone["count"]))
            spawn_cursor += 1

        for enemy in enemies:
            if enemy.health > 0:
                enemy.update(player)

        attack_started = player.attack_id != last_attack_id
        if attack_started:
            last_attack_id = player.attack_id
            pickup_rect = player.get_rect().inflate(68, 20)
            picked_weapon = None
            for obj in environment_objects:
                if obj.kind != "pipe":
                    continue
                if pickup_rect.colliderect(obj.get_rect()):
                    picked_weapon = obj
                    break
            if picked_weapon is not None:
                player.equip_weapon("pipe", hits=6, damage_bonus=8, range_bonus=20)
                environment_objects.remove(picked_weapon)

        weapon_hit_registered = False
        for enemy in enemies:
            if enemy.health <= 0:
                continue
            if check_attack_collision(player, enemy):
                enemy.health = max(0, enemy.health - player.get_attack_damage())
                apply_knockback(enemy, player)
                hit_pause_timer = HIT_PAUSE_FRAMES
                impact_timer = IMPACT_FLASH_FRAMES
                impact_rect = enemy.get_rect().copy()
                weapon_hit_registered = True

        attack_rect = player.get_attack_rect()
        if attack_rect is not None:
            for obj in list(environment_objects):
                if obj.health <= 0:
                    continue
                if not attack_rect.colliderect(obj.get_rect()):
                    continue
                if not obj.take_hit(player.attack_id, player.get_attack_damage()):
                    continue
                weapon_hit_registered = True
                hit_pause_timer = HIT_PAUSE_FRAMES
                impact_timer = IMPACT_FLASH_FRAMES
                impact_rect = obj.get_rect().copy()
                if obj.is_destroyed():
                    break_center_x = obj.x + obj.width / 2
                    break_center_y = obj.y + obj.height / 2
                    break_effects.append({"x": break_center_x, "y": break_center_y, "timer": 12})
                    if obj.kind == "barrel":
                        environment_objects.append(
                            EnvironmentObject("pipe", obj.x + 6, HEIGHT - 72, 28, 10)
                        )
                    environment_objects.remove(obj)

        if weapon_hit_registered:
            player.consume_weapon_hit()

    if impact_timer > 0:
        impact_timer -= 1

    remaining_enemies = []
    for enemy in enemies:
        if enemy.health <= 0:
            if not enemy.defeat_handled:
                enemy.defeat_handled = True
                enemies_beaten += 1
        else:
            remaining_enemies.append(enemy)
    enemies = remaining_enemies

    for effect in list(break_effects):
        effect["timer"] -= 1
        if effect["timer"] <= 0:
            break_effects.remove(effect)

    camera_target = player.x + player.width / 2 - WIDTH * CAMERA_FOLLOW_RATIO
    camera_x = max(0, min(int(camera_target), WORLD_WIDTH - WIDTH))
    if player.x < camera_x + 12:
        player.x = camera_x + 12

    stage_complete = (
        spawn_cursor >= len(enemy_spawn_zones)
        and not enemies
        and player.x >= STAGE_CLEAR_X
    )

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
    dash_offset = (-camera_x) % LANE_DASH_SPACING
    for x in range(-LANE_DASH_SPACING + dash_offset, WIDTH + LANE_DASH_SPACING, LANE_DASH_SPACING):
        pygame.draw.line(
            screen,
            (78, 78, 78),
            (x, center_lane_y),
            (x + LANE_DASH_LENGTH, center_lane_y),
            1,
        )

    drawables = []
    drawables.append(("player", player.ground_y, player))
    for enemy in enemies:
        drawables.append(("enemy", enemy.ground_y, enemy))
    for obj in environment_objects:
        drawables.append(("object", obj.y + obj.height, obj))
    drawables.sort(key=lambda item: item[1])

    for kind, _, entity in drawables:
        if kind == "player":
            entity.draw(screen, camera_x=camera_x)
        elif kind == "enemy":
            entity.draw(screen, camera_x=camera_x)
        else:
            entity.draw(screen, camera_x=camera_x)

    if impact_timer > 0 and impact_rect is not None:
        flash_rect = impact_rect.inflate(IMPACT_FLASH_INFLATE_X, IMPACT_FLASH_INFLATE_Y).move(-camera_x, 0)
        pulse_color = (230, 230, 230) if impact_timer % 2 == 0 else (200, 200, 200)
        pygame.draw.rect(screen, pulse_color, flash_rect, 2)

    for effect in break_effects:
        size = 6 + (12 - effect["timer"]) * 2
        fx = int(effect["x"] - camera_x)
        fy = int(effect["y"])
        pygame.draw.line(screen, (210, 210, 210), (fx - size, fy - size), (fx + size, fy + size), 2)
        pygame.draw.line(screen, (210, 210, 210), (fx - size, fy + size), (fx + size, fy - size), 2)

    if enemies:
        enemy_status = f"Enemies Alive: {len(enemies)}"
    elif spawn_cursor >= len(enemy_spawn_zones):
        enemy_status = "Enemies: CLEARED"
    else:
        enemy_status = "Enemies: WAITING"

    progress_pct = int((player.x / STAGE_CLEAR_X) * 100) if STAGE_CLEAR_X > 0 else 100
    progress_pct = max(0, min(progress_pct, 100))
    weapon_text = "Weapon: FISTS"
    if player.weapon_name is not None:
        weapon_text = f"Weapon: {player.weapon_name.upper()} ({player.weapon_hits_remaining})"
    hud_text = f"Player HP: {player.health}   {enemy_status}   Stage: {progress_pct}%   {weapon_text}"
    screen.blit(font.render(hud_text, True, (220, 220, 220)), (16, 16))
    if stage_complete:
        clear_text = font.render("AREA CLEAR - MOVE COMPLETE", True, (240, 240, 240))
        screen.blit(clear_text, (WIDTH // 2 - clear_text.get_width() // 2, 70))

    pygame.display.flip()
    frame_count += 1
    if SCREENSHOT_PATH is not None and frame_count == max(1, AUTO_EXIT_FRAMES):
        pygame.image.save(screen, SCREENSHOT_PATH)
    if AUTO_EXIT_FRAMES > 0 and frame_count >= AUTO_EXIT_FRAMES:
        running = False

pygame.quit()
sys.exit()
