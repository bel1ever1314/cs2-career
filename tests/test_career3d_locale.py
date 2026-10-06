"""Presentation-only translations preserve records, identities and numeric slots."""
from copy import deepcopy
import json
import re
import unittest

from tools.build_career3d_locale import compile_catalogue, sources, covered, TARGET
from tools.career3d_locale import english, localize_projection


class Career3DLocaleTests(unittest.TestCase):
    def test_stable_device_messages_have_both_languages_and_matching_slots(self):
        messages = json.loads((TARGET.parent/'ui_messages.json').read_text('utf-8'))['messages']
        self.assertGreaterEqual(len(messages), 30)
        for key, value in messages.items():
            self.assertRegex(key, r'^[a-z][a-z0-9_.]+$')
            self.assertEqual({'zh', 'en'}, set(value), key)
            self.assertTrue(value['zh'] and value['en'], key)
            self.assertFalse(re.search(r'[\u3400-\u9fff]', value['en']), key)
            self.assertEqual(sorted(re.findall(r'\{([^}]+)\}', value['zh'])),
                             sorted(re.findall(r'\{([^}]+)\}', value['en'])), key)
            printf = r'%(?:[-+0 #]*\d*(?:\.\d+)?)?[sdf]'
            self.assertEqual(re.findall(printf, value['zh']), re.findall(printf, value['en']), key)

    def test_device_hosts_use_stable_copy_ids(self):
        messages = json.loads((TARGET.parent/'ui_messages.json').read_text('utf-8'))['messages']
        for name in ('career_phone.gd', 'career_computer.gd', 'device_pages.gd'):
            source = (TARGET.parent.parent/'scripts'/name).read_text('utf-8')
            for key in re.findall(r'Locale\.(?:message|source)\("([a-z0-9_.]+)"\)', source):
                self.assertIn(key, messages, (name, key))
            strings = re.findall(r'"((?:[^"\\]|\\.)*)"', source)
            self.assertFalse(any(re.search(r'[\u3400-\u9fff]', text) for text in strings), name)

    def test_catalogue_is_reproducible_and_covers_native_ui_and_rts(self):
        expected = compile_catalogue()
        self.assertEqual(expected, json.loads(TARGET.read_text('utf-8')))
        missing = [(filename, source) for source, filename in sources().items()
                   if not covered(source, expected)]
        self.assertEqual([], missing)

    def test_new_ui_templates_preserve_money_and_coordinates(self):
        self.assertEqual('Owned 12 · Placed 3', english('已购买 12 · 已摆放 3'))
        self.assertEqual('Waypoint 2 · Position -7.5, 16.2', english('路点 2 · 位置 -7.5, 16.2'))
        self.assertEqual('Success chance 75%. Failed negotiation fee $250.', english('本次成功率 75%，失败谈判费 $250。'))
        self.assertEqual('Personal funds $350', english('个人资金 $350'))

    def test_backend_projection_keeps_original_save_fields_and_identity(self):
        original = {'ok': True, 'player': {'id': 'name.1', 'name': '冠军', 'ability': 82.7},
                    'team': {'id': 'club.1', 'name': '青训', 'money': 12999},
                    'stories': [{'id': 's1', 'title': '赛事冠军', 'text': '玩家自写的中文保留',
                                 'choices': [{'id': 'accept', 'label': '继续模拟'}]}],
                    'reason': '房间布置已保存。'}
        before = deepcopy(original)
        result = localize_projection(original)
        self.assertEqual(before, original)
        self.assertEqual(before['player'], result['player'])
        self.assertEqual(before['team'], result['team'])
        self.assertEqual('Room layout saved.', result['reason_en'])
        self.assertEqual('Tournament champion', result['stories'][0]['title_en'])
        self.assertEqual('accept', result['stories'][0]['choices'][0]['id'])
        self.assertEqual('玩家自写的中文保留', result['stories'][0]['text'])
        self.assertNotIn('text_en', result['stories'][0])

    def test_existing_authored_fields_win_without_touching_chinese(self):
        value = {'title': '赛事冠军', 'title_en': 'Authored event heading',
                 'text': '未知扩展文案', 'text_en': 'Community-authored story'}
        self.assertEqual(value, localize_projection(value))

    def test_nested_templates_preserve_identity_collisions(self):
        value = {'team': {'name': '冠军', 'roster': []},
                 'title': '冠军 · 赛事荣誉记录',
                 'message': '设施升级使用俱乐部账户。'}
        projected = localize_projection(value)
        self.assertEqual('冠军 · Tournament honours record', projected['title_en'])
        self.assertEqual('Bot Improver is not installed in the selected CS2 directory.',
                         english('人机增强尚未安装到所选 CS2 目录。'))
        self.assertEqual('Facilities or furniture cannot be purchased in the current career.',
                         english('当前生涯不能购买设施或家具。'))

    def test_every_authored_template_has_valid_slots(self):
        for row in compile_catalogue()['templates']:
            with self.subTest(source=row['source']):
                re.compile(row['pattern'])
                for key in row['keys']:
                    self.assertIn('{'+str(key)+'}', row['replacement'])


if __name__ == '__main__': unittest.main()
