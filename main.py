import pygame
import sys
import os
from player import Player
from enemy import Enemy, BOSS_MAX_HEALTH
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
BOSS_TRIGGER_X = WORLD_WIDTH - 520
BOSS_SPAWN_X = WORLD_WIDTH - 220
QUAD_FIGHTER_AUTO_EXIT_FRAMES = int(os.environ.get("QUAD_FIGHTER_AUTO_EXIT_FRAMES", "0"))
QUAD_FIGHTER_SCREENSHOT_PATH = os.environ.get("QUAD_FIGHTER_SCREENSHOT_PATH")
SPAWN_PLAYER_AHEAD = 60
SPAWN_PLAYER_SPACING = 36
SPAWN_TRIGGER_OFFSET = 420
SPAWN_TRIGGER_SPACING = 28
SPAWN_WORLD_RIGHT_PADDING = 80
DEFAULT_ENEMY_GROUND_Y = HEIGHT - 136
BREAK_EFFECT_FRAMES = 12
BREAK_EFFECT_BASE_SIZE = 6
BREAK_EFFECT_SIZE_PER_FRAME = 2
ENEMY_SPAWN_LANE_OFFSETS = (-28, 0, 30)
PIPE_WEAPON_HITS = 6
PIPE_WEAPON_DAMAGE_BONUS = 8
PIPE_WEAPON_RANGE_BONUS = 20

# Setup
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('Quad Fighter Prototype')
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

# Game objects
player = Player(140, HEIGHT - 136, WORLD_WIDTH, HEIGHT)
enemies_beaten = 0
last_attack_id = player.attack_id
hit_pause_timer = 0
impact_timer = 0
impact_rect = None
camera_x = 0
spawn_cursor = 0
stage_complete = False
boss_spawned = False
boss_defeated = False

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
    for i in range(count):
        spawn_x = max(
            player_x + WIDTH + SPAWN_PLAYER_AHEAD + i * SPAWN_PLAYER_SPACING,
            trigger_x + SPAWN_TRIGGER_OFFSET + i * SPAWN_TRIGGER_SPACING,
        )
        spawn_x = min(WORLD_WIDTH - SPAWN_WORLD_RIGHT_PADDING, spawn_x)
        enemy = Enemy(spawn_x, DEFAULT_ENEMY_GROUND_Y, WORLD_WIDTH, HEIGHT)
        enemy.ground_y = max(
            LANE_TOP,
            min(
                LANE_BOTTOM - enemy.height + 20,
                DEFAULT_ENEMY_GROUND_Y + ENEMY_SPAWN_LANE_OFFSETS[i % len(ENEMY_SPAWN_LANE_OFFSETS)],
            ),
        )
        enemy.y = enemy.ground_y
        spawned.append(enemy)
    return spawned

# Main loop
running = True
frame_count = 0
screenshot_saved = False
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

        if (
            not boss_spawned
            and spawn_cursor >= len(enemy_spawn_zones)
            and not enemies
            and player.x >= BOSS_TRIGGER_X
        ):
            boss = Enemy(BOSS_SPAWN_X, DEFAULT_ENEMY_GROUND_Y, WORLD_WIDTH, HEIGHT, is_boss=True)
            boss.ground_y = DEFAULT_ENEMY_GROUND_Y - 8
            boss.y = boss.ground_y
            enemies.append(boss)
            boss_spawned = True

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
                player.equip_weapon(
                    "pipe",
                    hits=PIPE_WEAPON_HITS,
                    damage_bonus=PIPE_WEAPON_DAMAGE_BONUS,
                    range_bonus=PIPE_WEAPON_RANGE_BONUS,
                )
                environment_objects.remove(picked_weapon)

        weapon_hit_registered = False
        for enemy in enemies:
            if enemy.health <= 0:
                continue
            if check_attack_collision(player, enemy):
                enemy.health = max(0, enemy.health - player.get_attack_damage())
                apply_knockback(enemy, player, knockback_distance=player.get_attack_knockback())
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
                    break_effects.append({"x": break_center_x, "y": break_center_y, "timer": BREAK_EFFECT_FRAMES})
                    if obj.kind == "barrel":
                        environment_objects.append(
                            EnvironmentObject("pipe", obj.x + 6, HEIGHT - 72, 28, 10)
                        )
                    environment_objects.remove(obj)

        if weapon_hit_registered:
            player.consume_weapon_hit()

        player_rect = player.get_rect()
        for enemy in enemies:
            if enemy.health <= 0:
                continue
            enemy_attack_rect = enemy.get_attack_rect()
            if enemy_attack_rect is None:
                continue
            if enemy.last_hit_player_attack_id == enemy.attack_id:
                continue
            if not enemy_attack_rect.colliderect(player_rect):
                continue
            player.health = max(0, player.health - enemy.attack_damage)
            apply_knockback(player, enemy, knockback_distance=enemy.attack_knockback)
            enemy.last_hit_player_attack_id = enemy.attack_id
            hit_pause_timer = HIT_PAUSE_FRAMES
            impact_timer = IMPACT_FLASH_FRAMES
            impact_rect = player.get_rect().copy()

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
    if boss_spawned and not boss_defeated and not any(enemy.is_boss for enemy in enemies):
        boss_defeated = True

    for effect in list(break_effects):
        effect["timer"] -= 1
        if effect["timer"] <= 0:
            break_effects.remove(effect)

    camera_target = player.x + player.width / 2 - WIDTH * CAMERA_FOLLOW_RATIO
    camera_x = max(0, min(int(camera_target), WORLD_WIDTH - WIDTH))
    if player.x < camera_x + 12:
        player.x = camera_x + 12

    stage_complete = (
        boss_spawned
        and boss_defeated
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
    camera_dash_offset = (-camera_x) % LANE_DASH_SPACING
    for x in range(-LANE_DASH_SPACING + camera_dash_offset, WIDTH + LANE_DASH_SPACING, LANE_DASH_SPACING):
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
        break_effect_size = (
            BREAK_EFFECT_BASE_SIZE + (BREAK_EFFECT_FRAMES - effect["timer"]) * BREAK_EFFECT_SIZE_PER_FRAME
        )
        fx = int(effect["x"] - camera_x)
        fy = int(effect["y"])
        pygame.draw.line(
            screen,
            (210, 210, 210),
            (fx - break_effect_size, fy - break_effect_size),
            (fx + break_effect_size, fy + break_effect_size),
            2,
        )
        pygame.draw.line(
            screen,
            (210, 210, 210),
            (fx - break_effect_size, fy + break_effect_size),
            (fx + break_effect_size, fy - break_effect_size),
            2,
        )

    boss_enemy = next((enemy for enemy in enemies if enemy.is_boss), None)
    regular_enemy_count = len([enemy for enemy in enemies if not enemy.is_boss])
    if boss_enemy is not None:
        enemy_status = "Boss: ENGAGED"
    elif regular_enemy_count > 0:
        enemy_status = f"Enemies Alive: {regular_enemy_count}"
    elif spawn_cursor >= len(enemy_spawn_zones) and not boss_spawned:
        enemy_status = "Boss: AHEAD"
    elif boss_spawned and boss_defeated:
        enemy_status = "Boss: DEFEATED"
    elif spawn_cursor >= len(enemy_spawn_zones):
        enemy_status = "Enemies: CLEARED"
    else:
        enemy_status = "Enemies: WAITING"

    progress_target = BOSS_TRIGGER_X if BOSS_TRIGGER_X > 0 else STAGE_CLEAR_X
    progress_pct = int((player.x / progress_target) * 100) if progress_target > 0 else 100
    progress_pct = max(0, min(progress_pct, 100))
    weapon_text = "Weapon: FISTS"
    if player.weapon_name is not None:
        weapon_text = f"Weapon: {player.weapon_name.upper()} ({player.weapon_hits_remaining})"
    hud_text = f"Player HP: {player.health}   {enemy_status}   Stage: {progress_pct}%   {weapon_text}"
    screen.blit(font.render(hud_text, True, (220, 220, 220)), (16, 16))
    if boss_enemy is not None:
        boss_label = font.render("BOSS", True, (250, 220, 220))
        screen.blit(boss_label, (16, 42))
        boss_ratio = max(0.0, min(1.0, boss_enemy.health / BOSS_MAX_HEALTH))
        bar_rect = pygame.Rect(78, 45, 240, 14)
        pygame.draw.rect(screen, (70, 22, 22), bar_rect)
        pygame.draw.rect(screen, (190, 62, 62), (bar_rect.x, bar_rect.y, int(bar_rect.width * boss_ratio), bar_rect.height))
        pygame.draw.rect(screen, (220, 220, 220), bar_rect, 2)
    if stage_complete:
        clear_text = font.render("BOSS DEFEATED - STAGE COMPLETE", True, (240, 240, 240))
        screen.blit(clear_text, (WIDTH // 2 - clear_text.get_width() // 2, 70))

    pygame.display.flip()
    frame_count += 1
    if (
        QUAD_FIGHTER_SCREENSHOT_PATH is not None
        and QUAD_FIGHTER_AUTO_EXIT_FRAMES > 0
        and frame_count >= QUAD_FIGHTER_AUTO_EXIT_FRAMES
        and not screenshot_saved
    ):
        screenshot_dir = os.path.dirname(QUAD_FIGHTER_SCREENSHOT_PATH)
        if screenshot_dir:
            os.makedirs(screenshot_dir, exist_ok=True)
        pygame.image.save(screen, QUAD_FIGHTER_SCREENSHOT_PATH)
        screenshot_saved = True
    if QUAD_FIGHTER_AUTO_EXIT_FRAMES > 0 and frame_count >= QUAD_FIGHTER_AUTO_EXIT_FRAMES:
        running = False

pygame.quit()
sys.exit()
