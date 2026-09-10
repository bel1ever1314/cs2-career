namespace CareerMatch;

// Startup readiness is recoverable. Missing scored rounds are not. Keep this
// separate from combat StatisticsError so recovery cannot erase genuine loss.
internal sealed class RosterReadiness
{
    private int? _waitingAtScore;
    private bool _lostData;
    public string Error => _lostData
        ? "阵容未就绪期间已有正式回合计分，战绩不完整，禁止录入"
        : _waitingAtScore.HasValue ? "正在等待本场十名选手身份就绪" : "";
    public void Reset() { _waitingAtScore = null; _lostData = false; }
    public void Missing(int score, bool interruptedLiveRound)
    {
        _waitingAtScore ??= score;
        _lostData |= interruptedLiveRound;
        ObserveScore(score);
    }
    public void ObserveScore(int score)
    {
        if (_waitingAtScore is int before && score > before) _lostData = true;
    }
    public void Ready(int score)
    {
        ObserveScore(score);
        _waitingAtScore = null;
    }
}
