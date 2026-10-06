"""Tiny composition helpers: pitches, chords, voicings, melodies, grooves, mixing."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.io import wavfile

import sf2
from sf2 import Note, RATE

PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
CHORDS = {
    '': [0, 4, 7], 'm': [0, 3, 7], 'maj7': [0, 4, 7, 11], 'm7': [0, 3, 7, 10], '7': [0, 4, 7, 10],
    '7sus4': [0, 5, 7, 10], 'sus4': [0, 5, 7], 'sus2': [0, 2, 7], 'm6': [0, 3, 7, 9], '6': [0, 4, 7, 9],
    'dim7': [0, 3, 6, 9], 'm7b5': [0, 3, 6, 10], 'maj9': [0, 4, 7, 11, 14], 'm9': [0, 3, 7, 10, 14],
    'add9': [0, 4, 7, 14], '9': [0, 4, 7, 10, 14], '13': [0, 4, 10, 14, 21], '5': [0, 7],
}


def pc(name: str) -> int:
    value = PC[name[0]]
    for ch in name[1:]:
        value += 1 if ch == '#' else -1 if ch == 'b' else 0
    return value % 12


def pitch(text: str) -> int:
    i = 1
    while i < len(text) and text[i] in '#b':
        i += 1
    return 12 * (int(text[i:]) + 1) + pc(text[:i])


def parse_chord(symbol: str) -> tuple[int, list[int], int]:
    bass = None
    if '/' in symbol:
        symbol, bass_name = symbol.split('/')
        bass = pc(bass_name)
    i = 1
    while i < len(symbol) and symbol[i] in '#b':
        i += 1
    root = pc(symbol[:i])
    return root, CHORDS[symbol[i:]], root if bass is None else bass


def voicing(symbol: str, lo: int, hi: int, prev: list[int] | None = None, size: int = 4) -> list[int]:
    """Close voicing inside [lo, hi] that moves least from prev."""
    root, intervals, _ = parse_chord(symbol)
    pcs = [(root + i) % 12 for i in intervals]
    if len(pcs) > size:  # drop the fifth first for big chords
        fifth = (root + 7) % 12
        if fifth in pcs: pcs.remove(fifth)
    pcs = pcs[:size]
    candidates = []
    for base in range(lo, hi):
        if base % 12 not in pcs: continue
        notes = [base]
        for p in pcs:
            if p == base % 12: continue
            n = base + ((p - base) % 12)
            notes.append(n)
        notes.sort()
        if notes[-1] <= hi:
            candidates.append(notes)
    if not candidates:
        return [lo + ((p - lo) % 12) for p in pcs]
    if not prev:
        centre = (lo + hi) / 2
        return min(candidates, key=lambda c: abs(np.mean(c) - centre))
    return min(candidates, key=lambda c: sum(min(abs(a - b) for b in prev) for a in c))


def bass_note(symbol: str, octave_lo: int = 36) -> int:
    _, _, b = parse_chord(symbol)
    return octave_lo + ((b - octave_lo) % 12)


def chord_tone(symbol: str, degree: int, octave_lo: int) -> int:
    root, intervals, _ = parse_chord(symbol)
    p = (root + intervals[degree % len(intervals)]) % 12
    return octave_lo + ((p - octave_lo) % 12)


def melody(text: str, start: float, vel: int = 90, legato: float = 0.92) -> list[Note]:
    """'E5:1 r:.5 G5:.5 ...'; '|' separators are ignored. '!' accents, '_' soft."""
    notes, beat = [], start
    for tok in text.replace('|', ' ').split():
        name, dur = tok.split(':')
        d = float(dur)
        if name != 'r':
            v = vel
            if name.endswith('!'): name, v = name[:-1], min(127, vel + 14)
            elif name.endswith('_'): name, v = name[:-1], max(1, vel - 18)
            notes.append(Note(beat, d * legato, pitch(name), v))
        beat += d
    return notes


def swing(notes: list[Note], ratio: float = 0.58, grid: float = 0.5) -> list[Note]:
    """Delay off-beat eighths (grid .5) or sixteenths (grid .25)."""
    out = []
    for n in notes:
        cell = n.beat / (grid * 2)
        frac = cell - np.floor(cell)
        if abs(frac - 0.5) < 1e-6:
            shift = (ratio - 0.5) * grid * 2
            n = Note(n.beat + shift, max(0.05, n.dur - shift), n.key, n.vel)
        out.append(n)
    return out


DRUM = {'kick': 36, 'snare': 38, 'stick': 37, 'clap': 39, 'swirl': 40, 'hat': 42, 'pedal': 44, 'open': 46,
        'ride': 51, 'bell': 53, 'crash': 49, 'shaker': 70, 'tamb': 54, 'lotom': 45, 'midtom': 47, 'hitom': 50,
        'tri': 81, 'cowbell': 56, 'snare2': 40, 'cabasa': 69, 'block': 76}
VEL = {'X': 118, 'x': 96, 'o': 72, 'g': 44, 'h': 58}


def groove(pattern: dict, bar: int, beats: int = 4, steps: int = 16, scale: float = 1.0) -> list[Note]:
    out = []
    step_len = beats / steps
    for name, row in pattern.items():
        row = row.replace(' ', '')
        for i, ch in enumerate(row):
            if ch in VEL:
                out.append(Note(bar * beats + i * step_len, step_len * 0.9, DRUM.get(name, name) if isinstance(name, str) else name,
                                int(VEL[ch] * scale)))
    return out


def jitter_vel(notes: list[Note], amount: int, rng) -> list[Note]:
    return [Note(n.beat, n.dur, n.key, int(np.clip(n.vel + rng.integers(-amount, amount + 1), 1, 127))) for n in notes]


@dataclass
class Part:
    name: str
    bank: int
    program: int
    gain_db: float = 0.0
    pan: float = 0.0
    reverb: float = 0.2
    humanize_ms: float = 6.0
    notes: list = field(default_factory=list)
    max_release: float = 4.0
    drive: float = 0.0

    def add(self, notes):
        self.notes.extend(notes)
        return self


@dataclass
class Song:
    id: str
    title: str
    bpm: float
    bars: int
    beats_per_bar: int = 4
    parts: list = field(default_factory=list)
    loop: bool = True
    tail: float = 6.0
    target_rms_db: float = -20.0
    reverb_room: float = 0.82
    reverb_damp: float = 0.35
    extra: list = field(default_factory=list)  # (stereo buffer, start_seconds)
    length_seconds: float | None = None
    gates: list = field(default_factory=list)
    eq: tuple = (0.0, 0.0)  # (low shelf dB @120 Hz, high shelf dB @3.5 kHz)  # (start_s, end_s) full mutes (suck-back)

    def part(self, *args, **kw) -> Part:
        p = Part(*args, **kw)
        self.parts.append(p)
        return p

    @property
    def seconds(self) -> float:
        if self.length_seconds is not None: return self.length_seconds
        return self.bars * self.beats_per_bar * 60.0 / self.bpm


def shelf(x, f0, gain_db, high):
    from scipy.signal import lfilter
    if not gain_db: return x
    A = 10 ** (gain_db / 40); w = 2 * np.pi * f0 / RATE; cw, sw = np.cos(w), np.sin(w)
    alpha = sw / 2 * np.sqrt(2)
    s = 1 if high else -1
    b0 = A * ((A + 1) + s * (A - 1) * cw + 2 * np.sqrt(A) * alpha)
    b1 = -2 * s * A * ((A - 1) + s * (A + 1) * cw)
    b2 = A * ((A + 1) + s * (A - 1) * cw - 2 * np.sqrt(A) * alpha)
    a0 = (A + 1) - s * (A - 1) * cw + 2 * np.sqrt(A) * alpha
    a1 = 2 * s * ((A - 1) - s * (A + 1) * cw)
    a2 = (A + 1) - s * (A - 1) * cw - 2 * np.sqrt(A) * alpha
    return lfilter([b0 / a0, b1 / a0, b2 / a0], [1, a1 / a0, a2 / a0], x)


def loudness(stereo: np.ndarray) -> float:
    from scipy.signal import butter, sosfilt
    mono = stereo.mean(axis=0)
    sos = butter(2, [150, 6000], 'bandpass', fs=RATE, output='sos')
    w = sosfilt(sos, mono)
    win = int(0.4 * RATE)
    frames = len(w) // win
    if frames == 0: return -100.0
    e = np.sqrt(np.mean(w[:frames * win].reshape(frames, win) ** 2, axis=1))
    active = e[e > e.max() * 0.05]
    if len(active) == 0: return -100.0
    top = np.sort(active)[len(active) // 2:]
    return float(20 * np.log10(np.sqrt(np.mean(top ** 2)) + 1e-12))


def _pan(stereo: np.ndarray, pan: float) -> np.ndarray:
    if not pan: return stereo
    left = np.cos((pan + 1) * np.pi / 4) * np.sqrt(2)
    right = np.sin((pan + 1) * np.pi / 4) * np.sqrt(2)
    return np.array([stereo[0] * min(1, left), stereo[1] * min(1, right)])


def render(song: Song, sf: sf2.SoundFont, out_dir: Path, seed: int = 1) -> dict:
    total = song.seconds + song.tail
    n = int(total * RATE) + RATE * 6
    dry = np.zeros((2, n), np.float32)
    send = np.zeros((2, n), np.float32)
    stats = {}
    for i, part in enumerate(song.parts):
        buf = sf2.render_part(sf, part.bank, part.program, part.notes, song.bpm, total, part.humanize_ms,
                              seed + i * 17, part.max_release)[:, :n]
        # gain_db is a loudness target relative to the lead (0 dB): measure the
        # part's weighted active RMS and scale it there, so balance does not
        # depend on how loud each SoundFont preset happens to be.
        if part.drive:
            peak = np.abs(buf).max() + 1e-9
            buf = np.tanh(part.drive * buf / peak) * peak / np.tanh(part.drive)
        level = loudness(buf)
        buf = _pan(buf, part.pan) * 10 ** ((part.gain_db - 20 - level) / 20)
        dry[:, :buf.shape[1]] += buf
        send[:, :buf.shape[1]] += buf * part.reverb
        stats[part.name] = {'notes': len(part.notes), 'preset': sf.preset_name(part.bank, part.program),
                            'peak_db': round(float(20 * np.log10(np.abs(buf).max() + 1e-9)), 1)}
    for item in song.extra:
        buf, at = item[0], item[1]
        amount = item[2] if len(item) > 2 else 0.3
        a = int(at * RATE); b = min(n, a + buf.shape[1])
        if b <= a: continue
        dry[:, a:b] += buf[:, :b - a]
        send[:, a:b] += buf[:, :b - a] * amount
    wet = sf2.reverb(send, song.reverb_room, song.reverb_damp)
    mix = dry + wet * 1.0
    for g0, g1 in song.gates:
        a, b = int(g0 * RATE), int(g1 * RATE)
        ramp = int(0.012 * RATE)
        env = np.ones(mix.shape[1], np.float32)
        env[a:b] = 0
        env[max(0, a - ramp):a] = np.linspace(1, 0, a - max(0, a - ramp))
        mix *= env
    L = int(round(song.seconds * RATE))
    if song.loop:
        T = n - L
        out = mix[:, :L].copy()
        out[:, :T] += mix[:, L:L + T]
    else:
        end = int((song.seconds + song.tail) * RATE)
        out = mix[:, :end].copy()
        fade = int(0.5 * RATE)
        out[:, -fade:] *= np.linspace(1, 0, fade)
    if any(song.eq):
        out = np.array([shelf(shelf(ch, 120, song.eq[0], False), 3500, song.eq[1], True) for ch in out], np.float32)
    # Level: target RMS, then a soft limiter keeps peaks under -1 dBFS.
    rms = np.sqrt(np.mean(out ** 2)) + 1e-9
    out *= 10 ** (song.target_rms_db / 20) / rms
    ceiling = 10 ** (-1 / 20)
    out = np.where(np.abs(out) > 0.7 * ceiling,
                   np.sign(out) * (0.7 * ceiling + 0.3 * ceiling * np.tanh((np.abs(out) - 0.7 * ceiling) / (0.3 * ceiling))),
                   out)
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f'{song.id}.wav'
    wavfile.write(wav, RATE, (out.T * 32767).astype(np.int16))
    ogg = out_dir / f'{song.id}.ogg'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(wav), '-c:a', 'libvorbis', '-q:a', '5', str(ogg)], check=True)
    info = {'id': song.id, 'title': song.title, 'bpm': song.bpm, 'bars': song.bars, 'loop': song.loop,
            'seconds': round(out.shape[1] / RATE, 3),
            'peak_dbfs': round(float(20 * np.log10(np.abs(out).max())), 2),
            'rms_dbfs': round(float(20 * np.log10(np.sqrt(np.mean(out ** 2)))), 2), 'parts': stats}
    return info
