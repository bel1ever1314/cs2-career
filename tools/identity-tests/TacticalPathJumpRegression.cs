using CareerMatch;

internal static class TacticalPathJumpRegression
{
    internal static void Run()
    {
        var count = 0;
        void Check(bool ok, string label) { count++; if (!ok) throw new Exception(label); }
        void RejectTime(Action call, string label)
        {
            var rejected = false;
            try { call(); } catch (ArgumentOutOfRangeException) { rejected = true; }
            Check(rejected, label);
        }

        var api = new Inputs();
        var guard = new TacticalPathJumpGuard(api, 4);
        Check(!guard.Active && !guard.Preparing && guard.Remaining(0) == 0,
            "new path guard has no input ownership");
        guard.Committed(0); guard.Tick(0); guard.Release();
        Check(api.Starts == 0 && api.Cancelled.Count == 0,
            "commit/tick/release without Begin never acquire or cancel another owner's token");
        guard.Begin(0);
        Check(guard.Active && guard.Preparing && guard.Remaining(0) == TacticalPathJumpGuard.MaximumPreparationSeconds,
            "Begin arms a distinct pending-path cycle");
        Check(api.Tokens.Single().Value == (4, 1UL << 1) && api.MovementCalls == 0 && api.LockChecks == 0,
            "path handoff owns only JUMP: no movement, aim locks, duck, fire or use");
        for (var tick = 0; tick < 4*64; tick++)
        {
            guard.Tick(tick/64f);
            Check(guard.Active && guard.Preparing && api.Starts == 1 && api.Cancelled.Count == 0,
                "pending native path retains one owned jump token across ticks: " + tick);
        }
        guard.Tick(4);
        Check(!guard.Active && !guard.Preparing && guard.Remaining(4) == 0 && api.Tokens.Count == 0,
            "uncommitted path guard releases at its absolute four-second cap");
        guard.Committed(4); guard.Tick(100);
        Check(api.Starts == 1 && api.Cancelled.Count == 1,
            "late acceptance after expiry cannot resurrect a token");

        guard.Begin(10); guard.Committed(10.25f);
        Check(guard.Active && !guard.Preparing && guard.Remaining(10.25f) == TacticalPathJumpGuard.GraceSeconds,
            "path acceptance opens a fixed three-quarter-second jump-only handoff");
        for (var tick = 0; tick <= 128; tick++)
        {
            var now = 10.25f+tick/64f;
            guard.Committed(now); // A movement renewal may report acceptance again.
            guard.Tick(now);
            Check(guard.Active == (tick < 48) && !guard.Preparing && api.Starts == 2,
                "repeated commits/renewals do not extend or restart the handoff: " + tick);
        }
        Check(api.Cancelled.Count == 2 && api.Tokens.Count == 0,
            "real NAV jumps are not globally suppressed after the fixed handoff expires");

        guard.Begin(20); guard.Committed(20.5f); guard.Begin(20.75f);
        Check(guard.Active && guard.Preparing && api.Starts == 3,
            "actual next path can reuse its own active token while starting a new preparation cycle");
        guard.Tick(21.25f);
        Check(guard.Active && guard.Preparing,
            "new pending path is not released by the previous committed deadline");
        guard.Committed(22); guard.Committed(22.7f); guard.Tick(22.75f);
        Check(!guard.Active && api.Starts == 3 && api.Cancelled.Count == 3,
            "the replacement path also gets one fixed expiry without token churn");

        guard.Begin(30); guard.Committed(33.984375f); guard.Tick(34.734375f);
        Check(!guard.Active, "a near-cap successful preparation still receives exactly its own bounded grace");
        guard.Begin(40); guard.Committed(44);
        Check(!guard.Active && !guard.Preparing,
            "a committed call at the preparation cap releases instead of extending pending ownership");

        // Paused/frozen game time does not simulate elapsed physics. Neither
        // duplicate commits nor ticks change the original committed timestamp.
        guard.Begin(50); guard.Committed(50);
        for (var tick = 0; tick < 256; tick++)
        {
            guard.Committed(50); guard.Tick(50);
            Check(guard.Active && !guard.Preparing && guard.Remaining(50) == .75f,
                "frozen finite game time keeps the same finite deadline, not a new one: " + tick);
        }
        guard.Tick(50.75f);
        Check(!guard.Active, "the frozen-clock cycle releases as soon as game time reaches its original deadline");

        foreach (var terminal in new[] { "combat", "utility", "death", "takeover", "pawn_changed", "round_end", "final", "path_refused" })
        foreach (var committed in new[] { false, true })
        {
            var inputs = new Inputs(); var terminalGuard = new TacticalPathJumpGuard(inputs, 5);
            terminalGuard.Begin(100);
            if (committed) terminalGuard.Committed(100.25f);
            terminalGuard.Release(); terminalGuard.Release();
            Check(!terminalGuard.Active && !terminalGuard.Preparing && inputs.Cancelled.Count == 1 && inputs.Tokens.Count == 0,
                "explicit terminal/native handoff releases its owned token immediately: " + terminal + "/" + committed);
            for (var tick = 0; tick < 64; tick++)
            {
                terminalGuard.Committed(101+tick/64f); terminalGuard.Tick(101+tick/64f);
                Check(inputs.Starts == 1 && inputs.Cancelled.Count == 1 && !terminalGuard.Active,
                    "late ticks cannot restart terminal path guard: " + terminal + "/" + committed + "/" + tick);
            }
        }

        var independent = new Inputs();
        var movement = new TacticalHoldControls.Lease(independent, 6);
        var handoff = new TacticalPathJumpGuard(independent, 6);
        var other = new TacticalPathJumpGuard(independent, 6);
        movement.Keep(); handoff.Begin(200); other.Begin(200);
        Check(independent.Tokens.Count == 3 && independent.Moves.Count == 1,
            "path hold, handoff and another owner have independent suppression tokens on one slot");
        movement.Release();
        Check(handoff.Active && other.Active && independent.Tokens.Count == 2 && independent.Moves.Count == 0,
            "releasing zero movement cannot expose jump while the handoff still owns its token");
        handoff.Committed(201); handoff.Tick(201.75f);
        Check(!handoff.Active && other.Active && independent.Tokens.Count == 1,
            "handoff expiry cannot remove another owner even when both suppress the same jump bit");
        other.Release();
        Check(independent.Tokens.Count == 0, "independent owner later releases only its own token");

        foreach (var time in new[] { float.NaN, float.PositiveInfinity, float.NegativeInfinity })
        {
            var invalidApi = new Inputs(); var invalidGuard = new TacticalPathJumpGuard(invalidApi, 7);
            RejectTime(() => invalidGuard.Begin(time), "nonfinite Begin rejected before token acquisition");
            RejectTime(() => invalidGuard.Committed(time), "nonfinite Committed rejected");
            RejectTime(() => invalidGuard.Tick(time), "nonfinite Tick rejected");
            RejectTime(() => invalidGuard.Remaining(time), "nonfinite diagnostic time rejected");
            Check(invalidApi.Starts == 0 && invalidApi.Cancelled.Count == 0 && !invalidGuard.Active,
                "invalid clock on an inactive guard has no native side effects");
            invalidGuard.Begin(300); invalidGuard.Committed(300);
            RejectTime(() => invalidGuard.Begin(time), "invalid replacement cannot mutate an accepted cycle");
            RejectTime(() => invalidGuard.Committed(time), "invalid repeat commit cannot extend an accepted cycle");
            RejectTime(() => invalidGuard.Tick(time), "invalid ticking cannot mutate an accepted cycle");
            Check(invalidGuard.Active && !invalidGuard.Preparing && invalidGuard.Remaining(300) == .75f && invalidApi.Starts == 1,
                "invalid time preserves the previously owned cycle for normal cleanup");
            invalidGuard.Tick(300.75f);
            Check(!invalidGuard.Active && invalidApi.Cancelled.Count == 1,
                "valid deadline still releases after invalid-clock refusal");
        }
        guard.Begin(float.MaxValue);
        Check(guard.Remaining(float.MaxValue) == 4 && guard.Preparing,
            "finite extreme clock retains the preparation duration without addition precision loss");
        guard.Committed(float.MaxValue);
        Check(guard.Remaining(float.MaxValue) == .75f,
            "finite extreme committed clock retains the fixed grace");
        guard.Release(); guard.Begin(-float.MaxValue); guard.Committed(-float.MaxValue); guard.Tick(float.MaxValue);
        Check(!guard.Active, "finite extreme elapsed subtraction cannot overflow into a non-expiring guard");

        foreach (var throwing in new[] { false, true })
        {
            var failingApi = new Inputs { RejectStart = !throwing, ThrowStart = throwing };
            var failing = new TacticalPathJumpGuard(failingApi, 8);
            var rejected = false;
            try { failing.Begin(400); } catch (Exception) { rejected = true; }
            Check(rejected && !failing.Active && !failing.Preparing && failing.Remaining(400) == 0
                && failingApi.Tokens.Count == 0 && failingApi.Cancelled.Count == 0,
                "failed acquisition leaves no partial guard or unrelated cancellation: " + throwing);
            failingApi.RejectStart = failingApi.ThrowStart = false;
            failing.Begin(401); failing.Release();
            Check(failingApi.Tokens.Count == 0 && failingApi.Cancelled.Count == 1,
                "a refused guard can start a later valid path cycle cleanly");
        }
        foreach (var throwing in new[] { false, true })
        {
            var failingApi = new Inputs { RejectCancel = !throwing, ThrowCancel = throwing };
            var failing = new TacticalPathJumpGuard(failingApi, 9);
            failing.Begin(500);
            var rejected = false;
            try { failing.Release(); } catch (Exception) { rejected = true; }
            Check(rejected && !failing.Active && !failing.Preparing && failing.Remaining(500) == 0
                && failingApi.Cancelled.Count == 1,
                "cancellation error clears local cycle and attempts only its exact token: " + throwing);
            failing.Release();
            Check(failingApi.Cancelled.Count == 1, "error cleanup remains locally idempotent");
        }
        Console.WriteLine($"{count} per-path jump-handoff checks passed (owned JUMP-only tokens, fixed game-time grace, bounded preparation, native/terminal release; no live CS2 jump claim).");
    }

    private sealed class Inputs : ITacticalHoldApi
    {
        internal readonly Dictionary<long, (int Slot, ulong Mask)> Tokens = [];
        internal readonly HashSet<long> Moves = [];
        internal readonly List<long> Cancelled = [];
        internal int Starts, MovementCalls, LockChecks;
        internal bool RejectStart, ThrowStart, RejectCancel, ThrowCancel;
        private long _serial;
        public int IsLocked(int slot, int kind) { LockChecks++; return 0; }
        public long StartMove(int slot) { MovementCalls++; var token = ++_serial; Moves.Add(token); return token; }
        public int UpdateMove(int slot, long token) { MovementCalls++; return Moves.Contains(token) ? 0 : -1; }
        public int CancelMove(int slot, long token) { MovementCalls++; return Moves.Remove(token) ? 0 : -1; }
        public long Suppress(int slot, ulong mask)
        {
            Starts++;
            if (ThrowStart) throw new IOException("fake_suppression_start_failed");
            if (RejectStart) return -1;
            var token = ++_serial; Tokens.Add(token, (slot, mask)); return token;
        }
        public int CancelSuppression(int slot, long token)
        {
            Cancelled.Add(token);
            var removed = Tokens.Remove(token);
            if (ThrowCancel) throw new IOException("fake_suppression_cancel_failed");
            return !RejectCancel && removed ? 0 : -1;
        }
    }
}
