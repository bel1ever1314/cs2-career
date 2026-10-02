using CareerMatch;

internal static class TacticalTravelGaitRegression
{
    internal static void Run()
    {
        var checks = 0;
        void Check(bool okay, string label) { checks++; if (!okay) throw new Exception(label); }
        void Reject(Action operation, string reason)
        {
            Exception? failure = null;
            try { operation(); } catch (Exception ex) { failure = ex; }
            Check(failure is not null && failure.Message.Contains(reason), "explicit failure: " + reason);
        }
        var clock = new Monotonic(); var api = new Inputs(clock); var gait = new TacticalTravelGait(api, 4, clock);
        Check(!gait.Active && gait.Mode == "", "new gait owns no inputs");
        gait.Release(); gait.Release();
        Check(api.Events.Count == 0, "inactive release is idempotent");
        for (var tick = 0; tick < 256; tick++)
        {
            clock.Set(tick/64d); gait.Keep("run", tick/64f);
            Check(gait.Active && gait.Mode == "run" && api.Suppressions.Count == 1 && api.Injections.Count == 0,
                "run keeps only one SPEED suppression at tick " + tick);
        }
        Check(api.SuppressionStarts == 1 && api.InjectionStarts == 0
            && api.Suppressions.Single().Value == (4, 1UL << 16), "run never injects movement or repeatedly starts tokens");
        gait.Release(); gait.Release();
        Check(!gait.Active && gait.Mode == "" && api.SuppressionCancels == 1 && api.Suppressions.Count == 0,
            "run release cancels only the owned suppression once");

        clock = new Monotonic(); api = new Inputs(clock); gait = new TacticalTravelGait(api, 5, clock);
        for (var tick = 0; tick <= 256; tick++)
        {
            clock.Set(tick/64d); gait.Keep("walk", tick/64f);
            Check(gait.Active && gait.Mode == "walk" && api.Injections.Count == 1 && api.Suppressions.Count == 0,
                "walk keeps one finite SPEED injection at tick " + tick);
        }
        Check(api.InjectionStarts == 17 && api.InjectionCancels == 16 && api.MaximumInjections == 2,
            "64-tick walk renews each .25 second with one bounded overlap and no accumulated tokens");
        Check(api.Injections.Single().Value.Slot == 5 && api.Injections.Single().Value.Mask == 1UL << 16
            && api.Durations.All(d => d == 500), "walk injects SPEED only for exactly 500ms");
        Check(api.Events[1].StartsWith("inject:") && api.Events[2].StartsWith("cancel_injection:"),
            "first walk renewal creates replacement before cancelling previous token");
        gait.Release(); gait.Release();
        Check(api.Injections.Count == 0 && api.InjectionCancels == 17 && !gait.Active && gait.Mode == "",
            "walk release removes only its latest token once");

        clock = new Monotonic(); api = new Inputs(clock); gait = new TacticalTravelGait(api, 6, clock);
        gait.Keep("walk", 10); var first = api.Injections.Single().Key;
        clock.Set(.24); gait.Keep("walk", 10);
        Check(api.InjectionStarts == 1, "neither clock elapsed .25 seconds yet: no renewal churn");
        clock.Set(.25); gait.Keep("walk", 10);
        Check(api.InjectionStarts == 2 && !api.Injections.ContainsKey(first),
            "steady-clock deadline renews even while game time is frozen");
        first = api.Injections.Single().Key; clock.Set(2);
        gait.Keep("walk", 10.015625f);
        Check(api.InjectionStarts == 3 && api.Injections.Count == 1 && api.MissingInjectionCancels == 1
            && !api.Injections.ContainsKey(first), "first Keep after pause/slow frame renews expired token and accepts -1");
        first = api.Injections.Single().Key;
        gait.Keep("walk", 10.265625f);
        Check(api.InjectionStarts == 4 && !api.Injections.ContainsKey(first),
            "game-clock deadline also renews when monotonic clock has not advanced");
        first = api.Injections.Single().Key; gait.Keep("walk", 1);
        Check(api.InjectionStarts == 5 && !api.Injections.ContainsKey(first),
            "game-clock rollback renews rather than assuming finite native token lifetime");
        clock.Set(100); api.ClearExpired(); gait.Release();
        Check(!gait.Active && api.Injections.Count == 0 && api.MissingInjectionCancels == 2,
            "Release accepts a previously expired finite token without claiming cancellation failure");

        clock = new Monotonic(); api = new Inputs(clock); gait = new TacticalTravelGait(api, 7, clock);
        gait.Keep("run", 0); api.Events.Clear(); gait.Keep("walk", 0);
        Check(api.Events[0].StartsWith("cancel_suppression:") && api.Events[1].StartsWith("inject:")
            && api.Suppressions.Count == 0 && api.Injections.Count == 1, "run-to-walk clears old mode first");
        api.Events.Clear(); gait.Keep("run", 0);
        Check(api.Events[0].StartsWith("cancel_injection:") && api.Events[1].StartsWith("suppress:")
            && api.Suppressions.Count == 1 && api.Injections.Count == 0, "walk-to-run clears old mode immediately");
        foreach (var mode in new string?[] { null, "", "RUN", "Walk", "auto", "jump", "forward" })
        {
            var before = api.Events.Count;
            Reject(() => gait.Keep(mode!, 0), "travel_gait_mode_invalid");
            Check(gait.Active && gait.Mode == "run" && api.Events.Count == before,
                "invalid mode cannot mutate existing ownership");
        }
        foreach (var now in new[] { float.NaN, float.PositiveInfinity, float.NegativeInfinity })
        {
            var before = api.Events.Count;
            Reject(() => gait.Keep("walk", now), "now");
            Check(gait.Active && gait.Mode == "run" && api.Events.Count == before,
                "nonfinite time rejected before mode switch or API call");
        }
        gait.Release(); gait.Keep("walk", float.MaxValue); clock.Set(.25); gait.Keep("walk", float.MaxValue);
        Check(api.InjectionStarts == 3, "finite extreme game clock cannot prevent monotonic renewal");
        gait.Release();

        clock = new Monotonic(); api = new Inputs(clock);
        var owner = new TacticalTravelGait(api, 8, clock); var other = new TacticalTravelGait(api, 8, clock);
        owner.Keep("walk", 0); other.Keep("walk", 0);
        var foreignInjection = api.Injections.Keys.Last(); owner.Release();
        Check(other.Active && api.Injections.Count == 1 && api.Injections.ContainsKey(foreignInjection),
            "same-slot walk owners release only their own tokens");
        other.Keep("run", 0); owner.Keep("run", 0);
        var foreignSuppression = api.Suppressions.Keys.First(); owner.Release();
        Check(other.Active && api.Suppressions.Count == 1 && api.Suppressions.ContainsKey(foreignSuppression),
            "same-slot run owners release only their own suppression tokens");
        other.Release();

        foreach (var mode in new[] { "run", "walk" })
        foreach (var throwing in new[] { false, true })
        {
            clock = new Monotonic(); api = new Inputs(clock) { RejectStart = !throwing, ThrowStart = throwing };
            gait = new TacticalTravelGait(api, 9, clock);
            Reject(() => gait.Keep(mode, 0), throwing ? "fake_start_failed" : "rejected");
            Check(!gait.Active && gait.Mode == "" && api.Injections.Count == 0 && api.Suppressions.Count == 0,
                "failed initial acquisition leaves no local token or mode");
            api.RejectStart = api.ThrowStart = false; gait.Keep(mode, 0); gait.Release();
            Check(!gait.Active, "valid acquisition recovers after initial refusal");
        }
        clock = new Monotonic(); api = new Inputs(clock); gait = new TacticalTravelGait(api, 10, clock);
        gait.Keep("walk", 0); api.RejectStart = true; clock.Set(.25);
        Reject(() => gait.Keep("walk", .25f), "travel_gait_injection_rejected");
        Check(!gait.Active && gait.Mode == "" && api.Injections.Count == 0,
            "failed renewal releases the previous owned injection");

        foreach (var throwing in new[] { false, true })
        {
            clock = new Monotonic(); api = new Inputs(clock); gait = new TacticalTravelGait(api, 11, clock);
            gait.Keep("walk", 0); var old = api.Injections.Single().Key;
            if (throwing) api.InjectionCancelThrows.Add(old); else api.InjectionCancelResults[old] = -2;
            clock.Set(.25);
            Reject(() => gait.Keep("walk", .25f), throwing ? "fake_cancel_failed" : "cancel_rejected:-2");
            Check(!gait.Active && gait.Mode == "" && api.Injections.Count == 1 && api.Injections.ContainsKey(old),
                "failed old-token cancellation recovers replacement but does not claim native cancellation");
            var cancels = api.InjectionCancels; gait.Release();
            Check(api.InjectionCancels == cancels, "failed cancellation has locally idempotent cleanup");
            clock.Set(1); api.ClearExpired();
            Check(api.Injections.Count == 0, "failed cancellation still leaves only finite native injection lifetime");
        }
        foreach (var result in new[] { -2, 1 })
        {
            clock = new Monotonic(); api = new Inputs(clock); gait = new TacticalTravelGait(api, 12, clock);
            gait.Keep("walk", 0); api.InjectionCancelResults[api.Injections.Single().Key] = result;
            Reject(gait.Release, "cancel_rejected:" + result);
            Check(!gait.Active && gait.Mode == "", "unknown injection cancellation return clears local state and throws");
        }
        clock = new Monotonic(); api = new Inputs(clock); gait = new TacticalTravelGait(api, 12, clock);
        gait.Keep("walk", 0); var failedOld = api.Injections.Single().Key;
        api.InjectionCancelResults[failedOld] = -2;
        api.InjectionCancelResults[failedOld+1] = -2;
        clock.Set(.25); AggregateException? combinedFailure = null;
        try { gait.Keep("walk", .25f); } catch (AggregateException ex) { combinedFailure = ex; }
        Check(combinedFailure?.InnerExceptions.Count == 2 && !gait.Active && gait.Mode == ""
            && api.InjectionCancels == 2 && api.Injections.Count == 2,
            "failed old and replacement cleanup report both errors without claiming native success");
        clock.Set(1); api.ClearExpired();
        Check(api.Injections.Count == 0, "even double-cancellation failure cannot create infinite walk injection tokens");
        foreach (var throwing in new[] { false, true })
        {
            clock = new Monotonic(); api = new Inputs(clock); gait = new TacticalTravelGait(api, 13, clock);
            gait.Keep("run", 0); api.RejectSuppressionCancel = !throwing; api.ThrowSuppressionCancel = throwing;
            var injections = api.InjectionStarts;
            Reject(() => gait.Keep("walk", 0), throwing ? "fake_cancel_failed" : "suppression_cancel_rejected");
            Check(!gait.Active && gait.Mode == "" && api.InjectionStarts == injections && api.Suppressions.Count == 1,
                "failed mode-change cancellation clears local state and never acquires the opposite gait");
            var cancels = api.SuppressionCancels; gait.Release();
            Check(cancels == api.SuppressionCancels, "suppression cancellation failure is locally idempotent");
        }
        Console.WriteLine($"{checks} tactical travel-gait checks passed (SPEED-only owned tokens, finite walk renewal, independent clocks, failure recovery; no native or live CS2 calls).");
    }

    private sealed class Monotonic : TimeProvider
    {
        private long _timestamp;
        public override long TimestampFrequency => 1_000_000;
        public override long GetTimestamp() => _timestamp;
        internal void Set(double seconds) => _timestamp = (long)Math.Round(seconds*TimestampFrequency);
    }

    private sealed class Inputs(Monotonic clock) : ITacticalTravelApi
    {
        internal readonly Dictionary<long, (int Slot, ulong Mask)> Suppressions = [];
        internal readonly Dictionary<long, (int Slot, ulong Mask, long Expires)> Injections = [];
        internal readonly Dictionary<long, int> InjectionCancelResults = [];
        internal readonly HashSet<long> InjectionCancelThrows = [];
        internal readonly List<string> Events = [];
        internal readonly List<int> Durations = [];
        internal int SuppressionStarts, SuppressionCancels, InjectionStarts, InjectionCancels, MissingInjectionCancels, MaximumInjections;
        internal bool RejectStart, ThrowStart, RejectSuppressionCancel, ThrowSuppressionCancel;
        private long _serial;
        public int IsLocked(int slot, int kind) => throw new Exception("gait must not take native decision/aim/movement locks");
        public long StartMove(int slot) => throw new Exception("gait must not inject direction");
        public int UpdateMove(int slot, long token) => throw new Exception("gait must not update direction");
        public int CancelMove(int slot, long token) => throw new Exception("gait must not cancel another movement lease");
        public long Suppress(int slot, ulong mask)
        {
            if (mask != 1UL << 16) throw new Exception("gait suppression touches a non-SPEED button");
            SuppressionStarts++;
            if (ThrowStart) throw new IOException("fake_start_failed");
            if (RejectStart) return -1;
            var token = ++_serial; Suppressions.Add(token, (slot, mask)); Events.Add("suppress:" + token); return token;
        }
        public int CancelSuppression(int slot, long token)
        {
            SuppressionCancels++; Events.Add("cancel_suppression:" + token);
            if (ThrowSuppressionCancel) throw new IOException("fake_cancel_failed");
            if (RejectSuppressionCancel) return -1;
            return Suppressions.TryGetValue(token, out var owned) && owned.Slot == slot && Suppressions.Remove(token) ? 0 : -1;
        }
        public long Inject(int slot, ulong mask, int durationMs)
        {
            if (mask != 1UL << 16 || durationMs != 500) throw new Exception("gait injection must be finite SPEED-only");
            InjectionStarts++;
            if (ThrowStart) throw new IOException("fake_start_failed");
            if (RejectStart) return -1;
            ClearExpired(); var token = ++_serial;
            Injections.Add(token, (slot, mask, clock.GetTimestamp()+durationMs*1000));
            MaximumInjections = Math.Max(MaximumInjections, Injections.Count);
            Durations.Add(durationMs); Events.Add("inject:" + token); return token;
        }
        public int CancelInjection(int slot, long token)
        {
            InjectionCancels++; Events.Add("cancel_injection:" + token);
            if (InjectionCancelThrows.Contains(token)) throw new IOException("fake_cancel_failed");
            if (InjectionCancelResults.TryGetValue(token, out var result)) return result;
            ClearExpired();
            if (Injections.TryGetValue(token, out var owned) && owned.Slot == slot && Injections.Remove(token)) return 0;
            MissingInjectionCancels++; return -1;
        }
        internal void ClearExpired()
        {
            foreach (var token in Injections.Where(p => p.Value.Expires <= clock.GetTimestamp()).Select(p => p.Key).ToArray())
                Injections.Remove(token);
        }
    }
}
