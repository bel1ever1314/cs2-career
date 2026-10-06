namespace CareerMatch;

// A queued file is not proof that the native avatar override was applied.
// Only the BotHider acknowledgement for the current identity completes it.
public sealed class AvatarDelivery
{
    public sealed class Entry
    {
        public int Slot { get; init; }
        public string PlayerId { get; init; } = "";
        public string Hash { get; init; } = "";
        public ulong SteamId { get; init; }
        public string Status { get; set; } = "waiting";
        public int Attempts { get; set; }
        internal bool Queued;
        internal double Next;
    }
    private readonly Dictionary<int, Entry> _entries = [];
    public IEnumerable<Entry> Entries => _entries.Values.OrderBy(e => e.Slot);
    public void Reset() => _entries.Clear();
    public void Forget(int slot) => _entries.Remove(slot);

    public void Update(int slot, string playerId, string hash, ulong expectedSid, double now,
        bool managed, ulong actualSid, bool applied, Func<bool> send)
    {
        if (!_entries.TryGetValue(slot, out var e) || e.PlayerId != playerId || e.Hash != hash || e.SteamId != expectedSid)
            _entries[slot] = e = new() { Slot = slot, PlayerId = playerId, Hash = hash, SteamId = expectedSid };
        if (now < e.Next) return;
        e.Next = now + 2;
        if (!managed) { e.Status = "waiting_for_managed_bot"; return; }
        if (actualSid == 0 || actualSid != expectedSid) { e.Status = "identity_mismatch"; return; }
        if (e.Queued && applied) { e.Status = "applied"; return; }
        if (e.Status == "applied") { e.Attempts = 0; e.Queued = false; }
        if (e.Attempts >= 5) { e.Status = "not_acknowledged"; return; }
        ++e.Attempts;
        e.Queued = send();
        e.Status = e.Queued ? "queued" : "rejected";
    }
}

// Bind to the actual shared API assembly loaded by CounterStrikeSharp. Keeping
// this optional avoids distributing a second, conflicting BotHiderApi assembly.
public sealed class BotAvatarBridge(object api, Type contract)
{
    private readonly Func<int, bool> _managed = Bind<Func<int, bool>>(api, contract, "IsManagedBot");
    private readonly Func<int, ulong> _sid = Bind<Func<int, ulong>>(api, contract, "GetBotSteamId");
    private readonly Func<int, bool> _applied = Bind<Func<int, bool>>(api, contract, "HasBotAvatar");
    private readonly Func<int, string, bool> _send = Bind<Func<int, string, bool>>(api, contract, "SetBotAvatar");
    private static T Bind<T>(object api, Type contract, string name) where T : Delegate =>
        (contract.GetMethod(name) ?? throw new MissingMethodException(contract.FullName, name)).CreateDelegate<T>(api);
    public object Provider => api;
    public bool Managed(int slot) => _managed(slot);
    public ulong SteamId(int slot) => _sid(slot);
    public bool Applied(int slot) => _applied(slot);
    public bool Send(int slot, string path) => _send(slot, path);
}
