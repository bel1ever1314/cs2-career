namespace CareerMatch;

// Invalid assets/identities prevent presentation writes. Invalid statistics
// prevent ingestion only: they must not stop names and safe avatars being kept.
internal sealed class SessionHealth
{
    public string ContractError { get; set; } = "";
    public string StatisticsError { get; set; } = "";
    public bool CanMaintainPresentation(bool active) => active && ContractError.Length == 0;
    public string ResultError => ContractError.Length > 0 ? ContractError : StatisticsError;
}
