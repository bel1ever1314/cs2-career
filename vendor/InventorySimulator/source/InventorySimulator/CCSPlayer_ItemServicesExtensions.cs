// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public static class CCSPlayer_ItemServicesExtensions
{
	public static CCSPlayerController? GetController(this CCSPlayer_ItemServices self)
	{
		CBasePlayerPawn value = self.Pawn.Value;
		if (!(value != null) || !(value.Controller.Value != null))
		{
			return null;
		}
		return value.Controller.Value.As<CCSPlayerController>();
	}

	public static void UpdateWearables(this CCSPlayer_ItemServices self)
	{
		Natives.CCSPlayer_ItemServices_SetWearables.Invoke(self.Handle);
	}
}
