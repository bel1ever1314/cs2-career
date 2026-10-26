using NadeSystem;

void Check(bool ok, string message) { if (!ok) throw new Exception(message); }
var b = new CareerNadeBudget();
b.Reset(); b.AddBot(1, 2, true); b.AddBot(2, 2, true); b.AddBot(3, 3, true);
CareerNadeBudget.Ticket? R(uint bot, int team, string type, float now = 0,
    float x = 0, ulong targets = 0) => b.Reserve(bot, team, type, now, x, 0, 0, targets);
var failed = R(1, 2, "he")!;
Check(R(1, 2, "molotov") == null, "reservation allows duplicate grenade");
Check(!b.Complete(failed, false, 0), "failed spawn commits");
var fire = R(1, 2, "molotov")!;
Check(b.Complete(fire, true, 0), "successful fire not committed");
Check(!b.Complete(fire, true, 0) && R(1, 2, "he") == null, "damage shared quota/replay");
int rolls = 0;
b.Decay(bot => bot != 3, () => { rolls++; return .34; });
Check(rolls == 1 && R(2, 2, "he") == null && R(3, 3, "he") != null, "holder-only decay");
var flash = R(1, 2, "flash", targets: 4)!;
Check(R(2, 2, "flash", x: 900, targets: 4) == null, "duplicate target not reserved");
b.Complete(flash, true, 10);
Check(R(2, 2, "flash", 12.9f) == null, "spacing starts before actual spawn");
var other = R(2, 2, "flash", 13)!;
Check(other != null, "flash spacing never expires");
b.Complete(other!, false, 13);
var second = R(1, 2, "flash", 13)!;
b.Complete(second, true, 13);
Check(R(1, 2, "flash", 20) == null, "more than two personal flashes");
var s1 = R(1, 2, "smoke", 20)!; b.Complete(s1, true, 20);
var s2 = R(1, 2, "smoke", 20)!; b.Complete(s2, true, 20);
Check(R(2, 2, "smoke", 20) == null, "smoke not shared across team");
var stale = R(2, 2, "flash", 20)!;
b.Reset(); b.AddBot(2, 2, true);
Check(!b.Complete(stale, true, 21), "previous-round callback commits");
Check(R(2, 2, "he", 21) != null, "old callback consumes new round item");
Console.WriteLine("PASS: damage/flash/smoke quotas, spawn rollback, holder decay, round isolation");
