using CareerMatch;

internal static class ProfileIdentityRegression
{
    public static void Run()
    {
        int count = 0;
        void Check(bool ok, string message) { count++; if (!ok) throw new Exception(message); }
        var bots = Enumerable.Range(0, 9).Select(i =>
            new IdentityBot($"p{i}", $"C2C_p{i}", $"Player {i}", (ulong)(100 + i))).ToList();
        // Reproduce the unsafe combination: a valid profile, but a different
        // requested player's temporary BotHider SID. All nine IDs are unique.
        var live = bots.Select((b, i) => new IdentitySlot(i + 1, $"conn{i}", b.Profile,
            bots[(i + 4) % bots.Count].SteamId, 0, true)).ToList();
        live.Add(new(0, "human", "donk", 999, 999, false));
        var bindings = new IdentityBindings();
        bindings.Update(live, bots, "human", requireProfile: true);
        Check(bindings.Slots.Count == 10, "ten identities despite shuffled personas");
        Check(bots.Select((b, i) => bindings.Slots[i + 1] == b.Id).All(x => x),
            "spawned profile wins over another player's synthetic SID");
        var members = live.Select(p => new TeamMembership(bindings.Slots[p.Slot],
            p.Slot <= 4 ? "ct" : "t", p.Slot <= 4 ? 3 : 2)).ToList();
        Check(TeamScoreMapping.OpeningRosterReady(members), "correct named opening lineup");
        var mixed = members.Select(p => p.Id == "p0" ? p with { CurrentSide = 2 }
            : p.Id == "p4" ? p with { CurrentSide = 3 } : p).ToList();
        Check(mixed.Count(p => p.CurrentSide == 3) == 5, "broken lineup still has five CTs");
        Check(!TeamScoreMapping.OpeningRosterReady(mixed), "five versus five alone is not readiness");
        var swapped = members.Select(p => p with { CurrentSide = 5 - p.CurrentSide }).ToList();
        Check(!TeamScoreMapping.OpeningRosterReady(swapped), "fully reversed opening sides blocked");
        Check(TeamScoreMapping.OpeningCtCurrentSide(swapped) == 2, "legitimate halftime still supported");
        bindings.Update(live.Select(p => p with { Name = "changed", SteamId = 555,
            IsBot = false }).ToList(), bots, "human", requireProfile: true);
        Check(bindings.Slots.Count == 10 && bindings.Slots[1] == "p0", "live binding survives presentation changes");
        bindings.Clear();
        bindings.Update([new(1, "generic", "BOT", 100, 0, true)], bots, "human", requireProfile: true);
        Check(bindings.Slots.Count == 0, "temporary generic name cannot claim a persona's identity");
        bindings.Update([new(1, "generic", "C2C_p0", 101, 0, true)], bots, "human", requireProfile: true);
        Check(bindings.Slots[1] == "p0", "delayed profile appearance can finish binding");
        bindings.Update([new(1, "replacement", "Player 0", 100, 0, true)], bots, "human", requireProfile: true);
        Check(bindings.Slots.Count == 0, "new connection must prove its profile, not inherit display name");
        bindings.Update([new(1, "a", "C2C_p0", 100, 0, true),
            new(2, "b", "C2C_p0", 101, 0, true)], bots, "human", requireProfile: true);
        Check(bindings.Slots.Count == 0, "duplicate profile claims cannot be resolved by slot order");
        var tenBots = bots.Append(new("p9", "C2C_p9", "Player 9", 109)).ToList();
        var observerLive = tenBots.Select((b, i) => new IdentitySlot(i + 1, $"obs{i}", b.Profile,
            (ulong)(100 + (i + 1) % 10), 0, false)).ToList();
        observerLive.Add(new(0, "spectator", "C2C_p0", 999, 999, false));
        bindings.Clear(); bindings.Update(observerLive, tenBots, "", requireProfile: true);
        Check(!bindings.Slots.ContainsKey(0), "real spectator cannot take a requested profile identity");
        observerLive[10] = observerLive[10] with { Name = "Observer" };
        bindings.Update(observerLive, tenBots, "", requireProfile: true);
        Check(bindings.Slots.Count == 10, "ten observer bots bind with shuffled synthetic IDs");
        Console.WriteLine($"{count} profile-authority checks passed (persona shuffle, delayed names, side membership, reconnect, observer).");
    }
}
