namespace CareerMatch;

// A zero-second waypoint is crossed before the successor is requested. While
// native NAV is rate-limited, retain the OLD owned goal/path and keep walking;
// never claim the successor is ready, install a zero-input hold, or skip a wait.
internal sealed class TacticalContinuousMove
{
    private float? _began;
    private float _nextAttempt;
    internal void Reset() { _began = null; _nextAttempt = 0; }
    internal TacticalPathAction Tick(float now, TacticalMoveCall commit, out string reason)
    {
        if (!float.IsFinite(now)) throw new ArgumentOutOfRangeException(nameof(now));
        _began ??= now;
        if (now - _began > TacticalDirectMove.MaximumPreparation)
        { reason = "custom_successor_path_timeout"; return TacticalPathAction.Failed; }
        if (now < _nextAttempt)
        { reason = "navigation_path_rate_limited"; return TacticalPathAction.Pending; }
        _nextAttempt = now + .125f;
        if (commit(out reason)) { Reset(); return TacticalPathAction.Moving; }
        if (reason == "navigation_path_rate_limited") return TacticalPathAction.Pending;
        if (reason == "native_combat_or_objective_retained")
        { Reset(); return TacticalPathAction.Yielded; }
        return TacticalPathAction.Failed;
    }
}
