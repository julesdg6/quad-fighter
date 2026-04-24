"""sfx.py – Procedural sound effects for Quad Fighter.

All sounds are synthesised at startup using numpy + pygame mixer.
No audio files are required.  If the mixer is unavailable the module
degrades gracefully and play() becomes a no-op.

Usage
-----
    from sfx import SfxPlayer
    sfx = SfxPlayer()              # call after pygame.mixer is initialised
    sfx.set_volume(0.8)            # 0.0–1.0
    sfx.play("punch")              # fire a named sound
"""

import numpy as np
import pygame

# Must match the mixer.pre_init() sample rate used in main.py (44100 Hz)
SR = 44100


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _to_int16(arr: np.ndarray) -> np.ndarray:
    return (np.clip(arr, -1.0, 1.0) * 32767).astype(np.int16)


def _make_sound(mono: np.ndarray) -> pygame.Sound:
    """Convert a float32 mono array to a stereo pygame.Sound."""
    s16 = _to_int16(mono)
    stereo = np.column_stack([s16, s16])
    return pygame.sndarray.make_sound(stereo)


def _hp_filter(noise: np.ndarray, coeff: float = 0.82) -> np.ndarray:
    """Simple 1-pole high-pass filter via smoothing subtraction."""
    smooth = np.zeros_like(noise)
    s = 0.0
    c = 1.0 - coeff
    for i in range(len(noise)):
        s = s * coeff + noise[i] * c
        smooth[i] = s
    return noise - smooth


# ── Sound generators ──────────────────────────────────────────────────────────

def _gen_punch() -> pygame.Sound:
    """Short snappy punch – primary / combo ground attack."""
    dur = 0.07
    n = int(dur * SR)
    t = np.linspace(0, dur, n, dtype=np.float32)
    rng = np.random.default_rng(7)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    crack = noise * np.exp(-t * 60.0)
    tone = np.sin(2 * np.pi * 130 * t) * np.exp(-t * 22.0)
    sig = crack * 0.65 + tone * 0.35
    return _make_sound(sig * 0.75)


def _gen_kick() -> pygame.Sound:
    """Heavier swinging whoosh – secondary / crouch kick."""
    dur = 0.13
    n = int(dur * SR)
    t = np.linspace(0, dur, n, dtype=np.float32)
    rng = np.random.default_rng(13)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    hp = _hp_filter(noise, 0.84)
    freq = 280 * np.exp(-t * 14) + 60
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 16.0)
    sig = (hp * 0.6 + np.sin(phase) * 0.4) * env
    return _make_sound(sig * 0.68)


def _gen_aerial() -> pygame.Sound:
    """Rising swoosh – aerial attack / flying kick."""
    dur = 0.18
    n = int(dur * SR)
    t = np.linspace(0, dur, n, dtype=np.float32)
    rng = np.random.default_rng(22)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    hp = _hp_filter(noise, 0.78)
    freq = 150.0 * np.exp(t * 6.0) + 100.0
    freq = np.minimum(freq, 2400.0).astype(np.float32)
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 10.0)
    sig = (hp * 0.55 + np.sin(phase) * 0.45) * env
    return _make_sound(sig * 0.65)


def _gen_impact() -> pygame.Sound:
    """Solid crack + low thump – successful hit connects."""
    dur = 0.14
    n = int(dur * SR)
    t = np.linspace(0, dur, n, dtype=np.float32)
    rng = np.random.default_rng(42)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    crack = noise * np.exp(-t * 70.0)
    freq = 90.0 * np.exp(-t * 14) + 48.0
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    thump = np.sin(phase) * np.exp(-t * 14.0)
    sig = crack * 0.55 + thump * 0.45
    return _make_sound(sig * 0.88)


def _gen_enemy_attack() -> pygame.Sound:
    """Short aggressive whoosh – regular enemy starts an attack."""
    dur = 0.12
    n = int(dur * SR)
    t = np.linspace(0, dur, n, dtype=np.float32)
    rng = np.random.default_rng(55)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    hp = _hp_filter(noise, 0.86)
    freq = 220.0 * np.exp(-t * 12) + 70.0
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 16.0)
    sig = (hp * 0.5 + np.sin(phase) * 0.5) * env
    return _make_sound(sig * 0.55)


def _gen_boss_attack() -> pygame.Sound:
    """Heavier, deeper whoosh – boss starts an attack."""
    dur = 0.20
    n = int(dur * SR)
    t = np.linspace(0, dur, n, dtype=np.float32)
    rng = np.random.default_rng(77)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    hp = _hp_filter(noise, 0.80)
    freq = 140.0 * np.exp(-t * 9) + 52.0
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 10.0)
    sig = (hp * 0.45 + np.sin(phase) * 0.55) * env
    return _make_sound(sig * 0.70)


def _gen_player_hurt() -> pygame.Sound:
    """Short impact noise – player takes damage."""
    dur = 0.10
    n = int(dur * SR)
    t = np.linspace(0, dur, n, dtype=np.float32)
    rng = np.random.default_rng(11)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    tone = np.sin(2 * np.pi * 320 * t * np.exp(-t * 3))
    env = np.exp(-t * 24.0)
    sig = (noise * 0.5 + tone * 0.5) * env
    return _make_sound(sig * 0.65)


def _gen_enemy_hurt() -> pygame.Sound:
    """Short higher-pitched hit noise – enemy takes damage."""
    dur = 0.09
    n = int(dur * SR)
    t = np.linspace(0, dur, n, dtype=np.float32)
    rng = np.random.default_rng(33)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    tone = np.sin(2 * np.pi * 480 * t * np.exp(-t * 4))
    env = np.exp(-t * 28.0)
    sig = (noise * 0.55 + tone * 0.45) * env
    return _make_sound(sig * 0.60)


def _gen_break() -> pygame.Sound:
    """Crash and splinter – crate or barrel destroyed."""
    dur = 0.22
    n = int(dur * SR)
    t = np.linspace(0, dur, n, dtype=np.float32)
    rng = np.random.default_rng(88)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    env = np.exp(-t * 12.0)
    tone = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 20)
    sig = (noise * 0.72 + tone * 0.28) * env
    return _make_sound(sig * 0.80)


def _gen_special() -> pygame.Sound:
    """Rising charged power burst – special move triggered."""
    dur = 0.24
    n = int(dur * SR)
    t = np.linspace(0, dur, n, dtype=np.float32)
    rng = np.random.default_rng(99)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    hp = _hp_filter(noise, 0.75)
    # Rapidly rising frequency sweep for that "power-up" feel
    freq = 110.0 * np.exp(t * 9.0) + 90.0
    freq = np.minimum(freq, 3600.0).astype(np.float32)
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 5.0)
    sig = (hp * 0.38 + np.sin(phase) * 0.62) * env
    return _make_sound(sig * 0.90)


# ── SfxPlayer ─────────────────────────────────────────────────────────────────

class SfxPlayer:
    """
    Centralised sound-effects manager.

    Instantiate after ``pygame.mixer`` is initialised.  All sounds are
    synthesised once at construction time; subsequent calls to ``play()``
    are non-blocking.

    ``set_volume(v)`` scales all SFX uniformly (0.0 – 1.0).
    ``play(name)`` silently ignores unknown or failed sounds so the game
    never crashes due to missing audio.
    """

    _GENERATORS = {
        "punch":        _gen_punch,
        "kick":         _gen_kick,
        "aerial":       _gen_aerial,
        "impact":       _gen_impact,
        "enemy_attack": _gen_enemy_attack,
        "boss_attack":  _gen_boss_attack,
        "player_hurt":  _gen_player_hurt,
        "enemy_hurt":   _gen_enemy_hurt,
        "break":        _gen_break,
        "special":      _gen_special,
    }

    def __init__(self):
        self._sounds: dict = {}
        self._volume: float = 1.0
        if not pygame.mixer.get_init():
            return
        for name, gen in self._GENERATORS.items():
            try:
                self._sounds[name] = gen()
            except Exception:
                pass  # degrade gracefully if synthesis fails for any sound

    def set_volume(self, volume: float) -> None:
        """Set playback volume for all SFX.  *volume* is clamped to 0.0–1.0."""
        self._volume = max(0.0, min(1.0, volume))
        for sound in self._sounds.values():
            sound.set_volume(self._volume)

    def play(self, name: str) -> None:
        """Play a named sound effect.  Silently ignores unknown or missing sounds."""
        sound = self._sounds.get(name)
        if sound is not None:
            sound.play()
