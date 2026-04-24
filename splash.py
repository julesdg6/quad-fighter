import pygame
import math

# Splash screen timing
SPLASH_DURATION_FRAMES = 180   # 3 s at 60 FPS
SCALE_IN_FRAMES = 40           # logo scale-in animation length
PROMPT_BLINK_PERIOD = 60       # "press any key" blink cycle in frames

# Colours
BG_TOP = (6, 6, 20)
BG_BOTTOM = (18, 12, 36)
LOGO_COLOUR = (230, 220, 255)
OUTLINE_COLOUR = (60, 0, 100)
GLOW_COLOUR = (140, 80, 220)
PROMPT_COLOUR = (200, 200, 220)
SUBTITLE_COLOUR = (120, 100, 150)


def _draw_background(screen, width, height):
    """Dark vertical gradient background."""
    for y in range(height):
        t = y / height
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        pygame.draw.line(screen, (r, g, b), (0, y), (width, y))


def _blit_centred(screen, surf, cx, cy):
    screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))


def _draw_logo(screen, width, height, frame, font_logo, font_tagline):
    """Render the QUAD FIGHTER logo with outline + glow, animated scale-in."""
    scale = min(1.0, frame / SCALE_IN_FRAMES) if SCALE_IN_FRAMES > 0 else 1.0
    # Ease-out: apply a square-root curve so it feels snappy
    scale = math.sqrt(scale)

    cx = width // 2
    logo_cy = int(height * 0.40)

    # --- Glow layer (slightly enlarged, semi-transparent purple) ---
    glow_surf = font_logo.render("QUAD FIGHTER", True, GLOW_COLOUR)
    glow_w = int(glow_surf.get_width() * scale * 1.04)
    glow_h = int(glow_surf.get_height() * scale * 1.04)
    if glow_w > 0 and glow_h > 0:
        glow_surf = pygame.transform.smoothscale(glow_surf, (glow_w, glow_h))
        glow_surf.set_alpha(90)
        _blit_centred(screen, glow_surf, cx, logo_cy)

    # --- Outline layer (dark colour, offset in 8 directions) ---
    outline_surf = font_logo.render("QUAD FIGHTER", True, OUTLINE_COLOUR)
    out_w = int(outline_surf.get_width() * scale)
    out_h = int(outline_surf.get_height() * scale)
    if out_w > 0 and out_h > 0:
        outline_surf = pygame.transform.smoothscale(outline_surf, (out_w, out_h))
        for dx, dy in ((-3, -3), (3, -3), (-3, 3), (3, 3),
                       (0, -3), (0, 3), (-3, 0), (3, 0)):
            screen.blit(
                outline_surf,
                (cx - out_w // 2 + dx, logo_cy - out_h // 2 + dy),
            )

    # --- Main text layer ---
    logo_surf = font_logo.render("QUAD FIGHTER", True, LOGO_COLOUR)
    logo_w = int(logo_surf.get_width() * scale)
    logo_h = int(logo_surf.get_height() * scale)
    if logo_w > 0 and logo_h > 0:
        logo_surf = pygame.transform.smoothscale(logo_surf, (logo_w, logo_h))
        _blit_centred(screen, logo_surf, cx, logo_cy)

    # --- Tagline under logo ---
    tag_surf = font_tagline.render("ARCADE BEAT-EM-UP", True, SUBTITLE_COLOUR)
    tag_scale = scale * 0.9
    tag_w = int(tag_surf.get_width() * tag_scale)
    tag_h = int(tag_surf.get_height() * tag_scale)
    if tag_w > 0 and tag_h > 0:
        tag_surf = pygame.transform.smoothscale(tag_surf, (tag_w, tag_h))
        _blit_centred(screen, tag_surf, cx, logo_cy + logo_h // 2 + tag_h)

    # --- Decorative horizontal rule ---
    rule_y = logo_cy + logo_h // 2 + tag_h * 2 + 10
    rule_alpha = int(255 * scale)
    rule_colour = tuple(int(c * rule_alpha / 255) for c in GLOW_COLOUR)
    if scale > 0.05:
        rule_half = int(width * 0.30 * scale)
        pygame.draw.line(screen, rule_colour, (cx - rule_half, rule_y), (cx + rule_half, rule_y), 2)


def _draw_prompt(screen, width, height, frame, font_prompt):
    """Blinking 'PRESS ANY KEY' prompt."""
    blink_on = (frame % PROMPT_BLINK_PERIOD) < (PROMPT_BLINK_PERIOD * 0.65)
    if not blink_on:
        return
    prompt_surf = font_prompt.render("PRESS ANY KEY TO START", True, PROMPT_COLOUR)
    _blit_centred(screen, prompt_surf, width // 2, int(height * 0.72))


class SplashScreen:
    """Self-contained splash / loading screen shown before gameplay."""

    def __init__(self, screen: pygame.Surface, width: int, height: int, fps: int):
        self.screen = screen
        self.width = width
        self.height = height
        self.fps = fps
        self.clock = pygame.time.Clock()

        # Build a cached gradient surface so we only loop once
        self._bg = pygame.Surface((width, height))
        _draw_background(self._bg, width, height)

        self.font_logo = pygame.font.SysFont(None, 112, bold=True)
        self.font_tagline = pygame.font.SysFont(None, 32)
        self.font_prompt = pygame.font.SysFont(None, 28)

    def run(self) -> None:
        """Block until the splash ends (key press or timer expiry)."""
        frame = 0
        while True:
            self.clock.tick(self.fps)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit
                if event.type == pygame.KEYDOWN:
                    return  # any key → skip to game

            self.screen.blit(self._bg, (0, 0))
            _draw_logo(self.screen, self.width, self.height, frame,
                       self.font_logo, self.font_tagline)

            # Only show the "press key" prompt after the scale-in finishes
            if frame >= SCALE_IN_FRAMES:
                _draw_prompt(self.screen, self.width, self.height, frame, self.font_prompt)

            pygame.display.flip()
            frame += 1

            if frame >= SPLASH_DURATION_FRAMES:
                return  # auto-advance after 3 s
