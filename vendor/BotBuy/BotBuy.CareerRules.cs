using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Cvars;

namespace BotBuyPatch;

public sealed partial class BotBuyPatch
{
    private bool CanCareerPurchase(CCSPlayerController player)
    {
        if (!_careerActive || !CanModify(player) || !string.IsNullOrEmpty(ConVar.Find("bot_loadout")?.StringValue))
            return false;
        var rules = Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules").FirstOrDefault()?.GameRules;
        return rules is { WarmupPeriod: false, FreezePeriod: true } && player.PlayerPawn.Value!.InBuyZone;
    }

    // Used only by an explicit tactical weapon reassignment, never by normal
    // native buying or the upstream teammate gift budget.
    private int PurchaseReserve(CCSPlayerController player)
    {
        var pawn = player.PlayerPawn.Value!;
        bool helmet = pawn.ItemServices is { Handle: not 0 }
            && new CCSPlayer_ItemServices(pawn.ItemServices.Handle).HasHelmet;
        bool utility = pawn.WeaponServices?.MyWeapons.Any(h => h.Value is { IsValid: true } w
            && w.DesignerName is "weapon_flashbang" or "weapon_smokegrenade" or "weapon_hegrenade"
                or "weapon_molotov" or "weapon_incgrenade") ?? false;
        return CareerWeaponPolicy.ArmorReserve(player.TeamNum == 3, pawn.ArmorValue, helmet) + (utility ? 0 : 300);
    }

    private void ApplyCareerPurchases(CCSPlayerController player)
    {
        if (!CanCareerPurchase(player)) return;
        NormalizePurchasedWeapons(player);
        // Native RiflePro/SniperPro handles normal buys/eco. Only a player-issued
        // tactical duty can override that profile for this round (e.g. double AWP).
        if (_tacticalDuties.TryGetValue(player.SteamID, out var duty) && duty != "auto")
            ApplyTacticalPurchase(player);
        RepairM4Preference(player);
    }
}
