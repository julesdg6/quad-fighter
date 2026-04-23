KNOCKBACK_DISTANCE = 20


def check_attack_collision(player, enemy):
    attack_rect = player.get_attack_rect()
    if attack_rect is None:
        return False
    if enemy.last_hit_attack_id == player.attack_id:
        return False
    return attack_rect.colliderect(enemy.get_rect())

def apply_knockback(target, source):
    if source.x > target.x:
        target.x -= KNOCKBACK_DISTANCE
    else:
        target.x += KNOCKBACK_DISTANCE
    target.x = max(0, min(target.x, target.screen_width - target.width))
    target.hit_stun_timer = 10
    target.hurt_flash_timer = 6
    target.last_hit_attack_id = source.attack_id
