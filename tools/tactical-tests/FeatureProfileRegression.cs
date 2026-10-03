using System.Buffers.Binary;
using System.Runtime.InteropServices;
using CareerMatch;

internal static class FeatureProfileRegression
{
    internal static void Run(string serverPath, bool observation, Func<byte[], (bool Passed, string Reason)> audit)
    {
        int checks = 0;
        void Check(bool value, string name) { checks++; if (!value) throw new Exception("Feature profile regression: " + name); }
        bool Audit(byte[] bytes, out string why)
        { var result = audit(bytes); why = result.Reason; return result.Passed; }
        var file = File.ReadAllBytes(serverPath);
        var fixture = new byte[file.Length + 1]; file.CopyTo(fixture, 0);
        Check(Audit(fixture, out var reason), "unrelated overlay keeps complete profile: " + reason);
        fixture[1024] ^= 1;
        Check(Audit(fixture, out reason), "unrelated .text byte keeps complete profile: " + reason);
        fixture[1024] ^= 1;
        int nt = BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(0x3c, 4));
        fixture[nt + 8] ^= 1;
        Check(Audit(fixture, out reason), "COFF timestamp is provenance, not feature ABI: " + reason);
        fixture[nt + 8] ^= 1;
        foreach (var body in TacticalFeatureAudit.ProfileBodies(observation))
        {
            int offset = 1024 + body.Rva - 4096 + body.Length / 2;
            fixture[offset] ^= 1;
            Check(!Audit(fixture, out reason) && reason.Contains("feature_complete_body_mismatch:"),
                $"complete primary/helper/chunk protected at 0x{body.Rva:X}: " + reason);
            fixture[offset] ^= 1;
        }
        // Constant and vtable content, mapping fields and loader directories
        // matter even when every guarded instruction is still byte-identical.
        foreach (int rva in new[] { 0x1782e0c, 0x17ad7b8, 0x17ad998 })
        {
            int offset = 24537088 + rva - 24543232;
            fixture[offset] ^= 1;
            Check(!Audit(fixture, out reason) && reason.Contains("feature_static_section_mismatch:.rdata"),
                "constant/vtable change rejected: " + reason);
            fixture[offset] ^= 1;
        }
        int optional = nt + 24, sectionTable = optional + 240;
        foreach (int offset in new[] { 0, nt + 22, optional + 16, optional + 24, optional + 32,
            optional + 56, sectionTable + 12, optional + 112 + 8 })
        {
            fixture[offset] ^= 1;
            Check(!Audit(fixture, out _), "mapping/loader/RVA migration requires a reviewed new profile");
            fixture[offset] ^= 1;
        }

        // A synthetic mapped image exercises binding and frozen extra code /
        // relocated vtable guards. It is allocated as data, never executable.
        var snapshot = TacticalFeatureAudit.Audit(fixture, observation);
        var image = new byte[39284736];
        foreach (var section in new[] { (4096, 1024, 24536064), (24543232, 24537088, 6490624) })
            fixture.AsSpan(section.Item2, section.Item3).CopyTo(image.AsSpan(section.Item1));
        nint buffer = Marshal.AllocHGlobal(image.Length);
        try
        {
            foreach (var slot in TacticalFeatureAudit.ProfileVtableSlots(observation))
            {
                long preferred = BinaryPrimitives.ReadInt64LittleEndian(image.AsSpan(slot, 8));
                BinaryPrimitives.WriteInt64LittleEndian(image.AsSpan(slot, 8), preferred - 0x180000000 + buffer.ToInt64());
            }
            Marshal.Copy(image, 0, buffer, image.Length);
            Check(snapshot.TryBind(buffer, observation, out var guard, out reason), "synthetic loaded profile binds: " + reason);
            var helper = TacticalFeatureAudit.ProfileBodies(observation).First();
            Marshal.WriteByte(buffer + helper.Rva, (byte)(image[helper.Rva] ^ 1));
            Check(!guard!.Verify(out reason) && reason.StartsWith("feature_loaded_dependency_mismatch:"),
                "loaded helper mutation rejects before native use");
            Marshal.WriteByte(buffer + helper.Rva, image[helper.Rva]);
            Check(!guard.VerifyIfDue(out _), "dependency failure remains latched after bytes are restored");
            Check(snapshot.TryBind(buffer, observation, out guard, out reason), "new synthetic bind uses independently checked baseline");
            int dataRva = observation ? 0x1782e0c : 0x17ad998;
            byte original = Marshal.ReadByte(buffer + dataRva);
            Marshal.WriteByte(buffer + dataRva, (byte)(original ^ 1));
            Check(!guard!.Verify(out reason), "loaded constant/vtable mutation rejects");
        }
        finally { Marshal.FreeHGlobal(buffer); }
        Console.WriteLine($"{checks} bounded feature profile checks passed; game DLL never loaded or executed.");
    }
}
