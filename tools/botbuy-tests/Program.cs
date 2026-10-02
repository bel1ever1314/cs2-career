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
Console.WriteLine($"PASS BotBuy career policy: {checks} assertions (pure rules; live buying not simulated).");
