using System.Text.Json;
using System.Text.Json.Serialization;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Commands;
using CounterStrikeSharp.API.Modules.Memory;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

// Engine-owned path following, collision, combat, utility and bomb interaction.
// Custom arrival waits/look requests and short opening jump suppression are
// separately owned/released; post-plant duties supersede the opening plan.
public sealed partial class CareerMatchPlugin
{
    private sealed class TacticalRoutes
    {
        [JsonPropertyName("schema_version")] public int Version { get; set; } = 1;
        [JsonPropertyName("map_routes")]
        public Dictionary<string, Dictionary<string, Dictionary<string, float[][]>>> Maps { get; set; } = [];
        public static TacticalRoutes Default() => new()
        {
            Maps = new()
            {
                ["de_dust2"] = new()
                {
                    // Static route hints, not prerecorded player movement or
                    // aim. The current map's NAV snaps each hint before use.
                    ["t"] = new()
                    {
                        ["A"] = [[773, 816, 3], [1528, 1736, 0]],
                        ["B"] = [[-1711, 1152, 35]],
                    },
                },
            },
        };
    }

    private sealed record TacticalTarget(float X, float Y, float Z, float Radius, bool Site)
    {
        public Vector Vector() => new(X, Y, Z);
        public bool Reached(Vector pos) => Math.Abs(pos.Z - Z) < 96
            && (pos.X - X) * (pos.X - X) + (pos.Y - Y) * (pos.Y - Y) <= Radius * Radius;
    }

    private sealed class TacticalActor(string id, int slot, uint pawn, TacticalTarget[] route, float now)
    {
        public readonly string Id = id;
        public readonly int Slot = slot;
        public readonly uint Pawn = pawn;
        public readonly TacticalTarget[] Route = route;
        public int Stage;
        public float NextIssue, YieldUntil, LastProgress = now;
        public float BestDistance = float.MaxValue;
        public int Health;
        public string State = "queued";
    }

    private readonly TacticalCommandQueue _tacticalQueue = new();
    private readonly Dictionary<int, TacticalActor> _tacticalActors = [];
    private sealed record TacticalRelease(string Id, int Slot, uint Pawn, TacticalTarget Target, float Expires);
    private readonly Dictionary<int, TacticalRelease> _tacticalReleases = [];
    private TacticalNativeNavigation? _tacticalNavigator;
    private string _tacticalFailure = "not_bound";
    private TacticalRoutes _tacticalRoutes = TacticalRoutes.Default();
    private CommandPlan? _tacticalPlan;
    private int _tacticalEpoch;
    private float _tacticalDeadline;
    private bool _tacticalTipShown;

    private void LoadTacticalCommands()
    {
        AddCommandListener("say", OnTacticalChat, HookMode.Pre);
        AddCommandListener("say_team", OnTacticalChat, HookMode.Pre);
        RegisterListener<Listeners.OnTick>(TickTacticalCommands);
        AddCommand("css_tactics", "Opening tactics: rusha / rushb / default", (player, command) =>
        {
            if (command.ArgCount > 1) OnTacticalChat(player, command, "say", command.ArgString);
            else
            {
                command.ReplyToCommand(TacticalCommands.Usage);
                command.ReplyToCommand($"[CareerTactics] {ModuleVersion}; navigation={_tacticalFailure}; pending={_tacticalQueue.Pending?.TacticId ?? _tacticalQueue.Pending?.Site ?? "none"}; active_bots={_tacticalActors.Count + _customTacticActors.Count}; playbook={_customPlaybookState}; hold={_customHoldState}; direction={_tacticalLookState}; postplant={_postPlantState}:{_postPlantActors.Count}");
                if (_request is { Observer: true })
                    command.ReplyToCommand("[CareerTactics] 观战模式不支持玩家战术槽；仅真人参赛模式使用槽1–5。");
                else if (_customAssignments.Count == 5 && _request is { } assignedRequest)
                {
                    foreach (var binding in _customAssignments)
                        command.ReplyToCommand($"[CareerTactics] 槽{binding.TacticSlot}={SlotDisplayName(binding.PlayerId)}（{binding.PlayerId}）；职责={binding.Route.Duty}"
                            + (binding.PlayerId == assignedRequest.HumanPlayerId ? "；真人始终手动" : ""));
                }
                else if (_request is { } request)
                {
                    command.ReplyToCommand($"[CareerTactics] 槽1=真人（你，始终手动）：{request.HumanPlayerId}");
                    var roster = (request.HumanTeam == "t" ? request.T : request.Ct).Players;
                    for (var i = 0; i < roster.Count; i++)
                        command.ReplyToCommand($"[CareerTactics] 槽{i+2}={roster[i].DisplayName}（{roster[i].PlayerId}）");
                }
            }
        });
        TacticalNativeNavigation.TryBind(Addresses.ServerPath, out _tacticalNavigator, out _tacticalFailure);
        Logger.LogInformation("Tactical native navigation: {State}", _tacticalFailure);
        TacticalNativeLook.TryBind(Addresses.ServerPath, out _tacticalLook, out _tacticalLookState);
        Logger.LogInformation("Tactical native observation: {State}", _tacticalLookState);
        var path = Path.Combine(ModuleDirectory, "tactical_routes.json");
        try
        {
            if (!File.Exists(path)) File.WriteAllText(path, JsonSerializer.Serialize(_tacticalRoutes, JsonOptions));
            if (new FileInfo(path).Length > 65536) throw new InvalidDataException("tactical_routes_too_large");
            var routes = JsonSerializer.Deserialize<TacticalRoutes>(File.ReadAllText(path));
            if (routes is null || routes.Version != 1 || routes.Maps.Count > 32
                || routes.Maps.Any(m => m.Value.Count > 2 || m.Value.Any(s => s.Key is not ("t" or "ct")
                    || s.Value.Count > 2 || s.Value.Any(r => r.Key is not ("A" or "B") || r.Value.Length > 8
                        || r.Value.Any(p => p.Length != 3 || p.Any(v => !float.IsFinite(v) || Math.Abs(v) > 32768))))))
                throw new InvalidDataException("tactical_routes_invalid");
            _tacticalRoutes = routes;
        }
        catch (Exception ex) { Logger.LogWarning("Tactical route file rejected; built-in routes retained: {Error}", ex.Message); }
        LoadCustomPlaybook();
    }

    private HookResult OnTacticalChat(CCSPlayerController? player, CommandInfo command) =>
        OnTacticalChat(player, command, command.GetArg(0), command.ArgString);

    private HookResult OnTacticalChat(CCSPlayerController? player, CommandInfo command, string channel, string text)
    {
        // Unrecognized chat never invokes roster/nav/native APIs and is untouched.
        var parsed = TacticalCommands.Parse(channel, text);
        if (parsed is null) return HookResult.Continue;
        BindPlayerSlots();
        var id = ControllerId(player) ?? "";
        var rules = Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules")
            .FirstOrDefault()?.GameRules;
        var context = new TacticalCommandContext
        {
            MatchNonce = _sessionNonce, Round = _tacticalEpoch, SpeakerId = id,
            Side = player?.Team == CsTeam.Terrorist ? "t" : player?.Team == CsTeam.CounterTerrorist ? "ct" : "",
            AuthorizedMatch = _setupDone && _request is { Active: true } && string.IsNullOrEmpty(_contractError),
            AuthorizedHuman = id.Length > 0 && id == _request?.HumanPlayerId,
            SpeakerValid = player is { IsValid: true, IsHLTV: false },
            SpeakerIsBot = _ledger.GetValueOrDefault(id)?.IsBot ?? true,
            Observer = _request?.Observer ?? false, Warmup = rules?.WarmupPeriod ?? true,
            Preparation = rules?.FreezePeriod ?? false, MatchCompleted = _resultWritten,
        };
        var decision = TacticalCommands.Gate(parsed, context);
        if (decision.Accepted && decision.Plan is { } plan)
        {
            if (_tacticalNavigator is null)
            {
                player?.PrintToChat(" \x02指挥：当前游戏版本的寻路接口未就绪，未设置战术。控制台输入 css_tactics 查看原因。\x01");
                return HookResult.Handled;
            }
            try
            {
                if (plan.Order == TacticalOrder.Playbook) PrepareCustomTactic(plan);
                else BuildTacticalRoute(plan, 0);
                PrepareOpeningGuards(plan);
            }
            catch (Exception ex)
            {
                Logger.LogWarning(ex, "Tactic preflight rejected {Tactic}: {Reason}", plan.TacticId ?? plan.Site, ex.Message);
                TacticalTrace("preflight_rejected", new { plan.TacticId, plan.Site, plan.Side, reason = ex.Message });
                player?.PrintToChat($" \x02指挥：战术未启动（{ex.Message}）。\x01");
                return HookResult.Handled;
            }
        }
        if (decision.Accepted)
        {
            _tacticalQueue.Submit(channel, text, context);
            if (parsed.Order == TacticalOrder.Cancel) StopTacticalCommands("player_cancelled");
            else
            {
                _tacticalRoundIntent = decision.Plan;
                if (decision.Plan is { } acceptedPlan) CommitCustomSlots(acceptedPlan);
            }
            SubmitTacticalBuying(decision.Plan, player);
        }
        var feedback = decision.Accepted && parsed.Order == TacticalOrder.Playbook
            ? $"本回合采用战术：{_customPlaybook?.Tactics.FirstOrDefault(t => t.Id == parsed.TacticId)?.Name ?? parsed.TacticId}。"
            : decision.Message;
        player?.PrintToChat($" \x04{feedback}\x01");
        // Don't expose an accepted team's opening plan through all-chat.
        return HookResult.Handled;
    }

    private TacticalTarget[] BuildTacticalRoute(CommandPlan plan, int ordinal, bool includeHints = true)
    {
        var areas = CCSNavArea.GetAllNavAreas();
        if (areas.Count == 0) throw new InvalidOperationException("地图导航未加载");
        var target = Utilities.FindAllEntitiesByDesignerName<CBombTarget>("func_bomb_target")
            .FirstOrDefault(t => t.IsValid && t.IsBombSiteB == (plan.Site == "B"));
        if (target?.AbsOrigin is not { } origin) throw new InvalidOperationException("没有对应包点");
        var collision = target.Collision;
        var mins = collision.Mins; var maxs = collision.Maxs;
        if (target.AbsRotation is { } rotation && (Math.Abs(rotation.X) > .1 || Math.Abs(rotation.Y) > .1 || Math.Abs(rotation.Z) > .1))
            throw new InvalidOperationException("包点坐标需要适配");
        var siteCenter = new Vector(origin.X + (mins.X + maxs.X) / 2,
            origin.Y + (mins.Y + maxs.Y) / 2, origin.Z + (mins.Z + maxs.Z) / 2);
        var route = new List<TacticalTarget>();
        var hints = includeHints ? _tacticalRoutes.Maps.GetValueOrDefault(Server.MapName)?.GetValueOrDefault(plan.Side)?.GetValueOrDefault(plan.Site) ?? [] : [];
        foreach (var hint in hints)
        {
            var point = new Vector(hint[0], hint[1], hint[2]);
            var area = CCSNavArea.GetClosestNavArea(point, 96);
            if (area is null) throw new InvalidOperationException("中途节点不在导航面");
            var snapped = area.GetClosestPoint(point);
            route.Add(new(snapped.X, snapped.Y, snapped.Z, 120, false));
        }
        // Choose distinct walkable endpoints INSIDE the plant brush, not a box
        // roof or a random offset. Teammates share a lane, not a single pixel.
        var siteAreas = areas.Where(a =>
        {
            var c = a.Center;
            return c.X >= origin.X + mins.X + 16 && c.X <= origin.X + maxs.X - 16
                && c.Y >= origin.Y + mins.Y + 16 && c.Y <= origin.Y + maxs.Y - 16
                && c.Z >= origin.Z + mins.Z - 8 && c.Z <= origin.Z + maxs.Z;
        }).OrderBy(a => a.GetDistanceToPoint(siteCenter)).ThenBy(a => a.Id).Take(12).ToList();
        if (siteAreas.Count == 0) throw new InvalidOperationException("包点没有可用导航落点");
        var end = siteAreas[ordinal % siteAreas.Count].Center;
        route.Add(new(end.X, end.Y, end.Z, 48, true));
        return route.ToArray();
    }

    private void ResetTacticalCommands(string reason, bool newMap = false)
    {
        StopTacticalCommands(reason);
        ClearCustomSlots();
        _tacticalRoundIntent = null;
        if (newMap) _tacticalReleases.Clear();
        _tacticalEpoch++;
        if (newMap) _tacticalTipShown = false;
    }

    private void StopTacticalCommands(string reason)
    {
        ReleaseOpeningGuards();
        StopPostPlantTactic(reason);
        if (reason is "player_cancelled" or "round_end" or "match_end" or "unload") _tacticalRoundIntent = null;
        if (reason is "player_cancelled" or "round_end" or "match_end" or "unload") ClearCustomSlots();
        StopCustomTactic(reason);
        if (_tacticalPlan is not null) TacticalTrace(reason, new { active = _tacticalActors.Count });
        foreach (var actor in _tacticalActors.Values) ReleaseTacticalActor(actor, reason);
        _tacticalQueue.Reset(); _tacticalActors.Clear(); _tacticalPlan = null;
        // Cancel only a still-owned native MoveTo, never a combat/plant/defuse
        // state or another controller's task. No previous raw state is restored.
    }

    private void ReleaseTacticalActor(TacticalActor actor, string reason)
    {
        try
        {
            var p = Utilities.GetPlayerFromSlot(actor.Slot);
            if (p is not { IsValid: true } || ControllerId(p) != actor.Id || _ledger.GetValueOrDefault(actor.Id)?.IsBot != true
                || actor.Stage >= actor.Route.Length || _tacticalNavigator is null) return;
            var point = actor.Route[actor.Stage];
            if (!_tacticalNavigator.IsMovingTo(p, actor.Pawn, point.X, point.Y, point.Z)) return;
            if (_tacticalNavigator.TryIdle(p, actor.Pawn, out var result))
                TacticalTrace("native_move_cancelled", new { actor.Id, reason, result });
            else if (result == "native_combat_or_objective_retained" && reason != "unload")
                _tacticalReleases[actor.Slot] = new(actor.Id, actor.Slot, actor.Pawn, point, Server.CurrentTime + 5);
        }
        catch (Exception ex) { Logger.LogWarning("Tactical release skipped for {Slot}: {Error}", actor.Slot, ex.Message); }
    }

    private bool TacticalOwnsSide(string side) => _tacticalPlan?.Side == side;
    private bool TacticalOwnsActor(int slot, string side) => TacticalOwnsSide(side)
        || (_customTacticPlan?.Side == side && _customTacticActors.ContainsKey(slot))
        || (_postPlantPlan?.Side == side && _postPlantActors.ContainsKey(slot));

    private void ShowTacticalTip()
    {
        if (_tacticalTipShown || _request is not { Active: true, Observer: false } || InWarmup()) return;
        var human = AllSlots().FirstOrDefault(p => ControllerId(p) == _request.HumanPlayerId);
        if (human is null) return;
        human.PrintToChat(" \x04准备阶段输入 play <id> / 战术 <id>，或 rusha / rushb；default 取消，指令仅对本回合有效。\x01");
        _tacticalTipShown = true;
    }

    private void StartTacticalCommands()
    {
        if (!_roundLive || _resultWritten || InWarmup() || _request is not { Active: true, Observer: false }) return;
        var human = AllSlots().FirstOrDefault(p => ControllerId(p) == _request.HumanPlayerId);
        if (human is null) { _tacticalQueue.Reset(); ReleaseOpeningGuards(); return; }
        var side = human.Team == CsTeam.Terrorist ? "t" : human.Team == CsTeam.CounterTerrorist ? "ct" : "";
        ShowTacticalTip();
        var plan = _tacticalQueue.Take(_sessionNonce, _tacticalEpoch, side);
        if (plan is null) { ReleaseOpeningGuards(); return; }
        LaunchOpeningGuards();
        if (plan.Order == TacticalOrder.Playbook) { StartCustomTactic(plan, human); return; }
        try
        {
            _tacticalPlan = plan;
            _tacticalDeadline = Server.CurrentTime + 55;
            var targets = AllSlots().Where(p => ControllerId(p) is { } id && id != plan.IssuerId
                && _ledger.GetValueOrDefault(id)?.IsBot == true && LiveSide(p) == side
                && !p.ControllingBot && !p.HasBeenControlledByPlayerThisRound
                && p.PlayerPawn.Value is { IsValid: true, Health: > 0, Bot: not null }).ToList();
            // Prepare ALL routes before issuing any native task. A bad fourth
            // endpoint cannot leave three teammates following a rejected plan.
            var actors = targets.Select((p, i) => new TacticalActor(ControllerId(p)!, p.Slot,
                p.PlayerPawn.Value!.EntityHandle.Raw, BuildTacticalRoute(plan, i), Server.CurrentTime)
                { Health = p.PlayerPawn.Value!.Health }).ToArray();
            if (targets.Count == 0) throw new InvalidOperationException("没有可指挥的同队 Bot");
            foreach (var actor in actors)
            {
                // A new accepted command supersedes any delayed cancellation
                // for that slot, including the same pawn/goal after a restart.
                _tacticalReleases.Remove(actor.Slot);
                ReleaseMotionClip(actor.Slot, "player_tactic"); ReleaseCorner(actor.Slot, "player_tactic");
                ReleaseNatural(actor.Slot, "player_tactic"); ReleaseNaturalRecovery(actor.Slot, "player_tactic");
                ReleaseNaturalJumpBlock(actor.Slot);
                _tacticalActors[actor.Slot] = actor;
            }
            foreach (var actor in _tacticalActors.Values) IssueTacticalMove(actor, Utilities.GetPlayerFromSlot(actor.Slot)!.PlayerPawn.Value!);
            TacticalTrace("started", new { site = plan.Site, side, bots = targets.Count,
                routes = _tacticalActors.Values.Select(a => new { a.Id, a.Slot, a.Route }) });
        }
        catch (Exception ex)
        {
            StopTacticalCommands("start_failed");
            human.PrintToChat($" \x02指挥未启动：{ex.Message}\x01");
        }
    }

    private void IssueTacticalMove(TacticalActor actor, CCSPlayerPawn pawn)
    {
        var point = actor.Route[actor.Stage];
        var player = Utilities.GetPlayerFromSlot(actor.Slot);
        if (player is null) return;
        if (!_tacticalNavigator!.TryMoveTo(player, actor.Pawn, point.X, point.Y, point.Z, out var reason))
        {
            // A native combat/utility action at round start is a temporary
            // handoff, not a failure of every teammate's opening command.
            if (reason != "native_combat_or_objective_retained") throw new InvalidOperationException(reason);
            actor.YieldUntil = Server.CurrentTime + 1;
            actor.State = "native_action";
            return;
        }
        actor.NextIssue = Server.CurrentTime + .9f;
        OpeningPathCommitted(actor.Slot);
        if (actor.State != "moving")
        {
            actor.State = "moving";
            TacticalTrace("move", new { actor.Id, actor.Slot, actor.Stage, target = point });
        }
    }

    private void TickTacticalCommands()
    {
        TickOpeningGuards();
        TickPostPlantTactic();
        TickCustomTactic();
        if (_tacticalReleases.Count > 0 && Server.TickCount % 16 == 0) TickTacticalReleases();
        if (_tacticalPlan is not { } plan || _tacticalActors.Count == 0) return;
        if (!_roundLive || _resultWritten || InWarmup() || Server.CurrentTime > _tacticalDeadline
            || plan.MatchNonce != _sessionNonce || plan.Round != _tacticalEpoch)
        { StopTacticalCommands("round_inactive_or_deadline"); return; }
        // Four teammate checks at 4 Hz, not whole-map raycasts/path searches.
        if (Server.TickCount % 16 != 0) return;
        try
        {
            foreach (var actor in _tacticalActors.Values.ToArray())
            {
                var p = Utilities.GetPlayerFromSlot(actor.Slot); var pawn = p?.PlayerPawn.Value;
                if (p is not { IsValid: true } || ControllerId(p) != actor.Id || LiveSide(p) != plan.Side
                    || p.ControllingBot || p.HasBeenControlledByPlayerThisRound
                    || pawn is not { IsValid: true, Health: > 0, Bot: not null, AbsOrigin: not null }
                    || pawn.EntityHandle.Raw != actor.Pawn)
                { _tacticalActors.Remove(actor.Slot); TacticalTrace("removed_death_takeover_disconnect", new { actor.Id }); continue; }
                var now = Server.CurrentTime;
                var bot = pawn.Bot; var weapon = pawn.WeaponServices?.ActiveWeapon.Value?.DesignerName ?? "";
                var combat = bot.IsEnemyVisible || bot.IsAttacking || pawn.Health < actor.Health
                    || pawn.BlindUntilTime > now || weapon.Contains("grenade") || weapon.Contains("flashbang")
                    || weapon.Contains("molotov") || weapon.Contains("c4") || pawn.IsDefusing;
                actor.Health = pawn.Health;
                if (combat)
                {
                    actor.YieldUntil = now + 1; actor.LastProgress = now;
                    if (actor.State != "native_action")
                    { actor.State = "native_action"; TacticalTrace("combat_or_objective", new { actor.Id, actor.Stage }); }
                    continue;
                }
                if (now < actor.YieldUntil) continue;
                var goal = actor.Route[actor.Stage]; var pos = pawn.AbsOrigin;
                if (goal.Reached(pos) && (!goal.Site || pawn.InBombZone))
                {
                    if (actor.Stage == actor.Route.Length - 1) ReleaseTacticalActor(actor, "site_arrived");
                    actor.Stage++; actor.BestDistance = float.MaxValue; actor.LastProgress = now;
                    TacticalTrace("waypoint_reached", new { actor.Id, stage = actor.Stage - 1 });
                    if (actor.Stage >= actor.Route.Length) { _tacticalActors.Remove(actor.Slot); continue; }
                    actor.NextIssue = 0; actor.State = "next_waypoint";
                }
                goal = actor.Route[actor.Stage];
                var distance = (pos.X - goal.X) * (pos.X - goal.X) + (pos.Y - goal.Y) * (pos.Y - goal.Y);
                if (distance + 400 < actor.BestDistance) { actor.BestDistance = distance; actor.LastProgress = now; }
                if (now - actor.LastProgress > 10)
                { ReleaseTacticalActor(actor, "stalled"); _tacticalActors.Remove(actor.Slot); TacticalTrace("stalled_native_fallback", new { actor.Id, actor.Stage }); continue; }
                // Don't continuously restart native MoveTo/path generation. A
                // completed/interrupted native task can be resumed after combat.
                if (now >= actor.NextIssue)
                {
                    if (!_tacticalNavigator!.IsMovingTo(p, actor.Pawn, goal.X, goal.Y, goal.Z))
                        IssueTacticalMove(actor, pawn);
                    else
                    {
                        if (!_tacticalNavigator.TryKeepRushing(p, actor.Pawn, out var reason)
                            && reason != "native_combat_or_objective_retained")
                            throw new InvalidOperationException(reason);
                        actor.NextIssue = now + .9f;
                    }
                }
            }
            if (_tacticalActors.Count == 0) StopTacticalCommands("all_arrived_or_released");
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "Player tactical opening stopped; native AI retained");
            StopTacticalCommands("execution_error");
            AllSlots().FirstOrDefault(p => ControllerId(p) == plan.IssuerId)?.PrintToChat(" \x02指挥执行遇到技术错误，已停止追加指令；队友继续原生 AI。控制台输入 css_tactics 查看接口状态。\x01");
        }
    }

    private void TickTacticalReleases()
    {
        foreach (var release in _tacticalReleases.Values.ToArray())
        {
            try
            {
                var p = Utilities.GetPlayerFromSlot(release.Slot); var goal = release.Target;
                if (Server.CurrentTime > release.Expires || _tacticalActors.ContainsKey(release.Slot) || _customTacticActors.ContainsKey(release.Slot)
                    || _postPlantActors.ContainsKey(release.Slot)
                    || p is not { IsValid: true } || ControllerId(p) != release.Id
                    || _ledger.GetValueOrDefault(release.Id)?.IsBot != true || _tacticalNavigator is null
                    || !_tacticalNavigator.IsMovingTo(p, release.Pawn, goal.X, goal.Y, goal.Z))
                { _tacticalReleases.Remove(release.Slot); continue; }
                if (_tacticalNavigator.TryIdle(p, release.Pawn, out var result))
                {
                    _tacticalReleases.Remove(release.Slot);
                    TacticalTrace("native_move_cancelled_after_combat", new { release.Id, result });
                }
                else if (result != "native_combat_or_objective_retained") _tacticalReleases.Remove(release.Slot);
            }
            catch (Exception ex)
            {
                _tacticalReleases.Remove(release.Slot);
                Logger.LogWarning("Deferred tactical release skipped: {Error}", ex.Message);
            }
        }
    }

    private void TacticalTrace(string kind, object data) => TraceIdentity("tactic_" + kind, data);
}
