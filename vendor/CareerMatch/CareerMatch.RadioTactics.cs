using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Commands;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    private readonly TacticalRadioPolicy _tacticalRadio = new();

    private void LoadTacticalRadio()
    {
        foreach (var name in TacticalRadioPolicy.Commands)
        {
            AddCommandListener(name, OnTacticalRadioCommand, HookMode.Pre);
            AddCommandListener(name, OnTacticalRadioCommandFinished, HookMode.Post);
        }
        RegisterEventHandler<EventPlayerRadio>(OnTacticalPlayerRadio, HookMode.Pre);
        // CSS event_manager.cpp: Pre callbacks precede native FireEvent listeners.
        // CS2 2000924 server.dll SHA256 098D4DDD57E2FBE9A73623A2BF68EBAFF86F7B6342DDB3D5A0F69CD6335B31CC:
        // command dispatcher synchronously emits player_radio AFTER cooldown
        // acceptance, BEFORE returning (radio groups / takepoint / coverme).
        // Thus event Pre releases our input BEFORE upstream/native radio acts.
        // Never replay/block the radio or retain a candidate after Command Post.
    }

    private TacticalRadioSpeaker RadioSpeaker(CCSPlayerController? player)
    {
        var id = ControllerId(player) ?? "";
        var pawn = player is { IsValid: true } ? player.PlayerPawn.Value : null;
        return new(new TacticalCommandContext
        {
            MatchNonce = _sessionNonce, Round = _tacticalEpoch, SpeakerId = id,
            Side = player is { IsValid: true } ? LiveSide(player) : "",
            AuthorizedMatch = _setupDone && _request is { Active: true } && string.IsNullOrEmpty(_contractError),
            AuthorizedHuman = id.Length > 0 && id == _request?.HumanPlayerId,
            SpeakerValid = player is { IsValid: true, IsHLTV: false },
            SpeakerIsBot = _ledger.GetValueOrDefault(id)?.IsBot ?? true,
            Observer = _request?.Observer ?? true, Warmup = InWarmup(), MatchCompleted = _resultWritten,
        }, player?.Slot ?? -1, pawn is { IsValid: true } ? pawn.EntityHandle.Raw : 0,
            Server.TickCount, pawn is { IsValid: true, Health: > 0 }, _roundLive,
            player is { IsValid: true } && (player.ControllingBot || player.HasBeenControlledByPlayerThisRound));
    }

    private HookResult OnTacticalRadioCommand(CCSPlayerController? player, CommandInfo command)
    {
        _tacticalRadio.BeginCommand(command.GetArg(0), RadioSpeaker(player));
        return HookResult.Continue;
    }

    private HookResult OnTacticalRadioCommandFinished(CCSPlayerController? player, CommandInfo command)
    {
        _tacticalRadio.EndCommand(command.GetArg(0), player?.Slot ?? -1);
        return HookResult.Continue;
    }

    private HookResult OnTacticalPlayerRadio(EventPlayerRadio ev, GameEventInfo info)
    {
        var player = ev.Userid;
        // Most radio events are native Bot chatter. Do not enumerate the roster
        // or query game rules for those, ordinary reports or unbound clients.
        if (!_tacticalRadio.HasPendingCommand || ControllerId(player) is not { } id || id != _request?.HumanPlayerId
            || _ledger.GetValueOrDefault(id)?.IsBot != false) return HookResult.Continue;
        var speaker = RadioSpeaker(player);
        var players = AllSlots().Where(p => p.IsValid).ToArray();
        var candidates = players.Select(p => new TacticalBotCandidate(ControllerId(p) ?? "", LiveSide(p),
            _ledger.GetValueOrDefault(ControllerId(p) ?? "")?.IsBot == true, p.IsValid,
            p.PlayerPawn.Value is { IsValid: true, Health: > 0, Bot: not null },
            p.ControllingBot || p.HasBeenControlledByPlayerThisRound));
        if (_tacticalRadio.Confirm(speaker, ev.Slot, candidates) is { } handoff)
            ReleaseForPlayerRadio(handoff, players);
        return HookResult.Continue;
    }

    private bool NativeRadioOwnsActor(CCSPlayerController player) => ControllerId(player) is { } id
        && _tacticalRadio.Owns(_sessionNonce, _tacticalEpoch, LiveSide(player), id);

    private void ReleaseForPlayerRadio(TacticalRadioHandoff handoff, CCSPlayerController[] players)
    {
        // Active actors can now be dead/disconnected: cancel their OWN tokens
        // too, without touching an opponent or applying input to a reused pawn.
        var ids = handoff.Recipients.ToHashSet(StringComparer.Ordinal);
        bool Same(CommandPlan? plan) => TacticalRadioPolicy.SameScope(plan, handoff);
        if (Same(_tacticalPlan)) foreach (var a in _tacticalActors.Values) ids.Add(a.Id);
        if (Same(_customTacticPlan)) foreach (var a in _customTacticActors.Values) ids.Add(a.Id);
        if (Same(_postPlantPlan)) foreach (var a in _postPlantActors.Values) ids.Add(a.Id);
        var cancelledIntent = Same(_tacticalRoundIntent) || Same(_tacticalQueue.Pending)
            || Same(_tacticalPlan) || Same(_customTacticPlan) || Same(_postPlantPlan);
        if (Same(_tacticalQueue.Pending)) _tacticalQueue.Reset();
        if (Same(_tacticalRoundIntent)) _tacticalRoundIntent = null;
        if (Same(_tacticalPlan)) _tacticalPlan = null;
        if (Same(_customTacticPlan)) _customTacticPlan = null;
        if (Same(_postPlantPlan)) { _postPlantPlan = null; _postPlantState = "stopped:player_radio"; }
        if (cancelledIntent) ClearCustomSlots();
        // Pending deferred Idle must never run AFTER the native radio sets its
        // new task, even if it happens to reuse an old tactical goal position.
        foreach (var release in _tacticalReleases.Values.Where(r => ids.Contains(r.Id)).ToArray())
            _tacticalReleases.Remove(release.Slot);
        void Failed(Exception ex) => Logger.LogWarning(ex, "Player radio token release failed; old actor remains cancelled");
        foreach (var actor in _customTacticActors.Values.Where(a => ids.Contains(a.Id)).ToArray())
        {
            _customTacticActors.Remove(actor.Slot); // Cancel its 20s clock immediately; no wait/timer can tick again.
            TacticalRadioRelease.All(Failed,
                () => ReleaseCustomJumpGuard(actor, "player_radio"),
                () => ReleaseCustomTravelGait(actor), () => ReleaseCustomLook(actor),
                () => actor.PathHold?.Release(), () => actor.Hold?.Release(),
                () => { actor.Continuation.Reset(); actor.DirectMove.Reset(); },
                () => ReleaseTacticalActor(new(actor.Id, actor.Slot, actor.Pawn,
                    [actor.Targets[Math.Min(actor.Clock.Stage, actor.Targets.Length - 1)]], Server.CurrentTime), "player_radio"));
        }
        foreach (var actor in _postPlantActors.Values.Where(a => ids.Contains(a.Id)).ToArray())
        {
            _postPlantActors.Remove(actor.Slot);
            TacticalRadioRelease.All(Failed, () => actor.Hold?.Release(), () => actor.PathHold?.Release(),
                () => actor.Path.Reset(), () => ReleaseTacticalActor(new(actor.Id, actor.Slot, actor.Pawn,
                    [actor.Target], Server.CurrentTime), "player_radio"));
        }
        foreach (var actor in _tacticalActors.Values.Where(a => ids.Contains(a.Id)).ToArray())
        { _tacticalActors.Remove(actor.Slot); ReleaseTacticalActor(actor, "player_radio"); }
        foreach (var guard in _openingGuards.Values.Where(g => ids.Contains(g.Id)).ToArray())
        { _openingGuards.Remove(guard.Slot); TacticalRadioRelease.All(Failed, () => guard.Lease.Release()); }
        foreach (var player in players.Where(p => ControllerId(p) is { } id && ids.Contains(id)
            && _ledger.GetValueOrDefault(id)?.IsBot == true && LiveSide(p) == handoff.Side))
        {
            var slot = player.Slot;
            TacticalRadioRelease.All(Failed, () => ReleaseMotionClip(slot, "player_radio"),
                () => ReleaseCorner(slot, "player_radio"), () => ReleaseNatural(slot, "player_radio"),
                () => ReleaseNaturalRecovery(slot, "player_radio"), () => ReleaseNaturalJumpBlock(slot));
            _naturalTasks.Remove(slot); _naturalAssignments.Remove(slot); _naturalLaneAssignments.Remove(slot);
            _naturalLaneLockUntil.Remove(slot); _naturalStuckTicks.Remove(slot);
        }
        TacticalTrace("radio_handoff", new { handoff.Command, handoff.RadioSlot, handoff.Side,
            handoff.IssuerId, bots = handoff.Recipients, cancelledIntent, revision = _tacticalRadio.Revision });
    }
}
