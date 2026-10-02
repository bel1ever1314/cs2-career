using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Core.Capabilities;
using CareerTactics;
using System.Text.Json;

namespace BotBuyPatch;

public sealed partial class BotBuyPatch
{
    private static readonly PluginCapability<Func<string, string>> TacticalBuying = new(TacticalBuyPlan.CapabilityName);
    private bool _buyApiLoaded;
    private string _careerNonce = "";
    private int _tacticalBuyRevision;
    private readonly Dictionary<ulong, string> _careerSides = new();
    private readonly Dictionary<ulong, string> _tacticalDuties = new();

    public override void Load(bool hotReload)
    {
        _buyApiLoaded = true;
        Capabilities.RegisterPluginCapability(TacticalBuying, () => ReceiveTacticalBuyPlan);
    }
    public override void Unload(bool hotReload)
    { _buyApiLoaded = false; _purchasePhase = false; _tacticalDuties.Clear(); _roundGeneration++; }

    private string PurchaseRole(CCSPlayerController player) =>
        _tacticalDuties.TryGetValue(player.SteamID, out var duty) && duty != "auto" ? duty : CareerRole(player);

    private string ReceiveTacticalBuyPlan(string json)
    {
        string Reply(bool accepted, string reason) => JsonSerializer.Serialize(new { accepted, reason });
        if (!_buyApiLoaded) return Reply(false, "botbuy_unloaded");
        try
        {
            var plan = TacticalBuyPlan.Parse(json);
            var rules = Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules").FirstOrDefault()?.GameRules;
            // Request ct/t are OPENING teams; use verified current controllers
            // for buying after halftime, never rewrite permanent roster identity.
            var liveRosterSides = Utilities.FindAllEntitiesByDesignerName<CCSPlayerController>("cs_player_controller")
                .Where(p => p.IsValid && _careerRoles.ContainsKey(p.SteamID) && p.TeamNum is 2 or 3)
                .GroupBy(p => p.SteamID).Where(g => g.Count() == 1)
                .ToDictionary(g => g.Key, g => g.Single().TeamNum == 3 ? "ct" : "t");
            if (rules is null || rules.WarmupPeriod || !plan.Matches(_careerNonce, Server.MapName,
                rules.TotalRoundsPlayed, _careerActive, _purchasePhase && rules.FreezePeriod, liveRosterSides))
                return Reply(false, "buy_plan_session_or_phase_mismatch");
            var players = Utilities.FindAllEntitiesByDesignerName<CCSPlayerController>("cs_player_controller")
                .Where(p => p.IsValid && plan.Duties.ContainsKey(p.SteamID)).ToArray();
            if (players.Length != plan.Duties.Count || players.Select(p => p.SteamID).Distinct().Count() != players.Length
                || players.Any(p => !CanModify(p) || (p.TeamNum == 3 ? "ct" : p.TeamNum == 2 ? "t" : "") != plan.Side))
                return Reply(false, "buy_plan_roster_not_unique");
            // Replace only this side's preference. Never give money or undo a
            // completed purchase on cancel/reassignment. Human inventory untouched.
            foreach (var id in _tacticalDuties.Keys.Where(id => liveRosterSides.GetValueOrDefault(id) == plan.Side).ToArray())
                _tacticalDuties.Remove(id);
            foreach (var item in plan.Duties) _tacticalDuties[item.Key] = item.Value;
            var revision = ++_tacticalBuyRevision;
            foreach (var player in players) ApplyTacticalPurchase(player);
            foreach (var delay in new[] { .2f, .8f, 1.6f, 3.2f })
                AddRoundTimer(delay, () => {
                    if (revision != _tacticalBuyRevision) return;
                    foreach (var player in Utilities.FindAllEntitiesByDesignerName<CCSPlayerController>("cs_player_controller"))
                        if (player.IsValid && _tacticalDuties.ContainsKey(player.SteamID)) ApplyTacticalPurchase(player);
                });
            return Reply(true, "accepted_money_required");
        }
        catch (Exception ex) { return Reply(false, "buy_plan_rejected:" + ex.Message); }
    }

    private void ApplyTacticalPurchase(CCSPlayerController player)
    {
        if (!CanModify(player) || !_tacticalDuties.TryGetValue(player.SteamID, out var duty) || duty == "auto") return;
        var pawn = player.PlayerPawn.Value!;
        var rules = Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules").FirstOrDefault()?.GameRules;
        if (rules is null || rules.WarmupPeriod || !rules.FreezePeriod || !pawn.InBuyZone) return;
        var primaries = pawn.WeaponServices?.MyWeapons.Select(h => h.Value)
            .Where(w => w is { IsValid: true } && TacticalBuyPolicy.PrimaryPrice(w.DesignerName) > 0).ToArray() ?? [];
        if (primaries.Length == 0)
        {
            if (duty == "awp" && (player.InGameMoneyServices?.Account ?? 0) >= TacticalBuyPolicy.AwpPrice)
                Buy(player, "weapon_awp");
            return;
        }
        if (primaries.Length != 1) return;
        var weapon = primaries[0]!; var name = weapon.DesignerName; var entity = weapon.EntityHandle.Raw;
        var bought = _purchasedWeapons.GetValueOrDefault(player.Slot)?.GetValueOrDefault(name) ?? 0;
        var old = _roundStartWeapons.GetValueOrDefault(player.Slot)?.Contains(entity) ?? true;
        var money = player.InGameMoneyServices?.Account ?? 0;
        if (TacticalBuyPolicy.CanReplace(duty, name, money, entity, bought, old, 1, CanRefund(player, name)))
            Swap(player, name, "weapon_awp");
        else if (duty != "awp" && name == "weapon_awp" && entity == bought && bought != 0 && !old && CanRefund(player, name))
            Swap(player, name, CareerWeaponPolicy.Rifle(player.TeamNum == 3, player.SteamID % 2 == 0 ? .25f : .75f));
    }
}
