// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public static class CAttributeListExtensions
{
	public static void SetOrAddAttributeValueByName(this CAttributeList self, string name, float value)
	{
		Natives.CAttributeList_SetOrAddAttributeValueByName.Invoke(self.Handle, name, value);
	}
}
