"""Panel commands and V5 export use isolated data; never open or modify CS2."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cs2career.career.career import Career
from cs2career.career import skins


class CosmeticsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='cosmetics-tests-', dir='D:/CS2CareerBuilds')
        self.env = patch.dict(os.environ, {
            'CS2CAREER_SAVE_DIR': str(Path(self.folder.name)/'save'),
            'CS2CAREER_EXTENSION_DIR': str(Path(self.folder.name)/'extensions'),
            'CS2CAREER_NO_GAME': '1',
        })
        self.env.start()
        self.career = Career()
        self.career.save = lambda: None
        self.career.money = 50000
        self.kit = skins.sticker_catalog()['stickers'][0]['def']
        self.addCleanup(self.env.stop)
        self.addCleanup(self.folder.cleanup)

    def weapon(self):
        self.career.buy_skin('ak-redline')
        return self.career.inventory[-1]

    def test_export_zero_parameters_and_fifth_sticker_anchor(self):
        row = self.weapon()
        row.update(wear=0.0, seed=0, stattrak=0, nametag='我的步枪')
        self.career.craft_skin(row['id'], [{'def': self.kit, 'slot': 4, 'schema': 0,
                                          'wear': 0, 'rotation': -90, 'x': 0, 'y': 0}])
        self.career.equip_skin(row['id'], 't')
        payload = skins.equipped_v5_body(self.career.inventory, {}, self.career.equipped_t)['tWeapons']['7']
        self.assertEqual(0, payload['wear'])
        self.assertEqual(0, payload['seed'])
        self.assertEqual(0, payload['stattrak'])
        self.assertEqual('我的步枪', payload['nametag'])
        self.assertEqual(4, payload['stickers'][0]['slot'])
        self.assertEqual(0, payload['stickers'][0]['schema'])
        before = payload['hash']
        self.career.craft_skin(row['id'], [])
        payload = skins.equipped_v5_body(self.career.inventory, {}, self.career.equipped_t)['tWeapons']['7']
        self.assertNotEqual(before, payload['hash'])
        self.assertEqual([], payload['stickers'])
        self.assertEqual(payload['hash'], skins._item_payload(self.career.inventory[-1])['hash'])

    def test_edit_is_free_and_rejected_edit_does_not_mutate(self):
        row = self.weapon()
        money = self.career.money
        self.career.craft_skin(row['id'], [{'def': self.kit, 'slot': 0}])
        self.assertEqual(money, self.career.money)
        saved = self.career.inventory[-1]
        self.assertEqual(saved['hash'], skins._item_payload(saved)['hash'])
        snapshot = deepcopy(self.career.inventory)
        for stickers in ([{'def': self.kit, 'slot': 0, 'x': 100}],
                         [{'def': self.kit, 'slot': 0}, {'def': self.kit, 'slot': 0}],
                         [{'def': self.kit, 'slot': 0, 'schema': 999}],
                         [{'def': self.kit, 'slot': 0, 'rotation': float('nan')}],
                         [{'def': 4294967295, 'slot': 0}]):
            with self.subTest(stickers=stickers), self.assertRaises(ValueError):
                self.career.craft_skin(row['id'], stickers)
            self.assertEqual(snapshot, self.career.inventory)

    def test_four_free_packs_are_idempotent_and_cannot_mint_money(self):
        shop = skins.shop_public(self.career)
        self.assertEqual({'donk', 'zywoo', 'monesy', 'niko'}, {p['player'] for p in shop['loadout_packs']})
        before_money = self.career.money
        for pack in shop['loadout_packs']:
            self.career.import_loadout(pack['id'])
            before = deepcopy((self.career.inventory, self.career.skin_seq))
            self.career.import_loadout(pack['id'])
            self.assertEqual(before, (self.career.inventory, self.career.skin_seq))
        self.assertEqual(before_money, self.career.money)
        self.assertTrue(all(p['imported'] for p in skins.shop_public(self.career)['loadout_packs']))
        for item in self.career.inventory:
            self.assertTrue(item['bound'])
            self.assertLessEqual(item['wear'], item['max_float'])
            self.assertGreaterEqual(item['wear'], item['min_float'])
            with self.assertRaises(ValueError):
                self.career.sell_skin(item['id'])
            self.assertEqual(before_money, self.career.money)
        self.assertEqual(len(self.career.inventory), len({r['id'] for r in self.career.inventory}))
        self.assertEqual({}, self.career.equipped_t)
        self.assertEqual({}, self.career.equipped_ct)

    def test_save_reload_preserves_source_and_attachment(self):
        pack = skins.pro_bundle()['packs'][0]
        self.career.import_loadout(pack['id'])
        item = next(r for r in self.career.inventory if r['slot'] == 'ak47')
        self.career.craft_skin(item['id'], [{'def': self.kit, 'slot': 0, 'wear': .2}])
        del self.career.save
        self.career.save()
        restored = Career.load()
        self.assertEqual(self.career.inventory, restored.inventory)
        self.assertEqual(self.career.skin_seq, restored.skin_seq)
        restored.save = lambda: None
        restored.import_loadout(pack['id'])
        self.assertEqual(self.career.inventory, restored.inventory)

    def test_expanded_packs_export_verified_knife_gloves_and_sidearms(self):
        expected = {
            'donk': (8, (515, 415), (5034, 10033)),
            'zywoo': (8, (507, 416), (5030, 1410)),
            'monesy': (8, (515, 415), (5034, 10033)),
            'niko': (9, (515, 619), (5034, 10033)),
        }
        from cs2career import skin_art
        artwork = skin_art.manifest()['items']
        for pack in skins.pro_bundle()['packs']:
            with self.subTest(player=pack['player']):
                count, knife_pair, glove_pair = expected[pack['player']]
                self.assertEqual(count, len(pack['items']))
                self.career.import_loadout(pack['id'])
                items = [r for r in self.career.inventory if r['source_pack_id'] == pack['id']]
                by_slot = {r['slot']: r for r in items}
                self.assertTrue({'knife', 'gloves', 'usp', 'glock', 'deagle'} <= set(by_slot))
                selected = {slot: by_slot[slot]['id'] for slot in ('knife', 'gloves')}
                body = skins.equipped_v5_body(items, selected, selected)
                for team in ('2', '3'):
                    for field, pair in (('knives', knife_pair), ('gloves', glove_pair)):
                        applied = body[field][team]
                        self.assertEqual(pair, (applied['def'], applied['paint']))
                        self.assertEqual([], applied['stickers'])
                for item in items:
                    self.assertEqual({'wear': None, 'seed': None}, item['source_parameters'])
                    self.assertEqual({'wear': 'declared_default', 'seed': 'declared_default'}, item['parameter_origin'])
                    art = artwork[item['skin_id']]
                    self.assertEqual('mapped', art['status'])
                    self.assertEqual((item['def'], item['paint']), (art['def'], art['paint']))

    def test_expanded_pack_adds_missing_items_and_keeps_existing_craft(self):
        data = skins.pro_bundle()
        pack = data['packs'][0]
        legacy = {**pack, 'items': pack['items'][:3]}
        with patch.object(skins, 'pro_bundle', return_value={**data, 'packs': [legacy]}):
            self.career.import_loadout(pack['id'])
        item = self.career.inventory[0]
        with patch.object(skins, 'sync_live'):
            self.career.craft_skin(item['id'], [{'def': self.kit, 'slot': 0, 'rotation': 12}])
        before = deepcopy(self.career.inventory)
        money = self.career.money
        self.assertFalse(skins.public_loadouts(self.career)[0]['imported'])
        self.career.import_loadout(pack['id'])
        self.assertEqual(before, self.career.inventory[:3])
        self.assertEqual(8, len(self.career.inventory))
        self.assertEqual(money, self.career.money)
        self.assertTrue(skins.public_loadouts(self.career)[0]['imported'])

    def test_old_unknown_sticker_can_load_and_be_removed(self):
        row = self.weapon()
        row['stickers'] = [{'def': 999999, 'slot': 0, 'wear': .1}]
        before = deepcopy(row['stickers'])
        skins.repair_items(self.career.inventory)
        self.assertEqual(before, row['stickers'])
        del self.career.save
        self.career.save()
        restored = Career.load()
        restored.save = lambda: None
        self.assertEqual(before, restored.inventory[-1]['stickers'])
        restored.craft_skin(row['id'], [])
        self.assertEqual([], restored.inventory[-1]['stickers'])

    def test_http_requires_session_and_validates_commands(self):
        from cs2career.web.server import create_server
        row = self.weapon()
        career = self.career

        from application_double import ApplicationDouble
        class FixtureState(ApplicationDouble):
            def __init__(self):
                self.career = career
            def persist(self):
                pass
            def payload(self, msg=''):
                return {'ok': True, 'msg': msg, 'state': {'career': {'skins': skins.shop_public(career)}}}

        server = create_server(FixtureState())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            def post(path, body, token=server.token):
                req = Request(base+path, data=json.dumps(body).encode(),
                              headers={'Content-Type': 'application/json', 'X-Career-Token': token})
                with urlopen(req, timeout=5) as reply:
                    return json.load(reply)
            snapshot = deepcopy(career.inventory)
            with self.assertRaises(HTTPError) as missing:
                post('/api/skins/craft', {'id': row['id'], 'stickers': []}, 'wrong')
            self.assertEqual(403, missing.exception.code)
            self.assertEqual(snapshot, career.inventory)
            with self.assertRaises(HTTPError) as invalid:
                post('/api/skins/craft', {'id': row['id'], 'stickers': [], 'money': 10})
            self.assertEqual(400, invalid.exception.code)
            result = post('/api/skins/craft', {'id': row['id'], 'stickers': [{'def': self.kit, 'slot': 0}]})
            self.assertTrue(result['ok'])
            self.assertEqual(self.kit, result['state']['career']['skins']['inventory'][0]['stickers'][0]['def'])
            result = post('/api/skins/loadout', {'id': skins.pro_bundle()['packs'][0]['id']})
            self.assertTrue(result['ok'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)


if __name__ == '__main__':
    unittest.main()
