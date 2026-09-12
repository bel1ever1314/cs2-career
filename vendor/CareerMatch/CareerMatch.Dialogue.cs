using CounterStrikeSharp.API;
using Microsoft.Extensions.Logging;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    private readonly MatchDialogue _dialogue = new();
    private ChatContract? _chatContract;
    private readonly DialoguePlayback _chatPlayback = new();
    private readonly HashSet<string> _clutchCandidates = [];

    private void LoadDialogue()
    {
        _chatPlayback.Cancel();
        _chatContract = null;
        try
        {
            if (_request?.MatchChat is { } raw)
            {
                var config = System.Text.Json.JsonSerializer.Deserialize<ChatContract>(raw.GetRawText());
                if (MatchDialogue.Valid(config)) _chatContract = config;
                else Logger.LogWarning("Invalid optional dialogue contract; chat disabled, match unchanged.");
            }
        }
        catch (Exception ex) { Logger.LogWarning("Dialogue config ignored: {Error}", ex.Message); }
    }

    private void AnnounceRoundDialogue(int ct, int t)
    {
        // Optional presentation must never invalidate or modify the event ledger.
        try
        {
            if (_request is null || !string.IsNullOrEmpty(_contractError)
                || !string.IsNullOrEmpty(_health.StatisticsError) || !string.IsNullOrEmpty(_rosterReadiness.Error)
                || !_ledger.TryGetValue(_request.HumanPlayerId, out var human)
                || !_roundSnapshot.TryGetValue(human.PlayerId, out var before)) return;
            var own = human.Team == "ct" ? ct : t;
            var other = human.Team == "ct" ? t : ct;
            var mine = human.Team == "ct" ? _request.Ct : _request.T;
            var enemy = human.Team == "ct" ? _request.T : _request.Ct;
            var clutch = _ledger.Values.FirstOrDefault(r => r.Team == human.Team && !r.RoundDead
                && _clutchCandidates.Contains(r.PlayerId));
            var context = new Dictionary<string, string> {
                ["player"] = human.Name, ["player_id"] = human.PlayerId,
                ["team"] = mine.Name, ["team_id"] = mine.TeamId, ["opponent"] = enemy.Name,
                ["map"] = _request.Map, ["score_for"] = own.ToString(), ["score_against"] = other.ToString(),
                ["lead"] = (own - other).ToString(), ["kills"] = human.Kills.ToString(),
                ["deaths"] = human.Deaths.ToString(), ["assists"] = human.Assists.ToString(),
                ["damage"] = human.Damage.ToString(), ["round_kills"] = (human.Kills - before.Kills).ToString(),
                ["clutch"] = clutch is null ? "0" : "1", ["clutch_player"] = clutch?.Name ?? "",
            };
            // Winner captured from normalized opening-team score, not live CT/T.
            var result = own > _chatOwnScoreAtStart ? "win" : "loss";
            var batch = _dialogue.EndRoundBatch(_chatContract, _request.Nonce, ct + t, result,
                context, _ledger.Values.Select(r => new ChatPerson(r.PlayerId, r.Name, r.Team, r.IsBot)).ToList(), human.Team);
            if (batch.Lines.Count == 0) return;
            var epoch = _chatPlayback.Begin();
            PlayDialogueLine(batch, 0, epoch, _request.Nonce, human.Team);
        }
        catch (Exception ex) { Logger.LogWarning("Career dialogue skipped: {Error}", ex.Message); }
    }

    private void PlayDialogueLine(ChatBatch batch, int index, long epoch, string nonce, string humanTeam)
    {
        try
        {
            if (_request is not { Active: true } || _request.Nonce != nonce || !_setupDone || InWarmup()
                || !string.IsNullOrEmpty(_contractError) || !string.IsNullOrEmpty(_health.StatisticsError)
                || !string.IsNullOrEmpty(_rosterReadiness.Error))
            {
                _chatPlayback.Cancel(); return;
            }
            if (!_chatPlayback.Take(epoch, index)) return;
            var message = batch.Lines[index].Message;
            if (message.Channel == "all") Server.PrintToChatAll(message.Text);
            else
                foreach (var player in AllSlots())
                    if (player.IsValid && !player.IsBot && _slotIds.TryGetValue(player.Slot, out var id)
                        && _ledger.TryGetValue(id, out var row) && row.Team == humanTeam)
                        player.PrintToChat(message.Text);
            if (index + 1 < batch.Lines.Count)
            {
                // Chain timers, rather than scheduling all lines concurrently.
                // Managed strings only; never retain native event/controller references.
                var delay = batch.Lines[index + 1].AfterSeconds - batch.Lines[index].AfterSeconds;
                AddTimer((float)delay, () => PlayDialogueLine(batch, index + 1, epoch, nonce, humanTeam),
                    CounterStrikeSharp.API.Modules.Timers.TimerFlags.STOP_ON_MAPCHANGE);
            }
        }
        catch (Exception ex)
        {
            _chatPlayback.Cancel();
            Logger.LogWarning("Dialogue playback cancelled: {Error}", ex.Message);
        }
    }

    private int _chatOwnScoreAtStart;
}
