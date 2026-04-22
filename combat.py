import pygame
def check_attack_collision(player, enemy):
    # Simple rectangle collision check between player attack and enemy hitbox
    attack_rect = pygame.Rect(
        player.x + player.width//2 - 5,
        player.y - 10,
        10, 10
    )
    
    return attack_rect.colliderect(
        pygame.Rect(enemy.x, enemy.y, enemy.width, enemy.height)
    )

def apply_knockback(target, source):
    # Basic knockback logic
    if source.x > target.x:
        target.x += 20
    else:
        target.x -= 20
    
    # Add vertical knockback
    target.vel_y = -10