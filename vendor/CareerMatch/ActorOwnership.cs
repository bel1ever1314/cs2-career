namespace CareerMatch;

// Presentation identity stays on the controller; match events belong to the
// original player of the body being controlled. Never change IdentityBindings.
internal sealed class ActorOwnership
{
    private readonly Dictionary<string, string?> _controlled = [];
    private readonly Dictionary<uint, string> _pawns = [];
    private readonly Dictionary<(string Victim, string Controller, bool Flash), HashSet<string>> _support = [];
    private readonly Dictionary<(string Controller, string Weapon), HashSet<string>> _throws = [];
    public bool HadTakeover { get; private set; }
    public void NewMatch() { HadTakeover = false; NewRound(); }
    public void Detach(string controller) { _controlled.Remove(controller); }
    public void NewRound() { _controlled.Clear(); _pawns.Clear(); _support.Clear(); _throws.Clear(); }
    public void RememberPawn(uint pawn, string owner) { if (pawn != 0) _pawns.TryAdd(pawn, owner); }
    public string? PawnOwner(uint pawn) => _pawns.GetValueOrDefault(pawn);
    public void AwaitTakeover(string controller)
    {
        HadTakeover = true; // Even a rejected signal must disable MatchStats fallback.
        _controlled[controller] = null; // Never silently charge the human while unresolved.
    }
    public void Takeover(string controller, string bot, uint pawn)
    {
        HadTakeover = true;
        _controlled[controller] = bot;
        if (pawn != 0) _pawns[pawn] = bot;
    }
    public string? Actor(string controller, uint pawn = 0, string? original = null)
    {
        // Explicit ownership also wins over stale/swapped OriginalController.
        if (_controlled.TryGetValue(controller, out var controlled)) return controlled;
        if (original is not null && original != controller)
        {
            RememberPawn(pawn, original);
            HadTakeover = true;
            return original;
        }
        // The takeover event is retained through death, when the engine may
        // already restore the human's own pawn before player_death is fired.
        return pawn != 0 && _pawns.TryGetValue(pawn, out var owner) ? owner : controller;
    }
    public void Support(string victim, string controller, string actor, bool flash = false)
    {
        var key = (victim, controller, flash);
        if (!_support.TryGetValue(key, out var actors)) _support[key] = actors = [];
        actors.Add(actor);
    }
    public string? Assister(string victim, string controller, bool flash)
    {
        if (_support.TryGetValue((victim, controller, flash), out var actors))
            return actors.Count == 1 ? actors.Single() : null;
        // No contribution evidence: only safe when the controller never took
        // over. Do not move an earlier human assist onto a currently held bot.
        return _controlled.ContainsKey(controller) ? null : controller;
    }
    public void Thrown(string controller, string weapon, string actor)
    {
        var key = (controller, weapon);
        if (!_throws.TryGetValue(key, out var actors)) _throws[key] = actors = [];
        actors.Add(actor);
    }
    public string? ProjectileActor(string controller, string weapon)
    {
        var candidates = new HashSet<string>();
        if (_throws.TryGetValue((controller, weapon), out var actors)) candidates.UnionWith(actors);
        // The bot may have thrown before a human took it over. Its contribution
        // was captured under the BOT controller, not the later human controller.
        if (_controlled.TryGetValue(controller, out var bot) && bot is not null
            && _throws.TryGetValue((bot, weapon), out var botThrows)) candidates.UnionWith(botThrows);
        if (candidates.Count > 0) return candidates.Count == 1 ? candidates.Single() : null;
        return _controlled.ContainsKey(controller) ? null : controller;
    }
}
