import pygame
import math


THROWN_GRAVITY = 0.62
THROWN_FLOOR_BUFFER = 52


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
        # Thrown-object physics state
        self.thrown = False
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.thrower = None  # reference to entity that threw this; skip self-collision

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

    def update(self, screen_height):
        """Advance thrown-object physics. No-op when `thrown` is False."""
        if not self.thrown:
            return
        self.vel_y += THROWN_GRAVITY
        self.x += self.vel_x
        self.y += self.vel_y
        # Hit the ground: break
        if self.y + self.height >= screen_height - THROWN_FLOOR_BUFFER:
            self.thrown = False
            self.vel_x = 0.0
            self.vel_y = 0.0
            self.health = 0  # breaks on impact

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
            tip = (draw_rect.right + 12, draw_rect.centery)
            pygame.draw.line(screen, (168, 168, 174), draw_rect.midright, tip, 4)
            pygame.draw.circle(screen, (196, 196, 202), tip, 4)
        elif self.kind == "bat":
            # Wooden baseball bat lying on the ground: handle left, barrel right
            cx, cy = draw_rect.centerx, draw_rect.centery
            handle_x = draw_rect.x + 4
            barrel_x = draw_rect.right - 4
            # Taper: handle is thin (4px), barrel is wide (10px)
            handle_top = cy - 2
            handle_bot = cy + 2
            barrel_top = cy - 5
            barrel_bot = cy + 5
            pts = [
                (handle_x, handle_top),
                (barrel_x, barrel_top),
                (barrel_x, barrel_bot),
                (handle_x, handle_bot),
            ]
            pygame.draw.polygon(screen, (160, 110, 60), pts)
            pygame.draw.polygon(screen, (110, 72, 38), pts, 1)
            # Knob at handle end
            pygame.draw.circle(screen, (110, 72, 38), (handle_x, cy), 4)
        elif self.kind == "whip":
            # Whip coiled on the ground: a curved line
            cx, cy = draw_rect.centerx, draw_rect.centery
            r = draw_rect.width // 2 - 2
            pts = []
            steps = 16
            for i in range(steps + 1):
                angle = math.pi * i / steps
                px = int(cx + r * math.cos(angle) * (1.0 - 0.35 * i / steps))
                py = int(cy + r * 0.5 * math.sin(angle))
                pts.append((px, py))
            if len(pts) >= 2:
                pygame.draw.lines(screen, (140, 90, 40), False, pts, 3)
                pygame.draw.circle(screen, (200, 140, 70), pts[-1], 3)
        elif self.kind == "chain":
            # Chain laid on the ground: linked oval links
            cy = draw_rect.centery
            link_w, link_h = 10, 6
            spacing = 12
            n_links = max(2, draw_rect.width // spacing)
            start_x = draw_rect.x + (draw_rect.width - (n_links * spacing - 2)) // 2
            for i in range(n_links):
                lx = start_x + i * spacing
                link_rect = pygame.Rect(lx, cy - link_h // 2, link_w, link_h)
                pygame.draw.ellipse(screen, (180, 180, 190), link_rect)
                pygame.draw.ellipse(screen, (110, 110, 120), link_rect, 2)
        elif self.kind == "nunchucks":
            # Two short sticks connected by a small chain in the middle
            cy = draw_rect.centery
            stick_w = max(6, draw_rect.width // 3 - 2)
            stick_h = 8
            mid = draw_rect.centerx
            # Left stick
            l_rect = pygame.Rect(draw_rect.x + 2, cy - stick_h // 2, stick_w, stick_h)
            pygame.draw.rect(screen, (80, 52, 28), l_rect, border_radius=2)
            pygame.draw.rect(screen, (50, 32, 14), l_rect, 1, border_radius=2)
            # Right stick
            r_rect = pygame.Rect(draw_rect.right - stick_w - 2, cy - stick_h // 2, stick_w, stick_h)
            pygame.draw.rect(screen, (80, 52, 28), r_rect, border_radius=2)
            pygame.draw.rect(screen, (50, 32, 14), r_rect, 1, border_radius=2)
            # Connecting cord
            pygame.draw.line(screen, (160, 160, 160), (l_rect.right, cy), (r_rect.x, cy), 2)
        elif self.kind == "food":
            shadow_rect = pygame.Rect(draw_rect.x - 1, draw_rect.bottom - 2, draw_rect.width + 2, 4)
            pygame.draw.ellipse(screen, (42, 42, 42), shadow_rect)
            food_rect = draw_rect.inflate(-4, -2)
            pygame.draw.ellipse(screen, (196, 52, 52), food_rect)
            pygame.draw.ellipse(screen, (126, 26, 26), food_rect, 2)
            pygame.draw.rect(
                screen,
                (92, 186, 88),
                (food_rect.centerx - 1, food_rect.y - 3, 3, 5),
            )
