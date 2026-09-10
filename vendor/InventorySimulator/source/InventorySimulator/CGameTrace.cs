// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.Numerics;
using System.Runtime.InteropServices;

namespace InventorySimulator;

[StructLayout(LayoutKind.Explicit, Size = 192)]
public struct CGameTrace
{
	[FieldOffset(132)]
	public Vector3 EndPos;

	[FieldOffset(144)]
	public Vector3 HitNormal;
}
