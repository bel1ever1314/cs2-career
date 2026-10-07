"""Opening identities, dates and calibrated skills must remain separate."""
from copy import deepcopy
import unittest

from cs2career.world import build_teams
from cs2career.world import calibrated
from cs2career.world.era_data import world_manifest, validate_world, quality_view
from tools import promote_calibration_pack as promotion
from tools.career3d_attribute_draw import source_pool


class OpeningRosterCompletionTests(unittest.TestCase):
    def test_every_retained_team_is_complete_unique_and_available_to_draw(self):
        for era, expected in [('2024', 52), ('2025', 58), ('2026', 46)]:
            with self.subTest(era=era):
                teams = build_teams(era)
                self.assertEqual(expected, len(teams))
                players = [p for t in teams for p in t['players']]
                self.assertEqual(expected * 5, len(players))
                self.assertEqual(len(players), len({p['player_id'] for p in players}))
                self.assertFalse(any(' slot' in p['name'] for p in players))
                self.assertEqual(expected * 5, len(source_pool(era, teams=teams)))
                for team in teams:
                    for player in team['players']:
                        row = calibrated.lookup(player['name'], era, team['name'])
                        self.assertIsNotNone(row)
                        self.assertFalse(row['placeholder'])

    def test_2026_uses_opening_not_midyear_teams(self):
        by = {t['name']: {p['name'] for p in t['players']} for t in build_teams('2026')}
        self.assertEqual({'JT', 'hallzerk', 'Grim', 'nicx', 'Kvem'}, by['Passion UA'])
        self.assertEqual({'KRIMZ', 'fEAR', 'jambo', 'Maden', 'jackasmo'}, by['fnatic'])
        self.assertEqual({'rain', 'device', 'Ag1l', 'sirah', 'poiii'}, by['100 Thieves'])
        self.assertEqual({'kyxsan', 'NiKo', 'm0NESY', 'kyousuke', 'TeSeS'}, by['Falcons'])
        self.assertIn('karrigan', by['FaZe'])
        self.assertIn('SunPayus', by['G2'])
        self.assertFalse({'Luminosity', 'Complexity', 'ATOX'} & by.keys())
        self.assertEqual({'SYDOX', 'jERK0z', 'tuxa', 'Moretz', 'blaze'}, by['SAW'])

    def test_explicit_january_completion_does_not_relax_strict_snapshots(self):
        raw = world_manifest('2026')
        fnatic = next(t for t in raw['teams'] if t['name'] == 'fnatic')
        self.assertEqual('2026-01-09', fnatic['roster_as_of'])
        for mutate in (
            lambda t: t.pop('roster_policy'),
            lambda t: t.update(roster_policy='anything'),
            lambda t: t.update(roster_as_of='2026-02-01', announced_at='2026-02-01'),
            lambda t: t.update(roster_as_of='2025-01-09'),
            lambda t: t.update(announced_at='2026-01-10'),
            lambda t: t['sources'][0].update(published_at='2026-07-01'),
            lambda t: t['sources'][0].pop('published_at'),
        ):
            modified = deepcopy(raw)
            mutate(next(t for t in modified['teams'] if t['name'] == 'fnatic'))
            with self.assertRaises(ValueError):
                validate_world(modified)
        self.assertEqual(raw, validate_world(raw))

    def test_actual_date_and_standin_are_exposed_without_mutating_saved_rows(self):
        saw = next(t for t in build_teams('2026') if t['name'] == 'SAW')
        original = deepcopy(saw)
        view = quality_view(saw, team=True)
        self.assertEqual('2026-01-05', view['roster_as_of'])
        self.assertEqual('2026-01-08', view['as_of'])
        self.assertEqual('provisional', view['status'])
        self.assertEqual('stand_in', next(p for p in saw['players'] if p['name'] == 'SYDOX')['roster_status'])
        self.assertEqual(original, saw)

    def test_transfers_preserve_same_era_base_and_new_people_use_no_fake_evidence(self):
        # The immutable lab snapshot predates this roster edit. Compare the
        # promoted artifact against it, not against a second copy of itself.
        import json
        lab = promotion.DEFAULT_LAB
        model = promotion._module(lab / 'calibration.py', 'opening_test_lab')
        original = promotion.compact_report(model.build_report(
            json.loads((lab / 'snapshot.json').read_text('utf-8')),
            json.loads((lab / 'parameters.json').read_text('utf-8'))), promotion._runtime())
        donors = {(p['era'], p['name'].casefold()): p for p in original['records']
                  if p['kind'] == 'world_roster' and not p['placeholder']}
        for row in calibrated.load_calibrated_pack()['records']:
            if row['kind'] != 'world_roster':
                continue
            before = donors.get((row['era'], row['name'].casefold()))
            if before:
                self.assertEqual(before['overall'], row['overall'])
                self.assertEqual(before['axes'], dict(row['axes']))
                self.assertEqual(before['reference_role'], row['reference_role'])
        newcomer = calibrated.lookup('segukawa', '2026', 'B8')
        self.assertEqual('provisional', newcomer['evidence']['level'])
        self.assertIsNone(newcomer['evidence']['top30_rating'])
        self.assertFalse(newcomer['evidence']['sources'])
        self.assertTrue(newcomer['roster_provenance']['sources'])
        self.assertNotIn('slot', newcomer['id'])


if __name__ == '__main__':
    unittest.main()
