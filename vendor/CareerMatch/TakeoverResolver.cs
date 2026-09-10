namespace CareerMatch;

// A bot_takeover event can contain the HUMAN in both userid and botid.
// Resolve from immutable round-start pawn ownership and the controller swap,
// never from roster order, display name, or BotHider's mutable IsBot flag.
internal sealed record ControlSnapshot(string Id, uint Pawn, string? Original,
    bool Controlling, bool WasControlled, bool IsBot, string Team, bool Dead);

internal static class TakeoverResolver
{
    public static string? Resolve(string humanId, IReadOnlyList<ControlSnapshot> live,
        string? pawnOwner, string? eventBotId)
    {
        var human = live.SingleOrDefault(p => p.Id == humanId);
        if (human is null || human.IsBot || !human.Dead) return null;
        // The real .2 trace shows PlayerPawn handles stay unchanged during
        // takeover: CS2 copies body state. OriginalControllerOfCurrentPawn is
        // the authoritative control link, not the initial physical pawn owner.
        var validBots = live.Where(bot => bot.IsBot && !bot.Dead && bot.Team == human.Team).ToList();
        var direct = validBots.SingleOrDefault(bot => bot.Id == human.Original);
        if (direct is not null) return direct.Id;
        var candidates = validBots.Where(bot =>
                // CS2 can swap the dead human pawn onto the bot controller.
                (bot.Original == humanId && bot.WasControlled)
                || bot.Id == eventBotId)
            .Select(bot => bot.Id).Distinct().ToList();
        return candidates.Count == 1 ? candidates[0] : null;
    }
}
