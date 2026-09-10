"""Historical roster acceptance is separate from rating/balance acceptance."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from cs2career.career import Career
from cs2career.world import build_teams, apply_roles
from cs2career.world.era_data import world_manifest, validate_world, quality_view


class IndependentEraTests(unittest.TestCase):
    def test_2025_independent_world_does_not_rebrand_or_use_future_transfers(self):
        teams = {t['name']: t for t in build_teams('2025')}
        names = {n: {p['name'] for p in t['players']} for n, t in teams.items()}
        self.assertEqual(59, len(teams))
        self.assertTrue({'Eternal Fire', 'Aurora', 'Cloud9', 'Wildcard', 'NAVI Junior', 'Spirit Academy'} <= teams.keys())
        self.assertFalse({'FUT', '100 Thieves', 'Luminosity', 'Grayhound'} & teams.keys())
        self.assertIn('XANTARES', names['Eternal Fire'])
        self.assertEqual({'clax', 'KENSI', 'Patsi', 'Norwi', 'gr1ks'}, names['Aurora'])
        self.assertIn('m0NESY', names['G2'])
        self.assertEqual({'NiKo', 'Magisk', 'TeSeS', 'degster', 'kyxsan'}, names['Falcons'])
        self.assertIn('Spinx', names['Vitality'])
        self.assertNotIn('ropz', names['Vitality'])
        self.assertNotIn('s1mple', names['FaZe'])
        self.assertIn('EliGE', names['Complexity'])
        self.assertIn('HeavyGod', names['Cloud9'])
        self.assertIn('siuhy', names['MOUZ'])
        self.assertNotIn('Jame', names['PARIVISION'])
        self.assertNotIn('Luken', names['9z'])
        self.assertTrue(all('2025 slot' in p for p in names['HEROIC']))

    def test_2025_includes_same_day_moves_but_not_next_day(self):
        teams = build_teams('2025')
        apply_roles(teams, '2025')
        by = {t['name']: t for t in teams}
        names = {n: {p['name'] for p in t['players']} for n, t in by.items()}
        self.assertIn('PR', names['GamerLegion'])
        self.assertFalse({'volt', 'REZ'} & names['GamerLegion'])
        self.assertIn('REZ', names['NiP'])
        self.assertFalse({'nawwk', 'fear', 'Burmylov'} & names['fnatic'])
        self.assertEqual({'forsyy', 'nbqq', 'Dytor', 'M1key', 'The eLiVe'}, names['ECLOT'])
        self.assertEqual({'beastik', 'SHOCK', 'MoriiSko', 'ZEDKO', 'Pepo'}, names['SINNERS'])
        self.assertIn('history', names['Fluxo'])
        self.assertNotIn('zevy', names['Fluxo'])
        self.assertEqual('provisional', quality_view(by['M80'], team=True)['status'])
        self.assertEqual('stand_in', next(p for p in by['M80']['players'] if p['name'] == 'k1to')['roster_status'])
        fallen = next(p for p in by['FURIA']['players'] if p['name'] == 'FalleN')
        self.assertTrue(fallen['is_igl'])
        self.assertEqual('awp', fallen['role'])
        ids = [p['player_id'] for t in teams for p in t['players']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_2026_axes_are_read_by_entire_2025_world(self):
        with patch('cs2career.world.ability.stats_for', side_effect=AssertionError('future statistics read')):
            teams = build_teams('2025')
        self.assertTrue(all(t['era_provenance']['ability_quality'] == 'estimated' for t in teams))

    def test_source_dates_cannot_silently_authorise_a_future_roster(self):
        raw = world_manifest('2025')
        for change in ({'published_at': '2025-01-09'}, {'observed_at': '2026-01-06'},
                       {'published_at': 'invalid'}, {'purpose': 'rumour'}):
            bad = deepcopy(raw)
            bad['teams'][0]['sources'][0].update(change)
            with self.assertRaises(ValueError):
                validate_world(bad)
        bad = deepcopy(raw)
        bad['teams'][0]['sources'][0]['purpose'] = 'exclusion'
        with self.assertRaises(ValueError):
            validate_world(bad)
        # PARIVISION/9z have later sources solely to document excluded arrivals.
        self.assertEqual(raw, validate_world(raw))

    def test_2024_has_independent_organisations_and_no_rebranded_shells(self):
        teams = {t['name']: t for t in build_teams('2024')}
        self.assertTrue({'Cloud9','Monte','Apeks','Eternal Fire','Grayhound','9 Pandas','HAVU','KOI','FORZE'} <= teams.keys())
        self.assertFalse({'100 Thieves','FUT','Luminosity','FlyQuest'} & teams.keys())
        self.assertEqual('eternal-fire', teams['Eternal Fire']['org_id'])
        self.assertEqual('aurora', teams['Aurora']['org_id'])
        self.assertIn('XANTARES', {p['name'] for p in teams['Eternal Fire']['players']})
        self.assertEqual({'Lack1','SELLTER','KENSI','Norwi','deko'}, {p['name'] for p in teams['Aurora']['players']})
        modern = {t['name'] for t in build_teams('2026')}
        self.assertIn('FlyQuest', modern)
        self.assertNotIn('Grayhound', modern)

    def test_prominent_roster_mismatches_are_corrected(self):
        teams = {t['name']: {p['name'] for p in t['players']} for t in build_teams('2024')}
        self.assertEqual({'Snappi','Magisk','Maden','SunPayus','BOROS'}, teams['Falcons'])
        self.assertEqual({'EliGE','JT','floppy','hallzerk','Grim'}, teams['Complexity'])
        self.assertEqual({'Twistzz','NAF','skullz','cadiaN','YEKINDAR'}, teams['Liquid'])
        self.assertEqual({'sjuush','TeSeS','nicoodoz','NertZ','kyxsan'}, teams['HEROIC'])
        self.assertEqual({'device','stavn','blameF','jabbi','Staehr'}, teams['Astralis'])
        self.assertEqual({'advent','kaze','JamYoung','Mercury','Moseyuh'}, teams['TYLOO'])
        self.assertEqual({'Westmelon','z4KR','Starry','Jee','EmiliaQAQ'}, teams['Lynn Vision'])

    def test_roles_preserve_dual_caller_no_awp_and_provisional_status(self):
        teams = build_teams('2024')
        apply_roles(teams, '2024')
        by_name = {t['name']: t for t in teams}
        self.assertFalse(any(p['role'] == 'awp' for p in by_name['Cloud9']['players']))
        jame = next(p for p in by_name['Virtus.pro']['players'] if p['name'] == 'Jame')
        self.assertTrue(jame['is_igl'])
        self.assertEqual('awp', jame['role'])
        mouz = by_name['MOUZ']
        self.assertEqual('provisional', quality_view(mouz, team=True)['status'])
        self.assertEqual('stand_in', next(p for p in mouz['players'] if p['name'] == 'Brollan')['roster_status'])

    def test_no_2026_axes_are_read_by_entire_2024_world(self):
        with patch('cs2career.world.ability.stats_for', side_effect=AssertionError('future statistics read')):
            teams = build_teams('2024')
        self.assertEqual(54, len(teams))
        self.assertTrue(all(t['era_provenance']['ability_quality'] == 'estimated' for t in teams))

    def test_manifest_rejects_cross_team_case_alias_future_and_bad_reference(self):
        raw = world_manifest('2024')
        for mutate in (
            lambda r: r['teams'][1]['players'][0].update(name='zywoo'),
            lambda r: r['teams'][1].update(observed_at='2024-01-09'),
            lambda r: r['teams'][1].update(id=r['teams'][0]['id']),
            lambda r: r['teams'][1].update(seed=900),
            lambda r: r['teams'][1]['players'][0].update(ability=float('inf')),
            lambda r: r['teams'][1]['players'][0].update(name='FaZe 2024 slot1'),
        ):
            modified = deepcopy(raw)
            mutate(modified)
            with self.assertRaises(ValueError):
                validate_world(modified)
        self.assertEqual(raw, world_manifest('2024'))

    def test_free_market_does_not_duplicate_different_case_active_name(self):
        career = Career()
        career.year = 2024
        career.save = Mock()
        teams = build_teams('2024')
        career.rebuild_free(teams)
        active = {p['player_id'] for t in teams for p in t['players']}
        self.assertFalse(active & {p['player_id'] for p in career.free})
        self.assertFalse(any(p['name'].casefold() == 'sunpayus' for p in career.free))

    def test_source_rank_is_not_compacted_game_seed(self):
        teams = {t['name']: t for t in build_teams('2024')}
        rare = quality_view(teams['Rare Atom'], team=True)
        self.assertEqual(142, rare['source_rank'])
        self.assertEqual(47, rare['game_seed'])
        self.assertIsNone(quality_view(teams['PARIVISION'], team=True)['source_rank'])

    def test_starter_teammates_exclude_active_names_case_insensitively(self):
        from cs2career.world.pool import starter_mates
        fake = [{'name':'sunpayus','role':'awp','ability':70,'region':'EU','note':'vet'},
                {'name':'Backup','role':'awp','ability':69,'region':'EU','note':'vet'}]
        with patch('cs2career.world.pool.agent_rows', return_value=fake):
            rows = starter_mates('EU', ['awp'], {'SunPayus'}, min_ability=40, max_ability=100)
        self.assertEqual('Backup', rows[0][0])
