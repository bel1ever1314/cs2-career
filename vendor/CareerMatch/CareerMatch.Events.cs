using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    private readonly Dictionary<string, string?> _pendingControls = [];
    private int _identityTraceCount;

    private string? ControllerId(CCSPlayerController? player) =>
        player is { IsValid: true } && _slotIds.TryGetValue(player.Slot, out var id) ? id : null;

    private List<ControlSnapshot> ControlSnapshots()
    {
        var result = new List<ControlSnapshot>();
        foreach (var player in AllSlots())
        {
            var id = ControllerId(player);
            if (id is null || !_ledger.TryGetValue(id, out var row)) continue;
            try
            {
                result.Add(new(id, player.PlayerPawn.Value?.EntityHandle.Raw ?? 0,
                    ControllerId(player.OriginalControllerOfCurrentPawn.Value),
                    player.ControllingBot, player.HasBeenControlledByPlayerThisRound,
                    row.IsBot, row.Team, row.RoundDead));
            }
            catch (Exception ex) { TraceIdentity("schema_error", new { id, error = ex.Message }); }
        }
        return result;
    }

    private void CaptureRoundPawns()
    {
        if (!_roundLive) return;
        foreach (var p in ControlSnapshots())
            if (!p.Dead && !p.Controlling && !p.WasControlled
                && (p.Original is null || p.Original == p.Id))
                _actors.RememberPawn(p.Pawn, p.Id);
    }

    private HookResult OnFreezeEnd(EventRoundFreezeEnd ev, GameEventInfo info)
    {
        CaptureRoundPawns();
        return HookResult.Continue;
    }

    private void TraceIdentity(string kind, object data)
    {
        // Store actual adapter evidence, not just counters from a pure unit test.
        // No account identifiers; trace files are never included in public ZIPs.
        if (_identityTraceCount++ >= 5000) return;
        try
        {
            var directory = Path.Combine(ModuleDirectory, "identity_traces");
            Directory.CreateDirectory(directory);
            var key = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
                System.Text.Encoding.UTF8.GetBytes(_sessionNonce)))[..16];
            var line = System.Text.Json.JsonSerializer.Serialize(new {
                version = ModuleVersion, nonce = _sessionNonce, round = _liveRounds,
                tick = Server.TickCount, kind, data });
            File.AppendAllText(Path.Combine(directory, key + ".jsonl"), line + "\n");
        }
        catch (Exception ex) { Logger.LogWarning("Identity trace write failed: {Error}", ex.Message); }
    }

    private bool ResolveControl(string humanId, string? eventBotId, string reason)
    {
        var live = ControlSnapshots();
        var human = live.SingleOrDefault(p => p.Id == humanId);
        var owner = human is null ? null : _actors.PawnOwner(human.Pawn);
        var botId = TakeoverResolver.Resolve(humanId, live, owner, eventBotId);
        TraceIdentity(reason, new { humanId, eventBotId, pawnOwner = owner, resolved = botId, live });
        if (botId is null) return false;
        // A valid round-start pawn is immutable. Do not relabel the dead human
        // pawn if PlayerPawn has not caught up with the engine's controller swap.
        var pawn = human!.Pawn;
        if (owner is not null && owner != botId) pawn = 0;
        _actors.Takeover(humanId, botId, pawn);
        _pendingControls.Remove(humanId);
        if (!_takeovers.Any(t => t.Round == _liveRounds && t.ControllerId == humanId && t.PlayerId == botId))
        {
            _takeovers.Add(new TakeoverRecord(_liveRounds, humanId, botId));
            // Keep the audit record, but do not clutter the in-game chat.
        }
        return true;
    }

    private LedgerRow? EventRow(CCSPlayerController? player, string weapon = "", bool required = true)
    {
        var own = ControllerId(player);
        if (own is null || player is null) return null;
        if (_pendingControls.TryGetValue(own, out var eventBot))
            ResolveControl(own, eventBot, "resolve_before_event");
        else if (_ledger.TryGetValue(own, out var ownRow) && !ownRow.IsBot && ownRow.RoundDead)
        {
            // Recovery if the takeover signal itself was missed. A controller's
            // own name/Steam identity remains untouched by this body binding.
            try
            {
                if (player.ControllingBot && _actors.Actor(own) == own)
                {
                    _actors.AwaitTakeover(own);
                    _pendingControls[own] = null;
                    ResolveControl(own, null, "schema_recovery");
                }
            }
            catch { _actors.AwaitTakeover(own); }
        }
        // OriginalController on a swapped BOT may point back to the human.
        // It is evidence for the resolver, never an unconditional event owner.
        var actor = _actors.Actor(own);
        var projectile = ProjectileType(weapon);
        if (projectile.Length > 0) actor = _actors.ProjectileActor(own, projectile);
        // Being dead is not an identity failure: delayed projectile/contact
        // damage can arrive after death. Pending takeover still resolves null.
        if (actor is null || !_ledger.TryGetValue(actor, out var row))
        {
            TraceIdentity("identity_rejected", new { controller = own, actor, weapon, required,
                currentActor = _actors.Actor(own), pending = _pendingControls.ContainsKey(own) });
            if (required)
                _health.StatisticsError = $"事件归属未确认：{_ledger[own].Name} / {(weapon.Length > 0 ? weapon : "角色事件")}，请保留 identity_traces 日志";
            return null;
        }
        return row;
    }

    private static string ProjectileType(string weapon) => weapon.Replace("weapon_", "") switch
    {
        "hegrenade" => "hegrenade",
        "molotov" or "incgrenade" or "inferno" => "fire",
        "flashbang" => "flashbang",
        "smokegrenade" => "smokegrenade",
        "decoy" => "decoy",
        _ => "",
    };

    private HookResult OnBotTakeover(EventBotTakeover ev, GameEventInfo info)
    {
        if (!_roundLive || InWarmup()) return HookResult.Continue;
        BindPlayerSlots();
        var humanId = ControllerId(ev.Userid);
        var eventBotId = ControllerId(ev.Botid);
        if (humanId is null || !_ledger.TryGetValue(humanId, out var human) || human.IsBot)
        {
            _health.StatisticsError = "接管事件的真人身份不在本场阵容中";
            TraceIdentity("takeover_invalid_controller", new { humanId, eventBotId });
            return HookResult.Continue;
        }
        _actors.AwaitTakeover(humanId);
        _pendingControls[humanId] = eventBotId;
        if (!ResolveControl(humanId, eventBotId, "bot_takeover"))
        {
            // Native controller fields can settle one frame after the event.
            // Capture only managed IDs, never use a disposed GameEvent later.
            var round = _liveRounds;
            var nonce = _sessionNonce;
            Server.NextFrame(() =>
            {
                if (!_roundLive || round != _liveRounds || nonce != _sessionNonce
                    || !_pendingControls.ContainsKey(humanId)) return;
                if (!ResolveControl(humanId, eventBotId, "takeover_next_frame"))
                {
                    _health.StatisticsError = "无法唯一确认接管的选手，已暂停该角色记账并阻止录入；请保留接管日志";
                    Server.PrintToChatAll($" \x02CareerMatch：{_health.StatisticsError}\x01");
                }
            });
        }
        return HookResult.Continue;
    }

    private HookResult OnGrenadeThrown(EventGrenadeThrown ev, GameEventInfo info)
    {
        if (!_roundLive || InWarmup()) return HookResult.Continue;
        BindPlayerSlots();
        var controller = ControllerId(ev.Userid);
        var actor = EventRow(ev.Userid, required: false);
        var weapon = ProjectileType(ev.Weapon);
        if (controller is not null && actor is not null && weapon.Length > 0)
            _actors.Thrown(controller, weapon, actor.PlayerId);
        TraceIdentity("grenade_thrown", new { controller, actor = actor?.PlayerId, weapon, rawWeapon = ev.Weapon });
        return HookResult.Continue;
    }

    private HookResult OnPlayerBlind(EventPlayerBlind ev, GameEventInfo info)
    {
        if (!_roundLive || InWarmup()) return HookResult.Continue;
        BindPlayerSlots();
        // A flash notification is contribution evidence, not itself an assist
        // or any counted stat. Only reject if a later scored assist is ambiguous.
        var victim = EventRow(ev.Userid, required: false);
        var actor = EventRow(ev.Attacker, "flashbang", required: false);
        var controller = ControllerId(ev.Attacker);
        if (victim is not null && actor is not null && controller is not null && victim.Team != actor.Team)
            _actors.Support(victim.PlayerId, controller, actor.PlayerId, true);
        return HookResult.Continue;
    }

    private HookResult OnPlayerHurt(EventPlayerHurt ev, GameEventInfo info)
    {
        if (!_roundLive || InWarmup()) return HookResult.Continue;
        if (ev.DmgHealth <= 0) return HookResult.Continue;
        BindPlayerSlots();
        var victim = EventRow(ev.Userid);
        var attacker = EventRow(ev.Attacker, ev.Weapon);
        if (victim is null || attacker is null || victim == attacker || victim.Team == attacker.Team)
            return HookResult.Continue;
        attacker.Damage += Math.Max(0, ev.DmgHealth);
        TraceIdentity("hurt", new { controller = ControllerId(ev.Attacker), actor = attacker.PlayerId,
            victim = victim.PlayerId, damage = ev.DmgHealth, weapon = ev.Weapon });
        if (ControllerId(ev.Attacker) is { } controller)
            _actors.Support(victim.PlayerId, controller, attacker.PlayerId);
        return HookResult.Continue;
    }

    private HookResult OnPlayerDeath(EventPlayerDeath ev, GameEventInfo info)
    {
        if (!_roundLive || InWarmup()) return HookResult.Continue;
        BindPlayerSlots();
        var victim = EventRow(ev.Userid);
        if (victim is null) return HookResult.Continue;
        if (victim.RoundDead)
        {
            _health.StatisticsError = "同一选手在单回合重复死亡，已阻止异常战绩录入";
            return HookResult.Continue;
        }
        var attacker = EventRow(ev.Attacker, ev.Weapon);
        // Resolve before setting RoundDead: a genuine suicide has the same
        // attacker and victim, not an unexplained shot from an already dead row.
        victim.Deaths++;
        victim.RoundDead = true;
        var legalKill = attacker is not null && attacker != victim && attacker.Team != victim.Team;
        TraceIdentity("death", new { controller = ControllerId(ev.Attacker), actor = attacker?.PlayerId,
            victimController = ControllerId(ev.Userid), victim = victim.PlayerId, legalKill, weapon = ev.Weapon });
        if (legalKill)
        {
            attacker!.Kills++;
            attacker.RoundKill = true;
            if (!_openingRecorded)
            {
                attacker.OpeningKills++;
                victim.OpeningDeaths++;
                _openingRecorded = true;
            }
            var now = Server.TickedTime;
            foreach (var pending in _pendingTrades.Where(x => x.KillerId == victim.PlayerId
                && now - x.At <= 5.0 && x.VictimTeam == attacker.Team).ToList())
            {
                if (_ledger.TryGetValue(pending.VictimId, out var traded))
                {
                    traded.RoundTraded = true;
                    traded.TradedDeaths++;
                }
            }
            _pendingTrades.Add(new PendingTrade(victim.PlayerId, attacker.PlayerId, victim.Team, now));
        }
        if (legalKill && ControllerId(ev.Assister) is { } assistController)
        {
            var assistId = _actors.Assister(victim.PlayerId, assistController, ev.Assistedflash);
            if (assistId is null)
                _health.StatisticsError = "接管前后的助攻贡献无法唯一归属，保留事件等待核查";
            else if (_ledger.TryGetValue(assistId, out var assister)
                && assister != attacker && assister != victim && assister.Team != victim.Team)
            {
                assister.Assists++;
                assister.RoundAssist = true;
            }
        }
        return HookResult.Continue;
    }
}
