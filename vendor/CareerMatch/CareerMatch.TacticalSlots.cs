using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Core.Capabilities;
using CareerTactics;
using System.Text.Json;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    private static readonly PluginCapability<Func<string, string>> TacticalBuying = new(TacticalBuyPlan.CapabilityName);
    private string _customAssignmentKey = "";
    private IReadOnlyList<TacticRosterBinding> _customAssignments = [];

    private IReadOnlyList<TacticRosterBinding> ResolveCustomSlots(CommandPlan plan, CustomTactic tactic)
    {
        var key = $"{plan.MatchNonce}:{plan.Round}:{plan.Side}:{plan.TacticId}";
        if (key == _customAssignmentKey) return _customAssignments;
        var request = _request ?? throw new InvalidDataException("本场名单未就绪");
        var team = request.HumanTeam == "t" ? request.T : request.Ct;
        var roster = new[] { request.HumanPlayerId }.Concat(team.Players.Select(p => p.PlayerId)).ToArray();
        var members = team.Players.Select(p => new TacticalRosterMember(p.PlayerId, p.Role,
            p.TacticalAbilities, p.EffectiveStrength)).Prepend(new(request.HumanPlayerId, "", request.HumanTacticalAbilities)).ToArray();
        return TacticalSlotAssignment.Assign(tactic, roster, request.HumanPlayerId, members);
    }

    private void CommitCustomSlots(CommandPlan plan)
    {
        if (plan.Order != TacticalOrder.Playbook) { ClearCustomSlots(); return; }
        var tactic = _customPlaybook!.Tactics.Single(t => t.Id == plan.TacticId);
        var assignments = ResolveCustomSlots(plan, tactic);
        _customAssignmentKey = $"{plan.MatchNonce}:{plan.Round}:{plan.Side}:{plan.TacticId}";
        _customAssignments = assignments;
        TacticalTrace("custom_slot_assignment", new { plan.TacticId, plan.Round, tactic.Assignment,
            tactic.HumanSlot, slots = assignments.Select(a => new { a.TacticSlot, a.PlayerId, a.Route.Duty }) });
    }
    private void ClearCustomSlots() { _customAssignmentKey = ""; _customAssignments = []; }

    private void SubmitTacticalBuying(CommandPlan? plan, CCSPlayerController? human)
    {
        if (_request is not { Active: true, Observer: false } request) return;
        var side = human?.TeamNum == 3 ? "ct" : human?.TeamNum == 2 ? "t" : plan?.Side;
        if (side is not ("ct" or "t")) return;
        var team = request.HumanTeam == "t" ? request.T : request.Ct;
        var duties = team.Players.ToDictionary(p => p.SteamId, _ => "auto");
        if (plan?.Order == TacticalOrder.Playbook)
            foreach (var binding in _customAssignments.Where(b => b.PlayerId != request.HumanPlayerId))
                duties[team.Players.Single(p => p.PlayerId == binding.PlayerId).SteamId] = binding.Route.Duty;
        var required = duties.Values.Any(d => d != "auto");
        try
        {
            var api = TacticalBuying.Get();
            if (api is null)
            {
                if (required) human?.PrintToChat(" \x09战术路线已接受，但 BotBuy 职责购买接口未加载，武器购买仍按原规则。\x01");
                return;
            }
            var rules = Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules").FirstOrDefault()?.GameRules;
            if (rules is null) return;
            var response = api(JsonSerializer.Serialize(new TacticalBuyPlan { Nonce = request.Nonce,
                Map = Server.MapName, Round = rules.TotalRoundsPlayed, Side = side, Duties = duties }));
            using var reply = JsonDocument.Parse(response);
            var accepted = reply.RootElement.TryGetProperty("accepted", out var okay) && okay.GetBoolean();
            TacticalTrace("custom_buy_plan", new { accepted, duties, response });
            if (required && !accepted) human?.PrintToChat(" \x09本回合职责购买未生效；武器保持原购买规则。\x01");
        }
        catch (Exception ex)
        {
            TacticalTrace("custom_buy_unavailable", new { reason = ex.Message });
            if (required) human?.PrintToChat(" \x09职责购买接口不可用；路线仍执行，武器保持原购买规则。\x01");
        }
    }

    private string SlotDisplayName(string id) => id == _request?.HumanPlayerId ? _request.Player
        : _request?.Ct.Players.Concat(_request.T.Players).FirstOrDefault(p => p.PlayerId == id)?.DisplayName ?? id;
}
