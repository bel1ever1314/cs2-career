// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public static class Runtime
{
	public static BasePlugin Plugin { get; set; }

	public static void Initialize(BasePlugin plugin)
	{
		Plugin = plugin;
	}
}
