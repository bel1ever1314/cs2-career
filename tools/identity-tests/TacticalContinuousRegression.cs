using CareerMatch;

internal static class TacticalContinuousRegression
{
    internal static void Run()
    {
        var count = 0;
        void Check(bool value, string message) { count++; if (!value) throw new Exception(message); }
        var move = new TacticalContinuousMove(); var calls = 0;
        bool Busy(out string reason) { calls++; reason = "navigation_path_rate_limited"; return false; }
        bool Ready(out string reason) { calls++; reason = "successor_path_accepted"; return true; }
        Check(move.Tick(0, Busy, out _) == TacticalPathAction.Pending && calls == 1, "busy successor stays pending");
        for (var frame = 1; frame < 8; frame++)
            Check(move.Tick(frame/64f, Ready, out _) == TacticalPathAction.Pending && calls == 1,
                "rate-limited retries do not reroute every engine tick");
        Check(move.Tick(.125f, Ready, out _) == TacticalPathAction.Moving && calls == 2,
            "successor is moving ONLY after actual native acceptance");
        Check(move.Tick(.126f, Ready, out _) == TacticalPathAction.Moving && calls == 3,
            "a newly crossed waypoint can commit immediately");
        move.Reset();
        Check(move.Tick(0, Busy, out _) == TacticalPathAction.Pending, "fresh pending starts");
        Check(move.Tick(3.01f, Ready, out var why) == TacticalPathAction.Failed && why == "custom_successor_path_timeout",
            "no indefinite pending at a zero wait point");
        move.Reset();
        Check(move.Tick(4, (out string why) => { why = "native_combat_or_objective_retained"; return false; }, out _)
            == TacticalPathAction.Yielded, "combat never reports successor accepted");
        Check(move.Tick(4, Ready, out _) == TacticalPathAction.Moving, "combat releases the pending cycle");
        move.Reset();
        Check(move.Tick(10, (out string why) => { why = "navigation_path_unavailable"; return false; }, out _)
            == TacticalPathAction.Failed, "unreachable successor is not opened as old/default movement");
        foreach (var time in new[] { float.NaN, float.PositiveInfinity, float.NegativeInfinity })
        {
            var before = calls; var rejected = false;
            try { move.Tick(time, Ready, out _); } catch (ArgumentOutOfRangeException) { rejected = true; }
            Check(rejected && calls == before, "invalid time cannot execute a native callback");
        }
        var direct = new TacticalDirectMove();
        direct.AdoptCommitted();
        Check(direct.Committed && !direct.NeedsPreparation(true), "atomic successor skips zero-input path preparation");
        var start = 0; var path = 0; var renew = 0;
        Check(direct.Tick(20, true,
                (out string why) => { start++; why = "start"; return true; },
                (out string why) => { path++; why = "path"; return true; },
                (out string why) => { renew++; why = "renew"; return true; }, out _) == TacticalPathAction.Moving
            && start == 0 && path == 0 && renew == 1, "accepted successor only renews, not re-enters MoveTo");
        direct.Reset();
        Check(!direct.Committed && direct.NeedsPreparation(true), "combat/death/reset require a fresh path again");
        Check(!TacticalWaypointPolicy.IsTransit(TacticStepAction.Advanced, 2)
            && !TacticalWaypointPolicy.IsTransit(TacticStepAction.Completed, 0), "waiting and last waypoint never use through-point continuation");
        Console.WriteLine($"{count} continuous successor path checks passed (no zero-input hold requested; live CS2 untested).");
    }
}
