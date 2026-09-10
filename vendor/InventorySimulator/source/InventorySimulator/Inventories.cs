// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.Collections.Generic;
using System.Diagnostics.CodeAnalysis;
using System.IO;
using System.Linq;
using System.Text.Json;
using CounterStrikeSharp.API;
using Microsoft.Extensions.Logging;

namespace InventorySimulator;

public static class Inventories
{
	private static readonly Dictionary<ulong, PlayerInventory> _loadedInventories = new Dictionary<ulong, PlayerInventory>();

	private static readonly string _inventoryFileDir = "csgo/addons/counterstrikesharp/configs/plugins/InventorySimulator";

	public static bool Load(string filename)
	{
		try
		{
			string text = new string[2]
			{
				Path.Combine(Server.GameDirectory, _inventoryFileDir, filename),
				Path.Combine(Server.GameDirectory, "csgo", filename)
			}.FirstOrDefault(File.Exists) ?? ((Path.IsPathRooted(filename) && File.Exists(filename)) ? filename : null);
			if (text == null)
			{
				return false;
			}
			Dictionary<ulong, PlayerInventory> dictionary = Parse(File.ReadAllText(text));
			_loadedInventories.Clear();
			foreach (KeyValuePair<ulong, PlayerInventory> item in dictionary)
			{
				_loadedInventories.TryAdd(item.Key, item.Value);
			}
			Runtime.Plugin.Logger.LogInformation("Loaded {Count} career inventories from \"{File}\".", dictionary.Count, filename);
			return dictionary.Count > 0;
		}
		catch
		{
			Runtime.Plugin.Logger.LogError("Error when processing \"{File}\".", filename);
			return false;
		}
	}

	private static Dictionary<ulong, PlayerInventory> Parse(string json)
	{
		Dictionary<ulong, PlayerInventory> dictionary = new Dictionary<ulong, PlayerInventory>();
		try
		{
			Dictionary<ulong, EquippedV5Response> dictionary2 = JsonSerializer.Deserialize<Dictionary<ulong, EquippedV5Response>>(json);
			if (dictionary2 != null)
			{
				foreach (KeyValuePair<ulong, EquippedV5Response> item in dictionary2)
				{
					dictionary[item.Key] = new PlayerInventory(item.Value);
				}
			}
		}
		catch
		{
		}
		if (dictionary.Count > 0)
		{
			return dictionary;
		}
		using JsonDocument jsonDocument = JsonDocument.Parse(json);
		foreach (JsonProperty item2 in jsonDocument.RootElement.EnumerateObject())
		{
			if (ulong.TryParse(item2.Name, out var result))
			{
				JsonElement jsonElement = item2.Value;
				if (jsonElement.ValueKind == JsonValueKind.Object && jsonElement.TryGetProperty("data", out var value))
				{
					jsonElement = value;
				}
				EquippedV5Response equippedV5Response = JsonSerializer.Deserialize<EquippedV5Response>(jsonElement.GetRawText());
				if (equippedV5Response != null)
				{
					dictionary[result] = new PlayerInventory(equippedV5Response);
				}
			}
		}
		return dictionary;
	}

	public static bool Has(ulong steamId)
	{
		return _loadedInventories.ContainsKey(steamId);
	}

	public static bool TryGet(ulong steamId, [MaybeNullWhen(false)] out PlayerInventory inventory)
	{
		if (_loadedInventories.TryGetValue(steamId, out PlayerInventory value))
		{
			inventory = value;
			return true;
		}
		inventory = null;
		return false;
	}

	public static PlayerInventory? Get(ulong steamId)
	{
		if (!_loadedInventories.TryGetValue(steamId, out PlayerInventory value))
		{
			return null;
		}
		return value;
	}
}
