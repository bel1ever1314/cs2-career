// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.Linq;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Core.Attributes.Registration;
using CounterStrikeSharp.API.Modules.Commands;
using CounterStrikeSharp.API.Modules.Memory;
using CounterStrikeSharp.API.Modules.Memory.DynamicFunctions;

namespace InventorySimulator;

public class InventorySimulator : BasePlugin
{
	private string _lastUrl = "";

	public override string ModuleAuthor => "Ian Lucas";

	public override string ModuleDescription => "Inventory Simulator (inventory.cstrike.app)";

	public override string ModuleName => "InventorySimulator";

	public override string ModuleVersion => "1.0.0";

	[ConsoleCommand("css_ws", "Refreshes player inventory from the Inventory Simulator service and displays the configured URL.")]
	public void OnWSCommand(CCSPlayerController? player, CommandInfo _)
	{
		string chatPrefix = Rules.GetChatPrefix();
		string text = UrlHelper.FormatUrl(ConVars.WsUrlPrintFormat.Value, ConVars.Url.Value);
		player?.PrintToChat(base.Localizer["invsim.announce", new object[2] { chatPrefix, text }]);
		if (ConVars.IsWsEnabled.Value && !(player == null))
		{
			CCSPlayerControllerState state = player.GetState();
			int value = ConVars.WsCooldown.Value;
			long num = DateTimeOffset.UtcNow.ToUnixTimeSeconds() - state.WsUpdatedAt;
			if (num < value)
			{
				player.PrintToChat(base.Localizer["invsim.ws_cooldown", new object[2]
				{
					chatPrefix,
					value - num
				}]);
			}
			else if (state.IsFetching)
			{
				player.PrintToChat(base.Localizer["invsim.ws_in_progress", new object[1] { chatPrefix }]);
			}
			else
			{
				player.RefreshInventory(force: true);
				player.PrintToChat(base.Localizer["invsim.ws_new", new object[1] { chatPrefix }]);
			}
		}
	}

	[ConsoleCommand("css_spray", "Applies the player's equipped graffiti spray at their current location.")]
	public void OnSprayCommand(CCSPlayerController? player, CommandInfo _)
	{
		if (player != null && ConVars.IsSprayEnabled.Value)
		{
			CCSPlayerControllerState state = player.GetState();
			int value = ConVars.SprayCooldown.Value;
			long num = DateTimeOffset.UtcNow.ToUnixTimeSeconds() - state.SprayUsedAt;
			if (num < value)
			{
				player.PrintToChat(base.Localizer["invsim.spray_cooldown", new object[2]
				{
					Rules.GetChatPrefix(),
					value - num
				}]);
			}
			else
			{
				player.SprayGraffiti();
			}
		}
	}

	[ConsoleCommand("css_wslogin", "Authenticates the player with Inventory Simulator and displays their login URL.")]
	public void OnWsloginCommand(CCSPlayerController? player, CommandInfo _)
	{
		if (ConVars.IsWsLogin.Value && Api.HasApiKey() && player != null)
		{
			CCSPlayerControllerState state = player.GetState();
			player.PrintToChat(base.Localizer["invsim.login_in_progress", new object[1] { Rules.GetChatPrefix() }]);
			if (!state.IsAuthenticating)
			{
				player.SignIn();
			}
		}
	}

	public void OnEntityCreated(CEntityInstance entity)
	{
		if (!(entity.DesignerName == "player_spray_decal") || !ConVars.IsSprayChangerEnabled.Value)
		{
			return;
		}
		Server.NextWorldUpdate(delegate
		{
			CPlayerSprayDecal cPlayerSprayDecal = entity.As<CPlayerSprayDecal>();
			if (cPlayerSprayDecal.IsValid && cPlayerSprayDecal.AccountID != 0)
			{
				CCSPlayerController playerFromAccountId = PlayerHelper.GetPlayerFromAccountId(cPlayerSprayDecal.AccountID);
				if (!(playerFromAccountId == null) && !playerFromAccountId.IsBot)
				{
					playerFromAccountId.HandleSprayDecalCreated(cPlayerSprayDecal);
				}
			}
		});
	}

	public void OnEntityDeleted(CEntityInstance entity)
	{
		if (entity.DesignerName == "cs_player_controller")
		{
			CCSPlayerController cCSPlayerController = entity.As<CCSPlayerController>();
			if (cCSPlayerController.SteamID != 0L)
			{
				cCSPlayerController.RemoveState();
			}
		}
	}

	public override void Load(bool hotReload)
	{
		Runtime.Initialize(this);
		ConVars.Initialize(this);
		RegisterListener<Listeners.OnEntityCreated>(OnEntityCreated);
		RegisterListener<Listeners.OnEntityDeleted>(OnEntityDeleted);
		RegisterEventHandler<EventPlayerConnect>(OnPlayerConnect);
		RegisterEventHandler<EventPlayerConnectFull>(OnPlayerConnectFull);
		RegisterEventHandler<EventPlayerDeath>(OnPlayerDeathPre);
		RegisterEventHandler<EventRoundMvp>(OnRoundMvpPre);
		RegisterEventHandler<EventPlayerDisconnect>(OnPlayerDisconnect);
		Natives.CCSPlayerController_ProcessUsercmds.Hook(OnProcessUsercmds, HookMode.Post);
		VirtualFunctions.GiveNamedItemFunc.Hook(OnGiveNamedItemPre, HookMode.Pre);
		Natives.CCSPlayerInventory_GetItemInLoadout.Hook(GetItemInLoadout, HookMode.Post);
		ConVars.File.ValueChanged += OnFileChanged;
		ConVars.IsRequireInventory.ValueChanged += OnIsRequireInventoryChanged;
		ConVars.Url.ValueChanged += OnUrlChanged;
		ConVars.ApiKey.ValueChanged += OnApiSuspensionConVarChanged;
		ConVars.IsPublicApiStatTrakIncrement.ValueChanged += OnApiSuspensionConVarChanged;
		ConVars.IsPublicApiSprayConsume.ValueChanged += OnApiSuspensionConVarChanged;
		_lastUrl = ConVars.Url.Value;
		OnFileChanged(null, ConVars.File.Value);
		OnIsRequireInventoryChanged(null, ConVars.IsRequireInventory.Value);
	}

	public void OnUrlChanged(object? _, string value)
	{
		Api.ResetSuspension();
		if (!(value == _lastUrl))
		{
			_lastUrl = value;
			if (!Uri.TryCreate(value, UriKind.Absolute, out Uri result) || !result.Host.Equals("inventory.cstrike.app", StringComparison.OrdinalIgnoreCase))
			{
				ConVars.IsPublicApiStatTrakIncrement.Value = false;
				ConVars.IsPublicApiSprayConsume.Value = false;
			}
		}
	}

	public void OnApiSuspensionConVarChanged<T>(object? _, T value)
	{
		Api.ResetSuspension();
	}

	public void OnFileChanged(object? _, string value)
	{
		if (!Inventories.Load(value))
		{
			return;
		}
		try
		{
			foreach (CCSPlayerController item in from p in Utilities.GetPlayers()
				where !p.IsBot
				select p)
			{
				if (Inventories.TryGet(item.SteamID, out PlayerInventory inventory))
				{
					item.GetState().Inventory = inventory;
				}
			}
		}
		catch (Exception)
		{
		}
	}

	public void OnIsRequireInventoryChanged(object? _, bool value)
	{
		if (ConVars.IsRequireInventory.Value)
		{
			Natives.CServerSideClientBase_ActivatePlayer.Hook(OnActivatePlayerPre, HookMode.Pre);
		}
		else
		{
			Natives.CServerSideClientBase_ActivatePlayer.Unhook(OnActivatePlayerPre, HookMode.Pre);
		}
	}

	public override void Unload(bool hotReload)
	{
		CCSPlayerControllerState.ClearAllEconItemView();
	}

	public HookResult OnPlayerConnect(EventPlayerConnect @event, GameEventInfo _)
	{
		CCSPlayerController userid = @event.Userid;
		if (userid != null && !userid.IsBot)
		{
			userid.HandleConnect();
		}
		return HookResult.Continue;
	}

	public HookResult OnPlayerConnectFull(EventPlayerConnectFull @event, GameEventInfo _)
	{
		CCSPlayerController userid = @event.Userid;
		if (userid != null && !userid.IsBot)
		{
			userid.HandleConnect();
		}
		return HookResult.Continue;
	}

	public HookResult OnPlayerDeathPre(EventPlayerDeath @event, GameEventInfo _)
	{
		CCSPlayerController attacker = @event.Attacker;
		CCSPlayerController userid = @event.Userid;
		if (attacker != null && userid != null)
		{
			bool num = !attacker.IsBot && attacker.IsValid;
			bool flag = (!ConVars.IsStatTrakIgnoreBots.Value || !userid.IsBot) && userid.IsValid;
			if (num & flag)
			{
				attacker.IncrementWeaponStatTrak(@event.Weapon, @event.WeaponItemid);
			}
		}
		return HookResult.Continue;
	}

	public HookResult OnRoundMvpPre(EventRoundMvp @event, GameEventInfo _)
	{
		CCSPlayerController userid = @event.Userid;
		if (userid != null && !userid.IsBot && userid.IsValid)
		{
			userid.IncrementMusicKitStatTrak(@event);
		}
		return HookResult.Continue;
	}

	public HookResult OnPlayerDisconnect(EventPlayerDisconnect @event, GameEventInfo _)
	{
		CCSPlayerController userid = @event.Userid;
		if (userid != null && !userid.IsBot)
		{
			userid.HandleDisconnect();
		}
		return HookResult.Continue;
	}

	public HookResult OnActivatePlayerPre(DynamicHook hook)
	{
		nint thisPtr = hook.GetParam<nint>(0);
		ushort userID = new CServerSideClientBase(thisPtr).UserID;
		CCSPlayerController player = Utilities.GetPlayerFromUserid(userID);
		if (player != null && Rules.IsOwned(player.SteamID))
		{
			player.Revalidate();
			CCSPlayerControllerState state = player.GetState();
			if (state.Inventory == null)
			{
				state.PostFetchCallback = delegate
				{
					Server.NextWorldUpdate(delegate
					{
						if (player.IsValid)
						{
							Natives.CServerSideClientBase_ActivatePlayer.Invoke(thisPtr);
						}
					});
				};
				if (!state.IsFetching)
				{
					player.RefreshInventory();
				}
				return HookResult.Stop;
			}
		}
		return HookResult.Continue;
	}

	public HookResult OnProcessUsercmds(DynamicHook hook)
	{
		if (!ConVars.IsSprayOnUse.Value)
		{
			return HookResult.Continue;
		}
		hook.GetParam<CCSPlayerController>(0).HandleProcessUsercmds();
		return HookResult.Continue;
	}

	public HookResult OnGiveNamedItemPre(DynamicHook hook)
	{
		CCSPlayer_ItemServices param = hook.GetParam<CCSPlayer_ItemServices>(0);
		string param2 = hook.GetParam<string>(1);
		CCSPlayerController controller = param.GetController();
		if (((object)controller == null || controller.SteamID != 0) && controller?.InventoryServices != null && Rules.IsOwned(controller.SteamID))
		{
			CEconItemDefinition cEconItemDefinition = SchemaHelper.GetItemSchema()?.GetItemDefinitionByName(param2);
			if (cEconItemDefinition != null)
			{
				CCSPlayerControllerState state = controller.GetState();
				InventoryItem inventoryItem = state.Inventory?.GetItemForSlot(controller.TeamNum, cEconItemDefinition.DefaultLoadoutSlot, cEconItemDefinition.DefIndex, ConVars.IsFallbackTeam.Value);
				if (inventoryItem != null)
				{
					hook.SetParam(3, state.GetEconItemView(controller.TeamNum, (int)cEconItemDefinition.DefaultLoadoutSlot, inventoryItem));
				}
			}
		}
		return HookResult.Continue;
	}

	public HookResult GetItemInLoadout(DynamicHook hook)
	{
		CCSPlayerInventory cCSPlayerInventory = new CCSPlayerInventory(hook.GetParam<nint>(0));
		if (!cCSPlayerInventory.IsValid)
		{
			return HookResult.Continue;
		}
		nint num = hook.GetReturn<nint>();
		if (num == IntPtr.Zero)
		{
			return HookResult.Continue;
		}
		CEconItemView cEconItemView = new CEconItemView(num);
		CCSPlayerController playerFromSteamId = PlayerHelper.GetPlayerFromSteamId(cCSPlayerInventory.SOCache.Owner.SteamID);
		if (playerFromSteamId == null || !Rules.IsOwned(playerFromSteamId.SteamID))
		{
			return HookResult.Continue;
		}
		int param = hook.GetParam<int>(1);
		int param2 = hook.GetParam<int>(2);
		CCSPlayerControllerState state = playerFromSteamId.GetState();
		InventoryItem inventoryItem = state.Inventory?.GetItemForSlot((byte)param, (loadout_slot_t)param2, cEconItemView.ItemDefinitionIndex, ConVars.IsFallbackTeam.Value, ConVars.MinModels.Value);
		if (inventoryItem != null)
		{
			hook.SetReturn(state.GetEconItemView(param, param2, inventoryItem, cEconItemView.Handle));
			return HookResult.Changed;
		}
		return HookResult.Continue;
	}
}
