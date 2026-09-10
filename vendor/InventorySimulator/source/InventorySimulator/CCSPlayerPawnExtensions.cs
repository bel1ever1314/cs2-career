// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public static class CCSPlayerPawnExtensions
{
	public static bool IsAbleToApplySpray(this CCSPlayerPawn self, nint ptr = 0)
	{
		return Natives.CCSPlayerPawn_IsAbleToApplySpray.Invoke(self.Handle, ptr, 0, 0) == IntPtr.Zero;
	}

	public static void SetModelFromLoadout(this CCSPlayerPawn self)
	{
		Natives.CCSPlayerPawn_SetModelFromLoadout.Invoke(self.Handle);
	}

	public static void SetModelFromClass(this CCSPlayerPawn self)
	{
		Natives.CCSPlayerPawn_SetModelFromClass.Invoke(self.Handle);
	}
}
