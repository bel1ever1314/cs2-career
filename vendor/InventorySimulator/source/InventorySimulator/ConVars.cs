// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Cvars;

namespace InventorySimulator;

public static class ConVars
{
	public static readonly FakeConVar<string> Url = new FakeConVar<string>("invsim_url", "API URL for the Inventory Simulator service.", "http://127.0.0.1:18768", ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<string> ApiKey = new FakeConVar<string>("invsim_apikey", "API key for the Inventory Simulator service.", "", ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<string> File = new FakeConVar<string>("invsim_file", "Inventory data file to load when the plugin starts.", "inventories.json", ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsWsEnabled = new FakeConVar<bool>("invsim_ws_enabled", "Allow players to refresh their inventory using the !ws command.", true, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsWsImmediately = new FakeConVar<bool>("invsim_ws_immediately", "Apply skin changes immediately without requiring a respawn.", true, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<int> WsCooldown = new FakeConVar<int>("invsim_ws_cooldown", "Cooldown duration in seconds between inventory refreshes per player.", 30, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<string> ChatPrefix = new FakeConVar<string>("invsim_chat_prefix", "Prefix displayed before chat messages.", "", ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<string> WsUrlPrintFormat = new FakeConVar<string>("invsim_ws_url_print_format", "URL format string displayed when using the !ws command.", "{Host}", ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsWsLogin = new FakeConVar<bool>("invsim_wslogin", "Allow players to authenticate with Inventory Simulator and display their login URL (not recommended).", false, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsPersistInventory = new FakeConVar<bool>("invsim_persist_inventory", "Keep a player's cached inventory after they disconnect.", false, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsRequireInventory = new FakeConVar<bool>("invsim_require_inventory", "Require the player's inventory to be fetched before allowing them to join the game.", false, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsSprayEnabled = new FakeConVar<bool>("invsim_spray_enabled", "Enable spraying via the !spray command and/or use key.", true, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsSprayOnUse = new FakeConVar<bool>("invsim_spray_on_use", "Apply spray when the player presses the use key.", false, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<int> SprayCooldown = new FakeConVar<int>("invsim_spray_cooldown", "Cooldown duration in seconds between sprays per player.", 30, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsSprayChangerEnabled = new FakeConVar<bool>("invsim_spraychanger_enabled", "Replace the player's vanilla spray with their equipped graffiti.", false, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsPublicApiStatTrakIncrement = new FakeConVar<bool>("invsim_public_api_stattrak_increment", "Send keyless StatTrak increment requests to the public API when invsim_apikey is not set.", true, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsPublicApiSprayConsume = new FakeConVar<bool>("invsim_public_api_spray_consume", "Send keyless graffiti consume requests to the public API when invsim_apikey is not set.", true, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsStatTrakIgnoreBots = new FakeConVar<bool>("invsim_stattrak_ignore_bots", "Ignore StatTrak kill count increments for bot kills.", true, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<bool> IsFallbackTeam = new FakeConVar<bool>("invsim_fallback_team", "Allow using skins from any team (prioritizes current team first).", true, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<int> MinModels = new FakeConVar<int>("invsim_minmodels", "Enable player agents (0 = enabled, 1 = use map models per team, 2 = SAS & Phoenix).", 0, ConVarFlags.FCVAR_NONE);

	public static readonly FakeConVar<string> OnlySteamId = new FakeConVar<string>("invsim_only_steamid", "If set, apply simulated inventory only to this SteamID. Everyone else is left alone.", "", ConVarFlags.FCVAR_NONE);

	public static void Initialize(BasePlugin plugin)
	{
		plugin.RegisterFakeConVars(typeof(ConVars));
	}
}
