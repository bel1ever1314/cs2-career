// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace InventorySimulator;

public class EquippedV5Response
{
	[JsonPropertyName("agents")]
	public Dictionary<byte, InventoryItem> Agents { get; set; } = new Dictionary<byte, InventoryItem>();

	[JsonPropertyName("collectible")]
	public InventoryItem? Collectible { get; set; }

	[JsonPropertyName("ctWeapons")]
	public Dictionary<ushort, InventoryItem> CTWeapons { get; set; } = new Dictionary<ushort, InventoryItem>();

	[JsonPropertyName("gloves")]
	public Dictionary<byte, InventoryItem> Gloves { get; set; } = new Dictionary<byte, InventoryItem>();

	[JsonPropertyName("graffiti")]
	public InventoryItem? Graffiti { get; set; }

	[JsonPropertyName("knives")]
	public Dictionary<byte, InventoryItem> Knives { get; set; } = new Dictionary<byte, InventoryItem>();

	[JsonPropertyName("musicKit")]
	public InventoryItem? MusicKit { get; set; }

	[JsonPropertyName("tWeapons")]
	public Dictionary<ushort, InventoryItem> TWeapons { get; set; } = new Dictionary<ushort, InventoryItem>();
}
