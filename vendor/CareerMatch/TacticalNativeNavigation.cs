using System.Buffers.Binary;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;

namespace CareerMatch;

// Current-CS2, fail-closed native navigation adapter. No DLL loading, hooks,
// teleport, velocity writes, aim locks, button ownership, or old-state restore.
// Audited games: 2000922 (Sep 30) and 2000924 / revision 11076591 (Oct 02).
// server.dll SHA256 below; addresses are derived from unique .text signatures,
// never from a CSGO address or from an assumed Source2 object layout.
//
// Native bot_goto_mark/selected callbacks (RVA 2e8ab0/2e8ba0) inline MoveTo:
//   MoveToState.position at bot+2e8/+2f0, route at bot+2f4 = 1,
//   RDX=bot+2e0, RCX=bot, call SetState (this build RVA 2de010).
// The genuine wrapper (RVA 2cfec0) takes RCX=bot, RDX=float[3]*,
// R8D=route; it performs those same writes and tail-calls SetState.
// Generic schema m_goalPosition is bot+5e4: writing it is NOT MoveTo.
// State identities were checked via GetName vtables and constructor writes:
//   Idle: getter 2c49e0, vtable 17ad728, bot+218.
//   MoveTo: getter 2c49f0, vtable 17ad7b8, bot+2e0.
// Constructor writes at 2af23d/2af28a and command registrations at
// 57720/57790 independently confirm these states. SetState's complete body
// still reads/writes the current state at +5c0; do not infer this from a hash.
// Idle's genuine wrapper clears task/entity then tail-calls the same SetState.
// Hidden layout is never written directly. IsMovingTo reads the audited state
// pointer/goal under the same build/code guard solely to debounce commands.
// True from TryMoveTo means the native call returned, NOT that a path exists
// or the bot arrived. MoveTo.OnEnter (32a630) ignores that wrapper's route and
// uses SAFEST=2 except for three native tasks. ComputePath (2bafa0) can also
// refuse during m_repathTimer without discarding the old path. Custom commands
// therefore enter MoveTo, hold briefly, then explicitly commit FASTEST=1 via
// that engine function. Its fifth bool* reports rate limiting. The identifiers
// come from this build's BT_ACTION_MOVETO_FASTEST_ROUTE/SAFEST_ROUTE parser
// (307c6d/307c89), not a legacy CSGO enum. No timer/task/path memory is written.
internal sealed class TacticalNativeNavigation
{
    internal const string AuditedServerSha256 = "098D4DDD57E2FBE9A73623A2BF68EBAFF86F7B6342DDB3D5A0F69CD6335B31CC";
    internal const string PreviousServerSha256 = "3541E46A3193FCF1151E97CE19CD4DAF86C5FDB2889033C2BAB1D4CC7F555B9C";
    internal const string AuditedVersion = "2000924 / 1.41.8.8 / 11076591 / 2026-10-02";
    // Both builds have identical complete bodies for all nine guarded path
    // functions, the two state wrappers, gait bodies and MoveTo vtable slots.
    // Reviewed hashes provide a legacy exact-file profile. A different file
    // may use the bounded complete current feature profile below instead.
    internal static bool IsAuditedServerHash(string hash) =>
        hash is AuditedServerSha256 or PreviousServerSha256 or TacticalServer927.Sha256;

    private static readonly byte[] MoveSignature = Convert.FromHexString(
        "F20F1002F20F1181E80200008B4208488D91E00200008981F0020000448981F4020000E928E10000");
    private static readonly byte[] IdleSignature = Convert.FromHexString(
        "C781D005000000000000488D9118020000C781D4050000FFFFFFFFE9C05D0100");
    private static readonly byte[] StatePrefix = Convert.FromHexString(
        "48895C240848896C24104889742418574883EC30");
    private static readonly byte[] PathSignature = Convert.FromHexString(
        "488BC448895818488970205557415441554156488DA8F8FEFFFF4881ECE0010000440F2940A8458BE0");
    private static readonly byte[] RunBody = Convert.FromHexString("C681C000000001C3");
    private static readonly byte[] WalkBody = Convert.FromHexString(
        "48895C2418574883EC20488BF9488D5424384881C1D04F0000E8226E9C004C8D87DC4F0000488BC8488D542430E81E70E9FF8038007C12C687C000000000488B5C24404883C4205FC3488B07488BCF488B5C24404883C4205F48FF6028");
    // Complete reviewed bodies needed for the path-before-goal handoff. These
    // do not contain base relocations. File bodies remain exact; loaded bodies
    // admit only the separately reviewed BotAI variant below, frozen at bind.
    // OnEnter's rate-limited ComputePath leaves the preceding accepted path
    // intact; OnExit and its look-reset helper do not clear movement paths.
    private static readonly (int Rva, int Length, string Name, string Sha)[] ContinuationBodies = [
        (0x2bafa0, 1758, "ComputePath", "4F3DD2316CA46CE449B3E5A3EA5A3324402C06A4C5CE010C2F7E4C1D4DB8238E"),
        (0x32a630, 151, "MoveToEnter", "4B0B23839CE97F9A6DF960DAE6412B60796D8117A2CE6996E304C971CEBCABCE"),
        (0x32aaf0, 33, "MoveToExit", "1CE8AE477D039B96ED838B9F5648F951C974404B103978CE70EF752E5A51401D"),
        (0x2de010, 275, "SetState", "2BCDEE4C23F098BD4B15590FCDA8CBC55E4F28DA055A5EEA8234ECB78244D268"),
        (0x2dd880, 173, "ExitLookReset", "B5F5989817A1BB2CEB87090E77995EC92DC6E7C85EB1FD4771EF18891065A5BA"),
        (0x330e90, 3133, "MoveToUpdate", "A82E98C28371C15B898A79941B4096CA092BC336D1E96B8C9F34C45A9C49249B"),
        (0x2cce50, 131, "EnterWeaponQuery", "5C05853A98A5D7E8AD46A6F4EA23F5121417CF418527F2A5F48952570BBB25A2"),
        (0x2cdc90, 46, "EnterTimeQuery", "EAEDDD37F262B5BE431A6E467F696E5D9CF6444B103EEF444AA152FD7C14041D"),
        (0x2cb9a0, 153, "EnterSceneQuery", "A4A6A316DF5369289D09479EA53919E668A2477D239F7DA874D1F05C77FF29D6"),
    ];
    private const int MoveToUpdateIndex = 5, DefuseVisibilityOffset = 0x33185b - 0x330e90;
    // BotAI WindowsPatchDefinitions.DefuseBomb_SkipIsVisibleCheck (offset 28):
    // MoveTo.OnUpdate's JE after the bomb visibility test becomes six NOPs.
    // This does not change the path/goal/timer writes used by continuation.
    // Source and installed plugin were checked separately from the game file.
    private static readonly byte[] DefuseVisibilityBranch = Convert.FromHexString("0F84D9000000");
    private static readonly byte[] DefuseVisibilityPatch = Convert.FromHexString("909090909090");

    [DllImport("kernel32.dll", EntryPoint = "GetModuleHandleW", CharSet = CharSet.Unicode)]
    private static extern nint GetModuleHandle(string fileName);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void MoveToFn(nint bot, nint vector, int route);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void IdleFn(nint bot);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate byte ComputePathFn(nint bot, nint vector, int route, float costPenalty, nint rateLimited);

    internal sealed record Audit(string Sha256, int MoveRva, int IdleRva, int StateRva, int PathRva, int ImageSize)
    {
        internal TacticalFeatureAudit.Snapshot? Dependencies { get; init; }
        public int BotVtableRva => Sha256 == TacticalServer927.Sha256 ? TacticalServer927.BotVtable : 0x17ad970;
        public int MoveToVtableRva => Sha256 == TacticalServer927.Sha256 ? TacticalServer927.MoveToVtable : 0x17ad7b8;
        public string CompatibilityProfile => Sha256 == TacticalServer927.Sha256 ? "reviewed_2000927"
            : Dependencies is null ? "reviewed_whole_file" : "current_stable_rva_features";
    }
    private readonly nint _module;
    private readonly MoveToFn _move;
    private readonly IdleFn _idle;
    private readonly ComputePathFn _path;
    private readonly byte[][] _continuationCode;
    private readonly byte[][] _continuationScratch;
    private readonly int _gameThread;
    private readonly TacticalFeatureAudit.LoadedGuard? _dependencyGuard;
    internal Audit Evidence { get; }
    internal string LoadedContinuationVariant { get; }

    private TacticalNativeNavigation(nint module, Audit audit, byte[][] continuationCode, string variant,
        TacticalFeatureAudit.LoadedGuard? dependencyGuard)
    {
        _module = module;
        Evidence = audit;
        _continuationCode = continuationCode;
        _continuationScratch = continuationCode.Select(body => new byte[body.Length]).ToArray();
        _gameThread = Environment.CurrentManagedThreadId;
        LoadedContinuationVariant = variant;
        _dependencyGuard = dependencyGuard;
        _move = Marshal.GetDelegateForFunctionPointer<MoveToFn>(module + audit.MoveRva);
        _idle = Marshal.GetDelegateForFunctionPointer<IdleFn>(module + audit.IdleRva);
        _path = Marshal.GetDelegateForFunctionPointer<ComputePathFn>(module + audit.PathRva);
    }

    // File-only audit is safe outside the game and does not load/execute it.
    internal static bool TryAuditFile(string serverPath, out Audit? audit, out string reason)
        => TryAuditCode(serverPath, out audit, out _, out reason);

    internal static bool TryAuditCode(string serverPath, out Audit? audit, out byte[][]? code, out string reason)
    {
        audit = null; code = null;
        try { return TryAuditBytes(File.ReadAllBytes(serverPath), out audit, out code, out reason); }
        catch (Exception ex) { reason = "navigation_audit_failed:" + ex.Message; return false; }
    }

    // Pure byte audit for regression fixtures; no temporary game DLL required.
    internal static bool TryAuditBytes(byte[] bytes, out Audit? audit, out byte[][]? code, out string reason)
    {
        audit = null; code = null;
        try
        {
            var hash = Convert.ToHexString(SHA256.HashData(bytes));
            var dependencies = IsAuditedServerHash(hash) ? null : TacticalFeatureAudit.Audit(bytes, observation: false);
            int nt = Read32(bytes, 0x3c);
            if (Read32(bytes, nt) != 0x4550 || Read16(bytes, nt + 4) != 0x8664)
                throw new InvalidDataException("server_pe_not_win64");
            int optional = nt + 24;
            if (Read16(bytes, optional) != 0x20b) throw new InvalidDataException("server_pe_not_pe32plus");
            int imageSize = Read32(bytes, optional + 56);
            int sections = Read16(bytes, nt + 6), table = optional + Read16(bytes, nt + 20);
            int textRva = -1, textRaw = -1, textLength = -1;
            for (int i = 0; i < sections; i++)
            {
                int row = table + i * 40;
                if (!bytes.AsSpan(row, 8).SequenceEqual(new byte[] { 46, 116, 101, 120, 116, 0, 0, 0 })) continue;
                if ((Read32(bytes, row + 36) & 0x20000000) == 0) throw new InvalidDataException("text_not_executable");
                textRva = Read32(bytes, row + 12); textLength = Read32(bytes, row + 16); textRaw = Read32(bytes, row + 20);
                break;
            }
            if (textRva < 0 || textRaw < 0 || textLength <= 0 || (long)textRaw + textLength > bytes.Length)
                throw new InvalidDataException("server_text_bounds");
            var text = bytes.AsSpan(textRaw, textLength);
            int move = UniqueIndex(text, MoveSignature), idle = UniqueIndex(text, IdleSignature), path = UniqueIndex(text, PathSignature);
            if (move < 0 || idle < 0 || path < 0) throw new InvalidDataException("navigation_signature_not_unique");
            int moveRva = checked(textRva + move), idleRva = checked(textRva + idle);
            if (moveRva != 0x2cfec0 || idleRva != 0x2c8230 || textRva + path != 0x2bafa0)
                throw new InvalidDataException("navigation_function_identity_mismatch");
            int moveState = TailTarget(moveRva, MoveSignature), idleState = TailTarget(idleRva, IdleSignature);
            if (moveState != idleState || moveState < textRva || moveState + StatePrefix.Length > textRva + textLength)
                throw new InvalidDataException("navigation_setstate_target_mismatch");
            if (!text.Slice(moveState - textRva, StatePrefix.Length).SequenceEqual(StatePrefix))
                throw new InvalidDataException("navigation_setstate_prefix_mismatch");
            for (var i = 0; i < ContinuationBodies.Length; i++)
            {
                var body = ContinuationBodies[i];
                var expected = hash == TacticalServer927.Sha256 ? TacticalServer927.NavigationHashes[i] : body.Sha;
                if (body.Rva < textRva || (long)body.Rva+body.Length > textRva+textLength
                    || Convert.ToHexString(SHA256.HashData(text.Slice(body.Rva-textRva, body.Length))) != expected)
                    throw new InvalidDataException("navigation_continuation_audit_mismatch:"+body.Name);
            }
            code = ContinuationBodies.Select(body =>
                bytes.AsSpan(textRaw+body.Rva-textRva, body.Length).ToArray()).ToArray();
            audit = new(hash, moveRva, idleRva, moveState, textRva + path, imageSize) { Dependencies = dependencies };
            reason = "file_audited_not_live_navigation_verified:profile=" + audit.CompatibilityProfile;
            return true;
        }
        catch (Exception ex) { reason = "navigation_audit_failed:" + ex.Message; return false; }
    }

    internal static bool TryBind(string serverPath, out TacticalNativeNavigation? navigation, out string reason)
    {
        navigation = null;
        if (!OperatingSystem.IsWindows() || IntPtr.Size != 8) { reason = "navigation_windows_x64_only"; return false; }
        if (!TryAuditCode(serverPath, out var audit, out var code, out reason)) return false;
        try
        {
            // Borrow only the exact module already loaded by CS2. A second
            // server.dll exists in Metamod: use the full game module path.
            var module = GetModuleHandle(Path.GetFullPath(serverPath));
            if (module == 0) { reason = "audited_server_module_not_loaded"; return false; }
            if (!MatchMemory(module + audit!.MoveRva, MoveSignature) ||
                !MatchMemory(module + audit.IdleRva, IdleSignature) ||
                !MatchMemory(module + audit.StateRva, StatePrefix) ||
                !MatchMemory(module + audit.PathRva, PathSignature))
            { reason = "loaded_navigation_code_differs_from_audited_file"; return false; }
            var observed = ContinuationBodies.Select(body => new byte[body.Length]).ToArray();
            for (var i = 0; i < ContinuationBodies.Length; i++)
                Marshal.Copy(module+ContinuationBodies[i].Rva, observed[i], 0, observed[i].Length);
            // Reject a foreign code body before publishing the adapter or
            // issuing any movement. Do not discover this only at node one.
            if (!TrySelectContinuationSnapshots(code!, observed, out var selected, out var variant, out reason)) return false;
            TacticalFeatureAudit.LoadedGuard? dependencies = null;
            if (audit.Dependencies is not null && !audit.Dependencies.TryBind(module, observation: false, out dependencies, out reason)) return false;
            navigation = new(module, audit, selected!, variant, dependencies);
            reason = "native_navigation_bound_not_live_navigation_verified:continuation=" + variant + ":profile=" + audit.CompatibilityProfile;
            return true;
        }
        catch (Exception ex) { reason = "navigation_bind_failed:" + ex.Message; return false; }
    }

    // Only after entering the corresponding MoveTo state. Calling this does
    // not change its native task or restore any state. Repeated attempts while
    // rate-limited are read/return only; successful calls use native NAV and
    // collision-aware path construction, never a forced straight line.
    internal bool TryShortestPath(CCSPlayerController player, uint expectedPawn, float x, float y, float z, out string reason)
    {
        if (!float.IsFinite(x) || !float.IsFinite(y) || !float.IsFinite(z)) { reason = "navigation_goal_not_finite"; return false; }
        if (!SafeBot(player, expectedPawn, out var bot, out reason) || !CodeUnchanged(out reason)) return false;
        if (!OwnsGoal(bot, x, y, z)) { reason = "navigation_goal_changed"; return false; }
        var buffer = Marshal.AllocHGlobal(16);
        try
        {
            Marshal.WriteInt32(buffer, 0, BitConverter.SingleToInt32Bits(x));
            Marshal.WriteInt32(buffer, 4, BitConverter.SingleToInt32Bits(y));
            Marshal.WriteInt32(buffer, 8, BitConverter.SingleToInt32Bits(z));
            Marshal.WriteByte(buffer, 12, 0);
            // Current OnEnter calls this exact ABI with 100.0 and a null fifth
            // argument. Supply our own one-byte flag to distinguish a busy
            // native timer from an unreachable destination. Do not clear or
            // guess the world-time basis of m_repathTimer.
            var accepted = _path(bot, buffer, 1, 100f, buffer + 12);
            var limited = Marshal.ReadByte(buffer, 12);
            if (accepted > 1 || limited > 1 || (accepted != 0 && limited != 0))
            { reason = "navigation_path_result_invalid"; return false; }
            if (limited != 0) { reason = "navigation_path_rate_limited"; return false; }
            if (accepted == 0) { reason = "navigation_path_unavailable"; return false; }
            RefreshRushIntent(player);
            reason = "shortest_native_path_accepted_arrival_unverified";
            return true;
        }
        finally { Marshal.FreeHGlobal(buffer); }
    }

    internal bool TryMoveTo(CCSPlayerController player, uint expectedPawn, float x, float y, float z, out string reason)
    {
        if (!float.IsFinite(x) || !float.IsFinite(y) || !float.IsFinite(z)) { reason = "navigation_goal_not_finite"; return false; }
        if (!SafeBot(player, expectedPawn, out var bot, out reason) || !CodeUnchanged(out reason)) return false;
        RefreshRushIntent(player);
        nint vector = Marshal.AllocHGlobal(12);
        try
        {
            Marshal.WriteInt32(vector, 0, BitConverter.SingleToInt32Bits(x));
            Marshal.WriteInt32(vector, 4, BitConverter.SingleToInt32Bits(y));
            Marshal.WriteInt32(vector, 8, BitConverter.SingleToInt32Bits(z));
            _move(bot, vector, 1); // Same route argument as bot_goto_mark/selected.
            reason = "move_to_issued_arrival_unverified";
            return true;
        }
        finally { Marshal.FreeHGlobal(vector); }
    }

    // Through-points keep the old owned goal while ComputePath is busy. Only
    // after a successor path is accepted do we enter its MoveTo state, in the
    // same server-thread call. Its OnEnter cannot erase the accepted path on
    // the same-frame rate-limited retry (see the continuation code audit).
    // No target/path/timer fields are patched and no movement hold is needed.
    internal bool TryContinueRoute(CCSPlayerController player, uint expectedPawn,
        float previousX, float previousY, float previousZ,
        float nextX, float nextY, float nextZ, out string reason)
    {
        if (!float.IsFinite(previousX) || !float.IsFinite(previousY) || !float.IsFinite(previousZ)
            || !float.IsFinite(nextX) || !float.IsFinite(nextY) || !float.IsFinite(nextZ))
        { reason = "navigation_goal_not_finite"; return false; }
        if (!SafeBot(player, expectedPawn, out var bot, out reason) || !CodeUnchanged(out reason)
            || !ContinuationCodeUnchanged(bot, out reason)) return false;
        if (!OwnsGoal(bot, previousX, previousY, previousZ))
        { reason = "navigation_previous_goal_changed"; return false; }
        var repath = player.PlayerPawn.Value!.Bot!.RepathTimer;
        if (repath.Timescale != 1f)
        { reason = "navigation_successor_clock_invalid"; return false; }
        var buffer = Marshal.AllocHGlobal(16);
        try
        {
            Marshal.WriteInt32(buffer, 0, BitConverter.SingleToInt32Bits(nextX));
            Marshal.WriteInt32(buffer, 4, BitConverter.SingleToInt32Bits(nextY));
            Marshal.WriteInt32(buffer, 8, BitConverter.SingleToInt32Bits(nextZ));
            Marshal.WriteByte(buffer, 12, 0);
            var accepted = _path(bot, buffer, 1, 100f, buffer + 12);
            var limited = Marshal.ReadByte(buffer, 12);
            if (accepted > 1 || limited > 1 || (accepted != 0 && limited != 0))
            { reason = "navigation_path_result_invalid"; return false; }
            if (limited != 0) { reason = "navigation_path_rate_limited"; return false; }
            if (accepted == 0) { reason = "navigation_path_unavailable"; return false; }
            // Same-frame OnEnter must see the cooldown just created by the
            // successful path call. Inspect validity only: no timer writes or
            // comparisons against the wrong server/world clock.
            if (!float.IsFinite(repath.Timestamp) || repath.Timescale != 1f
                || !float.IsFinite(repath.Duration) || repath.Duration < .4f || repath.Duration > .6f)
            { reason = "navigation_successor_repath_timer_invalid"; return false; }
            if (!SafeBot(player, expectedPawn, out var stillBot, out reason)) return false;
            if (stillBot != bot || !OwnsGoal(bot, previousX, previousY, previousZ))
            { reason = "navigation_successor_previous_goal_changed"; return false; }
            _move(bot, buffer, 1);
            if (!OwnsGoal(bot, nextX, nextY, nextZ))
            { reason = "navigation_successor_goal_not_owned"; return false; }
            RefreshRushIntent(player);
            reason = "continuous_native_successor_accepted_arrival_unverified";
            return true;
        }
        finally { Marshal.FreeHGlobal(buffer); }
    }

    // Public schema intent, not forced speed or input injection. The engine's
    // MoveTo uses IsHurrying to choose Run/Walk. Renew only while this command
    // owns the same live pawn; combat/utility gates still take priority.
    internal bool TryKeepRushing(CCSPlayerController player, uint expectedPawn, out string reason)
    {
        if (!SafeBot(player, expectedPawn, out _, out reason) || !CodeUnchanged(out reason)) return false;
        RefreshRushIntent(player);
        reason = "short_native_rush_intent_renewed";
        return true;
    }

    private static void RefreshRushIntent(CCSPlayerController player)
    {
        var bot = player.PlayerPawn.Value!.Bot!;
        var timer = bot.HurryTimer;
        timer.Duration = 2;
        timer.Timestamp = Server.CurrentTime + 2;
        timer.Timescale = 1;
        bot.IsRunning = true;
        // Never restore/clear this timer: an intervening native bomb/combat
        // decision may also use it. Stop renewing and allow it to expire.
    }

    // Read-only debounce: never re-enter MoveTo/OnEnter each poll while its
    // current state already owns the same goal. Private offsets are usable
    // ONLY under a reviewed file/complete feature profile and loaded-code gate.
    internal bool IsMovingTo(CCSPlayerController player, uint expectedPawn, float x, float y, float z)
    {
        if (!float.IsFinite(x) || !float.IsFinite(y) || !float.IsFinite(z) ||
            !SafeBot(player, expectedPawn, out var bot, out _, inspectOnly: true) || !CodeUnchanged(out _)) return false;
        return OwnsGoal(bot, x, y, z);
    }

    private static bool OwnsGoal(nint bot, float x, float y, float z)
    {
        if (Marshal.ReadIntPtr(bot + 0x5c0) != bot + 0x2e0) return false;
        float goalX = BitConverter.Int32BitsToSingle(Marshal.ReadInt32(bot + 0x2e8));
        float goalY = BitConverter.Int32BitsToSingle(Marshal.ReadInt32(bot + 0x2ec));
        float goalZ = BitConverter.Int32BitsToSingle(Marshal.ReadInt32(bot + 0x2f0));
        return Math.Abs(goalX - x) <= .01f && Math.Abs(goalY - y) <= .01f && Math.Abs(goalZ - z) <= .01f;
    }

    // Only a queue owner cancelling its OWN command may call this. Do not
    // restore an old raw state pointer: OnExit/resources/timers may be stale.
    // During combat this refuses; stop reissuing and defer Idle until safe.
    internal bool TryIdle(CCSPlayerController player, uint expectedPawn, out string reason)
    {
        if (!SafeBot(player, expectedPawn, out var bot, out reason) || !CodeUnchanged(out reason)) return false;
        _idle(bot);
        reason = "idle_issued_native_decisions_retained";
        return true;
    }

    private bool CodeUnchanged(out string reason)
    {
        if (Environment.CurrentManagedThreadId != _gameThread)
        { reason = "navigation_wrong_game_thread"; return false; }
        try
        {
            if (_dependencyGuard is not null && !_dependencyGuard.VerifyIfDue(out reason)) return false;
            if (!MatchMemory(_module + Evidence.MoveRva, MoveSignature) ||
                !MatchMemory(_module + Evidence.IdleRva, IdleSignature) ||
                !MatchMemory(_module + Evidence.StateRva, StatePrefix) ||
                !MatchMemory(_module + Evidence.PathRva, PathSignature))
            { reason = "loaded_navigation_code_changed"; return false; }
            for (var i = 0; i < ContinuationBodies.Length; i++)
                Marshal.Copy(_module+ContinuationBodies[i].Rva, _continuationScratch[i], 0, _continuationScratch[i].Length);
            // Reuse buffers for the frozen complete bodies, instead of
            // allocating/hashing them each tick or re-selecting a variant.
            return TryValidateContinuationSnapshot(_continuationCode, _continuationScratch, out reason);
        }
        catch (Exception ex) { reason = "navigation_code_read_failed:"+ex.GetType().Name; return false; }
    }

    private bool ContinuationCodeUnchanged(nint bot, out string reason)
    {
        // ASLR-aware pointers, not raw file VAs. SetState uses these virtual
        // methods; hashing their old bodies alone would miss a replaced slot.
        var botVtable = Marshal.ReadIntPtr(bot);
        if (!LayoutMatches(_module, botVtable, Evidence))
        { reason = "loaded_continuation_vtable_or_gait_changed"; return false; }
        reason = ""; return true;
    }

    // Also exercised with a synthetic, non-executable mapped image.
    internal static bool LayoutMatches(nint module, nint botVtable, Audit evidence) =>
        botVtable == module+evidence.BotVtableRva
        && Marshal.ReadIntPtr(botVtable+0x28) == module+0x2dcab0
        && Marshal.ReadIntPtr(botVtable+0x30) == module+0x2e7a00
        && Marshal.ReadIntPtr(module+evidence.MoveToVtableRva) == module+0x32a630
        && Marshal.ReadIntPtr(module+evidence.MoveToVtableRva+8) == module+0x330e90
        && Marshal.ReadIntPtr(module+evidence.MoveToVtableRva+16) == module+0x32aaf0
        && MatchMemory(module+0x2dcab0, RunBody) && MatchMemory(module+0x2e7a00, WalkBody);

    // Pure byte checks used by file/synthetic regression tests, without loading
    // a game module. Only two EXACT full-body variants exist. Other known
    // BotAI patches outside these bodies are not an excuse for unknown changes.
    internal static bool TrySelectContinuationSnapshots(byte[][] audited, byte[][] observed,
        out byte[][]? selected, out string variant, out string reason)
    {
        selected = null; variant = "";
        if (!ValidContinuationShape(audited) || !ValidContinuationShape(observed))
        { reason = "navigation_continuation_snapshot_shape_invalid"; return false; }
        // Select ONE complete build, never mix bodies from different releases.
        var hashes = audited.Select(body => Convert.ToHexString(SHA256.HashData(body))).ToArray();
        var current = hashes[0] == TacticalServer927.NavigationHashes[0];
        for (var i = 0; i < ContinuationBodies.Length; i++)
            if (hashes[i] != (current ? TacticalServer927.NavigationHashes[i] : ContinuationBodies[i].Sha))
            { reason = "navigation_continuation_snapshot_not_audited:"+ContinuationBodies[i].Name; return false; }
        if (!audited[MoveToUpdateIndex].AsSpan(DefuseVisibilityOffset, 6).SequenceEqual(DefuseVisibilityBranch))
        { reason = "navigation_defuse_visibility_branch_not_audited"; return false; }
        var candidate = audited.Select(body => body.ToArray()).ToArray();
        bool patched = observed[MoveToUpdateIndex].AsSpan(DefuseVisibilityOffset, 6).SequenceEqual(DefuseVisibilityPatch);
        if (patched) DefuseVisibilityPatch.CopyTo(candidate[MoveToUpdateIndex], DefuseVisibilityOffset);
        if (!CompareContinuationBodies(candidate, observed, "loaded_continuation_code_mismatch", out reason)) return false;
        selected = candidate;
        variant = patched ? "BotAI_DefuseBomb_SkipIsVisibleCheck" : "native_unpatched";
        reason = ""; return true;
    }

    internal static bool TryValidateContinuationSnapshot(byte[][] bound, byte[][] observed, out string reason)
    {
        if (!ValidContinuationShape(bound) || !ValidContinuationShape(observed))
        { reason = "navigation_continuation_snapshot_shape_invalid"; return false; }
        return CompareContinuationBodies(bound, observed, "loaded_continuation_code_changed", out reason);
    }

    private static bool ValidContinuationShape(byte[][] code)
    {
        if (code is null || code.Length != ContinuationBodies.Length) return false;
        for (var i = 0; i < code.Length; i++)
            if (code[i] is null || code[i].Length != ContinuationBodies[i].Length) return false;
        return true;
    }

    private static bool CompareContinuationBodies(byte[][] expected, byte[][] observed, string prefix, out string reason)
    {
        for (var i = 0; i < ContinuationBodies.Length; i++)
        {
            if (expected[i].AsSpan().SequenceEqual(observed[i])) continue;
            int offset = 0;
            while (expected[i][offset] == observed[i][offset]) offset++;
            reason = $"{prefix}:{ContinuationBodies[i].Name}:rva=0x{ContinuationBodies[i].Rva+offset:X}:expected={expected[i][offset]:X2}:loaded={observed[i][offset]:X2}";
            return false;
        }
        reason = ""; return true;
    }

    private static bool SafeBot(CCSPlayerController player, uint expectedPawn, out nint bot, out string reason, bool inspectOnly = false)
    {
        bot = 0;
        try
        {
            if (!player.IsValid || player.ControllingBot || player.HasBeenControlledByPlayerThisRound)
            { reason = "navigation_actor_not_owned_live_bot"; return false; }
            var pawn = player.PlayerPawn.Value;
            if (pawn is not { IsValid: true, Health: > 0 } ||
                pawn.EntityHandle.Raw != expectedPawn || pawn.Bot is not { } nativeBot || nativeBot.Handle == 0)
            { reason = "navigation_actor_not_owned_live_bot"; return false; }
            // IsBot is intentionally not a gate: BotHider changes fake-client
            // flags. The caller must additionally check the signed career roster.
            var weapon = pawn.WeaponServices?.ActiveWeapon.Value?.DesignerName ?? "";
            if (!inspectOnly && (nativeBot.IsEnemyVisible || nativeBot.IsAttacking || pawn.BlindUntilTime > Server.CurrentTime || pawn.IsDefusing ||
                weapon.Contains("grenade") || weapon.Contains("flashbang") || weapon.Contains("molotov") || weapon.Contains("c4")
                || nativeBot.IsAvoidingGrenade.Timestamp > Server.CurrentTime))
            { reason = "native_combat_or_objective_retained"; return false; }
            bot = nativeBot.Handle; reason = ""; return true;
        }
        catch (Exception ex) { reason = "navigation_actor_check_failed:" + ex.GetType().Name; return false; }
    }

    private static int UniqueIndex(ReadOnlySpan<byte> haystack, ReadOnlySpan<byte> needle)
    {
        int first = haystack.IndexOf(needle);
        if (first < 0 || haystack[(first + 1)..].IndexOf(needle) >= 0) return -1;
        return first;
    }
    private static int TailTarget(int rva, byte[] signature)
    {
        int jump = signature.Length - 5;
        if (signature[jump] != 0xe9) throw new InvalidDataException("navigation_wrapper_not_tail_jump");
        return checked(rva + signature.Length + Read32(signature, jump + 1));
    }
    private static bool MatchMemory(nint address, byte[] expected)
    {
        var observed = new byte[expected.Length]; Marshal.Copy(address, observed, 0, observed.Length);
        return observed.AsSpan().SequenceEqual(expected);
    }
    private static int Read32(byte[] bytes, int offset) => BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(offset, 4));
    private static ushort Read16(byte[] bytes, int offset) => BinaryPrimitives.ReadUInt16LittleEndian(bytes.AsSpan(offset, 2));
}
