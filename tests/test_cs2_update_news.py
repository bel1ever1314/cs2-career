import io
import json
import unittest
from unittest.mock import patch
from tools import career3d_runtime_updates as updates


class Response(io.BytesIO):
    status = 200


class CS2NewsTests(unittest.TestCase):
    def query(self, timestamp, **changes):
        item = dict(feedname='steam_community_announcements',
                    title='Counter-Strike 2 Update', date=timestamp, gid='12345')
        item.update(changes)
        body = json.dumps({'appnews': {'newsitems': [item]}}).encode()
        with patch.object(updates, 'load_runtime_manifest', return_value={
                'cs2_news_baseline': {'timestamp': 100}}), patch.object(
                updates.urllib.request, 'urlopen', return_value=Response(body)):
            return updates.check_cs2_updates()

    def test_same_newer_and_nonupdate_announcements(self):
        self.assertFalse(self.query(100)['update_available'])
        newer = self.query(101)
        self.assertTrue(newer['checked'] and newer['update_available'])
        self.assertEqual('not_live_verified', newer['compatibility'])
        self.assertFalse(self.query(101, title='Esports news')['checked'])
        self.assertFalse(self.query(101, feedname='community')['checked'])

    def test_failed_game_check_keeps_successful_improver_result(self):
        with patch.object(updates, 'check_updates', return_value={
                'checked': True, 'version': '1.4.7', 'reason': 'ok'}), patch.object(
                updates, 'check_cs2_updates', return_value={'checked': False, 'reason': 'retry'}):
            result = updates.check_all_updates()
        self.assertTrue(result['checked'])
        self.assertFalse(result['cs2']['checked'])


if __name__ == '__main__':
    unittest.main()
