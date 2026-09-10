// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public static class CBasePlayerWeaponExtensions
{
	public static string GetDesignerName(this CBasePlayerWeapon self)
	{
		string text = SchemaHelper.GetItemSchema()?.GetItemDefinition(self.AttributeManager.Item.ItemDefinitionIndex)?.DefinitionName ?? self.DesignerName;
		if (!ItemHelper.IsMeleeDesignerName(text))
		{
			return text;
		}
		return "weapon_knife";
	}

	public static bool HasCustomItemID(this CBasePlayerWeapon self)
	{
		return self.AttributeManager.Item.ItemID >= CEconItemViewExtensions.MinimumCustomItemID;
	}
}
