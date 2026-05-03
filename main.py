import pygame
import sys
import os
import math
from player import Player, GRAB_RANGE, CROUCH_DEFENSE_RATIO, SPECIAL_MOVES
from enemy import Enemy, BOSS_MAX_HEALTH
from combat import check_attack_collision, apply_knockback, get_hit_region
from objects import EnvironmentObject
from background import generate_background, draw_background_pre_lane, draw_background_post_lane, LEVEL_SEED_MULTIPLIER
from music import AcidMachine
from sfx import SfxPlayer
from splash import SplashScreen
from options import OptionsScreen
from settings import Settings
from theme import get_theme, next_theme_name
from moto_level import MotoLevel
from rampage_level import RampageLevel
from gauntlet_level import GauntletLevel
from pang_level import PangLevel
from rolling_ball_level import RollingBallLevel
from rtype_level import RTypeLevel
from level_manager import LevelManager
from version import GAME_VERSION, BUILD_NUMBER, PROTOCOL_VERSION
from net_client import NetClient

# Register all pluggable levels with the engine
LevelManager.register("moto",         MotoLevel)
LevelManager.register("rampage",      RampageLevel)
LevelManager.register("gauntlet",     GauntletLevel)
LevelManager.register("pang",         PangLevel)
LevelManager.register("rolling_ball", RollingBallLevel)
LevelManager.register("rtype",        RTypeLevel)

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
pygame.joystick.init()

# Load persistent settings
settings = Settings()
settings.load()

# Log version on launch
print(f"Quad Fighter  v{GAME_VERSION}  build {BUILD_NUMBER}  protocol {PROTOCOL_VERSION}")

# Network client (non-blocking; connect from the options screen)
net_client = NetClient()

# Detect first connected joystick (Xbox controller or similar)
def _init_joystick():
    if pygame.joystick.get_count() > 0:
        joy = pygame.joystick.Joystick(0)
        joy.init()
        return joy
    return None

def _init_joystick2():
    if pygame.joystick.get_count() > 1:
        joy = pygame.joystick.Joystick(1)
        joy.init()
        return joy
    return None

joystick = _init_joystick()
joystick2 = _init_joystick2()

# Configuration
WIDTH, HEIGHT = 800, 600
WORLD_WIDTH = 3200
FPS = 60
LANE_TOP = int(HEIGHT * 0.5)
LANE_BOTTOM = HEIGHT - 188
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
BOSS_INTRO_FRAMES = 90
BOSS_CAMERA_CENTER_WEIGHT = 0.5
BOSS_CAMERA_FORWARD_OFFSET_RATIO = 0.2
FOOD_HEAL_AMOUNT = 28
MID_SECTION_START_X = 780
QUAD_FIGHTER_AUTO_EXIT_FRAMES = int(os.environ.get("QUAD_FIGHTER_AUTO_EXIT_FRAMES", "0"))
QUAD_FIGHTER_SCREENSHOT_PATH = os.environ.get("QUAD_FIGHTER_SCREENSHOT_PATH")
SPECIAL_FLASH_ALPHA_RATE = 6  # alpha units per remaining-frame tick for the special-move banner
SPAWN_OFFSCREEN_MARGIN = 60  # how far off the right screen edge a right-side enemy spawns
SPAWN_PLAYER_SPACING = 36
SPAWN_TRIGGER_OFFSET = 420
SPAWN_TRIGGER_SPACING = 28
SPAWN_WORLD_RIGHT_PADDING = 80
DEFAULT_ENEMY_GROUND_Y = HEIGHT - 232
PLAYER_SPAWN_X = 140
LEVEL_COMPLETE_ANIM_FRAMES = 150
LEVEL_COMPLETE_AUTO_WALK_SPEED = 1.6
LEVEL_COMPLETE_PULSE_BASE = 220
LEVEL_COMPLETE_PULSE_AMPLITUDE = 35
LEVEL_COMPLETE_PULSE_PERIOD_FRAMES = 240
LEVEL_COMPLETE_PULSE_STEP = 0.25
BREAK_EFFECT_FRAMES = 12
BREAK_EFFECT_BASE_SIZE = 6
BREAK_EFFECT_SIZE_PER_FRAME = 2
ENEMY_SPAWN_LANE_OFFSETS = (-28, 0, 30, -14, 18)
SPAWN_LEFT_OFFSET = 300   # how far to the left of the player a left-side enemy spawns
SPAWN_LEFT_SPACING = 40   # extra spacing between left-side enemies in a group
ENEMY_ATTACK_STAGGER_FRAMES = 22  # per-enemy stagger offset so groups don't all attack at once
CAMERA_LOCK_PADDING = 80           # extra world-pixels beyond current right edge when locking
CAMERA_LOCK_RIGHT_MARGIN = 28      # keep player this far (px) from locked right screen edge
CAMERA_LOCK_BAR_WIDTH = 6          # width of the on-screen indicator drawn on right edge when locked
PIPE_WEAPON_HITS = 6
PIPE_WEAPON_DAMAGE_BONUS = 8
PIPE_WEAPON_RANGE_BONUS = 20
BAT_WEAPON_HITS = 8
BAT_WEAPON_DAMAGE_BONUS = 12
BAT_WEAPON_RANGE_BONUS = 28
WHIP_WEAPON_HITS = 10
WHIP_WEAPON_DAMAGE_BONUS = 6
WHIP_WEAPON_RANGE_BONUS = 52
CHAIN_WEAPON_HITS = 7
CHAIN_WEAPON_DAMAGE_BONUS = 10
CHAIN_WEAPON_RANGE_BONUS = 32
NUNCHUCKS_WEAPON_HITS = 6
NUNCHUCKS_WEAPON_DAMAGE_BONUS = 14
NUNCHUCKS_WEAPON_RANGE_BONUS = 18
# Crate/barrel sizes (bigger than before)
CRATE_W, CRATE_H = 62, 62
BARREL_W, BARREL_H = 54, 74
THROW_VEL_X = 9.0
THROW_VEL_Y = -9.0
THROW_DAMAGE = 32
GRAB_THROW_DAMAGE = 18        # HP lost by enemy on being thrown
GRAB_THROW_KNOCKBACK = 110    # horizontal displacement applied via apply_knockback
GRAB_VERTICAL_TOLERANCE = 20  # y-axis inflation of grab hitbox
# Pickup weapon kinds that can be grabbed from the floor
WEAPON_KINDS = {"pipe", "bat", "whip", "chain", "nunchucks"}
WEAPON_STATS = {
    "pipe":      {"hits": PIPE_WEAPON_HITS,      "damage": PIPE_WEAPON_DAMAGE_BONUS,      "range": PIPE_WEAPON_RANGE_BONUS},
    "bat":       {"hits": BAT_WEAPON_HITS,       "damage": BAT_WEAPON_DAMAGE_BONUS,       "range": BAT_WEAPON_RANGE_BONUS},
    "whip":      {"hits": WHIP_WEAPON_HITS,      "damage": WHIP_WEAPON_DAMAGE_BONUS,      "range": WHIP_WEAPON_RANGE_BONUS},
    "chain":     {"hits": CHAIN_WEAPON_HITS,     "damage": CHAIN_WEAPON_DAMAGE_BONUS,     "range": CHAIN_WEAPON_RANGE_BONUS},
    "nunchucks": {"hits": NUNCHUCKS_WEAPON_HITS, "damage": NUNCHUCKS_WEAPON_DAMAGE_BONUS, "range": NUNCHUCKS_WEAPON_RANGE_BONUS},
}

# Setup
display_flags = pygame.FULLSCREEN if settings.fullscreen else 0
screen = pygame.display.set_mode((WIDTH, HEIGHT), display_flags)
pygame.display.set_caption('Quad Fighter Prototype')
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

# Game objects
player = Player(PLAYER_SPAWN_X, HEIGHT - 232, WORLD_WIDTH, HEIGHT)
player2 = Player(PLAYER_SPAWN_X + 64, HEIGHT - 208, WORLD_WIDTH, HEIGHT)
player2.palette_variant = "player2"

def _apply_appearance(s):
    """Sync player appearance colour indices from *s* (Settings)."""
    player.suit_colour_idx = s.suit_colour_idx
    player.hair_colour_idx = s.hair_colour_idx

_apply_appearance(settings)
enemies_beaten = 0
last_attack_id = player.attack_id
last_attack_id2 = player2.attack_id
hit_pause_timer = 0
impact_timer = 0
impact_rect = None
camera_x = 0
current_theme = get_theme("street")
bg_data = generate_background(WORLD_WIDTH, LANE_TOP, theme=current_theme)
spawn_cursor = 0
stage_complete = False
boss_spawned = False
boss_defeated = False
boss_intro_timer = 0
section_name = None
section_message = ""
section_message_timer = 0
level_number = 1
level_transition_timer = 0
just_advanced_level = False

enemy_spawn_zones = [
    {"trigger_x": 260,  "count": 2, "variants": ["raider", "raider"],                         "lock_camera": True},
    {"trigger_x": 760,  "count": 3, "variants": ["raider", "brawler", "raider"],               "lock_camera": True},
    {"trigger_x": 1280, "count": 2, "variants": ["brawler", "raider"]},
    {"trigger_x": 1800, "count": 4, "variants": ["raider", "brawler", "raider", "brawler"],    "lock_camera": True},
    {"trigger_x": 2360, "count": 3, "variants": ["brawler", "raider", "brawler"],              "lock_camera": True},
]
enemies = []
lock_zone_enemies = []   # enemies from the current locked zone; cleared when all are defeated
camera_lock_right = None  # world-x of the maximum camera right-edge while a zone is locked
enemy_sfx_attack_ids: dict = {}  # id(enemy) → last attack_id when SFX was triggered
special_flash_timer = 0           # frames remaining for on-screen "SPECIAL!" banner
special_flash_name = ""           # name of the last special move triggered
special_flash_timer2 = 0          # same for player 2
special_flash_name2 = ""


def build_environment_objects():
    return [
        EnvironmentObject("bat",       360, HEIGHT - 74, 64, 16),
        EnvironmentObject("crate",     520, HEIGHT - CRATE_H - 34, CRATE_W, CRATE_H, health=40, solid=True),
        EnvironmentObject("barrel",    980, HEIGHT - BARREL_H - 34, BARREL_W, BARREL_H, health=50, solid=True),
        EnvironmentObject("pipe",     1060, HEIGHT - 72, 34, 12),
        EnvironmentObject("whip",     1150, HEIGHT - 74, 60, 18),
        EnvironmentObject("crate",    1540, HEIGHT - CRATE_H - 34, CRATE_W, CRATE_H, health=40, solid=True),
        EnvironmentObject("chain",    1620, HEIGHT - 74, 64, 16),
        EnvironmentObject("food",     1680, HEIGHT - 70, 26, 20),
        EnvironmentObject("nunchucks",1820, HEIGHT - 74, 64, 16),
        EnvironmentObject("barrel",   2120, HEIGHT - BARREL_H - 34, BARREL_W, BARREL_H, health=50, solid=True),
        EnvironmentObject("crate",    2620, HEIGHT - CRATE_H - 34, CRATE_W, CRATE_H, health=40, solid=True),
    ]


environment_objects = build_environment_objects()
break_effects = []

acid = AcidMachine()
acid.set_volume(settings.music_volume / 100.0)
sfx = SfxPlayer()
sfx.set_volume(settings.sfx_volume / 100.0)


def break_object(obj, environment_objects, break_effects):
    """Register a break effect and spawn drops for a destroyed crate or barrel."""
    cx = obj.x + obj.width / 2
    cy = obj.y + obj.height / 2
    break_effects.append({"x": cx, "y": cy, "timer": BREAK_EFFECT_FRAMES})
    if obj.kind == "crate":
        environment_objects.append(EnvironmentObject("food", obj.x + 8, HEIGHT - 70, 26, 20))
    elif obj.kind == "barrel":
        environment_objects.append(EnvironmentObject("pipe", obj.x + 6, HEIGHT - 72, 34, 12))
    if obj in environment_objects:
        environment_objects.remove(obj)


def spawn_enemies(player_x, zone, camera_x=0):
    trigger_x = zone["trigger_x"]
    count = zone["count"]
    variants = zone.get("variants") or ["raider"]
    spawned = []
    right_index = 0
    left_index = 0
    for i in range(count):
        variant_index = min(i, len(variants) - 1)
        # Alternate spawning left/right of the player so enemies surround from both sides.
        # i == 0 → right, i == 1 → left, i == 2 → right, i == 3 → left …
        if i % 2 == 0:
            # Spawn just off the right edge of the current screen view so enemies
            # are visible almost immediately and the player fights a group, not a queue.
            screen_right = camera_x + WIDTH
            spawn_x = screen_right + SPAWN_OFFSCREEN_MARGIN + right_index * SPAWN_PLAYER_SPACING
            spawn_x = max(spawn_x, trigger_x + SPAWN_TRIGGER_OFFSET + right_index * SPAWN_TRIGGER_SPACING)
            spawn_x = min(WORLD_WIDTH - SPAWN_WORLD_RIGHT_PADDING, spawn_x)
            right_index += 1
            approach_side = 1
        else:
            spawn_x = max(0, player_x - SPAWN_LEFT_OFFSET - left_index * SPAWN_LEFT_SPACING)
            left_index += 1
            approach_side = -1
        enemy = Enemy(spawn_x, DEFAULT_ENEMY_GROUND_Y, WORLD_WIDTH, HEIGHT, variant=variants[variant_index])
        enemy.ground_y = max(
            LANE_TOP,
            min(
                LANE_BOTTOM - enemy.height + 20,
                DEFAULT_ENEMY_GROUND_Y + ENEMY_SPAWN_LANE_OFFSETS[i % len(ENEMY_SPAWN_LANE_OFFSETS)],
            ),
        )
        enemy.y = enemy.ground_y
        # Keep each enemy on its natural flank (left or right of player).
        enemy.approach_side = approach_side
        # Stagger attack cooldowns so enemies in a group don't all attack simultaneously.
        enemy.attack_cooldown_timer = i * ENEMY_ATTACK_STAGGER_FRAMES
        spawned.append(enemy)
    return spawned

# Splash / options state machine (skip when running headless CI)
if QUAD_FIGHTER_AUTO_EXIT_FRAMES == 0:
    while True:
        result = SplashScreen(screen, WIDTH, HEIGHT, FPS, joystick=joystick).run()
        if result == "options":
            OptionsScreen(screen, WIDTH, HEIGHT, FPS, settings, joystick=joystick, net_client=net_client).run(acid, sfx)
            acid.set_volume(settings.music_volume / 100.0)
            sfx.set_volume(settings.sfx_volume / 100.0)
            # Sync appearance settings to player objects
            _apply_appearance(settings)
        elif result in LevelManager.available_keys():
            # Load and run any registered level by key
            LevelManager.load(
                result,
                screen, WIDTH, HEIGHT, FPS, settings, font, acid, sfx,
                joystick=joystick, joystick2=joystick2,
            ).run()
            # Loop back to the splash after the level ends
        else:
            break  # "game" – proceed to gameplay

# Start main game at 90 BPM (calm baseline; escalates with enemies/boss)
acid.set_target_bpm(90)

# Determine whether a second local player is active
p2_active = settings.num_players >= 2

# Main loop
running = True
frame_count = 0
screenshot_saved = False
while running:
    dt = clock.tick(FPS) / 1000.0
    # Update target BPM based on live enemies / boss presence (single pass)
    _boss_alive = False
    _live_count = 0
    for _e in enemies:
        if _e.health > 0:
            if _e.is_boss:
                _boss_alive = True
            else:
                _live_count += 1
    if _boss_alive:
        acid.set_target_bpm(174)
    else:
        acid.set_target_bpm(90 + 10 * _live_count)
    acid.tick(dt)
    # Draw background: sky gradient + far/mid buildings
    draw_background_pre_lane(screen, camera_x, bg_data, WIDTH, HEIGHT, LANE_TOP)
    # Fill below-lane foreground floor area
    pygame.draw.rect(screen, current_theme["floor_fg"], (0, LANE_BOTTOM, WIDTH, HEIGHT - LANE_BOTTOM))

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            settings.fullscreen = not settings.fullscreen
            display_flags = pygame.FULLSCREEN if settings.fullscreen else 0
            screen = pygame.display.set_mode((WIDTH, HEIGHT), display_flags)
            settings.save()
        elif event.type == pygame.JOYDEVICEADDED:
            joystick = _init_joystick()
            joystick2 = _init_joystick2()
        elif event.type == pygame.JOYDEVICEREMOVED:
            joystick = _init_joystick()
            joystick2 = _init_joystick2()

    # Update / hit-stop
    if special_flash_timer > 0:
        special_flash_timer -= 1
    if special_flash_timer2 > 0:
        special_flash_timer2 -= 1
    if hit_pause_timer > 0:
        hit_pause_timer -= 1
    else:
        prev_player_x = player.x
        ctrl_input = settings.read_controller(joystick)
        player.update(extra_input=ctrl_input, keyboard_map=settings.keyboard)
        player_rect = player.get_rect()

        if p2_active:
            prev_player2_x = player2.x
            ctrl_input2 = settings.read_controller(joystick2)
            player2.update(extra_input=ctrl_input2, keyboard_map=settings.keyboard_p2)
            player2_rect = player2.get_rect()

        # Grab attempt: P1
        if player.grab_triggered:
            grab_rect = player.get_rect().inflate(GRAB_RANGE * 2, GRAB_VERTICAL_TOLERANCE)
            for enemy in enemies:
                if enemy.health <= 0 or enemy.grabbed or enemy.is_boss:
                    continue
                if grab_rect.colliderect(enemy.get_rect()):
                    player.start_grab(enemy)
                    break

        # Grab attempt: P2
        if p2_active and player2.grab_triggered:
            grab_rect2 = player2.get_rect().inflate(GRAB_RANGE * 2, GRAB_VERTICAL_TOLERANCE)
            for enemy in enemies:
                if enemy.health <= 0 or enemy.grabbed or enemy.is_boss:
                    continue
                if grab_rect2.colliderect(enemy.get_rect()):
                    player2.start_grab(enemy)
                    break

        # Throw: P1
        if player.throw_triggered and player.grabbed_enemy is not None:
            throw_enemy = player.grabbed_enemy
            player.release_grab()
            throw_enemy.health = max(0, throw_enemy.health - GRAB_THROW_DAMAGE)
            throw_enemy.vel_y = -5.5
            throw_enemy.on_ground = False
            throw_enemy.y -= 4
            apply_knockback(
                throw_enemy, player,
                knockback_distance=GRAB_THROW_KNOCKBACK,
                hit_region="head",
            )
            hit_pause_timer = HIT_PAUSE_FRAMES
            impact_timer = IMPACT_FLASH_FRAMES
            impact_rect = throw_enemy.get_rect().copy()
            sfx.play("impact")
            sfx.play("enemy_hurt")

        # Throw: P2
        if p2_active and player2.throw_triggered and player2.grabbed_enemy is not None:
            throw_enemy2 = player2.grabbed_enemy
            player2.release_grab()
            throw_enemy2.health = max(0, throw_enemy2.health - GRAB_THROW_DAMAGE)
            throw_enemy2.vel_y = -5.5
            throw_enemy2.on_ground = False
            throw_enemy2.y -= 4
            apply_knockback(
                throw_enemy2, player2,
                knockback_distance=GRAB_THROW_KNOCKBACK,
                hit_region="head",
            )
            hit_pause_timer = HIT_PAUSE_FRAMES
            impact_timer = IMPACT_FLASH_FRAMES
            impact_rect = throw_enemy2.get_rect().copy()
            sfx.play("impact")
            sfx.play("enemy_hurt")

        # Solid object collision: P1
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

        # Solid object collision: P2
        if p2_active:
            for obj in environment_objects:
                if not obj.solid or obj.health <= 0:
                    continue
                obj_rect = obj.get_rect()
                if not player2_rect.colliderect(obj_rect):
                    continue
                if player2.x > prev_player2_x:
                    player2.x = obj.x - player2.width
                elif player2.x < prev_player2_x:
                    player2.x = obj.x + obj.width
                player2_rect = player2.get_rect()

        while spawn_cursor < len(enemy_spawn_zones) and player.x >= enemy_spawn_zones[spawn_cursor]["trigger_x"]:
            zone = enemy_spawn_zones[spawn_cursor]
            new_enemies = spawn_enemies(player.x, zone, camera_x)
            # Lock the camera for zones that mark a combat encounter
            if zone.get("lock_camera") and camera_lock_right is None:
                lock_zone_enemies = list(new_enemies)
                camera_lock_right = camera_x + WIDTH + CAMERA_LOCK_PADDING
            enemies.extend(new_enemies)
            spawn_cursor += 1

        for enemy in enemies:
            if enemy.health > 0:
                prev_sfx_attack_id = enemy_sfx_attack_ids.get(id(enemy), enemy.attack_id)
                if boss_intro_timer > 0 and enemy.is_boss:
                    # Face the nearest alive player during boss intro
                    if p2_active and player.health > 0 and player2.health > 0:
                        nearest = player if abs(player.x - enemy.x) <= abs(player2.x - enemy.x) else player2
                    elif p2_active and player2.health > 0:
                        nearest = player2
                    else:
                        nearest = player
                    enemy.facing = -1 if nearest.x < enemy.x else 1
                else:
                    # Target the nearest alive player
                    if p2_active and player.health > 0 and player2.health > 0:
                        d1 = abs((player.x + player.width / 2) - (enemy.x + enemy.width / 2))
                        d2 = abs((player2.x + player2.width / 2) - (enemy.x + enemy.width / 2))
                        target_p = player if d1 <= d2 else player2
                    elif p2_active and player2.health > 0:
                        target_p = player2
                    else:
                        target_p = player
                    enemy.update(target_p, enemies)
                if enemy.attack_id != prev_sfx_attack_id:
                    sfx.play("boss_attack" if enemy.is_boss else "enemy_attack")
                enemy_sfx_attack_ids[id(enemy)] = enemy.attack_id

        if (
            not boss_spawned
            and spawn_cursor >= len(enemy_spawn_zones)
            and (
                not any(enemy.health > 0 and not enemy.is_boss for enemy in enemies)
                or player.x >= STAGE_CLEAR_X - 120
            )
            and player.x >= BOSS_TRIGGER_X
        ):
            boss = Enemy(BOSS_SPAWN_X, DEFAULT_ENEMY_GROUND_Y, WORLD_WIDTH, HEIGHT, is_boss=True)
            boss.ground_y = DEFAULT_ENEMY_GROUND_Y - 8
            boss.y = boss.ground_y
            enemies.append(boss)
            boss_spawned = True
            boss_intro_timer = BOSS_INTRO_FRAMES
            section_name = "boss"
            section_message = "BOSS ENCOUNTER"
            section_message_timer = 90

        # ── Attack SFX + weapon pickup: P1 ───────────────────────────────────
        attack_started = player.attack_id != last_attack_id
        if attack_started:
            last_attack_id = player.attack_id
            attack_type = player.current_attack_type
            if attack_type in ("aerial_light", "aerial_heavy"):
                sfx.play("aerial")
            elif attack_type in ("secondary", "crouch_kick"):
                sfx.play("kick")
            elif attack_type in ("spin_attack", "dash_punch", "dive_kick"):
                sfx.play("special")
                special_flash_timer = 50
                special_flash_name = {
                    "spin_attack": "SPIN ATTACK",
                    "dash_punch":  "DASH PUNCH",
                    "dive_kick":   "DIVE KICK",
                }.get(attack_type, "SPECIAL")
            else:
                sfx.play("punch")
            if player.weapon_name is None and player.held_object is None:
                pickup_rect = player.get_rect().inflate(68, 20)
                picked_weapon = None
                for obj in environment_objects:
                    if obj.kind not in WEAPON_KINDS:
                        continue
                    if pickup_rect.colliderect(obj.get_rect()):
                        picked_weapon = obj
                        break
                if picked_weapon is not None:
                    stats = WEAPON_STATS[picked_weapon.kind]
                    player.equip_weapon(
                        picked_weapon.kind,
                        hits=stats["hits"],
                        damage_bonus=stats["damage"],
                        range_bonus=stats["range"],
                    )
                    environment_objects.remove(picked_weapon)

        # ── Attack SFX + weapon pickup: P2 ───────────────────────────────────
        if p2_active:
            attack_started2 = player2.attack_id != last_attack_id2
            if attack_started2:
                last_attack_id2 = player2.attack_id
                attack_type2 = player2.current_attack_type
                if attack_type2 in ("aerial_light", "aerial_heavy"):
                    sfx.play("aerial")
                elif attack_type2 in ("secondary", "crouch_kick"):
                    sfx.play("kick")
                elif attack_type2 in ("spin_attack", "dash_punch", "dive_kick"):
                    sfx.play("special")
                    special_flash_timer2 = 50
                    special_flash_name2 = {
                        "spin_attack": "SPIN ATTACK",
                        "dash_punch":  "DASH PUNCH",
                        "dive_kick":   "DIVE KICK",
                    }.get(attack_type2, "SPECIAL")
                else:
                    sfx.play("punch")
                if player2.weapon_name is None and player2.held_object is None:
                    pickup_rect2 = player2.get_rect().inflate(68, 20)
                    picked_weapon2 = None
                    for obj in environment_objects:
                        if obj.kind not in WEAPON_KINDS:
                            continue
                        if pickup_rect2.colliderect(obj.get_rect()):
                            picked_weapon2 = obj
                            break
                    if picked_weapon2 is not None:
                        stats2 = WEAPON_STATS[picked_weapon2.kind]
                        player2.equip_weapon(
                            picked_weapon2.kind,
                            hits=stats2["hits"],
                            damage_bonus=stats2["damage"],
                            range_bonus=stats2["range"],
                        )
                        environment_objects.remove(picked_weapon2)

        # Thrown object physics + enemy/ground collision
        for obj in list(environment_objects):
            if not obj.thrown:
                continue
            obj.update(HEIGHT)
            if obj.is_destroyed():
                # Hit ground
                break_object(obj, environment_objects, break_effects)
                sfx.play("break")
                continue
            obj_rect = obj.get_rect()
            for enemy in enemies:
                if enemy.health <= 0:
                    continue
                if not obj_rect.colliderect(enemy.get_rect()):
                    continue
                enemy.health = max(0, enemy.health - THROW_DAMAGE)
                thrower = obj.thrower if obj.thrower is not None else player
                apply_knockback(enemy, thrower, knockback_distance=96)
                hit_pause_timer = HIT_PAUSE_FRAMES
                impact_timer = IMPACT_FLASH_FRAMES
                impact_rect = enemy.get_rect().copy()
                # Break the thrown object on enemy contact
                break_object(obj, environment_objects, break_effects)
                sfx.play("impact")
                sfx.play("enemy_hurt")
                break

        # ── Player attacks on enemies: P1 ─────────────────────────────────────
        weapon_hit_registered = False
        for enemy in enemies:
            if enemy.health <= 0:
                continue
            if check_attack_collision(player, enemy):
                enemy.health = max(0, enemy.health - player.get_attack_damage())
                region = get_hit_region(player.get_attack_rect(), enemy)
                apply_knockback(enemy, player, knockback_distance=player.get_attack_knockback(), hit_region=region)
                hit_pause_timer = HIT_PAUSE_FRAMES
                impact_timer = IMPACT_FLASH_FRAMES
                impact_rect = enemy.get_rect().copy()
                sfx.play("impact")
                sfx.play("enemy_hurt")
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
                    break_object(obj, environment_objects, break_effects)
                    sfx.play("break")

        if weapon_hit_registered:
            player.consume_weapon_hit()

        # ── Player attacks on enemies: P2 ─────────────────────────────────────
        if p2_active:
            weapon_hit_registered2 = False
            for enemy in enemies:
                if enemy.health <= 0:
                    continue
                if check_attack_collision(player2, enemy):
                    enemy.health = max(0, enemy.health - player2.get_attack_damage())
                    region2 = get_hit_region(player2.get_attack_rect(), enemy)
                    apply_knockback(enemy, player2, knockback_distance=player2.get_attack_knockback(), hit_region=region2)
                    hit_pause_timer = HIT_PAUSE_FRAMES
                    impact_timer = IMPACT_FLASH_FRAMES
                    impact_rect = enemy.get_rect().copy()
                    sfx.play("impact")
                    sfx.play("enemy_hurt")
                    weapon_hit_registered2 = True

            attack_rect2 = player2.get_attack_rect()
            if attack_rect2 is not None:
                for obj in list(environment_objects):
                    if obj.health <= 0:
                        continue
                    if not attack_rect2.colliderect(obj.get_rect()):
                        continue
                    if not obj.take_hit(player2.attack_id, player2.get_attack_damage()):
                        continue
                    weapon_hit_registered2 = True
                    hit_pause_timer = HIT_PAUSE_FRAMES
                    impact_timer = IMPACT_FLASH_FRAMES
                    impact_rect = obj.get_rect().copy()
                    if obj.is_destroyed():
                        break_object(obj, environment_objects, break_effects)
                        sfx.play("break")

            if weapon_hit_registered2:
                player2.consume_weapon_hit()

        # ── Food pickup ────────────────────────────────────────────────────────
        player_rect = player.get_rect()
        for obj in list(environment_objects):
            if obj.kind != "food":
                continue
            if not player_rect.colliderect(obj.get_rect()):
                continue
            player.health = min(player.max_health, player.health + FOOD_HEAL_AMOUNT)
            environment_objects.remove(obj)
        if p2_active:
            player2_rect = player2.get_rect()
            for obj in list(environment_objects):
                if obj.kind != "food":
                    continue
                if not player2_rect.colliderect(obj.get_rect()):
                    continue
                player2.health = min(player2.max_health, player2.health + FOOD_HEAL_AMOUNT)
                environment_objects.remove(obj)

        # ── Enemy attacks on players ───────────────────────────────────────────
        player_rect = player.get_rect()
        player2_rect = player2.get_rect() if p2_active else None
        for enemy in enemies:
            if enemy.health <= 0:
                continue
            enemy_attack_rect = enemy.get_attack_rect()
            if enemy_attack_rect is None:
                continue
            # Check P1 first
            if enemy.last_hit_player_attack_id != enemy.attack_id:
                if enemy_attack_rect.colliderect(player_rect):
                    if player.invincible_timer > 0:
                        enemy.last_hit_player_attack_id = enemy.attack_id
                    else:
                        damage = enemy.attack_damage
                        if player.crouching:
                            damage = max(1, int(damage * CROUCH_DEFENSE_RATIO))
                        player.health = max(0, player.health - damage)
                        region = get_hit_region(enemy_attack_rect, player)
                        apply_knockback(player, enemy, knockback_distance=enemy.attack_knockback, hit_region=region)
                        enemy.last_hit_player_attack_id = enemy.attack_id
                        hit_pause_timer = HIT_PAUSE_FRAMES
                        impact_timer = IMPACT_FLASH_FRAMES
                        impact_rect = player.get_rect().copy()
                        sfx.play("impact")
                        sfx.play("player_hurt")
            # Check P2 (if enemy hasn't already landed a hit this swing)
            if p2_active and player2_rect is not None and enemy.last_hit_player_attack_id != enemy.attack_id:
                if enemy_attack_rect.colliderect(player2_rect):
                    if player2.invincible_timer > 0:
                        enemy.last_hit_player_attack_id = enemy.attack_id
                    else:
                        damage2 = enemy.attack_damage
                        if player2.crouching:
                            damage2 = max(1, int(damage2 * CROUCH_DEFENSE_RATIO))
                        player2.health = max(0, player2.health - damage2)
                        region2 = get_hit_region(enemy_attack_rect, player2)
                        apply_knockback(player2, enemy, knockback_distance=enemy.attack_knockback, hit_region=region2)
                        enemy.last_hit_player_attack_id = enemy.attack_id
                        hit_pause_timer = HIT_PAUSE_FRAMES
                        impact_timer = IMPACT_FLASH_FRAMES
                        impact_rect = player2.get_rect().copy()
                        sfx.play("impact")
                        sfx.play("player_hurt")

    if impact_timer > 0:
        impact_timer -= 1

    remaining_enemies = []
    for enemy in enemies:
        if enemy.health <= 0:
            if not enemy.defeat_handled:
                enemy.defeat_handled = True
                enemies_beaten += 1
            # Remove stale SFX tracking entry for this enemy
            enemy_sfx_attack_ids.pop(id(enemy), None)
        else:
            remaining_enemies.append(enemy)
    enemies = remaining_enemies
    if boss_spawned and not boss_defeated and not any(enemy.is_boss for enemy in enemies):
        boss_defeated = True

    # Unlock the camera once all enemies from the locked zone are defeated
    if camera_lock_right is not None and lock_zone_enemies:
        if not any(e in lock_zone_enemies for e in enemies):
            camera_lock_right = None
            lock_zone_enemies = []

    for effect in list(break_effects):
        effect["timer"] -= 1
        if effect["timer"] <= 0:
            break_effects.remove(effect)

    boss_enemy = next((enemy for enemy in enemies if enemy.is_boss), None)
    if boss_enemy is not None:
        # In boss fight, center on the midpoint of all players and the boss
        if p2_active:
            players_mid_x = (player.x + player.width / 2 + player2.x + player2.width / 2) / 2
        else:
            players_mid_x = player.x + player.width / 2
        focus_x = (
            (players_mid_x + boss_enemy.x) * BOSS_CAMERA_CENTER_WEIGHT
            + boss_enemy.width * BOSS_CAMERA_FORWARD_OFFSET_RATIO
        )
        camera_target = focus_x - WIDTH * 0.5
    else:
        # Follow the player (or average both players if P2 is active)
        if p2_active:
            mid_x = (player.x + player.width / 2 + player2.x + player2.width / 2) / 2
        else:
            mid_x = player.x + player.width / 2
        camera_target = mid_x - WIDTH * CAMERA_FOLLOW_RATIO
    max_camera_x = (camera_lock_right - WIDTH) if camera_lock_right is not None else (WORLD_WIDTH - WIDTH)
    camera_x = max(0, min(int(camera_target), max_camera_x))
    if player.x < camera_x + 12:
        player.x = camera_x + 12
    if camera_lock_right is not None:
        player.x = min(player.x, camera_lock_right - player.width - CAMERA_LOCK_RIGHT_MARGIN)
    if p2_active:
        if player2.x < camera_x + 12:
            player2.x = camera_x + 12
        if camera_lock_right is not None:
            player2.x = min(player2.x, camera_lock_right - player2.width - CAMERA_LOCK_RIGHT_MARGIN)

    stage_complete = (
        boss_spawned
        and boss_defeated
        and player.x >= STAGE_CLEAR_X
    )
    if stage_complete and level_transition_timer <= 0:
        level_transition_timer = LEVEL_COMPLETE_ANIM_FRAMES
        section_message = "LEVEL CLEAR"
        section_message_timer = LEVEL_COMPLETE_ANIM_FRAMES
    if level_transition_timer > 0:
        level_transition_timer -= 1
        player.x = min(WORLD_WIDTH - player.width, player.x + LEVEL_COMPLETE_AUTO_WALK_SPEED)
        if p2_active:
            player2.x = min(WORLD_WIDTH - player2.width, player2.x + LEVEL_COMPLETE_AUTO_WALK_SPEED)
        just_advanced_level = False
        if level_transition_timer == 0:
            level_number += 1
            current_theme = get_theme(next_theme_name(current_theme["name"]))
            bg_data = generate_background(WORLD_WIDTH, LANE_TOP, seed=level_number * LEVEL_SEED_MULTIPLIER + 5, theme=current_theme)
            player.x = PLAYER_SPAWN_X
            player.ground_y = player.screen_height - player.height - 40
            player.y = player.ground_y
            player.vel_x = 0.0
            player.vel_y = 0.0
            player.attack_timer = 0
            player.post_attack_timer = 0
            player.attack_cooldown_timer = 0
            player.health = min(player.max_health, player.health + 20)
            player.weapon_name = None
            player.weapon_hits_remaining = 0
            player.weapon_damage_bonus = 0
            player.weapon_range_bonus = 0
            player.held_object = None
            player.grab_timer = 0
            player.grab_cooldown_timer = 0
            player.grabbed_enemy = None
            player.grab_triggered = False
            player.throw_triggered = False
            player.combo_step = 0
            player.combo_window_timer = 0
            if p2_active:
                player2.x = PLAYER_SPAWN_X + 64
                player2.ground_y = player2.screen_height - player2.height - 16
                player2.y = player2.ground_y
                player2.vel_x = 0.0
                player2.vel_y = 0.0
                player2.attack_timer = 0
                player2.post_attack_timer = 0
                player2.attack_cooldown_timer = 0
                player2.health = min(player2.max_health, player2.health + 20)
                player2.weapon_name = None
                player2.weapon_hits_remaining = 0
                player2.weapon_damage_bonus = 0
                player2.weapon_range_bonus = 0
                player2.held_object = None
                player2.grab_timer = 0
                player2.grab_cooldown_timer = 0
                player2.grabbed_enemy = None
                player2.grab_triggered = False
                player2.throw_triggered = False
                player2.combo_step = 0
                player2.combo_window_timer = 0
            enemies.clear()
            environment_objects.clear()
            environment_objects.extend(build_environment_objects())
            break_effects.clear()
            spawn_cursor = 0
            stage_complete = False
            boss_spawned = False
            boss_defeated = False
            boss_intro_timer = 0
            lock_zone_enemies = []
            camera_lock_right = None
            section_name = f"level_{level_number}_start"
            section_message = f"LEVEL {level_number}"
            section_message_timer = 120
            just_advanced_level = True
    if boss_intro_timer > 0:
        boss_intro_timer -= 1
    if section_message_timer > 0:
        section_message_timer -= 1

    if level_transition_timer <= 0 and not just_advanced_level:
        if not boss_spawned:
            if player.x < MID_SECTION_START_X:
                next_section = "opening"
                next_message = "OPENING - PUSH FORWARD"
            else:
                next_section = "mid"
                next_message = "MID STAGE - CLEAR THE STREET"
        elif boss_defeated:
            next_section = "exit"
            next_message = "BOSS DOWN - REACH THE EXIT"
        else:
            next_section = "boss"
            next_message = "FINAL AREA - DEFEAT THE BOSS"
        if next_section != section_name:
            section_name = next_section
            section_message = next_message
            section_message_timer = 120
    elif just_advanced_level and section_message_timer <= 0:
        just_advanced_level = False

    # Draw
    lane_height = LANE_BOTTOM - LANE_TOP
    lane_bands   = current_theme["lane_bands"]
    lane_guides  = current_theme["lane_guides"]
    for i in range(LANE_BAND_COUNT):
        band_top = LANE_TOP + int(i * lane_height / LANE_BAND_COUNT)
        band_bottom = LANE_TOP + int((i + 1) * lane_height / LANE_BAND_COUNT)
        pygame.draw.rect(screen, lane_bands[i], (0, band_top, WIDTH, band_bottom - band_top))
        if i > 0:
            pygame.draw.line(screen, lane_guides[i - 1], (0, band_top), (WIDTH, band_top), 1)
    pygame.draw.line(screen, current_theme["lane_top_line"], (0, LANE_TOP), (WIDTH, LANE_TOP), 2)
    pygame.draw.line(screen, current_theme["lane_bot_line"], (0, LANE_BOTTOM), (WIDTH, LANE_BOTTOM), 2)
    center_lane_y = LANE_TOP + int(lane_height * LANE_GUIDE_RATIO)
    camera_dash_offset = (-camera_x) % LANE_DASH_SPACING
    for x in range(-LANE_DASH_SPACING + camera_dash_offset, WIDTH + LANE_DASH_SPACING, LANE_DASH_SPACING):
        pygame.draw.line(
            screen,
            current_theme["lane_dash"],
            (x, center_lane_y),
            (x + LANE_DASH_LENGTH, center_lane_y),
            1,
        )

    drawables = []
    # Draw near-layer background (lamps, vehicles, background characters)
    draw_background_post_lane(screen, camera_x, frame_count, bg_data, WIDTH, HEIGHT, LANE_TOP, LANE_BOTTOM)
    drawables.append(("player", player.ground_y, player))
    if p2_active:
        drawables.append(("player", player2.ground_y, player2))
    for enemy in enemies:
        drawables.append(("enemy", enemy.ground_y, enemy))
    for obj in environment_objects:
        drawables.append(("object", obj.y + obj.height, obj))
    drawables.sort(key=lambda item: item[1])

    for kind, _, entity in drawables:
        if kind == "player":
            entity.draw(screen, camera_x=camera_x, theme=current_theme)
        elif kind == "enemy":
            entity.draw(screen, camera_x=camera_x, theme=current_theme)
        else:
            entity.draw(screen, camera_x=camera_x)

    if impact_timer > 0 and impact_rect is not None:
        flash_rect = impact_rect.inflate(IMPACT_FLASH_INFLATE_X, IMPACT_FLASH_INFLATE_Y).move(-camera_x, 0)
        flash_base = current_theme["impact_flash"]
        pulse_color = flash_base if impact_timer % 2 == 0 else tuple(max(0, c - 30) for c in flash_base)
        pygame.draw.rect(screen, pulse_color, flash_rect, 2)

    # Grab indicator: outline around enemy grabbed by P1
    if player.is_grabbing() and player.grabbed_enemy is not None:
        ge = player.grabbed_enemy
        grab_draw_rect = ge.get_rect().move(-camera_x, 0).inflate(6, 6)
        pygame.draw.rect(screen, current_theme["grab_outline"], grab_draw_rect, 2)

    # Grab indicator: outline around enemy grabbed by P2
    if p2_active and player2.is_grabbing() and player2.grabbed_enemy is not None:
        ge2 = player2.grabbed_enemy
        grab_draw_rect2 = ge2.get_rect().move(-camera_x, 0).inflate(6, 6)
        pygame.draw.rect(screen, current_theme["grab_outline"], grab_draw_rect2, 2)

    for effect in break_effects:
        break_effect_size = (
            BREAK_EFFECT_BASE_SIZE + (BREAK_EFFECT_FRAMES - effect["timer"]) * BREAK_EFFECT_SIZE_PER_FRAME
        )
        fx = int(effect["x"] - camera_x)
        fy = int(effect["y"])
        pygame.draw.line(
            screen,
            current_theme["break_effect"],
            (fx - break_effect_size, fy - break_effect_size),
            (fx + break_effect_size, fy + break_effect_size),
            2,
        )
        pygame.draw.line(
            screen,
            current_theme["break_effect"],
            (fx - break_effect_size, fy + break_effect_size),
            (fx + break_effect_size, fy - break_effect_size),
            2,
        )

    # Camera-lock boundary indicator on the right screen edge
    if camera_lock_right is not None:
        lock_screen_x = camera_lock_right - camera_x - CAMERA_LOCK_BAR_WIDTH
        if 0 <= lock_screen_x < WIDTH:
            pygame.draw.rect(
                screen,
                current_theme["camera_lock_bar"],
                (lock_screen_x, LANE_TOP, CAMERA_LOCK_BAR_WIDTH, LANE_BOTTOM - LANE_TOP),
            )

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
    hud_text = f"Lvl: {level_number}   {enemy_status}   Stage: {progress_pct}%"
    screen.blit(font.render(hud_text, True, current_theme["hud_text"]), (16, 16))

    # Grab status prompt (P1 or P2)
    if player.is_grabbing():
        grab_prompt = font.render("P1 GRAB - PUNCH TO THROW", True, current_theme["hud_grab"])
        screen.blit(grab_prompt, (WIDTH // 2 - grab_prompt.get_width() // 2, HEIGHT - 42))
    elif p2_active and player2.is_grabbing():
        grab_prompt2 = font.render("P2 GRAB - PUNCH TO THROW", True, current_theme["hud_grab"])
        screen.blit(grab_prompt2, (WIDTH // 2 - grab_prompt2.get_width() // 2, HEIGHT - 42))

    # ── P1 health bar (left side) ─────────────────────────────────────────────
    hp_ratio = max(0.0, min(1.0, player.health / player.max_health))
    if hp_ratio > 0.6:
        hp_color = current_theme["hud_hp_good"]
    elif hp_ratio > 0.3:
        hp_color = current_theme["hud_hp_mid"]
    else:
        hp_color = current_theme["hud_hp_low"]
    hp_label = font.render("P1", True, current_theme["hud_text"])
    screen.blit(hp_label, (16, 36))
    hp_bar_rect = pygame.Rect(46, 39, 140, 12)
    pygame.draw.rect(screen, current_theme["hud_bar_bg"], hp_bar_rect)
    pygame.draw.rect(screen, hp_color, (hp_bar_rect.x, hp_bar_rect.y, int(hp_bar_rect.width * hp_ratio), hp_bar_rect.height))
    pygame.draw.rect(screen, current_theme["hud_bar_outline"], hp_bar_rect, 1)
    if player.weapon_name is not None:
        p1_weapon_surf = font.render(player.weapon_name.upper(), True, current_theme["hud_text"])
        screen.blit(p1_weapon_surf, (16, 55))

    # ── P2 health bar (right side) ────────────────────────────────────────────
    if p2_active:
        hp2_ratio = max(0.0, min(1.0, player2.health / player2.max_health))
        if hp2_ratio > 0.6:
            hp2_color = current_theme["hud_hp_good"]
        elif hp2_ratio > 0.3:
            hp2_color = current_theme["hud_hp_mid"]
        else:
            hp2_color = current_theme["hud_hp_low"]
        hp2_bar_rect = pygame.Rect(WIDTH - 186, 39, 140, 12)
        pygame.draw.rect(screen, current_theme["hud_bar_bg"], hp2_bar_rect)
        pygame.draw.rect(screen, hp2_color, (hp2_bar_rect.x, hp2_bar_rect.y, int(hp2_bar_rect.width * hp2_ratio), hp2_bar_rect.height))
        pygame.draw.rect(screen, current_theme["hud_bar_outline"], hp2_bar_rect, 1)
        hp2_label = font.render("P2", True, current_theme["hud_text"])
        screen.blit(hp2_label, (WIDTH - 40, 36))
        if player2.weapon_name is not None:
            p2_weapon_surf = font.render(player2.weapon_name.upper(), True, current_theme["hud_text"])
            screen.blit(p2_weapon_surf, (WIDTH - 186, 55))

    if boss_enemy is not None:
        boss_label = font.render("BOSS", True, current_theme["hud_text"])
        screen.blit(boss_label, (16, 57))
        boss_ratio = max(0.0, min(1.0, boss_enemy.health / BOSS_MAX_HEALTH))
        bar_rect = pygame.Rect(78, 60, 240, 14)
        pygame.draw.rect(screen, current_theme["hud_boss_bg"], bar_rect)
        pygame.draw.rect(screen, current_theme["hud_boss_bar"], (bar_rect.x, bar_rect.y, int(bar_rect.width * boss_ratio), bar_rect.height))
        pygame.draw.rect(screen, current_theme["hud_bar_outline"], bar_rect, 2)
    if section_message_timer > 0:
        section_text = font.render(section_message, True, current_theme["hud_section"])
        screen.blit(section_text, (WIDTH // 2 - section_text.get_width() // 2, 82))

    # Combo chain counter (P1)
    if player.combo_step > 0:
        combo_surf = font.render(f"COMBO  x{player.combo_step}", True, current_theme["hud_combo"])
        screen.blit(combo_surf, (WIDTH // 2 - combo_surf.get_width() // 2, 108))

    # Special move banner: fades out over ~50 frames (P1)
    if special_flash_timer > 0:
        alpha = min(255, special_flash_timer * SPECIAL_FLASH_ALPHA_RATE)
        special_surf = font.render(f"★  {special_flash_name}  ★", True, (200, 64, 255))
        special_surf.set_alpha(alpha)
        screen.blit(special_surf, (WIDTH // 2 - special_surf.get_width() // 2, 130))

    # Special move banner: P2
    if p2_active and special_flash_timer2 > 0:
        alpha2 = min(255, special_flash_timer2 * SPECIAL_FLASH_ALPHA_RATE)
        special_surf2 = font.render(f"★  {special_flash_name2}  ★", True, (64, 200, 255))
        special_surf2.set_alpha(alpha2)
        screen.blit(special_surf2, (WIDTH // 2 - special_surf2.get_width() // 2, 152))
    if stage_complete or level_transition_timer > 0:
        pulse_base = current_theme["hud_level_pulse"]
        pulse_amount = int(
            LEVEL_COMPLETE_PULSE_AMPLITUDE
            * abs(math.sin((frame_count % LEVEL_COMPLETE_PULSE_PERIOD_FRAMES) * LEVEL_COMPLETE_PULSE_STEP))
        )
        pulse_color = tuple(min(255, c + pulse_amount) for c in pulse_base)
        clear_text = font.render("LEVEL COMPLETE", True, pulse_color)
        screen.blit(clear_text, (WIDTH // 2 - clear_text.get_width() // 2, 112))
        if level_transition_timer > 0:
            seconds_remaining = max(1, (level_transition_timer + FPS - 1) // FPS)
            next_level_text = font.render(
                f"NEXT LEVEL IN {seconds_remaining}",
                True,
                current_theme["hud_text"],
            )
            screen.blit(next_level_text, (WIDTH // 2 - next_level_text.get_width() // 2, 138))

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
