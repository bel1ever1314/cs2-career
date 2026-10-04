namespace Microsoft.Extensions.Logging
{
    public sealed class TestLogger
    {
        public void LogInformation(string message, params object[] values) =>
            CounterStrikeSharp.API.Server.Console.Add(message + string.Join(" ", values));
    }
}

namespace CounterStrikeSharp.API.Core
{
    public enum HookResult { Continue }
    public sealed class GameEventInfo { }
    public sealed class EventItemPurchase
    {
        public CCSPlayerController? Userid { get; set; }
        public string Weapon { get; set; } = "";
    }
    public sealed class CHandle<T>(T? value) where T : class
    {
        public T? Value { get; set; } = value;
    }

    public sealed class EntityHandle(uint raw)
    {
        public uint Raw { get; } = raw;
    }

    public sealed class EntityData(uint raw, string name)
    {
        public EntityHandle EntityHandle { get; } = new(raw);
        public string DesignerName { get; } = name;
        public bool IsValid { get; set; } = true;
        public bool Killed { get; set; }
    }

    public class CEntityInstance
    {
        private readonly EntityData _entity;
        public CEntityInstance(IntPtr handle) => _entity = FakeWorld.Entities[handle];
        protected CEntityInstance(EntityData entity) => _entity = entity;
        public bool IsValid => _entity.IsValid;
        public EntityHandle EntityHandle => _entity.EntityHandle;
        public string DesignerName => _entity.DesignerName;
        public void AcceptInput(string input)
        {
            if (input != "Kill") throw new InvalidOperationException("Unexpected input: " + input);
            _entity.Killed = true;
            _entity.IsValid = false;
        }
    }

    public sealed class CBasePlayerWeapon(EntityData entity) : CEntityInstance(entity)
    {
        public AttributeManager AttributeManager { get; } = new();
    }
    public sealed class AttributeManager { public Item Item { get; } = new(); }
    public sealed class Item { public ushort ItemDefinitionIndex { get; set; } }

    public sealed class CCSPlayer_WeaponServices
    {
        public List<CHandle<CBasePlayerWeapon>> MyWeapons { get; } = [];
    }

    public sealed class ItemServices
    {
        public nint Handle { get; set; } = 1;
    }

    public sealed class CCSPlayer_ItemServices(nint handle)
    {
        public bool HasHelmet => FakeWorld.Helmets.GetValueOrDefault(handle);
    }

    public sealed class CCSPlayerPawn
    {
        public bool IsValid { get; set; } = true;
        public EntityHandle EntityHandle { get; set; } = new(100);
        public bool InBuyZone { get; set; } = true;
        public int ArmorValue { get; set; }
        public int Health { get; set; } = 100;
        public object? Bot { get; set; } = new();
        public ItemServices? ItemServices { get; set; } = new();
        public CCSPlayer_WeaponServices? WeaponServices { get; set; } = new();
    }

    public sealed class InGameMoneyServices
    {
        public int Account { get; set; }
    }

    public enum SpawnMode { Attached, Zero, Invalid, Unattached }

    public sealed class CCSPlayerController
    {
        public bool IsValid { get; set; } = true;
        public bool IsBot { get; set; } = true;
        public string PlayerName { get; set; } = "test bot";
        public bool ControllingBot { get; set; }
        public bool HasBeenControlledByPlayerThisRound { get; set; }
        public IntPtr Handle { get; set; } = new(10);
        public int Slot { get; set; } = 1;
        public ulong SteamID { get; set; } = 2;
        public int TeamNum { get; set; } = 3;
        public CounterStrikeSharp.API.Modules.Utils.CsTeam Team =>
            (CounterStrikeSharp.API.Modules.Utils.CsTeam)TeamNum;
        public CHandle<CCSPlayerPawn> PlayerPawn { get; } = new(new());
        public CHandle<CCSPlayerController> OriginalControllerOfCurrentPawn { get; } = new(null);
        public InGameMoneyServices? InGameMoneyServices { get; set; } = new() { Account = 4350 };
        public List<string> GiveCalls { get; } = [];
        public List<string> RemovalCalls { get; } = [];
        public bool RemoveSucceeds { get; set; } = true;
        public bool DeferredRemoval { get; set; }
        public List<string> Chat { get; } = [];
        public void PrintToChat(string text) => Chat.Add(text);
        public Func<CCSPlayerController, string, SpawnMode>? GiveBehavior { get; set; }
        public bool SharedVariantClass { get; set; }

        public bool RemoveItemByDesignerName(string name)
        {
            RemovalCalls.Add(name);
            if (!RemoveSucceeds) return false;
            var item = PlayerPawn.Value!.WeaponServices!.MyWeapons.FirstOrDefault(h => h.Value is { IsValid: true } w && w.DesignerName == name);
            if (item is null) return false;
            if (!DeferredRemoval) item.Value!.AcceptInput("Kill");
            return true;
        }

        public IntPtr GiveNamedItem(string name)
        {
            GiveCalls.Add(name);
            var mode = GiveBehavior?.Invoke(this, name) ?? SpawnMode.Attached;
            if (mode == SpawnMode.Zero) return IntPtr.Zero;
            var weapon = FakeWorld.NewWeapon(SharedVariantClass && name == "weapon_m4a1_silencer" ? "weapon_m4a1" : name);
            if (SharedVariantClass && name == "weapon_m4a1_silencer") weapon.AttributeManager.Item.ItemDefinitionIndex = 60;
            var handle = new IntPtr(weapon.EntityHandle.Raw);
            if (mode == SpawnMode.Invalid) FakeWorld.Entities[handle].IsValid = false;
            if (mode == SpawnMode.Attached)
                PlayerPawn.Value!.WeaponServices!.MyWeapons.Add(new(weapon));
            return handle;
        }
    }

    public sealed class CCSGameRules
    {
        public bool WarmupPeriod { get; set; }
        public bool FreezePeriod { get; set; } = true;
        public int TotalRoundsPlayed { get; set; } = 3;
    }

    public sealed class CCSGameRulesProxy
    {
        public CCSGameRules? GameRules { get; set; } = new();
    }

    public static class FakeWorld
    {
        private static uint _nextEntity = 1000;
        public static Dictionary<IntPtr, EntityData> Entities { get; } = [];
        public static Dictionary<nint, bool> Helmets { get; } = [];
        public static List<CCSPlayerController> Players { get; } = [];
        public static CCSGameRulesProxy RulesProxy { get; private set; } = new();
        public static int MoneyStateChanges { get; set; }

        public static CBasePlayerWeapon NewWeapon(string name)
        {
            var entity = new EntityData(_nextEntity++, name);
            Entities[new IntPtr(entity.EntityHandle.Raw)] = entity;
            return new(entity);
        }

        public static CBasePlayerWeapon AddWeapon(CCSPlayerController player, string name)
        {
            var weapon = NewWeapon(name);
            player.PlayerPawn.Value!.WeaponServices!.MyWeapons.Add(new(weapon));
            return weapon;
        }

        public static void Reset()
        {
            _nextEntity = 1000;
            Entities.Clear(); Helmets.Clear(); Players.Clear();
            RulesProxy = new(); MoneyStateChanges = 0;
            CounterStrikeSharp.API.Server.CurrentTime = 100f;
            CounterStrikeSharp.API.Server.MapName = "de_mirage";
            CounterStrikeSharp.API.Server.Console.Clear();
            CounterStrikeSharp.API.Server.Frames.Clear();
            CounterStrikeSharp.API.Modules.Cvars.ConVar.Reset();
        }
    }
}

namespace CounterStrikeSharp.API
{
    public static class Server
    {
        public static float CurrentTime { get; set; }
        public static string MapName { get; set; } = "de_mirage";
        public static List<string> Console { get; } = [];
        public static Queue<Action> Frames { get; } = [];
        public static void NextFrame(Action action) => Frames.Enqueue(action);
        public static void RunNextFrame()
        {
            var callbacks = Frames.ToArray(); Frames.Clear();
            foreach (var action in callbacks) action();
        }
        public static void PrintToConsole(string message) => Console.Add(message);
    }

    public static class Utilities
    {
        public static IEnumerable<T> FindAllEntitiesByDesignerName<T>(string name) where T : class => name switch
        {
            "cs_gamerules" => new object[] { Core.FakeWorld.RulesProxy }.OfType<T>(),
            "cs_player_controller" => Core.FakeWorld.Players.OfType<T>(),
            _ => []
        };
        public static void SetStateChanged(object target, string className, string memberName)
        {
            if (memberName == "m_pInGameMoneyServices") Core.FakeWorld.MoneyStateChanges++;
        }
    }
}

namespace CounterStrikeSharp.API.Modules.Utils
{
    public enum CsTeam { None, Spectator, Terrorist, CounterTerrorist }
    public static class ChatColors { public const string Green = "", Yellow = ""; }
}

namespace CounterStrikeSharp.API.Modules.Timers
{
    public enum TimerFlags { STOP_ON_MAPCHANGE }
}

namespace CounterStrikeSharp.API.Modules.Cvars
{
    public sealed class ConVar
    {
        private static readonly Dictionary<string, ConVar> Values = [];
        private object _value = "";
        public string StringValue => _value.ToString() ?? "";
        public T GetPrimitiveValue<T>() => _value is T typed ? typed
            : throw new InvalidOperationException($"ConVar is a {_value.GetType().Name} but you are trying to get a {typeof(T)} value.");
        public static ConVar? Find(string name) => Values.GetValueOrDefault(name);
        public static void Set(string name, object value) => Values[name] = new() { _value = value };
        public static void Reset()
        {
            Values.Clear();
            Set("bot_loadout", ""); Set("mp_maxmoney", 16000);
            Set("mp_freezetime", 15); Set("mp_maxrounds", 24);
            Set("mp_overtime_maxrounds", 6);
        }
    }
}
