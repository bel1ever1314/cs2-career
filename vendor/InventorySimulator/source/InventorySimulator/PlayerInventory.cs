// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.Collections.Generic;
using System.Linq;
using CounterStrikeSharp.API.Core;

namespace InventorySimulator;

public class PlayerInventory(EquippedV5Response data)
{
	private readonly EquippedV5Response _data = data;

	public Dictionary<(int paint, float wear), (ushort def, string stickers)> WeaponWearCache = new Dictionary<(int, float), (ushort, string)>();

	public Dictionary<byte, InventoryItem> Agents => _data.Agents;

	public InventoryItem? MusicKit => _data.MusicKit;

	public InventoryItem? Graffiti => _data.Graffiti;

	public static PlayerInventory Empty()
	{
		return new PlayerInventory(new EquippedV5Response());
	}

	public void InitializeWearOverrides()
	{
		foreach (InventoryItem value in _data.Knives.Values)
		{
			value.WearOverride = GetWeaponWear(value);
		}
		foreach (InventoryItem value2 in _data.CTWeapons.Values)
		{
			value2.WearOverride = GetWeaponWear(value2);
		}
		foreach (InventoryItem value3 in _data.TWeapons.Values)
		{
			value3.WearOverride = GetWeaponWear(value3);
		}
	}

	public InventoryItem? GetKnife(byte team, bool fallback)
	{
		if (_data.Knives.TryGetValue(team, out InventoryItem value))
		{
			return value;
		}
		if (fallback && _data.Knives.TryGetValue(TeamHelper.ToggleTeam(team), out value))
		{
			return value;
		}
		return null;
	}

	public Dictionary<ushort, InventoryItem> GetWeapons(byte team)
	{
		if (team != 2)
		{
			return _data.CTWeapons;
		}
		return _data.TWeapons;
	}

	public InventoryItem? GetWeapon(byte team, ushort def, bool fallback)
	{
		if (GetWeapons(team).TryGetValue(def, out InventoryItem value))
		{
			return value;
		}
		if (fallback && GetWeapons(TeamHelper.ToggleTeam(team)).TryGetValue(def, out value))
		{
			return value;
		}
		return null;
	}

	public InventoryItem? GetGloves(byte team, bool fallback)
	{
		if (_data.Gloves.TryGetValue(team, out InventoryItem value))
		{
			return value;
		}
		if (fallback && _data.Gloves.TryGetValue(TeamHelper.ToggleTeam(team), out value))
		{
			return value;
		}
		return null;
	}

	private float GetWeaponWear(InventoryItem item)
	{
		if ((object)item == null || !item.Def.HasValue || !item.Paint.HasValue || !item.Wear.HasValue || item.Stickers == null)
		{
			return 0f;
		}
		ushort value = item.Def.Value;
		int value2 = item.Paint.Value;
		float num = item.Wear.Value;
		string text = string.Join("_", from s in item.Stickers
			orderby s.Slot
			select $"{s.Slot}:{s.Def}:{s.Schema}:{s.Wear}:{s.Rotation}:{s.X}:{s.Y}");
		(ushort, string) value3;
		for (; WeaponWearCache.TryGetValue((value2, num), out value3); num += 0.001f)
		{
			if (value3.Item1 == value && !(value3.Item2 != text))
			{
				break;
			}
		}
		WeaponWearCache[(value2, num)] = (value, text);
		return num;
	}

	public InventoryItem? GetItemForSlot(byte team, loadout_slot_t slot, ushort def, bool fallback, int minModels = 0)
	{
		if (slot >= loadout_slot_t.LOADOUT_SLOT_MELEE)
		{
			switch (slot)
			{
			case loadout_slot_t.LOADOUT_SLOT_C4:
			case loadout_slot_t.LOADOUT_SLOT_SECONDARY0:
			case loadout_slot_t.LOADOUT_SLOT_SECONDARY1:
			case loadout_slot_t.LOADOUT_SLOT_SECONDARY2:
			case loadout_slot_t.LOADOUT_SLOT_SECONDARY3:
			case loadout_slot_t.LOADOUT_SLOT_SECONDARY4:
			case loadout_slot_t.LOADOUT_SLOT_SECONDARY5:
			case loadout_slot_t.LOADOUT_SLOT_SMG0:
			case loadout_slot_t.LOADOUT_SLOT_SMG1:
			case loadout_slot_t.LOADOUT_SLOT_SMG2:
			case loadout_slot_t.LOADOUT_SLOT_SMG3:
			case loadout_slot_t.LOADOUT_SLOT_SMG4:
			case loadout_slot_t.LOADOUT_SLOT_SMG5:
			case loadout_slot_t.LOADOUT_SLOT_RIFLE0:
			case loadout_slot_t.LOADOUT_SLOT_RIFLE1:
			case loadout_slot_t.LOADOUT_SLOT_RIFLE2:
			case loadout_slot_t.LOADOUT_SLOT_RIFLE3:
			case loadout_slot_t.LOADOUT_SLOT_RIFLE4:
			case loadout_slot_t.LOADOUT_SLOT_RIFLE5:
			case loadout_slot_t.LOADOUT_SLOT_HEAVY0:
			case loadout_slot_t.LOADOUT_SLOT_HEAVY1:
			case loadout_slot_t.LOADOUT_SLOT_HEAVY2:
			case loadout_slot_t.LOADOUT_SLOT_HEAVY3:
			case loadout_slot_t.LOADOUT_SLOT_HEAVY4:
			case loadout_slot_t.LOADOUT_SLOT_HEAVY5:
			case loadout_slot_t.LOADOUT_SLOT_FIRST_WHEEL_GRENADE:
			case loadout_slot_t.LOADOUT_SLOT_GRENADE1:
			case loadout_slot_t.LOADOUT_SLOT_GRENADE2:
			case loadout_slot_t.LOADOUT_SLOT_GRENADE3:
			case loadout_slot_t.LOADOUT_SLOT_GRENADE4:
			case loadout_slot_t.LOADOUT_SLOT_GRENADE5:
			case loadout_slot_t.LOADOUT_SLOT_EQUIPMENT0:
			case loadout_slot_t.LOADOUT_SLOT_EQUIPMENT1:
			case loadout_slot_t.LOADOUT_SLOT_EQUIPMENT2:
			case loadout_slot_t.LOADOUT_SLOT_EQUIPMENT3:
			case loadout_slot_t.LOADOUT_SLOT_EQUIPMENT4:
			case loadout_slot_t.LOADOUT_SLOT_EQUIPMENT5:
				return GetWeapon(team, def, fallback);
			case loadout_slot_t.LOADOUT_SLOT_MELEE:
				return GetKnife(team, fallback);
			}
		}
		switch (slot)
		{
		case loadout_slot_t.LOADOUT_SLOT_CLOTHING_CUSTOMPLAYER:
		{
			if (minModels > 0)
			{
				if (team != 2)
				{
					return new InventoryItem
					{
						Def = (ushort)5037
					};
				}
				return new InventoryItem
				{
					Def = (ushort)5036
				};
			}
			if (_data.Agents.TryGetValue(team, out InventoryItem value))
			{
				return value;
			}
			return null;
		}
		case loadout_slot_t.LOADOUT_SLOT_CLOTHING_HANDS:
			return GetGloves(team, fallback);
		case loadout_slot_t.LOADOUT_SLOT_FLAIR0:
			return _data.Collectible;
		case loadout_slot_t.LOADOUT_SLOT_MUSICKIT:
			return _data.MusicKit;
		default:
			return null;
		}
	}

	public void ClearGraffiti()
	{
		_data.Graffiti = null;
	}
}
