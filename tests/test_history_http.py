"""Exercise the authenticated API links with repeated yearly calendar IDs."""
import json
import threading
import unittest
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import test_history_identity as fixtures
from cs2career.web.server import create_server


class HistoryHttpTests(unittest.TestCase):
    def setUp(self):
        self.state, _ = fixtures.HistoryIdentityTests().repeated_seasons()
        self.server = create_server(self.state)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join()
        self.server.server_close()

    def get(self, path):
        req = Request(f'http://127.0.0.1:{self.server.server_port}' + path,
                      headers={'X-Career-Token': self.server.token})
        with urlopen(req, timeout=5) as response:
            return json.load(response)

    def test_directory_event_node_and_match_links_round_trip(self):
        directory = self.get('/api/events')
        self.assertEqual(2, len(directory))
        seen = []
        for row in directory:
            event = self.get('/api/event?id=' + quote(row['id']))
            detail = self.get('/api/match?id=' + quote(event['matches'][0]['id']))
            self.assertEqual(event['id'], detail['event']['id'])
            self.assertEqual(10, len(detail['match']['totals']))
            seen.append(detail['match']['maps'][0]['score'])
        self.assertEqual(['13-7', '13-9'], seen)

    def test_unknown_year_is_not_redirected_to_this_year(self):
        for path in ('/api/event?id=2025::old-event', '/api/match?id=2025::match-one'):
            with self.assertRaises(HTTPError) as exc:
                self.get(path)
            self.assertEqual(404, exc.exception.code)
