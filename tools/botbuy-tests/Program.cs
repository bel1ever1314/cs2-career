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
