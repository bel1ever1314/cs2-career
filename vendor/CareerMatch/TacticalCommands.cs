using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace CareerMatch;

public enum TacticalOrder { RushA, RushB, Cancel, Playbook }

public sealed record TacticalCommand(TacticalOrder Order, string Site, string Canonical, string TacticId = "");

/// <summary>Immutable intent only: no coordinates, console commands, pawn or Bot handles.</summary>
public sealed record CommandPlan(string MatchNonce, int Round, string Side, string IssuerId,
    TacticalOrder Order, string Site, string TacticId = "");

/// <summary>
/// Adapter supplies verified session/identity facts. Round is a preparation epoch, NOT a
/// scored-round counter. SpeakerIsBot must use the stable identity ledger, not BotHider's
/// mutable controller flag. Preparation must be read from current FreezePeriod.
/// </summary>
public sealed record TacticalCommandContext
{
    public string MatchNonce { get; init; } = "";
    public int Round { get; init; }
    public string SpeakerId { get; init; } = "";
    public string Side { get; init; } = "";
    public bool AuthorizedMatch { get; init; }
    public bool AuthorizedHuman { get; init; }
    public bool SpeakerValid { get; init; }
    public bool SpeakerIsBot { get; init; }
    public bool Observer { get; init; }
    public bool Warmup { get; init; }
    public bool Preparation { get; init; }
    public bool MatchCompleted { get; init; }
}

public sealed record TacticalDecision(bool Recognized, bool Accepted, string Code,
    string Message, CommandPlan? Plan);

/// <summary>Stable ledger identity and current ownership; do not infer either from a name.</summary>
public sealed record TacticalBotCandidate(string Id, string Side, bool IsBot,
    bool IsValid, bool Alive, bool HumanControlled = false);

public static class TacticalCommands
{
    public const string Usage = "准备阶段输入 play <id>。";
    public const int MaximumInputCharacters = 128;

    /// <summary>Only entire supported chat messages match; ordinary chat returns null.</summary>
    public static TacticalCommand? Parse(string? channel, string? arguments)
    {
        var source = (channel ?? "").Trim().ToLowerInvariant();
        if (source is not ("say" or "say_team") || arguments is null
            || arguments.Length > MaximumInputCharacters) return null;
        var text = arguments.Trim();
        if (text.Length >= 2 && IsQuotePair(text[0], text[^1])) text = text[1..^1].Trim();
        var normalized = new StringBuilder(text.Length);
        var space = false;
        foreach (var ch in text)
        {
            if (char.IsWhiteSpace(ch)) { space = normalized.Length > 0; continue; }
            // Do not remove embedded quotation/formatting/injection characters into a command.
            if (char.IsControl(ch) || char.GetUnicodeCategory(ch) == System.Globalization.UnicodeCategory.Format
                || ch is '\'' or '"' or '“' or '”' or '‘' or '’') return null;
            if (space) normalized.Append(' ');
            normalized.Append(char.ToLowerInvariant(ch));
            space = false;
        }
        text = normalized.ToString();
        if (text.StartsWith('!') || text.StartsWith('/')) text = text[1..].TrimStart();
        if (text is "default" or "取消战术") return new(TacticalOrder.Cancel, "", "default");
        foreach (var prefix in new[] { "play ", "tactic ", "战术 " })
            if (text.StartsWith(prefix, StringComparison.Ordinal))
            {
                var id = text[prefix.Length..];
                return TacticalPlaybook.ValidId(id) ? new(TacticalOrder.Playbook, "", "play " + id, id) : null;
            }
        if (text.StartsWith("5人", StringComparison.Ordinal)) text = text[2..].TrimStart();
        return text switch
        {
            "rusha" or "rush a" or "全员a" or "全员 a" => new(TacticalOrder.RushA, "A", "rusha"),
            "rushb" or "rush b" or "全员b" or "全员 b" => new(TacticalOrder.RushB, "B", "rushb"),
            _ => null
        };
    }

    public static TacticalDecision Gate(TacticalCommand command, TacticalCommandContext context)
    {
        TacticalDecision Reject(string code, string message) => new(true, false, code, message, null);
        if (!context.AuthorizedMatch || string.IsNullOrWhiteSpace(context.MatchNonce))
            return Reject("unauthorized_match", "当前不是已授权的 CareerMatch 比赛。");
        if (context.MatchCompleted) return Reject("match_completed", "比赛已结束，不能设置战术。");
        if (context.Observer) return Reject("observer", "观战模式不能指挥参赛 Bot。");
        if (!context.SpeakerValid || string.IsNullOrWhiteSpace(context.SpeakerId))
            return Reject("invalid_speaker", "当前玩家身份尚未就绪。");
        if (context.SpeakerIsBot) return Reject("bot_speaker", "Bot 不能发布玩家战术指令。");
        if (!context.AuthorizedHuman) return Reject("unauthorized_human", "只有本场绑定的真人选手可以指挥同队 Bot。");
        var side = NormalizeSide(context.Side);
        if (side is not ("t" or "ct")) return Reject("invalid_side", "请先加入本场 T 或 CT 队伍，旁观者不能指挥 Bot。");
        if (context.Warmup) return Reject("warmup", "暖身阶段不设置正式回合战术；请在正式准备阶段输入。");
        if (!context.Preparation || context.Round < 1) return Reject("not_preparation", "仅在正式比赛准备阶段可以设置或取消战术。");
        if (command.Order == TacticalOrder.Cancel)
            return new(true, true, "cancelled", "已取消本回合战术。", null);
        if (command.Order == TacticalOrder.Playbook && TacticalPlaybook.ValidId(command.TacticId) && command.Site.Length == 0)
            return new(true, true, "queued", $"本回合采用战术：{command.TacticId}。",
                new(context.MatchNonce, context.Round, side, context.SpeakerId, command.Order, "", command.TacticId));
        if ((command.Order == TacticalOrder.RushA && command.Site != "A")
            || (command.Order == TacticalOrder.RushB && command.Site != "B")
            || command.Order is not (TacticalOrder.RushA or TacticalOrder.RushB))
            return Reject("invalid_command", "无效的战术指令。");
        return new(true, true, "queued", $"本回合采用战术：Rush {command.Site}。",
            new(context.MatchNonce, context.Round, side, context.SpeakerId, command.Order, command.Site));
    }

    /// <summary>Apply-time target selection: teammates only, never a human or a taken-over Bot.</summary>
    public static IReadOnlyList<string> EligibleBots(CommandPlan plan, IEnumerable<TacticalBotCandidate> actors)
    {
        if (plan.Order is not (TacticalOrder.RushA or TacticalOrder.RushB)
            || NormalizeSide(plan.Side) is not ("t" or "ct")) return Array.Empty<string>();
        return actors.Where(actor => actor.IsValid && actor.Alive && actor.IsBot && !actor.HumanControlled
                && !string.IsNullOrWhiteSpace(actor.Id) && actor.Id != plan.IssuerId
                && NormalizeSide(actor.Side) == plan.Side)
            .Select(actor => actor.Id).Distinct(StringComparer.Ordinal).ToArray();
    }

    internal static string NormalizeSide(string? side) => (side ?? "").Trim().ToLowerInvariant();
    private static bool IsQuotePair(char first, char last) => (first, last) is
        ('"', '"') or ('\'', '\'') or ('“', '”') or ('‘', '’');
}

/// <summary>
/// Single authorized-human match queue. Only the last accepted intent survives.
/// Reset on each round-start/map/session/restart; Take consumes at freeze-end once.
/// Wrong nonce/epoch/side cannot consume or apply another round's plan. Game-thread use.
/// </summary>
public sealed class TacticalCommandQueue
{
    public CommandPlan? Pending { get; private set; }

    public TacticalDecision Submit(string? channel, string? arguments, TacticalCommandContext context)
    {
        var command = TacticalCommands.Parse(channel, arguments);
        if (command is null) return new(false, false, "ordinary_chat", "", null);
        var decision = TacticalCommands.Gate(command, context);
        if (!decision.Accepted) return decision;
        Pending = decision.Plan; // Cancel has no plan and clears the last accepted order.
        return decision;
    }

    public CommandPlan? Take(string matchNonce, int round, string side)
    {
        var plan = Pending;
        if (plan is null || plan.MatchNonce != matchNonce || plan.Round != round
            || plan.Side != TacticalCommands.NormalizeSide(side)) return null;
        Pending = null;
        return plan;
    }

    public void Reset() => Pending = null;
}
