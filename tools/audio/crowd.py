"""Synthetic arena crowd (no recordings): babble, cheers, whistles, claps, shouts.

Voices are glottal pulse trains through three vowel formants; a crowd is
thousands of short voiced events placed by an intensity curve, on top of a
formant-coloured roar bed, then put in a big room.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

RATE = 44100
VOWELS = {  # F1, F2, F3 (Hz)
    'a': (800, 1200, 2600), 'o': (500, 900, 2500), 'u': (350, 800, 2300),
    'e': (550, 1800, 2600), 'i': (330, 2200, 2900), 'ae': (700, 1700, 2600),
}
_SOS = {}


def _band(f, q):
    key = (int(f), q)
    if key not in _SOS:
        bw = f / q
        _SOS[key] = butter(1, [max(40, f - bw / 2), min(RATE / 2 - 100, f + bw / 2)], 'band', fs=RATE, output='sos')
    return _SOS[key]


def voice(seconds, f0_curve, vowel_from, vowel_to, rng, breath=0.15):
    """One voiced event. f0_curve: array len n (Hz)."""
    n = len(f0_curve)
    jitter = 1 + 0.012 * np.cumsum(rng.normal(0, 1, n)) / np.sqrt(np.arange(1, n + 1))
    vib = 1 + 0.02 * np.sin(2 * np.pi * rng.uniform(4.5, 6.5) * np.arange(n) / RATE)
    f0 = f0_curve * jitter * vib
    phase = np.cumsum(f0) / RATE
    saw = 2 * (phase % 1.0) - 1
    src = np.diff(np.concatenate([[0], saw])) * -1  # pulse-like, bright source
    src = sosfilt(butter(1, 120, 'high', fs=RATE, output='sos'), saw * 0.3 + src * 3)
    src += rng.normal(0, breath, n)
    def formants(v):
        return sum(sosfilt(_band(f, 5 + 3 * k), src) * g for k, (f, g) in enumerate(zip(VOWELS[v], (1.0, 0.6, 0.25))))
    out = formants(vowel_from)
    if vowel_to != vowel_from:
        mix = np.linspace(0, 1, n)
        out = out * (1 - mix) + formants(vowel_to) * mix
    return out


def envelope(n, attack, release):
    t = np.arange(n) / RATE
    dur = n / RATE
    return np.minimum(1, t / attack) * np.minimum(1, np.maximum(0, (dur - t) / release))


class Crowd:
    def __init__(self, seconds, seed=1):
        self.n = int(seconds * RATE)
        self.out = np.zeros((2, self.n + RATE * 4))
        self.rng = np.random.default_rng(seed)

    def place(self, mono, at, pan=0.0, gain=1.0, distance=0.5):
        a = int(at * RATE)
        if a >= self.out.shape[1] or a < 0: return
        b = min(self.out.shape[1], a + len(mono))
        # Farther voices are darker and quieter.
        if distance > 0.5:
            mono = sosfilt(butter(1, 5000 - 3200 * (distance - 0.5) * 2, 'low', fs=RATE, output='sos'), mono)
        mono = mono[:b - a] * gain * (1.2 - distance)
        self.out[0, a:b] += mono * np.cos((pan + 1) * np.pi / 4)
        self.out[1, a:b] += mono * np.sin((pan + 1) * np.pi / 4)

    # --- event types
    def cheer(self, at, loud=1.0):
        r = self.rng
        dur = r.uniform(0.7, 2.6)
        n = int(dur * RATE)
        male = r.random() < 0.7
        base = r.uniform(110, 165) if male else r.uniform(200, 290)
        t = np.linspace(0, 1, n)
        rise = r.uniform(1.25, 1.8)
        contour = base * (1 + (rise - 1) * np.sin(np.pi * np.minimum(1, t * 1.4)) ** 0.7)
        v1, v2 = r.choice([('o', 'u'), ('e', 'a'), ('a', 'a'), ('o', 'o'), ('ae', 'a'), ('u', 'o')])
        x = voice(dur, contour, v1, v2, r) * envelope(n, r.uniform(0.04, 0.25), r.uniform(0.2, 0.7))
        self.place(x, at, r.uniform(-0.9, 0.9), 0.05 * loud, r.uniform(0.3, 1.0))

    def chatter(self, at, loud=1.0):
        r = self.rng
        total = r.uniform(0.6, 2.0)
        t = 0.0
        base = r.uniform(100, 150) if r.random() < 0.65 else r.uniform(190, 260)
        while t < total:
            d = r.uniform(0.08, 0.22)
            n = int(d * RATE)
            contour = base * (1 + 0.15 * np.sin(np.linspace(0, np.pi, n) * r.uniform(0.5, 1.5)))
            vs = list(VOWELS)
            x = voice(d, contour, vs[r.integers(len(vs))], vs[r.integers(len(vs))], r, 0.3) * envelope(n, 0.015, 0.04)
            self.place(x, at + t, r.uniform(-0.9, 0.9), 0.02 * loud, r.uniform(0.6, 1.0))
            t += d + r.uniform(0.02, 0.12)

    def whistle(self, at, loud=1.0):
        r = self.rng
        dur = r.uniform(0.25, 1.1)
        n = int(dur * RATE)
        t = np.arange(n) / RATE
        f0 = r.uniform(1700, 2600)
        kind = r.integers(3)
        if kind == 0: f = f0 * (1 + 0.25 * t / dur)                      # rising
        elif kind == 1: f = f0 * (1 + 0.3 * np.sin(np.pi * t / dur))    # up-down
        else: f = f0 * np.where(t < dur / 2, 1.0, 1.22)                  # two-tone
        f = f * (1 + 0.006 * np.sin(2 * np.pi * 7 * t))
        x = np.sin(2 * np.pi * np.cumsum(f) / RATE) + r.normal(0, 0.08, n)
        x *= envelope(n, 0.02, 0.06)
        self.place(x, at, r.uniform(-0.8, 0.8), 0.012 * loud, r.uniform(0.45, 0.95))

    def clap(self, at, loud=1.0, pan=None, distance=None):
        r = self.rng
        n = int(0.05 * RATE)
        noise = r.normal(0, 1, n)
        c = r.uniform(900, 2200)
        x = sosfilt(butter(2, [c * 0.6, c * 1.6], 'band', fs=RATE, output='sos'), noise)
        x *= np.exp(-np.arange(n) / RATE * r.uniform(70, 120))
        self.place(x, at, r.uniform(-0.9, 0.9) if pan is None else pan, 0.05 * loud,
                   r.uniform(0.2, 1.0) if distance is None else distance)

    def shout(self, at, people=60, loud=1.0):
        """Group 'hey!': many short 'e' vowels on the same instant."""
        r = self.rng
        for _ in range(people):
            d = r.uniform(0.22, 0.38)
            n = int(d * RATE)
            base = r.uniform(120, 190) if r.random() < 0.7 else r.uniform(220, 320)
            contour = base * np.linspace(1.15, 0.9, n)
            x = voice(d, contour, 'e', 'e', r, 0.25) * envelope(n, 0.012, 0.12)
            self.place(x, at + r.normal(0, 0.025), r.uniform(-0.9, 0.9), 0.04 * loud, r.uniform(0.3, 1.0))

    def roar_bed(self, intensity):
        """Formant-coloured noise; intensity: array per sample (0..1)."""
        r = self.rng
        n = len(intensity)
        out = []
        for ch in range(2):
            noise = r.normal(0, 1, n)
            wob = [1 + 0.25 * np.sin(2 * np.pi * (np.arange(n) / RATE) * r.uniform(0.15, 0.6) + r.uniform(0, 6)) for _ in range(3)]
            bed = sum(sosfilt(_band(f, q), noise) * w * g for f, q, w, g in zip((520, 1150, 2600), (2, 3, 4), wob, (1.0, 0.7, 0.3)))
            out.append(bed * intensity ** 1.4 * 0.05)
        self.out[:, :n] += np.array(out)

    def finish(self, room=2.6, wet=0.55):
        n = int(room * RATE)
        rng = np.random.default_rng(9)
        t = np.arange(n) / RATE
        res = []
        for ch in range(2):
            ir = rng.normal(0, 1, n) * np.exp(-6.9 * t / room)
            ir = sosfilt(butter(1, 3000, 'low', fs=RATE, output='sos'), ir)
            ir /= np.sqrt((ir ** 2).sum())
            res.append(self.out[ch] * (1 - wet * 0.5) + fftconvolve(self.out[ch], ir)[:self.out.shape[1]] * wet)
        y = np.array(res)
        return sosfilt(butter(2, 70, 'high', fs=RATE, output='sos'), y)


def populate(c: Crowd, curve, t0=0.0, t1=None, cheer_rate=60, chatter_rate=14, whistle_rate=2.5, clap_rate=40):
    """Spawn events with Poisson rates scaled by curve(t) in [0, 1]."""
    t1 = t1 if t1 is not None else c.n / RATE
    r = c.rng
    t = t0
    dt = 0.02
    while t < t1:
        i = curve(t)
        if r.random() < cheer_rate * i ** 2.2 * dt: c.cheer(t, 0.6 + 0.6 * i)
        if r.random() < chatter_rate * max(0, 0.6 - i) * dt: c.chatter(t, 0.8)
        if r.random() < whistle_rate * i ** 1.5 * dt: c.whistle(t, 0.6 + 0.6 * i)
        if r.random() < clap_rate * i ** 2 * dt: c.clap(t, 0.5 + 0.5 * i)
        t += dt
