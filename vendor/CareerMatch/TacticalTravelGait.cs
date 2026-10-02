namespace CareerMatch;

internal interface ITacticalTravelApi : ITacticalHoldApi
{
    long Inject(int slot, ulong mask, int durationMs);
    int CancelInjection(int slot, long token);
}

// Own only SPEED, never direction, stance, jumping, firing, aim or native AI
// state. The caller must verify actor ownership and native/hold handoffs first.
internal sealed class TacticalTravelGait(ITacticalTravelApi api, int slot, TimeProvider? clock = null)
{
    internal const ulong SpeedMask = 1UL << 16;
    internal const int WalkDurationMs = 500;
    internal const double RenewSeconds = .25;
    private readonly TimeProvider _clock = clock ?? TimeProvider.System;
    private long _suppression, _injection;
    private double? _gameRenewedAt;
    private long? _wallRenewedAt;

    // Local ownership is not a claim that a finite native token is unexpired.
    internal bool Active => _suppression > 0 || _injection > 0;
    internal string Mode { get; private set; } = "";

    internal void Keep(string mode, float now)
    {
        if (mode is not ("run" or "walk")) throw new ArgumentException("travel_gait_mode_invalid", nameof(mode));
        if (!float.IsFinite(now)) throw new ArgumentOutOfRangeException(nameof(now));
        if (mode != Mode) Release(); // Never overlap opposite gait preferences.
        try
        {
            if (mode == "run")
            {
                if (_suppression > 0) return;
                var token = api.Suppress(slot, SpeedMask);
                if (token <= 0) throw new InvalidOperationException("travel_gait_suppression_rejected");
                _suppression = token; Mode = mode;
                return;
            }
            var timestamp = _clock.GetTimestamp();
            if (_injection > 0 && _gameRenewedAt is { } game && _wallRenewedAt is { } wall)
            {
                var gameElapsed = (double)now-game;
                var wallElapsed = _clock.GetElapsedTime(wall, timestamp).TotalSeconds;
                // Native injection expires on steady_clock, not game time.
                // A pause/slow frame must renew on its first resumed Keep even
                // when the game's clock has barely advanced or moved backward.
                if (gameElapsed >= 0 && gameElapsed < RenewSeconds
                    && wallElapsed >= 0 && wallElapsed < RenewSeconds) return;
            }
            var next = api.Inject(slot, SpeedMask, WalkDurationMs);
            if (next <= 0) throw new InvalidOperationException("travel_gait_injection_rejected");
            var previous = _injection;
            _injection = next; _gameRenewedAt = now; _wallRenewedAt = timestamp; Mode = mode;
            // Renew first, then remove only our old token: no expiry gap or
            // accumulated injection handles, even across rapid mode changes.
            if (previous > 0) CancelInjection(previous);
        }
        catch (Exception operation)
        {
            try { Release(); }
            catch (Exception cleanup)
            { throw new AggregateException("travel_gait_failure_cleanup_unconfirmed", operation, cleanup); }
            throw;
        }
    }

    internal void Release()
    {
        var suppression = _suppression; var injection = _injection;
        _suppression = _injection = 0; _gameRenewedAt = null; _wallRenewedAt = null; Mode = "";
        Exception? suppressionFailure = null;
        try
        {
            if (suppression > 0 && api.CancelSuppression(slot, suppression) != 0)
                throw new InvalidOperationException("travel_gait_suppression_cancel_rejected");
        }
        catch (Exception ex) { suppressionFailure = ex; }
        try { if (injection > 0) CancelInjection(injection); }
        catch (Exception ex)
        {
            if (suppressionFailure is not null)
                throw new AggregateException("travel_gait_release_unconfirmed", suppressionFailure, ex);
            throw;
        }
        if (suppressionFailure is not null) throw suppressionFailure;
    }

    private void CancelInjection(long token)
    {
        // Injection contract: -1 means this valid slot/token entry does not
        // exist (expired or cleared). The native adapter must verify that ABI;
        // unknown results are not success.
        var result = api.CancelInjection(slot, token);
        if (result is not (0 or -1))
            throw new InvalidOperationException("travel_gait_injection_cancel_rejected:" + result);
    }
}
