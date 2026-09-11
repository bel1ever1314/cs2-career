"""Regression paths use real Career/Season commands and isolated test-runner paths."""
import copy
import json
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from cs2career.application import ApplicationState
from cs2career.career import Career
from cs2career.career import incidents, player_transfers as pt
from cs2career.content.rules import validate_effects, validate_payload
from cs2career.league import Season
from cs2career.json_bytes import encode


class TransferFlowFixTests(unittest.TestCase):
    def setUp(self):
        self.app = ApplicationState()
        self.app.create_career(dict(mode='create', era='2026', name='FlowTest', org='Flow Club',
                                    origin='academy', role='rifle', region='EU'))
        self.c, self.s = self.app.career, self.app.season
        self.finish_stories()

    def finish_stories(self):
        while self.c.story_queue:
            row = self.c.story_queue[0]
            self.c.ack_story(row['id'], (row.get('choices') or [{'id': ''}])[0]['id'], self.s)

    def event(self):
        ev = dict(id='test-flow-cup', name='Flow Cup', type='t2', region='EU', size=2,
                  format='single_elim', dates=[self.s.date, self.s.date], status='upcoming',
                  matches=[], field=[], prize=1000, vrs_weight=1, best_of=1)
        self.s.events = [ev]
        self.c.inbox = []
        return ev

    def transfer(self):
        target = next(r for r in pt.public(self.c, self.s)['targets'] if not r['blocked'])
        with patch.object(pt, 'draw', return_value=20):
            pt.apply(self.c, self.s, target['team_id'], target['role'])
        row = next(r for r in self.c.story_queue if r.get('when') == 'transfer_decision')
        self.c.ack_story(row['id'], 'accept', self.s)
        return target

    def test_transfer_reissues_invites_and_new_team_really_plays(self):
        ev = self.event()
        old = self.c.offer_invite(self.s, ev)
        self.c.accept_invite(self.s, old['id'])
        old_id = self.c.team_id
        self.transfer()
        new = next(r for r in self.c.inbox if r.get('kind') == 'invite' and r.get('team_id') == self.c.team_id)
        self.assertEqual(old_id, old['team_id'])
        self.assertIn('原战队', self.c.accept_invite(self.s, old['id']))
        self.c.accept_invite(self.s, new['id'])
        self.finish_stories()
        self.s.open_event(ev)
        mine = self.c.my_team(self.s.teams)
        self.assertIn(mine['name'], ev['field'])
        pair = self.s.your_series()
        self.assertIsNotNone(pair)
        with patch.object(self.c, 'gate_match', return_value=''):
            self.s.skip_your_series(pair[1]['id'])
        self.assertTrue(pair[1]['played'])
        self.assertTrue(pair[1]['maps'])
        self.assertEqual(10, sum(len(players) for players in pair[1]['maps'][0]['players'].values()))

    def test_legacy_transfer_invites_repair_once_without_history_changes(self):
        ev = self.event()
        letter = self.c.offer_invite(self.s, ev)
        letter.pop('team_id'); letter['status'] = 'accepted'
        self.c.registered = [ev['id']]
        self.c.personal_transfers['moves'] = [{'date': self.s.date}]
        self.assertTrue(self.c.repair_invite_teams(self.s))
        self.assertFalse(self.c.repair_invite_teams(self.s))
        self.assertNotIn(ev['id'], self.c.registered)
        self.c.dispatch_invites(self.s)
        self.assertEqual(2, len(self.c.inbox))
        self.c.dispatch_invites(self.s)
        self.assertEqual(2, len(self.c.inbox))

    def test_employee_role_switch_retains_valid_five(self):
        self.transfer()
        mine = self.c.my_team(self.s.teams)
        mapping = {p['name']: p['role'] for p in mine['players']}
        mapping[self.c.player_name] = 'awp'
        self.c.set_roles(self.s, mapping, self.c.player_name)
        self.assertEqual('awp', self.c.role)
        self.assertEqual(1, sum(p['role'] == 'awp' for p in mine['players']))
        self.assertEqual(1, sum(p['role'] == 'igl' for p in mine['players']))

    def test_all_farewell_choices_reward_once_and_have_distinct_reactions(self):
        self.transfer()
        base = copy.deepcopy(self.c)
        texts = []
        for choice in ('thanks', 'promise', 'quiet'):
            self.c = copy.deepcopy(base)
            row = next(r for r in self.c.story_queue if r.get('when') == 'transfer_farewell')
            before = self.c.attr_points
            self.c.ack_story(row['id'], choice, self.s)
            self.c.ack_story(row['id'], choice, self.s)
            self.assertEqual(before+1, self.c.attr_points)
            texts.append(next(r['text'] for r in self.c.story_queue if r.get('when') == 'transfer_reaction'))
        self.assertEqual(3, len(set(texts)))

    def test_non_champion_awards_reveal_once(self):
        ev = self.event()
        mine = self.c.my_team(self.s.teams)['name']
        ev.update(status='done', champion='Other', awards={'mvp': {'player': 'Other', 'team': 'Other'}, 'five': []},
                  matches=[dict(team_a=mine, team_b='Other', winner='Other', played=True, stage='GF')])
        self.c.award_event(self.s, ev)
        points, cash = self.c.attr_points, self.c.money
        self.c.award_event(self.s, ev)
        self.assertEqual(1, sum(r.get('id') == 'awards.'+ev['id'] for r in self.c.story_queue))
        self.assertEqual((points, cash), (self.c.attr_points, self.c.money))
        self.assertFalse(any(r.get('when') == 'title' for r in self.c.story_queue))

    def incident(self, effects):
        row = dict(id='incident:test:1', kind='incident', pack_id='author.test', team_id=self.c.team_id,
                   title='为了重要的人', choices=[dict(id='yes', label='暂停比赛', effects=effects)])
        self.c.story_queue.append(row)
        return row

    def test_pause_forfeits_due_match_no_fake_stats_and_restores_by_date(self):
        ev = self.event()
        letter = self.c.offer_invite(self.s, ev)
        self.c.accept_invite(self.s, letter['id'])
        self.s.open_event(ev)
        match = next(m for m in ev['matches'] if self.s.is_yours(m))
        before = self.c.attr_points
        row = self.incident([dict(type='skill_points', amount=2), dict(type='competition_pause', amount=7)])
        self.c.ack_story(row['id'], 'yes', self.s)
        self.c.ack_story(row['id'], 'yes', self.s)
        self.assertEqual(before+2, self.c.attr_points)
        self.assertIsNone(self.s.your_series())
        self.assertIn('暂停', self.c.gate_match(self.s, match['id']))
        self.s.next_stage()
        self.assertTrue(match['forfeit'])
        self.assertFalse(match['maps'])
        self.assertEqual(before+2, self.c.attr_points)
        self.app.persist()
        loaded = Career.load()
        until = incidents.competition_status(loaded, self.s.date)['until']
        self.assertTrue(incidents.competition_paused(loaded, self.s.date))
        self.assertFalse(incidents.competition_paused(loaded, until))

    def test_pause_rejects_partial_series_before_any_effect(self):
        ev = self.event()
        ev['matches'] = [dict(team_a=self.c.my_team(self.s.teams)['name'], team_b='Other', maps=[{'map':'mirage'}])]
        before = self.c.attr_points
        row = self.incident([dict(type='skill_points', amount=5), dict(type='competition_pause', amount=3)])
        with self.assertRaises(ValueError): self.c.ack_story(row['id'], 'yes', self.s)
        self.assertEqual(before, self.c.attr_points)
        self.assertIn(row, self.c.story_queue)
        self.assertFalse(incidents.competition_paused(self.c, self.s.date))

    def test_effect_bounds(self):
        for effect in [dict(type='skill_points', amount=101), dict(type='skill_points', amount=-1),
                       dict(type='competition_pause', amount=366), dict(type='competition_pause', amount=True)]:
            with self.assertRaises(ValueError): validate_effects([effect])

    def test_shipped_pack_loads_and_branches_through_existing_incident_interface(self):
        from cs2career.content.loader import PackRegistry
        template = Path(__file__).resolve().parents[1]/'extensions/_templates/choice-effects-pack'
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(template, Path(folder)/'choices')
            registry = PackRegistry(Path(folder))
            self.assertEqual('ready', registry.packs[0].status, registry.packs[0].errors)
            with patch.object(incidents, 'get_registry', return_value=registry):
                incidents.emit(self.c, self.s, 'day')
                row = next(r for r in self.c.story_queue if r.get('kind') == 'incident')
                before = self.c.attr_points
                self.c.ack_story(row['id'], 'stay', self.s)
                self.assertEqual(before+2, self.c.attr_points)
                self.finish_stories()
                incidents.emit(self.c, self.s, 'day')
                row = next(r for r in self.c.story_queue if r.get('kind') == 'incident')
                self.assertEqual('陪伴之后', row['title'])
                self.c.ack_story(row['id'], 'return', self.s)
                self.assertFalse(incidents.competition_paused(self.c, self.s.date))
                self.finish_stories()
                incidents.emit(self.c, self.s, 'day')
                self.assertFalse(incidents.pending(self.c))

    def test_public_summary_does_not_copy_or_erase_history_events(self):
        self.s.history = [dict(id='old', name='Old', matches=[dict(id='old-m', maps=[{'round_events':[{'keep':True}]}])])]
        original = copy.deepcopy(self.s.history)
        self.assertEqual([], self.s.records(include_matches=False)[0]['matches'])
        self.assertEqual(original, self.s.records())
        self.s.save()
        loaded = Season.load_or_new()
        self.assertEqual(original, loaded.history)
        self.assertEqual(original, json.loads(encode(original)))
