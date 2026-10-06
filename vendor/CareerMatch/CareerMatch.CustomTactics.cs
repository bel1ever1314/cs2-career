using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    private sealed class CustomTacticActor(string id, int slot, int rosterSlot, uint pawn,
        TacticalTarget[] targets, CustomTacticSlot source, string side, int health, float now)
    {
        internal readonly string Id = id;
        internal readonly int Slot = slot, RosterSlot = rosterSlot;
        internal readonly uint Pawn = pawn;
        internal readonly TacticalTarget[] Targets = targets;
        internal readonly TacticalStepClock Clock = new(source.Steps.Select(s => s.Wait).ToArray(),
            TacticalFinishPolicy.HoldFinal(source.Finish, side));
        internal readonly CustomTacticSlot Source = source;
        internal readonly TacticalTravelProgress Travel = new();
        internal readonly TacticalDirectMove DirectMove = new();
        internal readonly TacticalContinuousMove Continuation = new();
        internal TacticalTravelGait? Gait;
        internal TacticalHoldControls.Lease? Hold;
        internal TacticalHoldControls.Lease? PathHold;
        internal TacticalPathJumpGuard? JumpGuard;
        internal bool? LastGrounded;
        internal TacticalNativeLook.Lease? Look;
        internal float NextLookAttempt;
        internal string LookState = "inactive";
        internal int Health = health;
        internal float YieldUntil, NextMove, LastProgress = now, BestDistance = float.MaxValue;
        internal float NextDiagnostic = now + 3;
        internal float? OtherOwnerSince;
        internal string State = "queued";
    }
    private TacticalPlaybook? _customPlaybook;
    private string _customPlaybookState = "not_loaded", _customHoldState = "not_bound";
    private TacticalHoldControls? _customHold;
    private TacticalNativeLook? _tacticalLook;
    private string _tacticalLookState = "not_bound";
    private CommandPlan? _customTacticPlan;
    private readonly Dictionary<int, CustomTacticActor> _customTacticActors = [];

    private void LoadCustomPlaybook(string? mapName = null)
    {
        // Reload at map boundaries, never halfway through an accepted plan.
        // Names/IDs are local to this map, not a global tactic namespace.
        _customPlaybook = null;
        try
        {
            _customPlaybook = TacticalPlaybook.ReadForMap(ModuleDirectory, mapName ?? Server.MapName);
            _customPlaybookState = $"{_customPlaybook.Map}:{_customPlaybook.Tactics.Count}";
            Logger.LogInformation("Custom tactical playbook loaded: {State}; direction={Direction}",
                _customPlaybookState, _tacticalLookState);
        }
        catch (Exception ex)
        {
            _customPlaybook = null; _customPlaybookState = "rejected:" + ex.Message;
            Logger.LogWarning("Custom tactical playbook rejected: {Error}", ex.Message);
        }
    }

    private CustomTacticActor[] PrepareCustomTactic(CommandPlan plan)
    {
        if (_customPlaybook is null)
            throw new InvalidDataException($"本地战术库未就绪：{_customPlaybookState}");
        if (!TacticalMapCatalog.Matches(_customPlaybook.Map, Server.MapName)
            || _request is null || !TacticalMapCatalog.Matches(_customPlaybook.Map, _request.Map))
            throw new InvalidDataException($"地图未对齐：游戏 {Server.MapName}，对局 {_request?.Map ?? "未载入"}，战术库 {_customPlaybook.Map}。退出 CS2 后同步当前对局战术；无需改战术名");
        var tactic = _customPlaybook.Tactics.FirstOrDefault(t => t.Id == plan.TacticId)
            ?? throw new InvalidDataException($"{_customPlaybook.Map} 没有战术 {plan.TacticId}。请同步此地图的战术库");
        if (tactic.Side != plan.Side) throw new InvalidDataException("战术阵营与当前 T/CT 不一致");
        if (_request is null) throw new InvalidDataException("本场名单未就绪");
        // The original career team keeps its five request slots after halftime.
        var players = AllSlots().Where(p => p.IsValid).ToArray();
        var candidates = players.Select(p => new TacticalBotCandidate(ControllerId(p) ?? "", LiveSide(p),
            _ledger.GetValueOrDefault(ControllerId(p) ?? "")?.IsBot == true, p.IsValid,
            p.PlayerPawn.Value is { IsValid: true, Health: > 0, Bot: not null },
            p.ControllingBot || p.HasBeenControlledByPlayerThisRound)).ToArray();
        var eligible = candidates.Where(c => c.IsBot && c.IsValid && c.Alive && !c.HumanControlled
            && c.Id != plan.IssuerId && c.Side == plan.Side).Select(c => c.Id).ToHashSet(StringComparer.Ordinal);
        var bindings = ResolveCustomSlots(plan, tactic).Where(b => b.Route.Steps.Count > 0 && eligible.Contains(b.PlayerId)).ToArray();
        if (bindings.Length == 0) throw new InvalidDataException("有路线的名单槽当前没有可指挥 Bot");
        // Even a zero-wait route needs a brief movement lease while the native
        // path timer is busy. It must not follow an old path during preparation.
        EnsureTacticalHold();
        if (bindings.Any(b => b.Route.Steps.Select((p, i) => p.LookAt is not null
            && (p.Wait > 0 || (i == b.Route.Steps.Count - 1 && TacticalFinishPolicy.HoldFinal(b.Route.Finish, plan.Side)))).Any(v => v))
            && _tacticalLook is null)
            throw new InvalidDataException("观察朝向接口未就绪：" + _tacticalLookState);
        var areas = CCSNavArea.GetAllNavAreas();
        if (areas.Count == 0) throw new InvalidDataException("地图导航未加载");
        var actors = new List<CustomTacticActor>();
        foreach (var binding in bindings)
        {
            var matches = players.Where(p => ControllerId(p) == binding.PlayerId).ToArray();
            if (matches.Length != 1) throw new InvalidDataException("名单身份重复或未绑定");
            var player = matches[0]; var pawn = player.PlayerPawn.Value!;
            var previousZ = pawn.AbsOrigin?.Z ?? throw new InvalidDataException("Bot 起点未就绪");
            var targets = new List<TacticalTarget>();
            foreach (var step in binding.Route.Steps)
            {
                var x = step.Position[0]; var y = step.Position[1];
                var candidatesNav = new List<TacticNavPoint>();
                foreach (var area in areas)
                {
                    var min = area.Min; var max = area.Max;
                    if (x < min.X - TacticalNavProjection.MaximumSnap || x > max.X + TacticalNavProjection.MaximumSnap
                        || y < min.Y - TacticalNavProjection.MaximumSnap || y > max.Y + TacticalNavProjection.MaximumSnap) continue;
                    var snapped = area.GetClosestPoint(new Vector(x, y, area.Center.Z));
                    if (!TacticalMapCatalog.IsLevelAllowed(_customPlaybook.Map, step.Level, snapped.Z)) continue;
                    candidatesNav.Add(new(area.Id, snapped.X, snapped.Y, snapped.Z));
                }
                if (candidatesNav.Count == 0 && step.Level is "upper" or "lower")
                    throw new InvalidDataException("当前点没有所选楼层的可行走导航面");
                var point = TacticalNavProjection.Select(x, y, step.Level, previousZ, candidatesNav);
                previousZ = point.Z;
                targets.Add(new(point.X, point.Y, point.Z, 40, false));
            }
            actors.Add(new(binding.PlayerId, player.Slot, binding.TacticSlot, pawn.EntityHandle.Raw,
                targets.ToArray(), binding.Route, plan.Side, pawn.Health, Server.CurrentTime));
        }
        return actors.ToArray();
    }

    private void StartCustomTactic(CommandPlan plan, CCSPlayerController human)
    {
        try
        {
            var prepared = PrepareCustomTactic(plan); // Validate every bot route atomically.
            _customTacticPlan = plan;
            foreach (var actor in prepared)
            {
                _tacticalReleases.Remove(actor.Slot);
                ReleaseMotionClip(actor.Slot, "custom_tactic"); ReleaseCorner(actor.Slot, "custom_tactic");
                ReleaseNatural(actor.Slot, "custom_tactic"); ReleaseNaturalRecovery(actor.Slot, "custom_tactic");
                ReleaseNaturalJumpBlock(actor.Slot);
                _customTacticActors.Add(actor.Slot, actor);
            }
            TacticalTrace("custom_started", new { plan.TacticId, plan.Side,
                direction = _tacticalLookState,
                actors = prepared.Select(a => new { a.Id, a.Slot, a.RosterSlot, a.Targets,
                    finish = a.Source.Finish, holdFinal = TacticalFinishPolicy.HoldFinal(a.Source.Finish, plan.Side) }) });
        }
        catch (Exception ex)
        {
            StopCustomTactic("start_failed");
            human.PrintToChat($" \x02自定义战术未启动：{ex.Message}\x01");
        }
    }

    private void ReleaseCustomTacticActor(CustomTacticActor actor, string reason, TacticalTarget? target = null,
        bool preserveJumpGuard = false)
    {
        if (!preserveJumpGuard) ReleaseCustomJumpGuard(actor, reason);
        ReleaseCustomTravelGait(actor);
        actor.Continuation.Reset();
        ReleaseCustomLook(actor);
        try { actor.PathHold?.Release(); }
        catch (Exception ex) { Logger.LogError(ex, "Custom tactic preparation release failed for {Slot}", actor.Slot); }
        actor.PathHold = null; actor.DirectMove.Reset();
        try { actor.Hold?.Release(); }
        catch (Exception ex) { Logger.LogError(ex, "Custom tactic hold release failed for {Slot}", actor.Slot); }
        actor.Hold = null;
        target ??= actor.Targets[Math.Min(actor.Clock.Stage, actor.Targets.Length - 1)];
        // Reuse the existing audited cancellation and deferred combat-safe release.
        ReleaseTacticalActor(new(actor.Id, actor.Slot, actor.Pawn, [target], Server.CurrentTime), reason);
    }
    private void StopCustomTactic(string reason)
    {
        foreach (var actor in _customTacticActors.Values) ReleaseCustomTacticActor(actor, reason);
        if (_customTacticPlan is not null) TacticalTrace("custom_stopped", new { reason, _customTacticPlan.TacticId });
        _customTacticActors.Clear(); _customTacticPlan = null;
        if (reason == "start_failed") ReleaseOpeningGuards();
    }

    private void ReleaseCustomLook(CustomTacticActor actor)
    {
        try { actor.Look?.Release(); }
        finally { actor.Look = null; }
    }

    private void ReleaseCustomTravelGait(CustomTacticActor actor)
    {
        try { actor.Gait?.Release(); }
        catch (Exception ex) { Logger.LogWarning(ex, "Custom travel gait release failed for {Slot}", actor.Slot); }
        actor.Gait = null;
    }

    private void KeepCustomTravelGait(CustomTacticActor actor)
    {
        var movement = actor.Source.Steps[actor.Clock.Stage].Movement;
        actor.Gait ??= new TacticalTravelGait(_customHold!, actor.Slot);
        var changed = actor.Gait.Mode != movement;
        actor.Gait.Keep(movement, Server.CurrentTime);
        if (changed) TacticalTrace("custom_travel_gait", new { actor.Id, stage = actor.Clock.Stage, movement });
    }

    private void BeginCustomJumpGuard(CustomTacticActor actor, string reason)
    {
        actor.JumpGuard ??= new TacticalPathJumpGuard(_customHold!, actor.Slot);
        actor.JumpGuard.Begin(Server.CurrentTime);
        TacticalTrace("custom_jump_handoff_begin", new { actor.Id, stage = actor.Clock.Stage,
            reason, mask = "JUMP_only", graceSeconds = TacticalPathJumpGuard.GraceSeconds });
    }

    private void ReleaseCustomJumpGuard(CustomTacticActor actor, string reason)
    {
        if (actor.JumpGuard is not { Active: true } guard) return;
        try { guard.Release(); }
        catch (Exception ex) { Logger.LogWarning(ex, "Custom jump handoff release failed for {Slot}", actor.Slot); }
        TacticalTrace("custom_jump_handoff_released", new { actor.Id, stage = actor.Clock.Stage, reason });
    }

    private void TickCustomJumpGuard(CustomTacticActor actor, CCSPlayerPawn pawn, bool nativeAction)
    {
        var now = Server.CurrentTime;
        if (nativeAction) ReleaseCustomJumpGuard(actor, "native_action");
        else if (actor.JumpGuard is { Active: true } guard)
        {
            guard.Tick(now);
            if (!guard.Active) TacticalTrace("custom_jump_handoff_released", new { actor.Id,
                stage = actor.Clock.Stage, reason = "handoff_window_expired" });
        }
        var grounded = (pawn.Flags & 1) != 0;
        if (actor.LastGrounded == true && !grounded)
            TacticalTrace("custom_airborne_started", new { actor.Id, stage = actor.Clock.Stage, actor.State,
                position = new { pawn.AbsOrigin!.X, pawn.AbsOrigin.Y, pawn.AbsOrigin.Z },
                verticalSpeed = pawn.AbsVelocity.Z, speed = pawn.AbsVelocity.Length2D(),
                nativeStuck = pawn.Bot!.IsStuck,
                jumpHandoffActive = actor.JumpGuard is { Active: true },
                pathPreparationHeld = actor.PathHold is { Active: true },
                holdActive = actor.Hold is { Active: true } });
        actor.LastGrounded = grounded;
    }

    private void UpdateCustomLook(CustomTacticActor actor, CCSPlayerController player, CCSPlayerPawn pawn,
        bool settled, bool nativeAction)
    {
        var step = actor.Source.Steps[actor.Clock.Stage];
        var now = Server.CurrentTime;
        if (!settled || nativeAction || step.LookAt is not { } target || (step.Wait <= 0 && !actor.Clock.FinalHold))
        {
            ReleaseCustomLook(actor);
            if (nativeAction) actor.NextLookAttempt = now+1;
            return;
        }
        if (now < actor.NextLookAttempt || _tacticalLook is null) return;
        actor.Look ??= _tacticalLook.CreateLease(actor.Slot, actor.Pawn, pawn.Health);
        var applied = actor.Look.Update(player, target[0], target[1], out var reason);
        if (reason != actor.LookState)
        {
            actor.LookState = reason;
            TacticalTrace("custom_look", new { actor.Id, stage = actor.Clock.Stage, target, applied, reason });
        }
        if (!applied) { ReleaseCustomLook(actor); actor.NextLookAttempt = now+1; }
    }

    private void TickCustomTactic()
    {
        if (_customTacticPlan is not { } plan) return;
        if (!_roundLive || _resultWritten || InWarmup() || _customPlaybook is null
            || !TacticalMapCatalog.Matches(_customPlaybook.Map, Server.MapName) || !_setupDone
            || _request is not { Active: true, Observer: false } || !string.IsNullOrEmpty(_contractError)
            || !TacticalMapCatalog.Matches(_customPlaybook.Map, _request.Map)
            || plan.MatchNonce != _sessionNonce || plan.Round != _tacticalEpoch)
        { StopCustomTactic("round_inactive"); return; }
        try
        {
            foreach (var actor in _customTacticActors.Values.ToArray())
            {
                var player = Utilities.GetPlayerFromSlot(actor.Slot); var pawn = player?.PlayerPawn.Value;
                if (player is not { IsValid: true } || ControllerId(player) != actor.Id || LiveSide(player) != plan.Side
                    || _ledger.GetValueOrDefault(actor.Id)?.IsBot != true || actor.Id == plan.IssuerId
                    || player.ControllingBot || player.HasBeenControlledByPlayerThisRound
                    || pawn is not { IsValid: true, Health: > 0, Bot: not null, AbsOrigin: not null }
                    || pawn.EntityHandle.Raw != actor.Pawn)
                {
                    ReleaseCustomTacticActor(actor, "death_takeover_disconnect_side_change");
                    _customTacticActors.Remove(actor.Slot); continue;
                }
                var now = Server.CurrentTime; var bot = pawn.Bot;
                if ((pawn.Health < actor.Health || bot.IsAvoidingGrenade.Timestamp > now)
                    && ReleaseTacticForDanger(player, pawn.Health < actor.Health ? "health_loss" : "avoiding_grenade")) continue;
                var weapon = pawn.WeaponServices?.ActiveWeapon.Value?.DesignerName ?? "";
                if (TacticalFinishPolicy.ObjectiveNeedsControl(actor.Clock.FinalHold, pawn.IsDefusing, weapon))
                {
                    ReleaseCustomTacticActor(actor, "objective_handoff");
                    _customTacticActors.Remove(actor.Slot);
                    TacticalTrace("custom_objective_handoff", new { actor.Id, actor.Clock.Stage, weapon, pawn.IsDefusing });
                    continue;
                }
                var nativeAction = bot.IsEnemyVisible || bot.IsAttacking || pawn.Health < actor.Health
                    || pawn.BlindUntilTime > now || pawn.IsDefusing || weapon.Contains("grenade")
                    || weapon.Contains("flashbang") || weapon.Contains("molotov") || weapon.Contains("c4")
                    || _naturalBombPlanted || bot.IsAvoidingGrenade.Timestamp > now;
                actor.Health = pawn.Health;
                // Run before holdPosition/interrupted: a positional wait may
                // keep movement during combat, but never keeps this short-lived
                // launch guard alive over native combat/utility ownership.
                TickCustomJumpGuard(actor, pawn, nativeAction);
                if (nativeAction) ReleaseCustomTravelGait(actor);
                else if (actor.Gait is { Active: true }) KeepCustomTravelGait(actor);
                var goal = actor.Targets[actor.Clock.Stage];
                var reached = goal.Reached(pawn.AbsOrigin) && Math.Abs(goal.Z-pawn.AbsOrigin.Z) < 24;
                var waiting = actor.Source.Steps[actor.Clock.Stage].Wait > 0 || actor.Clock.FinalHold;
                var holding = actor.Hold is { Active: true };
                var pos = pawn.AbsOrigin;
                var distance = (pos.X-goal.X)*(pos.X-goal.X) + (pos.Y-goal.Y)*(pos.Y-goal.Y);
                var holdingInBounds = holding && TacticalWaitPolicy.InHoldBounds(distance, goal.Z-pos.Z, goal.Radius);
                var holdPosition = TacticalWaitPolicy.ShouldHold(waiting, reached, holdingInBounds);
                if (TacticalWaitPolicy.YieldToNative(holdPosition, nativeAction)) actor.YieldUntil = now + 1;
                // Arrival owns movement during a wait or final defense. A stale native
                // jump/stuck intent is NOT evidence of danger and must never
                // release the lease. Fighting still uses native aim/shooting.
                var interrupted = !holdPosition && (nativeAction || now < actor.YieldUntil);
                var settled = (reached || holdingInBounds) && (!waiting || pawn.AbsVelocity.Length2D() < 32);
                if (holding && !holdingInBounds)
                    TacticalTrace("custom_hold_displaced", new { actor.Id, actor.Clock.Stage,
                        distance2D = MathF.Sqrt(distance), heightDifference = goal.Z-pos.Z });
                if (interrupted)
                {
                    ReleaseCustomTravelGait(actor); actor.Continuation.Reset();
                    ReleaseCustomJumpGuard(actor, "combat_or_yield");
                    ReleaseCustomLook(actor);
                    actor.PathHold?.Release(); actor.PathHold = null; actor.DirectMove.Reset();
                    actor.Hold?.Release(); actor.Hold = null;
                    actor.Clock.Tick(now, false, true); actor.LastProgress = now;
                    // Combat can displace an already-arrived bot. Returning to
                    // its waypoint is a new travel attempt, not a contest with
                    // the previous trip's near-zero best distance.
                    actor.BestDistance = float.MaxValue; actor.NextMove = 0;
                    actor.Travel.Reset(now);
                    if (actor.State != "native_action")
                    {
                        actor.State = "native_action";
                        TacticalTrace("custom_yield", new { actor.Id, actor.Clock.Stage,
                            visible = bot.IsEnemyVisible, attacking = bot.IsAttacking,
                            blind = pawn.BlindUntilTime > now, weapon, bombPlanted = _naturalBombPlanted });
                    }
                    continue;
                }
                // Acquire zero-input only after reaching the NAV destination. This
                // is an input token, not Idle, teleporting or a physics freeze.
                if (holdPosition)
                {
                    ReleaseCustomTravelGait(actor);
                    actor.PathHold?.Release(); actor.PathHold = null;
                    try
                    {
                        actor.Hold ??= _customHold!.CreateLease(actor.Slot);
                        actor.Hold.Keep(); actor.OtherOwnerSince = null;
                        actor.YieldUntil = 0;
                    }
                    catch (InvalidOperationException ex) when (ex.Message == "hold_other_owner")
                    {
                        actor.Hold?.Release(); actor.Hold = null;
                        actor.OtherOwnerSince ??= now;
                        actor.YieldUntil = now + .25f; actor.LastProgress = now;
                        actor.Clock.Tick(now, false, true);
                        if (now-actor.OtherOwnerSince > 10)
                        {
                            ReleaseCustomTacticActor(actor, "another_owner"); _customTacticActors.Remove(actor.Slot);
                            TacticalTrace("custom_another_owner_native_fallback", new { actor.Id, actor.Clock.Stage });
                        }
                        continue;
                    }
                }
                else { actor.Hold?.Release(); actor.Hold = null; ReleaseCustomLook(actor); }
                var stage = actor.Clock.Stage;
                var successorCommitted = false;
                // Zero-wait through-points do NOT brake for another initial
                // path preparation. Keep the old valid native goal/path during
                // rate limiting, then commit path+successor target atomically.
                if (!waiting && settled && stage+1 < actor.Targets.Length && actor.DirectMove.Committed
                    && _tacticalNavigator!.IsMovingTo(player, actor.Pawn, goal.X, goal.Y, goal.Z)
                    && !(actor.Targets[stage+1].Reached(pos) && Math.Abs(actor.Targets[stage+1].Z-pos.Z) < 24))
                {
                    var successor = actor.Targets[stage+1];
                    var continuation = actor.Continuation.Tick(now,
                        (out string why) => _tacticalNavigator.TryContinueRoute(player, actor.Pawn,
                            goal.X, goal.Y, goal.Z, successor.X, successor.Y, successor.Z, out why),
                        out var continuationReason);
                    if (continuation == TacticalPathAction.Pending)
                    {
                        KeepCustomTravelGait(actor);
                        if (now >= actor.NextMove)
                        {
                            _tacticalNavigator.TryKeepRushing(player, actor.Pawn, out _);
                            actor.NextMove = now+.9f;
                        }
                        actor.Clock.Tick(now, false, false); actor.Travel.Reset(now); actor.LastProgress = now;
                        if (actor.State != "continuing_path_pending")
                        {
                            actor.State = "continuing_path_pending";
                            TacticalTrace("custom_successor_pending", new { actor.Id, stage, successor,
                                reason = continuationReason, movementHeld = false });
                        }
                        continue;
                    }
                    if (continuation == TacticalPathAction.Yielded)
                    {
                        ReleaseCustomTravelGait(actor); ReleaseCustomJumpGuard(actor, "combat_or_yield");
                        actor.Continuation.Reset(); actor.DirectMove.Reset(); actor.YieldUntil = now+1;
                        continue;
                    }
                    if (continuation == TacticalPathAction.Failed && continuationReason != "navigation_previous_goal_changed")
                    {
                        if (continuationReason is not ("navigation_path_unavailable" or "custom_successor_path_timeout"))
                            throw new InvalidOperationException(continuationReason);
                        TacticalTrace("custom_successor_rejected", new { actor.Id, stage, successor, reason = continuationReason });
                        ReleaseCustomTacticActor(actor, continuationReason); _customTacticActors.Remove(actor.Slot);
                        AllSlots().FirstOrDefault(p => ControllerId(p) == plan.IssuerId)?.PrintToChat(
                            $" \x02战术槽 {actor.RosterSlot}：下一段路径未能建立，已恢复原生 AI；其他队友继续。\x01");
                        continue;
                    }
                    successorCommitted = continuation == TacticalPathAction.Moving;
                    if (successorCommitted) TacticalTrace("custom_successor_committed", new { actor.Id, stage, successor,
                        route = "native_fastest", movementHeld = false, speed = pawn.AbsVelocity.Length2D() });
                }
                var action = actor.Clock.Tick(now, settled, false);
                var transit = TacticalWaypointPolicy.IsTransit(action, actor.Source.Steps[stage].Wait);
                if (action is TacticStepAction.Advanced or TacticStepAction.Completed)
                {
                    if (action == TacticStepAction.Advanced && !nativeAction)
                        BeginCustomJumpGuard(actor, "next_waypoint");
                    if (transit)
                    {
                        // Continue the same route without an intervening Idle.
                        // An atomically accepted successor retains movement
                        // and needs no zero-input lease. Fresh/foreign goals
                        // still use the original validated preparation gate.
                        ReleaseCustomLook(actor);
                        actor.Hold?.Release(); actor.Hold = null;
                        actor.PathHold?.Release(); actor.PathHold = null;
                        if (successorCommitted) actor.DirectMove.AdoptCommitted();
                        else { actor.DirectMove.Reset(); ReleaseCustomTravelGait(actor); }
                        actor.Continuation.Reset();
                        actor.State = "transit";
                    }
                    else ReleaseCustomTacticActor(actor, "step_complete", goal,
                        preserveJumpGuard: action == TacticStepAction.Advanced && !nativeAction);
                    actor.NextMove = 0; actor.BestDistance = float.MaxValue; actor.LastProgress = now;
                    actor.Travel.Reset(now);
                    TacticalTrace("custom_step_complete", new { actor.Id, stage, transit });
                    if (action == TacticStepAction.Completed) _customTacticActors.Remove(actor.Slot);
                    if (!transit) continue;
                    // Advance at most once per actor per tick, even for
                    // overlapping zero-wait waypoints. Do not merge or skip
                    // waypoints, and do not recursively evaluate the route.
                    stage = actor.Clock.Stage;
                    goal = actor.Targets[stage];
                    distance = (pos.X-goal.X)*(pos.X-goal.X) + (pos.Y-goal.Y)*(pos.Y-goal.Y);
                }
                if (action == TacticStepAction.Wait)
                {
                    UpdateCustomLook(actor, player, pawn, settled, nativeAction);
                    actor.LastProgress = now;
                    var holdState = actor.Clock.HoldingFinal ? "holding_final" : "waiting";
                    if (actor.State != holdState)
                    {
                        actor.State = holdState;
                        TacticalTrace(actor.Clock.HoldingFinal ? "custom_final_hold_started" : "custom_wait_started",
                            new { actor.Id, stage, actor.Clock.Remaining, finish = actor.Source.Finish, side = plan.Side });
                    }
                    if (now >= actor.NextDiagnostic)
                    {
                        TraceCustomTacticPosition(actor, pawn, goal, "custom_hold_progress");
                        actor.NextDiagnostic = now + 3;
                    }
                    continue;
                }
                // Settling is covered by the same hold lease, not re-entering MoveTo.
                if (actor.Hold is { Active: true })
                { UpdateCustomLook(actor, player, pawn, settled, nativeAction); actor.LastProgress = now; continue; }
                // Preparation and arrival are separate leases: this one must
                // never make a bot far from its goal count as "already holding".
                if (actor.PathHold is { Active: true }) actor.PathHold.Keep();
                if (!TacticalWaypointPolicy.ShouldCheckMovement(Server.TickCount, transit,
                    transit && goal.Reached(pos) && Math.Abs(goal.Z-pos.Z) < 24)) continue;
                if (actor.State is "waiting" or "holding_final")
                { actor.BestDistance = float.MaxValue; actor.LastProgress = now; actor.Travel.Reset(now); }
                if (distance + 400 < actor.BestDistance) { actor.BestDistance = distance; actor.LastProgress = now; }
                if (actor.Travel.IsStalled(now, pos.X, pos.Y, MathF.Sqrt(distance)))
                {
                    // Capture live position BEFORE cancelling the MoveTo state.
                    // A native call returning is not evidence of actual travel.
                    TraceCustomTacticPosition(actor, pawn, goal, "custom_stalled_native_fallback");
                    ReleaseCustomTacticActor(actor, "stalled"); _customTacticActors.Remove(actor.Slot);
                    continue;
                }
                if (now >= actor.NextDiagnostic)
                {
                    TraceCustomTacticPosition(actor, pawn, goal, "custom_progress");
                    actor.NextDiagnostic = now + 3;
                }
                if (now < actor.NextMove) continue;
                var ownsGoal = _tacticalNavigator!.IsMovingTo(player, actor.Pawn, goal.X, goal.Y, goal.Z);
                if (actor.DirectMove.NeedsPreparation(ownsGoal))
                {
                    ReleaseCustomTravelGait(actor);
                    // Acquire BEFORE modifying the native state/path. Another
                    // controller's ownership must reject even a replan which
                    // would happen to succeed on the very first call.
                    try
                    {
                        actor.PathHold ??= _customHold!.CreateLease(actor.Slot);
                        actor.PathHold.Keep(); actor.OtherOwnerSince = null;
                        // The independent JUMP token bridges PathHold's release;
                        // prepare once, not on each .25s path retry or rush renew.
                        if (actor.JumpGuard is not { Preparing: true })
                            BeginCustomJumpGuard(actor, "path_preparation");
                    }
                    catch (InvalidOperationException ex) when (ex.Message == "hold_other_owner")
                    {
                        actor.PathHold?.Release(); actor.PathHold = null;
                        ReleaseCustomJumpGuard(actor, "another_owner");
                        actor.DirectMove.Reset(); actor.OtherOwnerSince ??= now;
                        actor.NextMove = now + .25f; actor.LastProgress = now; actor.Travel.Reset(now);
                        if (now-actor.OtherOwnerSince > 10)
                        {
                            ReleaseCustomTacticActor(actor, "another_owner"); _customTacticActors.Remove(actor.Slot);
                            TacticalTrace("custom_another_owner_native_fallback", new { actor.Id, actor.Clock.Stage });
                        }
                        continue;
                    }
                }
                // An owned goal alone previously debounced a FAILED native
                // replan forever, leaving the old middle route in place. Enter
                // MoveTo once, then commit a fresh FASTEST native NAV path; only
                // after acceptance release movement and renew hurry intent.
                var pathAction = actor.DirectMove.Tick(now,
                    ownsGoal,
                    (out string why) => _tacticalNavigator.TryMoveTo(player, actor.Pawn, goal.X, goal.Y, goal.Z, out why),
                    (out string why) => _tacticalNavigator.TryShortestPath(player, actor.Pawn, goal.X, goal.Y, goal.Z, out why),
                    (out string why) => _tacticalNavigator.TryKeepRushing(player, actor.Pawn, out why),
                    out var reason);
                if (pathAction == TacticalPathAction.Pending)
                {
                    actor.NextMove = now + .25f; actor.LastProgress = now;
                    actor.Travel.Reset(now);
                    if (actor.State != "preparing_path")
                    {
                        actor.State = "preparing_path";
                        TacticalTrace("custom_path_pending", new { actor.Id, stage, goal, reason,
                            movementHeld = actor.PathHold is { Active: true } });
                    }
                    continue;
                }
                // Commit the grace BEFORE removing the path-preparation token.
                // Renewing an existing native goal must not extend this window.
                if (pathAction == TacticalPathAction.Moving && actor.JumpGuard is { Preparing: true } preparedJump)
                {
                    preparedJump.Committed(now);
                    TacticalTrace("custom_jump_handoff_committed", new { actor.Id, stage,
                        graceSeconds = TacticalPathJumpGuard.GraceSeconds });
                }
                actor.PathHold?.Release(); actor.PathHold = null;
                if (pathAction == TacticalPathAction.Yielded)
                {
                    ReleaseCustomTravelGait(actor);
                    ReleaseCustomJumpGuard(actor, "native_path_yield");
                    actor.YieldUntil = now + 1; actor.LastProgress = now;
                    actor.BestDistance = float.MaxValue; actor.Travel.Reset(now); continue;
                }
                if (pathAction == TacticalPathAction.Failed)
                {
                    if (reason is not ("navigation_path_unavailable" or "custom_path_preparation_timeout"))
                        throw new InvalidOperationException(reason);
                    TraceCustomTacticPosition(actor, pawn, goal, "custom_path_failed");
                    TacticalTrace("custom_path_rejected", new { actor.Id, stage, goal, reason });
                    ReleaseCustomTacticActor(actor, reason); _customTacticActors.Remove(actor.Slot);
                    AllSlots().FirstOrDefault(p => ControllerId(p) == plan.IssuerId)?.PrintToChat(
                        $" \x02战术槽 {actor.RosterSlot}：该目的地路径未能建立，已恢复原生 AI；其他队友继续。\x01");
                    continue;
                }
                actor.NextMove = now + .9f;
                KeepCustomTravelGait(actor);
                OpeningPathCommitted(actor.Slot);
                if (actor.State != "moving")
                {
                    actor.State = "moving"; actor.Travel.Reset(now);
                    TacticalTrace("custom_move", new { actor.Id, stage, goal, route = "native_fastest", pathAccepted = true });
                }
            }
            if (_customTacticActors.Count == 0) StopCustomTactic("all_completed_or_released");
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "Custom tactic stopped; native AI retained");
            StopCustomTactic("execution_error");
            AllSlots().FirstOrDefault(p => ControllerId(p) == plan.IssuerId)?.PrintToChat(
                " \x02自定义战术遇到技术错误，已释放追加指令，队友继续原生 AI。\x01");
        }
    }

    private void TraceCustomTacticPosition(CustomTacticActor actor, CCSPlayerPawn pawn,
        TacticalTarget goal, string kind)
    {
        var pos = pawn.AbsOrigin!;
        var player = Utilities.GetPlayerFromSlot(actor.Slot)!;
        TacticalTrace(kind, new
        {
            actor.Id, actor.RosterSlot, stage = actor.Clock.Stage, actor.State,
            position = new { pos.X, pos.Y, pos.Z }, target = goal,
            distance2D = MathF.Sqrt((pos.X-goal.X)*(pos.X-goal.X) + (pos.Y-goal.Y)*(pos.Y-goal.Y)),
            heightDifference = goal.Z-pos.Z, speed = pawn.AbsVelocity.Length2D(),
            verticalSpeed = pawn.AbsVelocity.Z, grounded = (pawn.Flags & 1) != 0,
            nativeStuck = pawn.Bot!.IsStuck,
            jumpHandoffActive = actor.JumpGuard is { Active: true },
            jumpHandoffPreparing = actor.JumpGuard is { Preparing: true },
            nativeOwnsGoal = _tacticalNavigator!.IsMovingTo(player, actor.Pawn, goal.X, goal.Y, goal.Z),
            hurryRemaining = Math.Max(0, pawn.Bot!.HurryTimer.Timestamp-Server.CurrentTime),
            actor.Clock.Remaining,
            holdActive = actor.Hold is { Active: true },
            pathPreparationHeld = actor.PathHold is { Active: true },
            direction = actor.LookState,
            movement = actor.Source.Steps[actor.Clock.Stage].Movement,
            travelGaitOwned = actor.Gait is { Active: true },
        });
    }
}
