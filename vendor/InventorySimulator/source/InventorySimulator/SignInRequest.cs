// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.Text.Json.Serialization;

namespace InventorySimulator;

public class SignInRequest
{
	[JsonPropertyName("apiKey")]
	public required string ApiKey { get; set; }

	[JsonPropertyName("userId")]
	public required string UserId { get; set; }
}
