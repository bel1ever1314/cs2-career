// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
namespace InventorySimulator;

public static class TeamHelper
{
	public static byte ToggleTeam(byte team)
	{
		if (team <= 1)
		{
			return team;
		}
		if (team != 2)
		{
			return 2;
		}
		return 3;
	}
}
