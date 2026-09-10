// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public static class CCSPlayerController_InventoryServicesExtensions
{
	public static CCSPlayerInventory GetInventory(this CCSPlayerController_InventoryServices self)
	{
		return new CCSPlayerInventory(self.Handle + Natives.CCSPlayerController_InventoryServices_m_pInventory);
	}
}
