using BotBuyPatch;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Cvars;

int scenarios = 0, checks = 0;
var failures = new List<string>();
void Check(bool condition, string message)
{
    checks++;
    if (!condition) throw new InvalidOperationException(message);
}
void Scenario(string name, Action test)
{
    scenarios++; FakeWorld.Reset();
    try { test(); Console.WriteLine("PASS " + name); }
    catch (Exception ex) { failures.Add(name + ": " + ex.Message); Console.WriteLine("FAIL " + failures[^1]); }
}
CCSPlayerController Player(BotBuyPatch.BotBuyPatch patch, int money, int side = 3,
    bool bot = true, string role = "rifle", bool hidden = false)
{
    int slot = FakeWorld.Players.Count + 1;
    var player = new CCSPlayerController {
        Slot = slot, SteamID = (ulong)(1000 + slot), Handle = new(1000 + slot),
        TeamNum = side, IsBot = bot && !hidden, PlayerName = "player-" + slot
    };
    player.PlayerPawn.Value!.EntityHandle = new((uint)(100 + slot));
    player.PlayerPawn.Value.Bot = bot ? new() : null;
    player.InGameMoneyServices!.Account = money;
    if (bot) patch.Track(player, role);
    else FakeWorld.Players.Add(player);
    return player;
}
string[] Inventory(CCSPlayerController p) => p.PlayerPawn.Value!.WeaponServices!.MyWeapons
    .Select(h => h.Value).Where(w => w is { IsValid: true }).Select(w => w!.DesignerName).ToArray();

foreach (int side in new[] {2, 3})
foreach (string role in new[] {"rifle", "awp", "entry"})
Scenario($"native {side}/{role} owns normal 4350 purchase", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var p = Player(patch, 4350, side, role: role);
    patch.Schedule();
    foreach (float time in new[] {100.4f, 100.9f, 101.8f, 103.2f, 114.75f}) {
        patch.Apply(p); patch.Advance(time);
    }
    Check(p.GiveCalls.Count == 0 && patch.SwapCalls == 0, "No career fallback/upgrade fights native buying");
    Check(p.InGameMoneyServices!.Account == 4350, "No career reserve-driven spending");
    patch.EndPurchasePhase(); patch.Advance(116f);
    Check(patch.TimerTimes.Count() == 0, "Freeze-only gift review stops when buying ends");
});

foreach (string gun in new[] {"weapon_famas", "weapon_mp9", "weapon_awp", "weapon_ak47"})
Scenario("native or carried primary kept: " + gun, () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var p = Player(patch, 10000);
    FakeWorld.AddWeapon(p, gun); FakeWorld.AddWeapon(p, "weapon_knife");
    patch.Apply(p);
    Check(Inventory(p).Contains(gun) && p.GiveCalls.Count == 0 && patch.SwapCalls == 0,
        "Do not automatically upgrade, strip or rebuy native inventory");
});

foreach (int side in new[] {2, 3})
foreach (bool recipientBot in new[] {false, true})
Scenario($"upstream gift side={side} human={!recipientBot}", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    int price = side == 3 ? 2900 : 2700;
    var donor = Player(patch, price, side, hidden: true);
    var receiver = Player(patch, 500, side, bot: recipientBot);
    FakeWorld.AddWeapon(donor, side == 3 ? "weapon_m4a1" : "weapon_ak47");
    FakeWorld.AddWeapon(receiver, "weapon_deagle");
    patch.Schedule();
    Check(patch.TimerTimes.SequenceEqual(new[] {102f}), "Gift uses upstream two-second timing");
    patch.Advance(101.99f);
    Check(receiver.GiveCalls.Count == 0, "Native purchases finish first");
    patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 1, "Poor human and bot must both be eligible recipients");
    Check(side == 3 ? receiver.GiveCalls[0] is "weapon_m4a1" or "weapon_m4a1_silencer"
        : receiver.GiveCalls[0] == "weapon_ak47", "Gift uses current team's upstream rifle");
    Check(donor.InGameMoneyServices!.Account == 0 && receiver.InGameMoneyServices!.Account == 500,
        "Only AI donor pays the exact price; no extra armor/utility reserve");
    Check(Inventory(receiver).Contains("weapon_deagle"), "No recipient weapon removed");
    Check(receiver.Chat.Count == 1 && donor.Chat.Count == 1, "Both hear the upstream gift message");
    Check(Server.Console.Count(m => m.Contains("Gift donor")) == 1, "Gift outcome appears in the log");
    patch.GiveAgain();
    Check(receiver.GiveCalls.Count == 1 && FakeWorld.MoneyStateChanges == 1, "No duplicate gift or charge");
});

Scenario("rich human never funds automatic gifts", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var human = Player(patch, 16000, bot: false);
    var receiver = Player(patch, 500);
    FakeWorld.AddWeapon(human, "weapon_m4a1");
    patch.Schedule(); patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 0 && human.InGameMoneyServices!.Account == 16000, "Human money is untouched");
    Check(!patch.PurchaseDirect(human, "weapon_m4a1"), "Human cannot be an automatic purchaser either");
});

Scenario("native purchase before gift cancels just that recipient", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 5000);
    var receiver = Player(patch, 500, bot: false);
    FakeWorld.AddWeapon(donor, "weapon_m4a1");
    patch.Schedule();
    FakeWorld.AddWeapon(receiver, "weapon_mp9");
    patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 0 && receiver.Chat.Count == 0, "Already armed player gets no duplicate rifle");
    Check(donor.InGameMoneyServices!.Account == 5000, "No unused gift is billed");
});

foreach (string guard in new[] {"dead", "invalid", "missing-pawn", "missing-inventory", "missing-money",
    "other-team", "outside-zone", "replaced-pawn"})
Scenario("recipient validation: " + guard, () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 5000); var receiver = Player(patch, 500, bot: false);
    FakeWorld.AddWeapon(donor, "weapon_m4a1");
    patch.Schedule();
    switch (guard) {
        case "dead": receiver.PlayerPawn.Value!.Health = 0; break;
        case "invalid": receiver.IsValid = false; break;
        case "missing-pawn": receiver.PlayerPawn.Value = null; break;
        case "missing-inventory": receiver.PlayerPawn.Value!.WeaponServices = null; break;
        case "missing-money": receiver.InGameMoneyServices = null; break;
        case "other-team": receiver.TeamNum = 2; break;
        case "outside-zone": receiver.PlayerPawn.Value!.InBuyZone = false; break;
        case "replaced-pawn": receiver.PlayerPawn.Value!.EntityHandle = new(999); break;
    }
    patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 0 && donor.InGameMoneyServices!.Account == 5000, "No stale or invalid recipient grant");
});

foreach (string guard in new[] {"human-takeover", "controlled-earlier", "other-team", "dead", "poor", "unarmed", "outside-zone"})
Scenario("donor validation: " + guard, () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 5000); var receiver = Player(patch, 500, bot: false);
    if (guard != "unarmed") FakeWorld.AddWeapon(donor, "weapon_m4a1");
    patch.Schedule();
    switch (guard) {
        case "human-takeover": donor.ControllingBot = true; break;
        case "controlled-earlier": donor.HasBeenControlledByPlayerThisRound = true; break;
        case "other-team": donor.TeamNum = 2; break;
        case "dead": donor.PlayerPawn.Value!.Health = 0; break;
        case "poor": donor.InGameMoneyServices!.Account = 2899; break;
        case "outside-zone": donor.PlayerPawn.Value!.InBuyZone = false; break;
    }
    int money = donor.InGameMoneyServices!.Account;
    patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 0 && donor.InGameMoneyServices.Account == money, "Ineligible donor never spends");
});

foreach (string guard in new[] {"next-round", "map-change", "freeze-ended", "warmup", "loadout", "pistol", "closed-phase"})
Scenario("gift lifecycle: " + guard, () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 5000); var receiver = Player(patch, 500, bot: false);
    FakeWorld.AddWeapon(donor, "weapon_m4a1");
    patch.Schedule();
    switch (guard) {
        case "next-round": patch.NextRound(); break;
        case "map-change": Server.MapName = "de_inferno"; break;
        case "freeze-ended": FakeWorld.RulesProxy.GameRules!.FreezePeriod = false; break;
        case "warmup": FakeWorld.RulesProxy.GameRules!.WarmupPeriod = true; break;
        case "loadout": ConVar.Set("bot_loadout", "weapon_ak47"); break;
        case "pistol": FakeWorld.RulesProxy.GameRules!.TotalRoundsPlayed = 0; break;
        case "closed-phase": patch.EndPurchasePhase(); break;
    }
    patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 0 && donor.InGameMoneyServices!.Account == 5000, "No cross-round/live-round mutation");
});

Scenario("controlled teammate may receive a gift without automatic spending", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 5000); var receiver = Player(patch, 500);
    receiver.ControllingBot = true; receiver.HasBeenControlledByPlayerThisRound = true;
    FakeWorld.AddWeapon(donor, "weapon_m4a1");
    patch.Schedule(); patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 1 && receiver.InGameMoneyServices!.Account == 500, "Gift not confused with bot-only spending");
    Check(!patch.PurchaseDirect(receiver, "weapon_m4a1"), "Takeover inventory cannot be automatically purchased for");
});

foreach (var mode in new[] {SpawnMode.Zero, SpawnMode.Invalid, SpawnMode.Unattached})
Scenario("gift native return: " + mode, () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 10000); var receiver = Player(patch, 500, bot: false);
    FakeWorld.AddWeapon(donor, "weapon_m4a1"); receiver.GiveBehavior = (_, _) => mode;
    patch.Schedule(); patch.Advance(102f);
    bool success = mode == SpawnMode.Unattached;
    Check(donor.InGameMoneyServices!.Account == (success ? 7100 : 10000), "Only a valid native grant is charged");
    Check(receiver.Chat.Count == (success ? 1 : 0), "No success message for a failed grant");
    Check(FakeWorld.Entities.Values.All(e => !e.Killed), "Never delete an item awaiting native attachment");
    if (success) {
        patch.GiveAgain();
        Check(receiver.GiveCalls.Count == 1, "Delayed attachment still counts as one gift for this pawn");
    }
});

Scenario("gift limited to three recipients with shared pawn deduplication", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 16000); FakeWorld.AddWeapon(donor, "weapon_m4a1");
    var receivers = Enumerable.Range(0, 4).Select(_ => Player(patch, 500)).ToArray();
    patch.Schedule(); patch.Advance(102f);
    Check(receivers.Sum(p => p.GiveCalls.Count) == 3, "Upstream per-donor limit stays three");
    Check(donor.InGameMoneyServices!.Account == 7300, "All three debits use the actual CT rifle price");
});

Scenario("two controller views of same pawn receive only once", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 16000); FakeWorld.AddWeapon(donor, "weapon_m4a1");
    var one = Player(patch, 500); var two = Player(patch, 500, bot: false);
    two.PlayerPawn.Value = one.PlayerPawn.Value;
    one.GiveBehavior = two.GiveBehavior = (_, _) => SpawnMode.Unattached;
    patch.Schedule(); patch.Advance(102f);
    Check(one.GiveCalls.Count + two.GiveCalls.Count == 1, "Deduplicate by pawn, not BotHider/human display identity");
    Check(donor.InGameMoneyServices!.Account == 13100, "Shared pawn charged once");
});

Scenario("current buying power replaces the stale round-start poor cohort", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 10000); var receiver = Player(patch, 3000, bot: false);
    FakeWorld.AddWeapon(donor, "weapon_m4a1");
    patch.Schedule(); receiver.InGameMoneyServices!.Account = 500; patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 1, "Shopping after round start can create a real primary deficit");
    Check(receiver.InGameMoneyServices!.Account == 500 && donor.InGameMoneyServices!.Account == 7100,
        "Existing purchases stay intact and only the donor pays");
});

Scenario("logged CT deficit: 910 has 2250, torzsi has 8150 and a primary", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 8150, hidden: true); donor.PlayerName = "torzsi";
    var receiver = Player(patch, 4250, role: "awp", hidden: true); receiver.PlayerName = "910";
    FakeWorld.AddWeapon(donor, "weapon_ak47"); FakeWorld.AddWeapon(receiver, "weapon_usp_silencer");
    patch.Schedule(); patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 0, "Do not fund somebody who can still buy their own rifle");
    receiver.InGameMoneyServices!.Account = 2250;
    patch.Advance(103f);
    Check(receiver.GiveCalls.Count == 1 && donor.InGameMoneyServices!.Account == 5250, "Next freeze-time review funds the real deficit");
    Check(receiver.InGameMoneyServices.Account == 2250, "Receiver's AWP savings remain theirs");
    patch.Advance(104f); patch.GiveAgain();
    Check(receiver.GiveCalls.Count == 1, "Later checks never issue a second gun");
});

Scenario("donor finishes native purchasing after the initial check", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 9000); var receiver = Player(patch, 800);
    patch.Schedule(); patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 0, "Donor's own primary comes first");
    FakeWorld.AddWeapon(donor, "weapon_m4a1");
    donor.InGameMoneyServices!.Account = 6100; patch.Advance(103f);
    Check(receiver.GiveCalls.Count == 1 && donor.InGameMoneyServices.Account == 3200, "Late armed donor can still help");
});

Scenario("recipient buys their own gun between reviews", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 9000); var receiver = Player(patch, 800);
    patch.Schedule(); patch.Advance(102f);
    FakeWorld.AddWeapon(donor, "weapon_m4a1"); FakeWorld.AddWeapon(receiver, "weapon_mp9");
    patch.Advance(103f);
    Check(receiver.GiveCalls.Count == 0 && donor.InGameMoneyServices!.Account == 9000, "Latest inventory cancels a stale need");
});

Scenario("CT rifle affordability covers the old 2800 gap", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 8000); var receiver = Player(patch, 2850);
    FakeWorld.AddWeapon(donor, "weapon_m4a1"); patch.Schedule(); patch.Advance(102f);
    Check(receiver.GiveCalls.Count == 1, "2850 cannot buy a 2900 CT rifle");
});

Scenario("repeated review preserves cumulative donor limits", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 16000); FakeWorld.AddWeapon(donor, "weapon_m4a1");
    var receivers = Enumerable.Range(0,4).Select(_ => Player(patch, 500)).ToArray();
    patch.Schedule();
    for (int second = 102; second <= 116; second++) patch.Advance(second);
    Check(receivers.Sum(p => p.GiveCalls.Count) == 3 && donor.InGameMoneyServices!.Account == 7300,
        "Three per donor is per ROUND, not three every second");
    int blocked = Server.Console.Count(m => m.Contains("Gift waiting"));
    Check(blocked == 1, "Unchanged inability to gift does not spam logs");
});

Scenario("review stops before a late funded donor can mutate live play", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 5000); var receiver = Player(patch, 500);
    patch.Schedule(); patch.Advance(102f);
    FakeWorld.AddWeapon(donor, "weapon_m4a1");
    FakeWorld.RulesProxy.GameRules!.FreezePeriod = false;
    patch.Advance(103f);
    Check(receiver.GiveCalls.Count == 0 && !patch.TimerTimes.Any(), "No automatic grants after freeze time");
});

Scenario("invalid native gift remains unpaid and diagnostic is stable", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var donor = Player(patch, 9000); var receiver = Player(patch, 500);
    FakeWorld.AddWeapon(donor, "weapon_m4a1"); receiver.GiveBehavior = (_,_) => SpawnMode.Zero;
    patch.Schedule(); patch.Advance(102f); patch.Advance(103f);
    Check(donor.InGameMoneyServices!.Account == 9000 && receiver.Chat.Count == 0, "Failed native grants never cost money or claim success");
    Check(Server.Console.Count(m => m.Contains("Gift waiting")) == 1, "Native grant failure is logged once until reason changes");
});

Scenario("explicit double-AWP duties work without a global fallback loop", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var first = Player(patch, 5700); var second = Player(patch, 5700);
    patch.AssignDuty(first, "awp"); patch.AssignDuty(second, "awp");
    patch.Apply(first); patch.Apply(second); patch.Apply(first);
    Check(first.GiveCalls.SequenceEqual(new[] {"weapon_awp"}) && second.GiveCalls.SequenceEqual(new[] {"weapon_awp"}),
        "Only explicit affordable sniper duties override native roles, once each");
    Check(first.InGameMoneyServices!.Account == 950 && second.InGameMoneyServices!.Account == 950, "Real money is required");
});

Scenario("auto duty and unaffordable sniper leave decisions to native profiles", () => {
    var patch = new BotBuyPatch.BotBuyPatch();
    var p = Player(patch, 4350); patch.AssignDuty(p, "auto"); patch.Apply(p);
    patch.AssignDuty(p, "awp"); patch.Apply(p);
    Check(p.GiveCalls.Count == 0, "No custom budget rifle is forced by automatic or unaffordable sniper assignments");
});

foreach (bool sharedClass in new[] {false, true})
Scenario("upstream Buy keeps native M4-S grant sharedClass=" + sharedClass, () => {
    var patch = new BotBuyPatch.BotBuyPatch(); var p = Player(patch, 4350);
    p.SharedVariantClass = sharedClass;
    Check(patch.PurchaseDirect(p, "weapon_m4a1_silencer"), "Native return accepted");
    var item = p.PlayerPawn.Value!.WeaponServices!.MyWeapons.Single().Value!;
    Check(patch.CanonicalWeapon(item) == "weapon_m4a1_silencer", "Actual item definition resolves shared entity class");
    Check(p.InGameMoneyServices!.Account == 1450 && !FakeWorld.Entities.Values.Any(e => e.Killed), "One debit; no erroneous deletion");
});

foreach (var mode in new[] {SpawnMode.Zero, SpawnMode.Invalid, SpawnMode.Unattached})
Scenario("upstream Buy native return: " + mode, () => {
    var patch = new BotBuyPatch.BotBuyPatch(); var p = Player(patch, 4350);
    p.GiveBehavior = (_, _) => mode;
    bool result = patch.PurchaseDirect(p, "weapon_m4a1");
    Check(result == (mode == SpawnMode.Unattached), "Valid returned item accepted even if inventory updates later");
    Check(p.InGameMoneyServices!.Account == (result ? 1450 : 4350), "Failed grant never costs money");
    Check(FakeWorld.Entities.Values.All(e => !e.Killed), "Do not kill native returned items");
});

foreach (string gun in new[] {"weapon_famas", "weapon_m4a1", "weapon_p90", "weapon_mp9"})
foreach (bool hidden in new[] {false, true})
Scenario($"M4 preference repairs exact new {gun}, BotHider={hidden}", () => {
    var patch = new BotBuyPatch.BotBuyPatch(); var p = Player(patch, 4350, hidden: hidden);
    p.SharedVariantClass = true;
    FakeWorld.AddWeapon(p, gun);
    patch.Purchased(p, gun); Server.RunNextFrame();
    Check(p.GiveCalls.SequenceEqual(new[] {"weapon_m4a1_silencer"}), "Grant the actual silenced variant once");
    Check(p.InGameMoneyServices!.Account == 4350 + CareerTactics.TacticalBuyPolicy.PrimaryPrice(gun) - 2900,
        "Charge only the exact replacement difference");
    Check(p.PlayerPawn.Value!.WeaponServices!.MyWeapons.Count(h => h.Value is { IsValid: true }) == 1,
        "Do not leave two usable primaries");
    patch.Purchased(p, gun); Server.RunNextFrame(); patch.Apply(p); patch.Advance(100.21f);
    Check(p.GiveCalls.Count == 1, "Duplicate events or callbacks never charge twice");
    Check(Server.Console.Any(s => s.Contains("verification") && s.Contains("confirmed")),
        "Verify item definition 60 even when the entity class is weapon_m4a1");
});

foreach (string guard in new[] {"no-purchase-event", "carried", "pickup", "two-primaries", "poor", "T", "human",
    "takeover", "was-controlled", "dead", "invalid", "replaced-pawn", "next-round", "warmup", "live-round", "pistol", "loadout", "inactive",
    "outside-zone", "explicit-awp", "unknown-role", "missing-money"})
Scenario("M4 preference guard: " + guard, () => {
    var patch = new BotBuyPatch.BotBuyPatch(); var p = Player(patch, 4350, bot: guard != "human", role: guard == "unknown-role" ? "other" : "rifle");
    var gun = FakeWorld.AddWeapon(p, "weapon_famas");
    if (guard == "carried") patch.MarkRoundStart(p, gun);
    if (guard != "no-purchase-event") patch.Purchased(p, "weapon_famas");
    switch (guard) {
        case "pickup": gun.AcceptInput("Kill"); FakeWorld.AddWeapon(p, "weapon_mp9"); break;
        case "two-primaries": FakeWorld.AddWeapon(p, "weapon_ak47"); break;
        case "poor": p.InGameMoneyServices!.Account = 949; break;
        case "T": p.TeamNum = 2; break;
        case "takeover": p.ControllingBot = true; break;
        case "was-controlled": p.HasBeenControlledByPlayerThisRound = true; break;
        case "dead": p.PlayerPawn.Value!.Health = 0; break;
        case "invalid": p.IsValid = false; break;
        case "replaced-pawn": p.PlayerPawn.Value!.EntityHandle = new(999); break;
        case "next-round": patch.NextRound(); break;
        case "warmup": FakeWorld.RulesProxy.GameRules!.WarmupPeriod = true; break;
        case "live-round": FakeWorld.RulesProxy.GameRules!.FreezePeriod = false; break;
        case "pistol": FakeWorld.RulesProxy.GameRules!.TotalRoundsPlayed = 0; break;
        case "loadout": ConVar.Set("bot_loadout", "ak47"); break;
        case "inactive": patch.SetActive(false); break;
        case "outside-zone": p.PlayerPawn.Value!.InBuyZone = false; break;
        case "explicit-awp": patch.AssignDuty(p, "awp"); p.InGameMoneyServices!.Account = 950; break;
        case "missing-money": p.InGameMoneyServices = null; break;
    }
    int? money = p.InGameMoneyServices?.Account;
    Server.RunNextFrame();
    Check(p.GiveCalls.Count == 0 && p.RemovalCalls.Count == 0, "No unproven or ineligible replacement");
    Check(p.InGameMoneyServices?.Account == money, "Ineligible player balance is unchanged");
});

foreach (string gun in new[] {"weapon_awp", "weapon_ak47", "weapon_ssg08", "weapon_m4a1_silencer"})
Scenario("M4 preference preserves real purchase: " + gun, () => {
    var patch = new BotBuyPatch.BotBuyPatch(); var p = Player(patch, 10000);
    FakeWorld.AddWeapon(p, gun); patch.Purchased(p, gun); Server.RunNextFrame();
    Check(p.GiveCalls.Count == 0 && p.RemovalCalls.Count == 0, "No needless or destructive replacement");
});

foreach (string failure in new[] {"remove", "zero", "invalid"})
Scenario("M4 replacement failure rolls back: " + failure, () => {
    var patch = new BotBuyPatch.BotBuyPatch(); var p = Player(patch, 4350);
    FakeWorld.AddWeapon(p, "weapon_famas");
    p.RemoveSucceeds = failure != "remove";
    p.GiveBehavior = (_, name) => name == "weapon_m4a1_silencer" ? (failure == "invalid" ? SpawnMode.Invalid : SpawnMode.Zero) : SpawnMode.Attached;
    patch.Purchased(p, "weapon_famas"); Server.RunNextFrame(); patch.Apply(p);
    Check(Inventory(p).SequenceEqual(new[] {"weapon_famas"}), "Keep or restore the paid FAMAS if native M4 grant fails");
    Check(p.InGameMoneyServices!.Account == 4350, "Failed replacement does not cost money");
    Check(p.GiveCalls.Count(s => s == "weapon_m4a1_silencer") <= 1, "No failed-purchase loop");
});

Scenario("M4 correction survives delayed native attachment/removal without duplicate grants", () => {
    var patch = new BotBuyPatch.BotBuyPatch(); var p = Player(patch, 4350);
    p.DeferredRemoval = true; p.SharedVariantClass = true;
    p.GiveBehavior = (_, _) => SpawnMode.Unattached;
    FakeWorld.AddWeapon(p, "weapon_famas");
    patch.Purchased(p, "weapon_famas"); Server.RunNextFrame(); patch.Apply(p);
    patch.Purchased(p, "weapon_famas"); Server.RunNextFrame(); patch.Advance(100.21f);
    Check(p.GiveCalls.Count == 1 && p.RemovalCalls.Count == 1, "One grant/removal despite delayed inventory updates");
    Check(p.InGameMoneyServices!.Account == 3400, "One 950-dollar difference only");
    Check(Server.Console.Any(s => s.Contains("not_attached")), "Do not report an unobserved attachment as confirmed");
});

Scenario("M4 correction permits a new real purchase next round", () => {
    var patch = new BotBuyPatch.BotBuyPatch(); var p = Player(patch, 4350);
    for (int round = 0; round < 2; round++) {
        p.PlayerPawn.Value!.WeaponServices!.MyWeapons.Clear();
        p.InGameMoneyServices!.Account = 4350; patch.NewRoundForTest();
        FakeWorld.AddWeapon(p, "weapon_famas"); patch.Purchased(p, "weapon_famas"); Server.RunNextFrame();
    }
    Check(p.GiveCalls.Count == 2 && p.InGameMoneyServices!.Account == 3400, "Per-round dedup resets, not a permanent lockout");
});

Console.WriteLine($"BotBuy runtime: {scenarios} scenarios, {checks} checks, {failures.Count} failures.");
foreach (string failure in failures) Console.Error.WriteLine(failure);
return failures.Count == 0 ? 0 : 1;
