// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.Text.Json.Serialization;

namespace InventorySimulator;

public class KeychainItem
{
	[JsonPropertyName("def")]
	public uint Def { get; set; }

	[JsonPropertyName("seed")]
	public int Seed { get; set; }

	[JsonPropertyName("slot")]
	public uint Slot { get; set; }

	[JsonPropertyName("sticker")]
	public uint? Sticker { get; set; }

	[JsonPropertyName("x")]
	public float? X { get; set; }

	[JsonPropertyName("y")]
	public float? Y { get; set; }

	[JsonPropertyName("z")]
	public float? Z { get; set; }
}
