using CareerMatch;

if (args.Length != 1) throw new ArgumentException("Pass the installed server.dll (file audit only; never loads or executes the game DLL).");
if (!TacticalNativeNavigation.TryAuditFile(args[0], out var audit, out var error)) throw new Exception(error);
if (audit is null || audit.MoveRva != 0x2cfec0 || audit.IdleRva != 0x2c8230 || audit.StateRva != 0x2de010
    || audit.PathRva != 0x2bafa0)
    throw new Exception("Navigation wrapper identity disagrees with the static command-callback review.");
Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { file_audit = "passed", audit, live_call = "not_tested" }));
var fixture = Path.Combine(AppContext.BaseDirectory, "wrong-server.fixture");
try
{
    File.WriteAllBytes(fixture, [0x4d, 0x5a, 0x00, 0x00]);
    if (TacticalNativeNavigation.TryAuditFile(fixture, out _, out var reason)
        || !reason.StartsWith("server_build_not_audited:")) throw new Exception("Unreviewed server must never bind navigation.");
    if (TacticalNativeNavigation.TryAuditFile(fixture + ".missing", out _, out _)) throw new Exception("Missing server must reject.");
    Console.WriteLine("3 native-file audit checks passed. No server module loaded or executed.");
}
finally { File.Delete(fixture); }

TacticalContinuationRegression.Run(args[0]);
