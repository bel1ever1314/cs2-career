// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.Numerics;
using System.Runtime.InteropServices;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Memory;
using CounterStrikeSharp.API.Modules.Utils;

namespace InventorySimulator;

public static class SchemaHelper
{
	public static CEconItemView CreateCEconItemView(nint copyFrom = 0)
	{
		nint num = Marshal.AllocHGlobal(Schema.GetClassSize("CEconItemView"));
		Natives.CEconItemView_Constructor.Invoke(num);
		if (copyFrom != IntPtr.Zero)
		{
			Natives.CEconItemView_OperatorEquals.Invoke(num, copyFrom);
		}
		return new CEconItemView(num);
	}

	public static CEconItemSchema? GetItemSchema()
	{
		CEconItemSchema cEconItemSchema = new CEconItemSchema(Natives.GetItemSchema.Invoke());
		if (!cEconItemSchema.IsValid)
		{
			return null;
		}
		return cEconItemSchema;
	}

	public static CounterStrikeSharp.API.Modules.Utils.Vector ToVector(Vector3 vec)
	{
		return new CounterStrikeSharp.API.Modules.Utils.Vector(vec.X, vec.Y, vec.Z);
	}
}
