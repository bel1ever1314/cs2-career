import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from cs2career.application import ApplicationState
from cs2career.career import Career


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch('cs2career.league.season.STATE_PATH',self.root/'season.json'))
        self.stack.enter_context(patch.object(Career,'path',return_value=self.root/'career.json'))
        self.stack.enter_context(patch('cs2career.paths.save_root',return_value=self.root))
        self.state = ApplicationState()

    def payload(self,origin='academy'):
        return dict(era='2026',mode='create',origin=origin,name='Lifecycle Tester',org='Lifecycle Club',region='AS',role='rifle')

    def test_invalid_create_preserves_current_objects_and_files(self):
        self.state.create_career(self.payload())
        old = self.state.career
        files = {p.name:p.read_bytes() for p in self.root.glob('*.json')}
        with self.assertRaises(ValueError):
            self.state.create_career(dict(era='2024',mode='join',team_id='missing'))
        self.assertIs(old,self.state.career)
        self.assertEqual(files,{p.name:p.read_bytes() for p in self.root.glob('*.json')})

    def test_reset_and_replace_back_up_current_pair(self):
        self.state.create_career(self.payload())
        before=(self.root/'career.json').read_bytes()
        self.state.reset()
        self.assertTrue(any(p.read_bytes()==before for p in (self.root/'backups').glob('*/career.json')))
        self.assertFalse(self.state.career.exists)

    def test_unavailable_starter_roster_preserves_existing_career(self):
        self.state.create_career(self.payload())
        old = self.state.career
        files = {p.name:p.read_bytes() for p in self.root.glob('*.json')}
        with patch('cs2career.career.career.starter_mates',return_value=[]):
            with self.assertRaisesRegex(ValueError,'不足'):
                self.state.create_career(self.payload('prodigy'))
        self.assertIs(old,self.state.career)
        self.assertEqual(files,{p.name:p.read_bytes() for p in self.root.glob('*.json')})

    def test_overridden_path_controls_both_save_and_load(self):
        sentinel=self.root/'must-not-write.json'
        sentinel.write_text('original')
        with patch('cs2career.career.career.CAREER_PATH',sentinel):
            c=Career();c.money=1234;c.save()
            self.assertEqual(1234,Career.load().money)
        self.assertEqual('original',sentinel.read_text())

    def test_corrupt_save_is_not_silently_reset(self):
        target=self.root/'season.json';target.write_text('{broken')
        with self.assertRaises(ValueError):
            ApplicationState()
        self.assertEqual('{broken',target.read_text())
