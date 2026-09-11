"""Position strength: no preview matrix, no role-switch/growth exploits."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack

from cs2career.world.ability import (ability_of, calibrate_role, gun_score,
    refresh_player_ability, ensure_role_calibration, stats_for)
from cs2career.world.aging import apply_player_year
from cs2career.world.roles import apply_roles
from cs2career.world import build_teams
from cs2career.career.career import Career, _signed
from cs2career.engine.match import snapshot_players
from cs2career.cs2.launch import build_request, install_match_avatars
from cs2career.cs2.profiles import prepare_bots


def player(name='Role Tester', role='rifle', ability=80):
    stats = dict(firepower=80, entrying=58, trading=75, opening=64,
                 clutching=94, sniping=22, utility=62)
    calibrate_role(stats, role, ability)
    return dict(name=name, player_id='p_'+name.replace(' ', '_'), role=role,
                ability=ability, stats=stats, age=26, command=60, form_delta=-2)


class RoleAbilityTests(unittest.TestCase):
    def test_position_formulas_and_reversible_anchor(self):
        p = player(); st = p['stats']
        scores = [ability_of(st, r) for r in ('igl','lurk','rifle','awp','entry')]
        self.assertEqual(5, len(set(scores)))
        self.assertGreater(ability_of(st,'lurk'), ability_of(st,'rifle'))
        before = deepcopy(st)
        for _ in range(10):
            for role in ('igl','lurk','awp','entry','rifle'):
                p['role'] = role; refresh_player_ability(p)
                self.assertEqual(80, p['long_term_ability'])
        self.assertEqual(80, p['ability'])
        self.assertEqual(before, st)
        self.assertEqual(78, p['form'])

    def test_unclipped_scores_keep_star_role_differences(self):
        p = player(ability=96); p['stats']['firepower'] = 100
        p['stats']['trading'] = 100; p['stats']['clutching'] = 100
        calibrate_role(p['stats'], 'lurk', 96)
        self.assertGreater(gun_score(p['stats'],'lurk'),79.08)
        self.assertLess(ability_of(p['stats'],'entry'), ability_of(p['stats'],'lurk'))
        for role in ('igl','lurk','rifle','awp','entry'):
            self.assertTrue(40 <= ability_of(p['stats'],role) <= 100)

    def test_old_save_preserves_live_ability_not_stale_stats(self):
        p = player(ability=76.4)
        p['stats'].pop('role_reference_score'); p['stats'].pop('role_reference')
        p['stats']['ability'] = 85
        self.assertTrue(ensure_role_calibration(p))
        refresh_player_ability(p)
        self.assertEqual(76.4, p['ability'])
        restored = json.loads(json.dumps(p))
        self.assertFalse(ensure_role_calibration(restored))
        refresh_player_ability(restored)
        self.assertEqual(p, restored)

    def test_annual_growth_uses_baseline_and_does_not_snap_back(self):
        a = player(); b = deepcopy(a)
        b['role'] = 'entry'; refresh_player_ability(b)
        apply_player_year(a); apply_player_year(b)
        self.assertEqual(a['long_term_ability'], b['long_term_ability'])
        self.assertEqual(a['stats'], b['stats'])
        self.assertLess(a['ability'],80)
        for p in (a,b):
            before = deepcopy(p)
            refresh_player_ability(p)
            self.assertEqual(before, p)
        b['role'] = 'rifle'; refresh_player_ability(b)
        self.assertEqual(a['ability'], b['ability'])

    def fixture(self):
        players = [player(str(i),role) for i,role in enumerate(('rifle','awp','igl','entry','lurk'))]
        players[0]['you'] = True
        team = dict(id='role-club', name='Role Club',players=players,custom_roles=True,
                    command=65, strong_maps=[], weak_maps=[])
        career = Career(); career.team_id=team['id']; career.player_name='0'
        career.role='rifle'; career.exists=True; career.save=lambda:None
        return career, SimpleNamespace(teams=[team]), team

    def test_business_role_swap_and_growth(self):
        c,s,t = self.fixture(); p=t['players'][0]
        mapping = {p['name']:p['role'] for p in t['players']}
        c.set_roles(s,dict(mapping, **{'0':'lurk'}),'0')
        self.assertGreater(p['ability'],80)
        apply_roles(s.teams)
        self.assertGreater(p['ability'],80)
        before=p['ability']; c.attr_points=1
        c.spend_point(s,'clutching')
        self.assertGreater(p['ability'],before)
        self.assertEqual(0,c.attr_points)
        c.set_roles(s,mapping,'0')
        self.assertGreater(p['ability'],80)
        self.assertEqual(p['ability'],p['long_term_ability'])
        signed=_signed(p)
        self.assertEqual(p['stats'],signed['stats'])
        self.assertEqual(p['ability'],signed['ability'])

    def test_simulation_and_nine_bot_profiles_use_same_role_strength(self):
        _,_,team=self.fixture()
        opponent=deepcopy(team); opponent.update(id='opponent',name='Opponent')
        for p in opponent['players']:
            p['name']='Other'+p['name'];p['player_id']='other_'+p['player_id']
        target=team['players'][3]
        target['role']='lurk'  # Boundary must not accidentally use stale ability.
        expected=ability_of(target['stats'],'lurk')
        row=snapshot_players(team,opponent,'mirage')[3]
        self.assertEqual(expected,row['ability'])
        with tempfile.TemporaryDirectory() as raw:
            request=build_request(team,opponent,'0','de_mirage','ct')
            install_match_avatars(Path(raw),request)
            for difficulty in ('Low','Medium','High'):
                bots=prepare_bots(request,difficulty)
                self.assertEqual(9,len(bots))
                bot=next(b for b in bots if b['player_id']==target['player_id'])
                self.assertEqual(expected,bot['overall'])
                self.assertAlmostEqual(max(45,min(100,row['effective'])),bot['effective_strength'])

    def test_original_positions_keep_calibrated_star_baselines(self):
        teams=build_teams('2026',2026)
        for p in [p for t in teams for p in t['players']]:
            self.assertEqual(p['ability'],ability_of(p['stats'],p['role']))
        for name in ('ZywOo','donk','ropz'):
            p=next(p for t in teams for p in t['players'] if p['name']==name)
            before=p['ability']; refresh_player_ability(p)
            self.assertEqual(before,p['ability'])

    def test_v2_upgrade_backs_up_pair_and_role_survives_reload(self):
        from cs2career.application import ApplicationState
        with tempfile.TemporaryDirectory() as raw, ExitStack() as stack:
            root=Path(raw)
            stack.enter_context(patch('cs2career.league.season.STATE_PATH',root/'season.json'))
            stack.enter_context(patch.object(Career,'path',return_value=root/'career.json'))
            stack.enter_context(patch('cs2career.paths.save_root',return_value=root))
            state=ApplicationState()
            state.create_career(dict(era='2026',mode='create',origin='academy',
                name='Role Reload',org='Role Reload Club',region='AS',role='rifle'))
            team=state.career.my_team(state.season.teams)
            team['custom_roles']=True
            p=state.career.my_player(state.season.teams)
            p['stats'].pop('role_reference');p['stats'].pop('role_reference_score')
            p['ability']=67.2;p['stats']['ability']=74
            # A prior score-only snapshot must not be modified by live migration.
            state.season.history=[{'year':2025,'events':[], 'sentinel':{'ability':74}}]
            state.persist()
            originals={f.name:f.read_bytes() for f in root.glob('*.json')}
            state=ApplicationState()
            p=state.career.my_player(state.season.teams)
            self.assertEqual(67.2,p['ability'])
            import gzip
            self.assertTrue(any(all((folder/(name+'.gz')).is_file() and gzip.decompress((folder/(name+'.gz')).read_bytes())==data for name,data in originals.items())
                for folder in (root/'backups').iterdir()))
            mapping={p['name']:p['role'] for p in state.career.my_team(state.season.teams)['players']}
            mapping[p['name']]='lurk'
            state.career.set_roles(state.season,mapping,p['name'])
            expected=deepcopy(p); history=deepcopy(state.season.history)
            state.persist();state=ApplicationState()
            p=state.career.my_player(state.season.teams)
            for key in ('ability','long_term_ability','stats','role','form_delta'):
                self.assertEqual(expected[key],p[key])
            self.assertEqual(history,state.season.history)

    def test_player_detail_only_labels_current_role_ability(self):
        ui=(Path(__file__).resolve().parents[1]/'cs2career/web/static/desk/profiles.js').read_text(encoding='utf-8')
        self.assertIn("metric('当前位置能力',ui.num(row.ability))",ui)
        self.assertNotIn('role_ratings',ui)
