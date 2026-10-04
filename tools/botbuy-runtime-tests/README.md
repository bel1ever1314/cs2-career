# BotBuy execution regression harness

Run from the repository root:

```powershell
dotnet run --project tools/botbuy-runtime-tests/BotBuyRuntimeTests.csproj -c Release
```

If this development machine has only a newer preview runtime, the same
`net10.0` harness can run without installing another runtime:

```powershell
$env:DOTNET_ROLL_FORWARD = 'LatestMajor'
$env:DOTNET_ROLL_FORWARD_TO_PRERELEASE = '1'
dotnet run --project tools/botbuy-runtime-tests/BotBuyRuntimeTests.csproj -c Release
```

The project directly links the production `BotBuy.CareerRules.cs`,
`BotBuy.M4Preference.cs`, `BotBuy.TeamGifts.cs`, `BotBuy.WeaponIdentity.cs`,
`CareerWeaponPolicy.cs` and `TacticalBuyPlan.cs`. At build time it extracts and
compiles the current production `CanModify`, `HasPrimaryWeapon`, `Buy`,
`Refund`, `CanRefund`, `Swap`, `OnItemPurchase`, `IsFirstRoundOfHalf`,
`AddRoundTimer`, `NormalizePurchasedWeapons`, and `ApplyTacticalPurchase`.
It also checks that the round handler wires the gift schedule and resets the
M4 correction guard. If one of
these source anchors disappears the build fails; it does not silently substitute
a copied algorithm.

Minimal CounterStrikeSharp fakes supply game entities, cvars, spawning,
inventory, money-state notifications, next-frame callbacks, and time. This
exercises purchase-event proof, exact M4-S identity, price differences,
rollback, one-attempt-per-round guards and teammate gifts without a server.

Gift scenarios include current-money eligibility after armor/utility buying,
late donor readiness, the 2850 CT rifle-price gap, the observed 910/torzsi
inventory deficit, persistent per-round donor limits, and 1 Hz freeze-only
review with no grants after round/map changes. The fake API supplies inventory
attachment; it does not turn these scenarios into a live-match result.

Cvars retain their registered primitive type. `mp_freezetime` is modeled as
`Int32`; asking for `Single` throws instead of converting it. This reproduces
the actual hotfix.7 scheduling failure that a permissive numeric fake missed.

The harness does not emulate native BotProfile buying, network replication,
or API binary compatibility. It tests both immediate and pending inventory
removal/attachment; the final in-game weapon is recorded separately by the
plugin's verification log. Only legacy non-career refund history is stubbed;
the career purchase, refund and rollback methods are production code.
