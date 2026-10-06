using CareerMatch;

internal static class AvatarDeliveryTests
{
    public static void Run()
    {
        var count = 0;
        void Check(bool okay, string message) { ++count; if (!okay) throw new Exception(message); }
        var state = new AvatarDelivery();
        int sends = 0;
        bool Send() { ++sends; return true; }
        state.Update(1, "a", "hash1", 100, 0, false, 100, false, Send);
        Check(sends == 0, "Do not send before BotHider owns slot");
        state.Update(1, "a", "hash1", 100, 2, true, 200, false, Send);
        Check(sends == 0 && state.Entries.Single().Status == "identity_mismatch", "Do not publish to another identity");
        state.Update(1, "a", "hash1", 100, 4, true, 100, true, Send);
        Check(sends == 1 && state.Entries.Single().Status == "queued", "Old applied avatar is not our acknowledgement");
        state.Update(1, "a", "hash1", 100, 4.5, true, 100, true, Send);
        Check(state.Entries.Single().Status == "queued", "Wait until a later check for native acknowledgement");
        state.Update(1, "a", "hash1", 100, 6, true, 100, true, Send);
        Check(sends == 1 && state.Entries.Single().Status == "applied", "Native acknowledgement completes delivery");
        state.Update(1, "a", "hash1", 100, 8, true, 100, true, Send);
        Check(sends == 1, "No PNG IO or resend for confirmed avatar");
        state.Update(1, "a", "hash1", 100, 10, true, 100, false, Send);
        Check(sends == 2, "Lost native override is reapplied");
        state.Update(1, "a", "hash2", 100, 11, true, 100, true, Send);
        Check(sends == 3 && state.Entries.Single().Attempts == 1, "Logo change gets a new delivery");
        state.Forget(1);
        Check(!state.Entries.Any(), "Disconnect clears slot ownership");
        for (int i = 0; i < 30; ++i) state.Update(1, "b", "hash", 101, i * 2, true, 101, false, Send);
        Check(sends == 8 && state.Entries.Single().Status == "not_acknowledged", "Unacknowledged requests have at most five retries");
        state.Reset();
        Check(!state.Entries.Any(), "Map/session reset clears old delivery");
        var api = new FakeAvatarApi();
        var bridge = new BotAvatarBridge(api, typeof(IFakeAvatarApi));
        Check(bridge.Managed(1) && bridge.SteamId(1) == 101 && !bridge.Applied(1), "Shared interface read delegates bind");
        Check(bridge.Send(1, "safe.png") && bridge.Applied(1) && api.Path == "safe.png", "Shared interface write delegate binds explicit implementation");
        Check(ReferenceEquals(api, bridge.Provider), "Provider identity supports hot reload");
        Console.WriteLine($"{count} avatar delivery checks passed.");
    }

    private interface IFakeAvatarApi
    {
        bool IsManagedBot(int slot);
        ulong GetBotSteamId(int slot);
        bool HasBotAvatar(int slot);
        bool SetBotAvatar(int slot, string path);
    }
    private sealed class FakeAvatarApi : IFakeAvatarApi
    {
        public string Path = "";
        bool IFakeAvatarApi.IsManagedBot(int slot) => slot == 1;
        ulong IFakeAvatarApi.GetBotSteamId(int slot) => 101;
        bool IFakeAvatarApi.HasBotAvatar(int slot) => Path != "";
        bool IFakeAvatarApi.SetBotAvatar(int slot, string path) { Path = path; return true; }
    }
}
