import pygame
import math

from settings import AXIS_DEADZONE

# Splash screen timing
SPLASH_DURATION_FRAMES = 180   # 3 sec at 60 FPS
SCALE_IN_FRAMES = 40           # logo scale-in animation length
PROMPT_BLINK_PERIOD = 60       # "press any key" blink cycle in frames

# Font sizes
FONT_SIZE_LOGO = 112
FONT_SIZE_TAGLINE = 32
FONT_SIZE_PROMPT = 28
FONT_SIZE_MENU = 36

# Colours
BG_TOP = (6, 6, 20)
BG_BOTTOM = (18, 12, 36)
LOGO_COLOUR = (230, 220, 255)
OUTLINE_COLOUR = (60, 0, 100)
GLOW_COLOUR = (140, 80, 220)
PROMPT_COLOUR = (200, 200, 220)
SUBTITLE_COLOUR = (120, 100, 150)
MENU_COLOUR = (200, 200, 220)
MENU_SEL_COLOUR = (255, 240, 80)
MENU_SEL_GLOW = (200, 160, 0)
MENU_HINT_COLOUR = (110, 100, 140)

# Menu items and their return values
MENU_ITEMS = [
    ("Start Game",       "game"),
    ("Moto Level",       "moto"),
    ("Rampage Level",    "rampage"),
    ("Gauntlet Mode",    "gauntlet"),
    ("Pang Mode",        "pang"),
    ("Rolling Ball",     "rolling_ball"),
    ("R-Type Mode",      "rtype"),
    ("Options",          "options"),
]


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
    # sqrt maps [0,1] to [0,1] with a concave-down curve: fast at the start,
    # decelerating to rest — this is an ease-out (deceleration) effect.
    scale = math.sqrt(scale)

    cx = width // 2
    logo_cy = int(height * 0.30)

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


def _draw_menu(screen, width, height, frame, font_menu, font_hint, selection: int, logo_bottom_y: int):
    """Draw the Start Game / Options menu below the logo."""
    cx = width // 2
    menu_top = logo_bottom_y + 24

    for i, (label, _) in enumerate(MENU_ITEMS):
        item_y = menu_top + i * 48
        is_sel = (i == selection)

        if is_sel:
            # Glow outline
            glow = font_menu.render(label, True, MENU_SEL_GLOW)
            for dx, dy in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
                screen.blit(glow, (cx - glow.get_width() // 2 + dx, item_y + dy))
            # Arrow cursor
            arrow = font_menu.render("►", True, MENU_SEL_COLOUR)
            screen.blit(arrow, (cx - font_menu.size(label)[0] // 2 - arrow.get_width() - 10, item_y))
            surf = font_menu.render(label, True, MENU_SEL_COLOUR)
        else:
            surf = font_menu.render(label, True, MENU_COLOUR)

        screen.blit(surf, (cx - surf.get_width() // 2, item_y))

    # Navigation hint (blinks)
    if (frame // 40) % 2 == 0:
        hint = "↑↓ Navigate   Enter/A Select   Controller supported"
        hint_surf = font_hint.render(hint, True, MENU_HINT_COLOUR)
        screen.blit(hint_surf, (cx - hint_surf.get_width() // 2, height - 32))


class SplashScreen:
    """Splash / main-menu screen shown before gameplay.

    ``run()`` returns ``"game"`` or ``"options"`` depending on the player's
    choice.  The optional *joystick* parameter enables Xbox controller
    navigation.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
        fps: int,
        joystick=None,   # pygame.joystick.Joystick or None
    ):
        self.screen   = screen
        self.width    = width
        self.height   = height
        self.fps      = fps
        self.joystick = joystick
        self.clock    = pygame.time.Clock()

        # Build a cached gradient surface so we only loop once
        self._bg = pygame.Surface((width, height))
        _draw_background(self._bg, width, height)

        self.font_logo    = pygame.font.SysFont(None, FONT_SIZE_LOGO,    bold=True)
        self.font_tagline = pygame.font.SysFont(None, FONT_SIZE_TAGLINE)
        self.font_menu    = pygame.font.SysFont(None, FONT_SIZE_MENU,    bold=True)
        self.font_hint    = pygame.font.SysFont(None, FONT_SIZE_PROMPT)

        self._selection  = 0          # currently highlighted menu item
        self._prev_hat   = (0, 0)
        self._prev_stick = 0.0        # left-stick Y axis previous value

    def run(self) -> str:
        """Block until the player selects a menu item.  Returns ``"game"`` or ``"options"``."""
        frame = 0
        while True:
            self.clock.tick(self.fps)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit

                if event.type == pygame.KEYDOWN:
                    result = self._handle_key(event.key)
                    if result:
                        return result

                if event.type == pygame.JOYBUTTONDOWN:
                    result = self._handle_joy_button(event.button)
                    if result:
                        return result

                if event.type == pygame.JOYHATMOTION:
                    hx, hy = event.value
                    ph, _ = self._prev_hat
                    self._prev_hat = (hx, hy)
                    if hy > 0:   # D-pad up
                        self._move(-1)
                    elif hy < 0: # D-pad down
                        self._move(1)

                if event.type == pygame.JOYAXISMOTION and event.axis == 1:
                    prev = self._prev_stick
                    self._prev_stick = event.value
                    if event.value < -AXIS_DEADZONE and prev >= -AXIS_DEADZONE:
                        self._move(-1)
                    elif event.value > AXIS_DEADZONE and prev <= AXIS_DEADZONE:
                        self._move(1)

            self.screen.blit(self._bg, (0, 0))

            # Compute logo bottom so menu sits neatly below it
            logo_bottom = self._draw_logo_and_get_bottom(frame)

            if frame >= SCALE_IN_FRAMES:
                _draw_menu(
                    self.screen, self.width, self.height, frame,
                    self.font_menu, self.font_hint,
                    self._selection, logo_bottom,
                )

            pygame.display.flip()
            frame += 1

    # ── Input helpers ─────────────────────────────────────────────────────────

    def _move(self, direction: int) -> None:
        self._selection = (self._selection + direction) % len(MENU_ITEMS)

    def _handle_key(self, key: int) -> str | None:
        if key == pygame.K_UP:
            self._move(-1)
        elif key == pygame.K_DOWN:
            self._move(1)
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
            return MENU_ITEMS[self._selection][1]
        return None

    def _handle_joy_button(self, button: int) -> str | None:
        # A button (0) confirms selection
        if button == 0:
            return MENU_ITEMS[self._selection][1]
        return None

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw_logo_and_get_bottom(self, frame: int) -> int:
        """Draw logo + tagline; return the y coordinate of the bottom of the logo block."""
        _draw_logo(self.screen, self.width, self.height, frame,
                   self.font_logo, self.font_tagline)
        # Replicate the logo_cy + size calculation used inside _draw_logo
        scale = min(1.0, frame / SCALE_IN_FRAMES) if SCALE_IN_FRAMES > 0 else 1.0
        scale = math.sqrt(scale)
        logo_cy = int(self.height * 0.30)
        logo_h = int(self.font_logo.size("QUAD FIGHTER")[1] * scale)
        tag_h  = int(self.font_tagline.size("ARCADE BEAT-EM-UP")[1] * scale * 0.9)
        return logo_cy + logo_h // 2 + tag_h * 2 + 14
