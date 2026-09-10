import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from cs2career.web.server import create_server
from cs2career.career import Career, skins


class HttpSessionTests(unittest.TestCase):
    def setUp(self):
        self.saved = 0
        state = SimpleNamespace(career=SimpleNamespace(keep_drop=lambda: 'kept'), persist=self.persist,
                                payload=lambda msg='': {'ok': True, 'msg': msg, 'state': {}})
        self.server = create_server(state)
        self.server.preview = True
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def persist(self):
        self.saved += 1

    def tearDown(self):
        self.server.shutdown()
        self.worker.join()
        self.server.server_close()

    def request(self, path, method='GET', token=None):
        req = Request(self.base+path, data=b'{}' if method=='POST' else None, method=method,
                      headers={'X-Career-Token': token or ''})
        with urlopen(req, timeout=5) as response:
            return json.load(response)

    def test_unauthorized_read_and_write_rejected(self):
        for path, method in [('/api/state','GET'),('/api/skins/keep','POST')]:
            with self.assertRaises(HTTPError) as error:
                self.request(path,method)
            self.assertEqual(403,error.exception.code)
        self.assertEqual(0,self.saved)

    def test_preview_blocks_game_operations_and_allows_cosmetics(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/api/cs2/install','POST',self.server.token)
        self.assertEqual(403,error.exception.code)
        with self.assertRaises(HTTPError):
            self.request('/api/skins/pref','POST',self.server.token)
        result=self.request('/api/skins/keep','POST',self.server.token)
        self.assertTrue(result['ok'])
        self.assertEqual(1,self.saved)

    def test_windowed_exe_without_stderr_can_serve(self):
        with patch('sys.stderr',None):
            result=self.request('/api/state',token=self.server.token)
        self.assertTrue(result['design_preview'])

    def test_setup_exposes_dated_roster_and_unfinished_coverage_without_saving(self):
        result = self.request('/api/setup?era=2024', token=self.server.token)
        self.assertEqual(22, result['data_coverage']['placeholder_players'])
        self.assertEqual(47, result['data_coverage']['verified_rosters'])
        pari = next(t for t in result['teams'] if t['id'] == 'parivision')
        self.assertEqual('verified', pari['data_provenance']['status'])
        self.assertEqual('2024-01-08', pari['data_provenance']['as_of'])
        self.assertEqual({'Jerry','Patsi','ArtFr0st','Qikert','X5G7V'}, {p['name'] for p in pari['players']})
        self.assertEqual(0, self.saved)


    def test_setup_2025_serves_independent_rosters_and_discloses_vacancies(self):
        result = self.request('/api/setup?era=2025', token=self.server.token)
        self.assertEqual(59, result['data_coverage']['teams'])
        self.assertEqual(41, result['data_coverage']['verified_rosters'])
        self.assertEqual(28, result['data_coverage']['placeholder_players'])
        by = {t['name']: t for t in result['teams']}
        self.assertIn('Eternal Fire', by)
        self.assertNotIn('FUT', by)
        self.assertIn('Spinx', {p['name'] for p in by['Vitality']['players']})
        self.assertEqual('estimated', by['G2']['data_provenance']['status'])
        self.assertEqual(1, by['G2']['data_provenance']['placeholder_count'])
        self.assertEqual(65, by['PARIVISION']['data_provenance']['source_rank'])
        self.assertEqual('2025-01-08', by['PARIVISION']['data_provenance']['as_of'])
        self.assertEqual(0, self.saved)


class CasePersistenceTests(unittest.TestCase):
    def test_pending_drop_survives_reload_and_cannot_double_claim(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Career,'path',return_value=Path(directory)/'career.json'):
            career=Career()
            career.money=10000
            career.buy_case('rev')
            first=career.pending_drop.copy()
            balance=career.money
            career.buy_case('rev')
            self.assertEqual(balance,career.money)
            self.assertEqual(first,career.pending_drop)
            restored=Career.load()
            self.assertEqual(first,restored.pending_drop)
            restored.keep_drop()
            count=len(restored.inventory)
            restored.keep_drop()
            self.assertEqual(count,len(restored.inventory))
            self.assertEqual(balance,restored.money)


if __name__=='__main__':
    unittest.main()
