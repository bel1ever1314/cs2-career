"""Season boundaries and quiet notices are business rules, not UI shortcuts."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from cs2career.career import Career
from cs2career.league import Season, formats
from cs2career.career.fast_mode import configure_season, season_mode, step
from cs2career.career.notifications import reconcile, informational
from cs2career.career.assistance import configure
from cs2career.league.tournament_auto import step as event_step, decisive


class SeasonRunnerTests(unittest.TestCase):
    def setUp(self):
        self.s = Season(2026, '2026')
        self.c = Career(); self.s.career = self.c
        self.save = patch.object(self.c, 'save'); self.save.start(); self.addCleanup(self.save.stop)
        self.c.create(dict(mode='create', era='2026', name='Runner', org='Runner Club',
                           origin='academy', role='rifle', region='EU'), self.s)
        self.c.story_queue = []; self.c.inbox = []
        self.c.incident_state = {}
        self.c.assist = {'quick_mode': True}

    def fixture(self, status='done'):
        event = dict(id='end-fixture', name='End Fixture', type='t2', format='single_elim', size=2,
                     region='EU', dates=[self.s.date], prize=0, vrs_weight=1,
                     status=status, field=[], matches=[])
        self.s.events = [event]
        return event

    def test_completed_calendar_stops_without_rolling_and_replays(self):
        self.fixture()
        before = deepcopy(self.s.events)
        with patch.object(self.s, 'roll_year') as roll:
            result = step(self.c, self.s, 'season-done-1', 0)
            self.assertEqual('season_done', result['status'])
            self.assertEqual(2026, result['season_year'])
            self.assertEqual(result, step(self.c, self.s, 'season-done-1', 0))
            self.assertEqual('season_done', step(self.c, self.s, 'season-done-2', 1)['status'])
            roll.assert_not_called()
        self.assertEqual(before, self.s.events)
        self.assertEqual(2026, self.s.year)

    def test_last_world_event_can_complete_inside_step_without_crossing_year(self):
        event = self.fixture('live')
        def close(ev): ev['status'] = 'done'
        with patch.object(self.s, 'advance_event', side_effect=close), patch.object(self.c, 'dispatch_invites'), \
             patch.object(self.s, 'roll_year') as roll:
            out = step(self.c, self.s, 'close-world-1', 0)
            self.assertEqual('season_done', out['status']); roll.assert_not_called()

    def test_manual_advance_buttons_cannot_bypass_quick_year_boundary(self):
        for command in ('next_stage', 'skip_to_next_event'):
            with self.subTest(command=command):
                self.fixture()
                with patch.object(self.s, 'roll_year') as roll:
                    result = getattr(self.s, command)()
                    self.assertIn('请选择下一赛季', result)
                    self.assertEqual(2026, self.s.year); roll.assert_not_called()

    def test_manual_advance_buttons_stop_when_the_last_live_event_closes(self):
        for command in ('next_stage', 'skip_to_next_event'):
            with self.subTest(command=command):
                self.fixture('live')
                def close(ev): ev['status'] = 'done'
                with patch.object(self.s, 'advance_event', side_effect=close), \
                     patch.object(self.s, 'roll_year') as roll:
                    result = getattr(self.s, command)()
                    self.assertIn('请选择下一赛季', result)
                    self.assertEqual('done',self.s.events[0]['status']); roll.assert_not_called()

    def test_normal_advance_buttons_keep_existing_year_rollover(self):
        self.c.assist['quick_mode'] = False
        for command in ('next_stage', 'skip_to_next_event'):
            with self.subTest(command=command):
                self.fixture()
                with patch.object(self.s, 'roll_year', return_value='normal next season') as roll:
                    self.assertEqual('normal next season',getattr(self.s, command)())
                    roll.assert_called_once_with()

    def test_quick_manual_advancement_before_year_end_still_reaches_next_event(self):
        for command in ('next_stage', 'skip_to_next_event'):
            with self.subTest(command=command):
                self.s.date = '2026-01-12'
                event = self.fixture('upcoming'); event['dates'] = ['2026-01-20']
                with patch.object(self.s,'ensure_live'), patch.object(self.c,'dispatch_invites'), \
                     patch.object(self.c,'tick'), patch.object(self.c,'watch'), patch.object(self.s,'roll_year') as roll:
                    getattr(self.s,command)()
                    self.assertEqual('2026-01-20',self.s.date)
                    self.assertEqual(2026,self.s.year); roll.assert_not_called()

    def test_next_season_requires_explicit_mode_choice_and_retry_cannot_roll_twice(self):
        self.fixture(); self.c.attr_points = 5
        result = configure_season(self.c, self.s, False, 2026)
        self.assertEqual(2027, self.s.year)
        self.assertEqual('normal', result['selected'])
        self.assertEqual(5, self.c.attr_points, 'quick-season points survive changing next season to normal')
        self.assertFalse(result['choice_required'])
        with self.assertRaises(ValueError): configure_season(self.c, self.s, False, 2026)
        self.assertEqual(2027, self.s.year)

    def test_midseason_mode_change_cannot_use_old_assistance_endpoint(self):
        self.fixture('live')
        self.assertFalse(season_mode(self.c, self.s)['can_choose'])
        with self.assertRaises(ValueError): configure(self.c, self.s, {'quick_mode': False})
        self.assertTrue(self.c.assist['quick_mode'])
        configure(self.c, self.s, {'points': 'balanced', 'quick_mode': True})
        self.assertEqual('balanced', self.c.assist['points'])

    def test_legacy_midseason_quick_save_continues_current_year_only(self):
        self.fixture('live')
        with patch.object(self.s, 'next_stage', return_value='wait'), patch.object(self.c, 'dispatch_invites'):
            step(self.c, self.s, 'legacy-fast-1', 0)
        self.assertEqual(2026, self.c.assist['season_run']['year'])
        self.s.year = 2027
        with patch.object(self.s, 'next_stage') as advance:
            out = step(self.c, self.s, 'legacy-fast-2', 1)
            self.assertEqual('season_done', out['status']); advance.assert_not_called()

    def test_real_nonfinal_elimination_is_played_without_extra_prompt_in_both_modes(self):
        for quick in (False, True):
            self.c.assist = {'quick_mode': quick}; self.c.story_queue = []
            ev = self.fixture('live')
            mine = self.c.my_team(self.s.teams)
            other = next(t for t in self.s.teams if t['id'] != self.c.team_id)
            match = formats._mk(ev, 'SW5', self.s.date, mine['name'], other['name'], 1, meta={'record':'2-2'})
            ev.update(matches=[match], field=[mine['name'], other['name']])
            self.c.registered = [ev['id']]
            with patch.object(self.c, 'gate_match', return_value=''), patch.object(self.s, 'advance_event'):
                out = event_step(self.c, self.s, ev['id'], 'elim-match-' + str(quick))
            self.assertEqual('played', out['status']); self.assertTrue(match['played'])
            self.assertFalse(any(r.get('when') == 'tournament_decision' for r in self.c.story_queue))

    def test_notice_archive_keeps_full_payload_once_without_rewards(self):
        awards = dict(id='awards.cup',kind='awards',when='awards',title='Cup',champion='Runner Club',
                      mvp={'player':'Runner'},evp=[],five=[{'player':'Runner','role':'rifle'}])
        plain = dict(id='notice.1',kind='story',title='A letter',text='Hello',text_en='Hello')
        single_reward = dict(id='reward',kind='incident',choices=[{'id':'continue','effects':[{'type':'skill_points','amount':2}]}])
        self.c.story_queue = [awards, plain, single_reward]
        before = self.c.attr_points
        with patch.object(self.c, 'ack_story') as ack:
            self.assertTrue(reconcile(self.c, self.s)); self.assertFalse(reconcile(self.c, self.s))
            ack.assert_not_called()
        self.assertEqual([single_reward], self.c.story_queue)
        self.assertEqual(before, self.c.attr_points)
        self.assertEqual(2, len(self.c.inbox))
        self.assertEqual(awards, self.c.inbox[0]['notification'])
        self.c.story_queue.append(awards)
        reconcile(self.c, self.s); self.assertEqual(2,len(self.c.inbox))

    def test_deferred_plain_notices_no_longer_burst_at_major(self):
        notice = {'id':'later-info','text':'Filed', 'kind':'story'}
        decision = {'id':'romance','kind':'incident','arc':'romance','choices':[{'id':'yes'}]}
        self.c.incident_state = {'story_timing':{'deferred':[notice,decision]}}
        reconcile(self.c,self.s)
        self.assertEqual([decision],self.c.incident_state['story_timing']['deferred'])
        self.assertEqual('Filed',self.c.inbox[0]['body'])

    def test_existing_monthly_news_is_not_duplicated_or_relabelled(self):
        notice = {'id':'news:monthly:2026-02','when':'world_news','kind':'story',
                  'title':'二月月报','text':'赛果'}
        self.c.incident_state = {'arcs':{'history':[deepcopy(notice)]}}
        self.c.inbox = [{'id':'news.1','kind':'news','title':'二月月报','body':'赛果'}]
        self.c.story_queue = [notice]
        self.assertTrue(reconcile(self.c,self.s)); self.assertEqual(1,len(self.c.inbox))
        self.assertEqual([],self.c.story_queue)
        self.c.story_queue = [{'id':'another','title':'具体标题','text':'原文'}]
        reconcile(self.c,self.s)
        self.assertNotIn('title_en',self.c.inbox[-1])
        self.assertNotIn('body_en',self.c.inbox[-1])

    def test_important_choices_and_effectful_records_are_never_quieted(self):
        for row in ({'id':'fix','when':'fix_offer'}, {'id':'custom','kind':'incident'},
                    {'id':'points','kind':'story','effects':[{'type':'skill_points','amount':2}]},
                    {'id':'start','arc':'na_start'}, {'id':'one','choices':[{'id':'continue'}]}):
            self.assertFalse(informational(row))

    def legacy_prompt(self, stage='QF'):
        event = self.fixture('live')
        mine = self.c.my_team(self.s.teams)
        other = next(t for t in self.s.teams if t['id'] != self.c.team_id)
        match = formats._mk(event, stage, self.s.date, mine['name'], other['name'], 3)
        event['matches'] = [match]
        identity = f"{self.s.year}:{event['id']}:{match['id']}:{self.c.team_id}"
        return {'id':'tournament-moment:'+identity, 'kind':'story', 'when':'tournament_decision',
                'title':'Old elimination prompt', 'text':'Choose the match mode.',
                'choices':[{'id':cid,'label':cid} for cid in ('manual','simulate','later')],
                'auto_match':identity, 'event_id':event['id'], 'match_id':match['id'], 'team_id':self.c.team_id}

    def test_legacy_builtin_nonfinal_prompt_is_archived_without_answering(self):
        row = self.legacy_prompt()
        self.c.story_queue = [row]
        points, assistant = self.c.attr_points, deepcopy(self.c.assist)
        with patch.object(self.c,'ack_story') as ack, patch('cs2career.league.tournament_auto.resolve') as resolve:
            self.assertTrue(reconcile(self.c,self.s)); self.assertFalse(reconcile(self.c,self.s))
            ack.assert_not_called(); resolve.assert_not_called()
        self.assertEqual([],self.c.story_queue)
        self.assertEqual(points,self.c.attr_points); self.assertEqual(assistant,self.c.assist)
        self.assertFalse(self.s.events[0]['matches'][0]['played'])
        self.assertEqual(row,self.c.inbox[0]['notification'])
        self.assertEqual('nonfinal_confirmation_removed',self.c.inbox[0]['notification_superseded'])
        self.assertEqual(1,len(self.c.inbox))

    def test_legacy_migration_does_not_touch_finals_unknown_or_mismatched_decisions(self):
        final = self.legacy_prompt('GF')
        self.c.story_queue = [final]
        self.assertFalse(reconcile(self.c,self.s)); self.assertEqual([final],self.c.story_queue)
        baseline = self.legacy_prompt('QF')
        changed = [dict(baseline,id='pack:elimination'), dict(baseline,auto_match='other-identity'),
                   dict(baseline,team_id='previous-team'), dict(baseline,event_id='old-event'),
                   dict(baseline,arc='extension'), dict(baseline,kind='incident')]
        old_year = baseline['auto_match'].replace('2026:', '2025:', 1)
        changed.append(dict(baseline,id='tournament-moment:'+old_year,auto_match=old_year))
        effectful = deepcopy(baseline)
        effectful['choices'][0]['effects'] = [{'type':'skill_points','amount':2}]
        changed.append(effectful)
        for row in changed:
            with self.subTest(row=row):
                self.c.story_queue = [row]
                self.assertFalse(reconcile(self.c,self.s)); self.assertEqual([row],self.c.story_queue)


if __name__ == '__main__': unittest.main()
