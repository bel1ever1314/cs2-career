// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.Text.Json.Serialization;

namespace InventorySimulator;

public class ConsumeItemSprayRequest
{
	[JsonPropertyName("apiKey")]
	[JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
	public string? ApiKey { get; set; }

	[JsonPropertyName("targetUid")]
	public required int TargetUid { get; set; }

	[JsonPropertyName("userId")]
	public required string UserId { get; set; }
}
