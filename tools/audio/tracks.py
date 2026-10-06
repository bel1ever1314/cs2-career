"""Original background music for CS2 Career (home, club, LAN, awards, Major).

Every melody, progression and arrangement here is written for this project.
Instruments are rendered from GeneralUser GS 2.0.3 (see GeneralUser-GS-LICENSE.txt).
"""
from __future__ import annotations

import numpy as np

from mlib import Note, Song, bass_note, chord_tone, groove, jitter_vel, melody, pitch, swing, voicing

RNG = np.random.default_rng(7)


def bars_of(chords: list[str]) -> list[list[tuple[float, str]]]:
    """Each bar entry 'A B' splits the bar in half; returns [(beat_in_bar, symbol)]."""
    out = []
    for entry in chords:
        parts = entry.split()
        step = 4 / len(parts)
        out.append([(i * step, s) for i, s in enumerate(parts)])
    return out


def chord_spans(chords: list[str]):
    """(start_beat, length, symbol) for every chord."""
    for bar, entries in enumerate(bars_of(chords)):
        for i, (b, sym) in enumerate(entries):
            end = entries[i + 1][0] if i + 1 < len(entries) else 4
            yield bar * 4 + b, end - b, sym


# ---------------------------------------------------------------- home day
def home_day() -> Song:
    s = Song('home_day', '小屋的早晨', 92, 32, target_rms_db=-21)
    chords = ['Fmaj7', 'Am7', 'Bbmaj7', 'C7sus4 C7', 'Fmaj7', 'Dm7', 'Gm7', 'C7',
              'Fmaj7', 'Am7', 'Bbmaj7', 'Bbm6', 'Am7', 'D7', 'Gm7 C7', 'F6',
              'Bbmaj7', 'C/Bb', 'Am7', 'Dm7', 'Gm7', 'Am7', 'Bbmaj7', 'C7sus4 C7',
              'Fmaj7', 'Am7', 'Bbmaj7', 'Bbm6', 'Fmaj7/A', 'D7', 'Gm7', 'C7sus4 C7']
    A1 = ('r:.5 C5:.5 F5:.5 A5:.5 G5:1 E5:1 | C5:.5 E5:.5 G5:1 E5:.5 D5:.5 C5:1 | D5:1.5 C5:.5 A4:1 F4:1 | '
          'G4:.5 A4:.5 Bb4:.5 C5:.5 E5:2 | r:.5 C5:.5 F5:.5 A5:.5 C6:1 A5:1 | G5:.5 F5:.5 E5:.5 F5:.5 D5:2 | '
          'Bb4:.5 D5:.5 F5:.5 A5:.5 G5:1 F5:1 | E5:1 D5:.5 C5:.5 Bb4:1 r:1')
    A2 = ('r:.5 C5:.5 F5:.5 A5:.5 G5:1 E5:1 | C5:.5 E5:.5 G5:1 A5:.5 G5:.5 E5:1 | F5:1.5 D5:.5 Bb4:1 A4:1 | '
          'Db5:1.5 C5:.5 Bb4:1 G4:1 | C5:1 E5:1 G5:1.5 F5:.5 | F#5:2 E5:.5 D5:.5 C5:1 | '
          'Bb4:.5 D5:.5 F5:1 E5:.5 G5:.5 Bb5:1 | A5:3 r:1')
    B = ('D6:1.5 C6:.5 A5:2 | G5:1.5 E5:.5 C5:2 | E5:1 G5:1 C6:1 B5:.5 A5:.5 | A5:3 F5:1 | '
         'Bb5:1.5 A5:.5 G5:1 F5:1 | E5:1.5 D5:.5 C5:1 E5:1 | D5:.5 F5:.5 A5:.5 C6:.5 D6:1 C6:1 | '
         'Bb5:1 A5:.5 G5:.5 E5:1 C5:1')
    A3 = ('r:.5 C5:.5 F5:.5 A5:.5 G5:1 E5:1 | C5:.5 E5:.5 G5:1 E5:.5 D5:.5 C5:1 | D5:1.5 C5:.5 A4:1 F4:1 | '
          'Db5:1 F5:1 G5:1.5 F5:.5 | E5:1.5 F5:.5 A5:1 C6:1 | A5:.5 F#5:.5 D5:.5 E5:.5 F#5:1 A5:1 | '
          'G5:1.5 F5:.5 D5:1 Bb4:1 | A4:1 Bb4:1 E5:1 r:1')
    lead = s.part('piano melody', 0, 0, gain_db=-1, pan=0.12, reverb=0.28)
    for i, text in enumerate([A1, A2, B, A3]):
        lead.add(swing(melody(text, i * 32, vel=86), 0.56))
    glock = s.part('glockenspiel', 0, 9, gain_db=-13, pan=0.35, reverb=0.4)
    glock.add(swing([Note(n.beat, n.dur, n.key + 12, 60) for n in melody(B, 64, 70) if n.dur > 0.6], 0.56))
    # Fingerpicked nylon guitar: bass on 1 and 3, chord tones on the eighths.
    gtr = s.part('nylon guitar', 0, 24, gain_db=-3, pan=-0.3, reverb=0.22)
    prev = None
    for start, length, sym in chord_spans(chords):
        v = voicing(sym, 55, 72, prev, 3); prev = v
        low = bass_note(sym, 43)
        fifth = chord_tone(sym, 2, 43)
        pattern = [(low, 70), (v[0], 52), (v[-1], 58), (v[1], 50), (fifth, 64), (v[0], 50), (v[-1], 56), (v[1], 48)]
        for k in range(int(length * 2)):
            key, vel = pattern[k % 8]
            gtr.add([Note(start + k * 0.5, 0.9 if k % 4 else 1.8, key, vel)])
    gtr.notes = swing(jitter_vel(gtr.notes, 6, RNG), 0.56)
    bass = s.part('acoustic bass', 0, 32, gain_db=-2, pan=0.0, reverb=0.08)
    for start, length, sym in chord_spans(chords):
        root = bass_note(sym, 33)
        if length >= 4:
            bass.add([Note(start, 1.6, root, 92), Note(start + 2, 1.2, chord_tone(sym, 2, 33), 80),
                      Note(start + 3.5, 0.4, root + (2 if RNG.random() < .5 else -1), 62)])
        else:
            bass.add([Note(start, length * 0.85, root, 88)])
    bass.notes = swing(bass.notes, 0.56)
    kit = s.part('brush kit', 128, 40, gain_db=-9, pan=0.05, reverb=0.25)
    for bar in range(32):
        p = {'kick': 'o.......o.......', 'swirl': 'g...g...g...g...', 'snare': '....h.......h..g'}
        if bar % 8 == 7: p['snare'] = '....h...h.g.h.hg'
        if bar < 2: p = {'swirl': 'g.......g.......'}
        kit.add(groove(p, bar))
    kit.notes = swing(jitter_vel(kit.notes, 8, RNG), 0.56)
    return s


# ---------------------------------------------------------------- home night
def home_night() -> Song:
    s = Song('home_night', '窗边夜灯', 66, 24, target_rms_db=-23, reverb_room=0.86)
    chords = ['Cmaj7', 'Em7', 'Fmaj7', 'Fm6', 'Cmaj7', 'Am7', 'Dm7', 'G7sus4',
              'Cmaj7', 'Em7', 'Fmaj7', 'Fm6', 'Em7', 'A7', 'Dm7', 'G7sus4 G7',
              'Fmaj7', 'G/F', 'Em7', 'Am7', 'Dm7', 'Em7', 'Fmaj7', 'G7sus4']
    tune = ('E5:1 G5:1 B5:2 | D6:1.5 B5:.5 G5:2 | A5:1 C6:1 E6:1 C6:1 | D6:3 r:1 | '
            'E5:1 G5:1 B5:1 C6:1 | E6:2 C6:1 A5:1 | F5:1 A5:1 C6:1.5 A5:.5 | G5:3 r:1 | '
            'E5:1 G5:1 B5:2 | D6:1.5 E6:.5 B5:2 | A5:1 C6:1 G6:1 E6:1 | Ab5:2 F5:1 D5:1 | '
            'G5:1.5 F#5:.5 E5:2 | C#6:2 E6:1 G5:1 | F5:1 A5:1 C6:1 E6:1 | D6:2 B5:2 | '
            'C6:3 A5:1 | B5:2 D6:2 | G6:1.5 E6:.5 B5:2 | C6:3 E5:1 | '
            'F5:1 A5:1 D6:1 C6:1 | B5:3 G5:1 | A5:1 C6:1 E6:2 | D6:2 C6:1 r:1')
    s.part('celesta', 0, 8, gain_db=-2, pan=0.15, reverb=0.45, humanize_ms=10).add(melody(tune, 0, 80))
    box = s.part('music box', 0, 10, gain_db=-16, pan=-0.35, reverb=0.5)
    box.add([Note(n.beat + 0.5, n.dur, n.key + 12, 55) for n in melody(tune, 64, 70) if n.dur >= 1.0])
    piano = s.part('soft piano', 0, 0, gain_db=-5, pan=-0.15, reverb=0.4, humanize_ms=4)
    prev = None
    for start, length, sym in chord_spans(chords):
        v = voicing(sym, 52, 69, prev, 4); prev = v
        for k, key in enumerate(v):  # gently rolled
            piano.add([Note(start + k * 0.09, length * 0.95, key, 46 + k * 2)])
        if length >= 4:
            piano.add([Note(start + 2.5, 1.4, v[-1], 40), Note(start + 3.0, 0.9, v[-2], 36)])
    pad = s.part('warm pad', 0, 89, gain_db=-15, pan=0.0, reverb=0.3)
    prev = None
    for start, length, sym in chord_spans(chords):
        v = voicing(sym, 48, 64, prev, 3); prev = v
        pad.add([Note(start, length, k, 50) for k in v])
    bass = s.part('fretless bass', 0, 35, gain_db=-4, pan=0.0, reverb=0.12)
    for start, length, sym in chord_spans(chords):
        bass.add([Note(start, length * 0.9, bass_note(sym, 33), 70)])
    return s


# ---------------------------------------------------------------- club day
def club_day() -> Song:
    s = Song('club_day', '俱乐部的午后', 112, 32, target_rms_db=-20)
    chords = ['Gmaj7', 'Em7', 'Am7', 'D7', 'Bm7', 'E7', 'Am7', 'D7',
              'Gmaj7', 'Em7', 'Am7', 'D7', 'Bm7', 'Bbdim7', 'Am7 D7', 'G6',
              'Cmaj7', 'Cm6', 'Bm7', 'E7', 'Am7', 'D7', 'Em7 A7', 'Am7 D7',
              'Gmaj7', 'Em7', 'Am7', 'D7', 'Bm7', 'E7', 'Am7', 'D7']
    A = ('D5:.5 G5:.5 B5:.5 D6:1 B5:.5 A5:1 | G5:.5 E5:.5 G5:.5 B5:1.5 r:1 | C6:.5 B5:.5 A5:.5 G5:.5 E5:1 C5:1 | '
         'D5:.5 F#5:.5 A5:.5 C6:1.5 r:1 | B5:.5 A5:.5 F#5:.5 D5:1 F#5:.5 A5:1 | G#5:1.5 E5:.5 B4:1 D5:1 | '
         'C5:.5 E5:.5 A5:.5 C6:.5 B5:1 A5:1 | F#5:1 E5:.5 D5:.5 C5:1 r:1')
    A2 = ('D5:.5 G5:.5 B5:.5 D6:1 B5:.5 A5:1 | G5:.5 E5:.5 G5:.5 B5:1.5 r:1 | C6:.5 B5:.5 A5:.5 G5:.5 E5:1 G5:1 | '
          'F#5:1.5 A5:.5 C6:1 D6:1 | D6:.5 B5:.5 A5:.5 F#5:.5 D5:2 | E5:1 G5:1 Bb5:1.5 G5:.5 | '
          'A5:.5 C6:.5 E6:1 D6:.5 C6:.5 A5:1 | G5:3 r:1')
    B = ('E5:1 G5:.5 B5:.5 C6:1 B5:1 | Eb6:1.5 C6:.5 A5:1 G5:1 | F#5:1 A5:.5 B5:.5 D6:1 A5:1 | G#5:2 B5:1 D6:1 | '
         'C6:1.5 B5:.5 A5:1 E5:1 | F#5:.5 G5:.5 A5:.5 B5:.5 C6:1 A5:1 | G5:1 B5:1 C#6:1 E6:1 | '
         'E6:.5 D6:.5 C6:1 A5:.5 F#5:.5 D5:1')
    A3 = A.rsplit('|', 1)[0] + '| F#5:1 E5:.5 D5:.5 C5:.5 B4:.5 A4:.5 C5:.5'
    mar = s.part('marimba', 0, 12, gain_db=0, pan=0.1, reverb=0.2)
    whistle = s.part('whistle', 0, 78, gain_db=-7, pan=-0.05, reverb=0.3, humanize_ms=8)
    glock = s.part('glockenspiel', 0, 9, gain_db=-14, pan=0.4, reverb=0.35)
    sw = 0.6
    mar.add(swing(melody(A, 0, 92, 0.8), sw))
    whistle.add(swing(melody(A2, 32, 84), sw))
    mar.add(swing(melody(A2, 32, 62, 0.8), sw))
    mar.add(swing(melody(B, 64, 92, 0.8), sw))
    glock.add(swing([Note(n.beat, n.dur, n.key + 12, 62) for n in melody(B, 64, 70)], sw))
    whistle.add(swing(melody(A3, 96, 84), sw))
    mar.add(swing(melody(A3, 96, 66, 0.8), sw))
    ep = s.part('electric piano', 0, 4, gain_db=-6, pan=-0.25, reverb=0.18)
    gtr = s.part('steel guitar chops', 0, 25, gain_db=-11, pan=0.35, reverb=0.12, humanize_ms=4)
    prev = None
    for start, length, sym in chord_spans(chords):
        v = voicing(sym, 55, 71, prev, 4); prev = v
        hits = [0, 1.5, 3] if length >= 4 else [0, 1.5]
        for h in hits:
            ep.add([Note(start + h, 0.9 if h != 1.5 else 0.45, k, 64 if h == 0 else 54) for k in v])
        for k in range(int(length)):
            for j, key in enumerate(v[1:]):
                gtr.add([Note(start + k + 0.5 + j * 0.012, 0.22, key + 12, 56)])
    ep.notes = swing(ep.notes, sw); gtr.notes = swing(gtr.notes, sw)
    bass = s.part('finger bass', 0, 33, gain_db=-1, pan=0.0, reverb=0.05)
    for start, length, sym in chord_spans(chords):
        root = bass_note(sym, 31)
        if length >= 4:
            fifth = chord_tone(sym, 2, root)
            bass.add([Note(start, 0.9, root, 96), Note(start + 1.5, 0.4, root + 12, 76), Note(start + 2, 0.9, fifth, 88),
                      Note(start + 3, 0.45, root + 12, 70), Note(start + 3.5, 0.45, fifth - 2 if fifth - 2 > root else root + 10, 66)])
        else:
            bass.add([Note(start, 0.9, root, 94), Note(start + 1, 0.45, root + 7, 74), Note(start + 1.5, 0.45, root + 12, 66)])
    bass.notes = swing(bass.notes, sw)
    kit = s.part('drums', 128, 0, gain_db=-7, pan=0.0, reverb=0.15)
    for bar in range(32):
        p = {'kick': 'x.....o.x.......', 'stick': '....o.......o...', 'hat': 'o.g.o.g.o.g.o.g.',
             'shaker': 'g.gg g.gg g.gg g.gg'.replace(' ', '')}
        if bar in (0, 16): p['crash'] = 'o...............'
        if bar % 8 == 7: p['stick'] = '....o.......o.o.'; p['block'] = '..........g.g.g.'
        if 16 <= bar < 24: p['tamb'] = '....g.......g...'
        kit.add(groove(p, bar))
    kit.notes = swing(jitter_vel(kit.notes, 7, RNG), sw)
    return s


# ---------------------------------------------------------------- club night (lo-fi)
def club_night() -> Song:
    s = Song('club_night', '训练后的夜晚', 80, 24, target_rms_db=-21)
    chords = ['Abmaj7', 'Gm7', 'Fm7', 'Bb7sus4 Bb7', 'Ebmaj7', 'Cm7', 'Fm9', 'Bb7',
              'Abmaj7', 'Gm7', 'Fm7', 'Bb7sus4 Bb7', 'Ebmaj7', 'Cm7', 'Fm9', 'Bb7',
              'Abmaj7', 'Gm7 C7', 'Fm7', 'Bb7', 'Gm7', 'C7', 'Fm7', 'Bb7sus4']
    tune = ('C6:1 Eb6:.5 G5:1.5 r:1 | F5:.5 G5:.5 Bb5:1 D6:1 r:1 | Eb6:1.5 C6:.5 Ab5:2 | G5:1 F5:1 D5:1 r:1 | '
            'r:.5 Bb5:.5 D6:1 G6:1 F6:1 | Eb6:2 r:1 G5:1 | Ab5:1 C6:1 Eb6:1 G6:1 | F6:1 D6:1 Ab5:1 r:1 | '
            'C6:1 Eb6:.5 G5:1.5 r:1 | F5:.5 G5:.5 Bb5:1 D6:1 r:1 | Eb6:1.5 C6:.5 Ab5:2 | G5:1 F5:1 D5:1 r:1 | '
            'G6:1 F6:.5 D6:1.5 Bb5:1 | C6:3 r:1 | G5:1 Ab5:1 C6:1 Eb6:1 | D6:3 r:1 | '
            'Eb6:1.5 C6:.5 G5:2 | Bb5:1 D6:1 E6:1 Bb5:1 | Ab5:2 C6:1 F6:1 | D6:2 r:2 | '
            'F5:1 G5:1 Bb5:1 D6:1 | E6:2 G6:1 Bb5:1 | Ab6:1.5 G6:.5 Eb6:1 C6:1 | Eb6:2 r:2')
    sw = 0.62
    s.part('vibraphone', 0, 11, gain_db=-1, pan=0.15, reverb=0.35, humanize_ms=12).add(swing(melody(tune, 0, 78, 0.85), sw))
    ep = s.part('electric piano', 0, 4, gain_db=-3, pan=-0.2, reverb=0.25)
    prev = None
    for start, length, sym in chord_spans(chords):
        v = voicing(sym, 53, 70, prev, 4); prev = v
        hits = [(0, 1.4, 62), (1.5, 0.4, 46), (3.0, 0.9, 52)] if length >= 4 else [(0, 1.4, 60)]
        for h, d, vel in hits:
            for j, k in enumerate(v):
                ep.add([Note(start + h + j * 0.02, d, k, vel)])
    ep.notes = swing(jitter_vel(ep.notes, 5, RNG), sw)
    bass = s.part('finger bass', 0, 33, gain_db=-2, pan=0.0, reverb=0.05)
    for start, length, sym in chord_spans(chords):
        root = bass_note(sym, 31)
        if length >= 4:
            bass.add([Note(start, 1.3, root, 92), Note(start + 1.75, 0.4, root, 64), Note(start + 2.5, 1.0, chord_tone(sym, 2, root), 80)])
        else:
            bass.add([Note(start, length * 0.8, root, 88)])
    bass.notes = swing(bass.notes, sw)
    kit = s.part('lofi drums', 128, 8, gain_db=-6, pan=0.0, reverb=0.1)
    for bar in range(24):
        p = {'kick': 'x......o..x.....', 'snare': '....x.......x...', 'hat': 'o.g.o.g.o.g.o.go', 'shaker': '..g...g...g...g.'}
        if bar % 4 == 3: p['kick'] = 'x......o..x...o.'
        if bar % 8 == 7: p['open'] = '..............g.'
        kit.add(groove(p, bar))
    kit.notes = swing(jitter_vel(kit.notes, 8, RNG), sw, 0.25)
    s.extra.append((vinyl(s.seconds + s.tail), 0.0))
    return s


def vinyl(seconds: float) -> np.ndarray:
    n = int(seconds * 44100)
    rng = np.random.default_rng(3)
    hiss = rng.normal(0, 1, n).astype(np.float32)
    from scipy.signal import lfilter
    hiss = lfilter([0.05], [1, -0.95], hiss) * 0.0012
    crackle = np.zeros(n, np.float32)
    idx = rng.integers(0, n, int(seconds * 6))
    crackle[idx] = rng.uniform(0.004, 0.02, len(idx)) * rng.choice([-1, 1], len(idx))
    crackle = lfilter([1, -0.6], [1], crackle)
    mono = hiss + crackle
    return np.array([mono, np.roll(mono, 37)], np.float32)


# ---------------------------------------------------------------- LAN studio
def lan_studio() -> Song:
    s = Song('lan_studio', '赛前热身', 112, 32, target_rms_db=-20)
    loop = ['Am9', 'Fmaj7', 'Cmaj7', 'G6', 'Am9', 'Fmaj7', 'Dm9', 'E7sus4 E7']
    chords = loop * 4
    pad = s.part('halo pad', 0, 94, gain_db=-14, pan=0.0, reverb=0.35)
    stab = s.part('poly stabs', 0, 90, gain_db=-12, pan=-0.2, reverb=0.3)
    arp = s.part('fm arp', 0, 5, gain_db=-10, pan=0.25, reverb=0.3, humanize_ms=2)
    bass = s.part('synth bass', 0, 39, gain_db=-6, pan=0.0, reverb=0.05, humanize_ms=2)
    prev = None
    for start, length, sym in chord_spans(chords):
        bar = int(start // 4)
        v = voicing(sym, 57, 74, prev, 4); prev = v
        pad.add([Note(start, length, k - 12, 56) for k in v[:3]])
        seq = v + [v[1] + 12, v[2] + 12]
        for k in range(int(length * 4)):
            arp.add([Note(start + k * 0.25, 0.2, seq[(k * 3) % len(seq)], 60 if k % 4 == 0 else 46)])
        if 8 <= bar < 28:
            for h in (0.5, 1.5, 2.5, 3.5)[:int(length)]:
                stab.add([Note(start + h, 0.22, k, 58) for k in v])
            root = bass_note(sym, 33)
            for k in range(int(length * 2)):
                if k % 2 == 1: bass.add([Note(start + k * 0.5, 0.4, root + (12 if k % 4 == 3 else 0), 84)])
    lead = s.part('crystal motif', 0, 98, gain_db=-9, pan=0.1, reverb=0.45)
    motif = 'E5:.75 G5:.75 A5:.5 C6:1 B5:1 | r:4 | E5:.75 G5:.75 A5:.5 D6:1 C6:1 | r:2 B5:1 G5:1'
    for start in (32, 64, 96):
        lead.add(melody(motif, start, 74))
    kit = s.part('808 kit', 128, 25, gain_db=-8, pan=0.0, reverb=0.08, humanize_ms=1)
    for bar in range(32):
        p = {'hat': '..o...o...o...o.'}
        if bar >= 4: p['kick'] = 'x...x...x...x...'
        if 8 <= bar < 28: p['clap'] = '....o.......o...'; p['shaker'] = 'g.g.g.g.g.g.g.g.'
        if bar in (8, 24): p['crash'] = 'o...............'
        if bar % 8 == 7 and 8 <= bar < 28: p['clap'] = '....o.......o.oo'
        if bar >= 28: p['kick'] = 'x.......x.......'
        kit.add(groove(p, bar))
    kit.notes = jitter_vel(kit.notes, 5, RNG)
    return s


# ---------------------------------------------------------------- awards hall
def awards_hall() -> Song:
    s = Song('awards_hall', '颁奖之夜', 76, 24, target_rms_db=-21, reverb_room=0.88, reverb_damp=0.3)
    chords = ['Bbmaj7', 'Gm7', 'Ebmaj7', 'F7sus4 F7', 'Bbmaj7/D', 'Ebmaj7', 'Cm7', 'F7sus4',
              'Gm7', 'Dm7', 'Ebmaj7', 'Bbmaj7/D', 'Cm7', 'Dm7', 'Ebmaj7', 'F7sus4 F7',
              'Bbmaj7', 'Gm7', 'Ebmaj7', 'Ebm6', 'Bbmaj7/D', 'G7', 'Cm7', 'F7sus4']
    A = ('F5:1 Bb5:1 D6:2 | C6:1.5 Bb5:.5 G5:2 | Bb5:1 D6:1 G6:1.5 F6:.5 | F6:2 Eb6:1 C6:1 | '
         'D6:1.5 C6:.5 Bb5:1 F5:1 | G5:1 Bb5:1 Eb6:1 D6:1 | Eb6:1.5 D6:.5 C6:1 G5:1 | C6:2 Bb5:1 r:1')
    B = ('D5:1.5 C5:.5 Bb4:1 G4:1 | A4:2 F4:1 A4:1 | Bb4:1.5 C5:.5 D5:1 Eb5:1 | F5:3 D5:1 | '
         'Eb5:1.5 D5:.5 C5:1 G4:1 | F5:1.5 D5:.5 A4:2 | G4:1 Bb4:1 Eb5:1 G5:1 | F5:2 Eb5:1 A4:1')
    A3 = ('F5:1 Bb5:1 D6:2 | C6:1.5 Bb5:.5 G5:2 | Bb5:1 D6:1 G6:1.5 F6:.5 | Gb6:2 F6:1 C6:1 | '
          'D6:1.5 C6:.5 Bb5:1 F5:1 | B5:1 D6:1 F6:1.5 D6:.5 | Eb6:1.5 D6:.5 C6:1 G5:1 | C6:2 Bb5:1 r:1')
    s.part('celesta', 0, 8, gain_db=-3, pan=0.2, reverb=0.45).add(melody(A, 0, 82)).add(melody(A3, 64, 78))
    s.part('french horns', 0, 60, gain_db=-2, pan=-0.1, reverb=0.4, humanize_ms=10).add(melody(B, 32, 80, 0.97))
    s.part('flute', 0, 73, gain_db=-9, pan=0.3, reverb=0.4, humanize_ms=10).add(
        [Note(n.beat, n.dur, n.key - 12, 66) for n in melody(A3, 64, 70, 0.97) if n.dur >= 1])
    strings = s.part('slow strings', 0, 49, gain_db=-7, pan=0.0, reverb=0.4)
    harp = s.part('harp', 0, 46, gain_db=-5, pan=-0.3, reverb=0.4, humanize_ms=4)
    cello = s.part('cello', 0, 42, gain_db=-6, pan=0.1, reverb=0.3)
    prev = None
    for start, length, sym in chord_spans(chords):
        v = voicing(sym, 53, 69, prev, 4); prev = v
        strings.add([Note(start, length, k, 58) for k in v])
        root = bass_note(sym, 36)
        cello.add([Note(start, length * 0.98, root, 70)])
        seq = [root + 12, v[0], v[1], v[2], v[-1], v[2], v[1], v[0]]
        for k in range(int(length * 2)):
            harp.add([Note(start + k * 0.5, 1.2, seq[k % len(seq)], 62 if k % 4 == 0 else 50)])
    timp = s.part('timpani', 0, 47, gain_db=-10, pan=0.0, reverb=0.35)
    for bar in (0, 8, 16):
        timp.add([Note(bar * 4, 1.5, pitch('Bb2'), 70)])
    timp.add([Note(23 * 4 + 2 + k * 0.125, 0.12, pitch('F2'), 40 + k * 3) for k in range(16)])
    return s


# ---------------------------------------------------------------- Major walk-in (one shot, 136 BPM)
def major_walkin() -> Song:
    beat = 60 / 136
    s = Song('major_walkin', '冠军之路', 136, 8, loop=False, tail=2.4, target_rms_db=-16, reverb_room=0.84)
    s.length_seconds = beat * 32
    # Build (beats 0-8): timpani roll, tremolo strings, snare roll, riser.
    timp = s.part('timpani', 0, 47, gain_db=-4, reverb=0.3, humanize_ms=2)
    timp.add([Note(k * 0.25, 0.24, pitch('D2'), int(40 + k * 2.5)) for k in range(32)])
    timp.add([Note(8, 2, pitch('D2'), 120), Note(32, 3, pitch('D2'), 124)])
    trem = s.part('tremolo strings', 0, 44, gain_db=-8, reverb=0.3)
    trem.add([Note(0, 8, k, 50 + 0) for k in (pitch('D3'), pitch('A3'), pitch('D4'), pitch('F4'))])
    trem.add([Note(4, 4, k, 80) for k in (pitch('A4'), pitch('D5'))])
    kit = s.part('power kit', 128, 16, gain_db=-4, reverb=0.15, humanize_ms=2)
    kit.add([Note(4 + k * 0.25, 0.2, 38, int(50 + k * 4)) for k in range(16)])
    for bar in range(2, 8):
        p = {'kick': 'x...x.x.x...x.x.', 'snare': '....x.......x...', 'hat': 'o.o.o.o.o.o.o.o.'}
        if bar == 2: p['crash'] = 'X...............'; p['kick'] = 'X...x.x.x...x.x.'
        if bar == 4: p['crash'] = 'x...............'
        if bar == 7: p['snare'] = '....x.......xxxx'; p['hitom'] = '........o.o.....'; p['lotom'] = '............o.o.'
        kit.add(groove(p, bar))
    kit.add(groove({'crash': 'X...............', 'kick': 'X...............'}, 8))
    hit = s.part('orchestra hit', 0, 55, gain_db=-6, reverb=0.35)
    for at in (8, 32):
        hit.add([Note(at, 1.5, k, 118) for k in (pitch('D4'), pitch('F4'), pitch('A4'))])
    chords = ['Dm', 'Dm', 'Dm', 'Bb', 'F', 'C', 'Gm A', 'Dm']
    bass = s.part('synth bass', 0, 39, gain_db=-4, reverb=0.05, humanize_ms=1)
    strings = s.part('fast strings', 0, 48, gain_db=-7, reverb=0.3, humanize_ms=2)
    for start, length, sym in chord_spans(chords):
        if start < 8: continue
        root = bass_note(sym, 26)
        for k in range(int(length * 2)):
            bass.add([Note(start + k * 0.5, 0.42, root + (12 if k % 2 else 0), 100 if k % 2 == 0 else 84)])
        v = voicing(sym, 62, 76, None, 3)
        for k in range(int(length * 4)):
            strings.add([Note(start + k * 0.25, 0.2, v[k % 3], 84 if k % 2 == 0 else 66)])
    theme = ('D4:.75 D4:.25 A4:1.5 G4:.5 F4:1 | G4:.5 F4:.5 D4:1 F4:1 Bb4:1 | A4:1.5 C5:.5 F5:2 | '
             'E5:1 D5:.5 C5:.5 G4:2 | Bb4:1 D5:1 C#5:1 E5:1 | D5:4')
    brass = s.part('brass section', 0, 61, gain_db=-1, reverb=0.3, humanize_ms=3)
    brass.add(melody(theme, 8, 108, 0.94))
    brass.add([Note(n.beat, n.dur, n.key - 12, 96) for n in melody(theme, 8, 100, 0.94)])
    brass.add([Note(32, 2.5, k, 116) for k in (pitch('D3'), pitch('A3'), pitch('D4'), pitch('F4'))])
    horn = s.part('horns', 0, 60, gain_db=-5, reverb=0.35)
    horn.add([Note(8, 8, k, 90) for k in (pitch('D4'), pitch('F4'), pitch('A4'))])
    s.extra.append((riser(beat * 8), 0.0))
    return s


def riser(seconds: float) -> np.ndarray:
    from scipy.signal import lfilter
    n = int(seconds * 44100)
    rng = np.random.default_rng(11)
    noise = rng.normal(0, 1, n)
    t = np.arange(n) / n
    out = np.zeros(n)
    # Swept one-pole high-pass: the noise brightens as it rises.
    for seg in range(16):
        a, b = seg * n // 16, (seg + 1) * n // 16
        coeff = 0.98 - 0.6 * (seg / 16)
        out[a:b] = lfilter([1, -1], [1, -coeff], noise[a:b])
    out *= (t ** 2.2) * 0.05
    return np.array([out, np.roll(out, 61)], np.float32)


# ---------------------------------------------------------------- arena PA loop
def arena_pa() -> Song:
    s = Song('arena_pa', '场馆暖场', 128, 32, target_rms_db=-19)
    loop = ['Dm', 'Bb', 'F', 'C', 'Dm', 'Bb', 'Gm', 'A7sus4 A7']
    chords = loop * 4
    gtr = s.part('drive guitar', 0, 29, gain_db=-15, pan=-0.35, reverb=0.15, humanize_ms=3)
    syn = s.part('synth brass', 0, 62, gain_db=-11, pan=0.3, reverb=0.25)
    bass = s.part('synth bass', 0, 38, gain_db=-5, reverb=0.05, humanize_ms=1)
    pluck = s.part('pluck', 0, 5, gain_db=-13, pan=0.2, reverb=0.3, humanize_ms=1)
    for start, length, sym in chord_spans(chords):
        bar = int(start // 4)
        root = bass_note(sym, 26)
        for k in range(int(length * 2)):
            bass.add([Note(start + k * 0.5, 0.4, root + (12 if k % 4 == 3 else 0), 96 if k % 2 == 0 else 80)])
        power = [root + 12, root + 19, root + 24]
        if 8 <= bar < 24 or bar >= 28:
            for k in range(int(length * 2)):
                gtr.add([Note(start + k * 0.5, 0.35, p, 76) for p in power])
        v = voicing(sym, 60, 74, None, 3)
        if bar >= 16:
            syn.add([Note(start, 0.45, k, 84) for k in v] + [Note(start + 1.5, 0.45, k, 74) for k in v] +
                    [Note(start + 3, 0.9, k, 80) for k in v])
        seq = v + [v[0] + 12]
        for k in range(int(length * 4)):
            pluck.add([Note(start + k * 0.25, 0.18, seq[k % 4] + 12, 58 if k % 2 == 0 else 44)])
    kit = s.part('power kit', 128, 16, gain_db=-5, reverb=0.12, humanize_ms=2)
    for bar in range(32):
        p = {'kick': 'x...x...x...x...', 'hat': '..o...o...o...o.'}
        if bar >= 8: p['clap'] = '....x.......x...'; p['snare'] = '....o.......o...'
        if bar % 8 == 0: p['crash'] = 'o...............'
        if bar % 8 == 7: p['snare'] = '....o.......oooo'
        kit.add(groove(p, bar))
    hook = 'D5:.5 F5:.5 A5:1 G5:.5 F5:.5 E5:1 | D5:.5 C5:.5 D5:1 F5:2 | A5:.5 C6:.5 A5:1 G5:.5 F5:.5 G5:1 | E5:1 C#5:1 E5:2'
    lead = s.part('square lead', 0, 80, gain_db=-14, pan=0.0, reverb=0.3)
    for start in (64, 80, 112):
        lead.add(melody(hook, start, 80, 0.9))
    return s


TRACKS = [home_day, home_night, club_day, club_night, lan_studio, awards_hall, major_walkin, arena_pa]


# ---------------------------------------------------------------- Major walk-in v2 (restrained, tense)
def major_walkin_v2() -> Song:
    """Focus instead of fanfare: heartbeat intro, a pulsing build, a dry
    half-time groove under a minor piano motif, and a single low hit to end."""
    s = Song('major_walkin_v2', '冠军之路', 120, 16, loop=False, tail=3.5, target_rms_db=-17, reverb_room=0.8)
    spb = 0.5
    drone = s.part('drone', 0, 95, gain_db=-15, reverb=0.3)
    drone.add([Note(0, 32, pitch('D2'), 70), Note(0, 32, pitch('A2'), 62)])
    kit = s.part('kit', 128, 16, gain_db=-6, reverb=0.12, humanize_ms=2)
    for bar in range(4):
        kit.add(groove({'kick': 'o..g............', 'stick': 'g...g...g...g...'}, bar))
    for bar in range(4, 8):
        p = {'kick': 'o..g....o..g....', 'stick': 'g.g.g.g.g.g.g.g.'}
        if bar == 7:
            p['lotom'] = 'o.o.o.o.........'; p['midtom'] = '........o.o.o.o.'; p['snare'] = '........ggoooxxx'
        kit.add(groove(p, bar))
    for bar in range(8, 14):
        p = {'kick': 'x.....o...x.....', 'snare': '........X.......', 'hat': 'o.g.o.g.o.g.o.g.'}
        if bar == 8: p['crash'] = 'x...............'
        if bar == 11: p['kick'] = 'x.....o...x...o.'
        if bar == 13: p['snare'] = '........X...o.oo'
        kit.add(groove(p, bar))
    kit.add(groove({'kick': 'X...............'}, 14))
    timp = s.part('timpani', 0, 47, gain_db=-8, reverb=0.3)
    timp.add([Note(56, 3, pitch('D2'), 110)])
    piano = s.part('piano', 0, 0, gain_db=0, pan=0.05, reverb=0.3, humanize_ms=4)
    piano.add([Note(0, 4, pitch('D2'), 64), Note(0, 4, pitch('D3'), 56), Note(8, 4, pitch('D2'), 62), Note(8, 4, pitch('D3'), 54)])
    piano.add(melody('r:2 A4:.5 r:.5 F4:.5 E4:.5 | D4:4', 8, 60))
    chords = ['Dm', 'Dm', 'Dm', 'Dm', 'Dm', 'Dm/C', 'Bbmaj7', 'A7sus4 A7',
              'Dm', 'Dm/C', 'Bbmaj7', 'A7sus4 A7', 'Dm', 'Gm A7']
    bass = s.part('synth bass', 0, 38, gain_db=-10, reverb=0.04, humanize_ms=1)
    strings = s.part('low strings', 0, 49, gain_db=-7, reverb=0.35)
    pad = s.part('poly pad', 0, 90, gain_db=-13, pan=-0.2, reverb=0.3)
    prev = None
    for start, length, sym in chord_spans(chords):
        bar = int(start // 4)
        root = bass_note(sym, 26)
        if 4 <= bar < 8:
            for k in range(int(length * 4)):
                bass.add([Note(start + k * 0.25, 0.2, root, int(46 + (bar - 4) * 9 + (k % 4 == 0) * 10))])
        elif bar >= 8:
            pat = [(0, root, 96), (0.75, root, 70), (1.5, root + 12, 80), (2, root, 90), (2.75, root, 66), (3.5, root + 10, 74)]
            for off, key, vel in pat:
                if off < length: bass.add([Note(start + off, 0.22, key, vel)])
        if bar >= 4:
            v = voicing(sym, 50, 65, prev, 3); prev = v
            strings.add([Note(start, length, k, 54 + (bar - 4) * 4 if bar < 8 else 66) for k in v])
        if bar >= 8:
            v2 = voicing(sym, 60, 74, None, 3)
            for h in (0.5, 1.5, 2.5, 3.5):
                if h < length: pad.add([Note(start + h, 0.2, k, 60) for k in v2])
    motif = ('D5:.5 r:.25 D5:.25 F5:.5 A5:.5 G5:1 F5:.5 E5:.5 | F5:.75 E5:.25 D5:1 C5:1 A4:1 | '
             'D5:.5 F5:.5 A5:1 Bb5:.75 A5:.25 F5:1 | E5:2 C#5:2 | '
             'D5:.5 r:.25 D5:.25 F5:.5 A5:.5 C6:1 A5:1 | G5:.75 F5:.25 E5:1 C#5:1 A4:1')
    piano.add(melody(motif, 32, 92, 0.9))
    piano.add([Note(n.beat, n.dur, n.key - 12, 70) for n in melody(motif, 32, 70, 0.9)])
    s.part('synth strings', 0, 50, gain_db=-10, pan=0.25, reverb=0.35).add(
        [Note(n.beat, n.dur, n.key - 12, 70) for n in melody(motif, 32, 70, 1.0) if n.dur >= 0.75])
    piano.add([Note(56, 6, k, 84) for k in (pitch('D2'), pitch('A2'), pitch('D3'), pitch('F3'))])
    s.part('reverse cymbal', 0, 119, gain_db=-12, reverb=0.2).add([Note(32 - 4.2, 4.2, 60, 90)])
    s.extra.append((riser(4 * spb * 4) * 0.7, 12.0))
    return s

TRACKS.append(major_walkin_v2)


# ---------------------------------------------------------------- Major final opener v3 (dark hybrid trailer)
def major_final_v3() -> Song:
    """Grand-final opener: weight from low brass braams, taiko and a gritty
    bass, tension from a ticking timer and staccato strings. Minor/phrygian,
    no bright fanfare."""
    import sfx
    bpm = 128; spb = 60 / bpm
    s = Song('major_final_v3', '决赛开场', bpm, 21, loop=False, tail=4.5, target_rms_db=-15, reverb_room=0.84, eq=(-3.0, 6.0))
    bar = lambda b: b * 4  # bar index (0-based) to beat
    sec = lambda beat: beat * spb
    # Intro: drone, low piano hits, choir swell, ticking timer.
    s.part('drone', 0, 95, gain_db=-12, reverb=0.3).add([Note(0, bar(10), pitch('D2'), 72)])
    piano = s.part('low piano', 0, 0, gain_db=-4, reverb=0.35)
    for b in range(0, 10, 1):
        piano.add([Note(bar(b), 3, pitch('D1'), 96), Note(bar(b), 3, pitch('D2'), 88)])
    choir = s.part('choir', 0, 52, gain_db=-6, reverb=0.45)
    braam = s.part('braam', 0, 61, gain_db=-1, reverb=0.35, drive=2.5)
    tuba = s.part('low brass', 0, 57, gain_db=-4, reverb=0.3, drive=2.0)
    for b, extra in ((2, None), (4, None), (6, None), (8, 'Eb3')):
        keys = ['D2', 'A2', 'D3', 'F3'] + ([extra] if extra else [])
        braam.add([Note(bar(b), 6, pitch(k), 118) for k in keys])
        tuba.add([Note(bar(b), 6, pitch(k), 112) for k in ('D2', 'A2')])
        s.extra.append((sfx.sub_boom(2.4, gain=0.55), sec(bar(b)), 0.1))
    # Timer beeps: one per beat, then eighths, then sixteenths into the drop.
    t, step = 0.0, 1.0
    while t < bar(10) - 1:
        s.extra.append((sfx.beep(0.10 + 0.08 * t / bar(10)), sec(t), 0.15))
        if t >= bar(6): step = 0.5
        if t >= bar(8): step = 0.25
        t += step
    # Build: staccato strings, taiko, low strings, riser, snare roll.
    strings = s.part('staccato strings', 0, 48, gain_db=-3, reverb=0.3, humanize_ms=2)
    ost = ['D3', 'D3', 'F3', 'D3', 'A3', 'D3', 'F3', 'E3']
    for k in range(bar(3) * 4, bar(10) * 4 - 4):
        b = k // 16
        vel = min(110, 52 + (b - 3) * 9)
        strings.add([Note(k * 0.25, 0.16, pitch(ost[k % 8]), vel if k % 4 == 0 else vel - 18)])
    taiko = s.part('taiko', 0, 116, gain_db=-3, reverb=0.3, humanize_ms=3)
    pats = {3: 'x.......x.......', 4: 'x.......x.......', 5: 'x..x....x..x....', 6: 'x..x..x.x..x....',
            7: 'x..x..x.x..x..x.', 8: 'x.xx..x.x.xx..x.', 9: 'xxxxxxxxxxxxxxx.'}
    for b, p in pats.items():
        for i, ch in enumerate(p):
            if ch == 'x': taiko.add([Note(bar(b) + i * 0.25, 0.3, pitch('C3'), 90 + (b - 3) * 4 if b < 9 else 60 + i * 4)])
    lowstr = s.part('low strings', 0, 49, gain_db=-8, reverb=0.4)
    orch = s.part('orchestral kit', 128, 48, gain_db=-6, reverb=0.35, humanize_ms=1)
    orch.add([Note(bar(9) + k * 0.125, 0.12, 38, 40 + k * 3) for k in range(24)])
    s.extra.append((riser(sec(8) * 1.0) * 0.9, sec(bar(6)), 0.3))
    s.extra.append((sfx.whoosh(1.4, gain=0.35), sec(bar(10)) - 1.4 - 0.47, 0.2))
    s.gates.append((sec(bar(10)) - spb, sec(bar(10))))  # one-beat suck-back before the drop
    # Drop and peak.
    chords = ['Dm', 'Dm', 'Bb', 'A', 'Dm', 'Dm', 'Eb', 'A', 'Dm', 'Bb', 'A']
    motif = ('D4:1.5 D4:.5 F4:1 E4:1 | D4:1.5 C4:.5 A3:2 | Bb3:1 C4:1 D4:1 F4:1 | E4:2 C#4:1 A3:1 | '
             'D4:1.5 D4:.5 F4:1 G4:1 | A4:1.5 G4:.5 F4:1 E4:1 | Eb4:1.5 D4:.5 Bb3:1 G3:1 | A3:2 C#4:1 E4:1 | '
             'D4:1.5 D4:.5 F4:1 A4:1 | Bb4:1.5 A4:.5 F4:1 D4:1 | C#4:2 E4:2')
    horns = s.part('horns + trombones', 0, 60, gain_db=0, reverb=0.35, drive=1.4, humanize_ms=4)
    horns.add(melody(motif, bar(10), 110, 0.95))
    tuba.add([Note(n.beat, n.dur, n.key - 12, 108) for n in melody(motif, bar(10), 100, 0.95)])
    s.part('high strings', 0, 49, gain_db=-5, reverb=0.4).add(
        [Note(n.beat, n.dur, n.key + 12, 96) for n in melody(motif, bar(18), 90, 1.0)])
    reese_notes, prev = [], None
    for start, length, sym in chord_spans(['Dm'] * 10 + chords):
        if start < bar(10): continue
        root = bass_note(sym, 38)
        for k in range(int(length * 2)):
            reese_notes.append((start + k * 0.5, 0.42, root))
        v = voicing(sym, 50, 64, prev, 3); prev = v
        choir.add([Note(start, length, k, 92) for k in v])
        lowstr.add([Note(start, length, k - 12, 90) for k in v])
        for k in range(int(length * 4)):
            strings.add([Note(start + k * 0.25, 0.16, v[k % 3] + (12 if k % 8 >= 4 else 0), 104 if k % 4 == 0 else 80)])
    choir.add([Note(bar(1), bar(9), k, 64) for k in (pitch('D3'), pitch('A3'))])
    s.extra.append((sfx.reese(reese_notes, bpm, sec(bar(21)) + 1, gain=0.42), 0.0, 0.0))
    kit = s.part('drums', 128, 16, gain_db=1, reverb=0.15, humanize_ms=2)
    for b in range(10, 21):
        p = {'kick': 'x.....x...x.....', 'snare': '........X.......', 'hat': 'o.o.o.o.o.o.o.o.'}
        if b in (10, 14, 18): p['crash'] = 'X...............'
        if b == 13 or b == 17: p['snare'] = '........X...x.xx'
        if b >= 18: p['crash'] = 'x.......x.......'; p['kick'] = 'x.x...x...x.x...'
        if b == 20: p['snare'] = '........X.x.xxxx'; p['hitom'] = '....o.o.........'; p['lotom'] = '......o.o.......'
        kit.add(groove(p, b))
        for i, ch in enumerate('x..x..x...x..x..' if b < 18 else 'x.xx..x.x.xx..xx'):
            if ch == 'x': taiko.add([Note(bar(b) + i * 0.25, 0.3, pitch('C3'), 104)])
    for b in (10, 14, 18):
        s.extra.append((sfx.impact(2.8, gain=0.7 if b == 10 else 0.45), sec(bar(b)), 0.25))
    # Final hit and ring-out.
    end = bar(21)
    braam.add([Note(end, 7, pitch(k), 124) for k in ('D2', 'A2', 'D3', 'F3', 'A3')])
    tuba.add([Note(end, 7, pitch(k), 120) for k in ('D2', 'A2')])
    choir.add([Note(end, 7, k, 100) for k in (pitch('D3'), pitch('F3'), pitch('A3'), pitch('D4'))])
    kit.add(groove({'crash': 'X...............', 'kick': 'X...............'}, 21))
    taiko.add([Note(end, 1, pitch('C3'), 124)])
    s.extra.append((sfx.impact(4.0, gain=0.9, seed=9), sec(end), 0.3))
    s.extra.append((sfx.whoosh(1.4, gain=0.3, seed=4), sec(end) - 1.4, 0.2))
    s.length_seconds = sec(end) + 0.01
    return s

TRACKS.append(major_final_v3)
