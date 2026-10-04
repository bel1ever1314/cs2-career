using CareerMatch;

internal static class TacticalCommandRegression
{
    public static void Run()
    {
        int count = 0;
        void Check(bool ok, string label) { count++; if (!ok) throw new Exception(label); }
        var context = new TacticalCommandContext { MatchNonce = "nonce-1", Round = 7,
            SpeakerId = "human", Side = "t", AuthorizedMatch = true, AuthorizedHuman = true,
            SpeakerValid = true, Preparation = true };
        foreach (var channel in new[] { "say", "say_team", " SAY_TEAM " })
        foreach (var text in new[] { "rusha", "RUSHA", "rush a", " RuSh\t A ", "/rush a", "!rusha",
            "全员A", "全员 a", "5人rusha", "5人 rusha", "5人rush a", "5人 rush a", "\" RUSH A \"", "'rusha'", "“全员A”" })
        {
            var parsed = TacticalCommands.Parse(channel, text);
            Check(parsed is { Order: TacticalOrder.RushA, Site: "A", Canonical: "rusha" }, "rush-A alias: " + text);
        }
        foreach (var text in new[] { "rushb", "RUSH B", "/rush b", "!rushb", "全员B", "全员 b", "5人rushb", "5人 rush b", "\"rushb\"" })
            Check(TacticalCommands.Parse("say", text) is { Order: TacticalOrder.RushB, Site: "B", Canonical: "rushb" }, "rush-B alias: " + text);
        foreach (var text in new[] { "default", " DEFAULT ", "取消战术", "/default", "!取消战术", "\"default\"" })
            Check(TacticalCommands.Parse("say_team", text) is { Order: TacticalOrder.Cancel, Site: "" }, "cancel alias: " + text);
        foreach (var text in new[] { "play short_a", "PLAY short_a", "/play short_a", "tactic short_a", "战术 short_a" })
            Check(TacticalCommands.Parse("say_team", text) is { Order: TacticalOrder.Playbook, TacticId: "short_a", Canonical: "play short_a" }, "play/legacy alias: " + text);
        foreach (var text in new[] { "", "hello", "我觉得全员A不错", "can we rusha", "rusha please", "rush a now", "rusha!",
            "rush", "rush c", "rush ab", "rusha/b", "5人rusha/b", "! !rusha", "//rush a", "5人default",
            "\"rusha", "rusha\"", "\"rusha\"; quit", "rush\0 a", "rush\u200b a", "say rusha", "rush a;quit" })
            Check(TacticalCommands.Parse("say", text) is null, "ordinary/ambiguous/injection chat preserved: " + text);
        Check(TacticalCommands.Parse("say", new string(' ', 129) + "rusha") is null, "bounded parsing");
        Check(TacticalCommands.Parse("server", "rusha") is null && TacticalCommands.Parse(null, "rusha") is null, "only chat channels");
        Check(TacticalCommands.Parse("say", null) is null, "null chat safe");
        var command = TacticalCommands.Parse("say", "rusha")!;
        var allowed = TacticalCommands.Gate(command, context);
        Check(allowed.Accepted && allowed.Plan == new CommandPlan("nonce-1", 7, "t", "human", TacticalOrder.RushA, "A"), "verified immutable plan");
        Check(TacticalCommands.Gate(command, context with { Side = " CT " }).Plan?.Side == "ct", "current side normalized, not roster name");
        void Denied(TacticalCommandContext value, string code) {
            var denied = TacticalCommands.Gate(command, value);
            Check(denied.Recognized && !denied.Accepted && denied.Plan is null && denied.Code == code && denied.Message.Length > 0, code);
        }
        Denied(context with { AuthorizedMatch = false }, "unauthorized_match");
        Denied(context with { MatchNonce = "" }, "unauthorized_match");
        Denied(context with { MatchCompleted = true }, "match_completed");
        Denied(context with { Observer = true }, "observer");
        Denied(context with { SpeakerValid = false }, "invalid_speaker");
        Denied(context with { SpeakerId = "" }, "invalid_speaker");
        Denied(context with { SpeakerIsBot = true }, "bot_speaker");
        Denied(context with { AuthorizedHuman = false }, "unauthorized_human");
        Denied(context with { Side = "spectator" }, "invalid_side");
        Denied(context with { Side = "" }, "invalid_side");
        Denied(context with { Warmup = true }, "warmup");
        Denied(context with { Preparation = false }, "not_preparation");
        Denied(context with { Round = 0 }, "not_preparation");
        Check(!TacticalCommands.Gate(new(TacticalOrder.RushA, "B", "rusha"), context).Accepted, "mismatched plan target rejected");
        Check(!TacticalCommands.Gate(new((TacticalOrder)999, "A", "rusha"), context).Accepted, "unknown enum rejected");
        Check(!TacticalCommands.Gate(command, new()).Accepted, "context defaults fail closed");
        var queue = new TacticalCommandQueue();
        Check(queue.Submit("say", "rusha", context).Code == "queued" && queue.Pending?.Site == "A", "first command queues");
        Check(queue.Submit("say_team", "rushb", context).Accepted && queue.Pending?.Site == "B", "last command wins");
        var pending = queue.Pending;
        Check(!queue.Submit("say", "rusha please", context).Recognized && queue.Pending == pending, "ordinary chat does not mutate pending");
        Check(!queue.Submit("say", "rusha", context with { Preparation = false }).Accepted && queue.Pending == pending, "late freeze-end race rejects without mutation");
        Check(!queue.Submit("say", "default", context with { SpeakerIsBot = true }).Accepted && queue.Pending == pending, "unauthorized cancellation cannot erase plan");
        Check(queue.Take("old-nonce", 7, "t") is null && queue.Pending == pending, "old session cannot consume plan");
        Check(queue.Take("nonce-1", 6, "t") is null && queue.Pending == pending, "wrong preparation epoch cannot consume plan");
        Check(queue.Take("nonce-1", 7, "ct") is null && queue.Pending == pending, "opponent cannot consume plan");
        Check(queue.Take("nonce-1", 7, "T") == pending && queue.Pending is null, "exact scope consumes once");
        Check(queue.Take("nonce-1", 7, "t") is null, "duplicate freeze-end applies nothing");
        queue.Submit("say", "rusha", context);
        Check(queue.Submit("say", "取消战术", context).Code == "cancelled" && queue.Pending is null, "cancel clears only queued intent");
        queue.Submit("say", "rusha", context);
        queue.Reset(); Check(queue.Pending is null, "map/round/restart reset clears intent");
        queue.Submit("say", "rusha", context);
        queue.Submit("say", "rushb", context with { MatchNonce = "nonce-2", Round = 8, Side = "ct" });
        Check(queue.Take("nonce-1", 7, "t") is null && queue.Take("nonce-2", 8, "ct")?.Site == "B", "new scoped command replaces old session/side");
        TacticalBotCandidate[] actors = [
            new("b1", "t", true, true, true), new("b2", " T ", true, true, true),
            new("enemy", "ct", true, true, true), new("human", "t", false, true, true),
            new("other-human", "t", false, true, true), new("taken-over", "t", true, true, true, true),
            new("dead", "t", true, true, false), new("invalid", "t", true, false, true),
            new("spectator-bot", "spectator", true, true, true), new("", "t", true, true, true),
            new("human", "t", true, true, true), new("b1", "t", true, true, true)
        ];
        Check(TacticalCommands.EligibleBots(allowed.Plan!, actors).SequenceEqual(new[] { "b1", "b2" }), "only valid living same-side ledger Bots, never human/takeover/opponent");
        Check(TacticalCommands.EligibleBots(new("n", 1, "spectator", "human", TacticalOrder.RushA, "A"), actors).Count == 0, "observer plan cannot target anyone");
        Check(TacticalCommands.EligibleBots(new("n", 1, "t", "human", TacticalOrder.Cancel, ""), actors).Count == 0, "cancel has no Bot action");
        Check(TacticalCommands.Usage == "准备阶段输入 play <id>。", "help presents the supported play command without map-specific rush tips");
        Console.WriteLine($"{count} tactical-command checks passed (whole-chat parser, authorization, preparation scope, last-only queue, Bot-only targets).");
    }
}
