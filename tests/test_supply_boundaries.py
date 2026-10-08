"""Supply consumption follows actual map handoffs and durable results."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import test_unified_pace as pace_fixture
import test_booked_scrims as scrim_fixture
from cs2career.career import match_supplies as supplies
from cs2career.services import matches, match_launch, scrims
from cs2career.cs2 import launch


class SupplyBoundaryTests(unittest.TestCase):
    setUp=pace_fixture.UnifiedPaceTests.setUp
    career_fixture=pace_fixture.UnifiedPaceTests.career_fixture
    quiet=pace_fixture.UnifiedPaceTests.quiet
    ready=pace_fixture.UnifiedPaceTests.ready
    body=pace_fixture.UnifiedPaceTests.body
    current=pace_fixture.UnifiedPaceTests.current

    def prepare_supply(self,match,grade='strong'):
        c,s=self.state.career,self.state.season
        c.money=50000
        pid=supplies.identity(c.my_player(s.teams))
        with self.state.operation():
            supplies.command(self.state,'buy',dict(revision=matches._revision(self.state),axis='sniping',grade=grade,payer='personal'))
            supplies.command(self.state,'prepare',dict(revision=matches._revision(self.state),player_id=pid,item_id='supply.1',target=supplies.series_key(s,match)))
            self.state.persist()
        return pid

    def test_bo3_sim_cs2_rts_keeps_single_consumption_and_clears_effect(self):
        match=self.ready()
        pid=self.prepare_supply(match)
        original=deepcopy(self.state.career.my_player(self.state.season.teams)['stats'])
        # Reuse the full mixed-mode fixture, but not its save-resetting ready().
        with patch.object(self,'ready',return_value=match):
            pace_fixture.UnifiedPaceTests.test_sim_cs2_rts_maps_keep_bp_and_settle_each_map_once(self)
        self.assertEqual(['0','1','2'],list(match['supply_maps']))
        self.assertTrue(all(row[pid]['bonus']==5 for row in match['supply_maps'].values()))
        self.assertFalse(supplies.data(self.state.career)['stock'])
        self.assertFalse(supplies.data(self.state.career)['active'])
        self.assertEqual(original,self.state.career.my_player(self.state.season.teams)['stats'])

    def test_failed_dispatch_does_not_consume_or_start_cooldown(self):
        match=self.ready()
        self.prepare_supply(match,'normal')
        self.stack.enter_context(patch.object(self.state.season,'_phase_gate',return_value=False))
        self.stack.enter_context(patch('tools.career3d_activities.config_status',return_value=dict(ready=True,reason='')))
        self.stack.enter_context(patch('tools.career3d_activities.read_cs2_config',return_value=dict(launch.DEFAULTS,csgo_path='')))
        self.stack.enter_context(patch.object(launch,'require_cs2_closed'))
        self.stack.enter_context(patch.object(matches,'_peek',return_value={'status':'none'}))
        with patch.object(matches,'_dispatch_launch',side_effect=OSError('fixture launch failure')):
            out=match_launch.command(self.state,self.current('supply-failed-launch'))
        self.assertEqual('failed',out['status'])
        store=supplies.data(self.state.career)
        self.assertEqual(1,len(store['stock']))
        self.assertFalse(store['cooldowns'])
        self.assertFalse(store['active'])
        self.assertFalse(match.get('supply_maps'))


class SupplyScrimTests(unittest.TestCase):
    setUp=scrim_fixture.BookedScrimTests.setUp
    career_fixture=scrim_fixture.BookedScrimTests.career_fixture
    ready=scrim_fixture.BookedScrimTests.ready
    records=scrim_fixture.BookedScrimTests.records
    session=scrim_fixture.BookedScrimTests.session
    dispatch=scrim_fixture.BookedScrimTests.dispatch
    launch=scrim_fixture.BookedScrimTests.launch
    raw_result=scrim_fixture.BookedScrimTests.raw_result
    finish_body=scrim_fixture.BookedScrimTests.finish_body
    perform=scrim_fixture.BookedScrimTests.perform

    def supply_ready(self):
        self.ready()
        c=self.state.career
        c.money=50000
        pid=supplies.identity(c.my_player(self.state.season.teams))
        with self.state.operation():
            supplies.command(self.state,'buy',dict(revision=0,axis='firepower',grade='normal',payer='personal'))
            supplies.command(self.state,'prepare',dict(revision=0,player_id=pid,item_id='supply.1',target='scrim:'+self.booking['id']))
            self.state.persist()
        return pid

    def test_cs2_practice_and_repeated_collection_consume_once(self):
        pid=self.supply_ready()
        self.launch()
        self.assertEqual(3,self.booking['supply_maps']['0'][pid]['bonus'])
        self.assertFalse(supplies.data(self.state.career)['stock'])
        body=self.finish_body()
        with patch.object(scrims,'_raw',return_value=self.raw_result()):
            self.perform('collect',body)
            self.assertTrue(self.perform('collect',body)['replayed'])
        self.assertFalse(supplies.data(self.state.career)['active'])
        self.assertTrue(supplies.data(self.state.career)['cooldowns'])

    def test_simulated_practice_consumes_once(self):
        pid=self.supply_ready()
        self.perform('simulate',dict(id=self.booking['id']))
        self.assertEqual(3,self.booking['supply_maps']['0'][pid]['bonus'])
        self.assertFalse(supplies.data(self.state.career)['stock'])
        self.assertFalse(supplies.data(self.state.career)['active'])


if __name__=='__main__': unittest.main()
