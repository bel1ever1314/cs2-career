// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.Runtime.InteropServices;
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public class CEconItemDefinition(nint handle)
{
	public nint Handle { get; set; } = handle;

	public bool IsValid => Handle != IntPtr.Zero;

	public ushort DefIndex => (ushort)Marshal.ReadInt16(Handle + 16);

	public string? DefinitionName
	{
		get
		{
			nint num = Marshal.ReadIntPtr(Handle + 608);
			if (num == IntPtr.Zero)
			{
				return null;
			}
			return Marshal.PtrToStringUTF8(num);
		}
	}

	public loadout_slot_t DefaultLoadoutSlot => (loadout_slot_t)Marshal.ReadInt32(Handle + 824);
}
