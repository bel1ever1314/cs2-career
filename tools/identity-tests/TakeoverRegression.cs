using CareerMatch;

internal static class TakeoverRegression
{
    public static void Run()
    {
        int checks = 0;
        void Check(bool ok, string reason) { checks++; if (!ok) throw new Exception(reason); }
        // Fourteen observed .2 control snapshots, stripped of names, career IDs,
        // nonce, paths and native handles. They prove control-link resolution;
        // they cannot recover unlogged/rejected combat events from that match.
        using (var fixture = System.Text.Json.JsonDocument.Parse(File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory, "takeover_control_snapshots.json"))))
            foreach (var item in fixture.RootElement.EnumerateArray())
            {
                var live = System.Text.Json.JsonSerializer.Deserialize<List<ControlSnapshot>>(item.GetProperty("live"))!;
                Check(TakeoverResolver.Resolve("human", live, "human", item.GetProperty("eventBotId").GetString())
                    == item.GetProperty("expected").GetString(), "observed control-link replay");
            }
        // Native adapter regression: CS2 / CSS discussion #1102 reports userid==botid.
        // The old tests started AFTER Takeover() and missed the failing adapter.
        var control = new List<ControlSnapshot> {
            new("human", 202, "bot1", true, false, false, "ct", true),
            new("bot1", 101, "human", false, true, true, "ct", false),
            new("bot2", 303, "bot2", false, false, true, "ct", false),
            new("enemy", 404, "enemy", false, false, true, "t", false),
        };
        var actors = new ActorOwnership();
        actors.NewMatch();
        actors.RememberPawn(101, "human");
        actors.RememberPawn(202, "bot1");
        actors.RememberPawn(303, "bot2");
        var resolved = TakeoverResolver.Resolve("human", control, actors.PawnOwner(202), "human");
        Check(resolved == "bot1", "duplicate event IDs resolve via original pawn, not event Botid");
        var inverseOnly = control.Select(p => p.Id == "human" ? p with { Pawn = 101, Original = "human" } : p).ToList();
        Check(TakeoverResolver.Resolve("human", inverseOnly, "human", "human") == "bot1",
            "inverse original-controller relationship covers engine swap timing");
        var noSwap = inverseOnly.Select(p => p with { Original = p.Id, WasControlled = false }).ToList();
        Check(TakeoverResolver.Resolve("human", noSwap, "human", "human") is null,
            "identical event IDs without body evidence cannot guess a teammate");
        actors.AwaitTakeover("human");
        Check(actors.Actor("human") is null && actors.HadTakeover,
            "unresolved takeover cannot charge human or enable engine aggregate fallback");
        Check(actors.Actor("human", 202, "bot1") is null, "pending binding cannot bypass confirmation");
        Check(actors.ProjectileActor("human", "hegrenade") is null, "unknown projectile remains rejected");
        actors.Takeover("human", resolved!, 202);
        Check(actors.Actor("human", 101, "human") == "bot1", "explicit bot owner survives restored human pawn");
        Check(actors.Actor("bot1") == "bot1", "bot event does not reverse-map to human after pawn swap");
        var ambiguous = control.Select(p => p.Id == "bot2" ? p with { Original = "human", WasControlled = true } : p).ToList();
        Check(TakeoverResolver.Resolve("human", ambiguous, "human", "human") == "bot1", "direct original-controller link wins over stale inverse links");
        Check(TakeoverResolver.Resolve("human", ambiguous.Select(p => p.Id == "human" ? p with { Original="human" } : p).ToList(), "human", "human") is null,
            "two inverse links without a direct owner remain ambiguous");
        Check(TakeoverResolver.Resolve("human", control, "enemy", "enemy") == "bot1", "opponent cannot become takeover candidate");
        Check(TakeoverResolver.Resolve("human", control.Select(p => p.Id == "bot1" ? p with { Dead = true } : p).ToList(), "bot1", "human") is null,
            "dead bot cannot be newly controlled");
        Check(TakeoverResolver.Resolve("human", control.Select(p => p.Id == "human" ? p with { Dead = false } : p).ToList(), "bot1", "human") is null,
            "missing original death cannot be silently accepted");

        // Replay original body -> takeover -> second takeover -> next round.
        // Check distribution, not just total kills / score conservation.
        actors.NewMatch();
        var kills = new Dictionary<string,int> { ["human"]=0, ["bot1"]=0, ["bot2"]=0 };
        var deaths = new Dictionary<string,int>(kills);
        var damage = new Dictionary<string,int>(kills);
        void Shoot(string controller, int hp) { var actor=actors.Actor(controller)!; kills[actor]++; damage[actor]+=hp; }
        void Die(string controller) { deaths[actors.Actor(controller)!]++; }
        Shoot("human", 80); Die("human");
        actors.AwaitTakeover("human");
        actors.Takeover("human", TakeoverResolver.Resolve("human", control, "bot1", "human")!, 202);
        Shoot("human", 100); Shoot("human", 60); Die("human");
        var second = control.Select(p => p.Id == "human" ? p with { Pawn=303, Original="bot2" }
            : p.Id == "bot1" ? p with { Dead=true }
            : p.Id == "bot2" ? p with { Pawn=101, Original="human", WasControlled=true } : p).ToList();
        actors.AwaitTakeover("human");
        actors.Takeover("human", TakeoverResolver.Resolve("human", second, "bot2", "human")!, 303);
        Shoot("human", 75); Die("human");
        Check(kills["human"] == 1 && kills["bot1"] == 2 && kills["bot2"] == 1, "four kills distributed 1/2/1 without duplication");
        Check(deaths.Values.All(n => n == 1), "each original body dies once, human never dies three times");
        Check(damage["human"] == 80 && damage["bot1"] == 160 && damage["bot2"] == 75, "damage follows controlled career player");
        actors.NewRound();
        Shoot("human", 100);
        Check(kills["human"] == 2 && kills["bot2"] == 1, "new round returns event ownership to human");
        actors.NewMatch();
        actors.Thrown("bot1", "fire", "bot1");
        actors.Thrown("bot1", "flashbang", "bot1");
        actors.Takeover("human", "bot1", 0);
        Check(actors.ProjectileActor("human", "fire") == "bot1", "pre-takeover bot molotov retains its thrower across controller change");
        Check(actors.ProjectileActor("human", "flashbang") == "bot1", "pre-takeover bot flash is not missing human throw evidence");
        actors.Thrown("human", "fire", "human");
        Check(actors.ProjectileActor("human", "fire") is null, "genuinely ambiguous simultaneous throwers still fail closed");

        var roster = Enumerable.Range(0,10).Select(i => new TeamMembership($"p{i}", i<5?"ct":"t", i<5?3:2)).ToList();
        Check(TeamScoreMapping.OpeningCtCurrentSide(roster) == 3, "opening FURIA CT mapped from roster IDs");
        Check(TeamScoreMapping.Normalize(7,5,3) == (7,5), "first half does not reverse score");
        var switched = roster.Select(p => p with { CurrentSide = 5-p.CurrentSide }).ToList();
        Check(TeamScoreMapping.OpeningCtCurrentSide(switched) == 2, "halftime follows players, not initial CT team name");
        Check(TeamScoreMapping.Normalize(13,9,2) == (9,13), "FUT 13:9 is exported FURIA 9 / FUT 13");
        Check(TeamScoreMapping.Normalize(19,17,3) == (19,17), "overtime can switch back without a hardcoded half threshold");
        Check(TeamScoreMapping.OpeningCtCurrentSide(switched.Take(9).ToList()) is null, "missing roster cannot invent score mapping");
        Check(TeamScoreMapping.OpeningCtCurrentSide(switched.Select(p => p.Id=="p0" ? p with { CurrentSide=3 } : p).ToList()) is null,
            "transient mixed sides do not flip cached mapping");
        // Repeated warmup round_start at 0:0 must still identify live round 1.
        Check(TeamScoreMapping.LiveRoundIndex(0,0) == 1 && TeamScoreMapping.LiveRoundIndex(9,12) == 22,
            "round index is score-derived, not callback-derived");
        Console.WriteLine($"{checks} native-control regression checks passed (duplicate IDs, pawn swap, rejection, three-body replay).");
    }
}
