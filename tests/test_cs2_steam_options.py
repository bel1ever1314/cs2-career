"""Persistent Steam launch-option checks in temporary, synthetic directories."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs2career.cs2 import steam_options


def config(apps='', extra=''):
    return ('"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { '
            '"Apps" { ' + apps + ' } } } } ' + extra + ' }')


class SteamLaunchOptionsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='steam-options-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.exe = self.root / 'Steam' / 'steam.exe'
        self.exe.parent.mkdir()
        self.exe.write_bytes(b'never executed')
        (self.exe.parent / 'userdata').mkdir()
        with steam_options._CACHE_LOCK:
            steam_options._CACHE.clear()

    def write_account(self, account, text):
        path = self.exe.parent / 'userdata' / str(account) / 'config' / 'localconfig.vdf'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8') if isinstance(text, str) else text)
        return path

    def status(self):
        result = steam_options.launch_options_status(str(self.exe))
        self.assertEqual({'checked', 'insecure', 'reason'}, set(result))
        return result

    def test_normal_no_flag_is_checked_without_warning(self):
        path = self.write_account(1234, config('"730" { "LaunchOptions" "-novid +fps_max 144" }'))
        before = path.read_bytes()
        self.assertEqual(dict(checked=True, insecure=False, reason=''), self.status())
        self.assertEqual(before, path.read_bytes())

    def test_persistent_insecure_uses_fixed_warning_without_private_fields(self):
        self.write_account(987654, config('"730" { "LaunchOptions" "-novid -insecure" }'))
        result = self.status()
        self.assertTrue(result['checked'])
        self.assertTrue(result['insecure'])
        self.assertEqual(steam_options.INSECURE_REASON, result['reason'])
        for private in ('987654', '-novid', str(self.root)):
            self.assertNotIn(private, repr(result))

    def test_any_account_insecure_warns(self):
        self.write_account(1, config('"730" { "LaunchOptions" "" }'))
        self.write_account(2, config('"730" { "LaunchOptions" "-insecure" }'))
        self.assertTrue(self.status()['insecure'])

    def test_unrelated_app_and_unrelated_key_do_not_warn(self):
        self.write_account(1, config('"570" { "LaunchOptions" "-insecure" } '
                                    '"730" { "OtherOption" "-insecure" }',
                                    '"LaunchOptions" "-insecure"'))
        self.assertEqual(dict(checked=True, insecure=False, reason=''), self.status())

    def test_wrong_subtree_named_730_does_not_warn(self):
        self.write_account(1, config('"730" { "LaunchOptions" "-novid" }',
                                    '"Other" { "730" { "LaunchOptions" "-insecure" } }'))
        self.assertFalse(self.status()['insecure'])

    def test_case_insensitive_keys_bom_crlf_and_comments(self):
        content = config('"730" { "LAUNCHOPTIONS" "-INSECURE" }')
        content = content.replace('"Software"', '"software"').replace('"Valve"', '"VALVE"')
        content = '// header\r\n' + content.replace('{', '{\r\n') + '\r\n'
        self.write_account(1, b'\xef\xbb\xbf' + content.encode())
        self.assertTrue(self.status()['insecure'])

    def test_quoted_flag_is_detected(self):
        self.write_account(1, config('"730" { "LaunchOptions" "-novid \\"-insecure\\"" }'))
        self.assertTrue(self.status()['insecure'])

    def test_flag_like_substrings_and_comment_text_do_not_warn(self):
        self.write_account(1, config('"730" { "LaunchOptions" "-insecure-extra path/-insecure.exe" } '
                                    '// "730" { "LaunchOptions" "-insecure" }\n'))
        self.assertFalse(self.status()['insecure'])

    def test_duplicate_target_keys_all_checked_not_just_first_value(self):
        self.write_account(1, config('"730" { "LaunchOptions" "-novid" "LaunchOptions" "-insecure" }'))
        self.assertTrue(self.status()['insecure'])

    def test_missing_cs2_app_or_launchoptions_is_known_absence(self):
        for apps in ('', '"570" { "LaunchOptions" "-insecure" }', '"730" { "LastPlayed" "0" }'):
            with self.subTest(apps=apps):
                self.write_account(1, config(apps))
                self.assertEqual(dict(checked=True, insecure=False, reason=''), self.status())

    def test_unnumbered_userdata_directory_is_not_read(self):
        self.write_account('not-an-account', config('"730" { "LaunchOptions" "-insecure" }'))
        self.write_account(1, config('"730" { "LaunchOptions" "" }'))
        self.assertFalse(self.status()['insecure'])

    def test_missing_steam_or_config_never_claims_checked_safe(self):
        self.assertFalse(self.status()['checked'])
        for exe in ('', str(self.root / 'missing.exe'), str(self.root), None, 730):
            with self.subTest(exe=exe):
                self.assertFalse(steam_options.launch_options_status(exe)['checked'])

    def test_wrong_executable_name_is_unknown_even_with_valid_userdata(self):
        another = self.exe.with_name('notsteam.exe')
        another.write_bytes(b'never executed')
        self.write_account(1, config())
        self.assertFalse(steam_options.launch_options_status(str(another))['checked'])

    def test_invalid_format_encoding_and_root_are_unknown(self):
        for content in ('UserLocalConfigStore { Software {',
                        'UserLocalConfigStore { Software }', 'AnotherRoot { Software {} }',
                        config() + ' /* unfinished words',
                        'UserLocalConfigStore { Software "invalid subtree" }',
                        config('"730" { "LaunchOptions" { "unsafe" "flag" } }'), b'\xff\xff'):
            with self.subTest(content=content):
                self.write_account(1, content)
                result = self.status()
                self.assertFalse(result['checked'])
                self.assertFalse(result['insecure'])
                self.assertTrue(result['reason'])

    def test_block_comments_do_not_create_a_fake_flag(self):
        self.write_account(1, config('/* "730" { "LaunchOptions" "-insecure" } */ '
                                    '"730" { "LaunchOptions" "-novid" }'))
        self.assertEqual(dict(checked=True, insecure=False, reason=''), self.status())

    def test_failed_account_does_not_hide_other_accounts_known_insecure(self):
        self.write_account(1, 'UserLocalConfigStore {')
        self.write_account(2, config('"730" { "LaunchOptions" "-insecure" }'))
        result = self.status()
        self.assertFalse(result['checked'])
        self.assertTrue(result['insecure'])
        self.assertEqual(steam_options.INSECURE_REASON, result['reason'])

    def test_locked_file_is_unknown_not_safe_and_retry_can_recover(self):
        self.write_account(1, config())
        real_open = Path.open

        def locked(path, *args, **kwargs):
            if path.name == 'localconfig.vdf':
                raise PermissionError('isolated locked Steam config')
            return real_open(path, *args, **kwargs)

        with patch.object(Path, 'open', autospec=True, side_effect=locked):
            self.assertFalse(self.status()['checked'])
        self.assertTrue(self.status()['checked'])

    def test_successful_metadata_cache_skips_reparse_and_invalidates_on_edit(self):
        path = self.write_account(1, config('"730" { "LaunchOptions" "-novid" }'))
        with patch.object(steam_options, '_has_insecure', wraps=steam_options._has_insecure) as parse:
            self.assertFalse(self.status()['insecure'])
            self.assertFalse(self.status()['insecure'])
            self.assertEqual(1, parse.call_count)
            path.write_text(config('"730" { "LaunchOptions" "-novid -insecure" }'), encoding='utf-8')
            self.assertTrue(self.status()['insecure'])
            self.assertEqual(2, parse.call_count)
        self.assertTrue(all(type(value) is bool for value in steam_options._CACHE.values()))

    def test_size_limit_rejects_before_parsing(self):
        self.write_account(1, config())
        with patch.object(steam_options, 'MAX_CONFIG_BYTES', 16), \
             patch.object(steam_options, '_has_insecure', side_effect=AssertionError('do not parse oversize')):
            self.assertFalse(self.status()['checked'])

    def test_changed_during_read_is_unknown_and_not_cached(self):
        path = self.write_account(1, config())
        original = steam_options._stamp(path)
        modified = (*original[:-1], original[-1] + 1)
        with patch.object(steam_options, '_stamp', side_effect=(original, modified)):
            self.assertFalse(self.status()['checked'])
        self.assertFalse(steam_options._CACHE)

    def test_excessive_nesting_and_tokens_are_bounded(self):
        content = 'UserLocalConfigStore { ' + 'level { ' * 65 + 'value 1 ' + '} ' * 66
        self.write_account(1, content)
        self.assertFalse(self.status()['checked'])
        self.write_account(1, config('"730" { "LaunchOptions" "-insecure" }'))
        with patch.object(steam_options, 'MAX_TOKENS', 5):
            self.assertFalse(self.status()['checked'])


if __name__ == '__main__':
    unittest.main()
