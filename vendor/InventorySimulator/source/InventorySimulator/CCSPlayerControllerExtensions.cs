// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace InventorySimulator;

public static class CCSPlayerControllerExtensions
{
	private static readonly ConcurrentDictionary<uint, CCSPlayerControllerState> _controllerStateManager = new ConcurrentDictionary<uint, CCSPlayerControllerState>();

	public static CCSPlayerControllerState GetState(this CCSPlayerController self)
	{
		return _controllerStateManager.GetOrAdd(self.Index, (uint _) => new CCSPlayerControllerState(self.SteamID));
	}

	public static void Revalidate(this CCSPlayerController self)
	{
		if (self.GetState().SteamID != self.SteamID)
		{
			self.RemoveState();
		}
	}

	public static void RemoveState(this CCSPlayerController self)
	{
		CCSPlayerControllerState state = self.GetState();
		state.DisposeUseCmdTimer();
		state.ClearEconItemView();
		_controllerStateManager.TryRemove(self.Index, out CCSPlayerControllerState _);
	}

	public static void HandleConnect(this CCSPlayerController self)
	{
		self.Revalidate();
		if (Rules.IsOwned(self.SteamID))
		{
			self.RefreshInventory();
		}
	}

	public static async void RefreshInventory(this CCSPlayerController self, bool force = false)
	{
		if (!force)
		{
			await self.FetchInventory();
			Server.NextWorldUpdate(delegate
			{
				if (self.IsValid)
				{
					self.HandleInventoryLoad();
				}
			});
			return;
		}
		PlayerInventory oldInventory = self.GetState().Inventory;
		await self.FetchInventory(force: true);
		Server.NextWorldUpdate(delegate
		{
			if (self.IsValid)
			{
				self.PrintToChat(Runtime.Plugin.Localizer["invsim.ws_completed", new object[1] { Rules.GetChatPrefix() }]);
				self.HandleInventoryLoad();
				self.HandlePostRefreshInventory(oldInventory);
			}
		});
	}

	public static async Task FetchInventory(this CCSPlayerController self, bool force = false)
	{
		if (!Rules.IsOwned(self.SteamID))
		{
			return;
		}
		CCSPlayerControllerState controllerState = self.GetState();
		PlayerInventory existing = controllerState.Inventory;
		if (!force && controllerState.Inventory != null)
		{
			return;
		}
		if (!force && Inventories.TryGet(self.SteamID, out PlayerInventory inventory))
		{
			controllerState.Inventory = inventory;
		}
		else
		{
			if (controllerState.IsFetching)
			{
				return;
			}
			controllerState.IsFetching = true;
			EquippedV5Response equippedV5Response = await Api.FetchEquippedAsync(self.SteamID);
			PlayerInventory inventory2;
			if (equippedV5Response != null)
			{
				PlayerInventory playerInventory = new PlayerInventory(equippedV5Response);
				if (existing != null)
				{
					playerInventory.WeaponWearCache = existing.WeaponWearCache;
				}
				playerInventory.InitializeWearOverrides();
				controllerState.WsUpdatedAt = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
				controllerState.Inventory = playerInventory;
			}
			else if (Inventories.TryGet(self.SteamID, out inventory2))
			{
				controllerState.Inventory = inventory2;
			}
			controllerState.IsFetching = false;
			controllerState.TriggerPostFetch();
		}
	}

	public static void HandleInventoryLoad(this CCSPlayerController self)
	{
		CCSPlayerInventory cCSPlayerInventory = self.InventoryServices?.GetInventory();
		if (cCSPlayerInventory != null && cCSPlayerInventory.IsValid)
		{
			cCSPlayerInventory.SendInventoryUpdateEvent();
		}
	}

	public static void HandlePostRefreshInventory(this CCSPlayerController self, PlayerInventory? oldInventory)
	{
		PlayerInventory inventory = self.GetState().Inventory;
		if (inventory != null && ConVars.IsWsImmediately.Value)
		{
			self.RegiveAgent(inventory, oldInventory);
			self.RegiveGloves(inventory, oldInventory);
			self.RegiveWeapons(inventory, oldInventory);
		}
	}

	public static bool IsUseCmdBusy(this CCSPlayerController self)
	{
		CCSPlayerPawn? value = self.PlayerPawn.Value;
		if ((object)value != null && value.IsBuyMenuOpen)
		{
			return true;
		}
		CCSPlayerPawn? value2 = self.PlayerPawn.Value;
		if ((object)value2 != null && value2.IsDefusing)
		{
			return true;
		}
		CBasePlayerWeapon cBasePlayerWeapon = self.PlayerPawn.Value?.WeaponServices?.ActiveWeapon.Value;
		if (cBasePlayerWeapon?.DesignerName != "weapon_c4")
		{
			return false;
		}
		return cBasePlayerWeapon.As<CC4>().IsPlantingViaUse;
	}

	public static void HandleProcessUsercmds(this CCSPlayerController self)
	{
		if ((self.Buttons & PlayerButtons.Use) == (PlayerButtons)0uL)
		{
			return;
		}
		CCSPlayerPawn? value = self.PlayerPawn.Value;
		if ((object)value == null || !value.IsAbleToApplySpray())
		{
			return;
		}
		CCSPlayerControllerState controllerState = self.GetState();
		if (self.IsUseCmdBusy())
		{
			controllerState.IsUseCmdBlocked = true;
		}
		controllerState.DisposeUseCmdTimer();
		controllerState.UseCmdTimer = Runtime.Plugin.AddTimer(0.1f, delegate
		{
			if (controllerState.IsUseCmdBlocked)
			{
				controllerState.IsUseCmdBlocked = false;
			}
			else if (self.IsValid && !self.IsUseCmdBusy())
			{
				self.ExecuteClientCommandFromServer("css_spray");
			}
		});
	}

	public static void RegiveAgent(this CCSPlayerController self, PlayerInventory inventory, PlayerInventory? oldInventory)
	{
		if (ConVars.MinModels.Value > 0)
		{
			return;
		}
		CCSPlayerPawn value = self.PlayerPawn.Value;
		if (!(value == null))
		{
			byte teamNum = self.TeamNum;
			InventoryItem inventoryItem = (inventory.Agents.TryGetValue(teamNum, out InventoryItem value2) ? value2 : null);
			if (!(((oldInventory != null && oldInventory.Agents.TryGetValue(teamNum, out value2)) ? value2 : null) == inventoryItem))
			{
				value.SetModelFromLoadout();
				value.SetModelFromClass();
				value.AcceptInput("SetBodygroup", null, null, "default_gloves,1");
			}
		}
	}

	public static void RegiveGloves(this CCSPlayerController self, PlayerInventory inventory, PlayerInventory? oldInventory)
	{
		CCSPlayerPawn pawn = self.PlayerPawn.Value;
		CCSPlayer_ItemServices itemServices = pawn?.ItemServices?.As<CCSPlayer_ItemServices>();
		if (pawn == null || itemServices == null)
		{
			return;
		}
		bool value = ConVars.IsFallbackTeam.Value;
		byte teamNum = self.TeamNum;
		InventoryItem gloves = inventory.GetGloves(teamNum, value);
		if (oldInventory?.GetGloves(teamNum, value) == gloves)
		{
			return;
		}
		itemServices.UpdateWearables();
		pawn.AcceptInput("SetBodygroup", null, null, "first_or_third_person,0");
		Server.NextWorldUpdate(delegate
		{
			if (pawn.IsValid && itemServices.Handle != IntPtr.Zero)
			{
				pawn.AcceptInput("SetBodygroup", null, null, "first_or_third_person,1");
			}
		});
	}

	public static void RegiveWeapons(this CCSPlayerController self, PlayerInventory inventory, PlayerInventory? oldInventory)
	{
		CCSPlayerPawn? value = self.PlayerPawn.Value;
		CCSPlayer_WeaponServices cCSPlayer_WeaponServices = value?.WeaponServices?.As<CCSPlayer_WeaponServices>();
		if (value == null || cCSPlayer_WeaponServices == null)
		{
			return;
		}
		string text = cCSPlayer_WeaponServices.ActiveWeapon.Value?.DesignerName;
		List<(string, string, int, int, bool, gear_slot_t)> list = new List<(string, string, int, int, bool, gear_slot_t)>();
		foreach (CHandle<CBasePlayerWeapon> myWeapon in cCSPlayer_WeaponServices.MyWeapons)
		{
			CCSWeaponBase cCSWeaponBase = myWeapon.Value?.As<CCSWeaponBase>();
			if (cCSWeaponBase == null || !cCSWeaponBase.DesignerName.Contains("weapon_") || cCSWeaponBase.OriginalOwnerXuidLow != (uint)self.SteamID)
			{
				continue;
			}
			CCSWeaponBaseVData cCSWeaponBaseVData = cCSWeaponBase.VData?.As<CCSWeaponBaseVData>();
			bool flag = cCSWeaponBaseVData != null;
			if (flag)
			{
				gear_slot_t gearSlot = cCSWeaponBaseVData.GearSlot;
				bool flag2 = gearSlot <= gear_slot_t.GEAR_SLOT_KNIFE;
				flag = flag2;
			}
			if (flag)
			{
				ushort itemDefinitionIndex = cCSWeaponBase.AttributeManager.Item.ItemDefinitionIndex;
				bool value2 = ConVars.IsFallbackTeam.Value;
				InventoryItem? obj = ((cCSWeaponBaseVData.GearSlot != gear_slot_t.GEAR_SLOT_KNIFE) ? oldInventory?.GetWeapon(self.TeamNum, itemDefinitionIndex, value2) : oldInventory?.GetKnife(self.TeamNum, value2));
				InventoryItem inventoryItem = ((cCSWeaponBaseVData.GearSlot == gear_slot_t.GEAR_SLOT_KNIFE) ? inventory.GetKnife(self.TeamNum, value2) : inventory.GetWeapon(self.TeamNum, itemDefinitionIndex, value2));
				if (!(obj == inventoryItem))
				{
					int clip = cCSWeaponBase.Clip1;
					int item = cCSWeaponBase.ReserveAmmo[0];
					list.Add((cCSWeaponBase.DesignerName, cCSWeaponBase.GetDesignerName(), clip, item, text == cCSWeaponBase.DesignerName, cCSWeaponBaseVData.GearSlot));
				}
			}
		}
		foreach (var item3 in list)
		{
			string designerName = item3.Item1;
			string item2 = item3.Item2;
			int clip2 = item3.Item3;
			int reserve = item3.Item4;
			bool active = item3.Item5;
			gear_slot_t gearSlot2 = item3.Item6;
			CBasePlayerWeapon cBasePlayerWeapon = cCSPlayer_WeaponServices.MyWeapons.FirstOrDefault((CHandle<CBasePlayerWeapon> h) => h.Value?.DesignerName == designerName)?.Value;
			if (cBasePlayerWeapon != null)
			{
				cCSPlayer_WeaponServices.DropWeapon(cBasePlayerWeapon);
				cBasePlayerWeapon.Remove();
			}
			CBasePlayerWeapon weapon = self.GiveNamedItem<CBasePlayerWeapon>(item2);
			if (!(weapon != null))
			{
				continue;
			}
			Server.RunOnTick(Server.TickCount + 32, delegate
			{
				if (weapon.IsValid)
				{
					weapon.Clip1 = clip2;
					Utilities.SetStateChanged(weapon, "CBasePlayerWeapon", "m_iClip1");
					weapon.ReserveAmmo[0] = reserve;
					Utilities.SetStateChanged(weapon, "CBasePlayerWeapon", "m_pReserveAmmo");
					Server.NextWorldUpdate(delegate
					{
						if (active && self.IsValid)
						{
							string text2 = gearSlot2 switch
							{
								gear_slot_t.GEAR_SLOT_RIFLE => "slot1", 
								gear_slot_t.GEAR_SLOT_PISTOL => "slot2", 
								gear_slot_t.GEAR_SLOT_KNIFE => "slot3", 
								_ => null, 
							};
							if (text2 != null)
							{
								self.ExecuteClientCommand(text2);
							}
						}
					});
				}
			});
		}
	}

	public static async void SignIn(this CCSPlayerController self)
	{
		CCSPlayerControllerState controllerState = self.GetState();
		if (controllerState.IsFetching)
		{
			return;
		}
		controllerState.IsFetching = true;
		SignInUserResponse response = await Api.SendSignIn(self.SteamID.ToString());
		controllerState.IsFetching = false;
		Server.NextWorldUpdate(delegate
		{
			string chatPrefix = Rules.GetChatPrefix();
			if (response == null)
			{
				self?.PrintToChat(Runtime.Plugin.Localizer["invsim.login_failed", new object[1] { chatPrefix }]);
			}
			else
			{
				self?.PrintToChat(Runtime.Plugin.Localizer["invsim.login", new object[2]
				{
					chatPrefix,
					Api.GetUrl("/api/sign-in/callback") + "?token=" + response.Token
				}]);
			}
		});
	}

	public unsafe static void SprayGraffiti(this CCSPlayerController self)
	{
		if (!self.IsValid)
		{
			return;
		}
		InventoryItem inventoryItem = self.GetState().Inventory?.Graffiti;
		if (inventoryItem == null || !inventoryItem.Def.HasValue || !inventoryItem.Tint.HasValue)
		{
			return;
		}
		CCSPlayerPawn value = self.PlayerPawn.Value;
		if (value == null || value.LifeState != 0)
		{
			return;
		}
		CCSPlayer_MovementServices cCSPlayer_MovementServices = value.MovementServices?.As<CCSPlayer_MovementServices>();
		if (cCSPlayer_MovementServices == null)
		{
			return;
		}
		CGameTrace* ptr = stackalloc CGameTrace[1];
		if (value.IsAbleToApplySpray((nint)ptr) && ptr != (CGameTrace*)IntPtr.Zero)
		{
			self.EmitSound("SprayCan.Shake");
			self.GetState().SprayUsedAt = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
			Vector vector = SchemaHelper.ToVector(ptr->EndPos);
			Vector vector2 = SchemaHelper.ToVector(ptr->HitNormal);
			CPlayerSprayDecal cPlayerSprayDecal = Utilities.CreateEntityByName<CPlayerSprayDecal>("player_spray_decal");
			if (cPlayerSprayDecal != null)
			{
				cPlayerSprayDecal.EndPos.Add(vector);
				cPlayerSprayDecal.Start.Add(vector);
				cPlayerSprayDecal.Left.Add(cCSPlayer_MovementServices.Left);
				cPlayerSprayDecal.Normal.Add(vector2);
				cPlayerSprayDecal.AccountID = (uint)self.SteamID;
				cPlayerSprayDecal.Player = inventoryItem.Def.Value;
				cPlayerSprayDecal.TintID = inventoryItem.Tint.Value;
				cPlayerSprayDecal.DispatchSpawn();
				self.EmitSound("SprayCan.Paint");
				self.ConsumeGraffitiCharge(inventoryItem);
			}
		}
	}

	public static void ConsumeGraffitiCharge(this CCSPlayerController self, InventoryItem item)
	{
		if (item.Charges.HasValue)
		{
			item.Charges--;
			if (item.Uid.HasValue)
			{
				Api.SendConsumeItemSpray(self.SteamID, item.Uid.Value);
			}
			string chatPrefix = Rules.GetChatPrefix();
			if (item.Charges <= 0)
			{
				self.GetState().Inventory?.ClearGraffiti();
				self.PrintToChat(Runtime.Plugin.Localizer["invsim.spray_charges_empty", new object[1] { chatPrefix }]);
			}
			else
			{
				self.PrintToChat(Runtime.Plugin.Localizer["invsim.spray_charges", new object[2]
				{
					chatPrefix,
					item.Charges.Value
				}]);
			}
		}
	}

	public static void HandleSprayDecalCreated(this CCSPlayerController self, CPlayerSprayDecal sprayDecal)
	{
		InventoryItem inventoryItem = self.GetState().Inventory?.Graffiti;
		if (inventoryItem != null && inventoryItem.Def.HasValue && inventoryItem.Tint.HasValue)
		{
			sprayDecal.Player = inventoryItem.Def.Value;
			Utilities.SetStateChanged(sprayDecal, "CPlayerSprayDecal", "m_nPlayer");
			sprayDecal.TintID = inventoryItem.Tint.Value;
			Utilities.SetStateChanged(sprayDecal, "CPlayerSprayDecal", "m_nTintID");
		}
	}

	public static void IncrementWeaponStatTrak(this CCSPlayerController self, string designerName, string weaponItemId)
	{
		CBasePlayerWeapon cBasePlayerWeapon = self.PlayerPawn.Value?.WeaponServices?.ActiveWeapon.Value;
		if (!(cBasePlayerWeapon == null) && cBasePlayerWeapon.HasCustomItemID() && ulong.TryParse(weaponItemId, out var result) && cBasePlayerWeapon.AttributeManager.Item.AccountID == new CSteamID(self.SteamID).GetAccountID().m_AccountID && cBasePlayerWeapon.AttributeManager.Item.ItemID == result)
		{
			PlayerInventory inventory = self.GetState().Inventory;
			bool value = ConVars.IsFallbackTeam.Value;
			InventoryItem inventoryItem = ((!ItemHelper.IsMeleeDesignerName(designerName)) ? inventory?.GetWeapon(self.TeamNum, cBasePlayerWeapon.AttributeManager.Item.ItemDefinitionIndex, value) : inventory?.GetKnife(self.TeamNum, value));
			if (!(inventoryItem == null) && inventoryItem.Stattrak.HasValue && !(inventoryItem.Stattrak < 0) && inventoryItem.Uid.HasValue)
			{
				inventoryItem.Stattrak++;
				float value2 = TypeHelper.ViewAs<int, float>(inventoryItem.Stattrak.Value);
				cBasePlayerWeapon.AttributeManager.Item.NetworkedDynamicAttributes.SetOrAddAttributeValueByName("kill eater", value2);
				Utilities.SetStateChanged(cBasePlayerWeapon, "CBasePlayerWeapon", "m_AttributeManager");
				Api.SendStatTrakIncrement(self.SteamID, inventoryItem.Uid.Value);
			}
		}
	}

	public static void IncrementMusicKitStatTrak(this CCSPlayerController self, EventRoundMvp @event)
	{
		InventoryItem inventoryItem = self.GetState().Inventory?.MusicKit;
		if (inventoryItem != null && inventoryItem.Uid.HasValue && inventoryItem.Stattrak.HasValue && inventoryItem.Stattrak >= 0)
		{
			inventoryItem.Stattrak++;
			@event.Musickitmvps = inventoryItem.Stattrak.Value;
			Api.SendStatTrakIncrement(self.SteamID, inventoryItem.Uid.Value);
		}
	}

	public static void HandleDisconnect(this CCSPlayerController self)
	{
		if (!ConVars.IsPersistInventory.Value && !Inventories.Has(self.SteamID))
		{
			self.GetState().Inventory = null;
		}
	}
}
