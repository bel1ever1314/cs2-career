namespace CareerMatch;

public sealed record TacticalRosterMember(string Id, string Role,
    IReadOnlyDictionary<string, float>? Abilities = null, float Fallback = 75);

/// <summary>Assign the full signed roster BEFORE filtering alive/controlled bots.
/// Duties are slots, not permanent player roles; two AWP duties are valid.</summary>
public static class TacticalSlotAssignment
{
    public static bool ValidDuty(string? duty) => duty is "auto" or "awp" or "entry" or "lurk" or "rifle" or "igl";

    public static IReadOnlyList<TacticRosterBinding> Assign(CustomTactic tactic, IReadOnlyList<string> roster,
        string human, IReadOnlyList<TacticalRosterMember>? members = null)
    {
        if (roster.Count != 5 || roster.Any(string.IsNullOrWhiteSpace) || roster.Distinct().Count() != 5
            || roster.Count(id => id == human) != 1 || tactic.Slots.Count != 5
            || !tactic.Slots.Select(s => s.Slot).Order().SequenceEqual(Enumerable.Range(1, 5))
            || tactic.Assignment is not ("roster" or "ability") || tactic.HumanSlot is < 1 or > 5
            || (tactic.Assignment == "roster" && tactic.HumanSlot != 1)
            || tactic.Slots.Any(s => !ValidDuty(s.Duty)))
            throw new InvalidDataException("tactical_slot_assignment_invalid");
        var slots = tactic.Slots.OrderBy(s => s.Slot).ToArray();
        if (tactic.Assignment == "roster")
            return slots.Select((s, i) => new TacticRosterBinding(s.Slot, roster[i], s)).ToArray();
        var players = members?.ToDictionary(p => p.Id, StringComparer.Ordinal)
            ?? new Dictionary<string, TacticalRosterMember>(StringComparer.Ordinal);
        var freeSlots = slots.Where(s => s.Slot != tactic.HumanSlot).ToArray();
        var bots = roster.Where(id => id != human).Order(StringComparer.Ordinal).ToArray();
        string[]? best = null;
        long bestScore = long.MinValue;
        var used = new bool[4]; var choice = new string[4];
        void Search(int depth, long score)
        {
            if (depth == 4)
            {
                // Stable-ID traversal makes equal-fit assignments reproducible.
                if (score > bestScore) { bestScore = score; best = choice.ToArray(); }
                return;
            }
            for (var i = 0; i < bots.Length; i++)
            {
                if (used[i]) continue;
                var p = players.GetValueOrDefault(bots[i]) ?? new(bots[i], "");
                var duty = freeSlots[depth].Duty;
                var value = duty != "auto" && p.Abilities?.TryGetValue(duty, out var fit) == true ? fit : p.Fallback;
                if (!float.IsFinite(value)) value = 75;
                var weighted = (long)Math.Round(Math.Clamp(value, 0, 100) * 1000)
                    + (duty != "auto" && duty == p.Role ? 1 : 0);
                used[i] = true; choice[depth] = bots[i]; Search(depth + 1, score + weighted); used[i] = false;
            }
        }
        Search(0, 0);
        var assigned = new Dictionary<int, string> { [tactic.HumanSlot] = human };
        for (var i = 0; i < freeSlots.Length; i++) assigned[freeSlots[i].Slot] = best![i];
        return slots.Select(s => new TacticRosterBinding(s.Slot, assigned[s.Slot], s)).ToArray();
    }
}
