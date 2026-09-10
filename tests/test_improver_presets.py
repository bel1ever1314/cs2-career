"""Two independent axes: upstream base difficulty and current career tier."""
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from cs2career.cs2 import improver_presets as presets
from cs2career.cs2.profiles import (
    _manifest_hash, _profile_block, active_manifest, bot_parameters,
    classify_tier, effective_strength, generate_match_vpk, read_db,
)
from cs2career.cs2.launch import build_request, game_levels_ok, install_match_avatars
from test_v15_core import fake_team


class ImproverPresetTests(unittest.TestCase):
    def test_settings_resource_check_uses_new_presets(self):
        self.assertTrue(game_levels_ok(Path('unused-game-path')))

    def test_cross_language_manifest_digest(self):
        fixture = json.loads((Path(__file__).parent/'fixtures/bot_manifest_contract.json').read_text())
        self.assertEqual(_manifest_hash(fixture), '4a1ba36891a336167784dff4aa0b326af807c14c82f9f76cd0e73ee807959bf9')

    def test_only_global_look_fields_change_with_difficulty(self):
        raw = presets.preset('High')['raw_acceleration']
        expected = {
            'Low': (2000, 100, 25, 3000, 150, 30),
            'Medium': (2000, 300, 50, 5000, 500, 30),
            'High': (raw, 3000, 45, raw, 3000, 39.95),
        }
        look = [key for key in presets.PARAMETER_KEYS if key.startswith('LookAngle')]
        for role in ('rifle', 'entry', 'awp', 'igl', 'lurk'):
            for ability in (64, 65, 74, 75, 84, 85, 89, 90, 94, 95, 97, 98, 100):
                rows = [bot_parameters(ability, ability, level, role) for level in presets.LEVELS]
                self.assertEqual(len({tuple((k, v) for k, v in row.items() if k not in look) for row in rows}), 1)
                for level, row in zip(presets.LEVELS, rows):
                    if level != 'Medium':
                        self.assertEqual(tuple(row[k] for k in look), expected[level])
                    self.assertEqual(effective_strength(ability, -4, level), max(45, ability - 2))

    def test_templates_are_anonymous_and_tiers_equal_across_levels(self):
        reference = presets.preset('Medium')['blocks']
        for level in presets.LEVELS:
            source = presets.preset(level)
            self.assertEqual(len(source['blocks']), 24)
            self.assertNotRegex(source['text'], r'(?m)^.*\+.*"')
            if level == 'High':
                self.assertEqual(source['text'].count(source['raw_acceleration']), 2)
            for tier in reference:
                if tier != 'Default':
                    self.assertEqual(source['blocks'][tier], reference[tier])
        self.assertEqual(bot_parameters(70, 70)['ReactionTime'], .01)
        self.assertEqual(bot_parameters(80, 80)['ReactionTime'], .0001)
        precise = {'firepower': 99, 'clutching': 99, 'entrying': 50, 'opening': 50}
        self.assertEqual(classify_tier(87, 'rifle', precise), 'ProPrecise')
        self.assertEqual(bot_parameters(87, 87, stats=precise)['ReactionTime'], .01)

    def test_regeneration_retains_career_tier_stats_and_hash_contract(self):
        team = fake_team('A', 87)
        for player in team['players']:
            player['stats'].update(firepower=99, clutching=99, entrying=50, opening=50)
        match = build_request(team, fake_team('B', 82), 'A0', 'de_mirage', 'ct')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            install_match_avatars(root, match)
            old = None
            for level in presets.LEVELS:
                manifest = generate_match_vpk(root, match, level, root/'cache')
                self.assertTrue(active_manifest(root)['valid'])
                self.assertEqual(manifest['difficulty_model'], presets.MODEL)
                current = [(b['player_id'], b['effective_strength'], b['tier'], b['stats']) for b in manifest['bots']]
                if old is not None:
                    self.assertEqual(current, old)
                old = current
                db = read_db(root/'overrides/botprofile.vpk')
                self.assertEqual(len(re.findall(r'(?m)^.*"C2C_', db)), 9)
                for bot in manifest['bots']:
                    self.assertIn(_profile_block(bot), db)
                    self.assertEqual(bot['profile_hash'], hashlib.sha256(_profile_block(bot).encode()).hexdigest())
                for key in ('difficulty_model', 'preset_source_hash', 'template_hash'):
                    changed = dict(manifest, **{key: 'tampered'})
                    self.assertNotEqual(_manifest_hash(changed), manifest['manifest_hash'])
                path = root/'overrides/botprofile.manifest.json'
                altered = dict(manifest, template_hash='tampered')
                path.write_text(json.dumps(altered), encoding='utf-8')
                self.assertFalse(active_manifest(root)['valid'])

    def test_form_and_growth_select_tier_not_difficulty(self):
        for level in presets.LEVELS:
            self.assertEqual(classify_tier(effective_strength(74, 2, level)), 'ProSteady')
            self.assertEqual(classify_tier(effective_strength(75, -2, level)), 'ProSlow')
            self.assertEqual(classify_tier(effective_strength(85, 0, level)), 'ProFast')
            with self.assertRaises(ValueError):
                effective_strength(float('nan'), 0, level)

    def test_medium_anonymous_tuning_matches_extracted_groups(self):
        expected = {
            64: (9000, 900, 99, 9000, 990, 90),
            70: (2000, 300, 50, 5000, 500, 30),
            80: (5500, 1150, 100, 5500, 1150, 50),
            87: (7000, 700, 50, 7000, 2000, 40),
        }
        look = [k for k in presets.PARAMETER_KEYS if k.startswith('LookAngle')]
        for rating, params in expected.items():
            self.assertEqual(tuple(bot_parameters(rating, rating)[k] for k in look), params)
        self.assertEqual(bot_parameters(94,94)['LookAngleDampingAttacking'], 39.95)
        self.assertEqual(bot_parameters(95,95)['LookAngleDampingAttacking'], 39.9)
        self.assertEqual(bot_parameters(98,98)['LookAngleDampingAttacking'], 39.7)
        for rating in (90,94,95,98):
            self.assertEqual(bot_parameters(rating,rating)['LookAngleMaxAccelNormal'], presets.preset('High')['raw_acceleration'])

    def test_entry_prefers_rifle_without_losing_rusher_personality(self):
        from cs2career.cs2.profiles import ROLE_STYLE
        self.assertEqual(ROLE_STYLE['entry'], ('RiflePro','RusherPersonality'))
        source = presets.preset('Medium')['text']
        rifle = re.search(r'(?ms)^Template RiflePro\s*\n(.*?)^End', source)[1]
        self.assertLess(rifle.index('ak47'), rifle.index('p90'))
