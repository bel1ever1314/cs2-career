using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text;
using System.Security.Cryptography;
using System.Diagnostics;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Core.Attributes;
using CounterStrikeSharp.API.Modules.Timers;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

public sealed class MatchRequest
{
    [JsonPropertyName("schema_version")]
    public int SchemaVersion { get; set; }
    [JsonPropertyName("active")]
    public bool Active { get; set; }

    [JsonPropertyName("map")]
    public string Map { get; set; } = "de_dust2";

    [JsonPropertyName("human_team")]
    public string HumanTeam { get; set; } = "ct";

    [JsonPropertyName("ct")]
    public TeamConfig Ct { get; set; } = new();

    [JsonPropertyName("t")]
    public TeamConfig T { get; set; } = new();

    [JsonPropertyName("difficulty")]
    public string Difficulty { get; set; } = "";

    [JsonPropertyName("nonce")]
    public string Nonce { get; set; } = "";

    [JsonPropertyName("human_player_id")]
    public string HumanPlayerId { get; set; } = "";

    [JsonPropertyName("player")]
    public string Player { get; set; } = "";

    [JsonPropertyName("bot_identity")]
    public string BotIdentity { get; set; } = "player";

    [JsonPropertyName("bot_profile")]
    public BotProfileContract BotProfile { get; set; } = new();
}

public sealed class BotProfileContract
{
    [JsonPropertyName("nonce")] public string Nonce { get; set; } = "";
    [JsonPropertyName("count")] public int Count { get; set; }
    [JsonPropertyName("difficulty")] public string Difficulty { get; set; } = "";
    [JsonPropertyName("vpk_sha256")] public string VpkSha256 { get; set; } = "";
    [JsonPropertyName("manifest_hash")] public string ManifestHash { get; set; } = "";
    [JsonPropertyName("short_hash")] public string ShortHash { get; set; } = "";
    [JsonPropertyName("difficulty_model")] public string DifficultyModel { get; set; } = "";
    [JsonPropertyName("preset_source_hash")] public string PresetSourceHash { get; set; } = "";
    [JsonPropertyName("template_hash")] public string TemplateHash { get; set; } = "";
}

public sealed class BotConfig
{
    [JsonPropertyName("player_id")] public string PlayerId { get; set; } = "";
    [JsonPropertyName("profile_name")] public string ProfileName { get; set; } = "";
    [JsonPropertyName("display_name")] public string DisplayName { get; set; } = "";
    [JsonPropertyName("steam_id")] public ulong SteamId { get; set; }
    [JsonPropertyName("side")] public string Side { get; set; } = "";
    [JsonPropertyName("profile_hash")] public string ProfileHash { get; set; } = "";
    [JsonPropertyName("avatar_path")] public string AvatarPath { get; set; } = "";
    [JsonPropertyName("avatar_hash")] public string AvatarHash { get; set; } = "";
    [JsonPropertyName("avatar_kind")] public string AvatarKind { get; set; } = "default";
}

public sealed class TeamConfig
{
    [JsonPropertyName("team_id")]
    public string TeamId { get; set; } = "";

    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("logo")]
    public string Logo { get; set; } = "";

    [JsonPropertyName("players")]
    public List<BotConfig> Players { get; set; } = [];
}

public sealed class PlayerResult
{
    [JsonPropertyName("player_id")]
    public string PlayerId { get; set; } = "";
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("team")]
    public string Team { get; set; } = "";

    [JsonPropertyName("is_bot")]
    public bool IsBot { get; set; }

    [JsonPropertyName("kills")]
    public int Kills { get; set; }

    [JsonPropertyName("deaths")]
    public int Deaths { get; set; }

    [JsonPropertyName("assists")]
    public int Assists { get; set; }

    [JsonPropertyName("damage")]
    public int Damage { get; set; }

    [JsonPropertyName("score")]
    public int Score { get; set; }

    [JsonPropertyName("adr")] public double Adr { get; set; }
    [JsonPropertyName("kast")] public double Kast { get; set; }
    [JsonPropertyName("opening_kills")] public int OpeningKills { get; set; }
    [JsonPropertyName("opening_deaths")] public int OpeningDeaths { get; set; }
    [JsonPropertyName("survived_rounds")] public int SurvivedRounds { get; set; }
    [JsonPropertyName("traded_deaths")] public int TradedDeaths { get; set; }
    [JsonPropertyName("stats_source")] public string StatsSource { get; set; } = "event_ledger";
}

public sealed class MatchResult
{
    [JsonPropertyName("schema_version")]
    public int SchemaVersion { get; set; } = 2;

    [JsonPropertyName("request_nonce")]
    public string RequestNonce { get; set; } = "";
    [JsonPropertyName("status")]
    public string Status { get; set; } = "pending";

    [JsonPropertyName("map")]
    public string Map { get; set; } = "";

    [JsonPropertyName("winner")]
    public string Winner { get; set; } = "";

    [JsonPropertyName("ct_score")]
    public int CtScore { get; set; }

    [JsonPropertyName("t_score")]
    public int TScore { get; set; }

    [JsonPropertyName("ct_name")]
    public string CtName { get; set; } = "";

    [JsonPropertyName("t_name")]
    public string TName { get; set; } = "";

    [JsonPropertyName("ended_at")]
    public string EndedAt { get; set; } = "";

    [JsonPropertyName("players")]
    public List<PlayerResult> Players { get; set; } = [];

    [JsonPropertyName("complete")]
    public bool Complete { get; set; }

    [JsonPropertyName("validation_error")]
    public string ValidationError { get; set; } = "";
    [JsonPropertyName("identity_bindings")]
    public Dictionary<int, string> IdentityBindings { get; set; } = [];
    [JsonPropertyName("stat_identity_policy")]
    public string StatIdentityPolicy { get; set; } = "original_pawn_owner";
    [JsonPropertyName("identity_resolver_version")]
    public string IdentityResolverVersion { get; set; } = "controller_link_v3";
    [JsonPropertyName("score_identity_policy")]
    public string ScoreIdentityPolicy { get; set; } = "opening_roster_side";
    [JsonPropertyName("takeover_events")]
    public List<TakeoverRecord> TakeoverEvents { get; set; } = [];
}

internal sealed class LedgerRow
{
    public string PlayerId { get; init; } = "";
    public string Name { get; set; } = "";
    public string Team { get; set; } = "";
    public bool IsBot { get; init; }
    public int Kills, Deaths, Assists, Damage, OpeningKills, OpeningDeaths;
    public int SurvivedRounds, KastRounds, TradedDeaths;
    public bool RoundKill, RoundAssist, RoundDead, RoundTraded;
    public bool UsedMatchStatsFallback;
    public LedgerRow Copy() => new()
    {
        PlayerId = PlayerId, Name = Name, Team = Team, IsBot = IsBot,
        Kills = Kills, Deaths = Deaths, Assists = Assists, Damage = Damage,
        OpeningKills = OpeningKills, OpeningDeaths = OpeningDeaths,
        SurvivedRounds = SurvivedRounds, KastRounds = KastRounds,
        TradedDeaths = TradedDeaths, RoundKill = RoundKill,
        RoundAssist = RoundAssist, RoundDead = RoundDead, RoundTraded = RoundTraded,
        UsedMatchStatsFallback = UsedMatchStatsFallback,
    };
}

internal sealed record PendingTrade(string VictimId, string KillerId, string VictimTeam, double At);
public sealed record TakeoverRecord(
    [property: JsonPropertyName("round")] int Round,
    [property: JsonPropertyName("controller_id")] string ControllerId,
    [property: JsonPropertyName("player_id")] string PlayerId);

[MinimumApiVersion(304)]
public sealed partial class CareerMatchPlugin : BasePlugin
{
    public override string ModuleName => "CareerMatch";
    public override string ModuleVersion => "1.5.0-takeover.4";
    public override string ModuleAuthor => "CS2 Career Sim";
    public override string ModuleDescription =>
        "Auto-setup named career bots, force human side, export score + box score.";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    // Warmup long enough to join a side and read the scoreboard.
    private const int WarmupSeconds = 30;

    private MatchRequest? _request;
    private bool _setupDone;
    private readonly RosterReadiness _rosterReadiness = new();
    private bool _scoreCleared;
    private bool _resultWritten;
    private bool _announcedDifficulty;
    private int _liveRounds;
    private int _bestKillTotal;
    private int _lastWrittenKills = -1;
    private int _lastWrittenCt = -1;
    private int _lastWrittenT = -1;
    private string _lastWrittenStatus = "";
    private List<PlayerResult> _bestPlayers = [];
    private string _endedAt = "";
    private string _requestPath = "";
    private string _resultPath = "";
    private string _bestPath = "";
    private string _sessionNonce = "";
    private MatchResult? _bestDump;
    private readonly IdentityBindings _identities = new();
    private readonly ActorOwnership _actors = new();
    private readonly List<TakeoverRecord> _takeovers = [];
    private Dictionary<int, string> _slotIds => _identities.Slots;
    private readonly Dictionary<string, LedgerRow> _ledger = [];
    private readonly List<PendingTrade> _pendingTrades = [];
    private bool _roundLive;
    private bool _openingRecorded;
    private readonly SessionHealth _health = new();
    private string _contractError { get => _health.ContractError; set => _health.ContractError = value; }
    private readonly Dictionary<string, LedgerRow> _roundSnapshot = [];
    private int _scoreAtRoundStart;
    private readonly HashSet<string> _disconnected = [];
    private string _rosterNotice = "";
    private string _roundStatisticsError = "";
    private int _roundTakeoverCount;

    private static string SafeCommandText(string? value)
    {
        var clean = new string((value ?? "").Where(ch => ch >= ' ' && ch is not '"' and not '\\' and not ';').ToArray());
        return clean.Trim();
    }

    private bool TryValidatedAvatarPath(BotConfig bot, out string commandPath, out string error)
    {
        commandPath = "";
        error = "";
        try
        {
            var root = Path.GetFullPath(Path.Combine(ModuleDirectory, "avatars"))
                .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
                + Path.DirectorySeparatorChar;
            var full = Path.GetFullPath(bot.AvatarPath ?? "");
            if (!full.StartsWith(root, StringComparison.OrdinalIgnoreCase))
            {
                error = "头像不在 CareerMatch 安全目录";
                return false;
            }
            var info = new FileInfo(full);
            if (!info.Exists || info.Length <= 0 || info.Length > 16 * 1024)
            {
                error = "头像缺失或超过 16 KiB";
                return false;
            }
            var payload = File.ReadAllBytes(full);
            ReadOnlySpan<byte> png = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
            if (!payload.AsSpan().StartsWith(png))
            {
                error = "头像不是 PNG";
                return false;
            }
            var digest = Convert.ToHexString(SHA256.HashData(payload)).ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(bot.AvatarHash)
                || !digest.Equals(bot.AvatarHash, StringComparison.OrdinalIgnoreCase))
            {
                error = "头像 SHA-256 不一致";
                return false;
            }
            commandPath = full.Replace('\\', '/');
            if (commandPath.IndexOfAny(['"', ';', '\r', '\n']) >= 0)
            {
                error = "头像路径包含不安全字符";
                commandPath = "";
                return false;
            }
            return true;
        }
        catch (Exception ex)
        {
            error = "头像校验异常: " + ex.Message;
            return false;
        }
    }

    public override void Load(bool hotReload)
    {
        _requestPath = Path.Combine(ModuleDirectory, "match_request.json");
        _resultPath = Path.Combine(ModuleDirectory, "match_result.json");
        _bestPath = Path.Combine(ModuleDirectory, "match_result.best.json");
        _request = ReadRequest();
        _sessionNonce = _request?.Nonce ?? "";

        RegisterEventHandler<EventPlayerHurt>(OnPlayerHurt, HookMode.Pre);
        RegisterEventHandler<EventPlayerDeath>(OnPlayerDeath, HookMode.Pre);
        RegisterEventHandler<EventBotTakeover>(OnBotTakeover);
        RegisterEventHandler<EventGrenadeThrown>(OnGrenadeThrown);
        RegisterEventHandler<EventPlayerBlind>(OnPlayerBlind);

        RegisterEventHandler<EventCsWinPanelMatch>(OnMatchEnd);
        RegisterEventHandler<EventRoundEnd>(OnRoundEnd);
        RegisterEventHandler<EventRoundStart>(OnRoundStart);
        RegisterEventHandler<EventRoundFreezeEnd>(OnFreezeEnd);
        RegisterEventHandler<EventPlayerConnectFull>(OnPlayerConnect);
        RegisterEventHandler<EventPlayerDisconnect>(OnPlayerDisconnect);
        RegisterEventHandler<EventWarmupEnd>(OnWarmupEnd);
        RegisterListener<Listeners.OnMapStart>(OnMapStart);
        AddTimer(1.0f, CheckWarmupRoster, TimerFlags.REPEAT);
        AddTimer(1.0f, RefreshDisplayNames, TimerFlags.REPEAT);
        AddTimer(12.0f, TickSnapshot, TimerFlags.REPEAT);
    }

    private void CheckWarmupRoster()
    {
        if (!_setupDone || _request is not { Active: true } || !InWarmup()) return;
        BindPlayerSlots();
        var ready = _slotIds.Count == 10 && _slotIds.Values.Distinct().Count() == 10
            && AllSlots().Count(p => p.Team == CsTeam.CounterTerrorist) == 5
            && AllSlots().Count(p => p.Team == CsTeam.Terrorist) == 5
            && string.IsNullOrEmpty(_contractError);
        Server.ExecuteCommand($"mp_warmup_pausetimer {(ready ? 0 : 1)}");
        var notice = ready ? "十人身份已确认，准备开赛。"
            : $"等待十人身份和 5 对 5 阵容确认（已绑定 {_slotIds.Count}/10），暖身计时已暂停。{_contractError}";
        if (notice != _rosterNotice)
        {
            _rosterNotice = notice;
            Server.PrintToChatAll($" \x04CareerMatch：{notice}\x01");
        }
    }

    private HookResult OnPlayerConnect(EventPlayerConnectFull @event, GameEventInfo info)
    {
        // Only pin the human during warmup. After half, CS2 swaps sides;
        // pulling them back to the opening CT/T is the "keep swapping" bug.
        AddTimer(1.2f, ApplySideDuringWarmup);
        AddTimer(3.0f, ApplySideDuringWarmup);
        return HookResult.Continue;
    }

    private void OnMapStart(string mapName)
    {
        var incoming = ReadRequest();
        var nonce = incoming?.Nonce ?? "";
        var newSession = !string.IsNullOrEmpty(nonce) && nonce != _sessionNonce;
        if (newSession)
        {
            ResetBest();
            _sessionNonce = nonce;
        }

        _request = incoming;
        _setupDone = false;
        _rosterReadiness.Reset();
        _scoreCleared = false;
        _announcedDifficulty = false;
        _rosterNotice = "";
        _liveRounds = 0;
        _roundLive = false;
        _contractError = ValidateContract();
        _health.StatisticsError = "";
        _identities.Clear();
        _actors.NewMatch();
        _openingCtCurrentSide = null;
        _takeovers.Clear();
        _pendingControls.Clear();
        _identityTraceCount = 0;
        _ledger.Clear();
        _pendingTrades.Clear();
        _disconnected.Clear();

        // Quitting the match loads map "<empty>" at 0:0. Never wipe a real score with that.
        if (IsEmptyMap(mapName))
        {
            RestoreBestToDisk();
            return;
        }

        if (_request is not { Active: true })
        {
            return;
        }

        if (!string.IsNullOrEmpty(_contractError))
        {
            Server.PrintToChatAll($" \x02CareerMatch 已阻止开赛：{_contractError}\x01");
            Server.PrintToConsole($"[CareerMatch] contract rejected: {_contractError}");
            Server.ExecuteCommand("bot_kick");
            Server.ExecuteCommand("mp_warmup_pausetimer 1");
            return;
        }

        // Pick the final identity mode before bots are spawned. Switching the
        // fake-client presentation after spawn can leave CS2's scoreboard
        // cache without rows or avatars for the synthetic players.
        Server.ExecuteCommand($"bh_identity_mode {RequestedIdentityMode()}");
        Server.ExecuteCommand("bh_namesource 0");
        StartWarmup();
        AddTimer(2.0f, SetupMatchBots);
        AddTimer(4.5f, SetupMatchBots);
        AddTimer(6.0f, ApplySideDuringWarmup);
        AddTimer(8.0f, ApplySideDuringWarmup);
        AddTimer(10.0f, ClearStolenRounds);
        AddTimer(WarmupSeconds + 3.0f, ReleaseHumanTeam);
    }

    private void ResetBest()
    {
        _resultWritten = false;
        _bestKillTotal = 0;
        _lastWrittenKills = -1;
        _lastWrittenCt = -1;
        _lastWrittenT = -1;
        _lastWrittenStatus = "";
        _bestPlayers = [];
        _bestDump = null;
        _endedAt = "";
        _identities.Clear();
        _ledger.Clear();
        _pendingTrades.Clear();
        _disconnected.Clear();
    }

    private static bool IsEmptyMap(string? mapName)
    {
        var name = (mapName ?? "").Trim();
        return string.IsNullOrEmpty(name)
            || name.Equals("<empty>", StringComparison.OrdinalIgnoreCase)
            || name.Equals("empty", StringComparison.OrdinalIgnoreCase);
    }

    private void TickSnapshot()
    {
        if (IsEmptyMap(Server.MapName))
        {
            RestoreBestToDisk();
            return;
        }

        ApplyBotNames();
        WriteSnapshot(Server.MapName, _resultWritten ? "finished" : "in_progress");
    }

    private void RestoreBestToDisk()
    {
        if (_bestDump is null)
        {
            return;
        }

        WriteJson(_resultPath, _bestDump);
        WriteJson(_bestPath, _bestDump);
    }

    private HookResult OnWarmupEnd(EventWarmupEnd @event, GameEventInfo info)
    {
        ReleaseHumanTeam();
        return HookResult.Continue;
    }

    private static void StartWarmup()
    {
        Server.ExecuteCommand($"mp_warmuptime {WarmupSeconds}");
        Server.ExecuteCommand($"mp_warmuptime_all_players_connected {WarmupSeconds - 10}");
        Server.ExecuteCommand("mp_warmup_pausetimer 0");
        Server.ExecuteCommand("mp_warmup_start");
    }

    private static bool InWarmup()
    {
        foreach (var proxy in Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules"))
        {
            if (proxy.GameRules != null)
            {
                return proxy.GameRules.WarmupPeriod;
            }
        }

        return false;
    }

    private IEnumerable<CCSPlayerController> AllSlots()
    {
        for (var slot = 0; slot < 64; slot++)
        {
            CCSPlayerController? player = null;
            try { player = Utilities.GetPlayerFromSlot(slot); } catch { }
            if (player is { IsValid: true } && !player.IsHLTV)
            {
                yield return player;
            }
        }
    }

    private string ValidateContract()
    {
        if (_request is not { Active: true }) return "";
        var bots = _request.Ct.Players.Concat(_request.T.Players).ToList();
        if (_request.SchemaVersion != 2) return "比赛请求不是 schema v2";
        if (bots.Count != 9 || _request.BotProfile.Count != 9) return "Bot 清单不是 9 人";
        if (bots.Select(x => x.PlayerId).Distinct().Count() != 9) return "player_id 不唯一";
        if (bots.Select(x => x.ProfileName).Distinct().Count() != 9) return "profile_name 不唯一";
        if (bots.Any(x => x.SteamId == 0) || bots.Select(x => x.SteamId).Distinct().Count() != 9)
            return "Bot 合成 SteamID 缺失或不唯一";
        foreach (var bot in bots)
        {
            if (!TryValidatedAvatarPath(bot, out _, out var avatarError))
                return $"{bot.PlayerId} 的安全头像无效: {avatarError}";
        }
        if (_request.Nonce != _request.BotProfile.Nonce) return "VPK nonce 与请求不一致";
        if (_request.Difficulty != _request.BotProfile.Difficulty) return "VPK 难度与请求不一致";
        try
        {
            var root = Path.GetFullPath(Path.Combine(ModuleDirectory, "..", "..", "..", ".."));
            var vpk = Path.Combine(root, "overrides", "botprofile.vpk");
            var manifestPath = Path.Combine(root, "overrides", "botprofile.manifest.json");
            if (!File.Exists(vpk) || !File.Exists(manifestPath)) return "活动 VPK 或清单不存在";
            using var doc = JsonDocument.Parse(File.ReadAllText(manifestPath));
            var node = doc.RootElement;
            if (node.GetProperty("nonce").GetString() != _request.Nonce) return "活动 VPK nonce 不一致";
            if (node.GetProperty("difficulty").GetString() != _request.Difficulty) return "活动 VPK 难度不一致";
            var model = node.TryGetProperty("difficulty_model", out var modelNode) ? modelNode.GetString() ?? "" : "";
            if (model != _request.BotProfile.DifficultyModel) return "活动 VPK 难度模型不一致";
            if (model.Length > 0)
            {
                if (model is not ("bot_improver_base_career_tier_v1" or "bot_improver_career_tuned_v2"))
                    return "不支持的 Bot 难度模型";
                if (node.GetProperty("preset_source_hash").GetString() != _request.BotProfile.PresetSourceHash
                    || node.GetProperty("template_hash").GetString() != _request.BotProfile.TemplateHash)
                    return "活动 VPK 预设来源不一致";
            }
            if (node.GetProperty("count").GetInt32() != 9) return "活动清单不是 9 人";
            if (node.GetProperty("vpk_sha256").GetString() != _request.BotProfile.VpkSha256)
                return "活动清单与请求的 VPK 哈希不一致";
            var manifestBots = node.GetProperty("bots").EnumerateArray().ToList();
            if (manifestBots.Count != 9) return "活动清单 Bot 数量不是 9";
            var requestBots = bots.ToDictionary(x => x.PlayerId, StringComparer.Ordinal);
            foreach (var item in manifestBots)
            {
                var id = item.GetProperty("player_id").GetString() ?? "";
                if (!requestBots.TryGetValue(id, out var wanted)) return "活动清单含请求外 player_id";
                if (item.GetProperty("profile_name").GetString() != wanted.ProfileName
                    || item.GetProperty("side").GetString() != wanted.Side
                    || item.GetProperty("profile_hash").GetString() != wanted.ProfileHash
                    || item.GetProperty("avatar_hash").GetString() != wanted.AvatarHash)
                    return "活动清单 Bot 档案与请求不一致";
            }
            var writtenHash = node.GetProperty("manifest_hash").GetString() ?? "";
            if (writtenHash != _request.BotProfile.ManifestHash || writtenHash != ComputeManifestHash(node))
                return "活动清单哈希不一致";
            var digest = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(vpk))).ToLowerInvariant();
            if (digest != _request.BotProfile.VpkSha256) return "活动 VPK 内容哈希不一致";
            if (File.GetLastWriteTimeUtc(vpk) >= Process.GetCurrentProcess().StartTime.ToUniversalTime())
                return "活动 VPK 没有在本次 CS2 进程启动前写入";
        }
        catch (Exception ex)
        {
            return "活动 VPK 校验异常: " + ex.Message;
        }
        return "";
    }

    private static string ComputeManifestHash(JsonElement node) => ManifestDigest.Compute(node);

    private void BindPlayerSlots()
    {
        if (_request is not { Active: true }) return;
        var configs = _request.Ct.Players.Concat(_request.T.Players).ToList();
        var live = AllSlots().ToList();
        var snapshots = live.Select(player =>
        {
            ulong authorized = 0;
            try { authorized = player.AuthorizedSteamID?.SteamId64 ?? 0; } catch { }
            return new IdentitySlot(player.Slot, $"{player.Handle}:{player.UserId}",
                player.PlayerName, player.SteamID, authorized, player.IsBot);
        }).ToList();
        var previous = _slotIds.Values.ToHashSet();
        _identities.Update(snapshots, configs.Select(c => new IdentityBot(c.PlayerId,
            c.ProfileName, SafeCommandText(c.DisplayName), c.SteamId)).ToList(), _request.HumanPlayerId);
        foreach (var missing in previous.Except(_slotIds.Values)) _disconnected.Add(missing);
        foreach (var id in _slotIds.Values)
        {
            _disconnected.Remove(id);
            if (id == _request.HumanPlayerId)
                EnsureLedger(id, _request.Player, false,
                    _request.HumanTeam.Trim().ToLowerInvariant() == "t" ? "t" : "ct");
            else
            {
                var hit = configs.Single(c => c.PlayerId == id);
                EnsureLedger(id, hit.DisplayName, true, hit.Side);
            }
        }
    }

    private LedgerRow EnsureLedger(string id, string name, bool bot, string team)
    {
        if (!_ledger.TryGetValue(id, out var row))
        {
            row = new LedgerRow { PlayerId = id, Name = name, IsBot = bot, Team = team };
            _ledger[id] = row;
        }
        row.Name = string.IsNullOrWhiteSpace(name) ? row.Name : name;
        // Team is the opening request side. CS2 swaps the live CT/T team at
        // halftime, but career identity and result ownership must not swap.
        return row;
    }

    private LedgerRow? RowFor(CCSPlayerController? player)
    {
        if (player is not { IsValid: true }) return null;
        BindPlayerSlots();
        return _slotIds.TryGetValue(player.Slot, out var id) && _ledger.TryGetValue(id, out var row) ? row : null;
    }


    private void FinalizeRound()
    {
        if (!_roundLive) return;
        foreach (var row in _ledger.Values)
        {
            if (!row.RoundDead) row.SurvivedRounds++;
            if (row.RoundKill || row.RoundAssist || !row.RoundDead || row.RoundTraded) row.KastRounds++;
        }
        _roundLive = false;
    }

    /// Setup should never cost anyone a round. If it did, restart from 0:0.
    private void ClearStolenRounds()
    {
        if (_scoreCleared || _request is not { Active: true })
        {
            return;
        }

        _scoreCleared = true;
        var scores = ReadTeamScores();
        if (scores.Ct + scores.T <= 0)
        {
            return;
        }

        Server.PrintToConsole(
            $"[CareerMatch] Wiping {scores.Ct}:{scores.T} awarded during setup.");
        Server.ExecuteCommand("mp_restartgame 1");
    }

    private HookResult OnRoundStart(EventRoundStart @event, GameEventInfo info)
    {
        if (_resultWritten) return HookResult.Continue;
        // Map initialization can emit round_start before warmup/setup exists.
        // It is not a scored career round and must not poison the match.
        if (!_setupDone || _request is not { Active: true }) return HookResult.Continue;
        ApplySideDuringWarmup();
        ApplyBotNames();
        if (IsEmptyMap(Server.MapName))
        {
            RestoreBestToDisk();
            return HookResult.Continue;
        }
        if (!InWarmup())
        {
            BindPlayerSlots();
            var openingScore = ReadTeamScores();
            if (_slotIds.Count != 10 || _slotIds.Values.Distinct().Count() != 10)
            {
                _rosterReadiness.Missing(openingScore.Ct + openingScore.T, _roundLive);
                TraceIdentity("roster_waiting", new { score = openingScore.Ct + openingScore.T,
                    bindings = new Dictionary<int,string>(_slotIds), reason = _rosterReadiness.Error });
                _roundLive = false;
                return HookResult.Continue;
            }
            _rosterReadiness.Ready(openingScore.Ct + openingScore.T);
            // round_start may fire again while leaving warmup. Derive the
            // round index from the actual score, not the number of callbacks.
            _liveRounds = TeamScoreMapping.LiveRoundIndex(openingScore.Ct, openingScore.T);
            _roundLive = true;
            _scoreAtRoundStart = openingScore.Ct + openingScore.T;
            _openingRecorded = false;
            _pendingTrades.Clear();
            _actors.NewRound();
            _pendingControls.Clear();
            BindPlayerSlots();
            _roundSnapshot.Clear();
            _roundStatisticsError = _health.StatisticsError;
            _roundTakeoverCount = _takeovers.Count;
            foreach (var pair in _ledger)
            {
                _roundSnapshot[pair.Key] = pair.Value.Copy();
            }
            foreach (var row in _ledger.Values)
            {
                row.RoundKill = row.RoundAssist = row.RoundDead = row.RoundTraded = false;
            }
            CaptureRoundPawns();
            if (_liveRounds == 2)
            {
                AnnounceDifficulty();
            }
        }
        WriteSnapshot(Server.MapName, _resultWritten ? "finished" : "in_progress");
        return HookResult.Continue;
    }

    private HookResult OnPlayerDisconnect(EventPlayerDisconnect @event, GameEventInfo info)
    {
        if (@event.Userid is { } leaving)
        {
            if (_slotIds.TryGetValue(leaving.Slot, out var leavingId))
            {
                _disconnected.Add(leavingId);
                _actors.Detach(leavingId);
                _pendingControls.Remove(leavingId);
            }
            _identities.Remove(leaving.Slot);
        }
        var scores = ReadTeamScores();
        if (scores.Ct + scores.T <= 0 && _bestDump is not null)
        {
            RestoreBestToDisk();
            return HookResult.Continue;
        }
        if (!_resultWritten && IsMatchOver(scores.Ct, scores.T))
        {
            FinishMatch(scores.Ct, scores.T);
        }
        else
        {
            WriteSnapshot(Server.MapName, _resultWritten ? "finished" : "in_progress", scores.Ct, scores.T);
        }
        return HookResult.Continue;
    }

    private void AnnounceDifficulty()
    {
        if (_announcedDifficulty)
        {
            return;
        }

        var name = (_request?.BotProfile.Difficulty ?? _request?.Difficulty ?? "").Trim();
        if (string.IsNullOrWhiteSpace(name))
        {
            return;
        }

        _announcedDifficulty = true;
        var level = name.Equals("High", StringComparison.OrdinalIgnoreCase) ? "3/3"
            : name.Equals("Low", StringComparison.OrdinalIgnoreCase) ? "1/3"
            : "2/3";
        Server.PrintToChatAll($" \x04Career 难度: {name} [{level}]\x01");
        var tuning = _request?.BotProfile.DifficultyModel == "bot_improver_career_tuned_v2"
            ? "原版增强参数 + 生涯个人微调" : "旧版调校（下场重新生成）";
        Server.PrintToChatAll($" \x04{tuning}\x01");
        Server.PrintToChatAll($" \x04本场 Bot 档案: 9/9 · {_request?.BotProfile.ShortHash}\x01");
        Server.PrintToConsole($"[CareerMatch] Difficulty {name} [{level}] model={_request?.BotProfile.DifficultyModel} preset={_request?.BotProfile.PresetSourceHash}");
    }

    private void SetupMatchBots()
    {
        if (_setupDone || _request is not { Active: true })
        {
            return;
        }

        _setupDone = true;

        if (!InWarmup())
        {
            StartWarmup();
        }

        Server.ExecuteCommand("mp_autoteambalance 0");
        Server.ExecuteCommand("mp_limitteams 0");
        Server.ExecuteCommand("bot_auto_vacate 0");
        Server.ExecuteCommand("bot_join_after_player 0");
        Server.ExecuteCommand("bot_quota_mode normal");
        Server.ExecuteCommand($"bh_identity_mode {RequestedIdentityMode()}");
        Server.ExecuteCommand("bh_namesource 0");
        Server.ExecuteCommand("bot_kick");
        Server.ExecuteCommand("bot_quota 0");

        var humanTeam = _request.HumanTeam.Trim().ToLowerInvariant();
        if (humanTeam is "ct" or "t")
        {
            Server.ExecuteCommand($"mp_human_team {humanTeam}");
        }

        foreach (var bot in _request.Ct.Players)
        {
            if (!string.IsNullOrWhiteSpace(bot.ProfileName))
            {
                Server.ExecuteCommand($"bot_add_ct \"{bot.ProfileName.Trim()}\"");
            }
        }

        foreach (var bot in _request.T.Players)
        {
            if (!string.IsNullOrWhiteSpace(bot.ProfileName))
            {
                Server.ExecuteCommand($"bot_add_t \"{bot.ProfileName.Trim()}\"");
            }
        }

        // Never backfill with a random bot: contract validation guarantees nine.
        Server.ExecuteCommand("bot_quota 9");
        Server.ExecuteCommand("bot_quota_mode normal");

        if (!string.IsNullOrWhiteSpace(_request.Ct.Name))
        {
            Server.ExecuteCommand($"mp_teamname_1 \"{SafeCommandText(_request.Ct.Name)}\"");
        }

        if (!string.IsNullOrWhiteSpace(_request.T.Name))
        {
            Server.ExecuteCommand($"mp_teamname_2 \"{SafeCommandText(_request.T.Name)}\"");
        }

        Server.PrintToConsole(
            $"[CareerMatch] Setup CT={_request.Ct.Name}:{string.Join(",", _request.Ct.Players.Select(x => x.ProfileName))} " +
            $"T={_request.T.Name}:{string.Join(",", _request.T.Players.Select(x => x.ProfileName))}");
        ApplyBotNames();
        AddTimer(1.0f, ApplyBotNames);
        AddTimer(2.5f, ApplyBotIdentities);
        AddTimer(5.0f, ApplyBotNames);
        AddTimer(6.0f, ApplyBotIdentities);
        AddTimer(10.0f, ApplyBotNames);
        AddTimer(20.0f, ApplyBotNames);
    }

    private string RequestedIdentityMode()
    {
        return _request?.BotIdentity.Equals("bot", StringComparison.OrdinalIgnoreCase) == true
            ? "bot"
            : "player";
    }

    private void ApplyBotIdentities()
    {
        if (_request is not { Active: true } || !string.IsNullOrEmpty(_contractError)) return;
        BindPlayerSlots();
        var configs = _request.Ct.Players.Concat(_request.T.Players)
            .ToDictionary(x => x.PlayerId, StringComparer.Ordinal);
        foreach (var bot in AllSlots())
        {
            if (!_slotIds.TryGetValue(bot.Slot, out var id)
                || !configs.TryGetValue(id, out var config)
                || config.SteamId == 0)
            {
                continue;
            }
            // Reasserting the same deterministic ID is safe and also covers
            // the short window before BotHider marks a new slot as managed.
            Server.ExecuteCommand($"bh_setsid {bot.Slot} {config.SteamId}");
        }
        ApplyBotNames();
        AddTimer(0.6f, ApplyBotNames);
    }

    private void ApplySideDuringWarmup()
    {
        if (!InWarmup())
        {
            return;
        }

        ApplyNamesAndSide();
    }

    private static void ReleaseHumanTeam()
    {
        // Leave sides alone after the pistol half starts, including at halftime.
        Server.ExecuteCommand("mp_human_team any");
    }

    private void ApplyNamesAndSide()
    {
        if (_request is not { Active: true })
        {
            return;
        }

        var humanWant = _request.HumanTeam.Trim().ToLowerInvariant() == "t"
            ? CsTeam.Terrorist
            : CsTeam.CounterTerrorist;

        BindPlayerSlots();
        foreach (var player in AllSlots())
        {
            if (player is not { IsValid: true } || player.IsHLTV)
            {
                continue;
            }

            if (_slotIds.GetValueOrDefault(player.Slot) == _request.HumanPlayerId
                && player.Team is CsTeam.Terrorist or CsTeam.CounterTerrorist or CsTeam.Spectator)
            {
                if (player.Team != humanWant)
                {
                    try
                    {
                        player.SwitchTeam(humanWant);
                    }
                    catch (Exception ex)
                    {
                        Logger.LogWarning(ex, "CareerMatch: SwitchTeam failed");
                    }
                }
            }
        }

        BindPlayerSlots();
        ApplyBotNames();
    }

    private void ApplyBotNames() => ApplyBotPresentation(namesOnly: false);

    private void RefreshDisplayNames() => ApplyBotPresentation(namesOnly: true);

    private void ApplyBotPresentation(bool namesOnly)
    {
        if (_request is null || !_health.CanMaintainPresentation(_request.Active)) return;
        BindPlayerSlots();
        var configs = _request.Ct.Players.Concat(_request.T.Players)
            .ToDictionary(x => x.PlayerId, StringComparer.Ordinal);
        foreach (var bot in AllSlots())
        {
            if (_slotIds.GetValueOrDefault(bot.Slot) == _request.HumanPlayerId)
            {
                var humanName = SafeCommandText(_request.Player);
                if (!string.IsNullOrWhiteSpace(humanName) && bot.PlayerName != humanName)
                {
                    bot.PlayerName = humanName;
                    Utilities.SetStateChanged(bot, "CBasePlayerController", "m_iszPlayerName");
                }
                continue;
            }
            if (!_slotIds.TryGetValue(bot.Slot, out var id) || !configs.TryGetValue(id, out var config))
                continue;
            var name = SafeCommandText(config.DisplayName);
            var changed = !string.IsNullOrWhiteSpace(name)
                && !string.Equals(bot.PlayerName, name, StringComparison.Ordinal);
            if (changed)
            {
                bot.PlayerName = name;
                Utilities.SetStateChanged(bot, "CBasePlayerController", "m_iszPlayerName");
            }
            // BotHider can attach after the bot exists and can restore its base
            // persona later. Keep its shared persona in sync with the display.
            if (!string.IsNullOrWhiteSpace(name) && (changed || !namesOnly))
            {
                Server.ExecuteCommand($"bh_setname {bot.Slot} \"{name}\"");
            }
            // Always override BotHider's synthetic Steam identity. Unknown
            // teams have a bundled neutral PNG, so no random external Steam
            // avatar can leak through.
            if (!namesOnly && TryValidatedAvatarPath(config, out var avatarPath, out _))
            {
                Server.ExecuteCommand($"bh_setavatar {bot.Slot} \"{avatarPath}\"");
            }
        }
    }

    private int? _openingCtCurrentSide;
    private (int Ct, int T) ReadTeamScores()
    {
        var ct = 0;
        var t = 0;
        foreach (var team in Utilities.FindAllEntitiesByDesignerName<CCSTeam>("cs_team_manager"))
        {
            if (team.TeamNum == (byte)CsTeam.CounterTerrorist)
            {
                ct = team.Score;
            }
            else if (team.TeamNum == (byte)CsTeam.Terrorist)
            {
                t = team.Score;
            }
        }

        var members = AllSlots().Where(p => _slotIds.ContainsKey(p.Slot))
            .Select(p => new TeamMembership(_slotIds[p.Slot],
                _ledger.TryGetValue(_slotIds[p.Slot], out var row) ? row.Team : "", (int)p.Team)).ToList();
        var mapped = TeamScoreMapping.OpeningCtCurrentSide(members);
        if (mapped is not null && mapped != _openingCtCurrentSide)
        {
            _openingCtCurrentSide = mapped;
            TraceIdentity("score_side_mapping", new { openingCtCurrentSide = mapped, liveCt = ct, liveT = t, members });
        }
        // During disconnect/intermission retain the last ten-player mapping.
        // Never reverse a saved winner merely because current slots disappear.
        if (_openingCtCurrentSide is null && ct + t > 0 && _roundLive)
            _health.StatisticsError = "无法确认比分对应的生涯战队，请保留现场";
        return TeamScoreMapping.Normalize(ct, t, _openingCtCurrentSide ?? 3);
    }

    private HookResult OnRoundEnd(EventRoundEnd @event, GameEventInfo info)
    {
        var scores = ReadTeamScores();
        _rosterReadiness.ObserveScore(scores.Ct + scores.T);
        if (_roundLive && scores.Ct + scores.T <= _scoreAtRoundStart)
        {
            _ledger.Clear();
            foreach (var pair in _roundSnapshot)
            {
                _ledger[pair.Key] = pair.Value.Copy();
            }
            _liveRounds = Math.Max(0, _liveRounds - 1);
            _health.StatisticsError = _roundStatisticsError;
            if (_takeovers.Count > _roundTakeoverCount)
                _takeovers.RemoveRange(_roundTakeoverCount, _takeovers.Count - _roundTakeoverCount);
            _actors.NewRound();
            _roundLive = false;
            _pendingControls.Clear();
            Server.PrintToConsole("[CareerMatch] Discarded restarted/non-scoring round.");
        }
        else
        {
            FinalizeRound();
        }
        WriteSnapshot(Server.MapName, "in_progress", scores.Ct, scores.T);
        if (!_resultWritten && IsMatchOver(scores.Ct, scores.T))
        {
            FinishMatch(scores.Ct, scores.T);
        }

        return HookResult.Continue;
    }

    private HookResult OnMatchEnd(EventCsWinPanelMatch @event, GameEventInfo info)
    {
        var scores = ReadTeamScores();
        FinishMatch(scores.Ct, scores.T);
        return HookResult.Continue;
    }

    private static bool IsMatchOver(int ct, int t)
    {
        if (ct == t)
        {
            return false;
        }

        var high = Math.Max(ct, t);
        var low = Math.Min(ct, t);
        return (high == 13 && low <= 11)
            || (high >= 16 && (high - 16) % 3 == 0 && low <= high - 2);
    }

    private void FinishMatch(int ct, int t)
    {
        if (_resultWritten)
        {
            return;
        }

        _resultWritten = true;
        _endedAt = DateTime.UtcNow.ToString("o");
        WriteSnapshot(Server.MapName, "finished", ct, t, force: true);
        Server.PrintToConsole($"[CareerMatch] Result {ct}:{t} exported.");
    }

    private static int SnapshotQuality(int ct, int t, int kills, string status)
    {
        var rounds = Math.Max(0, ct) + Math.Max(0, t);
        var finished = status == "finished" || (ct != t && Math.Max(ct, t) >= 13) ? 1 : 0;
        return rounds * 100000 + kills * 10 + finished;
    }

    private void WriteSnapshot(string mapName, string status, int? ctScore = null, int? tScore = null, bool force = false)
    {
        if (IsEmptyMap(mapName) && _bestDump is not null)
        {
            RestoreBestToDisk();
            return;
        }

        var scores = (ctScore, tScore) is (int c, int t) ? (c, t) : ReadTeamScores();
        var players = CollectPlayerResults();
        var kills = players.Sum(p => p.Kills);
        var quality = SnapshotQuality(scores.Item1, scores.Item2, kills, status);
        var bestQuality = _bestDump is null
            ? -1
            : SnapshotQuality(_bestDump.CtScore, _bestDump.TScore, _bestDump.Players.Sum(p => p.Kills), _bestDump.Status);

        if (!force && quality < bestQuality)
        {
            RestoreBestToDisk();
            return;
        }

        if (!force
            && status == _lastWrittenStatus
            && scores.Item1 == _lastWrittenCt
            && scores.Item2 == _lastWrittenT
            && kills == _lastWrittenKills)
        {
            return;
        }

        if (IsMatchOver(scores.Item1, scores.Item2))
        {
            status = "finished";
            if (string.IsNullOrEmpty(_endedAt))
            {
                _endedAt = DateTime.UtcNow.ToString("o");
            }
            _resultWritten = true;
        }

        var winner = scores.Item1 == scores.Item2
            ? (status == "finished" ? "draw" : "")
            : scores.Item1 > scores.Item2 ? "ct" : "t";

        var result = new MatchResult
        {
            SchemaVersion = 2,
            RequestNonce = _request?.Nonce ?? "",
            Status = status,
            Map = mapName,
            Winner = status == "finished" ? winner : "",
            CtScore = scores.Item1,
            TScore = scores.Item2,
            CtName = _request?.Ct.Name ?? "",
            TName = _request?.T.Name ?? "",
            EndedAt = status == "finished" ? (!string.IsNullOrEmpty(_endedAt) ? _endedAt : DateTime.UtcNow.ToString("o")) : "",
            Players = players,
            IdentityBindings = new Dictionary<int, string>(_slotIds),
            TakeoverEvents = _takeovers.ToList(),
        };
        result.ValidationError = ValidateResult(players, scores.Item1 + scores.Item2);
        result.Complete = string.IsNullOrEmpty(result.ValidationError);
        if (quality >= bestQuality)
        {
            _bestDump = result;
            WriteJson(_bestPath, result);
        }
        WriteJson(_resultPath, result);
        _lastWrittenStatus = status;
        _lastWrittenCt = scores.Item1;
        _lastWrittenT = scores.Item2;
        _lastWrittenKills = kills;
    }

    private List<PlayerResult> CollectPlayerResults()
    {
        BindPlayerSlots();
        var rounds = Math.Max(1, _liveRounds);
        var scoreNow = ReadTeamScores();
        if (!_actors.HadTakeover && IsMatchOver(scoreNow.Ct, scoreNow.T))
        {
            foreach (var player in AllSlots())
            {
                var row = RowFor(player);
                var match = player.ActionTrackingServices?.MatchStats;
                if (row is null || match is null) continue;
                if (row.Kills + row.Deaths + row.Assists + row.Damage == 0
                    && match.Kills + match.Deaths + match.Assists + match.Damage > 0)
                {
                    row.Kills = match.Kills;
                    row.Deaths = match.Deaths;
                    row.Assists = match.Assists;
                    row.Damage = match.Damage;
                    row.SurvivedRounds = Math.Max(0, rounds - row.Deaths);
                    row.KastRounds = Math.Min(rounds, row.SurvivedRounds + row.Kills + row.Assists);
                    row.UsedMatchStatsFallback = true;
                }
            }
        }
        var rows = _ledger.Values.Select(row => new PlayerResult
        {
            PlayerId = row.PlayerId,
            Name = row.Name,
            Team = row.Team,
            IsBot = row.IsBot,
            Kills = row.Kills,
            Deaths = row.Deaths,
            Assists = row.Assists,
            Damage = row.Damage,
            Score = row.Kills * 2 + row.Assists,
            Adr = Math.Round((double)row.Damage / rounds, 2),
            Kast = Math.Round((double)row.KastRounds / rounds, 4),
            OpeningKills = row.OpeningKills,
            OpeningDeaths = row.OpeningDeaths,
            SurvivedRounds = row.SurvivedRounds,
            TradedDeaths = row.TradedDeaths,
            StatsSource = row.UsedMatchStatsFallback ? "matchstats_fallback" : "event_ledger",
        }).ToList();

        rows = rows
            .OrderByDescending(p => p.Score)
            .ThenByDescending(p => p.Kills)
            .ThenBy(p => p.Name, StringComparer.OrdinalIgnoreCase)
            .ToList();

        var totalKills = rows.Sum(p => p.Kills);
        if (totalKills > _bestKillTotal)
        {
            _bestPlayers = rows;
            _bestKillTotal = totalKills;
        }
        else if (_bestKillTotal > 0 && totalKills == 0)
        {
            return _bestPlayers;
        }

        return rows.Count > 0 ? rows : _bestPlayers;
    }

    private string ValidateResult(List<PlayerResult> rows, int scoreRounds)
    {
        if (!string.IsNullOrEmpty(_health.ResultError)) return _health.ResultError;
        _rosterReadiness.ObserveScore(scoreRounds);
        if (_rosterReadiness.Error.Length > 0) return _rosterReadiness.Error;
        if (_request is null || _request.Nonce != _sessionNonce) return "请求 nonce 不匹配";
        var actualMap = (Server.MapName ?? "").Replace("de_", "", StringComparison.OrdinalIgnoreCase);
        var wantedMap = (_request.Map ?? "").Replace("de_", "", StringComparison.OrdinalIgnoreCase);
        if (!actualMap.Equals(wantedMap, StringComparison.OrdinalIgnoreCase)) return "地图与请求不匹配";
        if (rows.Count != 10) return $"只采集到 {rows.Count}/10 名选手";
        if (rows.Select(x => x.PlayerId).Distinct().Count() != 10) return "结果 player_id 不唯一";
        var expected = _request.Ct.Players.Concat(_request.T.Players).Select(x => x.PlayerId)
            .Append(_request.HumanPlayerId).ToHashSet();
        if (!expected.SetEquals(rows.Select(x => x.PlayerId))) return "结果选手与请求的十人身份不一致";
        if (_disconnected.Count > 0) return "仍有选手断线未重连";
        if (rows.Count(x => x.Team == "ct") != 5 || rows.Count(x => x.Team == "t") != 5)
            return "结果不是两边各 5 人";
        if (_liveRounds < scoreRounds) return "正式回合账本少于比分回合数";
        if (rows.Any(x => x.Deaths > scoreRounds || x.Deaths < 0
            || x.SurvivedRounds + x.Deaths != scoreRounds || x.Kast < 0 || x.Kast > 1))
            return "死亡/存活/KAST 与正式回合数不守恒";
        if (rows.Sum(x => x.Kills) > rows.Sum(x => x.Deaths)) return "击杀/死亡不守恒";
        return "";
    }

    private MatchRequest? ReadRequest()
    {
        try
        {
            if (!File.Exists(_requestPath))
            {
                return null;
            }

            return JsonSerializer.Deserialize<MatchRequest>(File.ReadAllText(_requestPath), JsonOptions);
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "CareerMatch: failed to read request.");
            return null;
        }
    }

    private void WriteJson<T>(string path, T value)
    {
        try
        {
            File.WriteAllText(path, JsonSerializer.Serialize(value, JsonOptions));
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "CareerMatch: failed to write {Path}.", path);
        }
    }
}
