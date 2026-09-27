"""Dated personal occasions must not be swept into the Major story backlog."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from cs2career.career import Career, arcs, plot, story_timing
from cs2career.career.fast_mode import step
from cs2career.career.notifications import reconcile as reconcile_notices
from cs2career.league import Season


class CalendarOccasionTests(unittest.TestCase):
    def setUp(self):
        self.s = Season(2026, '2026')
        self.c = Career()
        self.s.career = self.c
        self.patch = patch.object(self.c, 'save')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.c.create(dict(mode='create', era='2026', name='Calendar Player',
                           org='Calendar Club', origin='academy', role='rifle', region='EU'), self.s)
        self.c.story_queue = []
        self.c.inbox = []
        self.c.incident_state.pop('story_timing', None)
        self.s.date = '2026-02-01'
        self.c.last_birthday = ''
        self.mates = [p for p in self.c.my_team(self.s.teams)['players'] if not p.get('you')]
        self.birthdays = {self.mates[0]['name']: (2, 4)}
        birth = patch('cs2career.career.career.birthday_md',
                      side_effect=lambda name: self.birthdays.get(name, (12, 31)))
        birth.start()
        self.addCleanup(birth.stop)
        # Real calendar/choice commands; isolate unrelated monthly RNG, invites
        # and world matches. Never save over a player's existing career.
        for target in ('cs2career.career.arcs.tick', 'cs2career.career.news.tick',
                       'cs2career.career.player_transfers.tick'):
            value = patch(target)
            value.start()
            self.addCleanup(value.stop)
        for method in ('dispatch_invites', 'watch'):
            value = patch.object(self.c, method)
            value.start()
            self.addCleanup(value.stop)
        self.s.events = [dict(id='calendar-next', name='Next event', type='t2',
                              status='upcoming', dates=['2026-02-10'], matches=[])]
        self.live = patch.object(self.s, 'ensure_live')
        self.live.start()
        self.addCleanup(self.live.stop)

    def birthday_rows(self):
        return [r for r in self.c.story_queue if r.get('when') == 'teammate_birthday']

    def test_birthday_is_current_in_both_modes_main_chapter_stays_deferred(self):
        for quick in (False, True):
            with self.subTest(quick=quick):
                self.c.assist['quick_mode'] = quick
                self.c.story_queue = [dict(plot.birthday_popup(self.mates[0]['name']), id='day'),
                                      dict(id='long', arc='romance_start', kind='incident', when='incident')]
                self.c.incident_state.pop('story_timing', None)
                story_timing.reconcile(self.c, self.s)
                self.assertEqual(['day'], [r['id'] for r in self.c.story_queue])
                self.assertEqual(['long'], [r['id'] for r in story_timing.state(self.c)['deferred']])

    def test_legacy_deferred_birthday_releases_once_without_applying_reward(self):
        row = plot.birthday_popup(self.mates[0]['name'])
        row.pop('timing')
        row['id'] = 'bday.2026-01-15.' + self.mates[0]['name']
        main = dict(id='romance', arc='marriage', kind='incident', when='incident')
        story_timing.state(self.c)['deferred'] = [row, deepcopy(row), main]
        before = self.c.attr_points
        story_timing.reconcile(self.c, self.s)
        snapshot = deepcopy(self.c.story_queue)
        self.assertFalse(story_timing.reconcile(self.c, self.s))
        self.assertEqual(snapshot, self.c.story_queue)
        self.assertEqual(1, len(self.birthday_rows()))
        self.assertEqual('2026-01-15', self.birthday_rows()[0]['date'])
        self.assertEqual([main], story_timing.state(self.c)['deferred'])
        self.assertEqual(before, self.c.attr_points)
        self.assertEqual('2026-02-01', self.s.date)

    def test_seen_deferred_birthday_is_not_replayed(self):
        row = dict(plot.birthday_popup('Mate'), id='old-day')
        self.c.seen_stories.append('old-day')
        story_timing.state(self.c)['deferred'] = [row]
        story_timing.reconcile(self.c, self.s)
        self.assertFalse(self.c.story_queue)
        self.assertFalse(story_timing.state(self.c)['deferred'])

    def test_legacy_birthday_reaction_is_not_held_until_major(self):
        row = dict(id='arc-notice:2026-02-01:birthday:Mate', when='arc_reaction',
                   kind='story', text='A reply')
        story_timing.state(self.c)['deferred'] = [row]
        story_timing.reconcile(self.c, self.s)
        self.assertEqual([row], self.c.story_queue)

    def test_advance_and_event_shortcut_land_on_birthday_then_resume(self):
        for command in ('next_stage', 'skip_to_next_event'):
            with self.subTest(command=command):
                self.s.date = '2026-02-01'
                self.c.last_birthday = ''
                self.c.seen_stories = []
                self.c.story_queue = []
                self.c.incident_state.pop('story_timing', None)
                getattr(self.s, command)()
                self.assertEqual('2026-02-04', self.s.date)
                row, = self.birthday_rows()
                self.assertEqual(self.s.date, row['date'])
                self.assertIn('生日', getattr(self.s, command)())
                self.assertEqual('2026-02-04', self.s.date)
                self.c.ack_story(row['id'], 'wish', self.s)
                getattr(self.s, command)()
                self.assertEqual('2026-02-10', self.s.date)
                self.assertFalse(self.birthday_rows())

    def test_skip_running_event_cannot_skip_a_calendar_stop(self):
        self.s.events[0].update(status='live', matches=[dict(date='2026-02-10', played=False)])
        with patch.object(self.s, 'advance_event'):
            self.s.skip_to_next_event()
        self.assertEqual('2026-02-04', self.s.date)
        self.assertEqual(1, len(self.birthday_rows()))

    def test_quick_runner_pauses_on_birthday_and_retries_do_not_duplicate(self):
        self.c.assist = {'quick_mode': True}
        result = step(self.c, self.s, 'birthday-step-1', 0)
        self.assertEqual('paused', result['status'])
        self.assertEqual('2026-02-04', result['date'])
        self.assertEqual(result, step(self.c, self.s, 'birthday-step-1', 0))
        self.assertEqual('paused', step(self.c, self.s, 'birthday-step-2', 1)['status'])
        self.assertEqual(1, len(self.birthday_rows()))
        row = self.birthday_rows()[0]
        self.c.ack_story(row['id'], 'wish', self.s)
        result = step(self.c, self.s, 'birthday-step-3', 2)
        self.assertEqual('progress', result['status'])
        self.assertEqual('2026-02-10', self.s.date)

    def test_birthday_response_is_same_day_for_each_choice_rewards_apply_once(self):
        self.s.date = '2026-02-04'
        self.c.assist = {'quick_mode': True}
        for choice in ('wish', 'train'):
            with self.subTest(choice=choice):
                row = dict(plot.birthday_popup(self.mates[0]['name']), id='birthday-' + choice)
                self.c.story_queue.append(row)
                before = self.c.attr_points
                self.c.ack_story(row['id'], choice, self.s)
                self.c.ack_story(row['id'], choice, self.s)
                reward = arcs.config()['rules']['focus_reward'] if choice == 'train' else 0
                self.assertEqual(before + reward, self.c.attr_points)
                self.assertFalse(story_timing.state(self.c)['deferred'])
                reaction = next(r for r in self.c.story_queue if r.get('when') == 'arc_reaction')
                self.assertEqual(self.s.date, reaction['date'])
                self.assertEqual('calendar', reaction['timing'])
                reconcile_notices(self.c, self.s)
                self.assertTrue(any(h['date'] == self.s.date and '回应' in h['title']
                                    for h in arcs.state(self.c)['history']))
                self.assertFalse(self.c.story_queue)
                self.s.date = '2026-02-05'
        self.assertIn('休赛期', self.c.spend_point(self.s, 'firepower'))

    def test_multiple_birthdays_are_in_date_order_and_share_a_day(self):
        self.birthdays[self.mates[1]['name']] = (2, 4)
        self.birthdays[self.mates[2]['name']] = (2, 7)
        self.s.next_stage()
        self.assertEqual('2026-02-04', self.s.date)
        self.assertEqual(2, len(self.birthday_rows()))
        first, second = self.birthday_rows()
        self.c.ack_story(first['id'], 'wish', self.s)
        self.s.next_stage()
        self.assertEqual('2026-02-04', self.s.date)
        self.c.ack_story(second['id'], 'wish', self.s)
        self.s.next_stage()
        self.assertEqual('2026-02-07', self.s.date)
        self.assertEqual(1, len(self.birthday_rows()))

    def test_calendar_lookup_excludes_player_and_departed_teammates(self):
        self.birthdays[self.c.player_name] = (2, 2)
        self.c.my_team(self.s.teams)['players'].remove(self.mates[0])
        self.assertIsNone(self.c.next_calendar_day(self.s, '2026-02-10'))
        self.c.unsigned = True
        self.assertIsNone(self.c.next_calendar_day(self.s, '2026-12-31'))

    def test_february_29_and_year_boundary_are_validated(self):
        self.birthdays[self.mates[0]['name']] = (2, 29)
        self.assertIsNone(self.c.next_calendar_day(self.s, '2026-03-01'))
        self.s.date = '2028-02-01'
        self.assertEqual('2028-02-29', self.c.next_calendar_day(self.s, '2028-03-01'))
        self.s.date = '2028-12-31'
        self.birthdays[self.mates[0]['name']] = (1, 3)
        self.assertEqual('2029-01-03', self.c.next_calendar_day(self.s, '2029-01-10'))


if __name__ == '__main__':
    unittest.main()
