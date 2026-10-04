using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Cvars;
using CareerTactics;
using Microsoft.Extensions.Logging;

namespace BotBuyPatch;

public sealed partial class BotBuyPatch
{
    private readonly HashSet<uint> _m4PreferenceAttempts = [];

    // CS2 1.41.8.8 reduces the M4-S item definition through its shared
    // weapon_m4a1 item_class when building a native bot's buy command. Fix the
    // resulting purchase, not the game's binaries or every bot's full-buy plan.
    // ROLE_STYLE uses RiflePro / SniperPro; both prefer M4-S to these fallbacks.
    private void RepairM4Preference(CCSPlayerController player)
    {
        if (!CanCareerPurchase(player) || player.TeamNum != 3 || IsFirstRoundOfHalf()
            || CareerRole(player) is not ("rifle" or "entry" or "support" or "igl" or "lurk" or "awp")
            || _tacticalDuties.GetValueOrDefault(player.SteamID) == "awp") return;
        var pawn = player.PlayerPawn.Value!;
        var primaries = pawn.WeaponServices?.MyWeapons.Select(h => h.Value)
            .Where(w => w is { IsValid: true } && !_refundingWeapons.Contains(w.EntityHandle.Raw)
                && TacticalBuyPolicy.PrimaryPrice(WeaponName(w)) > 0).ToArray();
        if (primaries is not { Length: 1 } || player.InGameMoneyServices is null) return;
        var weapon = primaries[0]!;
        var name = WeaponName(weapon);
        if (name is not ("weapon_m4a1" or "weapon_famas" or "weapon_p90" or "weapon_mp9")) return;
        // CanRefund requires the exact item_purchase entity from this round.
        // Carried weapons, pickups, teammate gifts and pending removals fail it.
        if (!CanRefund(player, name)) return;
        int before = player.InGameMoneyServices.Account;
        int price = TacticalBuyPolicy.PrimaryPrice("weapon_m4a1_silencer");
        if (Math.Min((long)(ConVar.Find("mp_maxmoney")?.GetPrimitiveValue<int>() ?? 16000),
            (long)before + TacticalBuyPolicy.PrimaryPrice(name)) < price
            || !_m4PreferenceAttempts.Add(pawn.EntityHandle.Raw)) return;

        bool replaced = Swap(player, name, "weapon_m4a1_silencer");
        Logger.LogInformation("[BotBuy] M4 preference slot={Slot} name={Name} from={From} result={Result} money={Before}->{After}",
            player.Slot, player.PlayerName, name, replaced ? "granted" : "failed",
            before, player.InGameMoneyServices.Account);
        if (!replaced) return;
        var expectedPawn = pawn.EntityHandle.Raw;
        // GiveNamedItem can attach on a later frame. Do not delete a valid return
        // just because it has not yet appeared in MyWeapons. Verify separately.
        AddRoundTimer(.2f, () =>
        {
            if (!CanModify(player) || player.PlayerPawn.Value?.EntityHandle.Raw != expectedPawn) return;
            var inventory = player.PlayerPawn.Value!.WeaponServices?.MyWeapons.Select(h => h.Value)
                .Where(w => w is { IsValid: true } && !_refundingWeapons.Contains(w.EntityHandle.Raw))
                .Select(w => WeaponName(w!)).ToArray() ?? [];
            Logger.LogInformation("[BotBuy] M4 preference verification slot={Slot} result={Result} weapons={Weapons}",
                player.Slot, inventory.Contains("weapon_m4a1_silencer") ? "confirmed" : "not_attached",
                string.Join(',', inventory));
        });
    }
}
