namespace CareerMatch;

// Pure identity logic: presentation flags, nicknames and CT/T can all change.
// Only a live connection binding, a requested bot identity, or authenticated
// Steam identity may assign a career player. Never guess by roster order.
internal sealed record IdentitySlot(int Slot, string Connection, string Name,
    ulong SteamId, ulong AuthorizedId, bool IsBot);
internal sealed record IdentityBot(string Id, string Profile, string Name, ulong SteamId);
internal sealed class IdentityBindings
{
    private readonly Dictionary<int, string> _connections = [];
    public Dictionary<int, string> Slots { get; } = [];
    private ulong _humanAccount;

    public void Clear() { Slots.Clear(); _connections.Clear(); _humanAccount = 0; }
    public void Remove(int slot) { Slots.Remove(slot); _connections.Remove(slot); }

    public void Update(IReadOnlyList<IdentitySlot> live, IReadOnlyList<IdentityBot> bots, string humanId)
    {
        foreach (var slot in Slots.Keys.ToList())
            if (!live.Any(p => p.Slot == slot && p.Connection == _connections[slot])) Remove(slot);
        var used = Slots.Values.ToHashSet();
        foreach (var player in live)
        {
            if (Slots.ContainsKey(player.Slot)) continue;
            var matches = bots.Where(b => b.SteamId != 0 && b.SteamId == player.SteamId).ToList();
            if (matches.Count == 0)
                matches = bots.Where(b => b.Profile == player.Name || b.Name == player.Name).ToList();
            if (matches.Count != 1 || used.Contains(matches[0].Id)) continue;
            Bind(player, matches[0].Id);
            used.Add(matches[0].Id);
        }
        if (used.Contains(humanId)) return;
        var candidates = live.Where(p => !Slots.ContainsKey(p.Slot) && !p.IsBot
            && p.AuthorizedId != 0 && !bots.Any(b => b.SteamId == p.AuthorizedId
                || b.SteamId == p.SteamId || b.Profile == p.Name || b.Name == p.Name)
            && (_humanAccount == 0 || p.AuthorizedId == _humanAccount)).ToList();
        if (candidates.Count != 1) return; // Ambiguity blocks readiness; it never merges two people.
        _humanAccount = candidates[0].AuthorizedId;
        Bind(candidates[0], humanId);
    }

    private void Bind(IdentitySlot player, string id)
    {
        Slots[player.Slot] = id;
        _connections[player.Slot] = player.Connection;
    }
}
