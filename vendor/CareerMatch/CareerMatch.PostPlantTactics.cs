using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    private sealed class PostPlantActor(string id, int slot, uint pawn, TacticalTarget target, int health)
    {
        internal readonly string Id = id;
        internal readonly int Slot = slot;
        internal readonly uint Pawn = pawn;
        internal readonly TacticalTarget Target = target;
        internal readonly TacticalDirectMove Path = new();
        internal TacticalHoldControls.Lease? Hold, PathHold;
        internal int Health = health;
        internal float YieldUntil, NextMove;
        internal string State = "assigned";
    }
    // Keep this round's accepted intent after the opening finishes. Planting
    // must still supersede it even when every earlier waypoint has completed.
    private CommandPlan? _tacticalRoundIntent, _postPlantPlan;
    private string _postPlantState = "not_started";
    private readonly Dictionary<int, PostPlantActor> _postPlantActors = [];

    private void OnTacticalBombPlanted(EventBombPlanted ev)
    {
        var plan = _tacticalRoundIntent;
        StopTacticalCommands("bomb_planted"); // Always cancels ALL old waits/look/routes first.
        if (plan is null || plan.MatchNonce != _sessionNonce || plan.Round != _tacticalEpoch
            || !_roundLive || _resultWritten || InWarmup() || _request is not { Active: true, Observer: false }) return;
        var epoch = _tacticalEpoch; var nonce = _sessionNonce;
        // planted_c4 may not be published yet inside the game event callback.
        Server.NextFrame(() =>
        {
            if (epoch != _tacticalEpoch || nonce != _sessionNonce || !_roundLive || _resultWritten
                || !_naturalBombPlanted || InWarmup()) return;
            StartPostPlantTactic(plan);
        });
    }

    private void StartPostPlantTactic(CommandPlan plan)
    {
        try
        {
            EnsureTacticalHold();
            var bomb = Utilities.FindAllEntitiesByDesignerName<CPlantedC4>("planted_c4")
                .FirstOrDefault(b => b.IsValid && b.BombTicking && !b.BombDefused && !b.HasExploded);
            var bombPos = bomb?.AbsOrigin ?? throw new InvalidOperationException("实际下包位置未就绪");
            var sites = Utilities.FindAllEntitiesByDesignerName<CBombTarget>("func_bomb_target")
                .Where(s => s.IsValid && s.AbsOrigin is not null && (s.AbsRotation is not { } r
                    || Math.Abs(r.X) < .1 && Math.Abs(r.Y) < .1 && Math.Abs(r.Z) < .1)).ToArray();
            var site = sites.SingleOrDefault(s =>
            {
                var o = s.AbsOrigin!; var min = s.Collision.Mins; var max = s.Collision.Maxs;
                return bombPos.X >= o.X+min.X-8 && bombPos.X <= o.X+max.X+8
                    && bombPos.Y >= o.Y+min.Y-8 && bombPos.Y <= o.Y+max.Y+8
                    && bombPos.Z >= o.Z+min.Z-16 && bombPos.Z <= o.Z+max.Z+16;
            }) ?? throw new InvalidOperationException("实际包点无法唯一确认");
            var siteName = site.IsBombSiteB ? "B" : "A";
            var actualPlan = plan with { Site = siteName };
            var players = AllSlots().Where(p => ControllerId(p) is { } id && id != plan.IssuerId
                && _ledger.GetValueOrDefault(id)?.IsBot == true && LiveSide(p) == plan.Side
                && !p.ControllingBot && !p.HasBeenControlledByPlayerThisRound
                && p.PlayerPawn.Value is { IsValid: true, Health: > 0, Bot: not null, AbsOrigin: not null }).ToArray();
            var prepared = new List<PostPlantActor>();
            var bombPoint = new TacticalObjectivePolicy.GuardPoint(bombPos.X, bombPos.Y, bombPos.Z);
            var guardCandidates = new List<TacticalObjectivePolicy.GuardPoint>();
            var occupied = new List<TacticalObjectivePolicy.GuardPoint>();
            if (plan.Side == "t")
            {
                var origin = site.AbsOrigin!; var min = site.Collision.Mins; var max = site.Collision.Maxs;
                guardCandidates.AddRange(CCSNavArea.GetAllNavAreas().OrderBy(a => a.Id).Select(a => a.Center)
                    .Where(c => c.X >= origin.X+min.X-384 && c.X <= origin.X+max.X+384
                        && c.Y >= origin.Y+min.Y-384 && c.Y <= origin.Y+max.Y+384)
                    .Select(c => new TacticalObjectivePolicy.GuardPoint(c.X, c.Y, c.Z))
                    .Where(c => TacticalObjectivePolicy.GuardFloor(c, bombPoint)));
                // Humans are not commanded, but their actual nearby position
                // reserves space rather than assigning another guard on top.
                occupied.AddRange(AllSlots().Where(p => LiveSide(p) == "t"
                    && (ControllerId(p) == plan.IssuerId || p.ControllingBot || p.HasBeenControlledByPlayerThisRound
                        || ControllerId(p) is { } id && _ledger.GetValueOrDefault(id)?.IsBot != true)
                    && p.PlayerPawn.Value is { IsValid: true, Health: > 0, AbsOrigin: not null })
                    .Select(p => p.PlayerPawn.Value!.AbsOrigin!)
                    .Select(c => new TacticalObjectivePolicy.GuardPoint(c.X, c.Y, c.Z))
                    .Where(c => TacticalObjectivePolicy.GuardFloor(c, bombPoint)));
            }
            for (var i = 0; i < players.Length; i++)
            {
                var p = players[i]; var pawn = p.PlayerPawn.Value!;
                // The old plant-brush target remains a native fallback only.
                var target = BuildTacticalRoute(actualPlan, i, includeHints: false)[^1];
                if (plan.Side == "t")
                {
                    var pos = pawn.AbsOrigin!;
                    var current = new TacticalObjectivePolicy.GuardPoint(pos.X, pos.Y, pos.Z);
                    var candidates = new List<TacticalObjectivePolicy.GuardPoint>(guardCandidates);
                    var point = CCSNavArea.GetClosestNavArea(pos, 48)?.GetClosestPoint(pos);
                    if (point is not null && Math.Abs(point.Z-pos.Z) < 24)
                        candidates.Insert(0, new(point.X, point.Y, point.Z));
                    var selected = TacticalObjectivePolicy.SelectGuard(current, bombPoint, candidates, occupied);
                    if (selected is { } guard)
                    {
                        target = new(guard.X, guard.Y, guard.Z, 40, true);
                    }
                    else TacticalTrace("post_plant_guard_space_fallback", new { id = ControllerId(p), candidates = candidates.Count });
                    occupied.Add(new(target.X, target.Y, target.Z));
                }
                else
                {
                    var point = CCSNavArea.GetClosestNavArea(bombPos, 96)?.GetClosestPoint(bombPos);
                    if (point is not null) target = new(point.X, point.Y, point.Z, 96, true);
                }
                prepared.Add(new(ControllerId(p)!, p.Slot, pawn.EntityHandle.Raw, target, pawn.Health));
            }
            _postPlantPlan = actualPlan;
            _postPlantState = plan.Side == "t" ? "guard_site" : "retake_site";
            foreach (var actor in prepared)
            {
                _tacticalReleases.Remove(actor.Slot);
                ReleaseMotionClip(actor.Slot, "post_plant"); ReleaseCorner(actor.Slot, "post_plant");
                ReleaseNatural(actor.Slot, "post_plant"); ReleaseNaturalRecovery(actor.Slot, "post_plant");
                ReleaseNaturalJumpBlock(actor.Slot);
                _postPlantActors.Add(actor.Slot, actor);
            }
            TacticalTrace("post_plant_started", new { side = plan.Side, siteName,
                mode = plan.Side == "t" ? "guard_site" : "retake_then_native_defuse",
                targets = prepared.Select(a => new { a.Id, a.Target }) });
            AllSlots().FirstOrDefault(p => ControllerId(p) == plan.IssuerId)?.PrintToChat(plan.Side == "t"
                ? " \x04炸弹已下：原战术结束，队友留在包点守包。\x01"
                : " \x04炸弹已下：原战术结束，队友回防实际包点。\x01");
        }
        catch (Exception ex)
        {
            StopPostPlantTactic("start_failed");
            Logger.LogWarning(ex, "Post-plant command not started; old opening remains cancelled");
            _postPlantState = "unavailable:" + ex.Message;
            TacticalTrace("post_plant_unavailable", new { reason = ex.Message });
            AllSlots().FirstOrDefault(p => ControllerId(p) == plan.IssuerId)?.PrintToChat(
                " \x02原战术已结束，但实际包点任务未能建立，队友暂用原生 AI。输入 css_tactics 查看原因。\x01");
        }
    }

    private void ReleasePostPlantActor(PostPlantActor actor, string reason)
    {
        actor.Hold?.Release(); actor.PathHold?.Release();
        actor.Hold = actor.PathHold = null; actor.Path.Reset();
        ReleaseTacticalActor(new(actor.Id, actor.Slot, actor.Pawn, [actor.Target], Server.CurrentTime), reason);
    }
    private void StopPostPlantTactic(string reason)
    {
        foreach (var actor in _postPlantActors.Values)
            try { ReleasePostPlantActor(actor, reason); }
            catch (Exception ex) { Logger.LogWarning(ex, "Post-plant release failed for {Slot}", actor.Slot); }
        if (_postPlantPlan is not null) TacticalTrace("post_plant_stopped", new { reason });
        _postPlantActors.Clear(); _postPlantPlan = null;
        _postPlantState = "stopped:" + reason;
    }

    private void TickPostPlantTactic()
    {
        if (_postPlantPlan is not { } plan) return;
        if (!_roundLive || _resultWritten || !_naturalBombPlanted || InWarmup() || !_setupDone
            || _request is not { Active: true, Observer: false } || !string.IsNullOrEmpty(_contractError)
            || plan.MatchNonce != _sessionNonce || plan.Round != _tacticalEpoch)
        { StopPostPlantTactic("round_or_bomb_inactive"); return; }
        try
        {
            foreach (var actor in _postPlantActors.Values.ToArray())
            {
                var p = Utilities.GetPlayerFromSlot(actor.Slot); var pawn = p?.PlayerPawn.Value;
                if (p is not { IsValid: true } || ControllerId(p) != actor.Id || LiveSide(p) != plan.Side
                    || _ledger.GetValueOrDefault(actor.Id)?.IsBot != true || p.ControllingBot || p.HasBeenControlledByPlayerThisRound
                    || pawn is not { IsValid: true, Health: > 0, Bot: not null, AbsOrigin: not null }
                    || pawn.EntityHandle.Raw != actor.Pawn)
                { ReleasePostPlantActor(actor, "death_takeover_disconnect"); _postPlantActors.Remove(actor.Slot); continue; }
                var now = Server.CurrentTime; var bot = pawn.Bot;
                var weapon = pawn.WeaponServices?.ActiveWeapon.Value?.DesignerName ?? "";
                var combat = bot.IsEnemyVisible || bot.IsAttacking || pawn.Health < actor.Health || pawn.BlindUntilTime > now
                    || pawn.IsDefusing || weapon.Contains("grenade") || weapon.Contains("flashbang")
                    || weapon.Contains("molotov") || weapon.Contains("c4") || bot.IsAvoidingGrenade.Timestamp > now;
                actor.Health = pawn.Health;
                // Target was geometrically selected on the actual plant-site
                // NAV. Do not require CT's plant-permission flag for a retake.
                var atSite = actor.Target.Reached(pawn.AbsOrigin) && Math.Abs(actor.Target.Z-pawn.AbsOrigin.Z) < 48;
                var action = TacticalObjectivePolicy.Decide(plan.Side, atSite, combat || now < actor.YieldUntil);
                if (action == TacticalBombAction.Combat)
                {
                    actor.Hold?.Release(); actor.PathHold?.Release(); actor.Hold = actor.PathHold = null;
                    actor.Path.Reset(); actor.NextMove = 0;
                    if (combat) actor.YieldUntil = now+1;
                    if (actor.State != "combat") TacticalTrace("post_plant_combat", new { actor.Id });
                    actor.State = "combat"; continue;
                }
                if (action == TacticalBombAction.NativeDefuse)
                {
                    ReleasePostPlantActor(actor, "native_defuse"); _postPlantActors.Remove(actor.Slot);
                    TacticalTrace("post_plant_native_defuse", new { actor.Id }); continue;
                }
                if (action == TacticalBombAction.Guard)
                {
                    actor.PathHold?.Release(); actor.PathHold = null;
                    actor.Hold ??= _customHold!.CreateLease(actor.Slot); actor.Hold.Keep();
                    // Movement-only token. Native eyes, fire and utility stay
                    // live; contact releases it immediately, quiet returns HERE.
                    if (actor.State != "guarding") TacticalTrace("post_plant_guarding", new { actor.Id, actor.Target });
                    actor.State = "guarding"; continue;
                }
                actor.Hold?.Release(); actor.Hold = null;
                if (actor.PathHold is { Active: true }) actor.PathHold.Keep();
                if (Server.TickCount % 16 != 0 || now < actor.NextMove) continue;
                var target = actor.Target;
                var owns = _tacticalNavigator!.IsMovingTo(p, actor.Pawn, target.X, target.Y, target.Z);
                if (actor.Path.NeedsPreparation(owns))
                { actor.PathHold ??= _customHold!.CreateLease(actor.Slot); actor.PathHold.Keep(); }
                var path = actor.Path.Tick(now, owns,
                    (out string why) => _tacticalNavigator.TryMoveTo(p, actor.Pawn, target.X, target.Y, target.Z, out why),
                    (out string why) => _tacticalNavigator.TryShortestPath(p, actor.Pawn, target.X, target.Y, target.Z, out why),
                    (out string why) => _tacticalNavigator.TryKeepRushing(p, actor.Pawn, out why), out var reason);
                if (path == TacticalPathAction.Pending) { actor.NextMove = now+.25f; continue; }
                actor.PathHold?.Release(); actor.PathHold = null;
                if (path == TacticalPathAction.Yielded) { actor.YieldUntil = now+1; continue; }
                if (path == TacticalPathAction.Failed)
                {
                    ReleasePostPlantActor(actor, reason); _postPlantActors.Remove(actor.Slot);
                    TacticalTrace("post_plant_native_fallback", new { actor.Id, reason }); continue;
                }
                actor.NextMove = now+.9f;
                if (actor.State != "moving") TacticalTrace("post_plant_move", new { actor.Id, target });
                actor.State = "moving";
            }
            if (_postPlantActors.Count == 0) StopPostPlantTactic("all_released");
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "Post-plant command released after technical failure");
            StopPostPlantTactic("execution_error");
        }
    }
}
