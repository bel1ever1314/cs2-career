using CounterStrikeSharp.API.Core;

namespace CounterStrikeSharp.API
{
    public static class Server { public static float CurrentTime => 20; }
}
namespace CounterStrikeSharp.API.Core
{
    public sealed class Handle<T>(T? value) { public T? Value = value; }
    public sealed class Pawn
    {
        public bool IsValid = true; public int Health = 97; public object? Bot = new();
        public Body EntityHandle = new(700);
    }
    public sealed record Body(uint Raw);
    public sealed class CCSPlayerController
    {
        public bool IsValid = true, ControllingBot, HasBeenControlledByPlayerThisRound;
        public int Slot = 7; public string? Id = "bot"; public string Side = "t";
        public Handle<Pawn> PlayerPawn = new(new());
    }
    public sealed class EventPlayerHurt
    {
        public CCSPlayerController? Userid; public int DmgHealth = 3, DmgArmor;
        // No attacker is needed to free movement from self/world/fire damage.
    }
}
namespace Microsoft.Extensions.Logging
{
    public sealed class TestLogger { public int Failures; }
    public static class TestLoggerExtensions
    {
        public static void LogWarning(this TestLogger logger, Exception error, string message, params object[] values)
            => logger.Failures++;
    }
}
namespace CareerMatch
{
    public sealed record CommandPlan(string MatchNonce, int Round, string Side);
    public sealed partial class CareerMatchPlugin
    {
        public bool _roundLive = true, _resultWritten, _setupDone = true, Warmup;
        public string _contractError = "", _sessionNonce = "match";
        public int _tacticalEpoch = 4;
        public sealed class Request { public bool Active = true, Observer; public string HumanPlayerId = "human"; }
        public Request? _request = new();
        public sealed record Row(bool IsBot);
        public readonly Dictionary<string, Row> _ledger = new() { ["bot"] = new(true), ["other"] = new(true) };
        public sealed class Token { public int Calls; public bool Throw; public void Release() { Calls++; if (Throw) throw new Exception("release failed"); } }
        public sealed class Path { public int Calls; public void Reset() => Calls++; }
        public sealed class Clock { public int Stage; }
        public sealed record Target(int Id);
        public sealed class CustomActor
        {
            public string Id = "bot"; public uint Pawn = 700;
            public Clock Clock = new(); public Target[] Targets = [new(1), new(2)];
            public Token Jump = new(), Gait = new(), Look = new(), PathHold = new(), Hold = new();
            public Path Continuation = new(), DirectMove = new();
        }
        public sealed class PostActor
        {
            public string Id = "bot"; public uint Pawn = 700; public Target Target = new(3);
            public Token Hold = new(), PathHold = new(); public Path Path = new();
        }
        public sealed record TacticalActor(string Id, int Slot, uint Pawn, Target[] Targets, float Time);
        public CommandPlan? _customTacticPlan = new("match", 4, "t"), _postPlantPlan = new("match", 4, "t"), _tacticalPlan = new("match", 4, "t");
        public readonly Dictionary<int, CustomActor> _customTacticActors = [];
        public readonly Dictionary<int, PostActor> _postPlantActors = [];
        public readonly Dictionary<int, TacticalActor> _tacticalActors = [];
        public readonly Dictionary<int, object> _tacticalReleases = [];
        public sealed class Opening { public Token Lease = new(); }
        public readonly Dictionary<int, Opening> _openingGuards = [];
        public readonly Dictionary<int, object> _naturalTasks = [], _naturalAssignments = [], _naturalLaneAssignments = [], _naturalLaneLockUntil = [], _naturalStuckTicks = [];
        public readonly Microsoft.Extensions.Logging.TestLogger Logger = new();
        public readonly List<string> NativeCalls = [], NaturalCalls = [], Traces = [];
        private bool InWarmup() => Warmup;
        private static string? ControllerId(CCSPlayerController? player) => player?.Id;
        private static string LiveSide(CCSPlayerController player) => player.Side;
        private static void ReleaseCustomJumpGuard(CustomActor a, string _) => a.Jump.Release();
        private static void ReleaseCustomTravelGait(CustomActor a) => a.Gait.Release();
        private static void ReleaseCustomLook(CustomActor a) => a.Look.Release();
        private void ReleaseTacticalActor(TacticalActor a, string reason) => NativeCalls.Add(a.Id+":"+reason);
        private void ReleaseMotionClip(int slot, string _) => NaturalCalls.Add("clip:"+slot);
        private void ReleaseCorner(int slot, string _) => NaturalCalls.Add("corner:"+slot);
        private void ReleaseNatural(int slot, string _) => NaturalCalls.Add("natural:"+slot);
        private void ReleaseNaturalRecovery(int slot, string _) => NaturalCalls.Add("recovery:"+slot);
        private void ReleaseNaturalJumpBlock(int slot) => NaturalCalls.Add("jump:"+slot);
        private void TacticalTrace(string kind, object data) => Traces.Add(kind);
        public void Hurt(CCSPlayerController? player, int hp = 3, int armor = 0)
            => OnTacticalDamage(new() { Userid = player, DmgHealth = hp, DmgArmor = armor });
        public bool Danger(CCSPlayerController? p, string reason) => ReleaseTacticForDanger(p, reason);
        public bool NativeOwns(CCSPlayerController p) => NativeSafetyOwnsActor(p);
        public void NextRound() { _tacticalSafetyHandoffs.Clear(); _tacticalEpoch++; }
    }
}
