using System.Runtime.InteropServices;
using System.Security.Cryptography;

namespace CareerMatch;

internal interface ITacticalHoldApi
{
    int IsLocked(int slot, int kind);
    long StartMove(int slot);
    int UpdateMove(int slot, long token);
    int CancelMove(int slot, long token);
    long Suppress(int slot, ulong mask);
    int CancelSuppression(int slot, long token);
}

// Borrow an already loaded ABI20/22 module; no hooks/module loads or raw
// position/velocity/view writes. Its existing zero movement token removes the
// native movement buttons too. Native perception/aim/actions remain running.
internal sealed class TacticalHoldControls : ITacticalTravelApi
{
    // v0.7.0 (451c7ba) is ABI22, not ABI20. Its six hold exports retain
    // their Cdecl argument widths and 0-success/-1-failure conventions.
    // Evidence: upstream src/bridge/exports.cpp at that exact commit and the
    // installed PE's GetVersion stub (B8 16 00 00 00 C3). Never accept a newer
    // ABI merely because its numeric version is greater.
    private static readonly Dictionary<string, int> AuditedModules = new(StringComparer.Ordinal)
    {
        ["8645168D4BB6A55CE8A8AC4246BCE394496E4EECF4F56C2F2A7932A98EB75D61"] = 22,
        ["E3D0424CE253B11CFFA714B03D53580EA2F176C0A53D4FA06FF1B9DE4C46DCE8"] = 20,
    };
    internal static int AuditedAbiForHash(string hash) => AuditedModules.TryGetValue(hash, out var version)
        ? version : throw new InvalidDataException("hold_module_not_audited:" + hash);
    internal static int ValidateAbi(string hash, int actual)
    {
        var expected = AuditedAbiForHash(hash);
        if (actual != expected)
            throw new InvalidDataException($"hold_ABI_mismatch:expected={expected},actual={actual}");
        return actual;
    }
    internal static readonly string[] RequiredExports = ["GetVersion", "IsLocked",
        "StartUsercmdMovement", "UpdateUsercmdMovement", "CancelUsercmdMovement",
        "StartUsercmdSuppression", "CancelUsercmdSuppression", "InjectUsercmd", "CancelUsercmdInjection"];
    internal static int CompatibleAbi(string hash, int actual, IEnumerable<string> exports)
    {
        var missing = RequiredExports.Except(exports, StringComparer.Ordinal).ToArray();
        if (missing.Length > 0) throw new InvalidDataException("hold_missing_exports:" + string.Join(",", missing));
        if (AuditedModules.ContainsKey(hash)) return ValidateAbi(hash, actual);
        // These exact ABI versions use the same Cdecl widths and token/return
        // conventions. A rebuild need not have the release's file hash. A new
        // ABI is NOT assumed compatible and never receives movement calls.
        if (actual is not (20 or 22)) throw new InvalidDataException($"hold_unsupported_ABI:{actual};supported=20,22");
        return actual;
    }
    [DllImport("kernel32.dll", EntryPoint = "GetModuleHandleW", CharSet = CharSet.Unicode)]
    private static extern nint GetModuleHandle(string path);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int VersionFn();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int LockedFn(int slot, int kind);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate long MoveFn(int slot, float forward, float left);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int UpdateFn(int slot, long token, float forward, float left);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int CancelFn(int slot, long token);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate long SuppressFn(int slot, ulong mask);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate long InjectFn(int slot, ulong mask, int durationMs);
    private readonly LockedFn _locked;
    private readonly MoveFn _move;
    private readonly UpdateFn _update;
    private readonly CancelFn _cancel, _cancelSuppression;
    private readonly SuppressFn _suppress;
    private readonly InjectFn _inject;
    private readonly CancelFn _cancelInjection;
    private readonly int _abi;
    private TacticalHoldControls(nint module, string hash)
    {
        T Export<T>(string name) where T : Delegate => Marshal.GetDelegateForFunctionPointer<T>(
            NativeLibrary.GetExport(module, "BotController_" + name));
        var exports = RequiredExports.Where(name => NativeLibrary.TryGetExport(module, "BotController_" + name, out _)).ToArray();
        if (!exports.Contains("GetVersion")) throw new InvalidDataException("hold_missing_exports:GetVersion");
        _abi = CompatibleAbi(hash, Export<VersionFn>("GetVersion")(), exports);
        _locked = Export<LockedFn>("IsLocked");
        _move = Export<MoveFn>("StartUsercmdMovement"); _update = Export<UpdateFn>("UpdateUsercmdMovement");
        _cancel = Export<CancelFn>("CancelUsercmdMovement");
        _suppress = Export<SuppressFn>("StartUsercmdSuppression");
        _cancelSuppression = Export<CancelFn>("CancelUsercmdSuppression");
        // Same Cdecl signatures in the pinned ABI20 and ABI22 sources. Travel
        // only uses SPEED; no movement vector, aim, jump or fire injection.
        _inject = Export<InjectFn>("InjectUsercmd");
        _cancelInjection = Export<CancelFn>("CancelUsercmdInjection");
    }
    internal static bool TryBind(string path, out TacticalHoldControls? controls, out string reason)
    {
        controls = null;
        try
        {
            if (!OperatingSystem.IsWindows() || IntPtr.Size != 8) throw new InvalidDataException("hold_windows_x64_only");
            var full = Path.GetFullPath(path);
            using var stream = File.OpenRead(full);
            var hash = Convert.ToHexString(SHA256.HashData(stream));
            var module = GetModuleHandle(full);
            if (module == 0) throw new InvalidDataException("hold_module_not_loaded");
            controls = new(module, hash); reason = $"ABI{controls._abi}_exports_bound:sha256={hash[..12]}"; return true;
        }
        catch (Exception ex) { reason = ex.Message; return false; }
    }

    int ITacticalHoldApi.IsLocked(int slot, int kind) => _locked(slot, kind);
    long ITacticalHoldApi.StartMove(int slot) => _move(slot, 0, 0);
    int ITacticalHoldApi.UpdateMove(int slot, long token) => _update(slot, token, 0, 0);
    int ITacticalHoldApi.CancelMove(int slot, long token) => _cancel(slot, token);
    long ITacticalHoldApi.Suppress(int slot, ulong mask) => _suppress(slot, mask);
    int ITacticalHoldApi.CancelSuppression(int slot, long token) => _cancelSuppression(slot, token);
    long ITacticalTravelApi.Inject(int slot, ulong mask, int durationMs) => _inject(slot, mask, durationMs);
    int ITacticalTravelApi.CancelInjection(int slot, long token) => _cancelInjection(slot, token);

    internal sealed class Lease(ITacticalHoldApi api, int slot)
    {
        private long _movement, _suppression;
        internal bool Active => _movement > 0;
        internal void Keep()
        {
            if (!Active)
            {
                if (Enumerable.Range(0, 3).Any(kind => api.IsLocked(slot, kind) != 0))
                    throw new InvalidOperationException("hold_other_owner");
                _movement = api.StartMove(slot);
                if (_movement <= 0) { _movement = 0; throw new InvalidOperationException("hold_token_rejected"); }
                try
                {
                    // Prevent native jump/duck while waiting; never suppress firing,
                    // reload or utility buttons, nor lock aim/decisions.
                    _suppression = api.Suppress(slot, (1UL << 1) | (1UL << 2) | (1UL << 16));
                    if (_suppression <= 0) throw new InvalidOperationException("hold_buttons_rejected");
                }
                catch { Release(); throw; }
            }
            if (api.UpdateMove(slot, _movement) != 0) throw new InvalidOperationException("hold_update_rejected");
        }
        internal void Release()
        {
            // Token cancellation is safe even after pawn identity is gone: it
            // only deletes this lease's entry, never applies input to a new body.
            var movement = _movement; var suppression = _suppression;
            _movement = _suppression = 0;
            try { if (movement > 0 && api.CancelMove(slot, movement) != 0) throw new InvalidOperationException("hold_cancel_rejected"); }
            finally { if (suppression > 0 && api.CancelSuppression(slot, suppression) != 0) throw new InvalidOperationException("hold_suppression_cancel_rejected"); }
        }
    }
    internal Lease CreateLease(int slot) => new(this, slot);

    // A distinct, short-lived opening token: suppress only JUMP while the new
    // path replaces the previous native opening. Never stop movement/aim/fire.
    // It is released after launch, not retained for the whole route, so NAV may
    // still jump a genuine obstacle later.
    internal sealed class OpeningLease(ITacticalHoldApi api, int slot)
    {
        private long _token;
        internal bool Active => _token > 0;
        internal void Start()
        {
            if (Active) return;
            _token = api.Suppress(slot, 1UL << 1);
            if (_token <= 0) { _token = 0; throw new InvalidOperationException("opening_jump_token_rejected"); }
        }
        internal void Release()
        {
            var token = _token; _token = 0;
            if (token > 0 && api.CancelSuppression(slot, token) != 0)
                throw new InvalidOperationException("opening_jump_cancel_rejected");
        }
    }
    internal OpeningLease CreateOpeningLease(int slot) => new(this, slot);
}
