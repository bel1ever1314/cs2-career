"""Original sound design layers synthesised in numpy (no samples)."""
import numpy as np
from scipy.signal import butter, sosfilt

RATE = 44100


def _stereo(x, spread=29):
    return np.array([x, np.roll(x, spread)], np.float32)


def sub_boom(seconds=2.2, f_start=90.0, f_end=34.0, gain=0.9):
    n = int(seconds * RATE); t = np.arange(n) / RATE
    f = f_end + (f_start - f_end) * np.exp(-t * 7)
    phase = 2 * np.pi * np.cumsum(f) / RATE
    x = np.sin(phase) * np.exp(-t * 1.6) * gain
    click = np.exp(-t * 300) * np.random.default_rng(1).normal(0, 0.4, n)
    return _stereo(np.tanh(1.6 * x) + click, 0)


def impact(seconds=3.0, gain=1.0, seed=2):
    n = int(seconds * RATE); t = np.arange(n) / RATE
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, n)
    body = sosfilt(butter(2, 900, 'low', fs=RATE, output='sos'), noise) * np.exp(-t * 3.2) * 0.9
    crack = sosfilt(butter(2, 2500, 'high', fs=RATE, output='sos'), noise) * np.exp(-t * 18) * 0.35
    boom = sub_boom(seconds)[0]
    x = (body + crack) * gain + boom * gain
    return np.array([x, np.roll(x, 41) * 0.95 + crack * 0.1], np.float32)


def whoosh(seconds=1.6, seed=3, gain=0.5):
    """Reverse swell that lands on the next downbeat."""
    n = int(seconds * RATE); t = np.arange(n) / RATE
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, n)
    out = np.zeros(n)
    for k in range(12):
        a, b = k * n // 12, (k + 1) * n // 12
        f = 400 + 5000 * (k / 11) ** 2
        out[a:b] = sosfilt(butter(2, [f * 0.6, f * 1.4], 'band', fs=RATE, output='sos'), noise[a:b])
    env = (t / seconds) ** 3
    return _stereo(out * env * gain, 53)


def beep(gain=0.12, freq=1900.0, length=0.07):
    n = int(length * RATE); t = np.arange(n) / RATE
    x = (np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 3 * t)) * np.minimum(1, t / 0.004) * np.exp(-t * 18)
    return _stereo(x * gain, 0)


def reese(notes, bpm, total_seconds, gain=0.5, cutoff=520.0, drive=2.2):
    """Detuned-saw bass. notes: list of (beat, dur_beats, midi)."""
    spb = 60.0 / bpm
    out = np.zeros(int(total_seconds * RATE) + RATE)
    for beat, dur, key in notes:
        f = 440.0 * 2 ** ((key - 69) / 12)
        n = int((dur * spb + 0.06) * RATE); t = np.arange(n) / RATE
        saw = lambda ff, ph: 2 * ((t * ff + ph) % 1.0) - 1
        x = saw(f * 1.006, 0.0) + saw(f * 0.994, 0.37) + 0.6 * saw(f * 2.003, 0.11)
        x = sosfilt(butter(2, cutoff, 'low', fs=RATE, output='sos'), x)
        x += 0.9 * np.sin(2 * np.pi * f * t)  # sub weight under the grit
        env = np.minimum(1, t / 0.006) * np.where(t > dur * spb, np.exp(-(t - dur * spb) * 40), 1.0)
        x = np.tanh(drive * x * env) * gain
        a = int(beat * spb * RATE)
        out[a:a + n] += x[:len(out) - a]
    return _stereo(out, 0)
