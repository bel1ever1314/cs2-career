"""Manual update checks use mocked metadata only, never GitHub or real saves."""
import importlib
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from tools import career3d_runtime_updates as updates


class Response(io.BytesIO):
    def __init__(self, payload, *, advertised_length=None, status=200):
        super().__init__(payload)
        self.status = status
        self.headers = {} if advertised_length is None else {
            'Content-Length': str(advertised_length)}
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


def release(version='v1.4.6', **changes):
    return {'name': 'Bot Improver release', 'tag_name': version,
            'html_url': updates.RELEASES_URL + '/tag/' + version,
            'draft': False, 'prerelease': False, **changes}


class RuntimeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.local = patch.object(updates, '_local_version', return_value='1.4.5').start()
        self.network = patch.object(updates.urllib.request, 'urlopen').start()
        self.addCleanup(patch.stopall)

    def respond(self, data, **options):
        payload = data if isinstance(data, bytes) else json.dumps(data).encode('utf-8')
        response = Response(payload, **options)
        self.network.return_value = response
        return response

    def test_only_explicit_check_sends_one_metadata_request(self):
        self.respond(release())
        self.network.assert_not_called()
        result = updates.check_updates()
        self.assertTrue(result['checked'])
        self.assertTrue(result['update_available'])
        self.assertEqual(result['version'], '1.4.6')
        self.assertEqual(result['current_version'], '1.4.5')
        self.network.assert_called_once()
        request = self.network.call_args.args[0]
        self.assertEqual(request.full_url, updates.LATEST_API)
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(request.get_header('Accept'), 'application/vnd.github+json')
        self.assertEqual(request.get_header('X-github-api-version'), '2026-03-10')
        self.assertEqual(self.network.call_args.kwargs, {'timeout': 8})

    def test_import_does_not_query_or_touch_settings(self):
        with patch.object(updates.urllib.request, 'urlopen') as network:
            importlib.reload(updates)
            network.assert_not_called()

    def test_local_version_comes_from_reviewed_manifest(self):
        self.local.stop()
        manifest = {'components': [{'name': 'Other', 'version': '999'},
                                    {'name': 'CS2 Bot Improver', 'version': '1.4.5'}]}
        with patch.object(updates, 'load_runtime_manifest', return_value=manifest):
            self.assertEqual(updates._local_version(), '1.4.5')
        self.network.assert_not_called()

    def test_numeric_comparison_not_lexical(self):
        self.respond(release('v1.4.10'))
        self.assertTrue(updates.check_updates()['update_available'])

    def test_same_and_older_releases_never_request_install(self):
        for version in ('v1.4.5', 'v1.4.4', 'v1.4.5.0'):
            with self.subTest(version=version):
                self.respond(release(version))
                result = updates.check_updates()
                self.assertTrue(result['checked'])
                self.assertFalse(result['update_available'])

    def test_unmarked_preview_tag_is_not_stable(self):
        for version in ('v1.5.0-preview.1', 'v1.5.0-rc1', 'v1.5.0-beta', 'latest'):
            with self.subTest(version=version):
                self.respond(release(version))
                result = updates.check_updates()
                self.assertFalse(result['checked'])
                self.assertFalse(result['update_available'])
                self.assertIn('正式版本', result['reason'])

    def test_prerelease_and_draft_flags_are_rejected(self):
        for flags in ({'prerelease': True}, {'draft': True}, {'draft': 'false'},
                      {'prerelease': None}):
            with self.subTest(flags=flags):
                self.respond(release(**flags))
                result = updates.check_updates()
                self.assertFalse(result['checked'])
                self.assertFalse(result['update_available'])

    def test_failure_is_friendly_and_does_not_leak_proxy_details(self):
        for error in (URLError('private proxy password=example'), TimeoutError(), OSError()):
            with self.subTest(error=type(error).__name__):
                self.network.side_effect = error
                result = updates.check_updates()
                self.assertFalse(result['checked'])
                self.assertFalse(result['update_available'])
                self.assertIn('不影响本地安装', result['reason'])
                self.assertNotIn('password', result['reason'])

    def test_http_rate_limit_no_retry(self):
        for status in (403, 429):
            with self.subTest(status=status):
                self.network.reset_mock()
                self.network.side_effect = HTTPError(updates.LATEST_API, status, 'limit', {}, None)
                result = updates.check_updates()
                self.assertIn('限制', result['reason'])
                self.network.assert_called_once()

    def test_no_release_is_not_reported_as_up_to_date(self):
        self.network.side_effect = HTTPError(updates.LATEST_API, 404, 'missing', {}, None)
        result = updates.check_updates()
        self.assertFalse(result['checked'])
        self.assertIn('没有可检查', result['reason'])

    def test_other_http_error_is_friendly(self):
        self.network.side_effect = HTTPError(updates.LATEST_API, 500, 'failure', {}, None)
        self.assertIn('不影响本地安装', updates.check_updates()['reason'])

    def test_response_is_bounded_even_without_length_header(self):
        response = self.respond(b'x' * (updates.MAX_RESPONSE_BYTES + 20))
        self.assertFalse(updates.check_updates()['checked'])
        self.assertEqual(response.read_sizes, [updates.MAX_RESPONSE_BYTES + 1])

    def test_advertised_oversized_payload_is_not_read(self):
        response = self.respond(b'{}', advertised_length=updates.MAX_RESPONSE_BYTES + 1)
        self.assertFalse(updates.check_updates()['checked'])
        self.assertEqual(response.read_sizes, [])

    def test_malformed_release_metadata_is_not_a_success(self):
        for data in (b'{', b'\xff', b'[]', b'null', {},
                     release(html_url='https://example.com/download'),
                     release(html_url='https://github.com@evil.invalid/download'),
                     release(html_url='https://github.com/ed0ard/CS2-Bot-Improver/releases/tag/v1?x=1'),
                     release(html_url=updates.RELEASES_URL + '/tag/v1#fragment')):
            with self.subTest(data=data):
                self.respond(data)
                result = updates.check_updates()
                self.assertFalse(result['checked'])
                self.assertFalse(result['update_available'])

    def test_version_read_failure_does_not_network(self):
        self.local.side_effect = ValueError('malformed manifest')
        result = updates.check_updates()
        self.assertFalse(result['checked'])
        self.network.assert_not_called()

    def test_version_missing_does_not_network(self):
        self.local.return_value = 'unknown'
        self.assertFalse(updates.check_updates()['checked'])
        self.network.assert_not_called()

    def test_release_title_falls_back_and_is_size_limited(self):
        self.respond(release(name=None))
        self.assertEqual(updates.check_updates()['title'], 'CS2 Bot Improver v1.4.6')
        self.respond(release(name='abc ' * 100))
        self.assertLessEqual(len(updates.check_updates()['title']), 160)

    def test_only_metadata_no_file_or_save_writes(self):
        self.respond(release(assets=[{'browser_download_url': 'https://example.com/file.zip'}]))
        with patch('pathlib.Path.write_text', side_effect=AssertionError('no writes')), \
             patch('pathlib.Path.write_bytes', side_effect=AssertionError('no writes')), \
             patch('subprocess.Popen', side_effect=AssertionError('no installer')):
            self.assertTrue(updates.check_updates()['checked'])
        self.network.assert_called_once()


if __name__ == '__main__':
    unittest.main()
