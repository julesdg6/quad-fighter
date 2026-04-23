KNOCKBACK_DISTANCE = 30
HIT_STUN_FRAMES = 18
HURT_FLASH_FRAMES = 9


def check_attack_collision(player, enemy):
    attack_rect = player.get_attack_rect()
    if attack_rect is None:
        return False
    if enemy.last_hit_attack_id == player.attack_id:
        return False
    return attack_rect.colliderect(enemy.get_rect())

def apply_knockback(target, source, knockback_distance=KNOCKBACK_DISTANCE):
    if source.x > target.x:
        target.x -= knockback_distance
    else:
        target.x += knockback_distance
    target.x = max(0, min(target.x, target.screen_width - target.width))
    if hasattr(target, "vel_y"):
        target.vel_y = min(target.vel_y, -3.0)
        target.y -= 2
    if hasattr(target, "on_ground"):
        target.on_ground = False
    target.hit_stun_timer = max(target.hit_stun_timer, HIT_STUN_FRAMES)
    target.hurt_flash_timer = max(target.hurt_flash_timer, HURT_FLASH_FRAMES)
    if hasattr(target, "hurt_anim_timer"):
        target.hurt_anim_timer = max(target.hurt_anim_timer, HIT_STUN_FRAMES)
    target.last_hit_attack_id = source.attack_id
