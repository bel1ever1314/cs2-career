using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Cvars;
using CounterStrikeSharp.API.Modules.Utils;
using CareerTactics;
using Microsoft.Extensions.Logging;

namespace BotBuyPatch;

public sealed partial class BotBuyPatch
{
    private readonly HashSet<uint> _giftedPawns = [];
    private readonly Dictionary<uint, int> _giftDonorCounts = [];
    private readonly Dictionary<uint, string> _giftWaitReasons = [];

    private List<CCSPlayerController> CaptureRoundPlayers()
    {
        var players = Utilities.FindAllEntitiesByDesignerName<CCSPlayerController>("cs_player_controller")
            .Where(p => p.IsValid).ToList();
        foreach (var player in players)
        {
            var pawn = player.PlayerPawn.Value;
            if (pawn is not { IsValid: true }) continue;
            _roundPawns[player.Slot] = pawn.EntityHandle.Raw;
            _roundStartWeapons[player.Slot] = pawn.WeaponServices?.MyWeapons
                .Select(h => h.Value).Where(w => w is { IsValid: true })
                .Select(w => w!.EntityHandle.Raw).ToHashSet() ?? [];
        }
        return players;
    }

    private void CapturePoorPlayers(List<CCSPlayerController> players)
    {
        _poorPlayersByTeam.Clear();
        _giftedPawns.Clear();
        _giftDonorCounts.Clear(); _giftWaitReasons.Clear();
        foreach (var team in new[] { CsTeam.CounterTerrorist, CsTeam.Terrorist })
            _poorPlayersByTeam[team] = players.Where(p => p.IsValid && p.Team == team
                && p.InGameMoneyServices?.Account < 2800).ToList();
    }

    private void ScheduleTeamGifts(List<CCSPlayerController> players)
    {
        var started = Server.CurrentTime;
        void Review()
        {
            var rules = Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules").FirstOrDefault()?.GameRules;
            if (!_purchasePhase || rules is not { WarmupPeriod: false, FreezePeriod: true }) return;
            GiveTeamWeapons(players);
            // Native buying, tactical AWP selection, and the human's shopping
            // don't all finish at exactly two seconds. Recheck only in freeze
            // time, at 1 Hz, with the existing round/map cancellation guard.
            if (Server.CurrentTime - started < 60) AddRoundTimer(1f, Review);
        }
        AddRoundTimer(2f, Review);
    }

    private bool CanReceiveTeamWeapon(CCSPlayerController player, CsTeam team)
    {
        if (!player.IsValid || player.Team != team || player.InGameMoneyServices is null) return false;
        var pawn = player.PlayerPawn.Value;
        if (pawn is not { IsValid: true, Health: > 0, WeaponServices: not null }
            || !_roundPawns.TryGetValue(player.Slot, out var expected) || expected != pawn.EntityHandle.Raw
            || _giftedPawns.Contains(expected) || HasPrimaryWeapon(player)) return false;
        // Use CURRENT buying power, not the pre-purchase poor-player cohort
        // (which is still used by upstream's armor/defuser policy).
        int riflePrice = TacticalBuyPolicy.PrimaryPrice(CareerWeaponPolicy.Rifle(team == CsTeam.CounterTerrorist, 0));
        if (player.InGameMoneyServices.Account >= riflePrice) return false;
        // Receiving does not spend the human's money or replace their equipment.
        // Do not use bot-only CanModify here (also covers human-controlled bots).
        return !_careerActive || pawn.InBuyZone;
    }

    private void GiveTeamWeapons(List<CCSPlayerController> players)
    {
        if (IsFirstRoundOfHalf() || !string.IsNullOrEmpty(ConVar.Find("bot_loadout")?.StringValue)) return;
        var rules = Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules").FirstOrDefault()?.GameRules;
        if (rules is not { WarmupPeriod: false, FreezePeriod: true } || !_purchasePhase) return;
        foreach (var team in new[] { CsTeam.CounterTerrorist, CsTeam.Terrorist })
        {
            var poor = players.Where(p => CanReceiveTeamWeapon(p, team))
                .OrderBy(p => p.InGameMoneyServices!.Account).ThenBy(p => p.Slot).ToArray();
            var failedThisCheck = new HashSet<uint>();
            int index = 0;
            foreach (var donor in players.Where(p => p.IsValid && p.Team == team)
                .OrderByDescending(p => p.InGameMoneyServices?.Account ?? 0).ThenBy(p => p.Slot))
            {
                var donorPawn = donor.PlayerPawn.Value?.EntityHandle.Raw ?? 0;
                int given = _giftDonorCounts.GetValueOrDefault(donorPawn);
                while (given < 3 && index < poor.Length)
                {
                    string gun = CareerWeaponPolicy.Rifle(team == CsTeam.CounterTerrorist, Random.Shared.NextSingle());
                    int price = TacticalBuyPolicy.PrimaryPrice(gun);
                    // Spending remains bot-only; BotHider identities use our verified roster.
                    if (!CanModify(donor) || donor.Team != team || donor.InGameMoneyServices is null
                        || donor.InGameMoneyServices.Account < price || !HasPrimaryWeapon(donor)
                        || (_careerActive && !CanCareerPurchase(donor))) break;
                    var recipient = poor[index++];
                    if (!CanReceiveTeamWeapon(recipient, team)) continue;
                    var handle = recipient.GiveNamedItem(gun);
                    if (handle == IntPtr.Zero || !new CEntityInstance(handle).IsValid)
                    {
                        failedThisCheck.Add(recipient.PlayerPawn.Value!.EntityHandle.Raw);
                        TraceGiftWait(recipient, "native_grant_failed"); continue;
                    }
                    // Guard delayed inventory attachment and duplicate pawn/controller views.
                    _giftedPawns.Add(recipient.PlayerPawn.Value!.EntityHandle.Raw);
                    _giftWaitReasons.Remove(recipient.PlayerPawn.Value!.EntityHandle.Raw);
                    donor.InGameMoneyServices.Account -= price;
                    Utilities.SetStateChanged(donor, "CCSPlayerController", "m_pInGameMoneyServices");
                    Logger.LogInformation("[BotBuy] Gift donor={Donor} recipient={Recipient} weapon={Weapon} remaining={Money}",
                        donor.PlayerName, recipient.PlayerName, gun, donor.InGameMoneyServices.Account);
                    VerifyTeamGift(recipient, gun, recipient.PlayerPawn.Value!.EntityHandle.Raw);
                    foreach (var teammate in players.Where(p => p.IsValid && p.Team == team))
                        teammate.PrintToChat($"{ChatColors.Green}{donor.PlayerName}{ChatColors.Yellow}: {recipient.PlayerName}, I dropped a weapon for ya");
                    given++;
                    _giftDonorCounts[donorPawn] = given;
                }
            }
            foreach (var recipient in poor.Where(p => CanReceiveTeamWeapon(p, team)
                && !failedThisCheck.Contains(p.PlayerPawn.Value!.EntityHandle.Raw)))
                TraceGiftWait(recipient, "no_funded_armed_donor");
        }
    }

    private void TraceGiftWait(CCSPlayerController recipient, string reason)
    {
        var pawn = recipient.PlayerPawn.Value!.EntityHandle.Raw;
        if (_giftWaitReasons.GetValueOrDefault(pawn) == reason) return;
        _giftWaitReasons[pawn] = reason;
        Logger.LogInformation("[BotBuy] Gift waiting recipient={Recipient} money={Money} reason={Reason}",
            recipient.PlayerName, recipient.InGameMoneyServices!.Account, reason);
    }

    private void VerifyTeamGift(CCSPlayerController recipient, string gun, uint expectedPawn)
    {
        AddRoundTimer(.2f, () =>
        {
            if (!recipient.IsValid || recipient.PlayerPawn.Value is not { IsValid: true } pawn
                || pawn.EntityHandle.Raw != expectedPawn) return;
            var inventory = pawn.WeaponServices?.MyWeapons.Select(h => h.Value)
                .Where(w => w is { IsValid: true }).Select(w => WeaponName(w!)).ToArray() ?? [];
            Logger.LogInformation("[BotBuy] Gift verification recipient={Recipient} weapon={Weapon} result={Result} weapons={Weapons}",
                recipient.PlayerName, gun, inventory.Contains(gun) ? "confirmed" : "not_attached", string.Join(',', inventory));
        });
    }
}
