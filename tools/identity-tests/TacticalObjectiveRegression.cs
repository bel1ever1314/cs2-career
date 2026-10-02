using CareerMatch;

internal static class TacticalObjectiveRegression
{
    private sealed class MockInputs : ITacticalHoldApi
    {
        internal readonly Dictionary<long, ulong> Tokens = [];
        internal long Serial;
        internal int Starts, Cancels;
        public int IsLocked(int slot, int kind) => 0;
        public long StartMove(int slot) => throw new Exception("opening must not own movement");
        public int UpdateMove(int slot, long token) => throw new Exception("opening must not own movement");
        public int CancelMove(int slot, long token) => throw new Exception("opening must not own movement");
        public long Suppress(int slot, ulong mask) { Starts++; Tokens.Add(++Serial, mask); return Serial; }
        public int CancelSuppression(int slot, long token) { Cancels++; return Tokens.Remove(token) ? 0 : -1; }
    }
    internal static void Run()
    {
        var checks = 0;
        void Check(bool value, string message) { checks++; if (!value) throw new Exception(message); }
        foreach (var side in new[] { "t", "ct" })
        foreach (var atSite in new[] { false, true })
        foreach (var contact in new[] { false, true })
        {
            var action = TacticalObjectivePolicy.Decide(side, atSite, contact);
            Check(action == (contact ? TacticalBombAction.Combat : !atSite ? TacticalBombAction.Travel
                : side == "t" ? TacticalBombAction.Guard : TacticalBombAction.NativeDefuse),
                $"post-plant follows side/site/contact: {side},{atSite},{contact}");
        }
        var badSide = false;
        try { TacticalObjectivePolicy.Decide("spectator", true, false); } catch (ArgumentOutOfRangeException) { badSide = true; }
        Check(badSide, "spectator never receives a bomb task");
        var api = new MockInputs(); var first = new TacticalHoldControls.OpeningLease(api, 4);
        var replacement = new TacticalHoldControls.OpeningLease(api, 4);
        first.Start(); first.Start();
        Check(api.Starts == 1 && api.Tokens.Single().Value == 2, "opening only suppresses jump, once");
        replacement.Start(); first.Release(); first.Release();
        Check(api.Cancels == 1 && replacement.Active && api.Tokens.Count == 1,
            "old opening release cannot clear replacement token");
        replacement.Release();
        Check(api.Tokens.Count == 0 && api.Cancels == 2, "cancel/death/round-end can release all opening tokens");
        for (var tick = 0; tick <= 160; tick++)
        foreach (var committed in new[] { false, true })
        {
            var elapsed = tick/64f;
            Check(TacticalObjectivePolicy.OpeningGuardExpired(100+elapsed, 100, committed)
                == (elapsed >= 1.25f || committed && elapsed >= .75f),
                "opening guard expires without banning route jumps: " + tick);
        }
        Check(TacticalObjectivePolicy.Decide("t", true, false) == TacticalBombAction.Guard,
            "planting never resumes the previous opening route");
        var bomb = new TacticalObjectivePolicy.GuardPoint(0, 0, 0);
        TacticalObjectivePolicy.GuardPoint[] guardPoints = [new(256,0,0), new(0,256,0),
            new(-256,0,0), new(0,-256,0), new(500,0,0), new(0,0,400), new(900,0,0)];
        var occupied = new List<TacticalObjectivePolicy.GuardPoint>();
        for (var actor = 0; actor < 5; actor++)
        {
            var guard = TacticalObjectivePolicy.SelectGuard(bomb, bomb, guardPoints, occupied);
            Check(guard is not null, "five distinct NAV guards fit broader postplant region");
            Check(occupied.All(p => p.DistanceTo(guard!.Value) >= 160), "guard bodies do not share a plant pixel");
            Check(TacticalObjectivePolicy.GuardFloor(guard!.Value, bomb), "guard stays on a nearby floor");
            occupied.Add(guard.Value);
        }
        Check(TacticalObjectivePolicy.SelectGuard(bomb, bomb, guardPoints, occupied) is null,
            "full region does not silently assign duplicate guards");
        Check(TacticalObjectivePolicy.SelectGuard(guardPoints[0], bomb, guardPoints, []) == guardPoints[0],
            "unoccupied valid existing guard can remain where it is");
        Check(!TacticalObjectivePolicy.GuardFloor(new(float.NaN,0,0), bomb)
            && !TacticalObjectivePolicy.GuardFloor(new(0,0,400), bomb), "nonfinite and unrelated floor rejected");
        Check(TacticalObjectivePolicy.SelectGuard(bomb, bomb, [guardPoints[0]], [guardPoints[0]]) is null,
            "human occupying a guard spot is respected");
        Console.WriteLine($"{checks} opening-input and post-plant policy checks passed (pure rules, not CS2 execution).");
    }
}
