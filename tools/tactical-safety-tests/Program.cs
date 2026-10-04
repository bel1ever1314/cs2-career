using CareerMatch;
using CounterStrikeSharp.API.Core;

int checks = 0;
void Check(bool condition, string name)
{
    checks++;
    if (!condition) throw new Exception("Tactical safety: " + name);
}
(CareerMatchPlugin Host, CCSPlayerController Player, CareerMatchPlugin.CustomActor Actor) Fresh()
{
    var host = new CareerMatchPlugin(); var player = new CCSPlayerController();
    var actor = new CareerMatchPlugin.CustomActor(); host._customTacticActors[7] = actor;
    host._customTacticActors[8] = new() { Id = "other", Pawn = 800 };
    host._openingGuards[7] = new(); host._tacticalReleases[7] = new();
    host._naturalTasks[7] = new(); host._naturalAssignments[7] = new();
    return (host, player, actor);
}
foreach (var damage in new[] { (3, 0), (0, 6), (9, 3) })
{
    var (host, player, actor) = Fresh(); var opening = host._openingGuards[7];
    host.Hurt(player, damage.Item1, damage.Item2);
    Check(!host._customTacticActors.ContainsKey(7) && host._customTacticActors.ContainsKey(8), "only injured actor exits");
    Check(new[] { actor.Jump, actor.Gait, actor.Look, actor.PathHold, actor.Hold, opening.Lease }.All(t => t.Calls == 1), "all movement/look/suppression tokens released");
    Check(actor.Continuation.Calls == 1 && actor.DirectMove.Calls == 1, "both route states reset");
    Check(host.NativeOwns(player) && !host._tacticalReleases.ContainsKey(7), "native owns remainder, stale deferred cancellation removed");
    Check(host.NativeCalls.SequenceEqual(new[] { "bot:danger_handoff" }), "owned native goal cancellation requested once");
    Check(host._customTacticPlan is not null && host.NaturalCalls.Count == 5 && !host._naturalTasks.ContainsKey(7), "team intent retained, old natural controllers cleared");
    host.Hurt(player); host.Danger(player, "avoiding_grenade");
    Check(actor.Hold.Calls == 1 && host.Traces.Count == 1, "continued burning never reinstates/re-releases a wait or floods logs");
    player.PlayerPawn.Value!.EntityHandle = new(900);
    Check(!host.NativeOwns(player), "respawn / reused body cannot inherit native handoff");
    player.PlayerPawn.Value.EntityHandle = new(700); player.Id = "other";
    Check(!host.NativeOwns(player), "reused slot identity cannot inherit handoff");
    player.Id = "bot"; host.NextRound();
    Check(!host.NativeOwns(player), "new round accepts fresh tactics");
}
foreach (var reason in new[] { "health_loss", "avoiding_grenade" })
{
    var (h, p, a) = Fresh();
    Check(h.Danger(p, reason) && a.Hold.Calls == 1, "tick fallback / pre-damage native avoidance: " + reason);
}
var guards = new (string, Action<CareerMatchPlugin, CCSPlayerController>)[]
{
    ("round ended", (h,p) => h._roundLive = false),
    ("result", (h,p) => h._resultWritten = true),
    ("setup", (h,p) => h._setupDone = false),
    ("warmup", (h,p) => h.Warmup = true),
    ("no request", (h,p) => h._request = null),
    ("inactive", (h,p) => h._request!.Active = false),
    ("observer", (h,p) => h._request!.Observer = true),
    ("contract", (h,p) => h._contractError = "bad"),
    ("invalid", (h,p) => p.IsValid = false),
    ("takeover", (h,p) => p.ControllingBot = true),
    ("taken earlier", (h,p) => p.HasBeenControlledByPlayerThisRound = true),
    ("no pawn", (h,p) => p.PlayerPawn.Value = null),
    ("invalid pawn", (h,p) => p.PlayerPawn.Value!.IsValid = false),
    ("dead", (h,p) => p.PlayerPawn.Value!.Health = 0),
    ("no native bot", (h,p) => p.PlayerPawn.Value!.Bot = null),
    ("missing identity", (h,p) => p.Id = null),
    ("human", (h,p) => h._request!.HumanPlayerId = "bot"),
    ("human ledger", (h,p) => h._ledger["bot"] = new(false)),
    ("unbound", (h,p) => h._ledger.Clear()),
    ("old round", (h,p) => h._tacticalEpoch++),
    ("old match", (h,p) => h._sessionNonce = "next"),
    ("other side", (h,p) => p.Side = "ct"),
    ("other pawn", (h,p) => p.PlayerPawn.Value!.EntityHandle = new(999)),
    ("other actor", (h,p) => h._customTacticActors[7].Id = "other"),
    ("no plan", (h,p) => h._customTacticPlan = null),
};
foreach (var (name, change) in guards)
{
    var (h, p, a) = Fresh(); change(h,p); h.Hurt(p);
    Check(h._customTacticActors.ContainsKey(7) && a.Hold.Calls == 0 && h.NativeCalls.Count == 0 && !h.NativeOwns(p), name);
}
{
    var (h,p,a) = Fresh(); h.Hurt(null); h.Hurt(p, 0, 0); h.Hurt(p, -1, -1);
    Check(a.Hold.Calls == 0, "null / no damage does not release ordinary wait");
    a.Jump.Throw = true; a.Look.Throw = true; a.PathHold.Throw = true;
    h.Hurt(p);
    Check(a.Gait.Calls == 1 && a.Hold.Calls == 1 && h.NativeCalls.Count == 1 && h.Logger.Failures == 3,
        "one cancellation failure cannot skip remaining escape controls");
    Check(!h._customTacticActors.ContainsKey(7) && h.NativeOwns(p), "failed callback never resurrects route");
}
foreach (var type in new[] { "postplant", "rush" })
{
    var (h,p,a) = Fresh(); h._customTacticActors.Remove(7);
    var post = new CareerMatchPlugin.PostActor();
    if (type == "postplant") h._postPlantActors[7] = post;
    else h._tacticalActors[7] = new("bot", 7, 700, [new(4)], 20);
    h.Hurt(p);
    Check(!h._postPlantActors.ContainsKey(7) && !h._tacticalActors.ContainsKey(7) && h.NativeOwns(p), type+" releases");
    Check(h.NativeCalls.Count == 1 && h._customTacticActors.ContainsKey(8), type+" keeps teammates");
    if (type == "postplant") Check(post.Hold.Calls == 1 && post.PathHold.Calls == 1 && post.Path.Calls == 1, "postplant hold and path cleared");
}
Console.WriteLine($"PASS tactical safety: {checks} checks; real handoff adapter, simulated native API.");
