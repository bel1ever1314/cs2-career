using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    // A damaged actor leaves this round's positional order, rather than being
    // pulled straight back into the same fire after a short combat cooldown.
    // ResetTacticalCommands clears this on round/map changes. Pawn + identity
    // checks prevent a reused slot from inheriting somebody else's handoff.
    private readonly Dictionary<int, (string Id, uint Pawn)> _tacticalSafetyHandoffs = [];

    private bool NativeSafetyOwnsActor(CCSPlayerController player) => player.IsValid
        && _tacticalSafetyHandoffs.TryGetValue(player.Slot, out var released)
        && ControllerId(player) == released.Id
        && player.PlayerPawn.Value is { IsValid: true } pawn && pawn.EntityHandle.Raw == released.Pawn;

    private void OnTacticalDamage(EventPlayerHurt ev)
    {
        // Self/fire/world/friendly damage matters too; do this before the
        // scoring handler filters out damage without an enemy attacker.
        if (ev.DmgHealth > 0 || ev.DmgArmor > 0)
            ReleaseTacticForDanger(ev.Userid, "damage");
    }

    private bool ReleaseTacticForDanger(CCSPlayerController? player, string reason)
    {
        if (!_roundLive || _resultWritten || !_setupDone || InWarmup()
            || _request is not { Active: true, Observer: false } || !string.IsNullOrEmpty(_contractError)
            || player is not { IsValid: true } || player.ControllingBot || player.HasBeenControlledByPlayerThisRound
            || player.PlayerPawn.Value is not { IsValid: true, Health: > 0, Bot: not null } pawn
            || ControllerId(player) is not { } id || id == _request.HumanPlayerId
            || _ledger.GetValueOrDefault(id)?.IsBot != true) return false;

        var slot = player.Slot; var body = pawn.EntityHandle.Raw;
        bool Owns(CommandPlan? plan, string actorId, uint actorPawn) => plan is not null
            && plan.MatchNonce == _sessionNonce && plan.Round == _tacticalEpoch && plan.Side == LiveSide(player)
            && actorId == id && actorPawn == body;
        var custom = _customTacticActors.GetValueOrDefault(slot);
        var postPlant = _postPlantActors.GetValueOrDefault(slot);
        var rush = _tacticalActors.GetValueOrDefault(slot);
        if (custom is not null && !Owns(_customTacticPlan, custom.Id, custom.Pawn)) custom = null;
        if (postPlant is not null && !Owns(_postPlantPlan, postPlant.Id, postPlant.Pawn)) postPlant = null;
        if (rush is not null && !Owns(_tacticalPlan, rush.Id, rush.Pawn)) rush = null;
        if (custom is null && postPlant is null && rush is null) return false;

        // Cancel the actor BEFORE releasing tokens, so the old wait/path can
        // never tick again. Other teammates and the round's plan stay intact.
        _tacticalSafetyHandoffs[slot] = (id, body);
        _tacticalReleases.Remove(slot);
        void Failed(Exception ex) => Logger.LogWarning(ex, "Tactical danger token release failed for {Slot}", slot);
        if (custom is not null)
        {
            _customTacticActors.Remove(slot);
            TacticalRadioRelease.All(Failed,
                () => ReleaseCustomJumpGuard(custom, reason), () => ReleaseCustomTravelGait(custom),
                () => ReleaseCustomLook(custom), () => custom.PathHold?.Release(), () => custom.Hold?.Release(),
                () => { custom.Continuation.Reset(); custom.DirectMove.Reset(); },
                () => ReleaseTacticalActor(new(custom.Id, slot, body,
                    [custom.Targets[Math.Min(custom.Clock.Stage, custom.Targets.Length - 1)]], Server.CurrentTime), "danger_handoff"));
        }
        if (postPlant is not null)
        {
            _postPlantActors.Remove(slot);
            TacticalRadioRelease.All(Failed, () => postPlant.Hold?.Release(), () => postPlant.PathHold?.Release(),
                () => postPlant.Path.Reset(), () => ReleaseTacticalActor(new(postPlant.Id, slot, body,
                    [postPlant.Target], Server.CurrentTime), "danger_handoff"));
        }
        if (rush is not null)
        { _tacticalActors.Remove(slot); ReleaseTacticalActor(rush, "danger_handoff"); }
        if (_openingGuards.Remove(slot, out var opening))
            TacticalRadioRelease.All(Failed, () => opening.Lease.Release());
        TacticalRadioRelease.All(Failed, () => ReleaseMotionClip(slot, reason), () => ReleaseCorner(slot, reason),
            () => ReleaseNatural(slot, reason), () => ReleaseNaturalRecovery(slot, reason), () => ReleaseNaturalJumpBlock(slot));
        _naturalTasks.Remove(slot); _naturalAssignments.Remove(slot); _naturalLaneAssignments.Remove(slot);
        _naturalLaneLockUntil.Remove(slot); _naturalStuckTicks.Remove(slot);
        TacticalTrace("danger_handoff", new { id, slot, reason, health = pawn.Health,
            stage = custom?.Clock.Stage, postPlant = postPlant is not null, owner = "native_ai" });
        return true;
    }
}
