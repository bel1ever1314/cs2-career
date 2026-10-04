using System.Text.Json;
using System.Text.Json.Serialization;

namespace CareerTactics;

// The capability uses only System.Func<string,string>. No assembly-specific
// interface crosses plugin load contexts, no console command or per-tick file IO.
public sealed class TacticalBuyPlan
{
    public const string CapabilityName = "career:tactical-buy:v1";
    [JsonRequired, JsonPropertyName("nonce")] public string Nonce { get; set; } = "";
    [JsonRequired, JsonPropertyName("map")] public string Map { get; set; } = "";
    [JsonRequired, JsonPropertyName("round")] public int Round { get; set; }
    [JsonRequired, JsonPropertyName("side")] public string Side { get; set; } = "";
    [JsonRequired, JsonPropertyName("duties")] public Dictionary<ulong, string> Duties { get; set; } = [];

    public static TacticalBuyPlan Parse(string json)
    {
        if (System.Text.Encoding.UTF8.GetByteCount(json) > 4096) throw new InvalidDataException("buy_plan_too_large");
        using var doc = JsonDocument.Parse(json, new JsonDocumentOptions { MaxDepth = 4 });
        void CheckKeys(JsonElement value)
        {
            if (value.ValueKind != JsonValueKind.Object) return;
            var keys = new HashSet<string>(StringComparer.Ordinal);
            foreach (var property in value.EnumerateObject())
            { if (!keys.Add(property.Name)) throw new InvalidDataException("buy_plan_duplicate_key"); CheckKeys(property.Value); }
        }
        CheckKeys(doc.RootElement);
        var result = JsonSerializer.Deserialize<TacticalBuyPlan>(json, new JsonSerializerOptions {
            UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow, MaxDepth = 4
        }) ?? throw new InvalidDataException("buy_plan_missing");
        if (string.IsNullOrWhiteSpace(result.Nonce) || result.Nonce.Length > 128
            || string.IsNullOrWhiteSpace(result.Map) || result.Map.Length > 32
            || result.Round is < 0 or > 10000 || result.Side is not ("ct" or "t")
            || result.Duties is null || result.Duties.Count > 4
            || result.Duties.Any(d => d.Key == 0 || !ValidDuty(d.Value)))
            throw new InvalidDataException("buy_plan_invalid");
        return result;
    }
    public static bool ValidDuty(string? duty) => duty is "auto" or "awp" or "entry" or "lurk" or "rifle" or "igl";
    public bool Matches(string nonce, string map, int round, bool active, bool buying,
        IReadOnlyDictionary<ulong, string> rosterSides) => active && buying && Nonce == nonce
        && Map == map && Round == round && Duties.Keys.All(id => rosterSides.GetValueOrDefault(id) == Side);
}

internal static class TacticalBuyPolicy
{
    internal const int AwpPrice = 4750;
    internal static int PrimaryPrice(string weapon) => weapon switch {
        "weapon_mac10" => 1050, "weapon_mp9" => 1250, "weapon_mp7" or "weapon_mp5sd" => 1500,
        "weapon_ump45" => 1200, "weapon_bizon" => 1400, "weapon_p90" => 2350,
        "weapon_nova" => 1050, "weapon_xm1014" => 2000, "weapon_sawedoff" => 1100, "weapon_mag7" => 1300,
        "weapon_galilar" => 1800, "weapon_ak47" => 2700, "weapon_sg556" => 3000,
        "weapon_famas" => 1950, "weapon_m4a1" or "weapon_m4a1_silencer" => 2900, "weapon_aug" => 3300,
        "weapon_ssg08" => 1700, "weapon_awp" => AwpPrice, "weapon_scar20" or "weapon_g3sg1" => 5000,
        "weapon_negev" => 1700, "weapon_m249" => 5200, _ => 0
    };
    internal static bool PrimaryAllowed(bool ct, string weapon) => PrimaryPrice(weapon) > 0 && (weapon switch {
        "weapon_famas" or "weapon_m4a1" or "weapon_m4a1_silencer" or "weapon_aug"
            or "weapon_scar20" or "weapon_mp9" or "weapon_mag7" => ct,
        "weapon_galilar" or "weapon_ak47" or "weapon_sg556" or "weapon_g3sg1"
            or "weapon_mac10" or "weapon_sawedoff" => !ct,
        _ => true
    });
    internal static bool CanReplace(string duty, string weapon, int money, uint entity, uint bought,
        bool existedAtStart, int matchingItems, bool refundable, int reserve = 0, int maxMoney = 16000) => duty == "awp" && weapon != "weapon_awp"
        && PrimaryPrice(weapon) > 0 && money >= 0 && reserve >= 0 && maxMoney > 0
        && Math.Min((long)maxMoney, (long)money + PrimaryPrice(weapon)) >= AwpPrice + (long)reserve
        && entity != 0 && entity == bought && !existedAtStart && matchingItems == 1 && refundable;
}
