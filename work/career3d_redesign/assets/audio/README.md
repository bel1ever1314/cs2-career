# Original audio

Everything here is original to this project: no field recordings, sampled
voices, commercial music or downloaded loops. Instruments are rendered from the
GeneralUser GS 2.0.3 SoundFont (licence: `GeneralUser-GS-LICENSE.txt`); crowds
are synthesized (formant voices, claps, whistles) in numpy. Generator scripts
and how to re-render them: `tools/audio/README.md` in the source repository.

Files are plain Ogg Vorbis read at runtime (`scripts/audio_assets.gd`), so the
packaged game does not rely on the editor import cache.

| File | Use | Notes |
|---|---|---|
| `music_club_day.ogg` | Club 06:00–19:00 | 112 BPM, seamless loop |
| `music_club_night.ogg` | Club 19:00–06:00 | 80 BPM lo-fi, seamless loop |
| `music_home_night.ogg` | Bedroom 19:00–06:00 | 66 BPM, seamless loop |
| `major_final_music.ogg` | Major walk-out and free-visit entrance | 128 BPM, one shot |
| `major_final_crowd.ogg` | Same timeline, crowd only | played as a synchronized stem |
| `major_final_cue.json` | Hold bar, silent beat, drop, hits, final hit | drives lights and the hold/drop logic |
| `crowd_arena_murmur.ogg` / `crowd_arena_active.ogg` | Major bowl ambience | 40 s seamless loops, mixed by crowd energy and capacity |
| `crowd_lan_room.ogg` | LAN studio room tone, keyboards | 30 s loop |
| `crowd_awards_hall.ogg` | Awards hall murmur, polite applause | 40 s loop, hushes during the show |

The retired 112 BPM orchestral cue is retained only as authoring history in
the source archive. It is not played or included in the game's audio folder;
neither it nor the old synthesized sting is an entrance fallback.

Music is chosen by `scripts/music_director.gd` (autoload `Music`): scene +
in-game clock, 2 s crossfades, ducking under phone/computer/presentations,
a 20–40 s rest after two plays. Sound, mute and music volume persist in
`user://audio_settings.cfg`.
