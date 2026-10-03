namespace CareerMatch;

internal sealed record TacticalRadioSpeaker(TacticalCommandContext Context, int Slot, uint Pawn,
    int Tick, bool Alive, bool RoundActive, bool HumanControlled = false);
internal sealed record TacticalRadioHandoff(string Command, int RadioSlot, string MatchNonce,
    int Round, string Side, string IssuerId, IReadOnlyList<string> Recipients);

/// <summary>
/// Engine acceptance, not a typed command, transfers authority. Command Pre opens
/// a scope; player_radio Pre confirms it; Command Post closes it, including when
/// the engine rejects a request on radio cooldown. No guessed radio-slot mapping.
/// Game-thread use. Overrides belong to stable identities and one match/round.
/// </summary>
internal sealed class TacticalRadioPolicy
{
    // Valve resource/ui/radiopanel.txt supplies the classic movement/support
    // commands. Current server.dll also registers regroup and coverme. Reports,
    // acknowledgements, chat-wheel sounds and radio-menu opens are NOT orders.
    internal static readonly IReadOnlyList<string> Commands = Array.AsReadOnly(new[]
    {
        "coverme", "takepoint", "holdpos", "regroup", "followme", "go", "fallback",
        "sticktog", "needbackup", "getout",
    });
    private sealed record Attempt(string Command, TacticalRadioSpeaker Speaker);
    private Attempt? _attempt;
    private readonly HashSet<(string Nonce, int Round, string Side, string Id)> _overrides = [];
    internal long Revision { get; private set; }
    internal bool HasPendingCommand => _attempt is not null;

    internal static string? Parse(string? command)
    {
        var name = (command ?? "").Trim().ToLowerInvariant();
        return Commands.Contains(name, StringComparer.Ordinal) ? name : null;
    }

    private static bool Authorized(TacticalRadioSpeaker speaker)
    {
        var c = speaker.Context;
        return c.AuthorizedMatch && c.AuthorizedHuman && c.SpeakerValid && !c.SpeakerIsBot
            && !c.Observer && !c.Warmup && !c.MatchCompleted && speaker.RoundActive
            && speaker.Alive && speaker.Slot >= 0 && speaker.Pawn != 0
            && c.Round > 0 && c.MatchNonce.Length > 0 && c.SpeakerId.Length > 0
            && TacticalCommands.NormalizeSide(c.Side) is "t" or "ct";
    }

    internal bool BeginCommand(string? command, TacticalRadioSpeaker speaker)
    {
        _attempt = null;
        if (Parse(command) is not { } name || !Authorized(speaker)) return false;
        _attempt = new(name, speaker);
        return true;
    }

    internal void EndCommand(string? command, int speakerSlot)
    {
        if (_attempt is { } attempt && attempt.Command == Parse(command) && attempt.Speaker.Slot == speakerSlot)
            _attempt = null;
    }

    internal TacticalRadioHandoff? Confirm(TacticalRadioSpeaker speaker, int radioSlot,
        IEnumerable<TacticalBotCandidate> candidates)
    {
        if (_attempt is not { } attempt || !Authorized(speaker) || radioSlot <= 0) return null;
        var previous = attempt.Speaker; var c = speaker.Context; var before = previous.Context;
        if (speaker.Slot != previous.Slot || speaker.Pawn != previous.Pawn || speaker.Tick != previous.Tick
            || c.MatchNonce != before.MatchNonce || c.Round != before.Round || c.SpeakerId != before.SpeakerId
            || TacticalCommands.NormalizeSide(c.Side) != TacticalCommands.NormalizeSide(before.Side)) return null;
        _attempt = null; // The genuine event consumes this command exactly once.
        var side = TacticalCommands.NormalizeSide(c.Side);
        var recipients = candidates.Where(a => a.IsBot && a.IsValid && a.Alive && !a.HumanControlled
            && a.Id.Length > 0 && a.Id != c.SpeakerId && TacticalCommands.NormalizeSide(a.Side) == side)
            .Select(a => a.Id).Distinct(StringComparer.Ordinal).ToArray();
        foreach (var id in recipients) _overrides.Add((c.MatchNonce, c.Round, side, id));
        Revision++;
        return new(attempt.Command, radioSlot, c.MatchNonce, c.Round, side, c.SpeakerId, recipients);
    }

    internal bool Owns(string nonce, int round, string side, string id) =>
        _overrides.Contains((nonce, round, TacticalCommands.NormalizeSide(side), id));
    internal static bool SameScope(CommandPlan? plan, TacticalRadioHandoff handoff) =>
        plan is not null && plan.MatchNonce == handoff.MatchNonce && plan.Round == handoff.Round
            && plan.Side == handoff.Side;

    internal void Supersede(CommandPlan plan)
    {
        _attempt = null;
        _overrides.RemoveWhere(k => k.Nonce == plan.MatchNonce && k.Round == plan.Round && k.Side == plan.Side);
        Revision++; // Invalidates pending callbacks from an earlier player intent.
    }

    internal void Reset()
    {
        _attempt = null; _overrides.Clear(); Revision++;
    }
}

internal static class TacticalRadioRelease
{
    // Remove an actor from registries BEFORE calling this. One failing token
    // must not keep the actor alive or skip its remaining movement/look tokens.
    internal static void All(Action<Exception> onError, params Action[] releases)
    {
        foreach (var release in releases)
            try { release(); }
            catch (Exception ex) { onError(ex); }
    }
}
