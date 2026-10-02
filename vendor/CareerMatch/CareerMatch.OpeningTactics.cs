using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    private sealed class OpeningGuard(string id, int slot, uint pawn, TacticalHoldControls.OpeningLease lease)
    {
        internal readonly string Id = id;
        internal readonly int Slot = slot;
        internal readonly uint Pawn = pawn;
        internal readonly TacticalHoldControls.OpeningLease Lease = lease;
        internal float? Launched;
        internal bool PathCommitted;
    }
    private readonly Dictionary<int, OpeningGuard> _openingGuards = [];

    private void EnsureTacticalHold()
    {
        if (_customHold is null && !TacticalHoldControls.TryBind(Path.GetFullPath(Path.Combine(ModuleDirectory,
                "../../../BotController/bin/win64/BotController.dll")), out _customHold, out _customHoldState))
            throw new InvalidDataException("到点保位接口未就绪：" + _customHoldState);
    }

    private void PrepareOpeningGuards(CommandPlan plan)
    {
        EnsureTacticalHold();
        var actors = AllSlots().Where(p => ControllerId(p) is { } id && id != plan.IssuerId
            && _ledger.GetValueOrDefault(id)?.IsBot == true && LiveSide(p) == plan.Side
            && !p.ControllingBot && !p.HasBeenControlledByPlayerThisRound
            && p.PlayerPawn.Value is { IsValid: true, Health: > 0, Bot: not null }).ToArray();
        if (plan.Order == TacticalOrder.Playbook)
        {
            var slots = PrepareCustomTactic(plan).Select(a => a.Slot).ToHashSet();
            actors = actors.Where(p => slots.Contains(p.Slot)).ToArray();
        }
        // Stage the entire replacement before releasing the old tokens. A bad
        // new order does not quietly cancel the previously accepted command.
        var staged = new List<OpeningGuard>();
        try
        {
            foreach (var p in actors)
            {
                var guard = new OpeningGuard(ControllerId(p)!, p.Slot,
                    p.PlayerPawn.Value!.EntityHandle.Raw, _customHold!.CreateOpeningLease(p.Slot));
                staged.Add(guard); guard.Lease.Start();
            }
        }
        catch { foreach (var guard in staged) guard.Lease.Release(); throw; }
        ReleaseOpeningGuards();
        foreach (var guard in staged) _openingGuards.Add(guard.Slot, guard);
        TacticalTrace("opening_jump_suppressed", new { slots = staged.Select(g => g.Slot), pending = true });
    }

    private void LaunchOpeningGuards()
    {
        foreach (var guard in _openingGuards.Values) guard.Launched = Server.CurrentTime;
    }
    private void OpeningPathCommitted(int slot)
    {
        if (_openingGuards.TryGetValue(slot, out var guard)) guard.PathCommitted = true;
    }
    private void ReleaseOpeningGuards()
    {
        foreach (var guard in _openingGuards.Values)
            try { guard.Lease.Release(); }
            catch (Exception ex) { Logger.LogWarning(ex, "Opening token release failed for {Slot}", guard.Slot); }
        _openingGuards.Clear();
    }
    private void TickOpeningGuards()
    {
        foreach (var guard in _openingGuards.Values.ToArray())
        {
            var p = Utilities.GetPlayerFromSlot(guard.Slot);
            if (_resultWritten || !_setupDone || InWarmup() || p is not { IsValid: true }
                || ControllerId(p) != guard.Id || p.ControllingBot || p.HasBeenControlledByPlayerThisRound
                || p.PlayerPawn.Value is not { IsValid: true, Health: > 0 } pawn || pawn.EntityHandle.Raw != guard.Pawn
                || guard.Launched is { } started && TacticalObjectivePolicy.OpeningGuardExpired(
                    Server.CurrentTime, started, guard.PathCommitted))
            {
                guard.Lease.Release(); _openingGuards.Remove(guard.Slot);
            }
        }
    }
}
