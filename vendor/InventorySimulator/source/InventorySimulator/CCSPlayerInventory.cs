// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.Runtime.InteropServices;
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public class CCSPlayerInventory(nint handle)
{
	public nint Handle { get; set; } = handle;

	public bool IsValid
	{
		get
		{
			if (Handle != IntPtr.Zero)
			{
				return SOCache.IsValid;
			}
			return false;
		}
	}

	public ulong SteamID => SOCache.Owner.SteamID;

	public CGCClientSharedObjectCache SOCache => new CGCClientSharedObjectCache(Marshal.ReadIntPtr(Handle + Natives.CCSPlayerInventory_m_pSOCache));

	public nint GetItemInLoadout(byte team, loadout_slot_t slot)
	{
		return Natives.CCSPlayerInventory_GetItemInLoadout.Invoke(Handle, team, (int)slot);
	}

	public void SendInventoryUpdateEvent()
	{
		Natives.CCSPlayerInventory_SendInventoryUpdateEvent.Invoke(Handle);
	}
}
