"""Only synthetic starter identities; never load or change player saves."""
from types import SimpleNamespace
from uuid import UUID
import unittest

from tools.career3d_start import requires_creation


class OnboardingTests(unittest.TestCase):
    def fixture(self):
        return SimpleNamespace(
            career=SimpleNamespace(exists=True, player_name='Old Player', mode='create',
                origin='academy', incident_state={}),
            season=SimpleNamespace(date='2026-01-01', events=[]),
            arena=SimpleNamespace(data={'history':[]}))

    def test_existing_unmarked_player_is_not_forced_to_restart(self):
        self.assertFalse(requires_creation(self.fixture()))

    def test_pending_template_requires_creation_even_though_career_exists(self):
        state = self.fixture()
        state.career.incident_state['career3d_start'] = {'schema_version':1, 'pending':True}
        self.assertTrue(requires_creation(state))
        state.career.incident_state['career3d_start']['pending'] = False
        self.assertFalse(requires_creation(state))

    def test_untouched_legacy_template_is_not_a_created_character(self):
        state = self.fixture()
        state.career.player_name = 'Career3D'
        state.career.incident_state['arcs'] = {'seed':UUID(int=20260930).hex, 'started':state.season.date}
        self.assertTrue(requires_creation(state))
        state.season.date = '2026-01-02'
        self.assertFalse(requires_creation(state))

    def test_created_receipt_and_saved_match_progress_preserve_legacy_careers(self):
        state = self.fixture()
        state.career.player_name = 'Career3D'
        state.career.incident_state['arcs'] = {'seed':UUID(int=20260930).hex, 'started':state.season.date}
        state.arena.data['history'] = [{'result_id':'fixture'}]
        self.assertFalse(requires_creation(state))
        state.arena.data['history'] = []
        state.career.incident_state['career3d_service'] = {'start_receipts':[{'id':'fixture-created'}]}
        self.assertFalse(requires_creation(state))
