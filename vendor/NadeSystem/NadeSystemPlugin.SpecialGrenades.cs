using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Core.Capabilities;
using CounterStrikeSharp.API.Modules.Commands;
using CounterStrikeSharp.API.Modules.Cvars;
using CounterStrikeSharp.API.Modules.Events;
using CounterStrikeSharp.API.Modules.Memory.DynamicFunctions;
using CounterStrikeSharp.API.Modules.Timers;
using CounterStrikeSharp.API.Modules.UserMessages;
using CounterStrikeSharp.API.Modules.Utils;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace NadeSystem;

public partial class NadeSystemPlugin : BasePlugin
{
    // ═══════════════════════════════════════════════════════════
    //  Special Nades
    // ═══════════════════════════════════════════════════════════
    // Defuse smoke/flash
    private bool TrySpawnInstantGrenade(CCSPlayerController bot, Vector spawnPos,
        string gtype, Vector? velocity = null, Action<bool>? completed = null)
    {
        if (!Utilities.GetPlayers().Any(p => p.IsValid && p.PawnIsAlive
            && p.TeamNum is 2 or 3 && p.TeamNum != bot.TeamNum)) return false;
        var vel = velocity ?? new Vector(0f, 0f, 0f);
        var grenade = new GrenadeData {
            Id = "career-instant-" + Guid.NewGuid().ToString("N"), GrenadeType = gtype,
            ProjectilePosition = new Vec3 { X = spawnPos.X, Y = spawnPos.Y, Z = spawnPos.Z },
            ProjectileVelocity = new Vec3 { X = vel.X, Y = vel.Y, Z = vel.Z },
            LandingPosition = new Vec3 { X = spawnPos.X, Y = spawnPos.Y, Z = spawnPos.Z }
        };
        return TryQueueCareerGrenade(bot, grenade, completed: completed);
    }

    // * Triggers defensive smoke or flash support during a defuse
    private HookResult OnBombBeginDefuse(EventBombBegindefuse @event, GameEventInfo info)
    {
        var bot = @event.Userid;
        if (bot == null || !bot.IsValid || !bot.IsBot) return HookResult.Continue;
        if (bot.HasBeenControlledByPlayerThisRound) return HookResult.Continue;

        var pawn = bot.PlayerPawn?.Value;
        if (pawn == null || !pawn.IsValid || !bot.PawnIsAlive)
            return HookResult.Continue;

        var pos = pawn.AbsOrigin;
        if (pos == null) return HookResult.Continue;
        var spawnPos = new Vector(pos.X, pos.Y, pos.Z + 5f);

        // Defuse smoke
        if (!_defuseSmokeUsed)
        {
            bool hasDefuser = false;
            if (pawn.ItemServices != null
                && pawn.ItemServices.Handle != nint.Zero)
            {
                hasDefuser = new CCSPlayer_ItemServices(pawn.ItemServices.Handle).HasDefuser;
            }

            if (hasDefuser || Random.Shared.NextDouble() < 0.33)
            {
                _defuseSmokeUsed = TrySpawnInstantGrenade(bot, spawnPos, "smoke", completed: ok => { if (!ok) _defuseSmokeUsed = false; });
            }
        }

        // Defuse flash
        if (!_defuseFlashUsed)
        {
            if (Random.Shared.NextDouble() < 0.20)
            {
                var flashVel = new Vector(0f, 0f, -800f);
                _defuseFlashUsed = TrySpawnInstantGrenade(bot, spawnPos, "flash", flashVel,
                    ok => { if (!ok) _defuseFlashUsed = false; });
            }
        }

        return HookResult.Continue;
    }

    // Plant smoke
    // * Triggers smoke support when a bot starts planting
    private HookResult OnBombBeginPlant(EventBombBeginplant @event, GameEventInfo info)
    {
        if (_plantSmokeUsed) return HookResult.Continue;

        var bot = @event.Userid;
        if (bot == null || !bot.IsValid || !bot.IsBot) return HookResult.Continue;
        if (bot.HasBeenControlledByPlayerThisRound) return HookResult.Continue;

        if (Random.Shared.NextDouble() >= 0.33) return HookResult.Continue;

        var pawn = bot.PlayerPawn?.Value;
        if (pawn == null || !pawn.IsValid || !bot.PawnIsAlive)
            return HookResult.Continue;

        var pos = pawn.AbsOrigin;
        if (pos == null) return HookResult.Continue;

        _plantSmokeUsed = TrySpawnInstantGrenade(bot, new Vector(pos.X, pos.Y, pos.Z + 5f), "smoke",
            completed: ok => { if (!ok) _plantSmokeUsed = false; });
        return HookResult.Continue;
    }

    // * Dispatches damage-driven grenade reactions
    private HookResult OnPlayerHurt(EventPlayerHurt @event, GameEventInfo info)
    {
        HandleMolotovEscape(@event);
        HandleRetaliationHE(@event);

        return HookResult.Continue;
    }
    // Put out the fire
    // * Uses smoke to help a bot escape sustained fire damage
    private void HandleMolotovEscape(EventPlayerHurt @event)
    {
        if (_botNadesMode == "off") return;
        var victim = @event.Userid;
        if (victim == null || !victim.IsValid || !victim.IsBot) return;
        if (victim.HasBeenControlledByPlayerThisRound) return;

        var pawn = victim.PlayerPawn?.Value;
        if (pawn == null || !pawn.IsValid || !victim.PawnIsAlive) return;

        string weapon = @event.Weapon ?? "";
        bool isMolotovDmg = weapon.Contains("inferno", StringComparison.OrdinalIgnoreCase)
                         || weapon.Contains("molotov", StringComparison.OrdinalIgnoreCase)
                         || weapon.Contains("incgrenade", StringComparison.OrdinalIgnoreCase);
        if (!isMolotovDmg)
        {
            _botMolotovDmgStart.Remove((uint)victim.Index);
            return;
        }

        int teamNum = victim.TeamNum;
        if (_molotovEscapeSmokeCooldown.TryGetValue(teamNum, out float expiry)
            && Server.CurrentTime < expiry) return;

        uint idx = (uint)victim.Index;
        float now = Server.CurrentTime;

        if (!_botMolotovDmgStart.TryGetValue(idx, out float start))
        {
            _botMolotovDmgStart[idx] = now;
            return;
        }

        if (now - start < 0.3f) return;

        _botMolotovDmgStart.Remove(idx);


        var pos = pawn.AbsOrigin;
        if (pos == null) return;
        if (TrySpawnInstantGrenade(victim, new Vector(pos.X, pos.Y, pos.Z + 5f), "smoke",
            completed: ok => { if (!ok) _molotovEscapeSmokeCooldown.Remove(teamNum); }))
            _molotovEscapeSmokeCooldown[teamNum] = now + 20f;
    }
    // Revenge grenade
    // * Selects and throws a retaliatory explosive grenade
    private void HandleRetaliationHE(EventPlayerHurt @event)
    {
        if (_botNadesMode == "off") return;
        var victim = @event.Userid;
        if (victim == null || !victim.IsValid || !victim.IsBot) return;
        if (victim.HasBeenControlledByPlayerThisRound) return;

        var victimPawn = victim.PlayerPawn?.Value;
        if (victimPawn == null || !victimPawn.IsValid || !victim.PawnIsAlive) return;

        var attacker = @event.Attacker;
        if (attacker == null || !attacker.IsValid || attacker.IsBot || !attacker.PawnIsAlive) return;

        if (attacker.TeamNum == victim.TeamNum) return;   // only retaliate against the enemies
        if (_roundOver) return;

        // No retaliation HE/molotov within 1s of victim firing
        if (FiredRecently(victim, 1f)) return;

        string weapon = @event.Weapon ?? "";
        bool isHE      = weapon.Contains("hegrenade",  StringComparison.OrdinalIgnoreCase);
        bool isMolotov = weapon.Contains("molotov",    StringComparison.OrdinalIgnoreCase)
                    || weapon.Contains("incgrenade",  StringComparison.OrdinalIgnoreCase)
                    || weapon.Contains("inferno",     StringComparison.OrdinalIgnoreCase);
        if (!isHE && !isMolotov) return;

        var atkPos = GetActiveLivePawn(attacker)?.AbsOrigin;
        if (atkPos == null) return;

        string map = Server.MapName;
        int teamNum = victim.TeamNum;
        // less / normal / more mode: retaliation cooldown per team (7s)
        if (_botNadesMode == "normal" || _botNadesMode == "more" || _botNadesMode == "less")
        {
            if (_retaliationCooldown.TryGetValue(teamNum, out float cdExpiry)
                && Server.CurrentTime < cdExpiry) return;
        }
        // Build candidate list (single pass: filter then sort)
        // primary  : satisfies both direction and distance check  -> first
        // secondary: nearest projectilePosition to victim         -> ascending
        var vPosForSort = victimPawn.AbsOrigin;
        var candidates = _mapNades
            .Where(g =>
            {
                string gt = g.GrenadeType; // lowercase since LoadDb
                if (gt != "he" && gt != "molotov" && gt != "incgrenade") return false;
                float d = Dist3D(atkPos.X, atkPos.Y, atkPos.Z,
                                 g.LandingPosition.X, g.LandingPosition.Y, g.LandingPosition.Z);
                if (d > 200f) return false;
                if (IsOnCooldown(g.Id)) return false;
                return true;
            })
            .OrderByDescending(g => FacesThrowDirection(victimPawn, g) ? 1 : 0)
            .ThenBy(g => vPosForSort == null ? 0f :
                Dist3D(vPosForSort.X, vPosForSort.Y, vPosForSort.Z,
                       g.ProjectilePosition.X, g.ProjectilePosition.Y, g.ProjectilePosition.Z))
            .ToList();

        foreach (var g in candidates)
        {
            if (TryQueueCareerGrenade(victim, g, completed: ok =>
                { if (!ok) _retaliationCooldown.Remove(teamNum); }))
            {
                _retaliationCooldown[teamNum] = Server.CurrentTime + 7f;
                break;
            }
        }
    }
}
