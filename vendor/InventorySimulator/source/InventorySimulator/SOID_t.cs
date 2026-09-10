// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
namespace InventorySimulator;

public readonly struct SOID_t
{
	private readonly ulong m_id;

	private readonly uint m_type;

	private readonly uint m_padding;

	public ulong SteamID => m_id;

	public ulong Part1 => m_id;

	public ulong Part2 => m_type;
}
