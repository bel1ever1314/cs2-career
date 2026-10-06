using System.Security.Cryptography;
using System.Runtime.InteropServices;
using CareerMatch;

// File/synthetic bytes only: no live module, pointer, hook or movement call.
internal static class TacticalContinuationRegression
{
    internal static void Run(string serverPath)
    {
        var checks = 0;
        void Check(bool value, string name) { checks++; if (!value) throw new Exception("Continuation regression: "+name); }
        byte[][] Copy(byte[][] code) => code.Select(body => body.ToArray()).ToArray();
        const int update = 5, offset = 0x9cb;
        var patch = Convert.FromHexString("909090909090");
        Check(TacticalNativeNavigation.TryAuditCode(serverPath, out var audit, out var file, out var why), "current file: "+why);
        Check(audit is not null && TacticalNativeNavigation.IsAuditedServerHash(audit.Sha256) && file is { Length: 9 }, "exact disk build and all nine bodies");
        var native = file!;
        if (audit!.Sha256 == TacticalServer927.Sha256)
        {
            // Read/copy file bytes as DATA. Do not load server.dll or call it.
            var disk = File.ReadAllBytes(serverPath);
            nint image = Marshal.AllocHGlobal(audit.ImageSize);
            try
            {
                foreach (var (rva, length) in new[] { (0x2dcab0, 8), (0x2e7a00, 93) })
                    Marshal.Copy(disk, 1024 + rva - 0x1000, image + rva, length);
                foreach (var (slot, target) in new[] { (audit.BotVtableRva + 0x28, 0x2dcab0),
                    (audit.BotVtableRva + 0x30, 0x2e7a00), (audit.MoveToVtableRva, 0x32a630),
                    (audit.MoveToVtableRva + 8, 0x330e90), (audit.MoveToVtableRva + 16, 0x32aaf0) })
                    Marshal.WriteIntPtr(image + slot, image + target);
                Check(TacticalNativeNavigation.LayoutMatches(image, image + audit.BotVtableRva, audit), "current mapped layout accepts ASLR pointers");
                Check(!TacticalNativeNavigation.LayoutMatches(image, image + 0x17ad970, audit), "old bot vtable rejects before dereference");
                Marshal.WriteIntPtr(image + audit.MoveToVtableRva + 8, image + 0x330e91);
                Check(!TacticalNativeNavigation.LayoutMatches(image, image + audit.BotVtableRva, audit), "foreign state callback rejects");
                Marshal.WriteIntPtr(image + audit.MoveToVtableRva + 8, image + 0x330e90);
                Marshal.WriteByte(image + 0x2dcab0, 0);
                Check(!TacticalNativeNavigation.LayoutMatches(image, image + audit.BotVtableRva, audit), "changed gait code rejects");
            }
            finally { Marshal.FreeHGlobal(image); }
        }
        Check(native[update].Length == 3133 && native[update].AsSpan(offset, 6).SequenceEqual(Convert.FromHexString("0F84D9000000")),
            "exact reviewed MoveToUpdate and original conditional branch");
        var patched = Copy(native); patch.CopyTo(patched[update], offset);
        var patchedHash = audit!.Sha256 == TacticalServer927.Sha256
            ? "102483B4190FB69DD908FEC4AB628DE93763DCED94B7A46E69D112FDB65D1E3D"
            : "38A734AD8D704385F9C67D1597114D6BDA2BC93622F630C87A14047D322E61F4";
        Check(Convert.ToHexString(SHA256.HashData(patched[update])) == patchedHash,
            "independently audited installed BotAI full-body variant");
        foreach (var (observed, name) in new[] { (native, "native_unpatched"), (patched, "BotAI_DefuseBomb_SkipIsVisibleCheck") })
        {
            Check(TacticalNativeNavigation.TrySelectContinuationSnapshots(native, observed, out var selected, out var variant, out why)
                && variant == name && selected is not null, "bind known complete variant: "+why);
            Check(TacticalNativeNavigation.TryValidateContinuationSnapshot(selected!, observed, out _), "frozen variant accepts same bytes");
            for (var body = 0; body < native.Length; body++)
                Check(!ReferenceEquals(selected![body], native[body]) && !ReferenceEquals(selected[body], observed[body])
                    && selected[body].AsSpan().SequenceEqual(observed[body]), "independent complete snapshot "+body);
            var otherVariant = name == "native_unpatched" ? patched : native;
            Check(!TacticalNativeNavigation.TryValidateContinuationSnapshot(selected!, otherVariant, out why)
                && why.StartsWith("loaded_continuation_code_changed:MoveToUpdate:rva=0x33185B:"), "bound variant cannot change/reselect");

            // Every single byte in MoveToUpdate is significant, even outside
            // the known patch. No wide mask, prefix-only or almost-patch match.
            for (var index = 0; index < observed[update].Length; index++)
            {
                var foreign = Copy(observed); foreign[update][index] ^= 1;
                Check(!TacticalNativeNavigation.TrySelectContinuationSnapshots(native, foreign, out var rejected, out _, out why)
                    && rejected is null && why.StartsWith("loaded_continuation_code_mismatch:MoveToUpdate:"), "foreign bind byte "+index);
                Check(!TacticalNativeNavigation.TryValidateContinuationSnapshot(selected!, foreign, out why)
                    && why.StartsWith("loaded_continuation_code_changed:MoveToUpdate:"), "foreign runtime byte "+index);
            }
            for (var body = 0; body < observed.Length; body++)
            {
                var foreign = Copy(observed); foreign[body][foreign[body].Length/2] ^= 1;
                Check(!TacticalNativeNavigation.TrySelectContinuationSnapshots(native, foreign, out _, out _, out _), "other body bind protected "+body);
                Check(!TacticalNativeNavigation.TryValidateContinuationSnapshot(selected!, foreign, out _), "other body runtime protected "+body);
            }
        }
        foreach (var (start, count) in new[] { (offset, 5), (offset, 7), (offset-1, 6), (offset+1, 6) })
        {
            var foreign = Copy(native); Array.Fill(foreign[update], (byte)0x90, start, count);
            Check(!TacticalNativeNavigation.TrySelectContinuationSnapshots(native, foreign, out _, out _, out _), "only exact six-byte patch at exact RVA");
        }
        var unreviewed = Copy(native); unreviewed[0][0] ^= 1;
        Check(!TacticalNativeNavigation.TrySelectContinuationSnapshots(unreviewed, unreviewed, out _, out _, out why)
            && why == "navigation_continuation_snapshot_not_audited:ComputePath", "modified audited baseline cannot self-authorize");
        var ownObserved = Copy(patched); var ownAudited = Copy(native);
        Check(TacticalNativeNavigation.TrySelectContinuationSnapshots(ownAudited, ownObserved, out var owned, out _, out _), "owned copy starts");
        ownObserved[update][0] ^= 1; ownAudited[0][0] ^= 1;
        Check(TacticalNativeNavigation.TryValidateContinuationSnapshot(owned!, patched, out _), "later caller-array mutation cannot corrupt frozen copy");
        var truncated = Copy(native); truncated[update] = truncated[update][..^1];
        var extended = Copy(native); extended[update] = [..extended[update], 0];
        var nullBody = Copy(native); nullBody[0] = null!;
        foreach (var invalid in new[] { truncated, extended, nullBody, native[..^1], native.Concat(new[] { native[0] }).ToArray(), null! })
        {
            Check(!TacticalNativeNavigation.TrySelectContinuationSnapshots(native, invalid, out _, out _, out _), "bad observed shape rejects");
            Check(!TacticalNativeNavigation.TrySelectContinuationSnapshots(invalid, native, out _, out _, out _), "bad audited shape rejects");
            Check(!TacticalNativeNavigation.TryValidateContinuationSnapshot(native, invalid, out _), "bad live shape rejects");
            Check(!TacticalNativeNavigation.TryValidateContinuationSnapshot(invalid, native, out _), "bad frozen shape rejects");
        }
        Console.WriteLine($"{checks} continuation exact-variant/frozen-snapshot checks passed; no server module loaded, no native movement executed.");
    }
}
