// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public static class CCSPlayer_WeaponServicesExtensions
{
	public static void DropWeapon(this CCSPlayer_WeaponServices self, CBasePlayerWeapon weapon)
	{
		Natives.CCSPlayer_WeaponServices_DropWeapon(self.Handle, weapon.Handle);
	}
}
