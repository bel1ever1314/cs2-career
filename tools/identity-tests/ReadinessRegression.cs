using CareerMatch;

internal static class ReadinessRegression
{
    public static void Run()
    {
        int count = 0;
        void Check(bool ok, string message) { count++; if (!ok) throw new Exception(message); }
        var gate = new RosterReadiness();
        var health = new SessionHealth();
        Check(gate.Error == "", "new session ready state");
        gate.Missing(0, false);
        Check(gate.Error.Contains("等待"), "loading is pending, not a permanent statistics failure");
        gate.Missing(0, false);
        gate.Ready(0);
        Check(gate.Error == "", "ten players at 0:0 clears transient readiness");
        gate.ObserveScore(13);
        Check(gate.Error == "", "later complete 13-round match not poisoned by startup");
        gate.Missing(13, false);
        health.StatisticsError = "damage identity unresolved";
        gate.Ready(13);
        Check(health.ResultError == "damage identity unresolved", "readiness cannot erase combat error");
        gate.Reset(); gate.Missing(0, false); gate.ObserveScore(1); gate.Ready(1);
        Check(gate.Error.Contains("不完整"), "missed opening round remains rejected even with ten players later");
        gate.Reset(); gate.Missing(5, false); gate.Missing(6, false); gate.Ready(6);
        Check(gate.Error.Contains("不完整"), "repeated missing check cannot reset gap start");
        gate.Reset(); gate.Missing(5, true); gate.Ready(5);
        Check(gate.Error.Contains("不完整"), "interrupted tracked round cannot silently recover");
        gate.Reset(); gate.Missing(5, false); gate.Ready(5); gate.ObserveScore(6);
        Check(gate.Error == "", "between-round temporary wait recovers without a scored gap");
        gate.Reset();
        Check(gate.Error == "", "new map clears previous match readiness");
        // Live trace: round_start tick 507 saw an unassigned human; tick 954
        // had the correct ten players. Freeze-end must retry BEFORE score 1.
        gate.Missing(0, false);
        gate.Ready(0); // shared BeginOfficialRound invoked at freeze_end
        gate.ObserveScore(1);
        Check(gate.Error == "", "late opening identity recovers at freeze-end before first score");
        gate.Reset(); gate.Missing(0, false); gate.ObserveScore(1); gate.Ready(1);
        Check(gate.Error.Contains("不完整"), "genuinely missed first combat round is still not importable");
        Console.WriteLine($"{count} roster-readiness checks passed (startup recovery, real loss, unrelated errors).");
    }
}
