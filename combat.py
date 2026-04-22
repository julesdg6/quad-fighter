KNOCKBACK_DISTANCE = 20


def check_attack_collision(player, enemy):
    attack_rect = player.get_attack_rect()
    if attack_rect is None:
        return False
    return attack_rect.colliderect(enemy.get_rect())

def apply_knockback(target, source):
    if source.x > target.x:
        target.x -= KNOCKBACK_DISTANCE
    else:
        target.x += KNOCKBACK_DISTANCE
    target.hit_stun_timer = 8
    target.vel_y = -10
