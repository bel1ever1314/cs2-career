using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace CareerMatch;

// Shared with the pure contract regression tests; order matches profiles.py.
public static class ManifestDigest
{
    public static string Compute(JsonElement node)
    {
        var lines = new List<string>
        {
            $"schema_version={node.GetProperty("schema_version").GetInt32()}",
            $"type={node.GetProperty("type").GetString()}",
            $"nonce={node.GetProperty("nonce").GetString()}",
            $"difficulty={node.GetProperty("difficulty").GetString()}",
            $"count={node.GetProperty("count").GetInt32()}",
            $"vpk_sha256={node.GetProperty("vpk_sha256").GetString()}",
        };
        if (node.TryGetProperty("difficulty_model", out var model) && !string.IsNullOrEmpty(model.GetString()))
        {
            lines.Add($"difficulty_model={model.GetString()}");
            lines.Add($"preset_source_hash={node.GetProperty("preset_source_hash").GetString()}");
            lines.Add($"template_hash={node.GetProperty("template_hash").GetString()}");
        }
        foreach (var bot in node.GetProperty("bots").EnumerateArray()
                     .OrderBy(x => x.GetProperty("player_id").GetString(), StringComparer.Ordinal))
        {
            lines.Add("bot=" + string.Join("|", new[]
            {
                bot.GetProperty("player_id").GetString() ?? "",
                bot.GetProperty("profile_name").GetString() ?? "",
                bot.GetProperty("side").GetString() ?? "",
                bot.GetProperty("profile_hash").GetString() ?? "",
                bot.GetProperty("avatar_hash").GetString() ?? "",
            }));
        }
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join("\n", lines))))
            .ToLowerInvariant();
    }

}
