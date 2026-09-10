// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using CounterStrikeSharp.API.Core.Translations;

namespace InventorySimulator;

public static class Rules
{
	public static bool IsOwned(ulong steamId)
	{
		if (steamId == 0L)
		{
			return false;
		}
		string text = (ConVars.OnlySteamId.Value ?? "").Trim();
		if (text.Length > 0 && ulong.TryParse(text, out var result))
		{
			return steamId == result;
		}
		return Inventories.Has(steamId);
	}

	public static string GetChatPrefix(bool stripColors = false)
	{
		string value = ConVars.ChatPrefix.Value;
		if (value != "")
		{
			return (stripColors ? value.StripColorTags() : value.ReplaceColorTags()) + " ";
		}
		return "";
	}
}
