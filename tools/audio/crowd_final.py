"""Crowd stem for 08 决赛开场 v3 — same timeline, separate file."""
import numpy as np, json, subprocess
from scipy.io import wavfile
import crowd

SPB = 60 / 128
BAR = lambda b: b * 4 * SPB
TOTAL = 43.885
BRAAMS = [BAR(b) for b in (2, 4, 6, 8)]
GATE0, DROP = BAR(10) - SPB, BAR(10)
HITS = [BAR(14), BAR(18)]
FINAL = BAR(21)


def curve(t):
    i = 0.22
    for b in BRAAMS:  # "ooh" swell after each braam
        if t >= b: i += 0.16 * np.exp(-(t - b) / 1.3)
    if t >= BAR(6): i += 0.55 * min(1, (t - BAR(6)) / (GATE0 - BAR(6))) ** 1.6
    if GATE0 <= t < DROP: i = 0.95
    if t >= DROP:
        i = 0.78 + 0.22 * np.exp(-(t - DROP) / 1.5)
        for h in HITS:
            if t >= h: i += 0.12 * np.exp(-(t - h) / 1.2)
        i += 0.04 * np.sin(2 * np.pi * t / 5.3)
    if t >= FINAL:
        i = 0.6 + 0.4 * np.exp(-(t - FINAL) / 2.2)
    return float(np.clip(i, 0, 1))


c = crowd.Crowd(TOTAL, seed=4)
n = c.n
curve_arr = np.array([curve(k / crowd.RATE) for k in range(0, n, 441)])
inten = np.interp(np.arange(n), np.arange(0, n, 441), curve_arr)
c.roar_bed(inten)
crowd.populate(c, curve, 0, TOTAL - 0.5, whistle_rate=0.6)
# Big reactions: a burst of extra cheers on the drop, the impacts and the final hit.
for at, k in [(DROP, 110), (HITS[0], 40), (HITS[1], 50), (FINAL, 130)]:
    for _ in range(k):
        c.cheer(at + abs(c.rng.normal(0, 0.15)), 1.1)
# Stadium claps on every beat through bars 15-17, everyone slightly late.
for beat in range(15 * 4, 18 * 4):
    for _ in range(140):
        c.clap(beat * SPB + abs(c.rng.normal(0.03, 0.025)), 1.0)
# Group "hey!" on the last beat of bars 15, 16, 17.
for b in (15, 16, 17):
    c.shout(BAR(b) + 3 * SPB + 0.02, 70, 1.1)
# Applause after the final hit.
for _ in range(2600):
    t = FINAL + 0.25 + c.rng.exponential(1.4)
    if t < TOTAL - 0.3: c.clap(t, 0.9)
y = c.finish(2.6, 0.5)[:, :int(TOTAL * crowd.RATE)]
fade = int(1.5 * crowd.RATE); y[:, -fade:] *= np.linspace(1, 0, fade)
rms = np.sqrt((y ** 2).mean()); y *= 10 ** (-20 / 20) / rms
peak = np.abs(y).max()
if peak > 0.89: y *= 0.89 / peak
wavfile.write('out/major_final_v3_crowd.wav', crowd.RATE, (y.T * 32767).astype(np.int16))
print('peak', 20 * np.log10(np.abs(y).max()), 'rms', 20 * np.log10(np.sqrt((y ** 2).mean())))
