using CounterStrikeSharp.API.Core;
using System.Text.Json;

namespace BotBuyPatch;

public sealed partial class BotBuyPatch
{
    private string _humanGiftRole = "";
    private ulong _humanGiftSteamId;

    private void ReadHumanGiftRole(JsonElement root)
    {
        _humanGiftRole = ""; _humanGiftSteamId = 0;
        if (root.TryGetProperty("observer", out var observer) && observer.ValueKind == JsonValueKind.True) return;
        if (root.TryGetProperty("human_role", out var role) && role.ValueKind == JsonValueKind.String)
            _humanGiftRole = role.GetString() ?? "";
    }

    private void BindHumanGiftRecipient(List<CCSPlayerController> players)
    {
        _humanGiftSteamId = 0;
        if (!_careerActive || string.IsNullOrEmpty(_humanGiftRole)) return;
        // BotHider can clear IsBot. A genuine human body must also have no
        // native Bot and no synthetic roster identity. Never bind by nickname
        // or opening team (teams change at halftime).
        var humans = players.Where(p => p.IsValid && !p.IsBot && !p.IsHLTV
            && !p.ControllingBot && p.SteamID != 0 && !_careerRoles.ContainsKey(p.SteamID)
            && p.TeamNum is 2 or 3 && p.PlayerPawn.Value is { IsValid: true, Bot: null }).ToArray();
        if (humans.Length == 1) _humanGiftSteamId = humans[0].SteamID;
    }

    private bool WantsSniperGift(CCSPlayerController player)
    {
        if (!_careerActive) return false;
        if (_careerRoles.ContainsKey(player.SteamID)) return PurchaseRole(player) == "awp";
        return _humanGiftSteamId != 0 && player.SteamID == _humanGiftSteamId
            && !player.ControllingBot && player.PlayerPawn.Value is { Bot: null }
            && _humanGiftRole == "awp";
    }
}
