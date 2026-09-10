// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.Runtime.InteropServices;

namespace InventorySimulator;

public class CServerSideClientBase(nint handle)
{
	public nint Handle { get; set; } = handle;

	public bool IsValid => Handle != IntPtr.Zero;

	public ushort UserID => (ushort)Marshal.ReadInt16(Handle + Natives.CServerSideClientBase_m_UserID);
}
