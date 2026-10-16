using BotAimImprover;

// No game DLLs, native hooks, or CounterStrikeSharp runtime are loaded.
try
{
    int checks = 0;
    foreach (short expected in new short[] { 0x1510, 0x1518, 0x14F8, 0x17E0 })
    {
        int calls = 0;
        int result = PawnBotSchema.Resolve((className, fieldName) =>
        {
            calls++;
            if (className != "CCSPlayerPawn" || fieldName != "m_pBot")
                throw new Exception("Wrong schema identity.");
            return expected;
        });
        if (result != expected || calls != 1)
            throw new Exception("Schema resolution must query once per plugin load.");
        checks++;
    }
    foreach (short missing in new short[] { 0, -1 })
    {
        bool rejected = false;
        try { PawnBotSchema.Resolve((_, _) => missing); }
        catch (InvalidOperationException) { rejected = true; }
        if (!rejected) throw new Exception("Missing schema offset was accepted.");
        checks++;
    }
    var failure = new InvalidOperationException("Schema is unavailable.");
    bool propagated = false;
    try { PawnBotSchema.Resolve((_, _) => throw failure); }
    catch (InvalidOperationException error) { propagated = ReferenceEquals(error, failure); }
    if (!propagated) throw new Exception("Schema failure must not silently use old offsets.");
    checks++;
    Console.WriteLine($"PASS {checks} schema resolver cases; no game runtime loaded.");
    return 0;
}
catch (Exception error)
{
    Console.Error.WriteLine(error);
    return 1;
}
