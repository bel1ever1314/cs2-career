"""Deploy into a temporary mock game tree, never the player's CS2 installation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cs2career.cs2 import launch


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root/'vendor'; self.src.mkdir()
        (self.src/'CareerMatch.dll').write_bytes(b'MZnew-plugin')
        (self.src/'CareerMatch.deps.json').write_text('{}',encoding='utf-8')
        self.csgo = self.root/'game'/'csgo'
        self.dst = launch.plugin_dir(self.csgo); self.dst.mkdir(parents=True)
        for target, value in [('career_match_src',self.src),('cs2_is_live',False)]:
            mock = patch.object(launch,target,return_value=value); mock.start(); self.addCleanup(mock.stop)

    def test_copy_verified_and_unchanged_not_replaced(self):
        dll=self.dst/'CareerMatch.dll'; dll.write_bytes(b'MZold-plugin')
        self.assertEqual(2,launch._copy_career_match(self.csgo))
        self.assertEqual(b'MZold-plugin',(self.dst/'CareerMatch.dll.career-backup').read_bytes())
        stamp=dll.stat().st_mtime_ns
        self.assertEqual(0,launch._copy_career_match(self.csgo))
        self.assertEqual(stamp,dll.stat().st_mtime_ns)

    def test_missing_or_locked_plugin_is_a_blocker_not_silent_success(self):
        with patch.object(launch.os,'replace',side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError): launch._copy_career_match(self.csgo)
        self.assertFalse(list(self.dst.glob('*.tmp')))
        (self.src/'CareerMatch.deps.json').unlink()
        with self.assertRaises(FileNotFoundError): launch._copy_career_match(self.csgo)
        self.assertFalse((self.dst/'CareerMatch.dll').exists())

    def test_running_game_rejects_deployment_before_copy(self):
        with patch.object(launch,'cs2_is_live',return_value=True):
            with self.assertRaisesRegex(ValueError,'退出 CS2'):
                launch._copy_career_match(self.csgo)
        self.assertFalse(list(self.dst.iterdir()))

    def test_process_detection_keeps_low_memory_startup_but_excludes_zero_handle_residue(self):
        with patch.object(launch,'_powershell',return_value='7,19') as shell:
            self.assertEqual([7,19],launch.live_cs2_pids())
        self.assertNotIn('WorkingSet',shell.call_args.args[0])
        self.assertIn('HandleCount -ne 0',shell.call_args.args[0])
        with patch.object(launch,'_powershell',return_value='0') as shell:
            self.assertEqual(0.0, launch.cs2_started_at())
        self.assertIn('HandleCount -ne 0', shell.call_args.args[0])

    def test_full_prepare_three_difficulties_never_launches_game(self):
        from cs2career.cs2.profiles import active_manifest, read_db, PROFILE_RE
        from test_v15_core import fake_team
        for path in ('addons/metamod','addons/counterstrikesharp','addons/BotHider'):
            (self.csgo/path).mkdir(parents=True,exist_ok=True)
        mod=self.root/'mod'; mod.mkdir()
        a,b=fake_team('A',90),fake_team('B',86)
        a['name']='测试战队'
        for level in ('Low','Medium','High'):
            request=launch.build_request(a,b,'A0','de_mirage','ct')
            with patch.object(launch,'install_skins_plugin',return_value=0), patch.object(launch,'launch_cs2') as start:
                launch.prepare_game(self.csgo,mod,request,dict(launch.DEFAULTS,difficulty=level))
                start.assert_not_called()
            saved=json.loads((self.dst/'match_request.json').read_text(encoding='utf-8'))
            self.assertTrue(saved['match_chat']['enabled'])
            self.assertEqual(11, len(saved['match_chat']['rules']))
            self.assertEqual(1, len(saved['match_chat']['scenes']))
            manifest=active_manifest(self.csgo)
            self.assertTrue(manifest['valid'])
            self.assertEqual(level,manifest['difficulty'])
            self.assertEqual(saved['nonce'],manifest['nonce'])
            self.assertEqual(9,len(PROFILE_RE.findall(read_db(self.csgo/'overrides/botprofile.vpk'))))
            self.assertEqual(9,len(json.loads((self.csgo/'addons/BotHider/bot_info.json').read_text())['players']))
            self.assertIn('测试战队',(self.csgo/'cfg/career_rules.cfg').read_text(encoding='utf-8'))

    def test_failed_launch_does_not_create_phantom_result_session(self):
        from cs2career.career import Career
        from cs2career.league.season import Season
        from test_v15_core import fake_team
        a,b=fake_team('A',80),fake_team('B',82)
        season=Season.__new__(Season)
        season.teams=[a,b]
        season.year=2026
        season.date='2026-03-01'
        season.career=Career()
        season.career.exists=True
        season.career.team_id=a['id']
        season.career.player_name='A0'
        season.career.gate_match=lambda *args:''
        match={'id':'m','team_a':'A','team_b':'B','pending_map':'mirage','maps':[]}
        event={'id':'launch-test','name':'Launch Test','type':'t2','matches':[match]}
        season.events=[event]
        with patch.object(season,'_require_yours',return_value=(event,match)), \
             patch.object(season,'open_your_series'), \
             patch('cs2career.league.season.read_result',return_value={}), \
             patch('cs2career.league.season.start_match',side_effect=PermissionError('locked DLL')):
            with self.assertRaises(PermissionError): season.launch_your_map('m')
        self.assertNotIn('cs2_session',match)

    def test_observer_full_prepare_ten_avatars_and_quota(self):
        from cs2career.cs2.profiles import active_manifest
        from test_v15_core import fake_team
        for path in ('addons/metamod','addons/counterstrikesharp','addons/BotHider'):
            (self.csgo/path).mkdir(parents=True,exist_ok=True)
        mod=self.root/'mod';mod.mkdir()
        request=launch.build_lobby_request(fake_team('A',90),fake_team('B',86),'','de_dust2','observer')
        with patch.object(launch,'install_skins_plugin',return_value=0),patch.object(launch,'launch_cs2') as start:
            launch.prepare_game(self.csgo,mod,request,dict(launch.DEFAULTS))
            start.assert_not_called()
        saved=json.loads((self.dst/'match_request.json').read_text('utf-8'))
        self.assertTrue(saved['observer']);self.assertEqual('',saved['human_player_id'])
        self.assertEqual(10,len(saved['bots']))
        self.assertEqual(10,active_manifest(self.csgo)['count'])
        self.assertTrue(active_manifest(self.csgo)['valid'])
        cfg=(self.csgo/'cfg/career_rules.cfg').read_text('utf-8')
        self.assertIn('bot_quota 10',cfg);self.assertIn('mp_forcecamera 0',cfg)
