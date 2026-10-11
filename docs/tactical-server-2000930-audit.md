# CS2 2000930 Windows compatibility — 2026-10-10

Target: CS2 1.41.9.0, server build 2000930, SourceRevision 11106093,
VersionDate 2026-10-08. `server.dll` SHA-256:
`9F31FC84164F7822E015DCD95EA958F9DD33D02308A646A2BEE5C9B39BD6FC28`.

CareerMatch version: `1.7.2-cs2.2000930.1`. This preserves the deployed
1.7.2 avatar, event and tactical fixes, including the exact 2000927 profile.
It adds a separate exact 2000930 profile; unknown layouts still fail closed.

## Native navigation and observation

The reviewed tactical functions moved by 0x850 relative to 2000924/2000927.
The delta is applied only to the listed functions after the exact server hash
matches. Unique signatures, complete function hashes and loaded-code snapshots
are checked independently. The legacy bounded feature profile remains unchanged.

- Bot constructor: 0x2AF8C0; main vtable: 0x17A8980;
  MoveTo vtable: 0x17A87C8; Idle vtable: 0x17A8738.
- MoveTo wrapper: 0x2D0710; Idle wrapper: 0x2C8A80;
  SetState: 0x2DE860; ComputePath: 0x2BB7F0.
- MoveTo Enter/Update/Exit: 0x32AE80 / 0x3316E0 / 0x32B340.
- Run/Walk: 0x2DD300 / 0x2E8250.
- SetLookAt / ClearLookAt / observation consumer:
  0x2DE290 / 0x2FCA20 / 0x2E7580.

The constructor, state callbacks, complete function bodies and field accesses
were disassembled against the installed game file. MoveTo goal offsets remain
+0x2E8/+0x2EC/+0x2F0, route +0x2F4, current state +0x5C0. ComputePath's Win64
fifth argument remains a one-byte rate-limit result; accepted route and arrival
remain distinct. Continuation retains the previous goal until a successor path
is accepted. No stale state restoration, teleport or velocity writes were added.

Observation fields remain state +0x535C, vector +0x5360, priority +0x536C,
duration +0x5370 and descriptor +0x5380. The lease projects the requested 2D
direction at actual eye height, checks alignment and yields to combat/objective
actions. Cancellation clears only its own request.

The live-code guard accepts the exact reviewed BotAI variants: six NOPs at
MoveToUpdate+0x9CB, and zero-drift replacements at observation consumer+0x56B
and +0x598. Any other byte mutation is rejected. RVAs alone are insufficient.

## Other components

- CounterStrikeSharp 1.0.376, Bot Improver 1.4.5, Controller 0.7.0,
  Hider 0.5.1, Vision 0.3.0 and Randomizer 1.3.2 were retained.
- Metamod is pinned to official Windows 2.0.0.1474. Archive SHA-256:
  `846158A0F67AD1E286B1AEC5EDB216D29DD35BB0FE754718A30F0FA2FE77A8CA`.
  The runtime fingerprint index was regenerated for that archive.
- InventorySimulator: updated only the Windows SetWearables and
  SetModelFromClass signatures from upstream gamedata. The old patterns
  respectively matched zero and two places. The replacement patterns match
  exactly once in this server. Other fields and Linux signatures are preserved.
- RayTrace: its two stale entity-I/O signatures can now be corrected for this
  exact game hash during install and preparation, with an external backup.
  This is **not** proof that its native plugin works. The installed VDF contains
  a placeholder rather than a plugin descriptor. With a valid descriptor the
  official 1.0.16 DLL is rejected by Metamod for SourceHook ABI 17 versus 18.
  The downloaded official DLL is byte-identical to the installed DLL. It was
  therefore not enabled or represented as repaired. CareerMatch navigation and
  observation do not depend on RayTrace. A source rebuild is separate remaining
  work for consumers that actually need that plugin.

Primary provenance:
[Metamod 1474](https://github.com/alliedmodders/metamod-source/releases/tag/2.0.0.1474),
[RayTrace 1.0.16](https://github.com/FUNPLAY-pro-CS2/Ray-Trace/releases/tag/v1.0.16),
[InventorySimulator gamedata](https://github.com/ianlucas/cs2-css-inventory-simulator/blob/main/gamedata/inventory-simulator.json).

## Verification and limits

- Release compilation: zero warnings/errors.
- Navigation: 4 provenance checks, 3 invalid-file checks, 12,631 continuation
  checks and 23 build-specific layout/mutation checks.
- Observation: 23 build-specific layout/mutation checks and 47 lease/native
  observation checks.
- Existing identity, observer, health, takeover, assist, roster, radio,
  playbook, movement and continuation regressions passed.
- BotBuy: 98 scenarios / 234 checks; tactical safety: 65 checks.
- Python: 152 CS2 tests (2 skipped), 39 compatibility tests, 73 tactical tests
  and 9 packaging tests passed.
- Before the user took over live testing, an isolated server loaded the
  candidate and bound both native interfaces with `profile=reviewed_2000930`.
  This proves module binding only. Movement, arrival, observation alignment,
  grenade throws, human takeover and a complete match/result handoff were
  **not** established in that session. The test process was stopped at the
  user's request; no further CS2 instances will be started for this task.

The distributable uses the reviewed 2026-10-08 1.7.2 application source and
assets as its base. Only this compatibility patch is overlaid before rebuilding
the backend, so the newer market, training and save-system work is preserved.
