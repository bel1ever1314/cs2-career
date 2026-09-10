namespace CareerMatch;

internal sealed record TeamMembership(string Id, string OpeningSide, int CurrentSide);

internal static class TeamScoreMapping
{
    public static int LiveRoundIndex(int ct, int t) => Math.Max(0, ct) + Math.Max(0, t) + 1;
    // CT/T in the result contract mean OPENING roster sides, not the current
    // in-game side. Use stable roster membership, not a halftime round formula
    // (which breaks with overtime, restarts and custom rules).
    public static int? OpeningCtCurrentSide(IReadOnlyList<TeamMembership> players)
    {
        if (players.Count != 10 || players.Select(p => p.Id).Distinct().Count() != 10) return null;
        var ct = players.Where(p => p.OpeningSide == "ct").ToList();
        var t = players.Where(p => p.OpeningSide == "t").ToList();
        if (ct.Count != 5 || t.Count != 5) return null;
        var a = ct.Select(p => p.CurrentSide).Distinct().ToList();
        var b = t.Select(p => p.CurrentSide).Distinct().ToList();
        return a.Count == 1 && b.Count == 1 && a[0] is 2 or 3 && b[0] == 5-a[0] ? a[0] : null;
    }
    public static (int Ct, int T) Normalize(int liveCt, int liveT, int openingCtSide) =>
        openingCtSide == 2 ? (liveT, liveCt) : (liveCt, liveT);
}
