"""Production wiring invariants alongside the executable C# handoff scenarios."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'vendor' / 'CareerMatch'


class TacticalSafetyWiringTests(unittest.TestCase):
    def test_damage_releases_before_stats_filter(self):
        source = (ROOT / 'CareerMatch.Events.cs').read_text('utf-8')
        hurt = source.split('private HookResult OnPlayerHurt(', 1)[1].split('private HookResult OnPlayerDeath(', 1)[0]
        self.assertLess(hurt.index('OnTacticalDamage(ev);'), hurt.index('ev.DmgHealth <= 0'))
        self.assertLess(hurt.index('OnTacticalDamage(ev);'), hurt.index('victim.Team == attacker.Team'))

    def test_wait_and_guard_check_danger_before_acquiring_movement(self):
        for name, marker in [('CareerMatch.CustomTactics.cs', 'private void TickCustomTactic()'),
                             ('CareerMatch.PostPlantTactics.cs', 'private void TickPostPlantTactic()')]:
            tick = (ROOT / name).read_text('utf-8').split(marker, 1)[1]
            self.assertLess(tick.index('ReleaseTacticForDanger('), tick.index('actor.Hold.Keep()'))
            self.assertIn('pawn.Health < actor.Health || bot.IsAvoidingGrenade.Timestamp > now', tick)

    def test_native_handoff_not_reclaimed(self):
        natural = (ROOT / 'CareerMatch.Natural.cs').read_text('utf-8')
        self.assertEqual(2, natural.count('NativeSafetyOwnsActor(player)'))
        tactics = (ROOT / 'CareerMatch.Tactics.cs').read_text('utf-8')
        reset = tactics.split('private void ResetTacticalCommands(', 1)[1].split('private void StopTacticalCommands(', 1)[0]
        self.assertIn('_tacticalSafetyHandoffs.Clear();', reset)
        self.assertIn('"unload" or "player_radio" or "danger_handoff"', tactics)
        self.assertIn('NativeRadioOwnsActor(p) || NativeSafetyOwnsActor(p)', tactics)
        plant = (ROOT / 'CareerMatch.PostPlantTactics.cs').read_text('utf-8')
        self.assertIn('!NativeRadioOwnsActor(p) && !NativeSafetyOwnsActor(p)', plant)
        native = (ROOT / 'TacticalNativeNavigation.cs').read_text('utf-8')
        self.assertIn('nativeBot.IsAvoidingGrenade.Timestamp > Server.CurrentTime', native)

    def test_postplant_success_is_silent_but_diagnostic_retained(self):
        source = (ROOT / 'CareerMatch.PostPlantTactics.cs').read_text('utf-8')
        self.assertNotIn('炸弹已下：原战术结束', source)
        self.assertIn('TacticalTrace("post_plant_started"', source)
        self.assertIn('包点任务未能建立', source)

    def test_final_defense_keeps_safety_objective_and_aim_handoffs(self):
        source = (ROOT / 'CareerMatch.CustomTactics.cs').read_text('utf-8')
        tick = source.split('private void TickCustomTactic()', 1)[1]
        self.assertIn('binding.Route, plan.Side, pawn.Health', source)
        self.assertLess(tick.index('ObjectiveNeedsControl('), tick.index('actor.Hold.Keep()'))
        self.assertLess(tick.index('ReleaseTacticForDanger('), tick.index('actor.Hold.Keep()'))
        self.assertIn('Wait > 0 || actor.Clock.FinalHold', tick)
        self.assertIn('step.Wait <= 0 && !actor.Clock.FinalHold', source)
        self.assertIn('!settled || nativeAction', source)
        self.assertIn('custom_final_hold_started', tick)
        cleanup = (ROOT / 'CareerMatch.Tactics.cs').read_text('utf-8')
        self.assertIn('"danger_handoff" or "objective_handoff"', cleanup)


if __name__ == '__main__':
    unittest.main()
