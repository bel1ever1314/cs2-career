"""Locale fields survive a real story acknowledgement without rewriting prose."""
from types import SimpleNamespace
from unittest import TestCase

from cs2career.career import arcs


class StoryLocaleHistoryTests(TestCase):
    def test_resolve_keeps_optional_english_fields_and_choice(self):
        value={'history':[], 'seen':[]}
        career=SimpleNamespace(incident_state={'arcs':value})
        season=SimpleNamespace(date='2026-06-20')
        row=dict(id='story',title='归途',text='收好键盘。',title_en='The journey home',
                 text_en='Pack up your keyboard.',arc_rules={},context={},
                 choices=[dict(id='continue',label='继续',label_en='Continue')])
        arcs.resolve(career,season,row,'continue')
        history=value['history'][0]
        self.assertEqual('The journey home',history['title_en'])
        self.assertEqual('Pack up your keyboard.',history['text_en'])
        self.assertEqual('Continue',history['choice_en'])
        self.assertEqual('收好键盘。',history['text'])

    def test_old_single_language_stories_keep_their_existing_shape(self):
        value={'history':[], 'seen':[]}
        career=SimpleNamespace(incident_state={'arcs':value})
        row=dict(id='old',title='旧剧情',text='原文',arc_rules={},context={},
                 choices=[dict(id='continue',label='继续')])
        arcs.resolve(career,SimpleNamespace(date='2026-06-20'),row,'continue')
        history=value['history'][0]
        self.assertNotIn('title_en',history)
        self.assertNotIn('text_en',history)
        self.assertNotIn('choice_en',history)
