"""make_icon.py – generate icon.png for Quad Fighter.

Run once to (re)create icon.png:
    python make_icon.py

The icon is drawn entirely with pygame primitives so it is consistent with
the project's "no bitmap sprites" philosophy.  Output is a 256×256 PNG.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import math

SIZE = 256
OUT = os.path.join(os.path.dirname(__file__), "icon.png")


def _draw_fighter(surf: pygame.Surface, cx: int, cy_feet: int, scale: float,
                  body_col, outline_col, fist_col):
    """Draw a simple side-on fighter silhouette using basic primitives."""
    s = scale

    # Helper: scaled int offset from centre
    def pt(dx, dy):
        return (int(cx + dx * s), int(cy_feet + dy * s))

    # --- legs ----------------------------------------------------------
    # left leg
    pygame.draw.line(surf, outline_col, pt(0, -14), pt(-5, 0), max(1, int(4 * s)))
    # right leg
    pygame.draw.line(surf, outline_col, pt(0, -14), pt(5, 0), max(1, int(4 * s)))
    # left leg coloured fill
    pygame.draw.line(surf, body_col, pt(0, -14), pt(-5, 0), max(1, int(2 * s)))
    # right leg coloured fill
    pygame.draw.line(surf, body_col, pt(0, -14), pt(5, 0), max(1, int(2 * s)))

    # --- torso ---------------------------------------------------------
    torso_rect = pygame.Rect(
        int(cx - 6 * s), int(cy_feet - 32 * s),
        int(12 * s), int(18 * s),
    )
    pygame.draw.rect(surf, outline_col, torso_rect, 0, int(2 * s))
    torso_inner = torso_rect.inflate(-int(3 * s), -int(3 * s))
    pygame.draw.rect(surf, body_col, torso_inner, 0, int(2 * s))

    # --- arms ----------------------------------------------------------
    # left arm (pulled back)
    pygame.draw.line(surf, outline_col, pt(-6, -26), pt(-14, -18), max(1, int(4 * s)))
    pygame.draw.line(surf, body_col,    pt(-6, -26), pt(-14, -18), max(1, int(2 * s)))
    # right arm (punching forward)
    pygame.draw.line(surf, outline_col, pt(6, -26), pt(20, -22), max(1, int(4 * s)))
    pygame.draw.line(surf, body_col,    pt(6, -26), pt(20, -22), max(1, int(2 * s)))
    # fist
    pygame.draw.circle(surf, outline_col, pt(20, -22), max(2, int(5 * s)))
    pygame.draw.circle(surf, fist_col,    pt(20, -22), max(1, int(3 * s)))

    # --- head ----------------------------------------------------------
    pygame.draw.circle(surf, outline_col, pt(0, -38), max(3, int(8 * s)))
    pygame.draw.circle(surf, body_col,    pt(0, -38), max(2, int(6 * s)))

    # --- feet ----------------------------------------------------------
    pygame.draw.ellipse(surf, outline_col,
                        pygame.Rect(int(cx - 8 * s), int(cy_feet - int(3 * s)),
                                    int(7 * s), int(4 * s)))
    pygame.draw.ellipse(surf, outline_col,
                        pygame.Rect(int(cx + 2 * s), int(cy_feet - int(3 * s)),
                                    int(7 * s), int(4 * s)))


def _draw_slash(surf, cx, cy, radius, col):
    """Draw a stylised impact slash arc."""
    for angle_deg in range(30, 140, 12):
        a = math.radians(angle_deg)
        inner = radius * 0.6
        x1 = int(cx + inner * math.cos(a))
        y1 = int(cy - inner * math.sin(a))
        x2 = int(cx + radius * math.cos(a))
        y2 = int(cy - radius * math.sin(a))
        pygame.draw.line(surf, col, (x1, y1), (x2, y2), 3)


def main():
    pygame.display.init()
    surf = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)

    # --- background: dark gradient ------------------------------------
    for y in range(SIZE):
        t = y / SIZE
        r = int(18 + t * 10)
        g = int(12 + t * 8)
        b = int(36 + t * 20)
        pygame.draw.line(surf, (r, g, b, 255), (0, y), (SIZE - 1, y))

    # --- floor line ---------------------------------------------------
    floor_y = SIZE - 42
    pygame.draw.line(surf, (80, 60, 120, 200), (0, floor_y), (SIZE, floor_y), 2)

    # --- title text ---------------------------------------------------
    pygame.font.init()
    try:
        font = pygame.font.SysFont("monospace", 18, bold=True)
    except Exception:
        font = pygame.font.Font(None, 22)

    title = font.render("QUAD FIGHTER", True, (220, 180, 40))
    surf.blit(title, (SIZE // 2 - title.get_width() // 2, 10))

    # --- impact slash -------------------------------------------------
    _draw_slash(surf, 162, 148, 44, (200, 64, 255, 220))

    # --- two fighters -------------------------------------------------
    # Player 1 – warm amber/orange
    _draw_fighter(surf, 100, floor_y, 2.4,
                  body_col=(220, 140, 40),
                  outline_col=(240, 200, 80),
                  fist_col=(255, 220, 100))

    # Player 2 / enemy – cool blue/teal, offset right
    _draw_fighter(surf, 164, floor_y, 2.2,
                  body_col=(40, 120, 200),
                  outline_col=(80, 180, 240),
                  fist_col=(120, 200, 255))

    # --- subtle vignette ----------------------------------------------
    vsurf = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    for r in range(SIZE // 2, 0, -1):
        alpha = max(0, int((1 - r / (SIZE / 2)) * 80))
        pygame.draw.circle(vsurf, (0, 0, 0, alpha), (SIZE // 2, SIZE // 2), r)
    surf.blit(vsurf, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

    pygame.image.save(surf, OUT)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
