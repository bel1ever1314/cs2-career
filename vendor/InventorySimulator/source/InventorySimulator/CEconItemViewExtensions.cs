// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.Collections.Generic;
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public static class CEconItemViewExtensions
{
	public static readonly ulong MinimumCustomItemID = 65155030971uL;

	private static ulong NextItemId = MinimumCustomItemID;

	public static void ApplyAttributes(this CEconItemView self, InventoryItem item, loadout_slot_t? slot, ulong? steamId)
	{
		bool num = slot == loadout_slot_t.LOADOUT_SLOT_MELEE;
		self.Initialized = true;
		if (item.Def.HasValue)
		{
			self.ItemDefinitionIndex = item.Def.Value;
		}
		ulong num2 = NextItemId++;
		self.ItemID = num2;
		self.ItemIDLow = (uint)(num2 & 0xFFFFFFFFu);
		self.ItemIDHigh = (uint)(num2 >> 32);
		if (steamId.HasValue)
		{
			self.AccountID = new CSteamID(steamId.Value).GetAccountID().m_AccountID;
		}
		if (num)
		{
			self.EntityQuality = 3;
		}
		else
		{
			self.EntityQuality = ((item.Stattrak >= 0) ? 9 : 4);
		}
		if (item.Nametag != null)
		{
			self.CustomName = item.Nametag;
		}
		List<(string, float)> attributes = item.GetAttributes();
		CAttributeList networkedDynamicAttributes = self.NetworkedDynamicAttributes;
		networkedDynamicAttributes.Attributes.RemoveAll();
		foreach (var (name, value) in attributes)
		{
			networkedDynamicAttributes.SetOrAddAttributeValueByName(name, value);
		}
	}
}
