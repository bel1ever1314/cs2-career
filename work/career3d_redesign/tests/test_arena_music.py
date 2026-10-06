"""Check the authored cue without needing the external audio toolchain."""
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("arena_composition", ROOT / "source" / "compose_arena_entrance.py")
MUSIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MUSIC)


class ArenaCompositionTest(unittest.TestCase):
    def test_original_multilayer_arrangement(self):
        events, report = MUSIC.arrangement()
        self.assertFalse(report["external_recordings"])
        self.assertGreaterEqual(report["parts"]["string_ostinato"], 64)
        self.assertGreaterEqual(report["parts"]["horn_theme"], 24)
        self.assertGreaterEqual(report["parts"]["bass_drum"], 16)
        self.assertGreaterEqual(report["parts"]["trombone_downbeat"], 12)
        self.assertGreaterEqual(report["parts"]["drum_fill"], 8)
        self.assertTrue(all(0 <= event[1] < 128 for _, event in events if len(event) > 1))

    def test_music_and_light_clock_agree(self):
        report = json.loads((ROOT / "assets/audio/major_final_cue.json").read_text(encoding="utf-8"))
        source = (ROOT / "scripts" / "arena_atmosphere.gd").read_text(encoding="utf-8")
        self.assertEqual(report["bpm"], 128)
        self.assertIn("const ENTRANCE_BPM := 128.0", source)
        self.assertAlmostEqual(report["beat_seconds"], 60 / report["bpm"])
        self.assertGreater(report["length"], report["final"])
        self.assertNotIn('arena_entrance.ogg', source)
        self.assertNotIn('CompetitiveCue', source)

    def test_standard_midi_is_complete(self):
        events, _ = MUSIC.arrangement()
        midi = MUSIC.midi_bytes(events)
        self.assertEqual(midi[:4], b"MThd")
        self.assertEqual(midi[14:18], b"MTrk")
        self.assertEqual(int.from_bytes(midi[18:22], "big"), len(midi) - 22)
        self.assertTrue(midi.endswith(b"\xff\x2f\x00"))
        pitches_on = [data[1] for _, data in events if data[0] & 0xF0 == 0x90]
        pitches_off = [data[1] for _, data in events if data[0] & 0xF0 == 0x80]
        self.assertEqual(sorted(pitches_on), sorted(pitches_off))


if __name__ == "__main__":
    unittest.main()
