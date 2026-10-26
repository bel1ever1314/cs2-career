using System;
using System.Collections.Generic;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Timers;

namespace NadeSystem;

public partial class NadeSystemPlugin
{
    private bool _careerBudgetStarted;
    private readonly CareerNadeBudget _careerBudget = new();

    private void StartCareerBudget()
    {
        _careerBudgetStarted = true;
        foreach (var bot in Utilities.GetPlayers())
            if (bot.IsValid && bot.IsBot && bot.PawnIsAlive && !bot.HasBeenControlledByPlayerThisRound)
                _careerBudget.AddBot(bot.Index, bot.TeamNum, (bot.InGameMoneyServices?.Account ?? 0) >= 300);
        int generation = _careerBudget.Generation;
        foreach (float seconds in new[] { 30f, 60f, 90f })
            AddTimer(seconds, () =>
            {
                if (generation != _careerBudget.Generation || _roundOver) return;
                _careerBudget.Decay(index =>
                {
                    var bot = Utilities.GetPlayerFromIndex((int)index);
                    return bot != null && bot.IsValid && bot.IsBot && bot.PawnIsAlive
                        && !bot.HasBeenControlledByPlayerThisRound;
                }, Random.Shared.NextDouble);
            }, TimerFlags.STOP_ON_MAPCHANGE);
    }

    private static ulong TargetMask(FlashTargetEvaluation? evaluation)
    {
        ulong mask = 0;
        if (evaluation is { } value)
            foreach (var enemy in value.BlindableEnemies)
                if (enemy.Slot >= 0 && enemy.Slot < 64) mask |= 1UL << enemy.Slot;
        return mask;
    }

    private bool TryQueueCareerGrenade(CCSPlayerController bot, GrenadeData grenade,
        ulong targets = 0, Action<bool>? completed = null)
    {
        if (_botNadesMode == "off" || _roundOver || _freezeEndTime <= 0f
            || !bot.IsValid || !bot.IsBot || !bot.PawnIsAlive || bot.HasBeenControlledByPlayerThisRound
            || _replayBots.Contains(bot.Index) || IsOnCooldown(grenade.Id)) return false;
        string type = grenade.GrenadeType == "incgrenade" ? "molotov" : grenade.GrenadeType;
        var money = bot.InGameMoneyServices;
        var costs = bot.TeamNum == 3 ? CostCT : CostT;
        if (money == null || !costs.TryGetValue(type, out int cost) || money.Account < cost
            || !HasLockedNadeMoney(bot.Index, cost)) return false;
        int spent = _roundSpendPerBot.GetValueOrDefault(bot.Index);
        if (spent + cost > GetRoundSpendCap(bot.TeamNum == 3, _poorBots.Contains(bot.Index))) return false;
        var landing = grenade.LandingPosition;
        var ticket = _careerBudget.Reserve(bot.Index, bot.TeamNum, type, Server.CurrentTime,
            landing.X, landing.Y, landing.Z, targets);
        if (ticket == null) return false;
        _replayBots.Add(bot.Index);
        RegisterCooldown(grenade.Id, type);
        SpawnProjectile(bot, grenade, spawned =>
        {
            if (ticket.Generation != _careerBudget.Generation) return;
            if (!_careerBudget.Complete(ticket, spawned, Server.CurrentTime))
            {
                _replayBots.Remove(ticket.Bot);
                _cooldowns.RemoveAll(c => c.GrenadeId == grenade.Id);
                completed?.Invoke(false);
                return;
            }
            // The projectile exists. Never refund it because a later visual or
            // network notification fails; this is the single commit point.
            money.Account = Math.Max(0, money.Account - cost);
            _roundSpendPerBot[ticket.Bot] = spent + cost;
            SpendLockedNadeMoney(ticket.Bot, cost);
            IncrementCount(type, ticket.Team);
            IncrementBotCount(type, ticket.Bot);
            if (type == "smoke" && Server.CurrentTime - _freezeEndTime < 5f)
                _earlySmokeCountByTeam[ticket.Team] = _earlySmokeCountByTeam.GetValueOrDefault(ticket.Team) + 1;
            AddTimer(1f, () =>
            {
                if (ticket.Generation == _careerBudget.Generation) _replayBots.Remove(ticket.Bot);
            }, TimerFlags.STOP_ON_MAPCHANGE);
            completed?.Invoke(true);
            Utilities.SetStateChanged(bot, "CCSPlayerController", "m_pInGameMoneyServices");
        }, () => ticket.Generation == _careerBudget.Generation && !_roundOver && bot.IsValid
            && bot.IsBot && bot.PawnIsAlive && bot.TeamNum == ticket.Team
            && !bot.HasBeenControlledByPlayerThisRound && money.Account >= cost);
        return true;
    }
}
