"""Deploy into a temporary mock game tree, never the player's CS2 installation."""
import hashlib
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
        (self.csgo/'gameinfo.gi').write_text(
            '"GameInfo"\n{\n\t"FileSystem"\n\t{\n\t\t"SearchPaths"\n\t\t{\n'
            '\t\t\tGame csgo\n\t\t}\n\t}\n}\n', encoding='utf-8')
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

    def test_install_preserves_current_configs_instead_of_legacy_mod_templates(self):
        from cs2career.cs2.gameinfo import patched_gameinfo
        mod = self.root/'mod'
        for name in ('addons/metamod', 'addons/counterstrikesharp', 'overrides', 'backup/WithBots'):
            (mod/name).mkdir(parents=True)
        for name in ('gameinfo.gi', 'gameinfo_branchspecific.gi', 'backup/WithBots/gameinfo.gi'):
            (mod/name).write_text('GameInfo { LayeredOnMod removed_csgo_core }', encoding='utf-8')
        (mod/'addons/metamod/mock-plugin.dat').write_bytes(b'mock plugin')
        before = (self.csgo/'gameinfo.gi').read_text('utf-8')
        branch = self.csgo/'gameinfo_branchspecific.gi'
        branch.write_bytes(b'official branch-specific config')
        with patch.object(launch, 'settings', return_value=dict(launch.DEFAULTS)), \
             patch.object(launch, '_copy_career_match', return_value=0), \
             patch.object(launch, '_deploy_tactical_playbook', return_value=0), \
             patch.object(launch, '_copy_botbuy_patch', return_value=0), \
             patch.object(launch, 'hook_competitive_cfg'), patch.object(launch, 'apply_bothider_config'):
            self.assertTrue(launch.install_mod(self.csgo, mod)['ok'])
        self.assertEqual(patched_gameinfo(before), (self.csgo/'gameinfo.gi').read_text('utf-8'))
        self.assertEqual(b'official branch-specific config', branch.read_bytes())
        self.assertFalse((self.csgo/'backup/WithBots/gameinfo.gi').exists())
        self.assertEqual(b'mock plugin', (self.csgo/'addons/metamod/mock-plugin.dat').read_bytes())

    def test_process_detection_keeps_low_memory_startup_but_excludes_zero_handle_residue(self):
        with patch.object(launch,'_powershell',return_value='7,19') as shell:
            self.assertEqual([7,19],launch.live_cs2_pids())
        self.assertNotIn('WorkingSet',shell.call_args.args[0])
        self.assertIn('HandleCount -ne 0',shell.call_args.args[0])
        with patch.object(launch,'_powershell',return_value='0') as shell:
            self.assertEqual(0.0, launch.cs2_started_at())
        self.assertIn('HandleCount -ne 0', shell.call_args.args[0])

    def test_installer_copies_dotnet_host_but_not_upstream_desktop_apps(self):
        mod = self.root / 'mod'
        for area in ('addons/metamod', 'addons/counterstrikesharp/dotnet', 'overrides'):
            (mod / area).mkdir(parents=True)
        host = 'addons/counterstrikesharp/dotnet/dotnet.exe'
        for name in (host, 'Panel.exe', 'addons/BotController/helper.exe'):
            target = mod / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'fixture executable, never run')
        with patch.object(launch, 'settings', return_value=dict(launch.DEFAULTS)), \
             patch.object(launch, '_copy_career_match', return_value=0), \
             patch.object(launch, '_deploy_tactical_playbook', return_value=0), \
             patch.object(launch, '_copy_botbuy_patch', return_value=0), \
             patch.object(launch, 'hook_competitive_cfg'), patch.object(launch, 'apply_bothider_config'):
            self.assertTrue(launch.install_mod(self.csgo, mod)['ok'])
        self.assertTrue((self.csgo / host).is_file())
        self.assertFalse((self.csgo / 'Panel.exe').exists())
        self.assertFalse((self.csgo / 'addons/BotController/helper.exe').exists())

    def test_compatible_randomizer_cannot_be_downgraded_by_old_parked_copy(self):
        mod = self.root / 'cache/cohort/runtime'
        relative = 'addons/counterstrikesharp/plugins/BotRandomizer/'
        hashes = {}
        for name in ('BotRandomizer.dll', 'BotRandomizer.deps.json', 'cosmetic_catalog.json', 'charm_placements.json'):
            target = mod / relative / name
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = ('new-compatible-' + name).encode()
            target.write_bytes(payload)
            hashes[relative + name] = hashlib.sha256(payload).hexdigest()
        (mod.parent / 'RUNTIME_COMPAT_RECEIPT.json').write_text(json.dumps({
            'schema_version': 1, 'components': [{'name': 'BotRandomizer', 'version': '1.3.2'}],
            'files': hashes}), encoding='utf-8')
        parked = launch._plugin_parked(self.csgo, 'BotRandomizer')
        parked.mkdir(parents=True)
        (parked / 'BotRandomizer.dll').write_bytes(b'old-parked')
        with patch.object(launch, 'settings', return_value={**launch.DEFAULTS, 'mod_source_path': str(mod)}):
            self.assertEqual(4, launch.restore_bot_randomizer(self.csgo))
            self.assertEqual(b'new-compatible-BotRandomizer.dll',
                             (launch._plugin_live(self.csgo, 'BotRandomizer') / 'BotRandomizer.dll').read_bytes())
            self.assertEqual(b'old-parked', (parked / 'BotRandomizer.dll').read_bytes())
            (mod / relative / 'BotRandomizer.dll').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, '未恢复旧插件'):
                launch.restore_bot_randomizer(self.csgo)
            self.assertEqual(b'new-compatible-BotRandomizer.dll',
                             (launch._plugin_live(self.csgo, 'BotRandomizer') / 'BotRandomizer.dll').read_bytes())

    def test_missing_compatible_cache_never_autofills_an_old_release(self):
        mod = self.root / 'runtime-cache/cohort/runtime'
        cfg = {**launch.DEFAULTS, 'mod_source_path': str(mod)}
        with patch.object(launch, 'find_steam_exe', return_value=''), \
             patch.object(launch, 'find_csgo_path', return_value=''), \
             patch.object(launch, 'find_mod_source', side_effect=AssertionError('do not fall back to old source')):
            self.assertEqual(str(mod), launch._autofill(cfg)['mod_source_path'])
        with patch.object(launch, 'settings', return_value=cfg):
            with self.assertRaisesRegex(ValueError, '重新安装'):
                launch.restore_bot_randomizer(self.csgo)
        self.assertFalse(launch._plugin_live(self.csgo, 'BotRandomizer').exists())

    def test_full_prepare_three_difficulties_never_launches_game(self):
        from cs2career.cs2.profiles import active_manifest, read_db, PROFILE_RE
        from cs2career.cs2.gameinfo import patched_gameinfo
        from test_v15_core import fake_team
        for path in ('addons/metamod','addons/counterstrikesharp','addons/BotHider'):
            (self.csgo/path).mkdir(parents=True,exist_ok=True)
        mod=self.root/'mod'; mod.mkdir()
        legacy_template = mod/'backup'/'WithBots'/'gameinfo.gi'
        legacy_template.parent.mkdir(parents=True)
        legacy_template.write_text('GameInfo { LayeredOnMod csgo_core }', encoding='utf-8')
        current_gameinfo = (self.csgo/'gameinfo.gi').read_text(encoding='utf-8')
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
            self.assertEqual(9,len(PROFILE_RE.findall(read_db(self.csgo/'overrides/career_botprofile.vpk'))))
            self.assertEqual(9,len(json.loads((self.csgo/'addons/BotHider/bot_info.json').read_text())['players']))
            self.assertIn('测试战队',(self.csgo/'cfg/career_rules.cfg').read_text(encoding='utf-8'))
            self.assertEqual(patched_gameinfo(current_gameinfo),
                             (self.csgo/'gameinfo.gi').read_text(encoding='utf-8'))
            self.assertNotIn('LayeredOnMod', (self.csgo/'gameinfo.gi').read_text(encoding='utf-8'))

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

    def _existing_buy_fixture(self):
        from test_v15_core import fake_team
        for relative in ('addons/metamod', 'addons/counterstrikesharp', 'addons/BotHider'):
            (self.csgo / relative).mkdir(parents=True, exist_ok=True)
        mod = self.root / 'mod'; mod.mkdir()
        launch._copy_career_match(self.csgo)
        target = launch._plugin_live(self.csgo, 'BotBuy')
        target.mkdir(parents=True)
        (target / 'BotBuy.dll').write_bytes(b'installed-career.10')
        (target / 'BotBuy.deps.json').write_text('{}', encoding='utf-8')
        a, b = fake_team('A', 90), fake_team('B', 86)
        a['players'][0]['role'] = 'awp'
        return mod, target, a, b

    def test_3d_existing_plugins_refreshes_bundled_buy_offline_before_match(self):
        mod, target, a, b = self._existing_buy_fixture()
        # This exact presence-only check previously passed while CS2 loaded
        # career.10 and ignored the new human_role=awp request.
        launch.require_existing_plugin(self.csgo, 'BotBuy')
        self.assertEqual(b'installed-career.10', (target / 'BotBuy.dll').read_bytes())
        for suffix in ('dll', 'deps.json'):
            (target / ('BotBuy.' + suffix + '.career-backup')).write_bytes(b'original-upstream-backup')
        personal = self.csgo / 'cfg/autoexec.cfg'
        personal.parent.mkdir(parents=True); personal.write_bytes(b'player crosshair and keys')
        settings = self.csgo / 'addons/counterstrikesharp/configs/plugins/BotBuy/BotBuy.json'
        settings.parent.mkdir(parents=True); settings.write_bytes(b'personal settings')
        with patch.object(launch.urllib.request, 'urlopen', side_effect=AssertionError('no network')), \
             patch.object(launch, 'install_mod', side_effect=AssertionError('no full reinstall')), \
             patch.object(launch, '_prepare_match_skins', return_value={}), \
             patch.object(launch, 'launch_cs2', side_effect=AssertionError('no Steam launch')):
            before = None
            for _ in range(2):
                request = launch.build_request(a, b, 'A0', 'de_anubis', 't')
                launch.prepare_game(self.csgo, mod, request, dict(launch.DEFAULTS), existing_plugins=True)
                saved = json.loads((self.dst / 'match_request.json').read_text('utf-8'))
                self.assertEqual('awp', saved['human_role'])
                for name in ('BotBuy.dll', 'BotBuy.deps.json'):
                    self.assertEqual((launch.vendor_root() / 'BotBuy' / name).read_bytes(), (target / name).read_bytes())
                    self.assertEqual(b'original-upstream-backup', (target / (name + '.career-backup')).read_bytes())
                stamps = [(target / name).stat().st_mtime_ns for name in ('BotBuy.dll', 'BotBuy.deps.json')]
                if before is not None:
                    self.assertEqual(before, stamps, 'Unchanged adapter must not be rewritten on the next launch')
                before = stamps
        self.assertEqual(b'player crosshair and keys', personal.read_bytes())
        self.assertEqual(b'personal settings', settings.read_bytes())

    def test_3d_locked_buy_update_prevents_steam_dispatch(self):
        mod, target, a, b = self._existing_buy_fixture()
        steam = self.root / 'steam.exe'; steam.write_bytes(b'fixture only')
        cfg = dict(launch.DEFAULTS, steam_exe=str(steam), csgo_path=str(self.csgo), mod_source_path=str(mod))
        request = launch.build_request(a, b, 'A0', 'de_anubis', 't')
        with patch.object(launch, '_arm_cs2_environment', return_value='generation'), \
             patch.object(launch, '_finish_cs2_environment') as restore, \
             patch.object(launch, '_spawn_cs2_environment_watch'), \
             patch.object(launch, '_copy_botbuy_patch', side_effect=PermissionError('locked BotBuy.dll')), \
             patch.object(launch, 'launch_cs2') as steam_start:
            with self.assertRaisesRegex(PermissionError, 'locked BotBuy'):
                launch.start_match(a, b, 'A0', 'de_anubis', 't', config=cfg,
                                   request_override=request, existing_plugins=True)
            steam_start.assert_not_called()
            restore.assert_called_once_with(self.csgo, 'generation')
        self.assertEqual(b'installed-career.10', (target / 'BotBuy.dll').read_bytes())

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
        self.assertIn('bot_ignore_radio 0',cfg)
