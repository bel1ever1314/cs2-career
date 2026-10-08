"""Render every in-game audio file and copy it into the Godot project.

    python tools/audio/build_game_audio.py --sf2 E:/CS2CareerTools/AudioTools/GeneralUser-GS-2.0.3.sf2

Needs Python 3.12 with numpy and scipy, and ffmpeg (libvorbis) on PATH.
Output is deterministic for a given SoundFont; intermediate WAVs stay in
tools/audio/out. Music loops are rendered with their tails folded onto the
start; ambience loops crossfade their overhang, so all of them repeat cleanly.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1] / 'work/career3d_redesign/assets/audio'
MUSIC = {'club_day': 'music_club_day', 'club_night': 'music_club_night', 'home_night': 'music_home_night',
         'major_final_v3': 'major_final_music', 'major_final_v3_crowd': 'major_final_crowd'}
AMBIENCE = ['crowd_arena_murmur', 'crowd_arena_active', 'crowd_lan_room', 'crowd_awards_hall']
CEREMONY = ['ceremony_roll', 'ceremony_roll_long', 'ceremony_hit', 'ceremony_fanfare', 'ceremony_applause',
            'ceremony_tick', 'ceremony_honours', 'ceremony_champion']


def run(*args):
    subprocess.run([sys.executable, '-B', *args], cwd=HERE, check=True,
                   env=dict(os.environ, CAREER_SF2=str(ARGS.sf2)))


def ogg(source, target, quality):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(source), '-c:a', 'libvorbis',
                    '-q:a', str(quality), str(target)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sf2', type=Path, required=True)
    parser.add_argument('--project-audio', type=Path, default=PROJECT)
    ARGS = parser.parse_args()
    (HERE / 'out').mkdir(exist_ok=True)
    run('render_all.py')  # all tracks, fixed order: humanization RNG matches the approved takes
    run('crowd_final.py')
    run('crowd_ambience.py')
    run('ceremony.py')
    for source, target in MUSIC.items():
        ogg(HERE / 'out' / f'{source}.wav', ARGS.project_audio / f'{target}.ogg', 5)
    for name in AMBIENCE + CEREMONY:
        shutil.copy2(HERE / 'out' / f'{name}.ogg', ARGS.project_audio / f'{name}.ogg')
    spb = 60 / 128
    bar = lambda b: b * 4 * spb
    cue = {'schema_version': 1, 'id': 'major_final', 'title': '决赛开场', 'bpm': 128, 'beat_seconds': spb,
           'hold_start': bar(8), 'hold_end': bar(9), 'gate': bar(10) - spb, 'drop': bar(10),
           'hits': [bar(14), bar(18)], 'final': bar(21), 'length': 43.885,
           'stems': {'music': 'major_final_music.ogg', 'crowd': 'major_final_crowd.ogg'},
           'note': 'Original composition; music and crowd are separate synchronized stems.'}
    (ARGS.project_audio / 'major_final_cue.json').write_text(json.dumps(cue, ensure_ascii=False, indent=1), 'utf-8')
    print('audio written to', ARGS.project_audio)
