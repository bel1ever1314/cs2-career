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
    scenarios++;
    FakeWorld.Reset();
    try { test(); Console.WriteLine("PASS " + name); }
    catch (Exception exception)
    {
        failures.Add(name + ": " + exception.Message);
        Console.WriteLine("FAIL " + failures[^1]);
    }
}

(BotBuyPatch.BotBuyPatch Patch, CCSPlayerController Player) Subject(int side = 3, string role = "rifle", int money = 4350)
{
    var player = new CCSPlayerController { TeamNum = side };
    player.InGameMoneyServices!.Account = money;
    var patch = new BotBuyPatch.BotBuyPatch();
    patch.Track(player, role);
    Server.CurrentTime = 100.9f;
    return (patch, player);
}

string[] Inventory(CCSPlayerController player) => player.PlayerPawn.Value!.WeaponServices!.MyWeapons
    .Select(handle => handle.Value).Where(weapon => weapon is { IsValid: true })
    .Select(weapon => weapon!.DesignerName).ToArray();

foreach (int side in new[] { 2, 3 })
foreach (string role in new[] { "rifle", "awp", "unknown" })
{
    Scenario($"4350 side={side} role={role} buys a reserved rifle exactly once", () =>
    {
        var (patch, player) = Subject(side, role);
        FakeWorld.AddWeapon(player, side == 3 ? "weapon_usp_silencer" : "weapon_glock");
        FakeWorld.AddWeapon(player, "weapon_knife");
        patch.Apply(player);
        string expected = side == 3 ? "weapon_m4a1" : "weapon_ak47";
        Check(Inventory(player).Contains(expected), "The real execution path must equip a rifle");
        Check(player.GiveCalls.SequenceEqual(new[] { expected }), "Only one spawn should be attempted");
        Check(player.InGameMoneyServices!.Account == (side == 3 ? 1450 : 1650), "Charge the real weapon price");
        Check(patch.PurchasedCount == 1 && FakeWorld.MoneyStateChanges == 1, "Record/replicate exactly one confirmed buy");
        patch.Apply(player);
        Check(player.GiveCalls.Count == 1 && FakeWorld.MoneyStateChanges == 1, "A retry must preserve the equipped primary");
    });
}

Scenario("CT alternate rifle selection follows current bot identity", () =>
{
    var (patch, player) = Subject();
    player.SteamID = 3;
    patch.Track(player, "rifle");
    patch.Apply(player);
    Check(Inventory(player).Contains("weapon_m4a1_silencer"), "Odd identity should use silenced M4");
});

Scenario("sniper buys AWP only at weapon plus reserve boundary", () =>
{
    var (patch, player) = Subject(role: "awp", money: 5700);
    patch.Apply(player);
    Check(player.GiveCalls.SequenceEqual(new[] { "weapon_awp" }), "AWP must precede rifles when affordable");
    Check(player.InGameMoneyServices!.Account == 950, "Leave CT kevlar/smoke reserve intact");
});

Scenario("tactical sniper assignment also receives affordable rifle fallback", () =>
{
    var (patch, player) = Subject();
    patch.AssignDuty(player, "awp");
    patch.TacticalOnly(player);
    Check(player.GiveCalls.Count == 0, "Tactical no-primary branch must defer to shared purchase path");
    patch.Apply(player);
    Check(Inventory(player).Contains("weapon_m4a1"), "Assigned sniper must not wait empty for unaffordable AWP");
});

Scenario("native primary purchase within grace is preserved", () =>
{
    var (patch, player) = Subject();
    Server.CurrentTime = 100.79f;
    patch.Apply(player);
    Check(player.GiveCalls.Count == 0, "Do not race native opening purchase before 0.8 seconds");
    Check(Server.Console.Count == 0, "Native grace should not produce a failure diagnostic");
    FakeWorld.AddWeapon(player, "weapon_mp9");
    Server.CurrentTime = 100.9f;
    patch.Apply(player);
    Check(player.GiveCalls.Count == 0 && patch.SwapCalls == 0, "Unproven native inventory must be preserved");
});

Scenario("exact grace boundary allows a missing-primary purchase", () =>
{
    var (patch, player) = Subject();
    Server.CurrentTime = 100.8f;
    patch.Apply(player);
    Check(player.GiveCalls.Count == 1, "Eligibility begins at the exact 0.8-second boundary");
});

Scenario("held knife does not hide carried primary", () =>
{
    var (patch, player) = Subject();
    FakeWorld.AddWeapon(player, "weapon_knife");
    var old = FakeWorld.AddWeapon(player, "weapon_ak47");
    patch.MarkRoundStart(player, old);
    patch.Apply(player);
    Check(player.GiveCalls.Count == 0 && Inventory(player).Contains("weapon_ak47"), "Search the full inventory and preserve carried gun");
});

Scenario("failed spawn falls back without a failed-attempt debit", () =>
{
    var (patch, player) = Subject();
    player.GiveBehavior = (_, name) => name == "weapon_m4a1" ? SpawnMode.Zero : SpawnMode.Attached;
    patch.Apply(player);
    Check(player.GiveCalls.SequenceEqual(new[] { "weapon_m4a1", "weapon_m4a1_silencer" }), "Try the next valid weapon after spawn failure");
    Check(Inventory(player).SequenceEqual(new[] { "weapon_m4a1_silencer" }), "Fallback primary must be attached");
    Check(player.InGameMoneyServices!.Account == 1450 && FakeWorld.MoneyStateChanges == 1, "Failed attempt must not deduct money");
});

Scenario("valid but unattached spawn is killed then fallback succeeds", () =>
{
    var (patch, player) = Subject();
    player.GiveBehavior = (_, name) => name == "weapon_m4a1" ? SpawnMode.Unattached : SpawnMode.Attached;
    patch.Apply(player);
    Check(FakeWorld.Entities.Values.Count(entity => entity.Killed) == 1, "Clean up an unattached valid primary");
    Check(Inventory(player).SequenceEqual(new[] { "weapon_m4a1_silencer" }), "Continue to a successfully attached fallback");
    Check(player.InGameMoneyServices!.Account == 1450 && patch.PurchasedCount == 1, "Only the attached primary has buy proof and charge");
});

Scenario("invalid and zero item handles never charge", () =>
{
    var (patch, player) = Subject();
    player.GiveBehavior = (_, _) => player.GiveCalls.Count % 2 == 1 ? SpawnMode.Invalid : SpawnMode.Zero;
    patch.Apply(player);
    Check(player.InGameMoneyServices!.Account == 4350, "Every failed spawn keeps the original balance");
    Check(patch.PurchasedCount == 0 && FakeWorld.MoneyStateChanges == 0, "No phantom purchase records/replication");
});

Scenario("all failed candidates can retry without repeat charges or log spam", () =>
{
    var (patch, player) = Subject(role: "awp");
    player.GiveBehavior = (_, _) => SpawnMode.Unattached;
    patch.Apply(player);
    int attempts = player.GiveCalls.Count;
    Check(attempts == 4, "Try two CT rifles, FAMAS and Scout for this sniper budget");
    patch.Apply(player);
    Check(player.GiveCalls.Count == attempts * 2, "A later callback may retry failures");
    Check(player.InGameMoneyServices!.Account == 4350 && patch.PurchasedCount == 0, "Retries must not silently consume money");
    Check(FakeWorld.MoneyStateChanges == 0 && Server.Console.Count == 1, "No charge notifications and only one identical diagnostic");
    Check(FakeWorld.Entities.Values.All(entity => entity.Killed), "No unattached entity leaks after attempts");
});

Scenario("native inventory acquired during a failed attempt stops fallback", () =>
{
    var (patch, player) = Subject();
    player.GiveBehavior = (who, _) =>
    {
        FakeWorld.AddWeapon(who, "weapon_mp9");
        return SpawnMode.Zero;
    };
    patch.Apply(player);
    Check(player.GiveCalls.Count == 1, "Recheck primary inventory before attempting next candidate");
    Check(player.InGameMoneyServices!.Account == 4350 && Inventory(player).Contains("weapon_mp9"), "Keep newly acquired primary without plugin charge");
});

Scenario("pending-refund primary must not block replacement fallback", () =>
{
    var (patch, player) = Subject();
    var pending = FakeWorld.AddWeapon(player, "weapon_aug");
    patch.MarkPendingRefund(pending);
    patch.Apply(player);
    Check(player.GiveCalls.SequenceEqual(new[] { "weapon_m4a1" }), "Ignore the pending removed entity in every primary check");
    Check(player.InGameMoneyServices!.Account == 1450, "Charge only replacement while removal is pending");
});

Scenario("human taking control during failure stops remaining attempts", () =>
{
    var (patch, player) = Subject();
    player.GiveBehavior = (who, _) => { who.ControllingBot = true; return SpawnMode.Zero; };
    patch.Apply(player);
    Check(player.GiveCalls.Count == 1 && player.InGameMoneyServices!.Account == 4350, "Per-attempt ownership recheck must stop buying");
});

Scenario("released human control remains protected for this round", () =>
{
    var (patch, player) = Subject();
    player.ControllingBot = true;
    player.HasBeenControlledByPlayerThisRound = true;
    patch.Apply(player);
    player.ControllingBot = false;
    patch.Apply(player);
    Check(player.GiveCalls.Count == 0, "Release of a takeover must not permit a delayed inventory mutation");
});

Scenario("replaced pawn and human controller are never purchased for", () =>
{
    var (patch, player) = Subject();
    player.PlayerPawn.Value!.EntityHandle = new(101);
    patch.Apply(player);
    Check(player.GiveCalls.Count == 0, "Round pawn identity guards stale delayed callback");
    player.PlayerPawn.Value.EntityHandle = new(100);
    player.OriginalControllerOfCurrentPawn.Value = new CCSPlayerController { Handle = new(999) };
    patch.Apply(player);
    Check(player.GiveCalls.Count == 0, "A pawn belonging to another controller must be preserved");
});

Scenario("request BotHider identity works while unknown bots remain ineligible", () =>
{
    var (patch, player) = Subject();
    player.IsBot = false;
    patch.Apply(player);
    Check(player.GiveCalls.Count == 1, "Verified request bot may have hidden IsBot flag");
    var unknown = new CCSPlayerController { Slot = 2, SteamID = 999 };
    patch.Apply(unknown);
    Check(unknown.GiveCalls.Count == 0, "Career mutation requires verified request membership");
});

foreach (int round in new[] { 0, 12 })
{
    Scenario($"pistol opening round {round} keeps native purchase decision", () =>
    {
        var (patch, player) = Subject(money: 16000);
        FakeWorld.RulesProxy.GameRules!.TotalRoundsPlayed = round;
        patch.Apply(player);
        Check(player.GiveCalls.Count == 0 && player.InGameMoneyServices!.Account == 16000, "No plugin primary on a regulation pistol opening");
        patch.Apply(player);
        Check(Server.Console.Count == 1, "A deferred state should log only once");
    });
}

foreach (int round in new[] { 24, 27 })
{
    Scenario($"OT opening round {round} recovers a failed initial primary", () =>
    {
        var (patch, player) = Subject(role: "awp", money: 10000);
        FakeWorld.RulesProxy.GameRules!.TotalRoundsPlayed = round;
        player.GiveBehavior = (_, _) => SpawnMode.Zero;
        Check(!patch.PurchaseDirect(player, "weapon_awp"), "Simulate a failed real OT first purchase");
        player.GiveBehavior = (_, _) => SpawnMode.Attached;
        patch.Apply(player);
        Check(Inventory(player).Contains("weapon_awp"), "OT half opening is a full-buy round, so the shared fallback must recover");
        Check(player.InGameMoneyServices!.Account == 5250, "The failed OT attempt must not charge; recovered AWP charges once");
    });
}

Scenario("eco below 2800 remains untouched", () =>
{
    var (patch, player) = Subject(money: 2799);
    patch.Apply(player);
    Check(player.GiveCalls.Count == 0 && player.InGameMoneyServices!.Account == 2799, "Do not force a primary in native eco range");
});

Scenario("2800 with existing armor can buy economy rifle", () =>
{
    var (patch, player) = Subject(money: 2800);
    player.PlayerPawn.Value!.ArmorValue = 100;
    patch.Apply(player);
    Check(player.GiveCalls.SequenceEqual(new[] { "weapon_famas" }), "Budget fallback must actually equip FAMAS");
    Check(player.InGameMoneyServices!.Account == 850, "Charge economy rifle price without discarding utility reserve");
});

Scenario("existing armor and utility remove only their actual reserves", () =>
{
    var (patch, player) = Subject(side: 2, role: "awp", money: 4750);
    player.PlayerPawn.Value!.ArmorValue = 100;
    FakeWorld.Helmets[1] = true;
    FakeWorld.AddWeapon(player, "weapon_smokegrenade");
    patch.Apply(player);
    Check(player.GiveCalls.SequenceEqual(new[] { "weapon_awp" }), "Already equipped helmet and smoke permit exact AWP affordability");
    Check(player.InGameMoneyServices!.Account == 0, "Do not reserve already held equipment twice");
});

Scenario("missing services are unavailable state and never fabricate inventory", () =>
{
    var (patch, player) = Subject();
    player.PlayerPawn.Value!.WeaponServices = null;
    patch.Apply(player);
    Check(player.GiveCalls.Count == 0, "Missing weapon services must not trigger GiveNamedItem");
    player.PlayerPawn.Value.WeaponServices = new();
    player.InGameMoneyServices = null;
    patch.Apply(player);
    Check(player.GiveCalls.Count == 0, "Missing money services must not trigger buying");
});

foreach (string guard in new[] { "loadout", "warmup", "freeze-ended", "outside-zone", "dead", "inactive" })
{
    Scenario($"eligibility guard: {guard}", () =>
    {
        var (patch, player) = Subject();
        switch (guard)
        {
            case "loadout": ConVar.Set("bot_loadout", "weapon_ak47"); break;
            case "warmup": FakeWorld.RulesProxy.GameRules!.WarmupPeriod = true; break;
            case "freeze-ended": FakeWorld.RulesProxy.GameRules!.FreezePeriod = false; break;
            case "outside-zone": player.PlayerPawn.Value!.InBuyZone = false; break;
            case "dead": player.PlayerPawn.Value!.Health = 0; break;
            case "inactive": patch.SetActive(false); break;
        }
        patch.Apply(player);
        Check(player.GiveCalls.Count == 0 && player.InGameMoneyServices!.Account == 4350, "Ineligible context must not mutate inventory/money");
    });
}

Scenario("freeze ending during a failed attempt stops fallback", () =>
{
    var (patch, player) = Subject();
    player.GiveBehavior = (_, _) => { FakeWorld.RulesProxy.GameRules!.FreezePeriod = false; return SpawnMode.Zero; };
    patch.Apply(player);
    Check(player.GiveCalls.Count == 1 && player.InGameMoneyServices!.Account == 4350, "Recheck live freeze phase before next candidate");
});

Scenario("live budget changed during failure retains reserve and eco threshold", () =>
{
    var (patch, player) = Subject();
    player.GiveBehavior = (who, _) =>
    {
        if (who.GiveCalls.Count != 1) return SpawnMode.Attached;
        who.InGameMoneyServices!.Account = 2000;
        return SpawnMode.Zero;
    };
    patch.Apply(player);
    Check(player.GiveCalls.Count == 1, "Recheck current economy eligibility before spawning another candidate");
    Check(player.InGameMoneyServices!.Account == 2000 && patch.PurchasedCount == 0, "A stale candidate list must not spend live armor/utility reserve");
});

Scenario("reduced live budget falls back to economy rifle within reserve", () =>
{
    var (patch, player) = Subject();
    player.GiveBehavior = (who, _) =>
    {
        if (who.GiveCalls.Count != 1) return SpawnMode.Attached;
        who.InGameMoneyServices!.Account = 3000;
        return SpawnMode.Zero;
    };
    patch.Apply(player);
    Check(player.GiveCalls.SequenceEqual(new[] { "weapon_m4a1", "weapon_famas" }), "Reject stale M4 affordability but permit affordable FAMAS");
    Check(player.InGameMoneyServices!.Account == 1050 && patch.PurchasedCount == 1, "Current balance must retain the current 950 reserve");
});

Scenario("changed tactical role rejects stale sniper-only fallback", () =>
{
    var (patch, player) = Subject(role: "awp", money: 10000);
    player.GiveBehavior = (_, _) =>
    {
        patch.AssignDuty(player, "rifle");
        return SpawnMode.Zero;
    };
    patch.Apply(player);
    Check(player.GiveCalls.SequenceEqual(new[] { "weapon_awp", "weapon_m4a1", "weapon_m4a1_silencer", "weapon_famas" }),
        "A Scout from the old sniper candidate list must not survive changed live rifle duty");
    Check(player.InGameMoneyServices!.Account == 10000, "Failed changed-role purchases preserve cash");
});

Scenario("changed live side rejects wrong-side candidates then later retries correctly", () =>
{
    var (patch, player) = Subject();
    player.GiveBehavior = (who, _) => { who.TeamNum = 2; return SpawnMode.Zero; };
    patch.Apply(player);
    Check(player.GiveCalls.SequenceEqual(new[] { "weapon_m4a1" }), "No CT-only candidate may be spawned after a side change");
    Check(player.InGameMoneyServices!.Account == 4350, "Rejected stale-side attempts must not charge");
    player.GiveBehavior = (_, _) => SpawnMode.Attached;
    patch.Apply(player);
    Check(player.GiveCalls.SequenceEqual(new[] { "weapon_m4a1", "weapon_ak47" }), "A later callback must use the live T-side candidate list");
    Check(player.InGameMoneyServices.Account == 1650, "Only the successful live-side weapon is charged");
});

Scenario("changed live armor reserve rejects stale rifle affordability", () =>
{
    var (patch, player) = Subject(money: 3000);
    player.PlayerPawn.Value!.ArmorValue = 100;
    var smoke = FakeWorld.AddWeapon(player, "weapon_smokegrenade");
    player.GiveBehavior = (who, _) =>
    {
        if (who.GiveCalls.Count != 1) return SpawnMode.Attached;
        who.PlayerPawn.Value!.ArmorValue = 0;
        smoke.AcceptInput("Kill");
        return SpawnMode.Zero;
    };
    patch.Apply(player);
    Check(player.GiveCalls.SequenceEqual(new[] { "weapon_m4a1", "weapon_famas" }), "New armor/smoke reserve must be rechecked after failure");
    Check(player.InGameMoneyServices!.Account == 1050, "Retain the live armor/utility budget");
});

Scenario("production final check retries 0.25 seconds before freeze end", () =>
{
    var (patch, player) = Subject();
    Server.CurrentTime = 100f;
    player.GiveBehavior = (_, _) => Server.CurrentTime >= 114.75f ? SpawnMode.Attached : SpawnMode.Zero;
    patch.Schedule();
    Check(patch.TimerTimes.Order().SequenceEqual(new[] { 100.9f, 101.8f, 103.2f, 114.75f }), "Compile and execute the real round-start purchase schedule");
    patch.Advance(100.9f); patch.Advance(101.8f); patch.Advance(103.2f);
    int failedAttempts = player.GiveCalls.Count;
    Check(failedAttempts > 0 && Inventory(player).Length == 0, "Earlier purchase attempts can all fail");
    patch.Advance(114.74f);
    Check(player.GiveCalls.Count == failedAttempts, "Do not execute final timer early");
    patch.Advance(114.75f);
    Check(Inventory(player).Contains("weapon_m4a1") && player.InGameMoneyServices!.Account == 1450, "Final timer must provide one confirmed primary before freeze end");
    FakeWorld.RulesProxy.GameRules!.FreezePeriod = false;
    patch.EndPurchasePhase();
    patch.Apply(player);
    Check(FakeWorld.MoneyStateChanges == 1, "Freeze end must not charge another purchase");
});

foreach (string expiry in new[] { "round", "map", "phase" })
{
    Scenario($"production timer cancels stale {expiry}", () =>
    {
        var (patch, player) = Subject();
        Server.CurrentTime = 100f;
        patch.Schedule();
        switch (expiry)
        {
            case "round": patch.NextRound(); break;
            case "map": Server.MapName = "de_nuke"; break;
            case "phase": patch.EndPurchasePhase(); break;
        }
        patch.Advance(114.75f);
        Check(player.GiveCalls.Count == 0, "All round-owned purchase timers must expire with their owner");
    });
}

Console.WriteLine($"BotBuy runtime: {scenarios} scenarios, {checks} checks, {failures.Count} failures.");
if (failures.Count > 0) Environment.Exit(1);
