// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.Text.Json.Serialization;

namespace InventorySimulator;

public class StickerItem
{
	[JsonPropertyName("def")]
	public uint Def { get; set; }

	[JsonPropertyName("rotation")]
	public float? Rotation { get; set; }

	[JsonPropertyName("schema")]
	public uint? Schema { get; set; }

	[JsonPropertyName("slot")]
	public uint Slot { get; set; }

	[JsonPropertyName("wear")]
	public float? Wear { get; set; }

	[JsonPropertyName("x")]
	public float? X { get; set; }

	[JsonPropertyName("y")]
	public float? Y { get; set; }
}
