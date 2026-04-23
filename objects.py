import pygame


class EnvironmentObject:
    def __init__(self, kind, x, y, width, height, health=0, solid=False):
        self.kind = kind
        self.x = float(x)
        self.y = float(y)
        self.width = width
        self.height = height
        self.health = health
        self.solid = solid
        self.last_hit_attack_id = -1

    def get_rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def take_hit(self, attack_id, damage):
        if self.health <= 0 or self.last_hit_attack_id == attack_id:
            return False
        self.health = max(0, self.health - damage)
        self.last_hit_attack_id = attack_id
        return True

    def is_destroyed(self):
        return self.health <= 0

    def draw(self, screen, camera_x):
        draw_rect = self.get_rect().move(-int(camera_x), 0)
        if self.kind == "crate":
            pygame.draw.rect(screen, (122, 102, 86), draw_rect)
            pygame.draw.rect(screen, (78, 62, 52), draw_rect, 2)
            pygame.draw.line(screen, (92, 74, 62), draw_rect.topleft, draw_rect.bottomright, 2)
            pygame.draw.line(screen, (92, 74, 62), draw_rect.topright, draw_rect.bottomleft, 2)
        elif self.kind == "barrel":
            pygame.draw.ellipse(screen, (112, 90, 74), draw_rect)
            pygame.draw.ellipse(screen, (72, 56, 46), draw_rect, 2)
            band_top = draw_rect.y + draw_rect.height // 3
            band_bottom = draw_rect.y + draw_rect.height * 2 // 3
            pygame.draw.line(screen, (64, 50, 42), (draw_rect.x, band_top), (draw_rect.right, band_top), 2)
            pygame.draw.line(screen, (64, 50, 42), (draw_rect.x, band_bottom), (draw_rect.right, band_bottom), 2)
        elif self.kind == "pipe":
            pygame.draw.rect(screen, (150, 150, 156), draw_rect)
            pygame.draw.rect(screen, (92, 92, 98), draw_rect, 1)
            tip = (
                draw_rect.right + 12,
                draw_rect.centery,
            )
            pygame.draw.line(screen, (168, 168, 174), draw_rect.midright, tip, 4)
            pygame.draw.circle(screen, (196, 196, 202), tip, 4)

