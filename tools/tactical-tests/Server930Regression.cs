using System.Buffers.Binary;
using System.Security.Cryptography;
using CareerMatch;

// File bytes only: validates the newly reviewed mapping as well as refusals.
internal static class Server930Regression
{
    internal static void Run(string path, Func<byte[], (bool Passed, string Reason)> audit)
    {
        int checks = 0;
        void Check(bool value, string name) { checks++; if (!value) throw new Exception("2000930 regression: " + name); }
        var file = File.ReadAllBytes(path);
        Check(Convert.ToHexString(SHA256.HashData(file)) == TacticalServer930.Sha256, "exact reviewed game file");
        int I32(int offset) => BinaryPrimitives.ReadInt32LittleEndian(file.AsSpan(offset, 4));
        int nt = I32(0x3c), table = nt + 24 + 240;
        int Offset(int rva)
        {
            for (int i = 0; i < 5; i++)
            {
                int row = table + i * 40, start = I32(row + 12), size = I32(row + 16);
                if (rva >= start && rva < start + size) return I32(row + 20) + rva - start;
            }
            throw new Exception("unmapped test RVA");
        }
        long Pointer(int rva) => BinaryPrimitives.ReadInt64LittleEndian(file.AsSpan(Offset(rva), 8)) - 0x180000000;
        int LeaTarget(int rva) => rva + 7 + I32(Offset(rva) + 3);
        Check(LeaTarget(0x2af9ef) == TacticalServer930.BotVtable, "constructor publishes new bot vtable");
        Check(LeaTarget(0x2afa83) == 0x17a8738, "constructor publishes new Idle vtable");
        Check(LeaTarget(0x2afad3) == TacticalServer930.MoveToVtable, "constructor publishes new MoveTo vtable");
        Check(Pointer(TacticalServer930.BotVtable + 0x28) == 0x2dd300, "Run slot");
        Check(Pointer(TacticalServer930.BotVtable + 0x30) == 0x2e8250, "Walk slot");
        Check(Pointer(TacticalServer930.MoveToVtable) == 0x32ae80, "MoveTo OnEnter");
        Check(Pointer(TacticalServer930.MoveToVtable + 8) == 0x3316e0, "MoveTo OnUpdate");
        Check(Pointer(TacticalServer930.MoveToVtable + 16) == 0x32b340, "MoveTo OnExit");
        Check(Pointer(0x17ad7b8) != 0x32ae80, "old MoveTo table must not be used");
        Check(BitConverter.Int32BitsToSingle(I32(Offset(0x177de0c))) == 10, "look near-target tolerance");
        foreach (int rva in new[] { 0x2af8c0, 0x2bb7f0, 0x2de860, 0x2de290, 0x2fca20,
            0x2e7580, 0x3316e0, 0x17a8980, 0x17a87c8, 0x177de0c })
        {
            int offset = Offset(rva); file[offset] ^= 1;
            Check(!audit(file).Passed, $"changed function/constructor/vtable/constant refuses 0x{rva:X}");
            file[offset] ^= 1;
        }
        file[table + 2 * 40 + 8] ^= 1;
        Check(!audit(file).Passed, "unreviewed data layout refuses");
        file[table + 2 * 40 + 8] ^= 1;
        Check(audit(file).Passed, "only intact reviewed profile passes again");
        Console.WriteLine($"{checks} CS2 2000930 layout/exact-file checks passed; no game code executed.");
    }
}
