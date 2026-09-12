using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using System.Security.Cryptography;

namespace CareerMatch;

// Pure cosmetic evaluator: cannot write stats, run console commands or use the
// match RNG. Round-end snapshots use opening-roster identities after takeover.
public sealed class ChatContract
{
    [JsonPropertyName("schema_version")] public int Version { get; set; }
    [JsonPropertyName("enabled")] public bool Enabled { get; set; }
    [JsonPropertyName("max_per_match")] public int Maximum { get; set; } = 8;
    [JsonPropertyName("global_cooldown_rounds")] public int Cooldown { get; set; } = 2;
    [JsonPropertyName("rules")] public List<ChatRule> Rules { get; set; } = [];
    [JsonPropertyName("scenes")] public List<ChatScene> Scenes { get; set; } = [];
}

public sealed class ChatRule
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("when")] public string When { get; set; } = "";
    [JsonPropertyName("speaker")] public string Speaker { get; set; } = "teammate";
    [JsonPropertyName("speaker_id")] public string SpeakerId { get; set; } = "";
    [JsonPropertyName("channel")] public string Channel { get; set; } = "team";
    [JsonPropertyName("color")] public string Color { get; set; } = "default";
    [JsonPropertyName("text")] public List<string> Text { get; set; } = [];
    [JsonPropertyName("conditions")] public Dictionary<string, JsonElement> Conditions { get; set; } = [];
    [JsonPropertyName("probability")] public double Probability { get; set; } = 1;
    [JsonPropertyName("cooldown_rounds")] public int Cooldown { get; set; } = 4;
    [JsonPropertyName("max_per_match")] public int Maximum { get; set; } = 2;
    [JsonPropertyName("priority")] public int Priority { get; set; }
}

public sealed record ChatPerson(string Id, string Name, string Team, bool IsBot);
public sealed record ChatMessage(string RuleId, string Text, string Channel);
public sealed class ChatStep
{
    [JsonPropertyName("speaker")] public string Speaker { get; set; } = "teammate";
    [JsonPropertyName("speaker_id")] public string SpeakerId { get; set; } = "";
    [JsonPropertyName("channel")] public string Channel { get; set; } = "team";
    [JsonPropertyName("color")] public string Color { get; set; } = "default";
    [JsonPropertyName("text")] public string Text { get; set; } = "";
    [JsonPropertyName("delay_seconds")] public double Delay { get; set; } = 2;
}
public sealed class ChatScene
{
    [JsonPropertyName("distinct_speakers")] public bool DistinctSpeakers { get; set; }
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("when")] public string When { get; set; } = "";
    [JsonPropertyName("conditions")] public Dictionary<string, JsonElement> Conditions { get; set; } = [];
    [JsonPropertyName("probability")] public double Probability { get; set; } = 1;
    [JsonPropertyName("cooldown_rounds")] public int Cooldown { get; set; } = 4;
    [JsonPropertyName("max_per_match")] public int Maximum { get; set; } = 2;
    [JsonPropertyName("priority")] public int Priority { get; set; }
    [JsonPropertyName("sequence")] public List<ChatStep> Sequence { get; set; } = [];
    public ChatRule Gate() => new() { Id = Id, When = When, Speaker = "coach", Text = ["scene"],
        Conditions = Conditions, Probability = Probability, Cooldown = Cooldown, Maximum = Maximum, Priority = Priority };
}
public sealed record ScheduledChat(ChatMessage Message, double AfterSeconds);
public sealed record ChatBatch(bool IsScene, List<ScheduledChat> Lines);

// A cancelled batch can never resume in a new map/round, even for the same nonce.
public sealed class DialoguePlayback
{
    private long _epoch;
    private int _next;
    public long Begin() { _next = 0; return ++_epoch; }
    public void Cancel() { ++_epoch; _next = 0; }
    public bool Take(long epoch, int index)
    {
        if (epoch != _epoch || index != _next) return false;
        _next++; return true;
    }
}

public sealed class MatchDialogue
{
    private static readonly HashSet<string> Numbers = ["round", "score_for", "score_against", "lead", "kills", "deaths", "assists", "damage", "round_kills", "win_streak", "loss_streak", "clutch"];
    private static readonly HashSet<string> Strings = ["result", "map", "player_id", "speaker_id", "team_id"];
    private static readonly HashSet<string> Tokens = [.. Numbers, .. Strings, "player", "speaker", "team", "opponent", "clutch_player"];
    private static readonly Regex Token = new(@"\{([a-z_]+)\}");
    private readonly Dictionary<string, (int Count, int Last)> _used = [];
    private int _lastRound, _lastMessage = -100, _total, _wins, _losses;

    public void Reset()
    {
        _used.Clear(); _lastRound = _total = _wins = _losses = 0; _lastMessage = -100;
    }

    public static string Clean(string? text, int maxBytes = 320)
    {
        var result = new StringBuilder();
        var bytes = 0;
        foreach (var rune in (text ?? "").EnumerateRunes())
        {
            if (Rune.IsControl(rune) || Rune.GetUnicodeCategory(rune) == System.Globalization.UnicodeCategory.Format) continue;
            if (bytes + rune.Utf8SequenceLength > maxBytes) break;
            result.Append(rune); bytes += rune.Utf8SequenceLength;
        }
        return result.ToString().Trim();
    }

    public static bool Valid(ChatContract? c)
    {
        if (c is null || c.Version is not (1 or 2) || c.Rules is null || c.Rules.Count > 200
            || c.Scenes is null || c.Scenes.Count > 50 || (c.Version == 1 && c.Scenes.Count != 0)
            || c.Maximum is < 1 or > 12 || c.Cooldown is < 1 or > 20) return false;
        var ids = new HashSet<string>();
        foreach (var r in c.Rules)
        {
            if (r is null || string.IsNullOrEmpty(r.Id) || r.Id.Length > 180 || !ids.Add(r.Id)
                || r.When != "round_end" || r.Speaker is not ("coach" or "teammate" or "opponent")
                || r.Channel is not ("team" or "all") || (r.Speaker == "opponent" && r.Channel != "all")
                || r.Color is not ("default" or "green" or "blue" or "gold")
                || !double.IsFinite(r.Probability) || r.Probability is < 0 or > 1
                || r.Cooldown is < 1 or > 100 || r.Maximum is < 1 or > 200 || r.Priority is < -100 or > 100
                || r.Text is null || r.Text.Count is < 1 or > 20 || r.Conditions is null
                || (r.Speaker == "coach" && !string.IsNullOrEmpty(r.SpeakerId))) return false;
            foreach (var line in r.Text)
            {
                if (string.IsNullOrWhiteSpace(line) || line.Length > 360 || line.Any(ch => char.IsControl(ch) && ch != '\n')) return false;
                var rest = Token.Replace(line, m => Tokens.Contains(m.Groups[1].Value) ? "" : m.Value);
                if (rest.Contains('{') || rest.Contains('}')) return false;
            }
            foreach (var (key, value) in r.Conditions)
            {
                if (Numbers.Contains(key))
                {
                    if (value.ValueKind != JsonValueKind.Object) return false;
                    double min = -100000, max = 100000;
                    var count = 0;
                    foreach (var prop in value.EnumerateObject())
                    {
                        if (prop.Name is not ("min" or "max") || prop.Value.ValueKind != JsonValueKind.Number
                            || !prop.Value.TryGetDouble(out var n) || !double.IsFinite(n) || Math.Abs(n) > 100000) return false;
                        if (prop.Name == "min") min = n; else max = n;
                        count++;
                    }
                    if (count == 0 || min > max) return false;
                }
                else if (!Strings.Contains(key) || value.ValueKind != JsonValueKind.String || string.IsNullOrEmpty(value.GetString())) return false;
            }
        }
        foreach (var scene in c.Scenes)
        {
            if (scene is null || scene.Sequence is null || scene.Sequence.Count is < 1 or > 6
                || scene.Conditions is null || scene.Conditions.ContainsKey("speaker_id") || !ids.Add(scene.Id)
                || !Valid(new ChatContract { Version = 2, Rules = [scene.Gate()] })) return false;
            foreach (var step in scene.Sequence)
            {
                if (step is null || !double.IsFinite(step.Delay) || step.Delay is < 0.5 or > 3
                    || !Valid(new ChatContract { Version = 2, Rules = [Speech(step)] })) return false;
            }
        }
        return true;
    }

    private static ChatRule Speech(ChatStep step) => new() { Id = "step", When = "round_end",
        Speaker = step.Speaker, SpeakerId = step.SpeakerId, Channel = step.Channel, Color = step.Color, Text = [step.Text] };

    private ChatPerson? Speaker(ChatRule rule, string nonce, int round, List<ChatPerson> people, string humanTeam)
    {
        if (rule.Speaker == "coach") return new("coach", "教练", humanTeam, false);
        var pool = people.Where(p => p.IsBot && (rule.Speaker == "opponent" ? p.Team != humanTeam : p.Team == humanTeam)
            && (string.IsNullOrEmpty(rule.SpeakerId) || p.Id == rule.SpeakerId)).OrderBy(p => p.Id, StringComparer.Ordinal).ToList();
        return pool.Count == 0 ? null : pool[(int)(Draw(nonce, rule.Id + round + "speaker") % (uint)pool.Count)];
    }

    private static ChatMessage Render(ChatRule rule, string text, ChatPerson person, Dictionary<string,string> context)
    {
        context = new(context) { ["speaker"] = person.Name, ["speaker_id"] = person.Id };
        text = Token.Replace(text, m => context.GetValueOrDefault(m.Groups[1].Value, ""));
        var color = rule.Color switch { "green" => "\x04", "blue" => "\x0B", "gold" => "\x10", _ => "\x01" };
        var prefix = rule.Channel == "all" ? "[生涯·全部]" : "[生涯·队内]";
        var header = " " + color + prefix + Clean(person.Name, 32) + "：" + "\x01";
        return new(rule.Id, header + Clean(text, Math.Max(0, 180 - Encoding.UTF8.GetByteCount(header))), rule.Channel);
    }

    private bool Available(ChatRule rule, string nonce, int round)
    {
        var used = _used.GetValueOrDefault(rule.Id, (0, -100));
        return used.Item1 < rule.Maximum && round - used.Item2 >= rule.Cooldown
            && Draw(nonce, rule.Id + round + "chance") / 4294967296.0 < rule.Probability;
    }

    private void Consume(ChatRule rule, int round) => _used[rule.Id] = (_used.GetValueOrDefault(rule.Id).Count + 1, round);

    public ChatBatch EndRoundBatch(ChatContract? c, string nonce, int round, string result,
        Dictionary<string, string> context, List<ChatPerson> people, string humanTeam)
    {
        if (c?.Version == 1)
        {
            var old = EndRound(c, nonce, round, result, context, people, humanTeam);
            return new(false, old is null ? [] : [new(old, 0)]);
        }
        if (c is not { Enabled: true } || !Valid(c) || round <= 0) return new(false, []);
        if (round < _lastRound) Reset();
        if (round == _lastRound) return new(false, []);
        if (round > _lastRound + 1) _wins = _losses = 0;
        _lastRound = round;
        _wins = result == "win" ? _wins + 1 : 0;
        _losses = result == "loss" ? _losses + 1 : 0;
        context = new(context) { ["round"] = round.ToString(), ["result"] = result,
            ["win_streak"] = _wins.ToString(), ["loss_streak"] = _losses.ToString() };
        // Stable sort preserves registry/file/array order for equal priority.
        // Scenes always outrank ordinary chat, regardless of numeric priority.
        foreach (var scene in c.Scenes.OrderByDescending(s => s.Priority))
        {
            var gate = scene.Gate();
            if (!Available(gate, nonce, round) || !Matches(gate, context)) continue;
            var lines = new List<ScheduledChat>();
            var spoken = new HashSet<string>();
            double delay = 0;
            foreach (var step in scene.Sequence)
            {
                var speech = Speech(step);
                speech.Id = scene.Id; // Same unspecified teammate throughout a scene.
                var cast = scene.DistinctSpeakers ? people.Where(p => !spoken.Contains(p.Id)).ToList() : people;
                var person = Speaker(speech, nonce, round, cast, humanTeam);
                if (person is null) { lines.Clear(); break; } // Never deliver half a missing-cast scene.
                spoken.Add(person.Id);
                if (lines.Count > 0) delay += step.Delay;
                lines.Add(new(Render(speech, step.Text, person, context), delay));
            }
            if (lines.Count == 0) continue;
            Consume(gate, round);
            return new(true, lines);
        }
        var output = new List<ScheduledChat>();
        // Coach and players have separate per-round slots; opponents share players.
        foreach (var coach in new[] { true, false })
        {
            foreach (var rule in c.Rules.Where(r => (r.Speaker == "coach") == coach).OrderByDescending(r => r.Priority))
            {
                if (!Available(rule, nonce, round)) continue;
                var person = Speaker(rule, nonce, round, people, humanTeam);
                if (person is null) continue;
                var values = new Dictionary<string,string>(context) { ["speaker"] = person.Name, ["speaker_id"] = person.Id };
                if (!Matches(rule, values)) continue;
                var line = rule.Text[(int)(Draw(nonce, rule.Id + round + "line") % (uint)rule.Text.Count)];
                output.Add(new(Render(rule, line, person, values), output.Count * 1.5));
                Consume(rule, round); break;
            }
        }
        return new(false, output);
    }

    private static uint Draw(string nonce, string key) =>
        System.Buffers.Binary.BinaryPrimitives.ReadUInt32BigEndian(SHA256.HashData(Encoding.UTF8.GetBytes(nonce + "|" + key)));

    public ChatMessage? EndRound(ChatContract? c, string nonce, int round, string result,
        Dictionary<string, string> context, List<ChatPerson> people, string humanTeam)
    {
        if (c is not { Enabled: true } || !Valid(c) || round <= 0) return null;
        if (round < _lastRound) Reset(); // A fully restarted score begins a new cosmetic sequence.
        if (round == _lastRound) return null;
        if (round > _lastRound + 1) _wins = _losses = 0; // No inferred streak across missing rounds.
        _lastRound = round;
        _wins = result == "win" ? _wins + 1 : 0;
        _losses = result == "loss" ? _losses + 1 : 0;
        if (_total >= c.Maximum || round - _lastMessage < c.Cooldown) return null;
        context = new(context) { ["round"] = round.ToString(), ["result"] = result,
            ["win_streak"] = _wins.ToString(), ["loss_streak"] = _losses.ToString() };
        foreach (var rule in c.Rules.OrderByDescending(r => r.Priority).ThenBy(r => r.Id, StringComparer.Ordinal))
        {
            var used = _used.GetValueOrDefault(rule.Id, (0, -100));
            if (used.Item1 >= rule.Maximum || round - used.Item2 < rule.Cooldown) continue;
            var pool = people.Where(p => p.IsBot && (rule.Speaker == "opponent" ? p.Team != humanTeam : p.Team == humanTeam)
                && (string.IsNullOrEmpty(rule.SpeakerId) || p.Id == rule.SpeakerId)).OrderBy(p => p.Id, StringComparer.Ordinal).ToList();
            if (rule.Speaker != "coach" && pool.Count == 0) continue;
            var person = rule.Speaker == "coach" ? new ChatPerson("coach", "教练", humanTeam, false)
                : pool[(int)(Draw(nonce, rule.Id + round + "speaker") % (uint)pool.Count)];
            context["speaker"] = person.Name; context["speaker_id"] = person.Id;
            if (!Matches(rule, context) || Draw(nonce, rule.Id + round + "chance") / 4294967296.0 >= rule.Probability) continue;
            var line = rule.Text[(int)(Draw(nonce, rule.Id + round + "line") % (uint)rule.Text.Count)];
            line = Token.Replace(line, m => context.GetValueOrDefault(m.Groups[1].Value, ""));
            var color = rule.Color switch { "green" => "\x04", "blue" => "\x0B", "gold" => "\x10", _ => "\x01" };
            // Mark as scripted career dialogue, never impersonate a real chat packet.
            var prefix = rule.Channel == "all" ? "[生涯·全部]" : "[生涯·队内]";
            var header = " " + color + prefix + Clean(person.Name, 32) + "：" + "\x01";
            var output = header + Clean(line, Math.Max(0, 180 - Encoding.UTF8.GetByteCount(header)));
            _used[rule.Id] = (used.Item1 + 1, round); _total++; _lastMessage = round;
            return new(rule.Id, output, rule.Channel);
        }
        return null;
    }

    private static bool Matches(ChatRule rule, Dictionary<string, string> context)
    {
        foreach (var (key, condition) in rule.Conditions)
        {
            if (!context.TryGetValue(key, out var actual)) return false;
            if (Numbers.Contains(key))
            {
                if (!double.TryParse(actual, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var n)) return false;
                if (condition.TryGetProperty("min", out var min) && n < min.GetDouble()) return false;
                if (condition.TryGetProperty("max", out var max) && n > max.GetDouble()) return false;
            }
            else if (!string.Equals(actual, condition.GetString(), StringComparison.OrdinalIgnoreCase)) return false;
        }
        return true;
    }
}
