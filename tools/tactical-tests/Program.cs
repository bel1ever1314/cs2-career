using CareerMatch;

if (args.Length != 1) throw new ArgumentException("Pass the installed server.dll (file audit only; never loads or executes the game DLL).");
if (!TacticalNativeNavigation.TryAuditFile(args[0], out var audit, out var error)) throw new Exception(error);
if (audit is null || audit.MoveRva != 0x2cfec0 || audit.IdleRva != 0x2c8230 || audit.StateRva != 0x2de010
    || audit.PathRva != 0x2bafa0)
    throw new Exception("Navigation wrapper identity disagrees with the static command-callback review.");
Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { file_audit = "passed", audit, live_call = "not_tested" }));
if (!TacticalNativeNavigation.IsAuditedServerHash(audit.Sha256)
    || !TacticalNativeNavigation.IsAuditedServerHash(TacticalNativeNavigation.PreviousServerSha256)
    || TacticalNativeNavigation.IsAuditedServerHash(new string('0', 64))
    || TacticalNativeNavigation.IsAuditedServerHash(TacticalNativeNavigation.AuditedServerSha256.ToLowerInvariant()))
    throw new Exception("Only the two explicitly reviewed build hashes may identify the legacy exact-file profile.");
Console.WriteLine("4 exact reviewed-file provenance checks passed.");
var fixture = Path.Combine(AppContext.BaseDirectory, "wrong-server.fixture");
try
{
    File.WriteAllBytes(fixture, [0x4d, 0x5a, 0x00, 0x00]);
    if (TacticalNativeNavigation.TryAuditFile(fixture, out _, out var reason)
        || !reason.StartsWith("navigation_audit_failed:")) throw new Exception("Invalid PE must never bind navigation.");
    if (TacticalNativeNavigation.TryAuditFile(fixture + ".missing", out _, out _)) throw new Exception("Missing server must reject.");
    Console.WriteLine("3 native-file audit checks passed. No server module loaded or executed.");
}
finally { File.Delete(fixture); }

TacticalContinuationRegression.Run(args[0]);
FeatureProfileRegression.Run(args[0], observation: false, bytes =>
{
    bool passed = TacticalNativeNavigation.TryAuditBytes(bytes, out _, out _, out var reason);
    return (passed, reason);
});
