namespace CareerMatch;

// This owns only a separate JUMP suppression token. It neither freezes movement
// nor changes native NAV/stuck state. Call Begin once for a NEW path cycle, not
// for each rate-limited retry or hurry renewal; terminal/native handoffs Release.
internal sealed class TacticalPathJumpGuard(ITacticalHoldApi api, int slot)
{
    internal const float GraceSeconds = .75f;
    internal const float MaximumPreparationSeconds = 4;
    private readonly TacticalHoldControls.OpeningLease _lease = new(api, slot);
    private double? _beganAt, _committedAt;

    internal bool Active => _lease.Active;
    internal bool Preparing => Active && _committedAt is null;

    internal void Begin(float now)
    {
        ValidateTime(now);
        try
        {
            // Reuse our token across rapid successive waypoints. Begin is an
            // explicit new cycle: the caller must not repeat it during retries.
            _lease.Start();
            _beganAt = now; _committedAt = null;
        }
        catch { Release(); throw; }
    }

    internal void Committed(float now)
    {
        ValidateTime(now);
        if (!Active || _committedAt is not null) return;
        // A caller missing the pending timeout cannot resurrect an expired
        // preparation token. DirectMove normally rejects earlier, at 3 seconds.
        if (_beganAt is not { } began || (double)now-began >= MaximumPreparationSeconds)
        { Release(); return; }
        _committedAt = now;
    }

    internal void Tick(float now)
    {
        ValidateTime(now);
        if (!Active) return;
        if (_committedAt is { } committed)
        {
            if ((double)now-committed >= GraceSeconds) Release();
        }
        else if (_beganAt is not { } began || (double)now-began >= MaximumPreparationSeconds) Release();
    }

    internal float Remaining(float now)
    {
        ValidateTime(now);
        if (!Active || _beganAt is not { } began) return 0;
        var limit = _committedAt is not null ? GraceSeconds : MaximumPreparationSeconds;
        return (float)Math.Clamp(limit-((double)now-(_committedAt ?? began)), 0, limit);
    }

    internal void Release()
    {
        // Clear the cycle before native cancellation, including error paths.
        // OpeningLease deletes only this token and makes release idempotent.
        _beganAt = _committedAt = null;
        _lease.Release();
    }

    private static void ValidateTime(float now)
    {
        if (!float.IsFinite(now)) throw new ArgumentOutOfRangeException(nameof(now));
    }
}
