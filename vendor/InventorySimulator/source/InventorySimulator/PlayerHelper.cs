// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public static class PlayerHelper
{
	public static CCSPlayerController? GetPlayerFromSteamId(ulong steamId)
	{
		return GetPlayerFromAccountId(new CSteamID(steamId).GetAccountID().m_AccountID);
	}

	public static CCSPlayerController? GetPlayerFromAccountId(uint accountId)
	{
		if (accountId == 0)
		{
			return null;
		}
		for (int i = 0; i < Server.MaxPlayers; i++)
		{
			CCSPlayerController playerFromSlot = Utilities.GetPlayerFromSlot(i);
			if ((object)playerFromSlot != null && playerFromSlot.IsValid && new CSteamID(playerFromSlot.SteamID).GetAccountID().m_AccountID == accountId)
			{
				return playerFromSlot;
			}
		}
		return null;
	}
}
