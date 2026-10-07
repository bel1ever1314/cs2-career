using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Timers;

namespace BotBuyPatch;

// Only unavailable plugin infrastructure is stubbed. The production purchase,
// eligibility, inventory, tactical and timer methods are compiled by the project.
public sealed partial class BotBuyPatch
{
    public Microsoft.Extensions.Logging.TestLogger Logger { get; } = new();
    private bool _careerActive = true, _purchasePhase = true;
    private int _roundGeneration = 1;
    private string _roundMap = "de_mirage";
    private readonly Dictionary<ulong, string> _careerRoles = [];
    private readonly Dictionary<ulong, string> _tacticalDuties = [];
    private readonly Dictionary<int, uint> _roundPawns = [];
    private readonly Dictionary<int, HashSet<uint>> _roundStartWeapons = [];
    private readonly Dictionary<int, Dictionary<string, uint>> _purchasedWeapons = [];
    private readonly HashSet<uint> _refundingWeapons = [];
    private readonly Dictionary<CounterStrikeSharp.API.Modules.Utils.CsTeam, List<CCSPlayerController>> _poorPlayersByTeam = [];
    private readonly List<(float At, Action Callback)> _timers = [];

    public int SwapCalls => FakeWorld.Players.Sum(p => p.RemovalCalls.Count);
    public int PurchasedCount => _purchasedWeapons.Values.Sum(items => items.Count);
    public IEnumerable<float> TimerTimes => _timers.Select(timer => timer.At);

    public void Track(CCSPlayerController player, string role)
    {
        _careerRoles[player.SteamID] = role;
        _roundPawns[player.Slot] = player.PlayerPawn.Value!.EntityHandle.Raw;
        _roundStartWeapons[player.Slot] = [];
        if (!FakeWorld.Players.Contains(player)) FakeWorld.Players.Add(player);
    }

    public void AssignDuty(CCSPlayerController player, string duty) => _tacticalDuties[player.SteamID] = duty;
    public void HumanRole(string json)
    {
        using var doc = System.Text.Json.JsonDocument.Parse(json);
        ReadHumanGiftRole(doc.RootElement);
    }
    public void MarkPendingRefund(CBasePlayerWeapon weapon) => _refundingWeapons.Add(weapon.EntityHandle.Raw);
    public void MarkRoundStart(CCSPlayerController player, CBasePlayerWeapon weapon) =>
        _roundStartWeapons[player.Slot].Add(weapon.EntityHandle.Raw);
    public void Purchased(CCSPlayerController player, string name) =>
        OnItemPurchase(new() { Userid = player, Weapon = name }, new());
    public void NewRoundForTest() { _roundGeneration++; _m4PreferenceAttempts.Clear(); }
    public void SetActive(bool active) => _careerActive = active;
    public void EndPurchasePhase() => _purchasePhase = false;
    public void NextRound() => _roundGeneration++;
    public void Schedule()
    {
        var players = CaptureRoundPlayers();
        CapturePoorPlayers(players);
        ScheduleTeamGifts(players);
    }
    public void GiveAgain() => GiveTeamWeapons(FakeWorld.Players);
    public void Apply(CCSPlayerController player) => ApplyCareerPurchases(player);
    public void TacticalOnly(CCSPlayerController player) => ApplyTacticalPurchase(player);
    public string CanonicalWeapon(CBasePlayerWeapon weapon) => WeaponName(weapon);
    public bool PurchaseDirect(CCSPlayerController player, string weapon) => Buy(player, weapon);

    public void Advance(float now)
    {
        Server.CurrentTime = now;
        foreach (var timer in _timers.Where(timer => timer.At <= now).OrderBy(timer => timer.At).ToArray())
        {
            _timers.Remove(timer);
            timer.Callback();
        }
    }

    private void AddTimer(float delay, Action callback, TimerFlags flags) =>
        _timers.Add((Server.CurrentTime + delay, callback));
    private string CareerRole(CCSPlayerController player) => _careerRoles.GetValueOrDefault(player.SteamID, "");
    private string PurchaseRole(CCSPlayerController player) =>
        _tacticalDuties.TryGetValue(player.SteamID, out var duty) && duty != "auto" ? duty : CareerRole(player);

    // Non-career legacy refund history is unrelated to the verified per-round
    // primary transaction under test. The primary refund and swap run production.
    private (List<string> Weapons, int Money, int Armor) PreviousInventory(CCSPlayerController player) => ([], 0, 0);
}
