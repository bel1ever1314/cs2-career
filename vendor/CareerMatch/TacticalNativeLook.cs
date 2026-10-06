using System.Buffers.Binary;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;

namespace CareerMatch;

internal readonly record struct TacticalLookActor(int Slot, uint Pawn, nint Bot, int Health,
    float EyeX, float EyeY, float EyeZ, bool NativeHandoff);
internal readonly record struct TacticalLookRequest(int State, int Priority, nint Descriptor,
    float X, float Y, float Z);

// The lease state machine is independently testable without executing CS2.
internal interface ITacticalLookApi
{
    float Now { get; }
    bool TryActor(int slot, out TacticalLookActor actor, out string reason);
    bool TryRequest(nint bot, out TacticalLookRequest request, out string reason);
    bool TrySet(nint bot, nint descriptor, float x, float y, float z, out string reason);
    bool TryClearOwned(nint bot, nint descriptor, out string reason);
}

// Native observation intent, never EyeAngles/Teleport/aim locks/usercmd view.
// Audited Windows servers 2000922 (Sep 30) and 2000924 (Oct 02 2026).
// SetLookAt 2dda40..2ddb9a copies Vector, retains char* description, and returns
// void. RCX=bot, RDX=description, R8=Vector*, R9D=priority; stack args are
// float duration, byte clearIfClose, float tolerance, byte attack. Existing
// greater priority wins. Native MoveTo requests priority 0 (331226); this
// hold-only request uses 1, and never requests attack. Enemy aim bypasses the
// observation consumer (2e6ec8, m_isAimingAtEnemy at +5c74).
//
// Hidden request state +535c and description +5380 were checked against the
// complete native ClearLookAt action 2fc1d0..2fc1e3: it ONLY clears those two
// fields. Its RCX is a BT context, NOT a bot; do not call it with a CCSBot.
// Here the same minimal clear is permitted only on the owning game thread,
// after rechecking the same live pawn/Bot and our unique descriptor pointer.
// Other owners' requests are never cleared. No strategic state is changed.
//
// Consumer 2e6d30..2e730b changes state 1 -> 2 only after alignment and starts
// duration at that moment, not submission. An unaligned request has no proven
// TTL, so the managed lease has an explicit 2-second alignment deadline.
// Same owned target is not resubmitted: a 32s duration covers the playbook's
// <=30s wait without fighting native smoothing. Release/handoff ends it now.
internal sealed class TacticalNativeLook : ITacticalLookApi
{
    internal const string AuditedServerSha256 = "098D4DDD57E2FBE9A73623A2BF68EBAFF86F7B6342DDB3D5A0F69CD6335B31CC";
    internal const string PreviousServerSha256 = "3541E46A3193FCF1151E97CE19CD4DAF86C5FDB2889033C2BAB1D4CC7F555B9C";
    internal static bool IsAuditedServerHash(string hash) =>
        hash is AuditedServerSha256 or PreviousServerSha256 or TacticalServer927.Sha256;
    // The new file was separately disassembled: request fields, argument
    // widths, priority/near-spot branches, alignment state and drift calls
    // retain the audited layout. Pin all three complete new bodies too.
    private static readonly string[] CurrentBodyHashes = [
        "196BC0346BA71B245A59CF0A0A15B350887F3E8A783BC90AA4BF9C8D860B0935",
        "AE3C4B176B72ABFD6C1524B58648CF714D0D338F3D3E652EF340777661808917",
        "C30F6D1B055D250092218AB745BD5A41E249158BFA251C950BB080CC4ECD2956",
    ];
    internal const int RequestPriority = 1;
    internal const float RequestDuration = 32;
    internal const float AlignmentTimeout = 2;
    private const int RequestStateOffset = 0x535c, DescriptorOffset = 0x5380;
    private const int LookLength = 0x15b, ClearLength = 20, ConsumerLength = 0x5dc;
    private const int ConsumerRva = 0x2e6d30, CosOffset = 0x2e729b - ConsumerRva, SinOffset = 0x2e72c8 - ConsumerRva;
    private static readonly byte[] CosCall = Convert.FromHexString("E830840300");
    private static readonly byte[] SinCall = Convert.FromHexString("E843840300");
    private static readonly byte[] ZeroDrift = Convert.FromHexString("0F57C09090");
    private static readonly byte[] LookPrefix = Convert.FromHexString(
        "48895C2418488974242057415441574883EC40488B59184C8BE2488BF9418BF1488D4C24304D8BF8");
    private static readonly byte[] ClearBytes = Convert.FromHexString("488B410833C989885C53000048898880530000C3");
    private static readonly byte[] ConsumerPrefix = Convert.FromHexString(
        "48895C2410488974241848897C242055488D6C24A94881ECA0000000488D05ED814C0148C745FF1F000000488945F74C8D45170F1045F7");

    [DllImport("kernel32.dll", EntryPoint = "GetModuleHandleW", CharSet = CharSet.Unicode)]
    private static extern nint GetModuleHandle(string fileName);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void LookAtFn(nint bot, nint descriptor, nint spot, int priority,
        float duration, byte clearIfClose, float angleTolerance, byte attack);

    internal sealed record Audit(string Sha256, int LookRva, int ClearRva, int ConsumerRva,
        int LookBytes, int ClearBytes, int ConsumerBytes, int ImageSize)
    {
        internal TacticalFeatureAudit.Snapshot? Dependencies { get; init; }
        public string CompatibilityProfile => Sha256 == TacticalServer927.Sha256 ? "reviewed_2000927"
            : Dependencies is null ? "reviewed_whole_file" : "current_stable_rva_features";
    }
    private readonly nint _module;
    private readonly int _gameThread;
    private readonly LookAtFn _look;
    private readonly TacticalFeatureAudit.LoadedGuard? _dependencyGuard;
    private readonly byte[][] _code;
    private readonly byte[][] _scratch;
    internal Audit Evidence { get; }
    internal string LoadedVariant { get; }

    private TacticalNativeLook(nint module, Audit audit, byte[][] code, string variant,
        TacticalFeatureAudit.LoadedGuard? dependencyGuard)
    {
        _module = module; Evidence = audit; _code = code;
        LoadedVariant = variant;
        _dependencyGuard = dependencyGuard;
        _scratch = code.Select(c => new byte[c.Length]).ToArray();
        _gameThread = Environment.CurrentManagedThreadId;
        _look = Marshal.GetDelegateForFunctionPointer<LookAtFn>(module + audit.LookRva);
    }

    // Static file audit only: this never loads or executes server.dll.
    internal static bool TryAuditFile(string serverPath, out Audit? audit, out string reason)
        => TryAuditCode(serverPath, out audit, out _, out reason);

    internal static bool TryAuditCode(string serverPath, out Audit? audit, out byte[][]? code, out string reason)
    {
        audit = null; code = null;
        try { return TryAuditBytes(File.ReadAllBytes(serverPath), out audit, out code, out reason); }
        catch (Exception ex) { reason = "look_audit_failed:" + ex.Message; return false; }
    }

    internal static bool TryAuditBytes(byte[] bytes, out Audit? audit, out byte[][]? code, out string reason)
    {
        audit = null; code = null;
        try
        {
            var hash = Convert.ToHexString(SHA256.HashData(bytes));
            var dependencies = IsAuditedServerHash(hash) ? null : TacticalFeatureAudit.Audit(bytes, observation: true);
            int nt = Read32(bytes, 0x3c), optional = checked(nt + 24);
            if (Read32(bytes, nt) != 0x4550 || Read16(bytes, nt + 4) != 0x8664 || Read16(bytes, optional) != 0x20b)
                throw new InvalidDataException("look_server_pe_not_win64");
            int imageSize = Read32(bytes, optional + 56);
            int sections = Read16(bytes, nt + 6), table = checked(optional + Read16(bytes, nt + 20));
            int textRva = -1, textRaw = -1, textLength = -1;
            for (int i = 0; i < sections; i++)
            {
                int row = checked(table + i * 40);
                if (!bytes.AsSpan(row, 8).SequenceEqual(new byte[] { 46, 116, 101, 120, 116, 0, 0, 0 })) continue;
                if ((Read32(bytes, row + 36) & 0x20000000) == 0) throw new InvalidDataException("look_text_not_executable");
                textRva = Read32(bytes, row + 12); textLength = Read32(bytes, row + 16); textRaw = Read32(bytes, row + 20);
                break;
            }
            if (textRva < 0 || textRaw < 0 || textLength <= 0 || (long)textRaw + textLength > bytes.Length)
                throw new InvalidDataException("look_text_bounds");
            var text = bytes.AsSpan(textRaw, textLength);
            var current = hash == TacticalServer927.Sha256;
            int look = UniqueIndex(text, LookPrefix), clear = UniqueIndex(text, ClearBytes),
                consumer = UniqueIndex(text, current ? TacticalServer927.ConsumerPrefix : ConsumerPrefix);
            if (look < 0 || clear < 0 || consumer < 0) throw new InvalidDataException("look_signature_not_unique");
            if (textRva + look != 0x2dda40 || textRva + clear != 0x2fc1d0 || textRva + consumer != 0x2e6d30)
                throw new InvalidDataException("look_function_identity_mismatch");
            // Copy the COMPLETE audited function bodies, not merely prologues.
            // These file bytes are also compared with the already-loaded code
            // before every read/call/owner-gated clear involving private fields.
            code = [text.Slice(look, LookLength).ToArray(), text.Slice(clear, ClearLength).ToArray(),
                text.Slice(consumer, ConsumerLength).ToArray()];
            // The old exact file is still its own immutable complete baseline.
            // Every other file MUST use all three pinned current complete bodies.
            if (hash != PreviousServerSha256)
                for (int i = 0; i < code.Length; i++)
                    if (Convert.ToHexString(SHA256.HashData(code[i])) != (current ? TacticalServer927.LookHashes[i] : CurrentBodyHashes[i]))
                        throw new InvalidDataException("look_complete_body_mismatch:" + i);
            if (code.Any(c => c[^1] != 0xc3)) throw new InvalidDataException("look_function_end_mismatch");
            if (!code[2].AsSpan(CosOffset, 5).SequenceEqual(CosCall) || !code[2].AsSpan(SinOffset, 5).SequenceEqual(SinCall))
                throw new InvalidDataException("look_native_drift_calls_not_audited");
            audit = new(hash, textRva + look, textRva + clear, textRva + consumer,
                LookLength, ClearLength, ConsumerLength, imageSize) { Dependencies = dependencies };
            reason = "look_file_audited_not_live_observation_verified:profile=" + audit.CompatibilityProfile;
            return true;
        }
        catch (Exception ex) { reason = "look_audit_failed:" + ex.Message; return false; }
    }

    internal static bool TryBind(string serverPath, out TacticalNativeLook? observation, out string reason)
    {
        observation = null;
        if (!OperatingSystem.IsWindows() || IntPtr.Size != 8) { reason = "look_windows_x64_only"; return false; }
        if (!TryAuditCode(serverPath, out var audit, out var code, out reason)) return false;
        try
        {
            var module = GetModuleHandle(Path.GetFullPath(serverPath));
            if (module == 0) { reason = "look_audited_server_not_loaded"; return false; }
            var setObserved = new byte[LookLength]; Marshal.Copy(module + audit!.LookRva, setObserved, 0, setObserved.Length);
            if (!setObserved.AsSpan().SequenceEqual(code![0]))
            { reason = Difference("SetLookAt", audit.LookRva, code[0], setObserved); return false; }
            var clearObserved = new byte[ClearLength]; Marshal.Copy(module + audit.ClearRva, clearObserved, 0, clearObserved.Length);
            if (!clearObserved.AsSpan().SequenceEqual(code[1]))
            { reason = Difference("ClearLookAt", audit.ClearRva, code[1], clearObserved); return false; }
            var consumerObserved = new byte[ConsumerLength]; Marshal.Copy(module + audit.ConsumerRva, consumerObserved, 0, consumerObserved.Length);
            if (!TrySelectConsumerSnapshot(code[2], consumerObserved, out var selected, out var variant, out reason)) return false;
            code[2] = selected!;
            TacticalFeatureAudit.LoadedGuard? dependencies = null;
            if (audit.Dependencies is not null && !audit.Dependencies.TryBind(module, observation: true, out dependencies, out reason)) return false;
            observation = new(module, audit, code, variant, dependencies);
            reason = "native_look_bound:" + variant + ":live_observation_not_verified:profile=" + audit.CompatibilityProfile;
            return true;
        }
        catch (Exception ex) { reason = "look_bind_failed:" + ex.Message; return false; }
    }

    // File-only/synthetic-testable selection of FOUR exact complete bodies.
    // Actual BotAI Windows patches named Upkeep_BotCOS_ZeroDrift / SIN replace
    // just calls at 2e729b / 2e72c8 with XORPS XMM0,XMM0; NOP; NOP. Both calls
    // produce additive periodic pitch/yaw drift AFTER the request consumer;
    // clearing their float result does not change request state/priority/owner,
    // stack or control flow. Log-all's applied addresses at base7ffce2820000
    // independently match these RVAs. No PE base relocations overlap any of
    // the three complete guarded functions: this is NOT an ASLR exception.
    // Every other byte is still exact. Bind freezes the selected whole body;
    // later even a transition to a different allowed variant fails closed.
    internal static bool TrySelectConsumerSnapshot(byte[] audited, byte[] observed, out byte[]? selected,
        out string variant, out string reason)
    {
        selected = null; variant = "";
        if (audited.Length != ConsumerLength || observed.Length != ConsumerLength ||
            !audited.AsSpan(CosOffset, 5).SequenceEqual(CosCall) || !audited.AsSpan(SinOffset, 5).SequenceEqual(SinCall))
        { reason = "look_consumer_snapshot_not_audited"; return false; }
        var candidate = audited.ToArray();
        bool cos = observed.AsSpan(CosOffset, 5).SequenceEqual(ZeroDrift), sin = observed.AsSpan(SinOffset, 5).SequenceEqual(ZeroDrift);
        if (cos) ZeroDrift.CopyTo(candidate, CosOffset);
        if (sin) ZeroDrift.CopyTo(candidate, SinOffset);
        if (!observed.AsSpan().SequenceEqual(candidate))
        { reason = Difference("LookConsumer", ConsumerRva, candidate, observed); return false; }
        selected = candidate;
        variant = cos ? sin ? "BotAI_COS_SIN_ZeroDrift" : "BotAI_COS_ZeroDrift"
            : sin ? "BotAI_SIN_ZeroDrift" : "native_unpatched";
        reason = "look_complete_consumer_snapshot_verified:" + variant;
        return true;
    }

    internal Lease CreateLease(int slot, uint expectedPawn, int initialHealth)
    {
        if (slot < 0 || expectedPawn == 0 || initialHealth <= 0) throw new ArgumentException("look_actor_identity_invalid");
        // SetLookAt stores this pointer. Never free a published descriptor,
        // including after disconnect, pawn replacement, reload, or failed code
        // guard: the old native body may still reference it. The allocation is
        // intentionally process-lifetime (one tiny unique string per lease).
        // There is NO finalizer/unload cleanup that could cause use-after-free.
        var descriptor = Marshal.StringToCoTaskMemUTF8("CareerMatch/custom-hold/" + Guid.NewGuid().ToString("N"));
        return new(this, slot, expectedPawn, initialHealth, descriptor);
    }

    float ITacticalLookApi.Now => Server.CurrentTime;
    bool ITacticalLookApi.TryActor(int slot, out TacticalLookActor actor, out string reason)
    {
        actor = default;
        if (!CodeUnchanged(out reason)) return false;
        try
        {
            var player = Utilities.GetPlayerFromSlot(slot);
            if (player is not { IsValid: true } || player.Slot != slot || player.PlayerPawn.Value is not { IsValid: true } pawn ||
                pawn.Bot is not { } bot || bot.Handle == 0)
            { reason = "look_actor_missing"; return false; }
            var eye = bot.EyePosition;
            var weapon = pawn.WeaponServices?.ActiveWeapon.Value?.DesignerName ?? "";
            bool handoff = player.ControllingBot || player.HasBeenControlledByPlayerThisRound ||
                bot.IsEnemyVisible || bot.IsAttacking || bot.IsAimingAtEnemy || pawn.BlindUntilTime > Server.CurrentTime || pawn.IsDefusing ||
                weapon.Contains("grenade", StringComparison.Ordinal) || weapon.Contains("flashbang", StringComparison.Ordinal) ||
                weapon.Contains("molotov", StringComparison.Ordinal) || weapon.Contains("c4", StringComparison.Ordinal);
            actor = new(slot, pawn.EntityHandle.Raw, bot.Handle, pawn.Health, eye.X, eye.Y, eye.Z, handoff);
            reason = ""; return true;
        }
        catch (Exception ex) { reason = "look_actor_check_failed:" + ex.GetType().Name; return false; }
    }

    bool ITacticalLookApi.TryRequest(nint bot, out TacticalLookRequest request, out string reason)
    {
        request = default;
        if (bot == 0) { reason = "look_request_unavailable"; return false; }
        if (!CodeUnchanged(out reason)) return false;
        int state = Marshal.ReadInt32(bot + RequestStateOffset);
        if (state is < 0 or > 2) { reason = "look_request_state_not_audited"; return false; }
        request = new(state, Marshal.ReadInt32(bot + 0x536c), Marshal.ReadIntPtr(bot + DescriptorOffset),
            ReadFloat(bot + 0x5360), ReadFloat(bot + 0x5364), ReadFloat(bot + 0x5368));
        reason = ""; return true;
    }

    bool ITacticalLookApi.TrySet(nint bot, nint descriptor, float x, float y, float z, out string reason)
    {
        var api = (ITacticalLookApi)this;
        if (!api.TryRequest(bot, out var before, out reason)) return false;
        if (before.State != 0 && before.Priority > RequestPriority)
        { reason = "native_look_priority_retained"; return false; }
        var vector = Marshal.AllocHGlobal(12);
        try
        {
            Marshal.WriteInt32(vector, BitConverter.SingleToInt32Bits(x));
            Marshal.WriteInt32(vector, 4, BitConverter.SingleToInt32Bits(y));
            Marshal.WriteInt32(vector, 8, BitConverter.SingleToInt32Bits(z));
            _look(bot, descriptor, vector, RequestPriority, RequestDuration, 0, 5f, 0);
        }
        finally { Marshal.FreeHGlobal(vector); }
        if (!api.TryRequest(bot, out var after, out reason)) return false;
        // Native near-vector comparison uses 10.0 (2ddaad -> rdata1782e0c).
        // An accepted same/near spot can retain the OLD vector and state while
        // assigning our descriptor. Do not mistake that documented path for
        // rejection; the lease reads back the actual native target below.
        if (after.State == 0 || after.Priority != RequestPriority || after.Descriptor != descriptor ||
            Math.Abs(after.X - x) > 10 || Math.Abs(after.Y - y) > 10 || Math.Abs(after.Z - z) > 10 ||
            !float.IsFinite(after.X) || !float.IsFinite(after.Y) || !float.IsFinite(after.Z))
        { reason = "native_look_request_not_accepted"; return false; }
        reason = "native_look_request_accepted_alignment_unverified"; return true;
    }

    bool ITacticalLookApi.TryClearOwned(nint bot, nint descriptor, out string reason)
    {
        if (bot == 0 || descriptor == 0) { reason = "look_clear_unavailable"; return false; }
        if (!CodeUnchanged(out reason)) return false;
        if (Marshal.ReadIntPtr(bot + DescriptorOffset) != descriptor)
        { reason = "look_other_owner_retained"; return true; }
        // EXACT native ClearLookAt writes (2fc1d6 and 2fc1dc), but gated by
        // our descriptor. No call/yield is allowed between compare and writes.
        Marshal.WriteInt32(bot + RequestStateOffset, 0);
        Marshal.WriteIntPtr(bot + DescriptorOffset, 0);
        reason = "look_owned_request_released"; return true;
    }

    private bool CodeUnchanged(out string reason)
    {
        if (Environment.CurrentManagedThreadId != _gameThread)
        { reason = "look_game_thread_required"; return false; }
        if (_dependencyGuard is not null && !_dependencyGuard.VerifyIfDue(out reason)) return false;
        if (!MatchMemory(_module + Evidence.LookRva, _code[0], _scratch[0]))
        { reason = Difference("SetLookAt", Evidence.LookRva, _code[0], _scratch[0]); return false; }
        if (!MatchMemory(_module + Evidence.ClearRva, _code[1], _scratch[1]))
        { reason = Difference("ClearLookAt", Evidence.ClearRva, _code[1], _scratch[1]); return false; }
        if (!MatchMemory(_module + Evidence.ConsumerRva, _code[2], _scratch[2]))
        { reason = Difference("LookConsumer", Evidence.ConsumerRva, _code[2], _scratch[2]); return false; }
        reason = ""; return true;
    }

    internal sealed class Lease(ITacticalLookApi api, int slot, uint expectedPawn, int initialHealth, nint descriptor)
    {
        private nint _bot;
        private float? _unalignedSince;
        private float _targetX, _targetY, _targetHeight, _markerX, _markerY;
        private bool _released;
        internal bool Active { get; private set; }
        internal bool Aligned { get; private set; }

        internal bool Update(CCSPlayerController player, float lookX, float lookY, out string reason)
        {
            if (!player.IsValid || player.Slot != slot)
            { Release(); reason = "look_actor_identity_changed"; return false; }
            return Update(lookX, lookY, out reason);
        }

        internal bool Update(float lookX, float lookY, out string reason)
        {
            if (_released) { reason = "look_lease_released"; return false; }
            if (!api.TryActor(slot, out var actor, out reason)) { CancelOwn(); return false; }
            if (actor.Slot != slot || actor.Pawn != expectedPawn || actor.Bot == 0 || (_bot != 0 && _bot != actor.Bot))
            { Release(); reason = "look_actor_identity_changed"; return false; }
            _bot = actor.Bot;
            if (actor.Health <= 0 || actor.Health < initialHealth || actor.NativeHandoff)
            { CancelOwn(); reason = "native_look_combat_or_objective_retained"; return false; }
            if (!float.IsFinite(lookX) || !float.IsFinite(lookY) || !float.IsFinite(actor.EyeX) ||
                !float.IsFinite(actor.EyeY) || !float.IsFinite(actor.EyeZ) || !float.IsFinite(api.Now))
            { CancelOwn(); reason = "look_target_not_finite"; return false; }
            float dx = lookX - actor.EyeX, dy = lookY - actor.EyeY;
            float distanceSquared = dx * dx + dy * dy;
            if (!float.IsFinite(distanceSquared))
            { CancelOwn(); reason = "look_target_not_finite"; return false; }
            if (distanceSquared < 16 * 16)
            { CancelOwn(); reason = "look_horizontal_target_too_close"; return false; }
            if (!api.TryRequest(_bot, out var request, out reason)) { CancelOwn(); return false; }
            // Sub-unit animation/eye bob must not restart a native look request
            // every tick. A meaningful posture/height change gets a new target
            // at the ACTUAL eye Z; tiny changes retain the native smooth aim.
            bool own = request.State != 0 && request.Descriptor == descriptor && SameSpot(request, _targetX, _targetY, _targetHeight)
                && Math.Abs(lookX - _markerX) <= .01f && Math.Abs(lookY - _markerY) <= .01f
                && Math.Abs(actor.EyeZ - _targetHeight) <= 4;
            if (!own)
            {
                _unalignedSince = api.Now;
                Aligned = false;
                // SetLookAt retains an existing near-vector (10 units), which
                // includes small but meaningful posture changes. End only our
                // own old request before changing its target, so native state
                // 0 copies the requested vector instead of retaining stale Z.
                if (request.Descriptor == descriptor && !api.TryClearOwned(_bot, descriptor, out reason))
                { CancelOwn(); return false; }
                // look_at is a 2D direction marker, not a target floor height.
                // Project along that horizontal ray at actual eye Z. A long
                // ray also prevents tiny eye bob from producing steep pitch
                // when a map marker happens to be close to the standing bot.
                float scale = 1024 / MathF.Sqrt(distanceSquared);
                float targetX = actor.EyeX + dx * scale, targetY = actor.EyeY + dy * scale;
                if (!api.TrySet(_bot, descriptor, targetX, targetY, actor.EyeZ, out reason))
                { CancelOwn(); return false; }
                if (!api.TryRequest(_bot, out var accepted, out reason) || accepted.State == 0 || accepted.Descriptor != descriptor)
                { CancelOwn(); reason = "native_look_request_changed_after_submission"; return false; }
                _targetX = accepted.X; _targetY = accepted.Y; _targetHeight = accepted.Z;
                _markerX = lookX; _markerY = lookY;
                Active = true; Aligned = accepted.State == 2;
                if (Aligned) _unalignedSince = null;
                reason = Aligned ? "native_look_request_aligned" : "native_look_request_accepted_alignment_unverified";
                return true;
            }
            Active = true; Aligned = request.State == 2;
            if (Aligned) _unalignedSince = null;
            else
            {
                _unalignedSince ??= api.Now;
                if (api.Now < _unalignedSince || api.Now - _unalignedSince >= AlignmentTimeout)
                { Release(); reason = "look_alignment_timeout"; return false; }
            }
            reason = Aligned ? "native_look_request_aligned" : "native_look_request_pending_alignment";
            return true;
        }

        internal void Release()
        {
            if (_released) return;
            CancelOwn(); _released = true;
        }

        private void CancelOwn()
        {
            // Never dereference the cached Bot after pawn replacement. A dead
            // but still-valid same pawn is readable and its OWN request may be
            // cleared. A controlled same pawn is likewise cleared immediately.
            if (_bot != 0 && api.TryActor(slot, out var actor, out _) && actor.Slot == slot &&
                actor.Pawn == expectedPawn && actor.Bot == _bot)
                api.TryClearOwned(_bot, descriptor, out _);
            Active = Aligned = false; _unalignedSince = null;
        }
    }

    private static bool SameSpot(TacticalLookRequest request, float x, float y, float z)
        => Math.Abs(request.X - x) <= .01f && Math.Abs(request.Y - y) <= .01f && Math.Abs(request.Z - z) <= .01f;
    private static float ReadFloat(nint address) => BitConverter.Int32BitsToSingle(Marshal.ReadInt32(address));
    private static string Difference(string name, int rva, byte[] expected, byte[] observed)
    {
        int index = 0;
        while (index < Math.Min(expected.Length, observed.Length) && expected[index] == observed[index]) index++;
        int count = Math.Min(8, Math.Min(expected.Length, observed.Length) - index);
        return $"look_loaded_code_mismatch:{name}:rva=0x{rva + index:X}:expected={Convert.ToHexString(expected.AsSpan(index, count))}" +
            $":observed={Convert.ToHexString(observed.AsSpan(index, count))}";
    }
    private static bool MatchMemory(nint address, byte[] expected, byte[] observed)
    {
        Marshal.Copy(address, observed, 0, observed.Length);
        return observed.AsSpan().SequenceEqual(expected);
    }
    private static int UniqueIndex(ReadOnlySpan<byte> bytes, ReadOnlySpan<byte> pattern)
    {
        int first = bytes.IndexOf(pattern);
        return first < 0 || bytes[(first + 1)..].IndexOf(pattern) >= 0 ? -1 : first;
    }
    private static int Read32(byte[] bytes, int offset) => BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(offset, 4));
    private static ushort Read16(byte[] bytes, int offset) => BinaryPrimitives.ReadUInt16LittleEndian(bytes.AsSpan(offset, 2));
}
