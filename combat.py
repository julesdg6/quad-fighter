import pygame

KNOCKBACK_DISTANCE = 30
HIT_STUN_FRAMES = 18
HURT_FLASH_FRAMES = 9
KNOCKDOWN_STUN_FRAMES = 44
KNOCKDOWN_STUN_FRAMES_LEGS = 22

# Per-region tuning: knockback multiplier, vertical impulse, stun duration
HIT_REGION_PARAMS = {
    "head":  {"knockback_mult": 1.5,  "vel_y": -5.5, "stun_frames": 28},
    "torso": {"knockback_mult": 1.0,  "vel_y": -3.0, "stun_frames": HIT_STUN_FRAMES},
    "legs":  {"knockback_mult": 0.55, "vel_y": -1.8, "stun_frames": 22},
}


def get_hit_region(attack_rect, target):
    """Return which body region ('head'/'torso'/'legs') of target was struck."""
    if attack_rect is None:
        return "torso"
    target_rect = target.get_rect()
    h = target_rect.height
    head_zone = pygame.Rect(target_rect.x, target_rect.y,
                            target_rect.width, int(h * 0.30))
    legs_zone = pygame.Rect(target_rect.x, target_rect.y + int(h * 0.65),
                            target_rect.width, int(h * 0.35))
    if attack_rect.colliderect(head_zone):
        return "head"
    if attack_rect.colliderect(legs_zone):
        return "legs"
    return "torso"


def check_attack_collision(player, enemy):
    attack_rect = player.get_attack_rect()
    if attack_rect is None:
        return False
    if enemy.last_hit_attack_id == player.attack_id:
        return False
    return attack_rect.colliderect(enemy.get_rect())


def apply_knockback(target, source, knockback_distance=KNOCKBACK_DISTANCE, hit_region="torso"):
    params = HIT_REGION_PARAMS.get(hit_region, HIT_REGION_PARAMS["torso"])
    actual_knockback = int(knockback_distance * params["knockback_mult"])
    if source.x > target.x:
        target.x -= actual_knockback
    else:
        target.x += actual_knockback
    target.x = max(0, min(target.x, target.screen_width - target.width))
    target.vel_y = min(target.vel_y, params["vel_y"])
    if hit_region != "legs":
        target.y -= 2
    target.on_ground = False
    stun_frames = params["stun_frames"]
    target.hit_stun_timer = max(target.hit_stun_timer, stun_frames)
    target.hurt_flash_timer = max(target.hurt_flash_timer, HURT_FLASH_FRAMES)
    if hasattr(target, "hurt_anim_timer"):
        target.hurt_anim_timer = max(target.hurt_anim_timer, stun_frames)
    target.last_hit_attack_id = source.attack_id
    # Store hit region so animations can vary by location
    if hasattr(target, "hit_region"):
        target.hit_region = hit_region
    # Trigger knockdown on heavy head hits or strong leg sweeps
    if hasattr(target, "knockdown_timer"):
        if hit_region == "head" and knockback_distance >= 70:
            target.knockdown_timer = max(target.knockdown_timer, KNOCKDOWN_STUN_FRAMES)
        elif hit_region == "legs" and knockback_distance >= 60:
            target.knockdown_timer = max(target.knockdown_timer, KNOCKDOWN_STUN_FRAMES_LEGS)
