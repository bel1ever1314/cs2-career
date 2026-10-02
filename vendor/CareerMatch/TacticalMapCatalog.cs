using System.Text.Json;

namespace CareerMatch;

// Shared build-time registry with the editor. No map bounds, radar image or
// script is supplied by an imported tactic. Live NAV, not radar pixels, resolves
// walkable positions and overlapping floors after these coarse bounds checks.
internal static class TacticalMapCatalog
{
    private sealed record Bounds(float MinX, float MinY, float MaxX, float MaxY,
        float? UpperMin, float? LowerMax);
    private static readonly IReadOnlyDictionary<string, Bounds> Maps = Load();

    internal static IEnumerable<string> MapIds => Maps.Keys;
    internal static bool IsSupported(string? map) => map is not null && Maps.ContainsKey(map);
    internal static bool Matches(string map, string? actual)
    {
        if (actual is null) return false;
        var canonical = actual.StartsWith("de_", StringComparison.OrdinalIgnoreCase)
            ? actual.ToLowerInvariant() : "de_" + actual.ToLowerInvariant();
        return IsSupported(map) && string.Equals(map, canonical, StringComparison.Ordinal);
    }
    internal static bool ContainsPoint(string map, float[]? value)
        => Maps.TryGetValue(map, out var bounds) && value is { Length: 2 } && value.All(float.IsFinite)
            && value[0] >= bounds.MinX && value[0] <= bounds.MaxX
            && value[1] >= bounds.MinY && value[1] <= bounds.MaxY;

    internal static bool IsLevelAllowed(string map, string level, float z)
        => Maps.TryGetValue(map, out var bounds) && float.IsFinite(z) && (level switch {
            "auto" => true,
            "upper" => bounds.UpperMin is not { } min || z >= min,
            "lower" => bounds.LowerMax is not { } max || z <= max,
            _ => false
        });

    private static IReadOnlyDictionary<string, Bounds> Load()
    {
        using var stream = typeof(TacticalMapCatalog).Assembly.GetManifestResourceStream("CareerMatch.TacticalMaps")
            ?? throw new InvalidDataException("tactical_map_registry_missing");
        using var document = JsonDocument.Parse(stream, new JsonDocumentOptions { MaxDepth = 16 });
        if (document.RootElement.GetProperty("schema_version").GetInt32() != 1)
            throw new InvalidDataException("tactical_map_registry_version");
        var maps = new Dictionary<string, Bounds>(StringComparer.Ordinal);
        foreach (var property in document.RootElement.GetProperty("maps").EnumerateObject())
        {
            var row = property.Value;
            double x = row.GetProperty("pos_x").GetDouble(), y = row.GetProperty("pos_y").GetDouble(),
                scale = row.GetProperty("scale").GetDouble();
            int width = row.GetProperty("width").GetInt32(), height = row.GetProperty("height").GetInt32();
            float? upperMin = null, lowerMax = null;
            var layers = row.GetProperty("layers").EnumerateArray().ToArray();
            if (layers.Any(layer => layer.GetProperty("id").GetString() == "lower"))
            {
                var upper = layers.Single(layer => layer.GetProperty("id").GetString() == "upper");
                var lower = layers.Single(layer => layer.GetProperty("id").GetString() == "lower");
                upperMin = (float)upper.GetProperty("altitude_min").GetDouble();
                lowerMax = (float)lower.GetProperty("altitude_max").GetDouble();
                if (!float.IsFinite(upperMin.Value) || !float.IsFinite(lowerMax.Value)
                    || Math.Abs(upperMin.Value) > 32768 || Math.Abs(lowerMax.Value) > 32768)
                    throw new InvalidDataException("tactical_map_registry_layers");
            }
            // The editor computes in doubles. Round each finished boundary
            // only once, exactly as its JSON world coordinate is parsed.
            var bounds = new Bounds((float)x, (float)(y-height*scale), (float)(x+width*scale), (float)y,
                upperMin, lowerMax);
            if (!property.Name.StartsWith("de_", StringComparison.Ordinal) || property.Name.Length > 32
                || property.Name.Any(c => !(c is >= 'a' and <= 'z' or >= '0' and <= '9' or '_'))
                || !double.IsFinite(scale) || scale <= 0 || width is <= 0 or > 4096 || height is <= 0 or > 4096
                || new[] {bounds.MinX, bounds.MinY, bounds.MaxX, bounds.MaxY}.Any(v => !float.IsFinite(v) || Math.Abs(v) > 32768)
                || !maps.TryAdd(property.Name, bounds))
                throw new InvalidDataException("tactical_map_registry_bounds");
        }
        if (maps.Count is 0 or > 32) throw new InvalidDataException("tactical_map_registry_count");
        return maps;
    }
}
