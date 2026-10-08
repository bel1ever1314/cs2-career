# Game audio generators

Original music and crowd sound for the 3D client. Nothing here samples
recordings: instruments come from the GeneralUser GS 2.0.3 SoundFont through a
small numpy SF2 renderer (`sf2.py`), crowds are synthesized voices, claps and
whistles (`crowd.py`).

| Script | Produces |
|---|---|
| `tracks.py` | All compositions (club day/night, home night, LAN, awards, arena PA, Major final opener) |
| `render_all.py` | Renders tracks to `out/*.wav` / `.ogg` (`CAREER_SF2` = SoundFont path) |
| `crowd_final.py` | Crowd stem on the Major opener timeline (`out/major_final_v3_crowd.wav`) |
| `crowd_ambience.py` | Seamless venue beds: arena murmur/active, LAN room, awards hall |
| `ceremony.py` | Awards ceremony and Top20/title popup one-shots: rolls, reveal hit, fanfare, applause, tick, honours, champion |
| `build_game_audio.py` | Runs all of the above and writes the files used by the game |

Rebuild everything the game uses:

    python -B tools/audio/build_game_audio.py --sf2 E:/CS2CareerTools/AudioTools/GeneralUser-GS-2.0.3.sf2

The opener's cue points (`major_final_cue.json`) are derived from its 128 BPM bar
grid; if the arrangement changes, keep `hold_start/hold_end/gate/drop` on bar
lines (tests/audio_integration_test checks the grid).
