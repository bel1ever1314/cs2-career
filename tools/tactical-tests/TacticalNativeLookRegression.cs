using CareerMatch;

// Standalone entry point. Compile THIS source (not the navigation Program.cs)
// with TacticalNativeLook.cs and the CSS API reference. It does not bind any
// live module, allocate a native descriptor, or execute a server.dll function.
if (args.Length != 1) throw new ArgumentException("Pass server.dll for a file-only look audit.");
TacticalNativeLookRegression.Run(args[0]);

internal static class TacticalNativeLookRegression
{
    private static int _checks;
    private static void Check(bool condition, string name)
    {
        if (!condition) throw new Exception("Look regression failed: " + name);
        _checks++;
    }
    private static (FakeApi Api, TacticalNativeLook.Lease Lease) Fresh()
    {
        var api = new FakeApi();
        return (api, new(api, 7, 1234, 100, (nint)0x5555));
    }

    internal static void Run(string serverPath)
    {
        Check(TacticalNativeLook.TryAuditFile(serverPath, out var audit, out var reason), "current file audit: " + reason);
        Check(TacticalNativeLook.IsAuditedServerHash(TacticalNativeLook.PreviousServerSha256), "previous reviewed build retained");
        Check(!TacticalNativeLook.IsAuditedServerHash(new string('0', 64)) &&
            !TacticalNativeLook.IsAuditedServerHash(TacticalNativeLook.AuditedServerSha256.ToLowerInvariant()),
            "unreviewed and non-exact build hashes refuse");
        Check(audit is { LookRva: 0x2dda40, ClearRva: 0x2fc1d0, ConsumerRva: 0x2e6d30,
            LookBytes: 347, ClearBytes: 20, ConsumerBytes: 1500 } && audit.Sha256 == TacticalNativeLook.AuditedServerSha256,
            "complete function identities");
        Check(!TacticalNativeLook.TryAuditFile(serverPath + ".missing", out _, out _), "missing server refuses");
        // The already-present CSS managed assembly is an unaudited file. This
        // test creates/deletes no fixture and does not load that assembly here.
        Check(!TacticalNativeLook.TryAuditFile(typeof(CounterStrikeSharp.API.Core.CCSBot).Assembly.Location,
            out _, out var wrongReason) && wrongReason.StartsWith("look_audit_failed:"), "different PE/profile refuses");
        Check(TacticalNativeLook.TryAuditCode(serverPath, out _, out var windows, out _), "file audit exposes complete synthetic windows");
        var nativeConsumer = windows![2];
        const int cosOffset = 0x2e729b - 0x2e6d30, sinOffset = 0x2e72c8 - 0x2e6d30;
        var zeroDrift = Convert.FromHexString("0F57C09090");
        string[] variants = ["native_unpatched", "BotAI_COS_ZeroDrift", "BotAI_SIN_ZeroDrift", "BotAI_COS_SIN_ZeroDrift"];
        for (int mask = 0; mask < 4; mask++)
        {
            var observed = nativeConsumer.ToArray();
            if ((mask & 1) != 0) zeroDrift.CopyTo(observed, cosOffset);
            if ((mask & 2) != 0) zeroDrift.CopyTo(observed, sinOffset);
            Check(TacticalNativeLook.TrySelectConsumerSnapshot(nativeConsumer, observed, out var accepted,
                out var variant, out _) && variant == variants[mask] && accepted!.AsSpan().SequenceEqual(observed),
                "only exact complete known consumer variant " + variants[mask]);
            byte saved = accepted![0]; observed[0] ^= 1;
            Check(accepted[0] == saved && !ReferenceEquals(accepted, observed), "bound snapshot owns an independent complete copy");
        }
        {
            var unexpected = nativeConsumer.ToArray(); zeroDrift.CopyTo(unexpected, cosOffset); zeroDrift.CopyTo(unexpected, sinOffset);
            unexpected[0x100] ^= 1;
            Check(!TacticalNativeLook.TrySelectConsumerSnapshot(nativeConsumer, unexpected, out _, out _, out var why) &&
                why.StartsWith("look_loaded_code_mismatch:LookConsumer:rva=0x2E6E30:"), "unknown byte outside known calls rejects with exact first RVA");
        }
        {
            var unexpected = nativeConsumer.ToArray(); zeroDrift.CopyTo(unexpected, cosOffset); unexpected[cosOffset + 4] = 0xcc;
            Check(!TacticalNativeLook.TrySelectConsumerSnapshot(nativeConsumer, unexpected, out _, out _, out _),
                "almost-known five-byte patch is not admitted");
            Check(!TacticalNativeLook.TrySelectConsumerSnapshot(nativeConsumer, nativeConsumer[..^1], out _, out _, out _),
                "incomplete consumer snapshot rejects");
            var wrongBefore = nativeConsumer.ToArray(); wrongBefore[cosOffset] ^= 1;
            Check(!TacticalNativeLook.TrySelectConsumerSnapshot(wrongBefore, wrongBefore, out _, out _, out _),
                "unreviewed native before-call bytes reject");
        }

        {
            var (api, lease) = Fresh();
            Check(lease.Update(100, 0, out _) && api.SetCalls == 1 && lease.Active && !lease.Aligned, "initial native request");
            Check(Math.Abs(api.Request.X - 1024) < .01f && Math.Abs(api.Request.Y) < .01f && api.Request.Z == 64,
                "2D marker becomes horizontal eye-height ray");
            api.Time = .2f;
            Check(lease.Update(100, 0, out _) && api.SetCalls == 1, "same pending goal does not resubmit");
            api.Request = api.Request with { State = 2 }; api.Time = 1;
            Check(lease.Update(100, 0, out _) && lease.Aligned && api.SetCalls == 1, "native alignment observed without angle write");
            api.Actor = api.Actor with { EyeZ = 64.5f }; api.Time = 1.1f;
            Check(lease.Update(100, 0, out _) && api.SetCalls == 1, "small eye bob does not restart native smoothing");
            api.Time = 20;
            Check(lease.Update(100, 0, out _) && api.SetCalls == 1, "aligned owned request remains stable");
            lease.Release(); lease.Release();
            Check(api.ClearWrites == 1 && api.Request.State == 0 && api.Request.Descriptor == 0 && !lease.Active,
                "release is owned and idempotent");
            Check(!lease.Update(100, 0, out var why) && why == "look_lease_released" && api.SetCalls == 1,
                "released lease cannot reacquire");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.Time = TacticalNativeLook.AlignmentTimeout;
            Check(!lease.Update(100, 0, out var why) && why == "look_alignment_timeout" && api.ClearWrites == 1 && api.SetCalls == 1,
                "pending native state has explicit deadline");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.Time = .5f;
            Check(lease.Update(0, 100, out _) && api.SetCalls == 2 && Math.Abs(api.Request.X) < .01f &&
                Math.Abs(api.Request.Y - 1024) < .01f, "different direction issues one new request");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.Actor = api.Actor with { EyeZ = 84 };
            Check(lease.Update(100, 0, out _) && api.SetCalls == 2 && api.Request.Z == 84, "posture change uses actual current eye height");
        }
        {
            var (api, lease) = Fresh(); api.NativeNearSpot = true;
            api.Request = new(2, 0, (nint)0x7777, 1029, 0, 68);
            Check(lease.Update(100, 0, out _) && lease.Aligned && api.Request.X == 1029 && api.Request.Z == 68,
                "native near-spot acceptance retains its state and actual vector");
            api.Time = .1f;
            Check(lease.Update(100, 0, out _) && api.SetCalls == 1 && api.ClearWrites == 0,
                "readback de-duplicates accepted near-spot request");
            api.Actor = api.Actor with { EyeZ = 73 }; api.Time = .2f;
            Check(lease.Update(100, 0, out _) && api.SetCalls == 2 && api.ClearWrites == 1 && api.Request.Z == 73,
                "owned posture change clears only itself before native vector replacement");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.Actor = api.Actor with { NativeHandoff = true };
            Check(!lease.Update(100, 0, out var why) && why == "native_look_combat_or_objective_retained" &&
                api.ClearWrites == 1 && api.SetCalls == 1, "enemy/attack/flash/utility/control handoff releases look");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.Actor = api.Actor with { Health = 99 };
            Check(!lease.Update(100, 0, out _) && api.ClearWrites == 1 && api.SetCalls == 1, "hurt immediately releases request");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.Actor = api.Actor with { Health = 0 }; lease.Release();
            Check(api.ClearWrites == 1, "same valid dead pawn may clear own request");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.Actor = api.Actor with { Pawn = 5678 };
            Check(!lease.Update(100, 0, out _) && api.ClearWrites == 0 && api.ClearCalls == 0 && api.SetCalls == 1,
                "pawn replacement does not touch cached old Bot");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.Actor = api.Actor with { Bot = (nint)0x9999 }; lease.Release();
            Check(api.ClearWrites == 0 && api.ClearCalls == 0, "same pawn but different Bot pointer is not cleared");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.Actor = api.Actor with { Slot = 8 }; lease.Release();
            Check(api.ClearWrites == 0 && api.ClearCalls == 0, "slot identity changed refuses clear");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.Request = api.Request with { Descriptor = (nint)0x7777, Priority = 2 }; lease.Release();
            Check(api.ClearCalls == 1 && api.ClearWrites == 0 && api.Request.Descriptor == (nint)0x7777,
                "other owner is never cancelled");
        }
        {
            var (api, lease) = Fresh(); api.Request = new(1, 2, (nint)0x7777, 0, 0, 64);
            Check(!lease.Update(100, 0, out var why) && why == "native_look_priority_retained" && api.ClearWrites == 0 &&
                api.Request.Descriptor == (nint)0x7777, "higher native priority is preserved");
        }
        {
            var (api, lease) = Fresh(); api.Request = new(1, 0, (nint)0x7777, 0, 0, 64);
            Check(lease.Update(100, 0, out _) && api.Request.Descriptor == (nint)0x5555 &&
                api.Request.Priority == 1, "hold priority exceeds ordinary native route look");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.ActorAvailable = false; lease.Release();
            Check(api.ClearCalls == 0 && api.ClearWrites == 0, "disconnect does not dereference cached body");
        }
        {
            var (api, lease) = Fresh(); lease.Update(100, 0, out _);
            api.CodeValid = false;
            Check(!lease.Update(100, 0, out var why) && why == "look_loaded_code_changed" && api.ClearWrites == 0,
                "changed loaded code fails closed even for clear");
        }
        {
            var (api, lease) = Fresh();
            Check(!lease.Update(float.NaN, 0, out _) && api.SetCalls == 0, "non-finite marker rejected");
            Check(!lease.Update(0, 0, out _) && api.SetCalls == 0, "zero heading rejected");
            Check(!lease.Update(float.MaxValue, 0, out _) && api.SetCalls == 0, "overflowing heading rejected");
        }
        FeatureProfileRegression.Run(serverPath, observation: true, bytes =>
        {
            bool passed = TacticalNativeLook.TryAuditBytes(bytes, out _, out _, out var why);
            return (passed, why);
        });
        Console.WriteLine($"{_checks} native-look file/lease checks passed. No server module loaded or executed; live aim is not tested.");
    }

    private sealed class FakeApi : ITacticalLookApi
    {
        internal float Time;
        internal bool ActorAvailable = true, CodeValid = true, NativeNearSpot;
        internal TacticalLookActor Actor = new(7, 1234, (nint)0x4242, 100, 0, 0, 64, false);
        internal TacticalLookRequest Request;
        internal int SetCalls, ClearCalls, ClearWrites;
        public float Now => Time;
        public bool TryActor(int slot, out TacticalLookActor actor, out string reason)
        {
            actor = Actor;
            reason = !CodeValid ? "look_loaded_code_changed" : !ActorAvailable ? "look_actor_missing" : "";
            return CodeValid && ActorAvailable;
        }
        public bool TryRequest(nint bot, out TacticalLookRequest request, out string reason)
        {
            request = Request; reason = CodeValid ? "" : "look_loaded_code_changed"; return CodeValid;
        }
        public bool TrySet(nint bot, nint descriptor, float x, float y, float z, out string reason)
        {
            SetCalls++;
            if (Request.State != 0 && Request.Priority > TacticalNativeLook.RequestPriority)
            { reason = "native_look_priority_retained"; return false; }
            bool near = NativeNearSpot && Request.State != 0 && Math.Abs(Request.X - x) <= 10 &&
                Math.Abs(Request.Y - y) <= 10 && Math.Abs(Request.Z - z) <= 10;
            Request = near ? Request with { Priority = TacticalNativeLook.RequestPriority, Descriptor = descriptor }
                : new(1, TacticalNativeLook.RequestPriority, descriptor, x, y, z);
            reason = "native_look_request_accepted_alignment_unverified"; return true;
        }
        public bool TryClearOwned(nint bot, nint descriptor, out string reason)
        {
            ClearCalls++;
            if (!CodeValid) { reason = "look_loaded_code_changed"; return false; }
            if (Request.Descriptor == descriptor)
            { Request = Request with { State = 0, Descriptor = 0 }; ClearWrites++; }
            reason = ""; return true;
        }
    }
}
