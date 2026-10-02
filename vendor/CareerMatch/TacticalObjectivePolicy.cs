namespace CareerMatch;

// Pure, map-independent decisions. All geometry comes from the live plant
// brush/NAV; no opponent coordinates and no hidden enemy state are consulted.
internal enum TacticalBombAction { Travel, Guard, NativeDefuse, Combat }
internal static class TacticalObjectivePolicy
{
    internal readonly record struct GuardPoint(float X, float Y, float Z)
    {
        internal float DistanceTo(GuardPoint other)
            => MathF.Sqrt((X-other.X)*(X-other.X) + (Y-other.Y)*(Y-other.Y));
    }
    // Guarding is NOT restricted to the planting brush. Select distinct nearby
    // NAV floors once at plant time; never read enemy positions to choose them.
    internal static bool GuardFloor(GuardPoint point, GuardPoint bomb)
        => float.IsFinite(point.X) && float.IsFinite(point.Y) && float.IsFinite(point.Z)
            && point.DistanceTo(bomb) <= 600 && MathF.Abs(point.Z-bomb.Z) <= 80;

    internal static GuardPoint? SelectGuard(GuardPoint current, GuardPoint bomb,
        IReadOnlyList<GuardPoint> candidates, IReadOnlyList<GuardPoint> occupied)
    {
        foreach (var spacing in new[] { 160f, 128f })
        {
            GuardPoint? selected = null;
            var best = float.PositiveInfinity;
            foreach (var point in candidates)
            {
                if (!GuardFloor(point, bomb) || point.DistanceTo(bomb) < 112) continue;
                var separation = occupied.Count == 0 ? 352 : occupied.Min(point.DistanceTo);
                if (separation < spacing) continue;
                var distance = point.DistanceTo(current);
                var cost = distance + .5f*MathF.Abs(point.DistanceTo(bomb)-256)
                    - .15f*MathF.Min(separation, 352) - (distance < 24 ? 160 : 0);
                if (cost >= best) continue;
                best = cost; selected = point;
            }
            if (selected is not null) return selected;
        }
        return null; // Narrow geometry: caller retains the validated native fallback.
    }

    internal static TacticalBombAction Decide(string side, bool atSite, bool nativeAction)
    {
        if (side is not ("t" or "ct")) throw new ArgumentOutOfRangeException(nameof(side));
        if (nativeAction) return TacticalBombAction.Combat;
        if (!atSite) return TacticalBombAction.Travel;
        return side == "t" ? TacticalBombAction.Guard : TacticalBombAction.NativeDefuse;
    }
    // A committed path retains a short opening suppression window. Failed/busy NAV
    // cannot retain an opening token forever, and an already airborne bot is
    // never teleported down or has its velocity overwritten.
    internal static bool OpeningGuardExpired(float now, float started, bool pathCommitted)
        => now-started >= 1.25f || pathCommitted && now-started >= .75f;
}
