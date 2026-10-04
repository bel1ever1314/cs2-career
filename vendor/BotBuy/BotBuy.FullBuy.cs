using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Cvars;
using CareerTactics;

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

    private int PurchaseReserve(CCSPlayerController player)
    {
        var pawn = player.PlayerPawn.Value!;
        bool helmet = pawn.ItemServices is { Handle: not 0 }
            && new CCSPlayer_ItemServices(pawn.ItemServices.Handle).HasHelmet;
        bool utility = pawn.WeaponServices?.MyWeapons.Any(h => h.Value is { IsValid: true } w
            && w.DesignerName is "weapon_flashbang" or "weapon_smokegrenade" or "weapon_hegrenade"
                or "weapon_molotov" or "weapon_incgrenade") ?? false;
        // Leave basic armor and one smoke's budget; existing utility is not charged twice.
        return CareerWeaponPolicy.ArmorReserve(player.TeamNum == 3, pawn.ArmorValue, helmet) + (utility ? 0 : 300);
    }

    private bool IsCareerPistolRound()
    {
        int played = Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules")
            .FirstOrDefault()?.GameRules?.TotalRoundsPlayed ?? -1;
        int maxRounds = ConVar.Find("mp_maxrounds")?.GetPrimitiveValue<int>() ?? 24;
        return played == 0 || (maxRounds > 0 && played == maxRounds / 2);
    }

    private void ApplyCareerPurchases(CCSPlayerController player)
    {
        if (!CanCareerPurchase(player)) return;
        ApplyTacticalPurchase(player); // Sniper duties take priority, without an intermediate M4 purchase.
        NormalizePurchasedWeapons(player);
        ApplyMissingPrimaryPurchase(player);
        var primaries = player.PlayerPawn.Value!.WeaponServices?.MyWeapons.Select(h => h.Value)
            .Where(w => w is { IsValid: true } && TacticalBuyPolicy.PrimaryPrice(w.DesignerName) > 0).ToArray() ?? [];
        if (primaries.Length != 1) return;
        var weapon = primaries[0]!;
        uint entity = weapon.EntityHandle.Raw;
        uint bought = _purchasedWeapons.GetValueOrDefault(player.Slot)?.GetValueOrDefault(weapon.DesignerName) ?? 0;
        bool old = _roundStartWeapons.GetValueOrDefault(player.Slot)?.Contains(entity) ?? true;
        if (CareerWeaponPolicy.CanUpgradeEconomyPrimary(_careerActive, CanModify(player), _purchasePhase,
            player.TeamNum == 3, PurchaseRole(player), weapon.DesignerName, player.InGameMoneyServices?.Account ?? -1,
            PurchaseReserve(player), ConVar.Find("mp_maxmoney")?.GetPrimitiveValue<int>() ?? 16000,
            entity, bought, old, primaries.Length, CanRefund(player, weapon.DesignerName)))
            Swap(player, weapon.DesignerName, CareerWeaponPolicy.Rifle(player.TeamNum == 3,
                player.SteamID % 2 == 0 ? .25f : .75f));
    }

    private void ApplyMissingPrimaryPurchase(CCSPlayerController player)
    {
        if (!CanCareerPurchase(player) || Server.CurrentTime < _emptyPrimaryReadyAt) return;
        var pawn = player.PlayerPawn.Value!;
        // A missing weapon service is unavailable state, not an empty inventory.
        if (pawn.WeaponServices is null || player.InGameMoneyServices is null) return;
        if (pawn.WeaponServices.MyWeapons.Any(h => h.Value is { IsValid: true } w
            && !_refundingWeapons.Contains(w.EntityHandle.Raw) && TacticalBuyPolicy.PrimaryPrice(w.DesignerName) > 0)) return;

        int money = player.InGameMoneyServices.Account;
        int reserve = PurchaseReserve(player);
        string role = PurchaseRole(player);
        bool pistolRound = IsCareerPistolRound();
        var candidates = CareerWeaponPolicy.EmptyPrimaryCandidates(_careerActive, CanModify(player), _purchasePhase,
            pistolRound, false, player.TeamNum == 3, role, money, reserve, player.SteamID % 2 == 0 ? .25f : .75f);
        if (candidates.Length == 0)
        {
            LogMissingPrimary(player, $"deferred role={role} money={money} reserve={reserve} pistol={pistolRound}");
            return;
        }
        foreach (var weapon in candidates)
        {
            // Recheck before every attempt, including after a failed item spawn.
            if (!CanCareerPurchase(player) || HasPrimaryWeapon(player)) return;
            var currentCandidates = CareerWeaponPolicy.EmptyPrimaryCandidates(_careerActive, CanModify(player),
                _purchasePhase, IsCareerPistolRound(), false, player.TeamNum == 3, PurchaseRole(player),
                player.InGameMoneyServices!.Account, PurchaseReserve(player), player.SteamID % 2 == 0 ? .25f : .75f);
            if (!currentCandidates.Contains(weapon, StringComparer.Ordinal)) continue;
            if (Buy(player, weapon))
            {
                LogMissingPrimary(player, $"purchased weapon={weapon} role={role} money={money} reserve={reserve} remaining={player.InGameMoneyServices.Account}");
                return;
            }
        }
        LogMissingPrimary(player, $"failed candidates={string.Join(',', candidates)} role={role} money={money} reserve={reserve}");
    }

    private void LogMissingPrimary(CCSPlayerController player, string reason)
    {
        if (_emptyPrimaryDiagnostics.GetValueOrDefault(player.Slot) == reason) return;
        _emptyPrimaryDiagnostics[player.Slot] = reason;
        Server.PrintToConsole($"[BotBuy] Missing primary slot={player.Slot} {reason}");
    }
}
