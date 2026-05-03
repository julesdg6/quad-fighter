"""level_randomizer.py

Random-level tournament mode for Quad Fighter.

When ``random_level`` is enabled in settings this module manages:

  - A spinning wheel to pick the next level
  - Post-round placement selection (host manually orders players 1st–4th)
  - Per-round and cumulative league table
  - "Press FIRE to continue" gating between screens

Usage (from main.py)::

    from level_randomizer import LevelRandomizer

    randomizer = LevelRandomizer(screen, WIDTH, HEIGHT, FPS, settings,
                                 joystick=joystick)
    level_key = randomizer.spin_wheel()       # first spin
    while level_key is not None:
        result = LevelManager.load(level_key, ...).run()
        if result == "exit":
            break
        level_key = randomizer.run_post_round(result)
"""

from __future__ import annotations

import math
import random

import pygame

from level_manager import LevelManager

# ── Scoring ───────────────────────────────────────────────────────────────────

#: Points awarded by finishing position (index 0 = 1st place)
PLACE_POINTS = [3, 2, 1, 0]

# ── Wheel spin parameters ────────────────────────────────────────────────────

SPIN_DECEL       = 0.97    # per-frame speed multiplier during deceleration
SPIN_STOP_SPEED  = 0.4     # deg/frame below which the spin is considered done
SPIN_SPEED_MIN   = 18.0    # deg/frame – slowest initial speed
SPIN_SPEED_MAX   = 30.0    # deg/frame – fastest initial speed
SPIN_EXTRA_TURNS = 3       # guaranteed extra full rotations for drama

# ── Layout ────────────────────────────────────────────────────────────────────

WHEEL_RADIUS  = 175
FONT_SIZE_HDR = 44
FONT_SIZE_MID = 24
FONT_SIZE_SM  = 18

# ── Colours ───────────────────────────────────────────────────────────────────

BG_TOP   = (6,  6,  20)
BG_BOT   = (18, 12, 36)
COL_HDR  = (230, 220, 255)
COL_TEXT = (200, 200, 220)
COL_SEL  = (255, 240,  80)
COL_DIM  = (100,  90, 130)
COL_HINT = (110, 100, 140)

WHEEL_COLOURS = [
    (200,  80,  80),
    ( 80, 200,  80),
    ( 80, 120, 220),
    (220, 160,  40),
    (180,  80, 220),
    ( 40, 200, 180),
    (200, 100,  40),
    (140, 200,  80),
]

PLAYER_COLOURS = [
    (100, 200, 255),   # P1 – cyan
    (255, 180,  60),   # P2 – amber
    (100, 255, 120),   # P3 – green
    (255, 100, 120),   # P4 – rose
]


# ── Private helpers ───────────────────────────────────────────────────────────

def _draw_bg(surface: pygame.Surface) -> None:
    w, h = surface.get_size()
    for y in range(h):
        t = y / h
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (w, y))


def _points_for_place(place: int) -> int:
    """Return points for a 0-indexed placement (0 = 1st)."""
    return PLACE_POINTS[min(place, len(PLACE_POINTS) - 1)]


def _blit_centred(surf: pygame.Surface, dst: pygame.Surface,
                  cx: int, cy: int) -> None:
    dst.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))


def _player_name(idx: int) -> str:
    return f"P{idx + 1}"


# ── LevelRandomizer ───────────────────────────────────────────────────────────

class LevelRandomizer:
    """Manages the random-level tournament: wheel, placements, league table.

    Parameters
    ----------
    screen   : pygame.Surface
    width    : int
    height   : int
    fps      : int
    settings : Settings
    joystick : pygame.joystick.Joystick | None
    """

    def __init__(self, screen: pygame.Surface, width: int, height: int,
                 fps: int, settings, joystick=None) -> None:
        self.screen   = screen
        self.width    = width
        self.height   = height
        self.fps      = fps
        self.settings = settings
        self.joystick = joystick
        self.clock    = pygame.time.Clock()

        self.num_players  = max(1, settings.num_players)
        self.scores       = [0] * self.num_players   # cumulative totals
        self.round_number = 0
        self.spinner_idx  = 0   # 0-indexed player who spins the wheel

        # Registered level keys (sorted for a consistent wheel layout)
        self._keys = LevelManager.available_keys()

        # Pre-render gradient background
        self._bg = pygame.Surface((width, height))
        _draw_bg(self._bg)

        self._font_hdr = pygame.font.SysFont(None, FONT_SIZE_HDR, bold=True)
        self._font_mid = pygame.font.SysFont(None, FONT_SIZE_MID)
        self._font_sm  = pygame.font.SysFont(None, FONT_SIZE_SM)

    # ── Public API ────────────────────────────────────────────────────────────

    def spin_wheel(self) -> str:
        """Show the spinning wheel and return the chosen level key."""
        if not self._keys:
            return ""

        chosen_idx = random.randrange(len(self._keys))
        chosen_key = self._keys[chosen_idx]

        n       = len(self._keys)
        seg_deg = 360.0 / n

        # The pointer sits at the top of the wheel (−90°).
        # We want segment `chosen_idx` to stop under it.
        # Centre of segment i is at angle: spin_angle + i*seg_deg + seg_deg/2.
        # We need that to equal −90 (mod 360).
        # → spin_angle = −90 − (chosen_idx + 0.5)*seg_deg  (mod 360)
        target = (-90.0 - (chosen_idx + 0.5) * seg_deg) % 360.0

        # ── Phase 1: wait for player to press fire ────────────────────────
        spin_angle = 0.0
        self._await_fire(
            draw_fn=lambda: self._draw_wheel_screen(
                spin_angle, prompt="Press FIRE / Z to spin the wheel",
            ),
        )

        # ── Phase 2: animated spin ────────────────────────────────────────
        speed       = random.uniform(SPIN_SPEED_MIN, SPIN_SPEED_MAX)
        total_rot   = 0.0
        # Minimum rotation: enough extra turns + distance to target
        min_rot     = SPIN_EXTRA_TURNS * 360.0 + (target - spin_angle) % 360.0
        decelerating = False

        while True:
            self.clock.tick(self.fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit

            spin_angle = (spin_angle + speed) % 360.0
            total_rot += speed

            if total_rot >= min_rot:
                decelerating = True

            if decelerating:
                speed *= SPIN_DECEL

            if decelerating and speed < SPIN_STOP_SPEED:
                spin_angle = target  # snap precisely
                self._draw_wheel_screen(
                    spin_angle,
                    prompt=f"▶  {chosen_key.replace('_', ' ').upper()}",
                )
                pygame.display.flip()
                pygame.time.wait(2200)
                break

            self._draw_wheel_screen(spin_angle, prompt="")
            pygame.display.flip()

        return chosen_key

    def run_post_round(self, level_result: str) -> str | None:
        """Show placement screen, award points, show league table, spin wheel.

        Returns the next level key, or ``None`` if the user exits.
        """
        self.round_number += 1

        # Determine placements ────────────────────────────────────────────────
        if self.num_players == 1:
            # Solo: complete = 1st place (3 pts), dead = DNF (0 pts)
            place = 0 if level_result == "complete" else len(PLACE_POINTS) - 1
            placements = [place]
        elif level_result != "complete":
            # All players DNF
            placements = [len(PLACE_POINTS) - 1] * self.num_players
        else:
            placements = self._select_placements()
            if placements is None:
                return None   # user escaped during placement

        # Award points ────────────────────────────────────────────────────────
        round_scores = [_points_for_place(p) for p in placements]
        for i, pts in enumerate(round_scores):
            self.scores[i] += pts

        # Next spinner = player with highest cumulative score (P1 if tied,
        # which is intentional: P1 acts as host in tie situations)
        self.spinner_idx = self.scores.index(max(self.scores))

        # Show league table and wait for fire ─────────────────────────────────
        exited = self._show_league_table(round_scores)
        if exited:
            return None

        # Spin for next level ─────────────────────────────────────────────────
        return self.spin_wheel()

    # ── Placement selection screen ────────────────────────────────────────────

    def _select_placements(self) -> list[int] | None:
        """Interactive reorder screen.

        The host uses ↑↓ to swap players in the ranking list.
        Returns ``placements[player_idx] = 0-indexed place``,
        or ``None`` if Esc is pressed.
        """
        # order[rank] = player_index
        order  = list(range(self.num_players))
        cursor = 0   # which rank row is selected

        while True:
            self.clock.tick(self.fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP and cursor > 0:
                        order[cursor], order[cursor - 1] = (
                            order[cursor - 1], order[cursor]
                        )
                        cursor -= 1
                    elif (event.key == pygame.K_DOWN
                          and cursor < self.num_players - 1):
                        order[cursor], order[cursor + 1] = (
                            order[cursor + 1], order[cursor]
                        )
                        cursor += 1
                    elif event.key in (pygame.K_z, pygame.K_SPACE,
                                       pygame.K_RETURN, pygame.K_x):
                        placements = [0] * self.num_players
                        for rank, p_idx in enumerate(order):
                            placements[p_idx] = rank
                        return placements
                    elif event.key == pygame.K_ESCAPE:
                        return None

                if event.type == pygame.JOYBUTTONDOWN:
                    a_btn = self.settings.controller.get("jump", 0)
                    back_btn = self.settings.controller.get("back", 6)
                    if event.button == a_btn:
                        placements = [0] * self.num_players
                        for rank, p_idx in enumerate(order):
                            placements[p_idx] = rank
                        return placements
                    if event.button == back_btn:
                        return None

                if event.type == pygame.JOYHATMOTION:
                    _, hy = event.value
                    if hy > 0 and cursor > 0:
                        order[cursor], order[cursor - 1] = (
                            order[cursor - 1], order[cursor]
                        )
                        cursor -= 1
                    elif hy < 0 and cursor < self.num_players - 1:
                        order[cursor], order[cursor + 1] = (
                            order[cursor + 1], order[cursor]
                        )
                        cursor += 1

            self._draw_placement_screen(order, cursor)
            pygame.display.flip()

    # ── League table screen ───────────────────────────────────────────────────

    def _show_league_table(self, round_scores: list[int]) -> bool:
        """Render the league table until the player confirms.

        Returns ``True`` if the user pressed Esc (wants to exit).
        """
        frame = 0
        while True:
            self.clock.tick(self.fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return True
                    if event.key in (pygame.K_z, pygame.K_SPACE,
                                     pygame.K_RETURN, pygame.K_x,
                                     pygame.K_c):
                        return False
                if event.type == pygame.JOYBUTTONDOWN:
                    back_btn = self.settings.controller.get("back", 6)
                    if event.button == back_btn:
                        return True
                    return False

            self._draw_league_table(round_scores, frame)
            pygame.display.flip()
            frame += 1

    # ── Fire-to-continue helper ───────────────────────────────────────────────

    def _await_fire(self, draw_fn) -> None:
        """Call ``draw_fn()`` each frame until the player presses fire."""
        while True:
            self.clock.tick(self.fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_z, pygame.K_SPACE,
                                     pygame.K_RETURN, pygame.K_x):
                        return
                if event.type == pygame.JOYBUTTONDOWN:
                    return
            draw_fn()
            pygame.display.flip()

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw_wheel_screen(self, angle: float, prompt: str) -> None:
        self.screen.blit(self._bg, (0, 0))
        cx = self.width  // 2
        cy = self.height // 2 + 10

        # Title
        p_col  = PLAYER_COLOURS[self.spinner_idx % len(PLAYER_COLOURS)]
        title  = f"{_player_name(self.spinner_idx)} SPINS THE WHEEL"
        t_surf = self._font_hdr.render(title, True, p_col)
        _blit_centred(t_surf, self.screen, cx, 28)

        # Wheel
        self._draw_wheel(cx, cy, angle)

        # Pointer arrow above wheel
        ptr_y = cy - WHEEL_RADIUS - 8
        pygame.draw.polygon(
            self.screen, COL_SEL,
            [(cx, ptr_y + 18), (cx - 12, ptr_y), (cx + 12, ptr_y)],
        )

        # Prompt
        if prompt:
            p_surf = self._font_sm.render(prompt, True, COL_SEL)
            _blit_centred(p_surf, self.screen, cx, cy + WHEEL_RADIUS + 32)

    def _draw_wheel(self, cx: int, cy: int, angle: float) -> None:
        n       = len(self._keys)
        seg_deg = 360.0 / n
        r       = WHEEL_RADIUS

        for i, key in enumerate(self._keys):
            a0  = math.radians(angle + i * seg_deg)
            a1  = math.radians(angle + (i + 1) * seg_deg)
            col = WHEEL_COLOURS[i % len(WHEEL_COLOURS)]

            # Pie-slice polygon
            steps = max(6, int(seg_deg))
            pts   = [(cx, cy)]
            for s in range(steps + 1):
                a = a0 + (a1 - a0) * s / steps
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

            pygame.draw.polygon(self.screen, col, pts)
            pygame.draw.polygon(self.screen, (0, 0, 0), pts, 2)

            # Segment label
            mid_a   = (a0 + a1) / 2
            label_r = r * 0.62
            lx      = cx + label_r * math.cos(mid_a)
            ly      = cy + label_r * math.sin(mid_a)
            label   = key.replace("_", " ").upper()
            l_surf  = self._font_sm.render(label, True, (255, 255, 255))
            _blit_centred(l_surf, self.screen, int(lx), int(ly))

        # Centre hub
        pygame.draw.circle(self.screen, (40, 30, 60), (cx, cy), 20)
        pygame.draw.circle(self.screen, COL_SEL,      (cx, cy), 20, 2)

    def _draw_placement_screen(self, order: list[int], cursor: int) -> None:
        self.screen.blit(self._bg, (0, 0))
        cx = self.width // 2

        title_surf = self._font_hdr.render(
            f"ROUND {self.round_number}  –  SET PLACEMENTS", True, COL_HDR,
        )
        _blit_centred(title_surf, self.screen, cx, 32)

        inst_surf = self._font_sm.render(
            "↑↓ Reorder players   Z / Enter  Confirm", True, COL_HINT,
        )
        _blit_centred(inst_surf, self.screen, cx, 68)

        _ALL_PLACE_LABELS = ["1ST", "2ND", "3RD", "4TH"]
        place_labels = _ALL_PLACE_LABELS[:self.num_players]
        row_h  = 56
        start_y = 100

        for pos, p_idx in enumerate(order):
            y        = start_y + pos * row_h
            selected = (pos == cursor)
            p_col    = PLAYER_COLOURS[p_idx % len(PLAYER_COLOURS)]
            bg_col   = (30, 24, 50) if selected else (14, 10, 28)

            row_rect = pygame.Rect(cx - 190, y, 380, row_h - 6)
            pygame.draw.rect(self.screen, bg_col, row_rect, border_radius=6)
            if selected:
                pygame.draw.rect(self.screen, COL_SEL, row_rect, 2,
                                 border_radius=6)

            ry = y + (row_h - 6) // 2

            pl_surf = self._font_mid.render(place_labels[pos], True, COL_DIM)
            self.screen.blit(pl_surf, (cx - 170, ry - pl_surf.get_height() // 2))

            nm_surf = self._font_mid.render(_player_name(p_idx), True, p_col)
            self.screen.blit(nm_surf, (cx - 60, ry - nm_surf.get_height() // 2))

            pts = _points_for_place(pos)
            pt_surf = self._font_mid.render(f"+{pts} pts", True,
                                            COL_SEL if selected else COL_TEXT)
            self.screen.blit(pt_surf, (cx + 80, ry - pt_surf.get_height() // 2))

    def _draw_league_table(self, round_scores: list[int], frame: int) -> None:
        self.screen.blit(self._bg, (0, 0))
        cx = self.width // 2

        title_surf = self._font_hdr.render(
            f"ROUND {self.round_number}  RESULTS", True, COL_HDR,
        )
        _blit_centred(title_surf, self.screen, cx, 28)

        # Sort by cumulative score descending (stable: P1 wins ties)
        ranked = sorted(range(self.num_players),
                        key=lambda i: -self.scores[i])

        # Column headers
        col_xs = [cx - 230, cx - 110, cx + 40, cx + 160]
        headers = ["RANK", "PLAYER", "THIS ROUND", "TOTAL"]
        header_y = 80
        for hdr, hx in zip(headers, col_xs):
            h_surf = self._font_sm.render(hdr, True, COL_DIM)
            self.screen.blit(h_surf, (hx, header_y))

        pygame.draw.line(
            self.screen, COL_DIM,
            (cx - 240, header_y + 22), (cx + 240, header_y + 22),
        )

        row_h   = 44
        start_y = header_y + 30

        for rank, p_idx in enumerate(ranked):
            y     = start_y + rank * row_h
            p_col = PLAYER_COLOURS[p_idx % len(PLAYER_COLOURS)]

            rank_surf  = self._font_mid.render(f"#{rank + 1}", True, COL_TEXT)
            name_surf  = self._font_mid.render(_player_name(p_idx), True, p_col)
            rnd_surf   = self._font_mid.render(
                f"+{round_scores[p_idx]}", True, COL_SEL,
            )
            total_surf = self._font_mid.render(
                str(self.scores[p_idx]), True, COL_HDR,
            )

            self.screen.blit(rank_surf,  (col_xs[0], y))
            self.screen.blit(name_surf,  (col_xs[1], y))
            self.screen.blit(rnd_surf,   (col_xs[2], y))
            self.screen.blit(total_surf, (col_xs[3], y))

        # Blinking hint at the bottom
        if (frame // 30) % 2 == 0:
            hint = "Press FIRE / Z / Enter to continue   |   Esc to exit"
            h_surf = self._font_sm.render(hint, True, COL_HINT)
            _blit_centred(h_surf, self.screen, cx, self.height - 28)
