// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace InventorySimulator;

public class InventoryItem
{
	private (int? statTrak, List<(string, float)> attributes)? _attributesCache;

	[JsonPropertyName("charges")]
	public int? Charges { get; set; }

	[JsonPropertyName("def")]
	public ushort? Def { get; set; }

	[JsonPropertyName("hash")]
	public string? Hash { get; set; }

	[JsonPropertyName("keychains")]
	public List<KeychainItem>? Keychains { get; set; }

	[JsonPropertyName("musicId")]
	public int? MusicId { get; set; }

	[JsonPropertyName("nametag")]
	public string? Nametag { get; set; }

	[JsonPropertyName("paint")]
	public int? Paint { get; set; }

	[JsonPropertyName("seed")]
	public int? Seed { get; set; }

	[JsonPropertyName("stattrak")]
	public int? Stattrak { get; set; }

	[JsonPropertyName("stickers")]
	public List<StickerItem>? Stickers { get; set; }

	[JsonPropertyName("tint")]
	public int? Tint { get; set; }

	[JsonPropertyName("uid")]
	public int? Uid { get; set; }

	[JsonPropertyName("wear")]
	public float? Wear { get; set; }

	public float? WearOverride { get; set; }

	public override int GetHashCode()
	{
		return Hash?.GetHashCode() ?? 0;
	}

	public override bool Equals(object? obj)
	{
		if (!(obj is InventoryItem inventoryItem))
		{
			return false;
		}
		return Hash == inventoryItem.Hash;
	}

	public static bool operator ==(InventoryItem? left, InventoryItem? right)
	{
		if ((object)left == right)
		{
			return true;
		}
		if ((object)left == null || (object)right == null)
		{
			return false;
		}
		return left.Equals(right);
	}

	public static bool operator !=(InventoryItem? left, InventoryItem? right)
	{
		return !(left == right);
	}

	public List<(string, float)> GetAttributes()
	{
		if (_attributesCache.HasValue && _attributesCache.Value.statTrak == Stattrak)
		{
			return _attributesCache.Value.attributes;
		}
		List<(string, float)> list = new List<(string, float)>();
		if (Paint.HasValue)
		{
			list.Add(("set item texture prefab", Paint.Value));
		}
		if (Seed.HasValue)
		{
			list.Add(("set item texture seed", Seed.Value));
		}
		float? num = WearOverride ?? Wear;
		if (num.HasValue)
		{
			list.Add(("set item texture wear", num.Value));
		}
		if (Stattrak.HasValue && Stattrak > -1)
		{
			float item = TypeHelper.ViewAs<int, float>(Stattrak.Value);
			list.Add(("kill eater", item));
			list.Add(("kill eater score type", 0f));
		}
		if (Stickers != null)
		{
			foreach (StickerItem sticker in Stickers)
			{
				string text = $"sticker slot {sticker.Slot}";
				float item2 = TypeHelper.ViewAs<uint, float>(sticker.Def);
				list.Add((text + " id", item2));
				if (sticker.Schema.HasValue)
				{
					float item3 = TypeHelper.ViewAs<uint, float>(sticker.Schema.Value);
					list.Add((text + " schema", item3));
				}
				if (sticker.Wear.HasValue)
				{
					list.Add((text + " wear", sticker.Wear.Value));
				}
				if (sticker.Rotation.HasValue)
				{
					list.Add((text + " rotation", sticker.Rotation.Value));
				}
				if (sticker.X.HasValue)
				{
					list.Add((text + " offset x", sticker.X.Value));
				}
				if (sticker.Y.HasValue)
				{
					list.Add((text + " offset y", sticker.Y.Value));
				}
			}
		}
		if (Keychains != null)
		{
			foreach (KeychainItem keychain in Keychains)
			{
				string text2 = $"keychain slot {keychain.Slot}";
				float item4 = TypeHelper.ViewAs<uint, float>(keychain.Def);
				list.Add((text2 + " id", item4));
				float item5 = TypeHelper.ViewAs<int, float>(keychain.Seed);
				list.Add((text2 + " seed", item5));
				if (keychain.Sticker.HasValue)
				{
					float item6 = TypeHelper.ViewAs<uint, float>(keychain.Sticker.Value);
					list.Add((text2 + " sticker", item6));
				}
				if (keychain.X.HasValue)
				{
					list.Add((text2 + " offset x", keychain.X.Value));
				}
				if (keychain.Y.HasValue)
				{
					list.Add((text2 + " offset y", keychain.Y.Value));
				}
				if (keychain.Z.HasValue)
				{
					list.Add((text2 + " offset z", keychain.Z.Value));
				}
			}
		}
		if (MusicId.HasValue)
		{
			float item7 = TypeHelper.ViewAs<int, float>(MusicId.Value);
			list.Add(("music id", item7));
		}
		_attributesCache = (Stattrak, list);
		return list;
	}
}
