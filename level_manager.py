"""level_manager.py

Simple registry and factory for Quad Fighter game levels.

Usage
-----
Register a level class once (typically at startup or in the level's
own module)::

    from level_manager import LevelManager
    from moto_level import MotoLevel

    LevelManager.register("moto", MotoLevel)

Then load and run a level by key::

    level = LevelManager.load(
        "moto", screen, width, height, fps,
        settings, font, acid, sfx,
        joystick=joystick,
    )
    result = level.run()

New levels can be added without modifying any engine code – just call
``LevelManager.register`` before calling ``load``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from base_level import BaseLevel


class LevelManager:
    """Registry and factory for game levels.

    All methods are class-level; no instance is needed.
    """

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, key: str, level_class: type) -> None:
        """Associate *key* with *level_class*.

        Parameters
        ----------
        key         : str  – the string used to look up this level
                             (e.g. ``"moto"``, ``"rampage"``).
        level_class : type – a class that inherits ``BaseLevel``.
        """
        cls._registry[key] = level_class

    @classmethod
    def load(cls, key: str, *args, **kwargs) -> "BaseLevel":
        """Instantiate the level registered under *key*.

        All positional and keyword arguments are forwarded to the
        level's ``__init__``.

        Raises
        ------
        KeyError
            If no level is registered under *key*.
        """
        if key not in cls._registry:
            raise KeyError(
                f"No level registered for key '{key}'. "
                f"Available keys: {sorted(cls._registry)}"
            )
        return cls._registry[key](*args, **kwargs)

    @classmethod
    def available_keys(cls) -> list[str]:
        """Return a sorted list of all registered level keys."""
        return sorted(cls._registry)
