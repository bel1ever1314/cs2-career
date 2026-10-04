using BotBuyPatch;
using CareerTactics;

int checks = 0;
void Check(bool condition, string name)
{
    checks++;
    if (!condition) throw new InvalidOperationException(name);
}
string[] roles = ["awp", "entry", "lurk", "igl", "rifle", "support", "", "unknown"];
string[] forbidden = ["weapon_aug", "weapon_scar20", "weapon_g3sg1"];
foreach (var role in roles)
{
    foreach (var weapon in forbidden)
    {
        Check(!CareerWeaponPolicy.CanBuy(true, weapon, role), "Active request forbids automatic " + weapon);
        Check(CareerWeaponPolicy.CanBuy(false, weapon, role), "Ordinary mod buying remains allowed");
    }
    Check(CareerWeaponPolicy.CanBuy(true, "weapon_awp", role) == (role == "awp"), "Only assigned AWP may auto buy AWP");
    foreach (var weapon in new[] { "weapon_ak47", "weapon_m4a1", "weapon_m4a1_silencer", "item_assaultsuit", "item_defuser" })
        Check(CareerWeaponPolicy.CanBuy(true, weapon, role), "Ordinary primary/equipment must remain available");
    for (int i = 0; i < 1000; i++)
    {
        var roll = i / 1000f;
        foreach (bool ct in new[] { false, true })
        {
            var gun = CareerWeaponPolicy.OvertimeWeapon(true, role, ct, roll);
            Check(!CareerWeaponPolicy.IsForbidden(gun), "OT never chooses AUG or automatic snipers");
            Check((gun == "weapon_awp") == (role == "awp"), "OT position, not nickname or chance, selects the sniper");
            if (role != "awp")
                Check(ct ? gun is "weapon_m4a1" or "weapon_m4a1_silencer" : gun == "weapon_ak47", "Non-AWP/unknown jobs use ordinary rifles");
        }
    }
}
Check(CareerWeaponPolicy.OvertimeWeapon(false, "rifle", true, .99f) == "weapon_scar20", "Non-career CT keeps upstream choice");
Check(CareerWeaponPolicy.OvertimeWeapon(false, "rifle", false, .99f) == "weapon_g3sg1", "Non-career T keeps upstream choice");
Check(CareerWeaponPolicy.OvertimeWeapon(false, "rifle", true, .8f) == "weapon_awp", "Non-career OT retains random AWP");
Check(CareerWeaponPolicy.CanModify(true, true, false, false, false, true, true), "Native bot may be modified");
Check(CareerWeaponPolicy.CanModify(true, false, true, false, false, true, true), "Known request bot tolerates BotHider IsBot false");
Check(!CareerWeaponPolicy.CanModify(true, false, false, false, false, true, true), "Human is never modified");
foreach (bool nativeBot in new[] { false, true })
foreach (bool requestBot in new[] { false, true })
{
    Check(!CareerWeaponPolicy.CanModify(true, nativeBot, requestBot, true, false, true, true), "Human taking over cannot be modified");
    Check(!CareerWeaponPolicy.CanModify(true, nativeBot, requestBot, false, true, true, true), "Controlled bot is never changed by delayed purchases");
    Check(!CareerWeaponPolicy.CanModify(true, nativeBot, requestBot, false, false, false, true), "A pawn belonging to another controller cannot be modified");
    Check(!CareerWeaponPolicy.CanModify(false, nativeBot, requestBot, false, false, true, true), "Invalid controller rejected");
    Check(!CareerWeaponPolicy.CanModify(true, nativeBot, requestBot, false, false, true, false), "Dead/disconnected pawn rejected");
}
foreach (var weapon in forbidden)
{
    Check(CareerWeaponPolicy.ShouldReplacePurchase(true, true, true, weapon, 123, 123, false, 1, true), "Confirmed new refundable purchase is normalized");
    Check(!CareerWeaponPolicy.ShouldReplacePurchase(false, true, true, weapon, 123, 123, false, 1, true), "No normalization outside career requests");
    Check(!CareerWeaponPolicy.ShouldReplacePurchase(true, false, true, weapon, 123, 123, false, 1, true), "A human/takeover cannot be normalized");
    Check(!CareerWeaponPolicy.ShouldReplacePurchase(true, true, false, weapon, 123, 123, false, 1, true), "No post-freeze inventory changes");
    Check(!CareerWeaponPolicy.ShouldReplacePurchase(true, true, true, weapon, 123, 123, true, 1, true), "A carried or old picked-up entity is preserved");
    Check(!CareerWeaponPolicy.ShouldReplacePurchase(true, true, true, weapon, 124, 123, false, 1, true), "A different picked-up gun is preserved");
    Check(!CareerWeaponPolicy.ShouldReplacePurchase(true, true, true, weapon, 123, 123, false, 2, true), "Duplicate names never justify stripping inventory");
    Check(!CareerWeaponPolicy.ShouldReplacePurchase(true, true, true, weapon, 123, 123, false, 1, false), "Refund-restricted guns are preserved");
    Check(!CareerWeaponPolicy.ShouldReplacePurchase(true, true, true, weapon, 0, 0, false, 1, true), "Invalid entity rejected");
}
Check(!CareerWeaponPolicy.ShouldReplacePurchase(true, true, true, "weapon_awp", 123, 123, false, 1, true), "Legitimate primary never normalized");
Check(TacticalBuyPolicy.CanReplace("awp","weapon_ak47",2050,1,1,false,1,true), "real money + new refundable AK permits AWP");
Check(!TacticalBuyPolicy.CanReplace("awp","weapon_ak47",2049,1,1,false,1,true), "one dollar short preserves rifle");
foreach (var duty in new[] {"rifle","entry","auto","lurk","igl"})
    Check(!TacticalBuyPolicy.CanReplace(duty,"weapon_ak47",16000,1,1,false,1,true), "only explicit sniper duty upgrades");
Check(!TacticalBuyPolicy.CanReplace("awp","weapon_awp",16000,1,1,false,1,true),"never rebuy AWP");
Check(!TacticalBuyPolicy.CanReplace("awp","weapon_ak47",16000,1,1,true,1,true),"carried gun not refunded");
Check(!TacticalBuyPolicy.CanReplace("awp","weapon_ak47",16000,2,1,false,1,true),"picked gun not refunded");
Check(!TacticalBuyPolicy.CanReplace("awp","weapon_ak47",16000,1,1,false,2,true),"ambiguous gun not refunded");
Check(!TacticalBuyPolicy.CanReplace("awp","weapon_ak47",16000,1,1,false,1,false),"used/refund-restricted gun kept");
Check(!TacticalBuyPolicy.CanReplace("awp","weapon_ak47",16000,0,0,false,1,true),"no fake purchase record");
Check(TacticalBuyPolicy.PrimaryPrice("weapon_aug")==3300 && TacticalBuyPolicy.PrimaryPrice("weapon_c4")==0,"purchase whitelist excludes bomb/utility");
Check(CareerWeaponPolicy.HasPrimary(["weapon_knife", "weapon_m4a1"]), "Holding knife does not make a carried rifle disappear");
Check(CareerWeaponPolicy.HasPrimary(["weapon_glock", "weapon_mac10"]), "Inventory scan includes the MAC-10");
Check(CareerWeaponPolicy.HasPrimary(["weapon_flashbang", "weapon_sg556"]), "Inventory scan includes the SG 553");
Check(!CareerWeaponPolicy.HasPrimary(["weapon_knife", "weapon_deagle", "weapon_c4"]), "Pistol, knife and bomb do not count as primary");
Check(CareerWeaponPolicy.ArmorReserve(true, 0, false) == 650, "CT upgrade reserves kevlar");
Check(CareerWeaponPolicy.ArmorReserve(false, 0, false) == 1000, "T upgrade reserves helmet and kevlar");
Check(CareerWeaponPolicy.ArmorReserve(false, 100, false) == 350, "Existing full kevlar needs only helmet budget");
Check(CareerWeaponPolicy.ArmorReserve(true, 70, false) == 0, "Usable CT armor is not purchased again");
Check(CareerWeaponPolicy.ArmorReserve(false, 70, true) == 0, "Existing usable helmet armor is not charged again");
string[] EmptyPrimary(bool ct, string role, int money, int reserve, float roll = .25f,
    bool active = true, bool eligible = true, bool buying = true, bool pistol = false, bool hasPrimary = false) =>
    CareerWeaponPolicy.EmptyPrimaryCandidates(active, eligible, buying, pistol, hasPrimary, ct, role, money, reserve, roll);
foreach (bool ct in new[] { false, true })
{
    int reserve = CareerWeaponPolicy.ArmorReserve(ct, 0, false) + 300;
    string rifle = ct ? "weapon_m4a1" : "weapon_ak47";
    string economyRifle = ct ? "weapon_famas" : "weapon_galilar";
    foreach (string role in roles)
        Check(EmptyPrimary(ct, role, 4350, reserve).FirstOrDefault() == rifle,
            "4350 buys the side's ordinary rifle, including AWP and unknown duties");
    Check(EmptyPrimary(ct, "awp", 4350, reserve).LastOrDefault() == "weapon_ssg08",
        "Scout remains a fallback after the sniper's ordinary rifles");
    foreach (int budget in new[] { 0, 950, 1300 })
    {
        int awpBoundary = 4750 + budget;
        Check(EmptyPrimary(ct, "awp", awpBoundary, budget).FirstOrDefault() == "weapon_awp",
            "AWP duty buys AWP at the exact weapon plus reserve boundary");
        Check(EmptyPrimary(ct, "awp", awpBoundary - 1, budget).FirstOrDefault() == rifle,
            "One dollar short of reserved AWP falls back to an ordinary rifle");
        Check(!EmptyPrimary(ct, "rifle", awpBoundary, budget).Contains("weapon_awp"),
            "A rich non-sniper still cannot auto buy AWP");
        int rifleBoundary = TacticalBuyPolicy.PrimaryPrice(rifle) + budget;
        Check(EmptyPrimary(ct, "rifle", Math.Max(2800, rifleBoundary), budget).FirstOrDefault() == rifle,
            "A non-eco round buys a rifle when its weapon plus reserve fits");
        if (rifleBoundary > 2800)
            Check(EmptyPrimary(ct, "rifle", rifleBoundary - 1, budget).FirstOrDefault() == economyRifle,
                "One dollar short of reserved rifle falls back to FAMAS or Galil");
    }
    Check(EmptyPrimary(ct, "rifle", 16000, reserve, active: false).Length == 0,
        "Missing-primary fallback only runs for active career requests");
    Check(EmptyPrimary(ct, "rifle", 16000, reserve, eligible: false).Length == 0,
        "Human, takeover, dead or otherwise ineligible player never gets a fallback");
    Check(EmptyPrimary(ct, "rifle", 16000, reserve, buying: false).Length == 0,
        "Warmup, closed purchase phase or outside buy zone never gets a fallback");
    Check(EmptyPrimary(ct, "awp", 16000, reserve, pistol: true).Length == 0,
        "First pistol round never gets a missing-primary fallback even with high money");
    Check(EmptyPrimary(ct, "awp", 16000, reserve, hasPrimary: true).Length == 0,
        "Existing primary never triggers missing-primary purchasing");
    Check(EmptyPrimary(ct, "awp", 2799, 0).Length == 0,
        "Below 2800 retains native eco decisions even when a cheaper primary fits");
    Check(EmptyPrimary(ct, "awp", -1, 0).Length == 0,
        "An unavailable or negative account cannot buy a fallback");
    Check(EmptyPrimary(ct, "awp", 16000, -1).Length == 0,
        "Negative reserve is rejected rather than increasing spending money");
    Check(EmptyPrimary(ct, "awp", 16000, int.MinValue).Length == 0,
        "Extreme invalid reserve cannot overflow into a purchase budget");
    Check(EmptyPrimary(ct, "awp", 16000, int.MaxValue).Length == 0,
        "A reserve exceeding the account leaves no affordable weapon");
}
Check(EmptyPrimary(true, "rifle", 4350, 950, .75f).SequenceEqual(
    new[] { "weapon_m4a1_silencer", "weapon_m4a1", "weapon_famas" }),
    "Failed preferred M4 can retry the alternate M4 then FAMAS, without duplicates");
Check(EmptyPrimary(false, "awp", 6050, 1300).SequenceEqual(
    new[] { "weapon_awp", "weapon_ak47", "weapon_galilar", "weapon_ssg08" }),
    "Failed AWP can retry ordinary T rifles before Scout within the same budget");
Check(EmptyPrimary(true, "rifle", 2800, 950).Length == 0,
    "2800 CT preserves full basic armor and smoke budget even if no rifle fits");
Check(EmptyPrimary(true, "awp", 2800, 950).SequenceEqual(new[] { "weapon_ssg08" }),
    "Budget-limited sniper may buy Scout when FAMAS does not fit");
Check(EmptyPrimary(false, "rifle", 3100, 1300).SequenceEqual(new[] { "weapon_galilar" }),
    "Galil at its exact boundary preserves basic T armor and smoke money");
Check(EmptyPrimary(false, "awp", 3000, 1300).SequenceEqual(new[] { "weapon_ssg08" }),
    "Scout at its exact boundary preserves basic T armor and smoke money");
foreach (bool ct in new[] { false, true })
foreach (string role in roles)
foreach (int reserve in new[] { 0, 300, 650, 950, 1000, 1300 })
foreach (int money in Enumerable.Range(0, 16001))
{
    var candidates = EmptyPrimary(ct, role, money, reserve);
    Check(candidates.Length == candidates.Distinct(StringComparer.Ordinal).Count(),
        "Every fallback list is deduplicated for sequential failure retries");
    foreach (string candidate in candidates)
    {
        Check(!CareerWeaponPolicy.IsForbidden(candidate) && TacticalBuyPolicy.PrimaryAllowed(ct, candidate),
            "Fallback never offers a banned gun or a primary from the wrong side");
        Check(TacticalBuyPolicy.PrimaryPrice(candidate) > 0
            && TacticalBuyPolicy.PrimaryPrice(candidate) + (long)reserve <= money,
            "Every fallback candidate retains the complete armor and utility reserve");
        Check(candidate != "weapon_awp" || role == "awp", "Fallback AWP is restricted to the sniper duty");
    }
    if (money < 2800)
        Check(candidates.Length == 0, "Every account below 2800 keeps native eco buying");
    else if (role == "awp" && money >= 4750 + reserve)
        Check(candidates.FirstOrDefault() == "weapon_awp", "Affordable reserved AWP has first priority");
    else if (money >= (ct ? 2900 : 2700) + reserve)
        Check(candidates.FirstOrDefault() == (ct ? "weapon_m4a1" : "weapon_ak47"),
            "Affordable reserved main rifle always precedes cheaper alternatives");
    else if (money >= (ct ? 1950 : 1800) + reserve)
        Check(candidates.FirstOrDefault() == (ct ? "weapon_famas" : "weapon_galilar"),
            "Affordable economy rifle is used when the main rifle cannot fit");
    else if (role == "awp" && money >= 1700 + reserve)
        Check(candidates.FirstOrDefault() == "weapon_ssg08", "Scout is the final budget-limited sniper fallback");
    else
        Check(candidates.Length == 0, "No money is charged when all reserved candidates are unaffordable");
}
Check(TacticalBuyPolicy.PrimaryAllowed(true, "weapon_m4a1") && !TacticalBuyPolicy.PrimaryAllowed(false, "weapon_m4a1"), "M4 restricted to CT purchases");
Check(TacticalBuyPolicy.PrimaryAllowed(false, "weapon_ak47") && !TacticalBuyPolicy.PrimaryAllowed(true, "weapon_ak47"), "AK restricted to T purchases");
Check(!TacticalBuyPolicy.PrimaryAllowed(true, "weapon_knife"), "Unknown or non-primary cannot use the primary price table");
foreach (bool ct in new[] { false, true })
{
    var gun = ct ? "weapon_famas" : "weapon_galilar";
    int refund = TacticalBuyPolicy.PrimaryPrice(gun);
    int target = TacticalBuyPolicy.PrimaryPrice(CareerWeaponPolicy.Rifle(ct, .25f));
    foreach (int reserve in new[] { 0, 300, 650, 1000, 1300 })
    foreach (int money in Enumerable.Range(0, 16001))
        Check(CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, true, ct, "rifle", gun,
            money, reserve, 16000, 1, 1, false, 1, true) == (Math.Min(16000, money + refund) >= target + reserve),
            "Upgrade budget follows real refundable money, armor/utility reserve and account cap");
    foreach (var role in new[] { "rifle", "entry", "lurk", "igl", "support", "auto", "unknown" })
        Check(CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, true, ct, role, gun,
            5000, 1000, 16000, 1, 1, false, 1, true), "Non-sniper rich new economy gun upgrades");
    Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, true, ct, "awp", gun,
        16000, 0, 16000, 1, 1, false, 1, true), "Sniper plan is handled before ordinary rifle upgrades");
    Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(false, true, true, ct, "rifle", gun,
        16000, 0, 16000, 1, 1, false, 1, true), "Outside career no economic replacement");
    Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, false, true, ct, "rifle", gun,
        16000, 0, 16000, 1, 1, false, 1, true), "Human or takeover cannot be upgraded");
    Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, false, ct, "rifle", gun,
        16000, 0, 16000, 1, 1, false, 1, true), "Not buying means no upgrade");
    Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, true, ct, "rifle", gun,
        16000, 0, 16000, 1, 1, true, 1, true), "Round-start saved gun remains untouched");
    Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, true, ct, "rifle", gun,
        16000, 0, 16000, 2, 1, false, 1, true), "Picked-up entity is not a refundable purchase");
    Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, true, ct, "rifle", gun,
        16000, 0, 16000, 1, 1, false, 2, true), "Multiple primaries are not stripped");
    Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, true, ct, "rifle", gun,
        16000, 0, 16000, 1, 1, false, 1, false), "Refund refusal preserves cheap primary");
    Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, true, ct, "rifle", gun,
        16000, 0, 16000, 0, 0, false, 1, true), "Missing entity cannot produce an upgrade");
    Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, true, ct, "rifle", gun,
        5000, 1000, target, 1, 1, false, 1, true), "Refund cap must leave armor money too");
    foreach (var kept in new[] { "weapon_ssg08", "weapon_awp", "weapon_ak47", "weapon_m4a1", "weapon_m4a1_silencer", "weapon_c4" })
        Check(!CareerWeaponPolicy.CanUpgradeEconomyPrimary(true, true, true, ct, "rifle", kept,
            16000, 0, 16000, 1, 1, false, 1, true), "Good primary, Scout and bomb are not cheap rifle upgrades");
}
Check(!TacticalBuyPolicy.CanReplace("awp", "weapon_famas", 2800, 1, 1, false, 1, true, 300), "AWP upgrade also preserves utility budget");
Check(TacticalBuyPolicy.CanReplace("awp", "weapon_famas", 3100, 1, 1, false, 1, true, 300), "AWP upgrade has enough refundable money and utility reserve");
Check(!TacticalBuyPolicy.CanReplace("awp", "weapon_famas", 16000, 1, 1, false, 1, true, 300, 4750), "AWP reserve respects max-money cap");
Check(CareerWeaponPolicy.GiftArmorPrice(true, 1700, 950) == 650, "CT armor gift uses spare money, not total balance");
Check(CareerWeaponPolicy.GiftArmorPrice(true, 950, 950) == 0, "CT gift does not consume the donor's armor and utility budget");
Check(CareerWeaponPolicy.GiftArmorPrice(false, 1999, 1000) == 0, "T armor gift requires spare full-armor money");
Check(CareerWeaponPolicy.GiftArmorPrice(false, 2000, 1000) == 1000, "T armor gift preserves donor's reserve");
foreach (var gun in new[] { "weapon_aug", "weapon_scar20", "weapon_awp" })
{
    Check(!CareerWeaponPolicy.CanBuy(true, gun, "rifle"), "Rollback does not change default purchase restrictions");
    Check(CareerWeaponPolicy.CanBuy(true, gun, "rifle", true), "Failed replacement may restore its verified original weapon");
}
Check(CareerWeaponPolicy.ConfirmedNewPrimary(1, 1, false, 1), "Recorded new exact entity permits primary refund");
Check(!CareerWeaponPolicy.ConfirmedNewPrimary(1, 1, true, 1), "Carried primary cannot be refunded even in pistol rounds");
Check(!CareerWeaponPolicy.ConfirmedNewPrimary(2, 1, false, 1), "Different pickup cannot be refunded");
Check(!CareerWeaponPolicy.ConfirmedNewPrimary(1, 1, false, 2), "Duplicate primary cannot be refunded by name");
Check(!CareerWeaponPolicy.ConfirmedNewPrimary(0, 0, false, 1), "No fake entity record can justify refund");
Check(!CareerWeaponPolicy.ConfirmedNewPrimary(1, 1, false, 1, true), "CSS delayed removal cannot refund the old entity twice");
// Match the actual CSS 0.1s Kill ordering: old gun remains present until later,
// but its proof is gone; buying or rolling back creates a different entity.
var purchaseProof = new Dictionary<string, uint> { ["weapon_aug"] = 123 };
var pendingRemovals = new HashSet<uint>();
Check(CareerWeaponPolicy.ConfirmedNewPrimary(123, purchaseProof["weapon_aug"], false, 1), "Initial AUG purchase eligible before sniper replacement");
pendingRemovals.Add(123); purchaseProof.Remove("weapon_aug");
purchaseProof["weapon_awp"] = 456;
Check(!CareerWeaponPolicy.ConfirmedNewPrimary(123, purchaseProof.GetValueOrDefault("weapon_aug"), false, 1,
    pendingRemovals.Contains(123)), "Pending AUG cannot be normalized after AUG-to-AWP refund");
Check(CareerWeaponPolicy.ConfirmedNewPrimary(456, purchaseProof["weapon_awp"], false, 1,
    pendingRemovals.Contains(456)), "Only the new AWP has a valid purchase proof");
Console.WriteLine($"PASS BotBuy career policy: {checks} assertions (pure rules; live buying not simulated).");
