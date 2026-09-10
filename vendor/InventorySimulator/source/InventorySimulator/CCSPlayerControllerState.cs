// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Timers;

namespace InventorySimulator;

public class CCSPlayerControllerState(ulong steamId)
{
	public ulong SteamID = steamId;

	public bool IsFetching;

	public bool IsAuthenticating;

	public bool IsLoadedFromFile;

	public long WsUpdatedAt;

	public long SprayUsedAt;

	public PlayerInventory? Inventory = Inventories.Get(steamId);

	public Timer? UseCmdTimer;

	public bool IsUseCmdBlocked;

	public Action? PostFetchCallback;

	private static readonly ConcurrentDictionary<(ulong SteamID, int Team, int Slot), nint> _econItemViewManager = new ConcurrentDictionary<(ulong, int, int), nint>();

	public void TriggerPostFetch()
	{
		if (PostFetchCallback != null)
		{
			PostFetchCallback();
			PostFetchCallback = null;
		}
	}

	public void DisposeUseCmdTimer()
	{
		UseCmdTimer?.Kill();
		UseCmdTimer = null;
	}

	public nint GetEconItemView(int team, int slot, InventoryItem item, nint copyFrom = 0)
	{
		(ulong, int, int) key = (SteamID, team, slot);
		if (_econItemViewManager.TryGetValue(key, out var value))
		{
			new CEconItemView(value).ApplyAttributes(item, (loadout_slot_t)slot, SteamID);
			return value;
		}
		CEconItemView cEconItemView = SchemaHelper.CreateCEconItemView(copyFrom);
		cEconItemView.ApplyAttributes(item, (loadout_slot_t)slot, SteamID);
		_econItemViewManager[key] = cEconItemView.Handle;
		return cEconItemView.Handle;
	}

	public void ClearEconItemView()
	{
		foreach (var key in _econItemViewManager.Keys)
		{
			if (key.SteamID == SteamID && _econItemViewManager.TryRemove(key, out var value))
			{
				Marshal.FreeHGlobal(value);
			}
		}
	}

	public static void ClearAllEconItemView()
	{
		foreach (nint value in _econItemViewManager.Values)
		{
			Marshal.FreeHGlobal(value);
		}
	}
}
