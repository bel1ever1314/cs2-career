"""No watcher child, Steam process, real game file or Career save is touched."""
from copy import deepcopy
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import career3d_backend_main, career3d_cs2_watchdog as watchdog
from cs2career.cs2 import process_state


class Clock:
    def __init__(self):
        self.value = 100.0
    def now(self):
        return self.value
    def sleep(self, seconds):
        self.value += seconds


def lease(mode='dispatch', **watch):
    return dict(schema_version=1, mode='enhanced', generation='generation-one',
                watch=dict(active=True, mode=mode, owner_pid=20,
                           started_at='1970-01-01T00:01:40Z', **watch))


class WatchLoopTests(unittest.TestCase):
    def run_loop(self, table=None, *, running=None, owner=None, finish=None, iterations=3, interval=1):
        clock = Clock()
        read = Mock(return_value=table or lease())
        finish = finish or Mock(return_value=dict(status='restored'))
        if isinstance(running, list):
            probe = Mock(side_effect=running)
        else:
            probe = Mock(return_value=running)
        owner_probe = Mock(return_value=owner)
        outcome = watchdog.run_watch(Path('X:/isolated-game/csgo'), 'generation-one',
            read=read, finish=finish, probe=probe, owner_probe=owner_probe,
            clock=clock.now, sleep=clock.sleep, max_iterations=iterations, interval=interval)
        return outcome, finish, probe, owner_probe, read

    def test_running_then_exit_restores_once_even_if_owner_has_already_closed(self):
        out, finish, _, owner, _ = self.run_loop(running=[True, True, False], owner=False)
        self.assertEqual('restored', out['status'])
        self.assertTrue(out['seen_running'])
        finish.assert_called_once_with(Path('X:/isolated-game/csgo'), 'generation-one')
        owner.assert_not_called()

    def test_unseen_dispatch_restores_only_after_90_seconds(self):
        out, finish, _, _, _ = self.run_loop(running=False, iterations=10, interval=10)
        self.assertEqual('restored', out['status'])
        self.assertEqual(10, out['iterations'])
        finish.assert_called_once()
        out, finish, _, _, _ = self.run_loop(running=False, iterations=9, interval=10)
        self.assertEqual('waiting', out['status'])
        finish.assert_not_called()

    def test_slow_preparation_is_not_treated_as_an_expired_worker_at_spawn(self):
        table = lease()
        table['watch']['started_at'] = '1970-01-01T00:00:01Z'
        out, finish, _, _, _ = self.run_loop(table, running=False, iterations=2)
        self.assertEqual('waiting', out['status'])
        finish.assert_not_called()

    def test_unknown_never_restores_even_after_timeout_and_owner_exit(self):
        out, finish, _, owner, _ = self.run_loop(lease('manual'), running=None,
                                               owner=False, iterations=3, interval=90)
        self.assertEqual('waiting', out['status'])
        finish.assert_not_called()
        owner.assert_not_called()
        out, finish, _, _, _ = self.run_loop(running=[True, None, None], iterations=3, interval=90)
        self.assertEqual('waiting', out['status'])
        finish.assert_not_called()

    def test_manual_without_game_does_not_expire_while_owner_is_open(self):
        out, finish, _, _, _ = self.run_loop(lease('manual'), running=False,
                                            owner=True, iterations=3, interval=90)
        self.assertEqual('waiting', out['status'])
        finish.assert_not_called()

    def test_manual_owner_exit_without_game_restores(self):
        out, finish, _, owner, _ = self.run_loop(lease('manual'), running=False, owner=False)
        self.assertEqual('restored', out['status'])
        finish.assert_called_once()
        owner.assert_called_once_with(20)

    def test_manual_owner_unknown_is_not_exit_permission(self):
        out, finish, _, _, _ = self.run_loop(lease('manual'), running=False, owner=None)
        self.assertEqual('waiting', out['status'])
        finish.assert_not_called()

    def test_new_generation_stops_old_watch_without_process_probe_or_write(self):
        table = lease()
        table['generation'] = 'a-new-generation'
        out, finish, probe, _, _ = self.run_loop(table, running=False)
        self.assertEqual('superseded', out['status'])
        finish.assert_not_called()
        probe.assert_not_called()

    def test_already_normal_or_inactive_has_no_write(self):
        for normal in (True, False):
            table = lease()
            if normal:
                table['mode'] = 'normal'
            else:
                table['watch']['active'] = False
            out, finish, probe, _, _ = self.run_loop(table, running=False)
            self.assertEqual('superseded', out['status'])
            finish.assert_not_called()
            probe.assert_not_called()

    def test_finish_guard_race_or_permissions_fail_are_retried_without_assuming_success(self):
        finish = Mock(side_effect=[ValueError('a new CS2 started'), PermissionError('temporarily locked'),
                                   dict(status='restored')])
        out, _, _, _, _ = self.run_loop(lease(seen_running=True), running=False, finish=finish)
        self.assertEqual('restored', out['status'])
        self.assertEqual(3, finish.call_count)

    def test_unreadable_lease_and_process_probe_failures_are_retried(self):
        clock = Clock()
        read = Mock(side_effect=[PermissionError('antivirus holds state'), lease(), lease(), lease()])
        probe = Mock(side_effect=[OSError('query failed'), True, False])
        finish = Mock(return_value=dict(status='restored'))
        out = watchdog.run_watch(Path('X:/isolated-game/csgo'), 'generation-one',
            read=read, probe=probe, finish=finish, clock=clock.now, sleep=clock.sleep,
            max_iterations=4)
        self.assertEqual('restored', out['status'])
        self.assertEqual(4, out['iterations'])
        finish.assert_called_once()

    def test_unreadable_owner_does_not_grant_manual_restore(self):
        finish = Mock()
        watchdog.run_watch(Path('X:/isolated-game/csgo'), 'generation-one',
            read=lambda _: lease('manual'), probe=lambda: False, finish=finish,
            owner_probe=Mock(side_effect=PermissionError('owner inaccessible')),
            clock=lambda: 100, sleep=lambda _: None, max_iterations=2)
        finish.assert_not_called()


class WorkerEntryTests(unittest.TestCase):
    def test_source_spawn_uses_hidden_independent_process_with_only_requested_directory(self):
        popen = Mock()
        with patch.object(sys, 'frozen', False, create=True):
            watchdog.spawn_watch(Path('X:/isolated game/csgo'), 'g-one', popen=popen)
        command = popen.call_args.args[0]
        options = popen.call_args.kwargs
        self.assertEqual(sys.executable, command[0])
        self.assertIn('--generation', command)
        self.assertEqual('g-one', command[-1])
        self.assertIn('career3d_cs2_watchdog.py', command[2])
        self.assertTrue(options['close_fds'])
        for stream in ('stdin', 'stdout', 'stderr'):
            self.assertEqual(subprocess.DEVNULL, options[stream])
        if os.name == 'nt':
            self.assertEqual(0x08000200, options['creationflags'])
        else:
            self.assertTrue(options['start_new_session'])

    def test_frozen_spawn_uses_backend_watchdog_flag_not_a_second_game_window(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / 'CareerBackend.exe'
            exe.write_bytes(b'not executable; Popen is mocked')
            popen = Mock()
            with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(exe)):
                watchdog.spawn_watch(Path(folder) / 'game/csgo', 'generation-test', popen=popen)
            command = popen.call_args.args[0]
            self.assertEqual([str(exe), '--cs2-environment-watchdog'], command[:2])

    def test_bad_spawn_identity_is_rejected_without_subprocess(self):
        popen = Mock()
        for args in (dict(generation=''), dict(generation='g', mode='wrong'),
                     dict(generation='g', owner_pid=0)):
            with self.assertRaises(ValueError):
                watchdog.spawn_watch(Path('X:/fixture'), popen=popen, **args)
        popen.assert_not_called()

    def test_backend_watchdog_branch_never_imports_application_service(self):
        fake_worker = SimpleNamespace(main=Mock(return_value=0))
        with patch.dict(sys.modules, {'tools.career3d_cs2_watchdog': fake_worker}):
            self.assertEqual(0, career3d_backend_main.main([
                '--cs2-environment-watchdog', '--csgo-path', 'X:/fixture', '--generation', 'g']))
        fake_worker.main.assert_called_once_with(['--csgo-path', 'X:/fixture', '--generation', 'g'])

    def test_fresh_pure_imports_do_not_load_business_or_create_save_directory(self):
        code = """
import sys
def audit(event, args):
    if event == 'os.mkdir':
        raise AssertionError('pure worker must not mkdir')
sys.addaudithook(audit)
import cs2career.cs2
import cs2career.cs2.process_state
import cs2career.cs2.environment
import tools.career3d_backend_main
import tools.career3d_cs2_watchdog
assert 'cs2career.cs2.launch' not in sys.modules
assert 'cs2career.application' not in sys.modules
assert 'tools.career3d_service' not in sys.modules
assert 'cs2career.paths' not in sys.modules
print('pure imports ok')
"""
        out = subprocess.run([sys.executable, '-B', '-c', code],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, out.returncode, out.stderr)
        self.assertIn('pure imports ok', out.stdout)

    def test_original_public_exports_are_retained_after_lazy_import(self):
        from cs2career import cs2
        from cs2career.cs2 import launch, result
        for name in cs2.__all__:
            with self.subTest(name=name):
                source = result if name in cs2._RESULT_EXPORTS else launch
                self.assertIs(getattr(source, name), getattr(cs2, name))


class NativeProcessProbeTests(unittest.TestCase):
    def kernel(self, *, handle=25, waited=258):
        return SimpleNamespace(OpenProcess=Mock(return_value=handle),
            WaitForSingleObject=Mock(return_value=waited), CloseHandle=Mock(return_value=True))

    def test_process_object_that_has_exited_is_not_a_live_cs2(self):
        kernel = self.kernel(waited=0)
        self.assertIs(False, process_state._windows_process_running(40, kernel))
        kernel.WaitForSingleObject.assert_called_once_with(25, 0)
        kernel.CloseHandle.assert_called_once_with(25)

    def test_live_process_and_unknown_wait_are_distinguished(self):
        for waited, expected in ((258, True), (0xFFFFFFFF, None), (128, None)):
            with self.subTest(waited=waited):
                kernel = self.kernel(waited=waited)
                self.assertIs(expected, process_state._windows_process_running(40, kernel))
                kernel.CloseHandle.assert_called_once_with(25)

    def test_absent_process_and_access_denial_are_distinguished(self):
        for error, expected in ((87, False), (1168, False), (5, None)):
            with self.subTest(error=error), patch.object(ctypes, 'get_last_error', return_value=error, create=True):
                kernel = self.kernel(handle=0)
                self.assertIs(expected, process_state._windows_process_running(40, kernel))
                kernel.WaitForSingleObject.assert_not_called()
                kernel.CloseHandle.assert_not_called()

    def test_invalid_owner_pid_is_not_assumed_to_be_closed(self):
        for pid in (None, False, True, 0, -1, '20'):
            self.assertIsNone(process_state.process_running(pid))

    def test_enumeration_ignores_ghost_cs2_and_preserves_unknowns(self):
        def first(_handle, entry):
            entry._obj.szExeFile = 'cs2.exe'
            entry._obj.th32ProcessID = 123
            return True
        for probe, expected in ((False, False), (None, None), (True, True)):
            with self.subTest(probe=probe):
                kernel = SimpleNamespace(CreateToolhelp32Snapshot=Mock(return_value=25),
                    Process32FirstW=Mock(side_effect=first), Process32NextW=Mock(return_value=False),
                    CloseHandle=Mock(return_value=True))
                with patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), \
                     patch.object(ctypes, 'get_last_error', return_value=18, create=True), \
                     patch.object(process_state, '_windows_process_running', return_value=probe):
                    self.assertIs(expected, process_state._windows_cs2_running())
                kernel.CloseHandle.assert_called_once_with(25)

    def test_snapshot_errors_are_not_an_empty_process_list(self):
        kernel = SimpleNamespace(CreateToolhelp32Snapshot=Mock(return_value=ctypes.c_void_p(-1).value),
            Process32FirstW=Mock(), Process32NextW=Mock(), CloseHandle=Mock())
        with patch.object(ctypes, 'WinDLL', return_value=kernel, create=True):
            self.assertIsNone(process_state._windows_cs2_running())
        kernel.Process32FirstW.assert_not_called()
        kernel.CloseHandle.assert_not_called()

    def test_failed_enumeration_is_unknown_instead_of_a_closed_game(self):
        kernel = SimpleNamespace(CreateToolhelp32Snapshot=Mock(return_value=25),
            Process32FirstW=Mock(return_value=False), Process32NextW=Mock(), CloseHandle=Mock())
        with patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), \
             patch.object(ctypes, 'get_last_error', return_value=5, create=True):
            self.assertIsNone(process_state._windows_cs2_running())
        kernel.CloseHandle.assert_called_once_with(25)


class IntegratedLeaseWorkerTests(unittest.TestCase):
    def setUp(self):
        from cs2career.cs2 import environment
        self.environment = environment
        temporary = tempfile.TemporaryDirectory(prefix='watchdog-fixture-')
        self.addCleanup(temporary.cleanup)
        self.csgo = Path(temporary.name) / 'game/csgo'
        (self.csgo / 'cfg').mkdir(parents=True)
        self.gi = self.csgo / 'gameinfo.gi'
        self.original = (b'GameInfo\n{\n\tFileSystem\n\t{\n\t\tSearchPaths\n\t\t{\n'
                         b'\t\t\tGame csgo\n\t\t\tGame core\n\t\t}\n\t}\n}\n')
        self.gi.write_bytes(self.original)
        (self.csgo / 'cfg/career_rules.cfg').write_bytes(b'// fixture, never executed\n')
        (self.csgo / 'cfg/gamemode_competitive.cfg').write_bytes(b'// Valve cfg\n')
        context = patch.object(process_state, 'cs2_running', return_value=False)
        context.start()
        self.addCleanup(context.stop)

    def test_real_lease_is_restored_after_worker_observes_exit(self):
        active = self.environment.switch_environment(self.csgo, 'enhanced', watch_mode='dispatch')
        self.assertNotEqual(self.original, self.gi.read_bytes())
        outcome = watchdog.run_watch(self.csgo, active['generation'],
            probe=Mock(side_effect=[True, False]), sleep=lambda _: None, max_iterations=2)
        self.assertEqual('restored', outcome['status'])
        self.assertEqual(self.original, self.gi.read_bytes())
        self.assertEqual('normal', self.environment.read_lease(self.csgo)['mode'])
        self.assertFalse(self.environment.read_lease(self.csgo)['watch']['active'])

    def test_new_real_lease_supersedes_old_worker_without_mutation(self):
        old = self.environment.switch_environment(self.csgo, 'enhanced', watch_mode='manual')
        new = self.environment.switch_environment(self.csgo, 'enhanced', watch_mode='dispatch')
        before = self.gi.read_bytes()
        probe = Mock(return_value=False)
        outcome = watchdog.run_watch(self.csgo, old['generation'], probe=probe, max_iterations=1)
        self.assertEqual('superseded', outcome['status'])
        probe.assert_not_called()
        self.assertEqual(before, self.gi.read_bytes())
        self.assertEqual(new['generation'], self.environment.read_lease(self.csgo)['generation'])

    def test_match_arm_extracts_generation_from_real_environment(self):
        from cs2career.cs2 import launch
        generation = launch._arm_cs2_environment(self.csgo)
        lease = self.environment.read_lease(self.csgo)
        self.assertEqual(generation, lease['generation'])
        self.assertEqual('dispatch', lease['watch']['mode'])
        self.assertEqual(os.getpid(), lease['watch']['owner_pid'])


class MatchEnvironmentDispatchTests(unittest.TestCase):
    def setUp(self):
        from cs2career.cs2 import launch
        self.launch = launch
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.steam = self.root / 'steam.exe'
        self.steam.write_bytes(b'never executed')
        self.csgo = self.root / 'game/csgo'
        self.cfg = dict(launch.DEFAULTS, steam_exe=str(self.steam), csgo_path=str(self.csgo),
                        mod_source_path=str(self.root / 'mod'))
        self.request = dict(human_team='ct', map='de_dust2', nonce='game-one',
            movement_style=dict(active='classic'), bot_profile=dict(count=9, short_hash='fixture'))
        for context in (patch.object(launch, 'settings', return_value=self.cfg),
                        patch.object(launch, '_arm_cs2_environment', return_value='lease-one'),
                        patch.object(launch, '_finish_cs2_environment'),
                        patch.object(launch, '_spawn_cs2_environment_watch'),
                        patch.object(launch, 'prepare_game'),
                        patch.object(launch, 'launch_cs2', return_value='launched')):
            context.start()
            self.addCleanup(context.stop)

    def start(self):
        return self.launch.start_match(dict(name='A'), dict(name='B'), 'Player', 'de_dust2', 'ct',
                                       request_override=deepcopy(self.request))

    def test_dispatch_arms_prepares_launches_then_spawns_one_worker(self):
        out = self.start()
        self.assertEqual('lease-one', out['match']['environment_generation'])
        self.launch._arm_cs2_environment.assert_called_once_with(self.csgo)
        self.launch._spawn_cs2_environment_watch.assert_called_once_with(self.csgo, 'lease-one')
        self.launch._finish_cs2_environment.assert_not_called()
        self.launch.launch_cs2.assert_called_once_with(str(self.steam))

    def test_prepare_dispatch_and_spawn_failures_restore_and_rethrow(self):
        for boundary in ('prepare_game', 'launch_cs2', '_spawn_cs2_environment_watch'):
            with self.subTest(boundary=boundary):
                self.launch._finish_cs2_environment.reset_mock()
                target = getattr(self.launch, boundary)
                target.side_effect = PermissionError(boundary + ' failed')
                with self.assertRaisesRegex(PermissionError, boundary + ' failed'):
                    self.start()
                self.launch._finish_cs2_environment.assert_called_once_with(self.csgo, 'lease-one')
                target.side_effect = None

    def test_partly_dispatched_live_game_gets_a_watch_instead_of_unsafe_restore(self):
        self.launch.launch_cs2.side_effect = RuntimeError('partial Steam dispatch')
        self.launch._finish_cs2_environment.side_effect = ValueError('CS2 still running')
        with self.assertRaisesRegex(RuntimeError, 'partial Steam dispatch'):
            self.start()
        self.launch._spawn_cs2_environment_watch.assert_called_once_with(self.csgo, 'lease-one')


if __name__ == '__main__':
    unittest.main()
