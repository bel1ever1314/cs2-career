using CareerMatch;

internal static class TacticalRadioRegression
{
    public static void Run()
    {
        var count = 0;
        void Check(bool ok, string label) { count++; if (!ok) throw new Exception("radio: " + label); }
        var context = new TacticalCommandContext
        {
            MatchNonce = "match-1", Round = 4, SpeakerId = "human", Side = "t",
            AuthorizedMatch = true, AuthorizedHuman = true, SpeakerValid = true,
        };
        var speaker = new TacticalRadioSpeaker(context, 0, 123, 1000, true, true);
        TacticalBotCandidate[] candidates =
        [
            new("b1", "t", true, true, true), new("b2", " T ", true, true, true),
            new("enemy", "ct", true, true, true), new("human", "t", false, true, true),
            new("other-human", "t", false, true, true), new("taken-over", "t", true, true, true, true),
            new("dead", "t", true, true, false), new("invalid", "t", true, false, true),
            new("spectator", "spectator", true, true, true), new("", "t", true, true, true),
            new("human", "t", true, true, true), new("b1", "t", true, true, true),
        ];
        var policy = new TacticalRadioPolicy();
        foreach (var command in TacticalRadioPolicy.Commands)
        {
            policy.Reset();
            var before = policy.Revision;
            Check(policy.BeginCommand(command.ToUpperInvariant(), speaker), command + " command pre accepted");
            Check(policy.Revision == before && !policy.Owns("match-1", 4, "t", "b1"),
                "typed command alone cannot release a tactic: " + command);
            var handoff = policy.Confirm(speaker, 19, candidates);
            Check(handoff is { } && handoff.Command == command
                && handoff.Recipients.SequenceEqual(new[] { "b1", "b2" }),
                "engine acceptance targets only living ledger teammates: " + command);
            Check(policy.Owns("match-1", 4, "t", "b1") && policy.Owns("match-1", 4, " T ", "b2")
                && !policy.Owns("match-1", 4, "ct", "enemy"), "no opposite-team override: " + command);
            Check(policy.Confirm(speaker, 19, candidates) is null, "duplicate engine event consumed once: " + command);
        }
        foreach (var command in new[] { "enemyspot", "sectorclear", "inposition", "reportingin", "report",
            "takingfire", "roger", "negative", "cheer", "thanks", "compliment", "enemydown",
            "radio", "radio1", "radio2", "radio3", "playerchatwheel", "say", "say_team", "stormfront",
            "followme;quit", "go now", "", "!followme" })
        {
            policy.Reset();
            Check(!policy.BeginCommand(command, speaker) && policy.Confirm(speaker, 19, candidates) is null,
                "information/chat/menu/non-command does not replace a purpose: " + command);
        }
        void Reject(TacticalRadioSpeaker value, string label)
        {
            policy.Reset();
            Check(!policy.BeginCommand("followme", value), label);
        }
        foreach (var c in new[]
        {
            context with { AuthorizedMatch = false }, context with { AuthorizedHuman = false },
            context with { SpeakerValid = false }, context with { SpeakerIsBot = true },
            context with { Observer = true }, context with { Warmup = true }, context with { MatchCompleted = true },
            context with { Side = "spectator" }, context with { Side = "" }, context with { SpeakerId = "" },
            context with { MatchNonce = "" }, context with { Round = 0 },
        }) Reject(speaker with { Context = c }, "invalid session, stable identity or side rejected");
        Reject(speaker with { Alive = false }, "dead speaker rejected");
        Reject(speaker with { RoundActive = false }, "inactive round rejected");
        Reject(speaker with { Pawn = 0 }, "missing speaker pawn rejected");
        Reject(speaker with { Slot = -1 }, "server console rejected");
        // A human issuing radio while taking over a bot is still an authorized
        // human. The controlled body is excluded from recipients above.
        Check(policy.BeginCommand("followme", speaker with { HumanControlled = true }), "human takeover may issue real radio");
        Check(policy.Confirm(speaker with { HumanControlled = true }, 19, candidates) is not null,
            "human takeover never means applying movement to the human");

        policy.Reset(); policy.BeginCommand("holdpos", speaker);
        foreach (var mismatch in new[]
        {
            speaker with { Slot = 1 }, speaker with { Pawn = 124 }, speaker with { Tick = 1001 },
            speaker with { Context = context with { MatchNonce = "match-2" } },
            speaker with { Context = context with { Round = 5 } },
            speaker with { Context = context with { SpeakerId = "foreign" } },
            speaker with { Context = context with { Side = "ct" } },
            speaker with { Context = context with { SpeakerIsBot = true } },
        }) Check(policy.Confirm(mismatch, 19, candidates) is null, "event cannot steal another command scope");
        Check(policy.Confirm(speaker, 0, candidates) is null, "empty radio slot is not an accepted order");
        Check(policy.Confirm(speaker, 19, candidates) is not null, "matching synchronous accepted event confirms");
        policy.Reset(); var rejectedRevision = policy.Revision;
        policy.BeginCommand("followme", speaker); policy.EndCommand("followme", speaker.Slot);
        Check(!policy.HasPendingCommand && policy.Confirm(speaker, 19, candidates) is null
            && policy.Revision == rejectedRevision, "cooldown reject/post closure never cancels a tactic");
        Check(policy.Confirm(speaker with { Tick = 1001 }, 19, candidates) is null,
            "later grenade/chatter event cannot revive the closed candidate");
        policy.BeginCommand("followme", speaker); policy.Reset();
        Check(policy.Confirm(speaker, 19, candidates) is null, "round reset invalidates unconfirmed event");

        // Full wait handoff harness uses the production input leases and
        // cancellation runner, not a twenty-second timeout or native DLL.
        policy.BeginCommand("followme", speaker);
        var accepted = policy.Confirm(speaker, 19, candidates)!;
        var api = new RadioHoldApi();
        var hold = new TacticalHoldControls.Lease(api, 1); hold.Keep();
        var pathHold = new TacticalHoldControls.Lease(api, 1); pathHold.Keep();
        var opening = new TacticalHoldControls.OpeningLease(api, 1); opening.Start();
        var opponentHold = new TacticalHoldControls.Lease(api, 8); opponentHold.Keep();
        var wait = new TacticalStepClock([20, 0]);
        Check(wait.Tick(5, true, false) == TacticStepAction.Wait && wait.Remaining == 20, "node holds twenty seconds before radio");
        var active = new Dictionary<string, TacticalStepClock> { ["b1"] = wait };
        var callbacks = new List<Action>(); var issues = 0;
        var oldRevision = policy.Revision;
        callbacks.Add(() => { if (policy.Revision == oldRevision) issues++; });
        policy.BeginCommand("fallback", speaker); accepted = policy.Confirm(speaker, 19, candidates)!;
        Check(active.Remove("b1"), "remove actor immediately, not at end of node wait");
        var errors = 0; var lookReleased = false;
        TacticalRadioRelease.All(_ => errors++, () => throw new InvalidOperationException("synthetic look release failure"),
            hold.Release, pathHold.Release, opening.Release, () => lookReleased = true);
        Check(errors == 1 && lookReleased && !hold.Active && !pathHold.Active && !opening.Active,
            "one release failure does not skip hold, preparation, jump or view cleanup");
        Check(api.Moves.Count == 1 && api.Moves.Values.Single() == 8 && opponentHold.Active,
            "cancel only own tokens; opposite team and other owners unaffected");
        for (var i = 0; i < 200; i++)
            foreach (var clock in active.Values) { clock.Tick(5+i*.25f, true, false); issues++; }
        foreach (var callback in callbacks) callback();
        Check(wait.Remaining == 20 && issues == 0, "old wait and next-frame postplant task never resume after native radio");
        Check(policy.Owns("match-1", 4, "t", "b1"), "natural task layer remains suppressed for the rest of this round");
        Check(!policy.Owns("match-1", 5, "t", "b1") && !policy.Owns("match-2", 4, "t", "b1")
            && !policy.Owns("match-1", 4, "t", "replacement"), "override cannot leak across round/session/identity reuse");
        Check(TacticalRadioPolicy.SameScope(new("match-1", 4, "t", "human", TacticalOrder.Playbook, "", "x"), accepted)
            && !TacticalRadioPolicy.SameScope(new("match-1", 4, "ct", "human", TacticalOrder.Playbook, "", "x"), accepted)
            && !TacticalRadioPolicy.SameScope(new("match-1", 5, "t", "human", TacticalOrder.Playbook, "", "x"), accepted),
            "pending intent removal is same-team and exact-round only");
        policy.Supersede(new("match-1", 4, "ct", "human", TacticalOrder.RushB, "B"));
        Check(policy.Owns("match-1", 4, "t", "b1"), "opposite side explicit tactic cannot reclaim radio team");
        policy.Supersede(new("match-1", 4, "t", "human", TacticalOrder.RushA, "A"));
        Check(!policy.Owns("match-1", 4, "t", "b1"), "new explicitly accepted same-team tactic supersedes prior radio");
        policy.BeginCommand("followme", speaker); policy.Confirm(speaker, 19, candidates);
        policy.Reset();
        Check(!policy.Owns("match-1", 4, "t", "b1") && !policy.HasPendingCommand,
            "new-round reset frees tasks with no old radio token or attempt");
        // Even no surviving recipients must invalidate a pending bomb callback.
        var capture = policy.Revision;
        policy.BeginCommand("go", speaker); policy.Confirm(speaker, 19, []);
        Check(policy.Revision != capture, "accepted radio without live teammates still cancels captured old intent");
        opponentHold.Release();
        Console.WriteLine($"{count} tactical-radio checks passed (engine-confirmed orders, team scope, immediate 20s hold release, token cleanup, stale callbacks, round reset).");
    }

    private sealed class RadioHoldApi : ITacticalHoldApi
    {
        private long _next;
        internal readonly Dictionary<long, int> Moves = [];
        private readonly HashSet<long> _suppression = [];
        public int IsLocked(int slot, int kind) => 0;
        public long StartMove(int slot) { Moves[++_next] = slot; return _next; }
        public int UpdateMove(int slot, long token) => Moves.GetValueOrDefault(token) == slot ? 0 : -1;
        public int CancelMove(int slot, long token) => Moves.Remove(token) ? 0 : -1;
        public long Suppress(int slot, ulong mask) { _suppression.Add(++_next); return _next; }
        public int CancelSuppression(int slot, long token) => _suppression.Remove(token) ? 0 : -1;
    }
}
