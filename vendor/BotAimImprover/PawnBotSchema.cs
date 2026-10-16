namespace BotAimImprover;

internal static class PawnBotSchema
{
    internal static int Resolve(Func<string, string, short> schemaOffset)
    {
        int offset = schemaOffset("CCSPlayerPawn", "m_pBot");
        if (offset <= 0)
            throw new InvalidOperationException("CCSPlayerPawn::m_pBot schema field is unavailable; aim hook not installed.");
        return offset;
    }
}
