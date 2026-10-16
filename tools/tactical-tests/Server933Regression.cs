using System.Buffers.Binary;
using System.Security.Cryptography;
using CareerMatch;

// File bytes only: neither maps executable pages nor invokes any game code.
internal static class Server933Regression
{
    internal static void Run(string path, Func<byte[], (bool Passed, string Reason)> audit)
    {
        int checks = 0;
        void Check(bool value, string name) { checks++; if (!value) throw new Exception("2000933 regression: " + name); }
        var file = File.ReadAllBytes(path);
        Check(Convert.ToHexString(SHA256.HashData(file)) == TacticalServer933.Sha256, "exact reviewed game file");
        int I32(int offset) => BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(offset, 4));
        int nt = I32(0x3c);
        int sections = BinaryPrimitives.ReadUInt16LittleEndian(file.AsSpan(nt + 6, 2));
        int table = nt + 24 + BinaryPrimitives.ReadUInt16LittleEndian(file.AsSpan(nt + 20, 2));
        long imageBase = BinaryPrimitives.ReadInt64LittleEndian(file.AsSpan(nt + 48, 8));
        int Offset(int rva)
        {
            for (int i = 0; i < sections; i++)
            {
                int row = table + i * 40, start = I32(row + 12), size = I32(row + 16);
                if (rva >= start && rva < start + size) return I32(row + 20) + rva - start;
            }
            throw new Exception("unmapped test RVA");
        }
        long Pointer(int rva) => BinaryPrimitives.ReadInt64LittleEndian(file.AsSpan(Offset(rva), 8)) - imageBase;
        int LeaTarget(int rva) => rva + 7 + I32(Offset(rva) + 3);
        int CallTarget(int rva)
        {
            Check(file[Offset(rva)] == 0xe8, $"direct call opcode at 0x{rva:X}");
            return rva + 5 + I32(Offset(rva) + 1);
        }

        Check(Convert.ToHexString(SHA256.HashData(file.AsSpan(Offset(0x2aed40), 2342))) ==
            "BACCEA02C5D112F64172FA68C59A170185C18850A52B1CB5CEA56D4624D34AF3", "complete reviewed constructor");
        Check(LeaTarget(0x2aee6f) == TacticalServer933.BotVtable, "constructor publishes bot vtable");
        Check(LeaTarget(0x2aef03) == 0x17a8778, "constructor publishes Idle vtable");
        Check(LeaTarget(0x2aef53) == TacticalServer933.MoveToVtable, "constructor publishes MoveTo vtable");
        Check(Pointer(TacticalServer933.BotVtable + 0x28) == 0x2dc780, "Run slot");
        Check(Pointer(TacticalServer933.BotVtable + 0x30) == 0x2e76d0, "Walk slot");
        Check(Pointer(TacticalServer933.MoveToVtable) == 0x32a300, "MoveTo OnEnter");
        Check(Pointer(TacticalServer933.MoveToVtable + 8) == 0x330b60, "MoveTo OnUpdate");
        Check(Pointer(TacticalServer933.MoveToVtable + 16) == 0x32a7c0, "MoveTo OnExit");
        Check(Pointer(TacticalServer930.MoveToVtable) != 0x32a300, "930 MoveTo table must not be used");
        Check(CallTarget(0x32a313) == 0x2ccb20, "EnterWeaponQuery resolved by call target, not its ambiguous normalized pattern");
        Check(CallTarget(0x32a31f) == 0x2cd960, "EnterTimeQuery call target");
        Check(CallTarget(0x32a32b) == 0x2cb670, "EnterSceneQuery call target");
        Check(CallTarget(0x32a381) == 0x2bac70, "ComputePath call target");
        Check(BitConverter.Int32BitsToSingle(I32(Offset(0x177de0c))) == 10, "look near-target tolerance");
        Check(Pointer(0x1d99470) == 0x178c3a0 && file.AsSpan(Offset(0x178c3a0), 7).SequenceEqual("m_pBot\0"u8)
            && I32(Offset(0x1d99470) + 0x10) == 0x14f8, "current pawn schema, not old fixed m_pBot offset");
        Check(file.AsSpan(Offset(0x330b60) + 0x627, 16).SequenceEqual(Convert.FromHexString("4038BB001500007415488B8BF8140000")),
            "MoveToUpdate pawn fields agree with current schema; bot-owned offsets are unchanged");

        foreach (int rva in new[] { 0x2aed40, 0x2aee6f, 0x2aef53, 0x2bac70, 0x2ddce0, 0x2dd710,
            0x2fbea0, 0x2e6a00, 0x330b60, 0x33118a, 0x32a313, 0x17a89c0, 0x17a8808,
            0x177de0c, 0x1d99480, 0x178c3a0 })
        {
            int offset = Offset(rva); file[offset] ^= 1;
            Check(!audit(file).Passed, $"changed function/constructor/vtable/schema refuses 0x{rva:X}");
            file[offset] ^= 1;
        }
        file[table + 2 * 40 + 8] ^= 1;
        Check(!audit(file).Passed, "unreviewed data layout refuses");
        file[table + 2 * 40 + 8] ^= 1;
        Check(audit(file).Passed, "only intact reviewed profile passes again");
        Console.WriteLine($"{checks} CS2 2000933 layout/exact-file checks passed; no game code executed.");
    }
}
