using CareerMatch;

var bots = Enumerable.Range(1, 9).Select(i => new IdentityBot($"p{i}", $"C2C_p{i}", $"Player {i}", (ulong)(100+i))).ToList();
var live = bots.Select((b,i) => new IdentitySlot(i+1, $"connection-{i+1}", b.Profile, 0, 0, true)).ToList();
live.Add(new IdentitySlot(0, "human-1", "Steam nickname", 999, 999, false));
var bindings = new IdentityBindings();
void Check(bool ok, string message) { if (!ok) throw new Exception(message); }
bindings.Update(live, bots, "human");
Check(bindings.Slots.Count == 10, "initial ten identities");
// BotHider changes flag, name and Steam presentation; no row may become human.
live = live.Select(p => p.Slot == 0 ? p : p with { IsBot=false, Name="renamed", SteamId=888 }).ToList();
bindings.Update(live, bots, "human");
Check(bindings.Slots.Count(p => p.Value == "human") == 1, "one human after flag flip");
Check(bindings.Slots[1] == "p1", "existing bot binding preserved");
// Slot reuse by an unknown client must not inherit the former player.
live[0] = live[0] with { Connection="replacement", Name="unknown", SteamId=0 };
bindings.Update(live, bots, "human");
Check(!bindings.Slots.ContainsKey(1), "unknown replacement is not assigned by roster order");
live[0] = live[0] with { SteamId=101 };
bindings.Update(live, bots, "human");
Check(bindings.Slots[1] == "p1", "synthetic Steam ID reconnect");
live.RemoveAll(p => p.Slot == 0);
bindings.Update(live,bots,"human");
live.Add(new IdentitySlot(11,"human-2","new nickname",999,999,false));
bindings.Update(live,bots,"human");
Check(bindings.Slots[11] == "human", "authenticated human reconnect preserves ID");
bindings.Clear();
bindings.Update([new(0,"a","A",999,999,false),new(1,"b","B",998,998,false)],bots,"human");
Check(bindings.Slots.Count == 0,"ambiguous humans do not merge");
bindings.Update([new(1,"a","renamed",101,0,false)],bots,"human");
Check(bindings.Slots[1] == "p1","disguised bot identified before mutable flag");
Console.WriteLine("8 identity checks passed (flags, rename, reconnect, slot reuse, ambiguity, synthetic identity).");
var health = new SessionHealth();
Check(health.CanMaintainPresentation(true), "valid request maintains names");
health.StatisticsError = "duplicate death after takeover";
Check(health.CanMaintainPresentation(true), "stats rejection must not disable name/avatar repair");
Check(health.ResultError == health.StatisticsError, "invalid stats remain blocked from ingestion");
health.ContractError = "invalid VPK hash";
Check(!health.CanMaintainPresentation(true), "untrusted request cannot write persona");
Check(health.ResultError == health.ContractError, "contract error takes precedence");
health.ContractError = "";
Check(!health.CanMaintainPresentation(false), "inactive request cannot rename players");
Console.WriteLine("6 session-health checks passed (presentation independent of statistics).");
using (var doc = System.Text.Json.JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "bot_manifest_contract.json"))))
{
    Check(ManifestDigest.Compute(doc.RootElement) == "4a1ba36891a336167784dff4aa0b326af807c14c82f9f76cd0e73ee807959bf9",
        "Python/C# contract digest includes tuning model and both source hashes");
}
Console.WriteLine("1 cross-language manifest digest check passed.");
var actors = new ActorOwnership();
actors.NewMatch();
Check(actors.Actor("human") == "human", "own body is human");
actors.Support("enemy", "human", "human");
actors.Thrown("human", "hegrenade", "human");
actors.Takeover("human", "bot1", 123);
Check(actors.Actor("human", 123) == "bot1", "controlled bot owns rifle kills/damage/death");
Check(actors.Actor("human") == "bot1", "death without pawn keeps bot owner");
Check(actors.Assister("enemy", "human", false) == "human", "pre-takeover assist stays human");
Check(actors.ProjectileActor("human", "hegrenade") == "human", "delayed grenade stays thrower");
actors.Support("enemy2", "human", "bot1");
Check(actors.Assister("enemy2", "human", false) == "bot1", "bot-body assist stays bot");
actors.Takeover("human", "bot2", 456);
Check(actors.Actor("human", 456) == "bot2", "second takeover switches only event actor");
Check(actors.Assister("enemy2", "human", false) == "bot1", "earlier bot assist survives another takeover");
actors.Support("enemy2", "human", "bot2");
Check(actors.Assister("enemy2", "human", false) is null, "ambiguous cross-body assist rejected");
actors.Thrown("human", "hegrenade", "bot2");
Check(actors.ProjectileActor("human", "hegrenade") is null, "ambiguous delayed projectiles rejected");
actors.Support("enemy3", "human", "bot2", true);
Check(actors.Assister("enemy3", "human", true) == "bot2", "flash contribution bound at event time");
actors.NewRound();
Check(actors.Actor("human") == "human" && actors.HadTakeover, "new round clears control, disables fallback for match");
Check(actors.Actor("human", 567, "bot3") == "bot3", "original pawn owner covers missed takeover signal");
actors.Takeover("human", "bot4", 789);
actors.Detach("human");
Check(actors.Actor("human") == "human", "reconnect does not inherit old control");
actors.NewMatch();
Check(!actors.HadTakeover, "new match clears takeover audit flag");
Console.WriteLine("15 actor ownership checks passed (multiple takeovers, assists, grenades, flash, reconnect, reset).");
TakeoverRegression.Run();
ReadinessRegression.Run();
