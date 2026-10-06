using System.Reflection;
using System.Text.Json;
using CounterStrikeSharp.API.Core.Capabilities;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    private readonly AvatarDelivery _avatarDelivery = new();
    private BotAvatarBridge? _avatarBridge;
    private object? _avatarCapability;
    private MethodInfo? _avatarGet;
    private Type? _avatarContract;
    private string _avatarError = "";
    private string _avatarSnapshot = "";
    private bool _avatarApiReady;

    private BotAvatarBridge? ResolveAvatarBridge()
    {
        _avatarApiReady = false;
        try
        {
            if (_avatarCapability is null)
            {
                _avatarContract = AppDomain.CurrentDomain.GetAssemblies()
                    .Where(a => a.GetName().Name == "BotHiderApi")
                    .Select(a => a.GetType("BotHiderApi.IBotHiderApi")).FirstOrDefault(t => t is not null);
                if (_avatarContract is null) { _avatarError = "BotHiderApi not loaded"; return null; }
                // PluginCapability<T> stores providers per T, so object is NOT
                // interchangeable with the provider's real shared interface.
                var type = typeof(PluginCapability<>).MakeGenericType(_avatarContract);
                _avatarCapability = Activator.CreateInstance(type, "bothider:api");
                _avatarGet = type.GetMethod("Get");
            }
            var provider = _avatarGet!.Invoke(_avatarCapability, null);
            if (provider is null) { _avatarError = "BotHider provider unavailable"; return null; }
            if (_avatarBridge is null || !ReferenceEquals(_avatarBridge.Provider, provider))
            {
                _avatarBridge = new BotAvatarBridge(provider, _avatarContract!);
                _avatarDelivery.Reset();
            }
            _avatarError = "";
            _avatarApiReady = true;
            return _avatarBridge;
        }
        catch (Exception ex)
        {
            _avatarError = (ex.InnerException ?? ex).Message;
            return null;
        }
    }

    private void ApplyBotAvatar(int slot, BotConfig bot, BotAvatarBridge bridge)
    {
        try
        {
            _avatarDelivery.Update(slot, bot.PlayerId, bot.AvatarHash, bot.SteamId,
                Environment.TickCount64 / 1000.0, bridge.Managed(slot), bridge.SteamId(slot), bridge.Applied(slot),
                () => {
                    if (!TryValidatedAvatarPath(bot, out var path, out var error))
                    { _avatarError = error; return false; }
                    return bridge.Send(slot, path);
                });
        }
        catch (Exception ex) { _avatarError = (ex.InnerException ?? ex).Message; }
    }

    private void WriteAvatarStatus()
    {
        var snapshot = JsonSerializer.Serialize(new { nonce = _request?.Nonce, active = _request?.Active ?? false,
            contract_error = _contractError, api_ready = _avatarApiReady,
            error = _avatarError, bots = _avatarDelivery.Entries });
        if (snapshot == _avatarSnapshot) return;
        try
        {
            var path = Path.Combine(ModuleDirectory, "avatar_status.json");
            File.WriteAllText(path + ".tmp", snapshot);
            File.Move(path + ".tmp", path, true);
            _avatarSnapshot = snapshot;
        }
        catch (IOException ex) { Logger.LogWarning("CareerMatch avatar status: {Error}", ex.Message); }
    }
}
