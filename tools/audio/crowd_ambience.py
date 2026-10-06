"""Seamless ambience loops for venues (no recordings): arena murmur / active,
LAN room, awards hall. Each loop is rendered longer than its length and the
overhang is equal-power crossfaded into the head, so it repeats invisibly."""
import json
import zlib
import subprocess
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

import crowd

RATE = crowd.RATE
OVERLAP = 4.0


def seamless(y, length):
    L = int(length * RATE); X = int(OVERLAP * RATE)
    out = y[:, :L].copy()
    ramp = np.linspace(0, 1, X)
    out[:, :X] = y[:, :X] * np.sqrt(ramp) + y[:, L:L + X] * np.sqrt(1 - ramp)
    return out


def keyboard(c: crowd.Crowd, t0, t1, desks=10):
    """Mechanical keyboard bursts and mouse clicks from the players' desks."""
    r = c.rng
    for desk in range(desks):
        pan = -0.8 + 1.6 * desk / max(1, desks - 1)
        t = t0 + r.uniform(0, 2)
        while t < t1:
            burst = r.uniform(0.4, 2.2)
            k = t
            while k < t + burst:
                n = int(0.012 * RATE)
                x = r.normal(0, 1, n) * np.exp(-np.arange(n) / RATE * 600)
                x = sosfilt(butter(2, [1800, 7000], 'band', fs=RATE, output='sos'), x)
                c.place(x, k, pan, 0.010 * r.uniform(0.6, 1.0), 0.55)
                k += r.uniform(0.06, 0.16)
            for _ in range(r.integers(0, 4)):  # mouse clicks
                n = int(0.008 * RATE)
                x = sosfilt(butter(2, [2500, 6000], 'band', fs=RATE, output='sos'), r.normal(0, 1, n)) * np.exp(-np.arange(n) / RATE * 900)
                c.place(x, k + r.uniform(0, 0.8), pan, 0.012, 0.55)
            t += burst + r.uniform(0.8, 4.0)


def small_cheer(c: crowd.Crowd, at, people=4):
    for _ in range(people):
        c.cheer(at + abs(c.rng.normal(0, 0.12)), 0.5)


def applause_swell(c: crowd.Crowd, at, seconds=4.0, people=120, loud=0.6):
    for _ in range(int(people * seconds * 4)):
        t = at + c.rng.uniform(0, seconds)
        w = np.sin(np.pi * (t - at) / seconds)
        if c.rng.random() < w: c.clap(t, loud * (0.4 + 0.6 * w))


def render(name, length, build, room, wet, rms_db):
    total = length + OVERLAP + 0.5
    c = crowd.Crowd(total, seed=zlib.crc32(name.encode()) % 100000)
    build(c, total)
    y = c.finish(room, wet)[:, :int(total * RATE)]
    y = seamless(y, length)
    y *= 10 ** (rms_db / 20) / np.sqrt((y ** 2).mean())
    peak = np.abs(y).max()
    if peak > 0.89: y *= 0.89 / peak
    wav = f'out/{name}.wav'
    wavfile.write(wav, RATE, (y.T * 32767).astype(np.int16))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-c:a', 'libvorbis', '-q:a', '4', f'out/{name}.ogg'], check=True)
    print(name, 'rms', round(float(20 * np.log10(np.sqrt((y ** 2).mean()))), 1), 'peak', round(float(20 * np.log10(np.abs(y).max())), 1))
    return {'id': name, 'seconds': length, 'loop': True}


def arena_murmur(c, total):
    curve = lambda t: 0.16 + 0.05 * np.sin(2 * np.pi * t / 17) + 0.03 * np.sin(2 * np.pi * t / 7.3)
    n = c.n
    c.roar_bed(np.interp(np.arange(n), np.arange(0, n, 441), [curve(k / RATE) for k in range(0, n, 441)]))
    crowd.populate(c, curve, 0, total, cheer_rate=40, chatter_rate=26, whistle_rate=0.15, clap_rate=12)
    for at in (9.0, 27.0):
        applause_swell(c, at, 2.5, 30, 0.4)


def arena_active(c, total):
    curve = lambda t: 0.48 + 0.12 * np.sin(2 * np.pi * t / 13) + 0.06 * np.sin(2 * np.pi * t / 5.1)
    n = c.n
    c.roar_bed(np.interp(np.arange(n), np.arange(0, n, 441), [curve(k / RATE) for k in range(0, n, 441)]))
    crowd.populate(c, curve, 0, total, cheer_rate=55, chatter_rate=10, whistle_rate=0.35, clap_rate=40)
    for at in (6.0, 21.0, 33.0):
        applause_swell(c, at, 3.0, 90, 0.7)


def lan_room(c, total):
    curve = lambda t: 0.12 + 0.04 * np.sin(2 * np.pi * t / 11)
    crowd.populate(c, curve, 0, total, cheer_rate=0, chatter_rate=9, whistle_rate=0, clap_rate=0)
    keyboard(c, 0, total)
    for at in (8.5, 21.0):
        small_cheer(c, at, 4)


def awards_hall(c, total):
    curve = lambda t: 0.14 + 0.04 * np.sin(2 * np.pi * t / 19)
    crowd.populate(c, curve, 0, total, cheer_rate=0, chatter_rate=22, whistle_rate=0, clap_rate=4)
    for at in (12.0, 31.0):
        applause_swell(c, at, 3.5, 60, 0.45)


if __name__ == '__main__':
    specs = {
        'crowd_arena_murmur': (40, arena_murmur, 2.6, 0.55, -24),
        'crowd_arena_active': (40, arena_active, 2.6, 0.55, -21),
        'crowd_lan_room': (30, lan_room, 0.7, 0.3, -30),
        'crowd_awards_hall': (40, awards_hall, 1.8, 0.45, -28),
    }
    names = sys.argv[1:] or list(specs)
    manifest = [render(n, *specs[n]) for n in names]
    print(json.dumps(manifest))
