"""base_level.py

Abstract base class for all game levels / modes in Quad Fighter.

Every game mode (beat-em-up, moto, rampage, gauntlet, pang,
rolling-ball, …) inherits from BaseLevel and receives the shared
engine resources at construction time.

The minimal surface a concrete level must implement is ``run()``,
which drives its own tight loop and returns one of the canonical
result strings: ``"complete"``, ``"dead"``, or ``"exit"``.

Levels that wish to participate in an external engine-driven loop
can additionally override:

  handle_event(event)  – process a single pygame.Event
  update(dt)           – advance simulation by *dt* seconds
  draw()               – render the current frame to self.screen
"""

from __future__ import annotations

import abc


class BaseLevel(abc.ABC):
    """Common interface for all Quad Fighter game modes.

    Parameters
    ----------
    screen   : pygame.Surface   – the shared display surface
    width    : int              – display width  (pixels)
    height   : int              – display height (pixels)
    fps      : int              – target frame-rate
    settings : Settings         – user-configurable settings
    font     : pygame.font.Font – default UI font
    acid     : AcidMachine      – music / audio engine
    sfx      : SfxPlayer        – sound-effects player
    joystick : Joystick | None  – primary gamepad (optional)
    joystick2: Joystick | None  – secondary gamepad (optional)
    """

    def __init__(self, screen, width: int, height: int, fps: int,
                 settings, font, acid, sfx,
                 joystick=None, joystick2=None):
        self.screen    = screen
        self.width     = width
        self.height    = height
        self.fps       = fps
        self.settings  = settings
        self.font      = font
        self.acid      = acid
        self.sfx       = sfx
        self.joystick  = joystick
        self.joystick2 = joystick2

    # ── Required: tight-loop entry-point ──────────────────────────────────────

    @abc.abstractmethod
    def run(self) -> str:
        """Drive the level's main loop until it ends.

        Returns one of: ``"complete"``, ``"dead"``, ``"exit"``.
        """

    # ── Optional: external-loop hooks ─────────────────────────────────────────

    def handle_event(self, event) -> str | None:
        """Process a single ``pygame.Event``.

        Return a result string (e.g. ``"exit"``) to stop the level,
        or ``None`` to continue.
        """
        return None

    def update(self, dt: float) -> str | None:
        """Advance game logic by *dt* seconds.

        Return a result string to stop the level, or ``None`` to
        continue.
        """
        return None

    def draw(self) -> None:
        """Render the current frame to ``self.screen``."""
