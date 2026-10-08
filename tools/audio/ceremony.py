"""Annual awards ceremony stingers (one-shots, no loops).

The ceremony used additive-sine placeholders that sounded like a toy. These are
orchestral cues on the same SoundFont as the rest of the score, in B-flat major
with a dominant (F) pedal for the suspense, so every reveal resolves:

  ceremony_roll       ~2.6 s  timpani + suspended cymbal roll on F, low strings
  ceremony_roll_long  ~3.8 s  the podium version, horns join the swell
  ceremony_hit        ~2.4 s  bass drum, cymbal, timpani and a short tutti B-flat
  ceremony_fanfare    ~6.5 s  broad brass phrase over strings, ends on B-flat
  ceremony_applause   ~4.5 s  a hall of people clapping, a few cheers
  ceremony_tick       ~0.9 s  soft pizzicato + harp for each Top20 name (ranks 20–4)
  ceremony_honours    ~3.4 s  harp sweep into a warm string chord (awards popup opens)
  ceremony_champion   ~4.6 s  timpani pickup into a brass/strings B-flat (title won)

The game cuts the rolls when the name lands (awards_venue.gd), so the rolls
only build; the hit and fanfare start on the beat and line up when layered.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile
import subprocess

import mlib
import sf2
import crowd
from mlib import Song, melody, pitch
from sf2 import Note

KIT = (128, 48)          # GS orchestral kit
BASS_DRUM, CYMBAL, CYMBAL_2 = 36, 57, 59


def roll(beats: float, rate: float, lo: int, hi: int):
    """Evenly spaced strokes whose velocity climbs from lo to hi."""
    count = int(beats * rate)
    return [(k / rate, int(lo + (hi - lo) * (k / max(1, count - 1)) ** 1.6)) for k in range(count)]


def ceremony_roll(seconds: float = 2.6, name: str = 'ceremony_roll', horns: bool = False) -> Song:
    # 60 BPM so one beat is one second.
    s = Song(name, '颁奖鼓点', 60, 1, loop=False, tail=1.2, target_rms_db=-20, reverb_room=0.86, reverb_damp=0.3)
    s.length_seconds = seconds
    timp = s.part('timpani', 0, 47, gain_db=0, reverb=0.35, humanize_ms=3)
    timp.add([Note(t, 0.07, pitch('F2'), v) for t, v in roll(seconds, 18, 34, 112)])
    cym = s.part('suspended cymbal', *KIT, gain_db=-7, reverb=0.45, humanize_ms=4)
    cym.add([Note(t, 0.06, CYMBAL_2, v) for t, v in roll(seconds, 14, 12, 84)])
    low = s.part('low strings', 0, 44, gain_db=-8, reverb=0.4, humanize_ms=0)
    # Tremolo strings re-struck quieter-to-louder so the bed swells with the roll.
    for t, v in roll(seconds, 2, 40, 92):
        low.add([Note(t, 0.62, k, v) for k in (pitch('F2'), pitch('C3'), pitch('F3'))])
    if horns:
        horn = s.part('horns', 0, 60, gain_db=-6, reverb=0.45, humanize_ms=6)
        for t, v in roll(seconds - 1.0, 2, 36, 88):
            horn.add([Note(1.0 + t, 0.6, k, v) for k in (pitch('C4'), pitch('F4'), pitch('A4'))])
    return s


def ceremony_hit() -> Song:
    s = Song('ceremony_hit', '颁奖揭晓', 76, 1, loop=False, tail=2.2, target_rms_db=-17, reverb_room=0.88, reverb_damp=0.28)
    s.length_seconds = 0.4
    kit = s.part('bass drum and cymbal', *KIT, gain_db=-1, reverb=0.45, humanize_ms=0)
    kit.add([Note(0, 1.5, BASS_DRUM, 122), Note(0, 2.5, CYMBAL, 112)])
    timp = s.part('timpani', 0, 47, gain_db=-2, reverb=0.35, humanize_ms=0)
    timp.add([Note(0, 1.5, pitch('Bb1'), 124), Note(0, 1.5, pitch('F2'), 100)])
    brass = s.part('brass tutti', 0, 61, gain_db=-1, reverb=0.4, humanize_ms=2)
    brass.add([Note(0, 0.9, k, 116) for k in (pitch('Bb2'), pitch('F3'), pitch('Bb3'), pitch('D4'), pitch('F4'), pitch('Bb4'))])
    strings = s.part('strings', 0, 48, gain_db=-5, reverb=0.45, humanize_ms=2)
    strings.add([Note(0, 1.4, k, 104) for k in (pitch('Bb3'), pitch('D4'), pitch('F4'), pitch('Bb4'), pitch('D5'))])
    tuba = s.part('tuba', 0, 58, gain_db=-6, reverb=0.3, humanize_ms=0)
    tuba.add([Note(0, 1.0, pitch('Bb1'), 110)])
    return s


def ceremony_fanfare() -> Song:
    # 76 BPM, 2/2 feel: a broad rising phrase that lands on a held B-flat chord.
    s = Song('ceremony_fanfare', '颁奖号角', 76, 2, loop=False, tail=2.4, target_rms_db=-18, reverb_room=0.9, reverb_damp=0.28)
    s.length_seconds = 8 * 60 / 76
    tune = 'Bb4:1 F5:1.5 Eb5:.5 | D5:.5 Eb5:.5 F5:1 C5:1 | D5:4'
    trumpets = s.part('trumpets', 0, 56, gain_db=0, pan=0.15, reverb=0.4, humanize_ms=6)
    trumpets.add(melody(tune, 0, 104, 0.96))
    horns = s.part('horns', 0, 60, gain_db=-3, pan=-0.2, reverb=0.45, humanize_ms=8)
    horns.add(melody('F4:1 Bb4:1.5 Bb4:.5 | Bb4:1 A4:1 A4:1 | Bb4:4', 0, 96, 0.97))
    horns.add(melody('D4:1 D4:1.5 G4:.5 | F4:1 C4:1 F4:1 | F4:4', 0, 88, 0.97))
    trombones = s.part('trombones', 0, 57, gain_db=-4, pan=-0.05, reverb=0.4, humanize_ms=6)
    # Bb – Eb/Bb – Bb/F – F – Bb
    for start, length, keys in [(0, 2, ('Bb2', 'F3', 'D4')), (2, 1, ('Bb2', 'G3', 'Eb4')), (3, 1, ('F2', 'F3', 'D4')),
                                (4, 1, ('F2', 'C3', 'A3')), (5, 1, ('F2', 'C3', 'Eb4')), (6, 1, ('Bb2', 'F3', 'D4')), (7, 1, ('Bb2', 'F3', 'D4'))]:
        trombones.add([Note(start, length * 0.95, pitch(k), 92) for k in keys])
    tuba = s.part('tuba', 0, 58, gain_db=-7, reverb=0.3)
    tuba.add([Note(0, 2, pitch('Bb1'), 96), Note(2, 1, pitch('Eb2'), 90), Note(3, 2, pitch('F1'), 92), Note(5, 1, pitch('F1'), 90),
              Note(6, 2, pitch('Bb1'), 100)])
    strings = s.part('strings', 0, 49, gain_db=-6, reverb=0.45)
    strings.add([Note(0, 3, k, 80) for k in (pitch('Bb3'), pitch('D4'), pitch('F4'), pitch('Bb4'))])
    strings.add([Note(3, 3, k, 84) for k in (pitch('A3'), pitch('C4'), pitch('F4'), pitch('C5'))])
    strings.add([Note(6, 4, k, 96) for k in (pitch('Bb3'), pitch('D4'), pitch('F4'), pitch('Bb4'), pitch('D5'), pitch('F5'))])
    timp = s.part('timpani', 0, 47, gain_db=-4, reverb=0.35, humanize_ms=2)
    timp.add([Note(0, 1, pitch('Bb1'), 108), Note(3, 1, pitch('F2'), 96), Note(4.5, .5, pitch('F2'), 84)])
    timp.add([Note(5 + k / 12, 0.08, pitch('F2'), 50 + 4 * k) for k in range(12)])
    timp.add([Note(6, 2, pitch('Bb1'), 118)])
    kit = s.part('cymbals', *KIT, gain_db=-5, reverb=0.5, humanize_ms=0)
    kit.add([Note(6, 3, CYMBAL, 104), Note(6, 2, BASS_DRUM, 108)])
    bells = s.part('bells', 0, 14, gain_db=-14, pan=0.3, reverb=0.55)
    bells.add([Note(6, 3, pitch('Bb5'), 70), Note(6, 3, pitch('F5'), 60)])
    return s


def ceremony_tick() -> Song:
    s = Song('ceremony_tick', '名次翻开', 60, 1, loop=False, tail=0.5, target_rms_db=-24, reverb_room=0.8, reverb_damp=0.35)
    s.length_seconds = 0.4
    pizz = s.part('pizzicato', 0, 45, gain_db=0, reverb=0.4, humanize_ms=0)
    pizz.add([Note(0, 0.3, pitch('F3'), 84), Note(0, 0.3, pitch('C4'), 76)])
    harp = s.part('harp', 0, 46, gain_db=-4, reverb=0.45, humanize_ms=0)
    harp.add([Note(0.02, 0.6, pitch('F5'), 70)])
    return s


def ceremony_honours() -> Song:
    s = Song('ceremony_honours', '荣誉揭幕', 60, 1, loop=False, tail=1.6, target_rms_db=-20, reverb_room=0.9, reverb_damp=0.28)
    s.length_seconds = 2.0
    harp = s.part('harp', 0, 46, gain_db=0, pan=-0.2, reverb=0.5, humanize_ms=3)
    sweep = ['Bb2', 'F3', 'Bb3', 'D4', 'F4', 'Bb4', 'D5', 'F5', 'Bb5']
    harp.add([Note(k * 0.07, 1.6, pitch(n), 70 + k * 3) for k, n in enumerate(sweep)])
    strings = s.part('strings', 0, 49, gain_db=-3, reverb=0.5)
    strings.add([Note(0.35, 2.2, pitch(n), 78) for n in ('Bb2', 'F3', 'D4', 'F4', 'C5', 'D5')])
    horns = s.part('horns', 0, 60, gain_db=-8, reverb=0.5, humanize_ms=6)
    horns.add([Note(0.6, 1.8, pitch(n), 70) for n in ('F3', 'Bb3', 'D4')])
    cym = s.part('cymbal', *KIT, gain_db=-12, reverb=0.55, humanize_ms=0)
    cym.add([Note(t, 0.06, CYMBAL_2, v) for t, v in roll(0.6, 14, 10, 56)])
    return s


def ceremony_champion() -> Song:
    s = Song('ceremony_champion', '冠军', 76, 2, loop=False, tail=2.4, target_rms_db=-17, reverb_room=0.9, reverb_damp=0.28)
    s.length_seconds = 3 * 60 / 76
    timp = s.part('timpani', 0, 47, gain_db=-2, reverb=0.35, humanize_ms=2)
    timp.add([Note(k / 16, 0.06, pitch('F2'), 50 + 4 * k) for k in range(16)])
    timp.add([Note(1, 2, pitch('Bb1'), 124)])
    kit = s.part('bass drum and cymbal', *KIT, gain_db=-3, reverb=0.5, humanize_ms=0)
    kit.add([Note(1, 2, BASS_DRUM, 118), Note(1, 3, CYMBAL, 112)])
    trumpets = s.part('trumpets', 0, 56, gain_db=0, pan=0.15, reverb=0.4, humanize_ms=5)
    trumpets.add(melody('F4:.5 Bb4:.5 | D5:1 F5:1 Bb5:2', 0, 108, 0.96))
    brass = s.part('brass', 0, 61, gain_db=-3, reverb=0.45, humanize_ms=4)
    brass.add([Note(1, 3, pitch(n), 104) for n in ('Bb2', 'F3', 'Bb3', 'D4', 'F4')])
    strings = s.part('strings', 0, 48, gain_db=-5, reverb=0.45)
    strings.add([Note(1, 3, pitch(n), 100) for n in ('Bb3', 'D4', 'F4', 'Bb4', 'D5', 'F5')])
    bells = s.part('bells', 0, 14, gain_db=-12, pan=0.3, reverb=0.55)
    bells.add([Note(3, 2, pitch('Bb5'), 72), Note(3, 2, pitch('D6'), 60)])
    return s


def ceremony_applause(seconds: float = 4.5):
    rate = crowd.RATE
    c = crowd.Crowd(seconds + 1.5, seed=88)
    for _ in range(int(240 * seconds * 3.2)):
        t = c.rng.uniform(0.02, seconds)
        # Fast attack, long warm sustain, natural thinning at the end.
        w = min(1.0, t / 0.35) * (1.0 if t < seconds * 0.6 else max(0.0, 1 - (t - seconds * 0.6) / (seconds * 0.4)))
        if c.rng.random() < w: c.clap(t, 0.55 + 0.45 * w)
    for _ in range(10):
        c.cheer(0.2 + abs(c.rng.normal(0, 0.6)), 0.45)
    y = c.finish(1.9, 0.45)[:, :int((seconds + 1.0) * rate)]
    fade = int(0.8 * rate)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    y *= 10 ** (-20 / 20) / np.sqrt((y ** 2).mean())
    peak = np.abs(y).max()
    if peak > 0.89: y *= 0.89 / peak
    out = Path(__file__).with_name('out')
    wavfile.write(out / 'ceremony_applause.wav', rate, (y.T * 32767).astype(np.int16))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(out / 'ceremony_applause.wav'), '-c:a', 'libvorbis', '-q:a', '5',
                    str(out / 'ceremony_applause.ogg')], check=True)
    return {'id': 'ceremony_applause', 'seconds': round(y.shape[1] / rate, 3)}


SONGS = [lambda: ceremony_roll(2.6), lambda: ceremony_roll(3.8, 'ceremony_roll_long', True), ceremony_hit, ceremony_fanfare,
         ceremony_tick, ceremony_honours, ceremony_champion]
FILES = ['ceremony_roll', 'ceremony_roll_long', 'ceremony_hit', 'ceremony_fanfare', 'ceremony_applause',
         'ceremony_tick', 'ceremony_honours', 'ceremony_champion']


if __name__ == '__main__':
    import os
    sf = sf2.SoundFont(os.environ.get('CAREER_SF2', str(Path(__file__).with_name('gu.sf2'))))
    out = Path(__file__).with_name('out')
    infos = [mlib.render(make(), sf, out) for make in SONGS]
    infos.append(ceremony_applause())
    print(json.dumps([{k: i[k] for k in ('id', 'seconds')} | ({'peak_dbfs': i['peak_dbfs']} if 'peak_dbfs' in i else {}) for i in infos], ensure_ascii=False))
