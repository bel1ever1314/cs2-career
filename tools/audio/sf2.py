"""Minimal SoundFont 2 renderer (numpy).

Parses an .sf2 bank and renders note events with the parts of the SF2 voice
model that matter for clean, natural playback: key/velocity zones, preset and
instrument generator layering, root key / tuning, sample loops, the volume
envelope, initial attenuation, pan, a static low-pass filter (including the
default velocity-to-cutoff modulator) and exclusive classes (hi-hat choke).
Modulation envelopes, LFOs and chorus are not modelled.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

import numpy as np
from scipy.signal import lfilter

RATE = 44100

GEN_DEFAULTS = {
    8: 13500,      # initialFilterFc (absolute cents)
    9: 0,          # initialFilterQ (cB)
    17: 0,         # pan
    33: -12000, 34: -12000, 35: -12000, 36: -12000,  # vol env delay/attack/hold/decay
    37: 0,         # sustainVolEnv (cB attenuation)
    38: -12000,    # releaseVolEnv
    39: 0, 40: 0,  # keynumToVolEnvHold/Decay
    48: 0,         # initialAttenuation
    51: 0, 52: 0,  # coarse/fine tune
    54: 0,         # sampleModes
    56: 100,       # scaleTuning
    57: 0,         # exclusiveClass
    58: -1,        # overridingRootKey
    0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 12: 0, 45: 0, 50: 0,
}
RANGE_GENS = (43, 44)
# Generators that may not be used at preset level (sample addressing etc.).
INSTRUMENT_ONLY = {0, 1, 2, 3, 4, 12, 45, 50, 54, 57, 58}


@dataclass
class Sample:
    name: str
    start: int
    end: int
    loop_start: int
    loop_end: int
    rate: int
    pitch: int
    correction: int
    kind: int


@dataclass
class Zone:
    gens: dict = field(default_factory=dict)
    key: tuple = (0, 127)
    vel: tuple = (0, 127)


def _chunks(data: bytes, offset: int, end: int):
    while offset < end:
        cid = data[offset:offset + 4].decode('latin1')
        size = struct.unpack_from('<I', data, offset + 4)[0]
        yield cid, offset + 8, size
        offset += 8 + size + (size & 1)


class SoundFont:
    def __init__(self, path: str):
        data = open(path, 'rb').read()
        assert data[:4] == b'RIFF' and data[8:12] == b'sfbk'
        pdta = {}
        for cid, off, size in _chunks(data, 12, len(data)):
            if cid != 'LIST':
                continue
            kind = data[off:off + 4]
            for sub, soff, ssize in _chunks(data, off + 4, off + size):
                if kind == b'sdta' and sub == 'smpl':
                    raw = np.frombuffer(data, dtype='<i2', count=ssize // 2, offset=soff)
                    self.samples_pcm = raw.astype(np.float32) / 32768.0
                elif kind == b'pdta':
                    pdta[sub] = data[soff:soff + ssize]
        self._parse(pdta)
        self._cache = {}

    def _parse(self, p: dict) -> None:
        def rows(name, fmt):
            size = struct.calcsize(fmt)
            blob = p[name]
            return [struct.unpack_from(fmt, blob, i) for i in range(0, len(blob), size)]

        phdr = rows('phdr', '<20sHHHIII')
        pbag = rows('pbag', '<HH')
        pgen = rows('pgen', '<HH')
        inst = rows('inst', '<20sH')
        ibag = rows('ibag', '<HH')
        igen = rows('igen', '<HH')
        shdr = rows('shdr', '<20sIIIIIBbHH')
        self.samples = [Sample(r[0].split(b'\0')[0].decode('latin1'), *r[1:8], r[9]) for r in shdr[:-1]]

        def zones(bags, gens, bag_start, bag_end, terminal):
            out_global, out = None, []
            for b in range(bag_start, bag_end):
                g0, g1 = bags[b][0], bags[b + 1][0]
                zone = Zone()
                for oper, amount in gens[g0:g1]:
                    if oper in RANGE_GENS:
                        lo, hi = amount & 0xFF, amount >> 8
                        if oper == 43: zone.key = (lo, hi)
                        else: zone.vel = (lo, hi)
                    elif oper in (41, 53):
                        zone.gens[oper] = amount
                    else:
                        zone.gens[oper] = amount - 65536 if amount >= 32768 else amount
                if terminal in zone.gens:
                    out.append(zone)
                elif b == bag_start:
                    out_global = zone
            return out_global, out

        self.instruments = []
        for i in range(len(inst) - 1):
            self.instruments.append(zones(ibag, igen, inst[i][1], inst[i + 1][1], 53))
        self.presets = {}
        for i in range(len(phdr) - 1):
            name, preset, bank, bag = phdr[i][:4]
            self.presets[(bank, preset)] = (name.split(b'\0')[0].decode('latin1'),
                                            zones(pbag, pgen, bag, phdr[i + 1][3], 41))

    def preset_name(self, bank: int, program: int) -> str:
        return self.presets[(bank, program)][0]

    def voices(self, bank: int, program: int, key: int, vel: int) -> list:
        """Merged generator dicts + sample for every zone that sounds."""
        cache_key = (bank, program, key, vel)
        if cache_key in self._cache:
            return self._cache[cache_key]
        if (bank, program) not in self.presets:
            bank = 128 if bank == 128 else 0
            if (bank, program) not in self.presets:
                program = 0
        _, (pglobal, pzones) = self.presets[(bank, program)]
        result = []
        for pz in pzones:
            if not (pz.key[0] <= key <= pz.key[1] and pz.vel[0] <= vel <= pz.vel[1]):
                continue
            iglobal, izones = self.instruments[pz.gens[41]]
            for iz in izones:
                if not (iz.key[0] <= key <= iz.key[1] and iz.vel[0] <= vel <= iz.vel[1]):
                    continue
                g = dict(GEN_DEFAULTS)
                if iglobal: g.update(iglobal.gens)
                g.update(iz.gens)
                for src in (pglobal, pz):
                    if not src: continue
                    for oper, amount in src.gens.items():
                        if oper in INSTRUMENT_ONLY or oper in (41, 53): continue
                        g[oper] = g.get(oper, 0) + amount
                result.append((g, self.samples[iz.gens[53]]))
        self._cache[cache_key] = result
        return result


def _tc(value: float) -> float:
    """Timecents to seconds."""
    return 0.0 if value <= -12000 else 2.0 ** (value / 1200.0)


def _lowpass(signal: np.ndarray, cutoff: float, q_cb: float) -> np.ndarray:
    cutoff = min(cutoff, RATE * 0.45)
    w = 2 * np.pi * cutoff / RATE
    q = max(0.5, 10 ** (q_cb / 200.0) * 0.7071)
    alpha = np.sin(w) / (2 * q)
    cos = np.cos(w)
    b = np.array([(1 - cos) / 2, 1 - cos, (1 - cos) / 2])
    a = np.array([1 + alpha, -2 * cos, 1 - alpha])
    return lfilter(b / a[0], a / a[0], signal)


def render_voice(sf: SoundFont, g: dict, s: Sample, key: int, vel: int, seconds: float,
                 cut_at: float | None = None, max_release: float = 4.0) -> tuple[np.ndarray, float]:
    """Mono voice and its pan (-1..1). seconds = held duration."""
    start = s.start + g[0] + 32768 * g[4]
    end = s.end + g[1] + 32768 * g[12]
    loop_start = s.loop_start + g[2] + 32768 * g[45]
    loop_end = s.loop_end + g[3] + 32768 * g[50]
    root = g[58] if g[58] >= 0 else s.pitch
    if g.get(46, -1) >= 0 and 46 in g: key_for_pitch = g[46]
    else: key_for_pitch = key
    cents = (key_for_pitch - root) * g[56] + g[51] * 100 + g[52] + s.correction
    step = 2.0 ** (cents / 1200.0) * s.rate / RATE

    delay, attack = _tc(g[33]), _tc(g[34])
    hold = _tc(g[35] + g[39] * (60 - key))
    decay = _tc(g[36] + g[40] * (60 - key))
    sustain_db = -min(1440, max(0, g[37])) / 10.0
    release = min(max_release, max(0.006, _tc(g[38])))
    if cut_at is not None and cut_at < seconds:
        seconds, release = cut_at, min(release, 0.06)
    total = seconds + release
    n = int(total * RATE) + 1
    looping = g[54] in (1, 3) and loop_end > loop_start + 4

    pos = np.arange(n, dtype=np.float64) * step
    length = end - start
    if looping:
        ls, le = loop_start - start, loop_end - start
        over = pos >= le
        pos[over] = ls + np.mod(pos[over] - ls, le - ls)
        valid = n
    else:
        valid = int(min(n, np.searchsorted(pos, length - 1)))
        pos = pos[:valid]
    if valid <= 1:
        return np.zeros(1, np.float32), 0.0
    pcm = sf.samples_pcm[start:end + 2]
    i0 = pos.astype(np.int64)
    frac = (pos - i0).astype(np.float32)
    i0 = np.clip(i0, 0, len(pcm) - 2)
    out = pcm[i0] * (1 - frac) + pcm[i0 + 1] * frac

    # Volume envelope in dB, then release in dB from the level reached.
    t = np.arange(valid, dtype=np.float64) / RATE
    env_db = np.full(valid, sustain_db)
    a0, a1 = delay, delay + attack
    h1 = a1 + hold
    d1 = h1 + decay
    env_db[t < a0] = -100.0
    att = (t >= a0) & (t < a1)
    if attack > 0:
        lin = np.maximum((t[att] - a0) / attack, 1e-5)
        env_db[att] = 20 * np.log10(lin)
    env_db[(t >= a1) & (t < h1)] = 0.0
    dec = (t >= h1) & (t < d1)
    if decay > 0:
        # SF2 decay: time to fall 100 dB; it stops at the sustain level.
        env_db[dec] = np.maximum(-100.0 * (t[dec] - h1) / decay, sustain_db)
    rel = t >= seconds
    if rel.any():
        idx = min(int(seconds * RATE), valid - 1)
        level = env_db[idx]
        env_db[rel] = level - 100.0 * (t[rel] - seconds) / release
    amp = 10 ** (np.maximum(env_db, -100.0) / 20.0)
    out = out * amp

    # Default velocity modulators: concave attenuation and darker low velocities.
    vel_db = 40.0 * np.log10(max(vel, 1) / 127.0)
    atten_db = -0.4 * g[48] / 10.0  # FluidSynth-compatible EMU scaling
    out = out * 10 ** ((vel_db + atten_db) / 20.0)
    fc = g[8] - 2400 * (1 - vel / 127.0)
    if fc < 13400:
        out = _lowpass(out, 8.176 * 2 ** (fc / 1200.0), g[9])
    pan = max(-500, min(500, g[17])) / 500.0
    return out.astype(np.float32), pan


@dataclass
class Note:
    beat: float      # start in beats
    dur: float       # duration in beats
    key: int
    vel: int


def render_part(sf: SoundFont, bank: int, program: int, notes: list, bpm: float,
                total_seconds: float, humanize_ms: float = 0.0, seed: int = 0,
                max_release: float = 4.0) -> np.ndarray:
    """Stereo float buffer for one instrument part."""
    rng = np.random.default_rng(seed)
    spb = 60.0 / bpm
    buf = np.zeros((2, int(total_seconds * RATE) + RATE * 6), np.float32)
    # Exclusive classes: a later note in the same class cuts the earlier one.
    events = sorted(notes, key=lambda n: n.beat)
    starts = []
    for note in events:
        jitter = rng.normal(0, humanize_ms / 1000.0) if humanize_ms else 0.0
        starts.append(max(0.0, note.beat * spb + jitter))
    classes = []
    for note in events:
        vs = sf.voices(bank, program, note.key, note.vel)
        classes.append(max([g[57] for g, _ in vs] or [0]))
    for i, note in enumerate(events):
        t0 = starts[i]
        cut = None
        if classes[i]:
            for j in range(i + 1, len(events)):
                if classes[j] == classes[i] and starts[j] > t0:
                    cut = starts[j] - t0
                    break
        for g, s in sf.voices(bank, program, note.key, note.vel):
            mono, pan = render_voice(sf, g, s, note.key, note.vel, note.dur * spb, cut, max_release)
            a = int(t0 * RATE)
            b = min(buf.shape[1], a + len(mono))
            if b <= a: continue
            left = np.cos((pan + 1) * np.pi / 4)
            right = np.sin((pan + 1) * np.pi / 4)
            buf[0, a:b] += mono[:b - a] * left
            buf[1, a:b] += mono[:b - a] * right
    return buf


def reverb(stereo: np.ndarray, room: float = 0.82, damp: float = 0.35, width: int = 23) -> np.ndarray:
    """Convolution with a synthetic hall impulse (decaying, darkening stereo noise).

    room 0..1 maps to an RT60 of about 1.2-3.2 s; damp sets how fast highs die.
    """
    from scipy.signal import fftconvolve
    rt60 = 1.2 + 2.5 * max(0.0, room - 0.7) / 0.25
    n = int(rt60 * RATE)
    rng = np.random.default_rng(5)
    t = np.arange(n) / RATE
    out = []
    for ch in range(2):
        noise = rng.normal(0, 1, n)
        # Split into low/high bands with different decay rates (air absorption).
        low = lfilter([0.08], [1, -0.92], noise)
        high = noise - low
        decay_low = np.exp(-6.9 * t / rt60)
        decay_high = np.exp(-6.9 * t / (rt60 * (0.5 - 0.4 * damp)))
        ir = low * decay_low * 1.6 + high * decay_high * 0.3
        pre = int(0.018 * RATE) + ch * width
        ir = np.concatenate([np.zeros(pre), ir])
        # A few early reflections.
        for d, g in ((0.011, 0.5), (0.019, 0.35), (0.027, 0.28), (0.041, 0.2)):
            k = int((d + ch * 0.003) * RATE)
            ir[k] += g * (1 if ch == 0 else -1)
        ir /= np.sqrt(np.sum(ir ** 2))
        out.append(fftconvolve(stereo[ch], ir)[:stereo.shape[1]] * 0.6)
    return np.array(out, np.float32)
