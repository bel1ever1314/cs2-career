// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.Runtime.InteropServices;

namespace InventorySimulator;

public struct CGCClientSharedObjectCache(nint handle)
{
	public nint Handle { get; set; } = handle;

	public readonly bool IsValid => Handle != IntPtr.Zero;

	public readonly SOID_t Owner
	{
		get
		{
			if (IsValid)
			{
				return Marshal.PtrToStructure<SOID_t>(Handle + Natives.CGCClientSharedObjectCache_m_Owner);
			}
			throw new InvalidOperationException("Invalid cache.");
		}
	}
}
