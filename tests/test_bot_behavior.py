"""Career identity VPKs retain the reviewed 1.4.5 behavior resources."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from zlib import crc32

from cs2career.cs2 import bot_behavior
from cs2career.cs2.launch import build_lobby_request, build_request, install_match_avatars
from cs2career.cs2.profiles import generate_match_vpk, read_db, vpk_bytes
from tools.career3d_package_sources import source_files
from test_v15_core import fake_team


def entries(blob):
    signature, version, tree_size, data_size, _, md5_size, signature_size = struct.unpack_from('<IIIIIII', blob)
    assert signature == 0x55AA1234 and version == 2 and md5_size == 48 and signature_size == 0
    assert len(blob) == 28 + tree_size + data_size + 48
    end, cursor = 28 + tree_size, 28
    def string():
        nonlocal cursor
        stop = blob.index(b'\0', cursor, end)
        text = blob[cursor:stop].decode()
        cursor = stop + 1
        return text
    result = {}
    while (ext := string()):
        while (folder := string()):
            while (name := string()):
                crc, preload, archive, offset, length, terminator = struct.unpack_from('<IHHIIH', blob, cursor)
                assert preload == 0 and archive == 0x7FFF and terminator == 0xFFFF
                cursor += 18
                payload = blob[end + offset:end + offset + length]
                assert len(payload) == length and crc32(payload) == crc
                path = ('' if folder == ' ' else folder + '/') + name + '.' + ext
                assert path not in result
                result[path] = payload
    assert cursor == end
    assert blob[-48:-32] == hashlib.md5(blob[28:end]).digest()
    assert blob[-32:-16] == hashlib.md5(b'').digest()
    assert blob[-16:] == hashlib.md5(blob[:-16]).digest()
    return result


class BotBehaviorTests(unittest.TestCase):
    def test_upstream_resources_are_checked_and_cached_without_player_names(self):
        for level in bot_behavior.LEVELS:
            resources = bot_behavior.resources(level)
            self.assertEqual(set(resources), bot_behavior.RESOURCE_PATHS)
            self.assertTrue(all(0 < len(p) < 65536 for p in resources.values()))
            resources.clear()
            self.assertEqual(len(bot_behavior.resources(level)), 2)
        self.assertNotEqual(bot_behavior.resources('Low'), bot_behavior.resources('High'))
        with self.assertRaises(ValueError):
            bot_behavior.resources('../High')

    def test_modified_or_misdirected_resource_rejects(self):
        bot_behavior._resources.cache_clear()
        real = bot_behavior.data_file
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'changed.kv3'
            target.write_text('changed', encoding='utf-8')
            with patch.object(bot_behavior, 'data_file', side_effect=lambda name:
                              target if name.endswith('bt_config_Low.kv3') else real(name)):
                with self.assertRaisesRegex(ValueError, '校验失败'):
                    bot_behavior.resources('Low')
        bot_behavior._resources.cache_clear()

    def test_writer_deterministic_and_legacy_single_entry_still_valid(self):
        self.assertEqual(entries(vpk_bytes('fixture')), {'botprofile.db': b'fixture'})
        resources = bot_behavior.resources('Medium')
        blob = vpk_bytes('fixture', resources)
        self.assertEqual(entries(blob), {'botprofile.db': b'fixture', **resources})
        self.assertEqual(blob, vpk_bytes('fixture', dict(reversed(list(resources.items())))))
        for path in ('botprofile.db', '../payload.kv3', 'scripts/other.kv3'):
            with self.assertRaises(ValueError):
                vpk_bytes('fixture', {path: b'bad'})

    def test_generated_nine_and_ten_rosters_keep_behavior_and_identity_hash(self):
        for observer in (False, True):
            match = (build_lobby_request(fake_team('A', 87), fake_team('B', 82), '', 'de_dust2', 'fixture')
                     if observer else build_request(fake_team('A', 87), fake_team('B', 82), 'A0', 'de_dust2', 'ct'))
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                install_match_avatars(root, match)
                for level in bot_behavior.LEVELS:
                    manifest = generate_match_vpk(root, match, level, root / 'cache')
                    active = root / 'overrides/botprofile.vpk'
                    payload = active.read_bytes()
                    packed = entries(payload)
                    self.assertEqual(set(packed), {'botprofile.db', *bot_behavior.RESOURCE_PATHS})
                    self.assertEqual({p: packed[p] for p in bot_behavior.RESOURCE_PATHS}, bot_behavior.resources(level))
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest['vpk_sha256'])
                    db = read_db(active)
                    self.assertEqual(db, packed['botprofile.db'].decode())
                    self.assertEqual(len(manifest['bots']), 10 if observer else 9)
                    self.assertEqual(db.count('"C2C_'), 10 if observer else 9)

    def test_behavior_scripts_are_in_public_source_selection(self):
        root = Path(__file__).resolve().parents[1]
        selected = {p.relative_to(root).as_posix() for p in source_files(root)}
        for name in ('bt_default.kv3', 'bt_config_Low.kv3', 'bt_config_Medium.kv3', 'bt_config_High.kv3', 'resources.json'):
            self.assertIn('cs2career/data/botprofile_behavior/' + name, selected)


if __name__ == '__main__':
    unittest.main()
