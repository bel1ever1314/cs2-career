// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
namespace InventorySimulator;

public static class ItemHelper
{
	public static bool IsMeleeDesignerName(string designerName)
	{
		if (!designerName.Contains("bayonet"))
		{
			return designerName.Contains("knife");
		}
		return true;
	}
}
