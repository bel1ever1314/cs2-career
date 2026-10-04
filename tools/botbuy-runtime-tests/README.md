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

The project directly links the production `BotBuy.FullBuy.cs`,
`CareerWeaponPolicy.cs` and `TacticalBuyPlan.cs`. At build time it extracts and
compiles the current production `CanModify`, `HasPrimaryWeapon`, `Buy`,
`IsFirstRoundOfHalf`, `AddRoundTimer`, `NormalizePurchasedWeapons`,
`ApplyTacticalPurchase`, and the career purchase scheduling block. If one of
these source anchors disappears the build fails; it does not silently substitute
a copied algorithm.

Minimal CounterStrikeSharp fakes supply game entities, cvars, spawning,
inventory, money-state notifications, and time. This exercises the actual
fallback execution, attachment-before-charge transaction and delayed callback
guards without installing a game or connecting to a server.

The harness intentionally does **not** emulate the game's native bot buying,
network replication, API binary compatibility, or asynchronous refund/removal.
`CanRefund` and `Swap` are surrounding stubs: refund-pending inventory is injected
explicitly. A successful run proves the isolated execution contract, not an
in-game playtest.
