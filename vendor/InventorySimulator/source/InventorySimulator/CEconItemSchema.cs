// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;

namespace InventorySimulator;

public class CEconItemSchema(nint handle)
{
	public nint Handle { get; set; } = handle;

	public bool IsValid => Handle != IntPtr.Zero;

	public CEconItemDefinition? GetItemDefinitionByName(string pchName)
	{
		CEconItemDefinition cEconItemDefinition = new CEconItemDefinition(Natives.CEconItemSchema_GetItemDefinitionByName.Invoke(Handle, pchName));
		if (!cEconItemDefinition.IsValid)
		{
			return null;
		}
		return cEconItemDefinition;
	}

	public CEconItemDefinition? GetItemDefinition(uint defIndex)
	{
		CEconItemDefinition cEconItemDefinition = new CEconItemDefinition(Natives.CEconItemSchema_GetItemDefinition.Invoke(Handle, defIndex, 0));
		if (!cEconItemDefinition.IsValid)
		{
			return null;
		}
		return cEconItemDefinition;
	}
}
