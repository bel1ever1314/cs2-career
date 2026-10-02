"""Compose and render a 20-second ORIGINAL arena entrance cue.

No downloaded music. MIDI is authored here: D minor / B-flat / F / C,
layered strings, low strings, horns, trombones, timpani and GM drums.
Run only against the new redesign output, never the prototype directory:

  python compose_arena_entrance.py --output E:\\CS2CareerTools\\Career3DRedesign\\assets\\audio

The caller owns write approval for --output. A --midi-only mode makes the
arrangement inspectable without invoking a renderer or writing audio.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
import subprocess
from pathlib import Path

BPM = 112
TICKS = 480
BEAT_SECONDS = 60 / BPM
BARS = 8
CUE_SECONDS = BARS * 4 * BEAT_SECONDS + 3.3
SF2 = Path(r"E:\CS2CareerTools\AudioTools\GeneralUser-GS-2.0.3.sf2")
FLUIDSYNTH = Path(r"E:\CS2CareerTools\AudioTools\fluidsynth-2.6.1\fluidsynth-v2.6.1-win10-x64-cpp11\bin\fluidsynth.exe")
FFMPEG = Path(r"D:\CS2CareerVideo\v1.6.0\tools\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")


def variable_length(value: int) -> bytes:
    result = bytearray([value & 0x7F])
    while value > 0x7F:
        value >>= 7
        result.insert(0, (value & 0x7F) | 0x80)
    return bytes(result)


def arrangement() -> tuple[list[tuple[int, bytes]], dict]:
    events: list[tuple[int, bytes]] = []
    counts: dict[str, int] = {}

    def note(channel: int, pitch: int, start: float, duration: float, velocity: int, part: str):
        events.append((round(start * TICKS), bytes([0x90 | channel, pitch, velocity])))
        events.append((round((start + duration) * TICKS), bytes([0x80 | channel, pitch, 0])))
        counts[part] = counts.get(part, 0) + 1

    # GM program numbers are zero-based. Channel 10 (index 9) is percussion.
    for channel, program, volume, pan in [(0, 48, 91, 35), (1, 60, 96, 58),
            (2, 57, 90, 73), (3, 42, 96, 82), (4, 43, 93, 49),
            (5, 47, 95, 66), (6, 49, 77, 93), (9, 0, 108, 64)]:
        events.extend([(0, bytes([0xC0 | channel, program])),
                       (0, bytes([0xB0 | channel, 7, volume])),
                       (0, bytes([0xB0 | channel, 10, pan])),
                       (0, bytes([0xB0 | channel, 91, 29]))])

    chords = [(50, [62, 65, 69]), (46, [58, 62, 65]),
              (41, [57, 60, 65]), (48, [60, 64, 67])] * 2
    melody = [[62, 65, 69], [70, 69, 65], [69, 72, 77], [76, 74, 72],
              [74, 77, 81], [82, 81, 77], [81, 79, 77], [76, 72, 74]]
    for bar, (root, chord) in enumerate(chords):
        start = bar * 4
        # Weighty low hits establish the pulse. The second half adds motion.
        note(4, root - 12, start, 3.8, 82 + (bar >= 4) * 8, "double_bass")
        for beat in [0, 2]:
            note(5, root - 12, start + beat, 0.75, 104 if beat == 0 else 93, "timpani")
            note(9, 36, start + beat, 0.18, 120 if beat == 0 else 109, "bass_drum")
            note(9, 41, start + beat + 0.08, 0.22, 74, "low_tom")
        for beat in [1, 3]:
            note(9, 38, start + beat, 0.16, 94 + (bar >= 4) * 12, "snare")
            note(9, 39, start + beat + 0.012, 0.12, 55, "clap_layer")
        if bar in [0, 4, 7]:
            note(9, 49, start, 1.6, 80 if bar < 4 else 99, "cymbal")
        for step in range(8):
            pitch = chord[[0, 2, 1, 2, 0, 2, 1, 2][step]]
            note(0, pitch, start + step * 0.5, 0.43, 66 + (step % 2 == 0) * 14 + (bar >= 4) * 8, "string_ostinato")
            if bar >= 2:
                note(3, root + (7 if step % 2 else 0), start + step * 0.5, 0.43, 65 + (bar >= 4) * 11, "cello_ostinato")
            if bar >= 4:
                note(9, 51, start + step * 0.5, 0.10, 45 + (step % 2 == 0) * 14, "ride")
        if bar >= 2:
            for pitch in chord:
                note(6, pitch + 12, start + 0.035, 3.7, 45 + (bar >= 4) * 11, "high_string_pad")
        # The horns speak in long phrases; low brass answers the downbeat.
        for offset, duration, pitch in zip([0, 1.5, 2.5], [1.35, 0.85, 1.35], melody[bar]):
            note(1, pitch, start + offset, duration, 86 + (bar >= 4) * 11, "horn_theme")
        if bar >= 1:
            for pitch in [root, root + 7]:
                note(2, pitch, start + 0.025, 1.1, 79 + (bar >= 4) * 14, "trombone_downbeat")
        if bar in [3, 7]:
            for offset, drum, velocity in [(2.75, 45, 79), (3.25, 43, 91), (3.5, 41, 101), (3.75, 38, 113)]:
                note(9, drum, start + offset, 0.12, velocity, "drum_fill")
    # Final D-minor cadence rings out after the final rising phrase.
    end = BARS * 4
    for pitch in [50, 57, 62, 65, 69, 74]:
        note(0 if pitch > 60 else 2, pitch, end, 2.7, 99, "final_cadence")
    note(4, 38, end, 3.0, 97, "final_bass")
    note(5, 38, end, 1.4, 119, "final_timpani")
    note(9, 36, end, 0.4, 125, "final_drum")
    note(9, 49, end, 2.5, 102, "final_cymbal")
    return events, {"title": "Threshold / Original arena entrance", "composer": "Original code-authored arrangement",
                    "bpm": BPM, "bars": BARS, "beat_seconds": BEAT_SECONDS,
                    "cadence_seconds": end * BEAT_SECONDS, "parts": counts,
                    "external_recordings": False, "license": "Original composition; GeneralUser GS soundfont instrument rendering"}


def midi_bytes(events: list[tuple[int, bytes]]) -> bytes:
    tempo = round(60_000_000 / BPM)
    track = bytearray(b"\x00\xff\x51\x03" + tempo.to_bytes(3, "big"))
    track.extend(b"\x00\xff\x58\x04\x04\x02\x18\x08")
    cursor = 0
    # Note-off precedes note-on at equal ticks to avoid sustained overlaps.
    for tick, data in sorted(events, key=lambda entry: (entry[0], 0 if entry[1][0] & 0xF0 == 0x80 else 1)):
        track.extend(variable_length(tick - cursor))
        track.extend(data)
        cursor = tick
    track.extend(variable_length(480) + b"\xff\x2f\x00")
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, TICKS) + b"MTrk" + struct.pack(">I", len(track)) + track


def render(output: Path, sf2: Path, synth: Path, ffmpeg: Path) -> dict:
    import numpy as np
    from scipy.io import wavfile

    for tool in [sf2, synth, ffmpeg]:
        if not tool.is_file():
            raise FileNotFoundError(tool)
    raw = output / "arena_entrance_dry.wav"
    subprocess.run([str(synth), "-ni", "-F", str(raw), "-r", "44100", "-g", "0.66",
                    "-o", "synth.reverb.active=0", "-o", "synth.chorus.active=0",
                    str(sf2), str(output / "arena_entrance.mid")], check=True)
    rate, samples = wavfile.read(raw)
    audio = samples.astype(np.float64) / max(1, np.iinfo(samples.dtype).max)
    if audio.ndim == 1:
        audio = np.repeat(audio[:, None], 2, axis=1)
    # Short venue tail, with early reflections kept below the original hit.
    frames = round(CUE_SECONDS * rate)
    audio = np.pad(audio, ((0, max(0, frames - len(audio))), (0, 0)))[:frames]
    wet = np.copy(audio)
    for delay, gain in [(0.091, 0.12), (0.147, 0.09), (0.223, 0.07), (0.347, 0.045), (0.511, 0.025), (0.731, 0.014)]:
        offset = round(delay * rate)
        wet[offset:] += audio[:-offset, ::-1] * gain
    tail = round(0.65 * rate)
    wet[-tail:] *= np.linspace(1.0, 0.0, tail)[:, None]
    # Avoid hard limiting; retain the low drum attack and orchestral dynamics.
    peak = float(np.max(np.abs(wet)))
    wet *= 0.87 / max(peak, 0.001)
    mastered = output / "arena_entrance_master.wav"
    wavfile.write(mastered, rate, np.round(wet * 32767).astype(np.int16))
    target = output / "arena_entrance.ogg"
    subprocess.run([str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(mastered),
                    "-af", "loudnorm=I=-16:TP=-1.2:LRA=9", "-c:a", "libvorbis", "-q:a", "6", str(target)], check=True)
    # Native Godot WAV loading works before an editor import; keep the .ogg
    # as the packaged music file and WAV as an explicit portable fallback.
    shutil.copyfile(mastered, output / "arena_entrance.wav")
    rms = float(np.sqrt(np.mean(wet ** 2)))
    return {"sample_rate": rate, "channels": int(wet.shape[1]), "duration_seconds": len(wet) / rate,
            "pre_encode_peak": float(np.max(np.abs(wet))), "rms_dbfs": 20 * math.log10(max(rms, 1e-9)),
            "ogg": str(target), "wav": str(output / "arena_entrance.wav")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--midi-only", action="store_true")
    parser.add_argument("--sf2", type=Path, default=SF2)
    parser.add_argument("--fluidsynth", type=Path, default=FLUIDSYNTH)
    parser.add_argument("--ffmpeg", type=Path, default=FFMPEG)
    args = parser.parse_args()
    if "Career3DPrototype" in args.output.resolve().parts:
        parser.error("Write only to the separate redesign output, not Career3DPrototype.")
    args.output.mkdir(parents=True, exist_ok=True)
    events, report = arrangement()
    (args.output / "arena_entrance.mid").write_bytes(midi_bytes(events))
    if not args.midi_only:
        report["render"] = render(args.output, args.sf2, args.fluidsynth, args.ffmpeg)
    (args.output / "arena_entrance_composition.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
