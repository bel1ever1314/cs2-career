import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cs2career.career import Career
from cs2career.career import incidents
from cs2career.content.loader import PackRegistry
from cs2career.content.rules import validate_payload
from cs2career.cs2.dialogue import build_dialogue

ROOT = Path(__file__).resolve().parents[1]


def event_rule(**extra):
    return {'id': 'coach', 'when': 'before_match', 'title': '虚构教练离队', 'text': '<script>只是文字</script>',
            'choices': [{'id': 'pay', 'label': '安排人手', 'effects': [{'type': 'club_money', 'amount': -100},
                         {'type': 'flag', 'key': 'replaced', 'value': True}]},
                        {'id': 'decline', 'label': '内部安排', 'effects': []}], **extra}


class DialogueIncidentTests(unittest.TestCase):
    def setUp(self):
        self.c = Career()
        self.c.exists = True
        self.c.mode = 'create'
        self.c.team_id = 'test'
        self.c.player_name = '虚构选手'
        self.c.save = Mock()
        self.s = SimpleNamespace(date='2026-02-01', teams=[{'id': 'test', 'name': '测试队', 'money': 1000, 'mentality': 70}])

    def registry(self, rows=None, overrides=None):
        return SimpleNamespace(payloads=lambda kind: [{'_pack_id': 'test.pack', 'incidents': rows or [event_rule()], 'overrides': overrides or []}] if kind == 'incidents' else [])

    def test_builtin_chat_and_pack_templates_validate(self):
        for filename in ['cs2career/data/match_chat.json', 'extensions/_templates/match-chat-pack/match_chat/example.json',
                         'extensions/_templates/incident-pack/incidents/example.json']:
            kind = 'incidents' if 'incidents/' in filename else 'match_chat'
            validate_payload(kind, json.loads((ROOT / filename).read_text('utf-8')))
        with patch('cs2career.cs2.dialogue.get_registry', return_value=self.registry()):
            before = random.getstate()
            contract = build_dialogue()
            self.assertEqual(before, random.getstate())
            self.assertEqual(11, len(contract['rules']))
            self.assertEqual(1, len(contract['scenes']))
            self.assertTrue(contract['scenes'][0]['distinct_speakers'])
            self.assertTrue(all(r['id'].startswith('builtin:') for r in contract['rules']))
            self.assertFalse(build_dialogue(False)['enabled'])
            self.assertEqual([], build_dialogue(include_builtin=False)['rules'])

    def test_scene_pack_validates_and_compiles_in_file_order(self):
        raw = json.loads((ROOT/'extensions/_templates/match-scene-pack/match_chat/example.json').read_text('utf-8'))
        validate_payload('match_chat', raw)
        registry = SimpleNamespace(payloads=lambda kind: [dict(raw, _pack_id='test.scene')])
        before = random.getstate()
        with patch('cs2career.cs2.dialogue.get_registry', return_value=registry):
            contract = build_dialogue(include_builtin=False)
        self.assertEqual(2, contract['schema_version'])
        self.assertEqual('test.scene:coach-first-round', contract['rules'][0]['id'])
        self.assertEqual('test.scene:third-round-huddle', contract['scenes'][0]['id'])
        self.assertEqual(['coach', 'teammate', 'coach'], [s['speaker'] for s in contract['scenes'][0]['sequence']])
        self.assertEqual(before, random.getstate())
        contract['scenes'][0]['sequence'][0]['text'] = 'changed'
        self.assertNotEqual('changed', raw['scenes'][0]['sequence'][0]['text'])

    def test_invalid_scene_fields_rejected(self):
        raw = json.loads((ROOT/'extensions/_templates/match-scene-pack/match_chat/example.json').read_text('utf-8'))
        scene = raw['scenes'][0]
        for change in [dict(sequence=[]), dict(sequence=scene['sequence']*3),
                       dict(conditions={'speaker_id':'abc'}), dict(priority=101)]:
            with self.assertRaises(ValueError):
                validate_payload('match_chat', {'schema_version':1, 'scenes':[dict(scene, **change)]})
        for step in [dict(scene['sequence'][0], delay_seconds=float('nan')),
                     dict(scene['sequence'][0], delay_seconds=4),
                     dict(scene['sequence'][0], text=['not a string']),
                     dict(scene['sequence'][0], text='{player.__class__}'),
                     dict(scene['sequence'][0], speaker='opponent', channel='team')]:
            with self.assertRaises(ValueError):
                validate_payload('match_chat', {'schema_version':1, 'scenes':[dict(scene, sequence=[step])]})
        with self.assertRaises(ValueError):
            validate_payload('match_chat', dict(raw, scenes=[dict(scene, id=raw['rules'][0]['id'])]))

    def test_scene_and_rule_duplicate_across_files_rejected(self):
        raw = json.loads((ROOT/'extensions/_templates/match-scene-pack/match_chat/example.json').read_text('utf-8'))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); pack = root/'scene'; (pack/'match_chat').mkdir(parents=True)
            (pack/'pack.json').write_text(json.dumps({'schema_version':1,'id':'test.scene','types':['match_chat']}))
            (pack/'match_chat/a.json').write_text(json.dumps(raw))
            (pack/'match_chat/b.json').write_text(json.dumps(raw))
            registry = PackRegistry(root)
            self.assertEqual('rejected', registry.packs[0].status)
            self.assertTrue(any('跨文件重复' in e for e in registry.packs[0].errors))

    def test_v2_rule_allows_every_round_without_global_cap(self):
        raw = json.loads((ROOT/'cs2career/data/match_chat.json').read_text('utf-8'))
        raw['rules'][0]['max_per_match'] = 200
        validate_payload('match_chat', raw)
        raw['rules'][0]['max_per_match'] = 201
        with self.assertRaises(ValueError): validate_payload('match_chat', raw)

    def test_existing_coach_and_before_match_hooks(self):
        rows = [event_rule(when='coach_absent')]
        self.s.teams[0]['name'] = '测试队'
        with patch.object(incidents, 'get_registry', return_value=self.registry(rows)), patch('cs2career.career.career.random.random', return_value=0):
            self.c.maybe_major_coach(self.s, {'id': 'major1', 'type': 'major', 'name': 'Major', 'field': ['测试队']})
        self.assertTrue(any(r.get('kind') == 'incident' for r in self.c.story_queue))
        self.assertEqual(65, self.s.teams[0]['mentality'])
        self.assertIn('先处理', self.c.gate_match(self.s, 'match1'))

    def test_bad_conditions_and_effects_rejected(self):
        base = json.loads((ROOT/'cs2career/data/match_chat.json').read_text('utf-8'))
        for bad in [{'lead': {'min': float('nan')}}, {'kills': {'min': 10, 'max': 0}}, {'oops': 'value'}]:
            row = copy.deepcopy(base['rules'][0]); row['conditions'] = bad
            with self.assertRaises(ValueError):
                validate_payload('match_chat', {'schema_version': 1, 'rules': [row]})
        for effect in [{'type': 'exec', 'value': 'bot_kick'}, {'type': 'club_money', 'amount': True},
                       {'type': 'mentality', 'amount': 21}]:
            row = event_rule(); row['choices'][0]['effects'] = [effect]
            with self.assertRaises(ValueError):
                validate_payload('incidents', {'schema_version': 1, 'incidents': [row]})

    def test_free_escape_required(self):
        row = event_rule(); row['choices'].pop()
        with self.assertRaises(ValueError):
            validate_payload('incidents', {'schema_version': 1, 'incidents': [row]})

    def test_queue_resolve_once_and_remove_pack(self):
        with patch.object(incidents, 'get_registry', return_value=self.registry()):
            before = random.getstate()
            self.c.emit_incidents(self.s, 'before_match', 'match1')
            self.c.emit_incidents(self.s, 'before_match', 'match1')
            self.assertEqual(before, random.getstate())
            self.assertEqual(1, len(self.c.story_queue))
        sid = self.c.story_queue[0]['id']
        # No registry required when resolving an already saved decision.
        with patch.object(incidents, 'get_registry', side_effect=AssertionError('pack removed')):
            self.c.ack_story(sid, 'pay', self.s)
            self.c.ack_story(sid, 'pay', self.s)
        self.assertEqual(900, self.s.teams[0]['money'])
        self.assertEqual(1, len(self.c.cashflow))
        self.assertTrue(self.c.incident_state['flags']['test.pack:replaced'])
        with patch.object(incidents, 'get_registry', return_value=self.registry()):
            self.c.emit_incidents(self.s, 'before_match', 'match2')
        self.assertEqual([], self.c.story_queue)

    def test_insufficient_money_does_not_partially_apply(self):
        with patch.object(incidents, 'get_registry', return_value=self.registry()):
            self.c.emit_incidents(self.s, 'before_match')
        row = self.c.story_queue[0]
        self.s.teams[0]['money'] = 0
        with self.assertRaises(ValueError):
            self.c.ack_story(row['id'], 'pay', self.s)
        self.assertEqual({}, self.c.incident_state['flags'])
        self.assertEqual(1, len(self.c.story_queue))
        self.c.ack_story(row['id'], 'decline', self.s)
        self.assertFalse(self.c.story_queue)

    def test_followup_flags_and_cooldown(self):
        rows = [event_rule(), event_rule(id='followup', when='after_series', conditions={'flags': {'replaced': True}})]
        with patch.object(incidents, 'get_registry', return_value=self.registry(rows)):
            self.c.emit_incidents(self.s, 'after_series')
            self.assertFalse(self.c.story_queue)
            self.c.emit_incidents(self.s, 'before_match')
            self.c.ack_story(self.c.story_queue[0]['id'], 'pay', self.s)
            self.c.emit_incidents(self.s, 'after_series')
            self.assertIn('followup', self.c.story_queue[0]['id'])

    def test_old_save_and_pending_save_roundtrip(self):
        with patch.object(incidents, 'get_registry', return_value=self.registry()):
            self.c.emit_incidents(self.s, 'before_match')
        with tempfile.TemporaryDirectory() as folder, patch('cs2career.career.career.CAREER_PATH', Path(folder)/'career.json'):
            Career.save(self.c)
            loaded = Career.load()
            self.assertEqual(self.c.incident_state, loaded.incident_state)
            self.assertEqual(self.c.story_queue, loaded.story_queue)
            loaded.save = Mock()
            loaded.ack_story(loaded.story_queue[0]['id'], 'pay', self.s)
            self.assertEqual(900, self.s.teams[0]['money'])

    def test_builtin_override_cannot_change_decision_identity(self):
        original = {'when': 'fix_offer', 'title': '旧标题', 'text': '旧文本', 'choices': [{'id': 'accept', 'label': '旧选项'}]}
        overrides = [{'when': 'fix_offer', 'title': '虚构剧情', 'labels': {'accept': '承担风险'}}]
        with patch.object(incidents, 'get_registry', return_value=self.registry(overrides=overrides)):
            changed = incidents.decorate(original)
        self.assertEqual('accept', changed['choices'][0]['id'])
        self.assertEqual('承担风险', changed['choices'][0]['label'])
        self.assertEqual('旧标题', original['title'])

    def test_invalid_pack_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); pack = root/'broken'; (pack/'match_chat').mkdir(parents=True)
            (pack/'pack.json').write_text(json.dumps({'schema_version': 1, 'id': 'bad.pack', 'types': ['match_chat']}))
            (pack/'match_chat'/'bad.json').write_text(json.dumps({'schema_version': 1, 'rules': [{'id': 'x'}]}))
            registry = PackRegistry(root)
            self.assertEqual('rejected', registry.packs[0].status)
            self.assertFalse(registry.payloads('match_chat'))

    def test_changed_team_cannot_charge_new_team(self):
        with patch.object(incidents, 'get_registry', return_value=self.registry()):
            self.c.emit_incidents(self.s, 'before_match')
        self.s.teams.append({'id': 'new', 'money': 1000}); self.c.team_id = 'new'
        self.c.ack_story(self.c.story_queue[0]['id'], 'pay', self.s)
        self.assertEqual(1000, self.s.teams[1]['money'])
        self.assertFalse(self.c.story_queue)
