// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
namespace InventorySimulator;

public class CSteamID(ulong ulSteamID)
{
	public ulong m_SteamID = ulSteamID;

	public AccountID_t GetAccountID()
	{
		return new AccountID_t((uint)(m_SteamID & 0xFFFFFFFFu));
	}
}
