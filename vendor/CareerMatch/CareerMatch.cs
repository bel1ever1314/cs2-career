using System.Text.Json;
using System.Text.Json.Serialization;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Core.Attributes;
using CounterStrikeSharp.API.Modules.Timers;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

public sealed class MatchRequest
{
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

    [JsonPropertyName("applied_difficulty")]
    public string AppliedDifficulty { get; set; } = "";

    [JsonPropertyName("nonce")]
    public string Nonce { get; set; } = "";
}

public sealed class TeamConfig
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("logo")]
    public string Logo { get; set; } = "";

    [JsonPropertyName("players")]
    public List<string> Players { get; set; } = [];
}

public sealed class PlayerResult
{
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
}

public sealed class MatchResult
{
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
}

[MinimumApiVersion(304)]
public sealed class CareerMatchPlugin : BasePlugin
{
    public override string ModuleName => "CareerMatch";
    public override string ModuleVersion => "1.1.3";
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

    public override void Load(bool hotReload)
    {
        _requestPath = Path.Combine(ModuleDirectory, "match_request.json");
        _resultPath = Path.Combine(ModuleDirectory, "match_result.json");
        _bestPath = Path.Combine(ModuleDirectory, "match_result.best.json");
        _request = ReadRequest();
        _sessionNonce = _request?.Nonce ?? "";

        RegisterEventHandler<EventCsWinPanelMatch>(OnMatchEnd);
        RegisterEventHandler<EventRoundEnd>(OnRoundEnd);
        RegisterEventHandler<EventRoundStart>(OnRoundStart);
        RegisterEventHandler<EventPlayerConnectFull>(OnPlayerConnect);
        RegisterEventHandler<EventPlayerDisconnect>(OnPlayerDisconnect);
        RegisterEventHandler<EventWarmupEnd>(OnWarmupEnd);
        RegisterListener<Listeners.OnMapStart>(OnMapStart);
        AddTimer(12.0f, TickSnapshot, TimerFlags.REPEAT);
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
        _scoreCleared = false;
        _announcedDifficulty = false;
        _liveRounds = 0;

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
        ApplySideDuringWarmup();
        if (IsEmptyMap(Server.MapName))
        {
            RestoreBestToDisk();
            return HookResult.Continue;
        }
        if (!InWarmup())
        {
            _liveRounds += 1;
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

        var name = (_request?.AppliedDifficulty ?? _request?.Difficulty ?? "").Trim();
        if (string.IsNullOrWhiteSpace(name))
        {
            return;
        }

        _announcedDifficulty = true;
        var level = name.Equals("High", StringComparison.OrdinalIgnoreCase) ? "3/3"
            : name.Equals("Low", StringComparison.OrdinalIgnoreCase) ? "1/3"
            : "2/3";
        Server.PrintToChatAll($" \x04Career 难度: {name} [{level}]\x01");
        Server.PrintToConsole($"[CareerMatch] Difficulty {name} [{level}]");
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
        Server.ExecuteCommand("bot_kick");
        Server.ExecuteCommand("bot_quota 0");

        var humanTeam = _request.HumanTeam.Trim().ToLowerInvariant();
        if (humanTeam is "ct" or "t")
        {
            Server.ExecuteCommand($"mp_human_team {humanTeam}");
        }

        foreach (var name in _request.Ct.Players)
        {
            if (!string.IsNullOrWhiteSpace(name))
            {
                Server.ExecuteCommand($"bot_add_ct \"{name.Trim()}\"");
            }
        }

        foreach (var name in _request.T.Players)
        {
            if (!string.IsNullOrWhiteSpace(name))
            {
                Server.ExecuteCommand($"bot_add_t \"{name.Trim()}\"");
            }
        }

        // Ask for a full 5v5 so the game backfills any name it refused.
        var totalBots = Math.Max(9, _request.Ct.Players.Count + _request.T.Players.Count);
        Server.ExecuteCommand($"bot_quota {totalBots}");
        Server.ExecuteCommand("bot_quota_mode normal");

        if (!string.IsNullOrWhiteSpace(_request.Ct.Name))
        {
            Server.ExecuteCommand($"mp_teamname_1 \"{_request.Ct.Name}\"");
        }

        if (!string.IsNullOrWhiteSpace(_request.T.Name))
        {
            Server.ExecuteCommand($"mp_teamname_2 \"{_request.T.Name}\"");
        }

        Server.PrintToConsole(
            $"[CareerMatch] Setup CT={_request.Ct.Name}:{string.Join(",", _request.Ct.Players)} " +
            $"T={_request.T.Name}:{string.Join(",", _request.T.Players)}");
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

        foreach (var player in Utilities.GetPlayers())
        {
            if (player is not { IsValid: true } || player.IsHLTV)
            {
                continue;
            }

            if (!player.IsBot && player.Team is CsTeam.Terrorist or CsTeam.CounterTerrorist or CsTeam.Spectator)
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

        RenameBots(CsTeam.CounterTerrorist, _request.Ct.Players);
        RenameBots(CsTeam.Terrorist, _request.T.Players);
    }

    private static void RenameBots(CsTeam team, List<string> names)
    {
        var bots = Utilities.GetPlayers()
            .Where(p => p is { IsValid: true, IsBot: true } && p.Team == team)
            .OrderBy(p => p.Slot)
            .ToList();

        for (var i = 0; i < bots.Count && i < names.Count; i++)
        {
            var name = names[i].Trim();
            if (string.IsNullOrWhiteSpace(name) || string.Equals(bots[i].PlayerName, name, StringComparison.Ordinal))
            {
                continue;
            }

            bots[i].PlayerName = name;
            Utilities.SetStateChanged(bots[i], "CBasePlayerController", "m_iszPlayerName");
            Server.ExecuteCommand($"bh_setname {bots[i].Slot} {name}");
        }
    }

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

        return (ct, t);
    }

    private HookResult OnRoundEnd(EventRoundEnd @event, GameEventInfo info)
    {
        var scores = ReadTeamScores();
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

        return Math.Max(ct, t) >= 13;
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
            Status = status,
            Map = mapName,
            Winner = status == "finished" ? winner : "",
            CtScore = scores.Item1,
            TScore = scores.Item2,
            CtName = _request?.Ct.Name ?? "",
            TName = _request?.T.Name ?? "",
            EndedAt = status == "finished" ? (!string.IsNullOrEmpty(_endedAt) ? _endedAt : DateTime.UtcNow.ToString("o")) : "",
            Players = players,
        };
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
        var rows = new List<PlayerResult>();
        foreach (var player in Utilities.GetPlayers())
        {
            if (player is not { IsValid: true } || player.IsHLTV)
            {
                continue;
            }

            if (player.Team is not (CsTeam.Terrorist or CsTeam.CounterTerrorist))
            {
                continue;
            }

            var stats = player.ActionTrackingServices?.MatchStats;
            var kills = stats?.Kills ?? 0;
            var deaths = stats?.Deaths ?? 0;
            var assists = stats?.Assists ?? 0;
            var damage = stats?.Damage ?? 0;
            rows.Add(new PlayerResult
            {
                Name = player.PlayerName ?? "Unknown",
                Team = player.Team == CsTeam.CounterTerrorist ? "ct" : "t",
                IsBot = player.IsBot,
                Kills = kills,
                Deaths = deaths,
                Assists = assists,
                Damage = damage,
                Score = player.Score > 0 ? player.Score : kills * 2 + assists,
            });
        }

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
