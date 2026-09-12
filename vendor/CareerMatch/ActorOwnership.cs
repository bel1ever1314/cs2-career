namespace CareerMatch;

internal sealed record AssistResolution(string? PlayerId, bool Ambiguous, string Reason, string[] Candidates);

// Presentation identity stays on the controller; match events belong to the
// original player of the body being controlled. Never change IdentityBindings.
internal sealed class ActorOwnership
{
    private readonly Dictionary<string, string?> _controlled = [];
    private readonly Dictionary<uint, string> _pawns = [];
    private readonly Dictionary<(string Victim, string Controller, bool Flash), HashSet<string>> _support = [];
    private readonly Dictionary<string, HashSet<string>> _controlHistory = [];
    private readonly Dictionary<(string Victim, string Actor), (int Damage, long Order)> _damage = [];
    private long _contributionOrder;
    private readonly Dictionary<(string Controller, string Weapon), HashSet<string>> _throws = [];
    public bool HadTakeover { get; private set; }
    public void NewMatch() { HadTakeover = false; NewRound(); }
    public void Detach(string controller) { _controlled.Remove(controller); }
    public void NewRound() { _controlled.Clear(); _pawns.Clear(); _support.Clear(); _throws.Clear(); _controlHistory.Clear(); _damage.Clear(); _contributionOrder = 0; }
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
        if (!_controlHistory.TryGetValue(controller, out var bodies)) _controlHistory[controller] = bodies = [];
        bodies.Add(bot);
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
    public void Support(string victim, string controller, string actor, bool flash = false, int damage = 0)
    {
        // Store physical contribution once, outside the controller alias index.
        if (!flash && damage > 0)
        {
            var previous = _damage.GetValueOrDefault((victim, actor));
            _damage[(victim, actor)] = (previous.Damage + damage, ++_contributionOrder);
        }
        var key = (victim, controller, flash);
        if (!_support.TryGetValue(key, out var actors)) _support[key] = actors = [];
        actors.Add(actor);
        // CS2 can report an assist using either the human controller or the
        // original bot. Index the same contribution under its actual actor too.
        // This is not another assist: sets contain evidence, never counters.
        if (actor != controller)
        {
            var actorKey = (victim, actor, flash);
            if (!_support.TryGetValue(actorKey, out var own)) _support[actorKey] = own = [];
            own.Add(actor);
        }
    }
    public string? Assister(string victim, string controller, bool flash)
        => ResolveAssist(victim, controller, flash).PlayerId;

    public AssistResolution ResolveAssist(string victim, string controller, bool flash, string? killer = null)
    {
        var candidates = new HashSet<string>();
        if (_support.TryGetValue((victim, controller, flash), out var actors))
            candidates.UnionWith(actors);
        // Include damage/flash the bot caused autonomously before takeover.
        // Keep earlier controlled bodies until round reset, not just the last
        // body: a human may take over several teammates in the same round.
        if (_controlHistory.TryGetValue(controller, out var bodies))
            foreach (var body in bodies)
                if (_support.TryGetValue((victim, body, flash), out var prior)) candidates.UnionWith(prior);
        var evidence = candidates.Order(StringComparer.Ordinal).ToArray();
        var eligible = evidence.Where(id => id != killer && id != victim).ToArray();
        // The final killing hit is also a hurt event. It must not turn an
        // otherwise unique earlier contributor into an "ambiguous assist".
        if (eligible.Length == 1) return new(eligible[0], false, "unique_contributor", evidence);
        if (eligible.Length > 1)
        {
            // Career-specific rule approved by the player: most damage wins;
            // ties go to whoever reached that total first. Not engine parity.
            // Missing evidence and flash assists still fail closed.
            if (!flash && eligible.All(id => _damage.ContainsKey((victim, id))))
            {
                var winner = eligible.OrderByDescending(id => _damage[(victim, id)].Damage)
                    .ThenBy(id => _damage[(victim, id)].Order).First();
                return new(winner, false, "career_damage_then_reached_first_v1", evidence);
            }
            return new(null, true, "multiple_non_killer_contributors", evidence);
        }
        if (evidence.Length > 0) return new(null, false, "only_killer_or_victim", evidence);
        // No contribution evidence: only safe when the controller never took
        // over. Do not move an earlier human assist onto a currently held bot.
        if (_controlled.ContainsKey(controller) || _controlHistory.ContainsKey(controller)
            || _controlHistory.Values.Any(ids => ids.Contains(controller)))
            return new(null, true, "missing_takeover_contribution", evidence);
        return new(controller == killer || controller == victim ? null : controller,
            false, "unchanged_controller", evidence);
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
