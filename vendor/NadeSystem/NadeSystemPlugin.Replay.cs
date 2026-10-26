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
    //  Grenade Replay
    // ═══════════════════════════════════════════════════════════

    private void TryReplay(CCSPlayerController bot, GrenadeData g,
        List<CCSPlayerController> allControllers, ulong targets = 0)
        => TryQueueCareerGrenade(bot, g, targets);

    // * Creates a grenade projectile with the recorded position and velocity
    private void SpawnProjectile(CCSPlayerController bot, GrenadeData g, Action<bool>? completed = null, Func<bool>? stillValid = null)
    {
        // ── Item definition indices (weapon_def_index) ────────────
        // The native Create() functions require the item def index.
        static ushort GetItemIndex(string t) => t switch
        {
            "smoke"   => 45,
            "flash"   => 43,
            "he"      => 44,
            _         => 45,
        };

        var gtype    = g.GrenadeType.ToLowerInvariant();
        var origin   = new Vector(g.ProjectilePosition.X,
                                  g.ProjectilePosition.Y,
                                  g.ProjectilePosition.Z);
        var velocity = new Vector(g.ProjectileVelocity.X,
                                  g.ProjectileVelocity.Y,
                                  g.ProjectileVelocity.Z);

        // Angles derived from velocity (nade model orientation only, not trajectory)
        float yaw   =  MathF.Atan2(velocity.Y, velocity.X) * (180f / MathF.PI);
        float hDist =  MathF.Sqrt(velocity.X * velocity.X + velocity.Y * velocity.Y);
        float pitch = -MathF.Atan2(velocity.Z, hDist)      * (180f / MathF.PI);
        var angles  =  new QAngle(pitch, yaw, 0f);

        var teamNum  = bot.TeamNum;
        var itemDef  = (int)GetItemIndex(gtype);

        int generation = _careerBudget.Generation;
        Server.NextFrame(() =>
        {
            bool spawned = false;
            try
            {
                if (generation != _careerBudget.Generation || _roundOver
                    || (stillValid != null && !stillValid())) return;
                var botPawn = bot.PlayerPawn?.Value;
                if (botPawn == null || !botPawn.IsValid)
                {
                    Server.PrintToConsole("[NadeSystem] bot pawn invalid, skipping replay");
                    return;
                }

                // ── FLASH — CreateEntityByName is sufficient ───────────
                // No native factory needed.
                if (gtype == "flash")
                {
                    var flash = Utilities.CreateEntityByName<CFlashbangProjectile>(
                        "flashbang_projectile");
                    if (flash == null)
                    {
                        Server.PrintToConsole("[NadeSystem] flash CreateEntityByName null");
                        return;
                    }
                    flash.TeamNum             = teamNum;
                    flash.Thrower.Raw         = botPawn.EntityHandle.Raw;
                    flash.OriginalThrower.Raw = botPawn.EntityHandle.Raw;
                    flash.OwnerEntity.Raw     = botPawn.EntityHandle.Raw;
                    flash.InitialPosition.X   = origin.X;
                    flash.InitialPosition.Y   = origin.Y;
                    flash.InitialPosition.Z   = origin.Z;
                    flash.InitialVelocity.X   = velocity.X;
                    flash.InitialVelocity.Y   = velocity.Y;
                    flash.InitialVelocity.Z   = velocity.Z;
                    flash.Elasticity          = 0.33f;
                    flash.Teleport(origin, angles, velocity);
                    flash.DispatchSpawn();
                    spawned = true;
                    flash.Teleport(origin, angles, velocity);
                    AnnounceGrenadeThrow(bot, gtype);
                    // Flash Immunity
                    float immuneUntil = Server.CurrentTime + 2f;
                    foreach (var teammate in Utilities
                        .FindAllEntitiesByDesignerName<CCSPlayerController>("cs_player_controller"))
                    {
                        if (!teammate.IsValid || !teammate.IsBot) continue;
                        if ((int)teammate.TeamNum != (int)bot.TeamNum) continue;
                        _botFlashImmunityUntil[(uint)teammate.Index] = immuneUntil;
                    }
                    Server.PrintToConsole(
                        $"[NadeSystem] Replayed [flash] id={g.Id[..8]}... " +
                        $"bot=[{bot.PlayerName}] " +
                        $"origin=({origin.X:F0},{origin.Y:F0},{origin.Z:F0}) " +
                        $"vel=({velocity.X:F1},{velocity.Y:F1},{velocity.Z:F1})");
                    return;
                }

                // ── DECOY — CreateEntityByName ─────────────────────────────
                if (gtype == "decoy")
                {
                    var decoy = Utilities.CreateEntityByName<CFlashbangProjectile>("flashbang_projectile");
                    if (decoy == null)
                    {
                        Server.PrintToConsole("[NadeSystem] decoy CreateEntityByName null");
                        return;
                    }
                    decoy.TeamNum             = teamNum;
                    decoy.Thrower.Raw         = botPawn.EntityHandle.Raw;
                    decoy.OriginalThrower.Raw = botPawn.EntityHandle.Raw;
                    decoy.OwnerEntity.Raw     = botPawn.EntityHandle.Raw;
                    decoy.InitialPosition.X   = origin.X;
                    decoy.InitialPosition.Y   = origin.Y;
                    decoy.InitialPosition.Z   = origin.Z;
                    decoy.InitialVelocity.X   = velocity.X;
                    decoy.InitialVelocity.Y   = velocity.Y;
                    decoy.InitialVelocity.Z   = velocity.Z;
                    decoy.Elasticity          = 0.33f;
                    decoy.Teleport(origin, angles, velocity);
                    decoy.DispatchSpawn();
                    spawned = true;
                    decoy.Teleport(origin, angles, velocity);
                    // Don't detonate
                    StartDecoyFlashLoop(bot, g, decoy, teamNum, angles);
                    AnnounceGrenadeThrow(bot, gtype);
                    Server.PrintToConsole(
                        $"[NadeSystem] Replayed [decoy] id={g.Id[..8]}... " +
                        $"bot=[{bot.PlayerName}] " +
                        $"origin=({origin.X:F0},{origin.Y:F0},{origin.Z:F0})");
                    return;
                }

                // ── SMOKE — native CSmokeGrenadeProjectile::Create() ───
                if (gtype == "smoke")
                {
                    var smoke = _smokeCreate.Invoke(
                        origin.Handle,
                        origin.Handle,
                        velocity.Handle,
                        velocity.Handle,
                        botPawn.Handle,
                        itemDef,
                        teamNum);
                    if (smoke == null || !smoke.IsValid)
                    {
                        Server.PrintToConsole("[NadeSystem] smoke native Create returned null");
                        return;
                    }
                    spawned = true;
                    smoke.TeamNum             = teamNum;
                    smoke.Thrower.Raw         = botPawn.EntityHandle.Raw;
                    smoke.OriginalThrower.Raw = botPawn.EntityHandle.Raw;
                    smoke.OwnerEntity.Raw     = botPawn.EntityHandle.Raw;
                    AnnounceGrenadeThrow(bot, gtype);
                    Server.PrintToConsole(
                        $"[NadeSystem] Replayed [smoke] id={g.Id[..8]}... " +
                        $"bot=[{bot.PlayerName}] " +
                        $"origin=({origin.X:F0},{origin.Y:F0},{origin.Z:F0}) " +
                        $"vel=({velocity.X:F1},{velocity.Y:F1},{velocity.Z:F1})");
                    return;
                }

                // ── HE — native CHEGrenadeProjectile::Create() ────────
                if (gtype == "he")
                {
                    var he = _heCreate.Invoke(
                        origin.Handle,
                        origin.Handle,
                        velocity.Handle,
                        velocity.Handle,
                        botPawn.Handle,
                        itemDef);
                    if (he == null || !he.IsValid)
                    {
                        Server.PrintToConsole("[NadeSystem] HE native Create returned null");
                        return;
                    }
                    spawned = true;
                    he.TeamNum             = teamNum;
                    he.Thrower.Raw         = botPawn.EntityHandle.Raw;
                    he.OriginalThrower.Raw = botPawn.EntityHandle.Raw;
                    he.OwnerEntity.Raw     = botPawn.EntityHandle.Raw;
                    AnnounceGrenadeThrow(bot, gtype);
                    Server.PrintToConsole(
                        $"[NadeSystem] Replayed [he] id={g.Id[..8]}... " +
                        $"bot=[{bot.PlayerName}] " +
                        $"origin=({origin.X:F0},{origin.Y:F0},{origin.Z:F0}) " +
                        $"vel=({velocity.X:F1},{velocity.Y:F1},{velocity.Z:F1})");
                    return;
                }

                // ── MOLOTOV — native CMolotovProjectile::Create() ─────
                if (gtype is "molotov" or "incgrenade")
                {
                    int molotovItemDef = (teamNum == (int)CsTeam.CounterTerrorist) ? 48 : 46;

                    var molotov = _molotovCreate.Invoke(
                        origin.Handle,
                        origin.Handle,
                        velocity.Handle,
                        velocity.Handle,
                        botPawn.Handle,
                        molotovItemDef);
                    if (molotov == null || !molotov.IsValid)
                    {
                        Server.PrintToConsole("[NadeSystem] molotov native Create returned null");
                        return;
                    }
                    spawned = true;
                    molotov.TeamNum             = teamNum;
                    molotov.Thrower.Raw         = botPawn.EntityHandle.Raw;
                    molotov.OriginalThrower.Raw = botPawn.EntityHandle.Raw;
                    molotov.OwnerEntity.Raw     = botPawn.EntityHandle.Raw;
                    AnnounceGrenadeThrow(bot, gtype);
                    Server.PrintToConsole(
                        $"[NadeSystem] Replayed [molotov] id={g.Id[..8]}... " +
                        $"bot=[{bot.PlayerName}] " +
                        $"origin=({origin.X:F0},{origin.Y:F0},{origin.Z:F0}) " +
                        $"vel=({velocity.X:F1},{velocity.Y:F1},{velocity.Z:F1})");
                    return;
                }

                Server.PrintToConsole(
                    $"[NadeSystem] Unknown grenadeType '{g.GrenadeType}' for id {g.Id}");
            }
            catch (Exception ex)
            {
                Server.PrintToConsole($"[NadeSystem] SpawnProjectile error: {ex.Message}");
            }
            finally { completed?.Invoke(spawned); }
        });
    }

    // Prevent a flashbang from detonating
    // * Recreates a decoy flash projectile until its movement stops
    private void StartDecoyFlashLoop(CCSPlayerController bot, GrenadeData g,
        CFlashbangProjectile flash, int teamNum, QAngle angles)
    {
        AddTimer(1f, () =>
        {
            if (!flash.IsValid) return;

            // Get current position and velocity
            var curPos = flash.AbsOrigin;
            var curVel = flash.AbsVelocity;
            if (curPos == null || curVel == null) return;

            float speed = MathF.Sqrt(curVel.X*curVel.X + curVel.Y*curVel.Y + curVel.Z*curVel.Z);

            // Kill old flash
            flash.AcceptInput("Kill");

            // Stop if velocity is near zero
            if (speed < 5f) return;

            // recreate a new flash with all the current state
            var botPawn = bot.PlayerPawn?.Value;
            if (botPawn == null || !botPawn.IsValid) return;

            var newOrigin = new Vector(curPos.X, curPos.Y, curPos.Z);
            var newVel    = new Vector(curVel.X, curVel.Y, curVel.Z);

            var newFlash = Utilities.CreateEntityByName<CFlashbangProjectile>("flashbang_projectile");
            if (newFlash == null) return;

            newFlash.TeamNum             = (byte)teamNum;
            newFlash.Thrower.Raw         = botPawn.EntityHandle.Raw;
            newFlash.OriginalThrower.Raw = botPawn.EntityHandle.Raw;
            newFlash.OwnerEntity.Raw     = botPawn.EntityHandle.Raw;
            newFlash.Elasticity          = 0.33f;
            newFlash.Teleport(newOrigin, angles, newVel);
            newFlash.DispatchSpawn();
            newFlash.Teleport(newOrigin, angles, newVel);

            // Cycle
            StartDecoyFlashLoop(bot, g, newFlash, teamNum, angles);
        });
    }

}
