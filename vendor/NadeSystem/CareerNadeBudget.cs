using System;
using System.Collections.Generic;
using System.Linq;

namespace NadeSystem;

// Value-only round ledger. No entity queries, visibility tests or tick polling.
internal sealed class CareerNadeBudget
{
    internal sealed record Ticket(int Generation, uint Bot, int Team, string Type,
        float X, float Y, float Z, ulong Targets);
    private sealed class Wallet
    {
        internal int Team;
        internal int Flashes = 2;
        internal bool Damage;
    }
    private readonly Dictionary<uint, Wallet> _bots = new();
    private readonly Dictionary<int, int> _smokes = new();
    private readonly Dictionary<uint, Ticket> _pending = new();
    private readonly List<(Ticket Ticket, float Until)> _flashes = new();
    internal int Generation { get; private set; }

    internal void Reset()
    {
        Generation++;
        _bots.Clear();
        _smokes.Clear();
        _pending.Clear();
        _flashes.Clear();
    }

    internal void AddBot(uint bot, int team, bool canAffordDamage)
    {
        if (team is not (2 or 3) || _bots.ContainsKey(bot)) return;
        _bots[bot] = new Wallet { Team = team, Damage = canAffordDamage };
        _smokes[team] = _smokes.GetValueOrDefault(team) + 1;
    }

    internal Ticket? Reserve(uint bot, int team, string type, float now,
        float x, float y, float z, ulong targets)
    {
        if (type == "incgrenade") type = "molotov";
        if (!_bots.TryGetValue(bot, out var wallet) || wallet.Team != team || _pending.ContainsKey(bot))
            return null;
        if (type is "he" or "molotov")
        {
            if (!wallet.Damage) return null;
        }
        else if (type == "smoke")
        {
            if (_smokes.GetValueOrDefault(team) <= _pending.Values.Count(t => t.Team == team && t.Type == "smoke"))
                return null;
        }
        else if (type == "flash")
        {
            if (wallet.Flashes <= 0) return null;
            _flashes.RemoveAll(f => f.Until <= now);
            foreach (var previous in _pending.Values.Concat(_flashes.Select(f => f.Ticket)))
            {
                if (previous.Type != "flash" || previous.Team != team) continue;
                float dx = x - previous.X, dy = y - previous.Y;
                if (dx * dx + dy * dy <= 320f * 320f && MathF.Abs(z - previous.Z) <= 160f
                    || (targets & previous.Targets) != 0) return null;
            }
        }
        else return null;
        var ticket = new Ticket(Generation, bot, team, type, x, y, z, targets);
        _pending.Add(bot, ticket);
        return ticket;
    }

    internal bool Complete(Ticket ticket, bool spawned, float now)
    {
        if (ticket.Generation != Generation || !_pending.TryGetValue(ticket.Bot, out var current)
            || !ReferenceEquals(ticket, current)) return false;
        _pending.Remove(ticket.Bot);
        if (!spawned) return false;
        var wallet = _bots[ticket.Bot];
        if (ticket.Type == "flash")
        {
            wallet.Flashes--;
            _flashes.Add((ticket, now + 3f));
        }
        else if (ticket.Type == "smoke") _smokes[ticket.Team]--;
        else wallet.Damage = false;
        return true;
    }

    // Called exactly at 30/60/90 seconds, only for living holders. Actual uses
    // already removed the item; no team credit or replenishment is involved.
    internal void Decay(Func<uint, bool> isAlive, Func<double> random)
    {
        foreach (var (bot, wallet) in _bots)
            if (wallet.Damage && !_pending.ContainsKey(bot) && isAlive(bot) && random() < 0.35)
                wallet.Damage = false;
    }
}
