using System.Text.Json;
using System.Text.Json.Serialization;
using System.Globalization;
using System.Text;
using System.Buffers;

namespace CareerMatch;

/// <summary>Local map intents. No enemy, engine address, command or player handle is accepted.</summary>
public sealed class TacticalPlaybook
{
    public const int MaximumBytes = 262144;
    [JsonRequired, JsonPropertyName("schema_version")] public int Version { get; set; }
    [JsonRequired, JsonPropertyName("map")] public string Map { get; set; } = "";
    [JsonRequired, JsonPropertyName("tactics")] public List<CustomTactic> Tactics { get; set; } = [];

    public static TacticalPlaybook Parse(string json)
    {
        if (System.Text.Encoding.UTF8.GetByteCount(json) > MaximumBytes)
            throw new InvalidDataException("tactical_playbook_too_large");
        using var document = JsonDocument.Parse(json, new JsonDocumentOptions { MaxDepth = 16 });
        RejectDuplicateProperties(document.RootElement);
        var result = JsonSerializer.Deserialize<TacticalPlaybook>(json, new JsonSerializerOptions {
            MaxDepth = 16, UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow
        }) ?? throw new InvalidDataException("tactical_playbook_missing");
        if (result.Version != 1 || !TacticalMapCatalog.IsSupported(result.Map) || result.Tactics is null || result.Tactics.Count > 20)
            throw new InvalidDataException("tactical_playbook_header_invalid");
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var tactic in result.Tactics)
        {
            if (tactic is null || !ValidId(tactic.Id) || !ids.Add(tactic.Id)
                || !ValidName(tactic.Name) || tactic.Side is not ("t" or "ct")
                || tactic.Assignment is not ("roster" or "ability") || tactic.HumanSlot is < 1 or > 5
                || (tactic.Assignment == "roster" && tactic.HumanSlot != 1)
                || tactic.Slots is null || tactic.Slots.Count != 5
                || !tactic.Slots.Select(s => s?.Slot ?? 0).Order().SequenceEqual(Enumerable.Range(1, 5)))
                throw new InvalidDataException("tactical_playbook_tactic_invalid");
            foreach (var slot in tactic.Slots)
            {
                if (slot.Steps is null || slot.Steps.Count > 12 || !TacticalSlotAssignment.ValidDuty(slot.Duty)
                    || !TacticalFinishPolicy.Valid(slot.Finish))
                    throw new InvalidDataException("tactical_playbook_steps_invalid");
                foreach (var step in slot.Steps)
                    if (step is null || !TacticalMapCatalog.ContainsPoint(result.Map, step.Position) || step.Level is not ("auto" or "upper" or "lower")
                        || !float.IsFinite(step.Wait) || step.Wait < 0 || step.Wait > 30 || step.Movement is not ("run" or "walk")
                        || (step.LookAt is not null && !TacticalMapCatalog.ContainsPoint(result.Map, step.LookAt)))
                        throw new InvalidDataException("tactical_playbook_step_invalid");
            }
        }
        return result;
    }

    public static bool ValidId(string? id) => id is { Length: > 0 and <= 32 }
        && id.All(c => c is >= 'a' and <= 'z' or >= '0' and <= '9' or '_' or '-');
    private static bool ValidName(string? value)
    {
        if (string.IsNullOrWhiteSpace(value)) return false;
        var remaining = value.AsSpan(); var count = 0;
        while (remaining.Length > 0)
        {
            if (Rune.DecodeFromUtf16(remaining, out var rune, out var consumed) != OperationStatus.Done || ++count > 40)
                return false;
            if (Rune.GetUnicodeCategory(rune) is UnicodeCategory.Control or UnicodeCategory.Format
                or UnicodeCategory.Surrogate or UnicodeCategory.PrivateUse or UnicodeCategory.OtherNotAssigned) return false;
            remaining = remaining[consumed..];
        }
        return true;
    }
    private static void RejectDuplicateProperties(JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var item in value.EnumerateObject())
            {
                if (!names.Add(item.Name)) throw new InvalidDataException("tactical_playbook_duplicate_property");
                RejectDuplicateProperties(item.Value);
            }
        }
        else if (value.ValueKind == JsonValueKind.Array)
            foreach (var item in value.EnumerateArray()) RejectDuplicateProperties(item);
    }
}

public sealed class CustomTactic
{
    [JsonRequired, JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonRequired, JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonRequired, JsonPropertyName("side")] public string Side { get; set; } = "";
    [JsonRequired, JsonPropertyName("slots")] public List<CustomTacticSlot> Slots { get; set; } = [];
    [JsonPropertyName("assignment")] public string Assignment { get; set; } = "roster";
    [JsonPropertyName("human_slot")] public int HumanSlot { get; set; } = 1;
}
public sealed class CustomTacticSlot
{
    [JsonRequired, JsonPropertyName("slot")] public int Slot { get; set; }
    [JsonRequired, JsonPropertyName("steps")] public List<CustomTacticStep> Steps { get; set; } = [];
    [JsonPropertyName("duty")] public string Duty { get; set; } = "auto";
    [JsonPropertyName("finish")] public string Finish { get; set; } = "auto";
}
public sealed class CustomTacticStep
{
    [JsonRequired, JsonPropertyName("position")] public float[] Position { get; set; } = [];
    [JsonRequired, JsonPropertyName("level")] public string Level { get; set; } = "auto";
    [JsonRequired, JsonPropertyName("wait")] public float Wait { get; set; }
    [JsonRequired, JsonPropertyName("look_at")] public float[]? LookAt { get; set; }
    // Travel TO this waypoint; its wait applies AFTER arrival. Old libraries
    // have no movement property and continue running by default.
    [JsonPropertyName("movement")] public string Movement { get; set; } = "run";
}

public sealed record TacticRosterBinding(int TacticSlot, string PlayerId, CustomTacticSlot Route);
public static class TacticalRosterSlots
{
    // Roster order is the signed match-request order, never current entity order.
    public static IReadOnlyList<TacticRosterBinding> Bind(CustomTactic tactic, IReadOnlyList<string> roster,
        string human, IEnumerable<TacticalBotCandidate> candidates, string side,
        IReadOnlyList<TacticalRosterMember>? abilities = null)
    {
        if (roster.Count != 5 || roster.Any(string.IsNullOrWhiteSpace) || roster.Distinct().Count() != 5
            || roster.Count(id => id == human) != 1 || tactic.Side != side)
            throw new InvalidDataException("tactical_roster_not_five_stable_slots");
        var eligible = candidates.Where(a => a.IsBot && a.IsValid && a.Alive && !a.HumanControlled
            && a.Id != human && a.Side == side).Select(a => a.Id).ToHashSet(StringComparer.Ordinal);
        return TacticalSlotAssignment.Assign(tactic, roster, human, abilities)
            .Where(s => s.Route.Steps.Count > 0 && eligible.Contains(s.PlayerId)).ToArray();
    }
}

public sealed record TacticNavPoint(uint Area, float X, float Y, float Z);
public static class TacticalNavProjection
{
    public const float MaximumSnap = 48;
    // Each candidate is already the actual NAV area's closest point at XY.
    public static TacticNavPoint Select(float x, float y, string level, float previousZ,
        IEnumerable<TacticNavPoint> points)
    {
        var candidates = points.Select(p => (Point: p, Distance: MathF.Sqrt((p.X-x)*(p.X-x)+(p.Y-y)*(p.Y-y))))
            .Where(p => float.IsFinite(p.Point.X) && float.IsFinite(p.Point.Y) && float.IsFinite(p.Point.Z)
                && p.Distance <= MaximumSnap).ToArray();
        if (candidates.Length == 0) throw new InvalidDataException("点击远离可行走导航面");
        var minimum = candidates.Min(p => p.Distance);
        // Do not choose a higher/lower floor across a wall when a containing floor exists.
        candidates = candidates.Where(p => p.Distance <= minimum + 8).ToArray();
        var chosenZ = level switch {
            "upper" => candidates.Max(p => p.Point.Z), "lower" => candidates.Min(p => p.Point.Z),
            "auto" => candidates.OrderBy(p => Math.Abs(p.Point.Z-previousZ)).ThenBy(p => p.Distance)
                .ThenBy(p => p.Point.Area).First().Point.Z,
            _ => throw new InvalidDataException("导航层无效")
        };
        return candidates.Where(p => Math.Abs(p.Point.Z-chosenZ) <= 8)
            .OrderBy(p => p.Distance).ThenBy(p => Math.Abs(p.Point.Z-chosenZ)).ThenBy(p => p.Point.Area).First().Point;
    }
}

public enum TacticStepAction { Move, Wait, Paused, Advanced, Completed }
internal static class TacticalFinishPolicy
{
    internal static bool Valid(string? finish) => finish is "auto" or "hold" or "native";
    // Resolve against the accepted round's SIDE, never a roster's original side
    // or a player's weapon role. Intermediate waits remain finite.
    internal static bool HoldFinal(string finish, string side)
        => finish == "hold" || (finish == "auto" && side == "ct");
    internal static bool ObjectiveNeedsControl(bool finalHold, bool defusing, string weapon)
        => finalHold && (defusing || weapon == "weapon_c4");
}
internal static class TacticalWaitPolicy
{
    // A wait is a positional order, not a request to suspend native perception.
    // Once acquired, keep movement through braking and ordinary observation /
    // firing. Damage and native grenade avoidance remove the actor BEFORE this
    // policy runs. Native aim, firing and use remain untouched by the lease.
    internal static bool InHoldBounds(float distanceSquared, float heightDifference, float arrivalRadius)
        => distanceSquared <= (arrivalRadius+32)*(arrivalRadius+32) && Math.Abs(heightDifference) < 48;
    internal static bool ShouldHold(float wait, bool reached, bool holdingInBounds)
        => wait > 0 && (reached || holdingInBounds);
    internal static bool ShouldHold(bool waiting, bool reached, bool holdingInBounds)
        => waiting && (reached || holdingInBounds);
    internal static bool YieldToNative(bool holdPosition, bool nativeAction)
        => nativeAction && !holdPosition;
}

internal sealed class TacticalTravelProgress
{
    private (float X, float Y)? _checkpoint;
    private float _bestDistance = float.MaxValue;
    private float _lastProgress;

    internal void Reset(float now)
    { _checkpoint = null; _bestDistance = float.MaxValue; _lastProgress = now; }

    internal bool IsStalled(float now, float x, float y, float distance)
    {
        // NAV can legitimately route away from the straight-line destination.
        // Count real travel too; do not cancel a bot running around a wall just
        // because its closest-ever distance has not improved for ten seconds.
        if (_checkpoint is not { } previous || distance + 20 < _bestDistance
            || (x-previous.X)*(x-previous.X)+(y-previous.Y)*(y-previous.Y) >= 24*24)
        {
            _checkpoint = (x,y); _lastProgress = now;
            _bestDistance = Math.Min(distance, _bestDistance);
        }
        return now-_lastProgress > 10;
    }
}

public sealed class TacticalStepClock(IReadOnlyList<float> waits, bool holdFinal = false)
{
    public int Stage { get; private set; }
    public bool Arrived { get; private set; }
    public float Remaining { get; private set; } = waits.Count > 0 ? waits[0] : 0;
    public bool FinalHold => holdFinal && Stage == waits.Count - 1 && waits.Count > 0;
    public bool HoldingFinal => FinalHold && Arrived && Remaining <= 0;
    private float? _lastWait;
    public TacticStepAction Tick(float now, bool reached, bool interrupted)
    {
        if (!float.IsFinite(now)) throw new ArgumentOutOfRangeException(nameof(now));
        if (Stage >= waits.Count) return TacticStepAction.Completed;
        if (interrupted) { _lastWait = null; return TacticStepAction.Paused; }
        if (!reached) { _lastWait = null; return TacticStepAction.Move; }
        Arrived = true;
        if (_lastWait is { } last) Remaining = Math.Max(0, Remaining - Math.Clamp(now-last, 0, .25f));
        _lastWait = now;
        if (Remaining > 0) return TacticStepAction.Wait;
        // Keep a real terminal task instead of extending the timer or dropping
        // native ownership for a frame. Round/radio/danger/objective releases
        // still remove the actor through the same control cleanup paths.
        if (FinalHold) return TacticStepAction.Wait;
        Stage++; Arrived = false; _lastWait = null;
        Remaining = Stage < waits.Count ? waits[Stage] : 0;
        return Stage >= waits.Count ? TacticStepAction.Completed : TacticStepAction.Advanced;
    }
}

internal delegate bool TacticalMoveCall(out string reason);
internal static class TacticalMoveMaintenance
{
    // Keep the native movement intent alive without restarting an owned goal.
    // A refusal belongs to the selected native call; never retry through Start.
    internal static bool Tick(bool ownsGoal, TacticalMoveCall start, TacticalMoveCall renew, out string reason)
        => ownsGoal ? renew(out reason) : start(out reason);
}

internal enum TacticalPathAction { Pending, Moving, Yielded, Failed }

// A recorded MoveTo goal is NOT proof that ComputePath accepted it. Custom
// waypoints commit a fresh shortest native NAV path before releasing movement;
// the timer is read by the native adapter, not inferred from this clock.
internal sealed class TacticalDirectMove
{
    internal const float MaximumPreparation = 3;
    private bool _committed;
    private float? _preparingSince;

    internal void Reset() { _committed = false; _preparingSince = null; }
    // A successor path has already been accepted atomically by the native
    // adapter. Do not run the first-goal preparation/zero-input lease again.
    internal bool Committed => _committed;
    internal void AdoptCommitted() { _committed = true; _preparingSince = null; }
    internal bool NeedsPreparation(bool ownsGoal) => !_committed || !ownsGoal;

    internal TacticalPathAction Tick(float now, bool ownsGoal, TacticalMoveCall start,
        TacticalMoveCall commitPath, TacticalMoveCall renew, out string reason)
    {
        if (!float.IsFinite(now)) throw new ArgumentOutOfRangeException(nameof(now));
        if (!ownsGoal) _committed = false;
        if (_committed)
        {
            if (renew(out reason)) return TacticalPathAction.Moving;
            return Refused(reason);
        }
        _preparingSince ??= now;
        if (now-_preparingSince > MaximumPreparation)
        { reason = "custom_path_preparation_timeout"; return TacticalPathAction.Failed; }
        if (!ownsGoal && !start(out reason)) return Refused(reason);
        if (commitPath(out reason))
        {
            _committed = true; _preparingSince = null;
            return TacticalPathAction.Moving;
        }
        return reason is "navigation_path_rate_limited" or "navigation_goal_changed"
            ? TacticalPathAction.Pending : Refused(reason);
    }

    private TacticalPathAction Refused(string reason)
    {
        if (reason != "native_combat_or_objective_retained") return TacticalPathAction.Failed;
        Reset(); return TacticalPathAction.Yielded;
    }
}
