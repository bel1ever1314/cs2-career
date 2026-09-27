namespace CareerMatch;

// Shared by the isolated control lab and the future local-actions owner. This
// type has no engine dependency: failed acquisition/release is regression-tested.
internal interface ILocalControlApi
{
    int IsLocked(int slot, int kind);
    int Lock(int slot, int kind, int argument);
    int Unlock(int slot, int kind);
    long StartMove(int slot, float forward, float left);
    int UpdateMove(int slot, long token, float forward, float left);
    int CancelMove(int slot, long token);
    long Suppress(int slot, ulong mask);
    int CancelSuppression(int slot, long token);
}

internal sealed class LocalControlLease(ILocalControlApi api, int slot, bool suspendDecisions = false)
{
    private long _movement, _suppression;
    private bool _aim, _weapon, _decisions, _released;
    internal bool Acquired { get; private set; }
    internal bool Released => _released;
    internal List<string> CleanupErrors { get; } = [];

    internal void Acquire()
    {
        if (_released || Acquired) throw new InvalidOperationException("lease_not_fresh");
        if (slot is < 0 or >= 64) throw new ArgumentOutOfRangeException(nameof(slot));
        if (Enumerable.Range(0, 3).Any(kind => api.IsLocked(slot, kind) != 0))
            throw new InvalidOperationException("another_owner");
        try
        {
            // Aim-only leaves CCSBot::Update running. The isolated control lab
            // suspends that decision producer for this one slot, not all bots.
            if (suspendDecisions)
            {
                if (api.Lock(slot, 0, 0) != 0) throw new InvalidOperationException("decision_acquire_failed");
                _decisions = true;
                if (api.IsLocked(slot, 0) != 1) throw new InvalidOperationException("decision_lock_not_observed");
            }
            if (api.Lock(slot, 1, 0) != 0) throw new InvalidOperationException("aim_acquire_failed");
            _aim = true;
            _movement = api.StartMove(slot, 0, 0);
            if (_movement <= 0) throw new InvalidOperationException("movement_acquire_failed");
            // Only the lab's own suppression; native random jumps cannot spoil
            // a flat-ground control measurement. Never cancel somebody else's token.
            _suppression = api.Suppress(slot, (1UL << 1) | (1UL << 2) | (1UL << 16));
            if (_suppression <= 0) throw new InvalidOperationException("suppression_acquire_failed");
            Acquired = true;
        }
        catch { Release(); throw; }
    }

    internal void Move(float forward, float left)
    {
        if (!Acquired || _released || !float.IsFinite(forward) || !float.IsFinite(left))
            throw new InvalidOperationException("invalid_movement_state");
        if (_decisions && api.IsLocked(slot, 0) != 1) throw new InvalidOperationException("decision_ownership_lost");
        if (api.UpdateMove(slot, _movement, Math.Clamp(forward, -1, 1), Math.Clamp(left, -1, 1)) != 0)
            throw new InvalidOperationException("movement_update_failed");
    }

    internal void SelectWeaponSlot(int slotNumber)
    {
        if (!Acquired || _released || slotNumber is < 1 or > 3)
            throw new InvalidOperationException("invalid_weapon_state");
        if (!_weapon && api.IsLocked(slot, 2) != 0) throw new InvalidOperationException("weapon_already_owned");
        if (api.Lock(slot, 2, slotNumber) != 0) throw new InvalidOperationException("weapon_lock_failed");
        _weapon = true; // A request, NOT proof the active weapon actually changed.
    }

    internal void Release()
    {
        if (_released) return;
        _released = true;
        Acquired = false;
        void Attempt(string name, Func<int> call)
        {
            try { if (call() != 0) CleanupErrors.Add(name + ":rejected"); }
            catch (Exception ex) { CleanupErrors.Add(name + ":" + ex.GetType().Name); }
        }
        if (_movement > 0) Attempt("movement", () => api.CancelMove(slot, _movement));
        if (_suppression > 0) Attempt("suppression", () => api.CancelSuppression(slot, _suppression));
        if (_weapon) Attempt("weapon", () => api.Unlock(slot, 2));
        if (_aim) Attempt("aim", () => api.Unlock(slot, 1));
        // Resume native decisions only after releasing our input and view owners.
        if (_decisions) Attempt("decisions", () => api.Unlock(slot, 0));
        // Do not claim success just because cancellation returned without throwing.
        if (_weapon) Attempt("weapon_unlocked", () => api.IsLocked(slot, 2));
        if (_aim) Attempt("aim_unlocked", () => api.IsLocked(slot, 1));
        if (_decisions) Attempt("decisions_unlocked", () => api.IsLocked(slot, 0));
        _movement = _suppression = 0;
        _aim = _weapon = _decisions = false;
    }
}
