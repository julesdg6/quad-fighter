"""
music.py

Procedural acid house music engine for Quad Fighter.

Synthesises a continuously evolving TB-303 acid bassline plus kick/snare/hi-hat
drums using numpy and pygame's mixer.  No audio files are required – every
sound is generated from first principles with simple waveforms and filters.

Usage
-----
    from music import AcidMachine
    acid = AcidMachine()   # call after pygame.mixer is initialised
    # inside game loop:
    acid.tick(dt)          # dt = seconds elapsed since last frame
"""

import math
import random
import threading

import numpy as np
import pygame

# ── Constants ─────────────────────────────────────────────────────────────────

SR = 44100            # sample rate (Hz)
BPM_BASE = 138        # base tempo – classic acid house range
STEPS_PER_BAR = 16    # 16th-note resolution

# Minor-pentatonic + tritone interval set (semitones above root).
# Gives that greasy, squelchy 303 feel.
SCALE = [0, 3, 5, 7, 10, 12, 15, 17, 19]

# Mixer channels reserved for the acid machine.
CH_KICK = 4
CH_SNARE = 5
CH_HIHAT = 6
CH_BASS = 7
CH_BASS2 = 8


# ── Helpers ───────────────────────────────────────────────────────────────────

def _midi_to_hz(midi: int) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _to_int16(arr: np.ndarray) -> np.ndarray:
    arr = np.clip(arr, -1.0, 1.0)
    return (arr * 32767).astype(np.int16)


def _make_sound(mono: np.ndarray) -> pygame.Sound:
    """Convert a float32 mono array to a stereo pygame.Sound."""
    s16 = _to_int16(mono)
    stereo = np.column_stack([s16, s16])   # shape (n, 2)
    return pygame.sndarray.make_sound(stereo)


# ── Drum synthesis ────────────────────────────────────────────────────────────

def _make_kick(duration: float = 0.32) -> pygame.Sound:
    n = int(duration * SR)
    t = np.linspace(0, duration, n, dtype=np.float32)
    freq = 180.0 * np.exp(-t * 24.0) + 52.0          # pitch envelope
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 9.0)
    click = np.exp(-t * 140.0) * 0.45                 # transient click
    sig = (np.sin(phase) + click) * env
    return _make_sound(sig * 0.92)


def _make_snare(duration: float = 0.19) -> pygame.Sound:
    rng = np.random.default_rng(42)
    n = int(duration * SR)
    t = np.linspace(0, duration, n, dtype=np.float32)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    tone = np.sin(2.0 * np.pi * 215.0 * t)
    env = np.exp(-t * 22.0)
    sig = (noise * 0.65 + tone * 0.35) * env
    return _make_sound(sig * 0.78)


def _make_hihat(open_hat: bool = False) -> pygame.Sound:
    seed = 99 if open_hat else 7
    decay = 14.0 if open_hat else 60.0
    duration = 0.14 if open_hat else 0.045
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.linspace(0, duration, n, dtype=np.float32)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    # High-pass via 1-pole smoothing subtraction
    smooth = np.zeros(n, dtype=np.float32)
    s = 0.0
    for i in range(n):
        s = s * 0.82 + noise[i] * 0.18
        smooth[i] = s
    hp = noise - smooth
    env = np.exp(-t * decay)
    return _make_sound(hp * env * 0.50)


# ── Acid bass synthesis (TB-303 style) ────────────────────────────────────────

def _make_bass_note(midi: int, accent: bool, step_secs: float,
                    waveform: str = 'saw') -> pygame.Sound:
    """
    Synthesise a single 303-style bass note.

    Uses an oscillator (sawtooth or square) fed through a resonant state-variable
    filter (SVF) whose cutoff decays exponentially – the classic acid sweep.
    ``waveform`` may be ``'saw'`` (TB-303 default) or ``'square'`` (brighter buzz,
    used for the second 303 voice).
    """
    duration = step_secs * (1.65 if accent else 0.80)
    n = int(duration * SR)
    t = np.linspace(0, duration, n, dtype=np.float32)
    freq = _midi_to_hz(midi)

    # Oscillator – sawtooth or square
    phase = (freq * t) % 1.0
    if waveform == 'square':
        osc = (2.0 * (phase < 0.5).astype(np.float32) - 1.0)
    else:
        osc = (2.0 * phase - 1.0).astype(np.float32)

    # Amplitude envelope (snappier on accents)
    att = int(SR * 0.004)
    amp_env = np.exp(-t * (5.0 if accent else 9.0))
    amp_env[:att] *= np.linspace(0, 1, att)

    # Resonant SVF – per-sample variable cutoff (the "acid sweep")
    cutoff_start = 2800.0 if accent else 950.0
    cutoff_floor = 300.0
    cutoff = cutoff_start * np.exp(-t * (9.0 if accent else 6.0)) + cutoff_floor
    resonance = 4.5 + (2.0 if accent else 0.0)   # higher = more squelch
    r = 1.0 / max(0.5, resonance)                 # 1/Q

    f_arr = 2.0 * np.sin(np.pi * np.minimum(cutoff, SR * 0.48) / SR)
    filtered = np.zeros(n, dtype=np.float32)
    lp_s, bp_s = 0.0, 0.0
    for i in range(n):
        hp_s = osc[i] - lp_s - r * bp_s
        bp_s = f_arr[i] * hp_s + bp_s
        lp_s = f_arr[i] * bp_s + lp_s
        filtered[i] = lp_s

    sig = filtered * amp_env
    # Soft clip / overdrive for that gritty 303 warmth
    sig = np.tanh(sig * 1.8) / np.tanh(np.float32(1.8))
    peak = float(np.max(np.abs(sig)))
    if peak > 1e-6:
        sig /= peak
    # Square wave is a little louder in the mix; pull it back slightly
    vol = 0.72 if waveform == 'square' else 0.78
    return _make_sound(sig * vol)


# ── Pattern generators ────────────────────────────────────────────────────────

def _gen_bass_pattern(root: int, rng: random.Random) -> list:
    """
    Return a 16-step bass pattern.  Each entry is (midi_note, accent_bool)
    or None (rest).
    """
    scale_midi = [root + s for s in SCALE]
    pattern = []
    for i in range(STEPS_PER_BAR):
        # Beat 1 always hits (keeps energy constant)
        if i == 0:
            pattern.append((rng.choice(scale_midi[:4]), rng.random() < 0.65))
        # Other downbeats (2, 3, 4) often hit
        elif i in (4, 8, 12):
            if rng.random() < 0.78:
                note = rng.choice(scale_midi[:6])
                pattern.append((note, rng.random() < 0.42))
            else:
                pattern.append(None)
        # Off-beats: occasional 16th notes for groove
        else:
            if rng.random() < 0.42:
                octave_shift = rng.choice([0, 0, 0, 12, -12])
                note = max(24, min(72, rng.choice(scale_midi) + octave_shift))
                pattern.append((note, rng.random() < 0.25))
            else:
                pattern.append(None)
    return pattern


def _gen_drum_pattern(rng: random.Random, bar: int) -> dict:
    """Return kick/snare/hihat/openhat step lists for one bar."""
    kick    = [False] * STEPS_PER_BAR
    snare   = [False] * STEPS_PER_BAR
    hihat   = [False] * STEPS_PER_BAR
    openhat = [False] * STEPS_PER_BAR

    # Four-on-the-floor kick – always present
    for s in (0, 4, 8, 12):
        kick[s] = True

    # Snare on beats 2 and 4
    snare[4] = True
    snare[12] = True

    # Hi-hat: straight 8ths early on, 16ths when energy builds
    hat_step = 2 if (bar // 4) % 2 == 0 else 1
    for s in range(0, STEPS_PER_BAR, hat_step):
        hihat[s] = True

    # Occasional extra kick on the "and" of beat 2 or 4 for drive
    if bar % 2 == 1:
        if rng.random() < 0.55:
            kick[2] = True
        if rng.random() < 0.35:
            kick[10] = True

    # Open hi-hat on offbeats every few bars
    if bar % 4 == 3 and rng.random() < 0.65:
        openhat[6] = True
    if bar % 8 == 7 and rng.random() < 0.50:
        openhat[14] = True

    # Snare ghost on 16th before beat 3 occasionally
    if bar % 4 == 2 and rng.random() < 0.40:
        snare[7] = True

    return {"kick": kick, "snare": snare, "hihat": hihat, "openhat": openhat}


# ── Root note evolution ───────────────────────────────────────────────────────

# Classic acid house root-note cycle (C, F, G, A♭ …)
_ROOT_SHIFTS = [0, 5, 7, 3, 10, 2, 8, 0]


# ── AcidMachine ───────────────────────────────────────────────────────────────

class AcidMachine:
    """
    Procedural acid house sequencer.

    Call ``tick(dt)`` once per game frame where *dt* is the elapsed time in
    seconds.  The machine schedules drum hits and acid bass notes onto
    dedicated pygame mixer channels.
    """

    def __init__(self):
        self._enabled = False
        if not pygame.mixer.get_init():
            return  # mixer not available – run silently

        pygame.mixer.set_num_channels(max(10, pygame.mixer.get_num_channels()))

        self._bpm = BPM_BASE
        self._step_secs = 60.0 / (self._bpm * 4)
        self._rng = random.Random()  # unseeded – different music every session
        self._step = 0
        self._bar = 0
        self._time_acc = 0.0
        self._root_idx = 0
        self._root = 36  # C2

        # Drum sounds (generated once)
        self._kick    = _make_kick()
        self._snare   = _make_snare()
        self._hihat   = _make_hihat(open_hat=False)
        self._openhat = _make_hihat(open_hat=True)

        # Bass note cache: (midi, accent, waveform) → pygame.Sound
        self._note_cache: dict = {}
        self._cache_lock = threading.Lock()

        # Generate initial patterns (two independent bass patterns for dual 303)
        self._drum_pattern = _gen_drum_pattern(self._rng, self._bar)
        self._bass_pattern = _gen_bass_pattern(self._root, self._rng)
        self._bass_pattern2 = _gen_bass_pattern(self._root, self._rng)

        # Track which roots are already being pre-generated to avoid duplicate threads.
        self._pregenerate_roots: set = set()
        self._pregenerate_async(self._root)

        # Dedicated mixer channels
        self._ch_kick   = pygame.mixer.Channel(CH_KICK)
        self._ch_snare  = pygame.mixer.Channel(CH_SNARE)
        self._ch_hihat  = pygame.mixer.Channel(CH_HIHAT)
        # Two 303 voices: sawtooth (slightly left) and square (slightly right)
        self._ch_bass   = pygame.mixer.Channel(CH_BASS)
        self._ch_bass2  = pygame.mixer.Channel(CH_BASS2)
        self._ch_bass.set_volume(1.0, 0.75)
        self._ch_bass2.set_volume(0.75, 1.0)

        self._enabled = True

    # ── Pre-generation ────────────────────────────────────────────────────────

    def _pregenerate_async(self, root: int) -> None:
        """Spawn a daemon thread to warm the note cache for the given root.
        Skips silently if a thread for this root is already running."""
        with self._cache_lock:
            if root in self._pregenerate_roots:
                return
            self._pregenerate_roots.add(root)

        step_secs = self._step_secs

        def _work():
            # Range: −1 octave to +2 octaves above root; both waveforms
            for semitone in range(-12, 25):
                midi = root + semitone
                if not (24 <= midi <= 72):
                    continue
                for accent in (False, True):
                    for wf in ('saw', 'square'):
                        key = (midi, accent, wf)
                        with self._cache_lock:
                            if key in self._note_cache:
                                continue
                        sound = _make_bass_note(midi, accent, step_secs, wf)
                        with self._cache_lock:
                            self._note_cache[key] = sound

        threading.Thread(target=_work, daemon=True).start()

    def _get_bass_sound(self, midi: int, accent: bool, waveform: str = 'saw') -> pygame.Sound:
        key = (midi, accent, waveform)
        with self._cache_lock:
            cached = self._note_cache.get(key)
        if cached is not None:
            return cached
        # Not cached yet – generate inline (rare after warm-up)
        sound = _make_bass_note(midi, accent, self._step_secs, waveform)
        with self._cache_lock:
            self._note_cache[key] = sound
        return sound

    # ── Sequencer ─────────────────────────────────────────────────────────────

    def _evolve(self) -> None:
        """Called at the end of each bar to evolve the patterns."""
        self._bar += 1
        self._drum_pattern = _gen_drum_pattern(self._rng, self._bar)

        # Shift root note every 8 bars for tonal movement
        if self._bar % 8 == 0:
            self._root_idx = (self._root_idx + 1) % len(_ROOT_SHIFTS)
            self._root = 36 + _ROOT_SHIFTS[self._root_idx]
            self._pregenerate_async(self._root)

        # New bass patterns every 8 bars (was 2) – let each phrase breathe
        if self._bar % 8 == 0:
            self._bass_pattern = _gen_bass_pattern(self._root, self._rng)
            self._bass_pattern2 = _gen_bass_pattern(self._root, self._rng)

        # Subtle BPM drift every 16 bars (±3 BPM) – keeps it alive
        if self._bar % 16 == 0:
            self._bpm = BPM_BASE + self._rng.randint(-3, 3)
            self._step_secs = 60.0 / (self._bpm * 4)

    def _play_step(self, step: int) -> None:
        dp = self._drum_pattern
        if dp["kick"][step]:
            self._ch_kick.play(self._kick)
        if dp["snare"][step]:
            self._ch_snare.play(self._snare)
        if dp["hihat"][step]:
            self._ch_hihat.play(self._hihat)
        if dp["openhat"][step]:
            self._ch_hihat.play(self._openhat)

        # Voice 1 – sawtooth 303
        bp = self._bass_pattern[step]
        if bp is not None:
            midi, accent = bp
            self._ch_bass.play(self._get_bass_sound(midi, accent, 'saw'))

        # Voice 2 – square-wave 303 (complementary pattern, panned right)
        bp2 = self._bass_pattern2[step]
        if bp2 is not None:
            midi2, accent2 = bp2
            self._ch_bass2.play(self._get_bass_sound(midi2, accent2, 'square'))

    def tick(self, dt: float) -> None:
        """Advance the sequencer by *dt* seconds.  Call once per game frame."""
        if not self._enabled:
            return
        self._time_acc += dt
        while self._time_acc >= self._step_secs:
            self._time_acc -= self._step_secs
            self._play_step(self._step)
            self._step += 1
            if self._step >= STEPS_PER_BAR:
                self._step = 0
                self._evolve()

    def set_volume(self, volume: float) -> None:
        """Set overall music volume.  *volume* is clamped to 0.0–1.0."""
        if not self._enabled:
            return
        v = max(0.0, min(1.0, volume))
        self._ch_kick.set_volume(v)
        self._ch_snare.set_volume(v * 0.90)
        self._ch_hihat.set_volume(v * 0.70)
        self._ch_bass.set_volume(v, v * 0.75)
        self._ch_bass2.set_volume(v * 0.75, v)
