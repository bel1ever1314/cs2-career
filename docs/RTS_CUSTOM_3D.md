# Custom matches and local RTS prototype

The Python application remains the single authoritative Career/Arena owner.
The 3D computer now exposes the original custom Arena room. This is shared with
ranked matchmaking, not a second lobby store. Existing launch nonce, frozen
ten-player identities, CS2 tactics deployment and result ingestion are reused.
Custom results never award ranked Elo or Career progression.

`tools/career3d_activities.py` projects custom catalogs/status and read-only RTS
rosters. `tools/career3d_service.py` serializes authenticated writes through the
same ApplicationState lock. `computer_custom.gd` handles the room UI, retry and
uncertain-result reconciliation. It never automatically retries a failed write.

## Local commander module

Canonical standalone source: `work/career_rts/`. It reuses the existing
CS2Tactical2D project, local Bot Lab NAV geometry and aggregate Demo knowledge.
`tools/sync_career_rts.ps1` generates the namespaced `rts/` resource copy inside
`work/career3d_redesign/`; edit the canonical source, not that generated copy.
The generated module has no autoload, HTTP client or Career writer.

`computer_rts.gd` passes the selected custom room's immutable ten-player roster
to `game.gd` in commander mode. It preserves the computer device lock while a
full-screen local Control covers the monitor. Closing releases local simulation
input and returns to the computer, without closing or settling the Arena room.

`match_sim.gd` owns a fixed-step 2D round state. `command_move` plans selected
friendly live units, validates targets, and accepts bounded queued waypoints.
The renderer only selects from the supplied friendly observation layer and
returns radar coordinates. Map zoom/panning cannot change game positions.

The NAV projection is an approximation, not BSP collision/visibility. Door tests
must exercise actual motion and body traffic; path existence alone is insufficient.
The local RTS report is not accepted as a CS2 result or Career series result.
Career RTS settlement, additional maps and three-dimensional movement fidelity
are explicitly outside this first prototype.

## Safe validation and packaging

Tests run with mock transports/`--no-service` and isolated D/E directories.
No real game DLL is installed or changed by these deployment scripts.
`deploy_career3d_redesign.ps1` includes the namespaced RTS resources and backs up
changed source files; `deploy_career_rts.ps1` updates the existing independent
2D tool. Neither removes runtime, player inventories or saved games.

The release/public-source uploader is not invoked by this work.

## Verification record, 2026-10-02

- Original custom-room API: seven isolated workflow groups pass, including
  observer ten-Bot launch, arbitrary nine-Bot player launch, failed launch retry,
  exact-once ten-ID ingestion and no Career/Elo rewards. Actual game/process,
  file preparation and result provider boundaries are mocked, not a live CS2 test.
- Custom UI: 50 checks; existing ladder draft/BP: 70; CS2 ladder UI: 10.
- Commander mouse/mode boundaries: 28; embedded device/keyboard boundaries: 12;
  actual 3D module flow/clock gates: 18. These use isolated or mock transports.
- Actual NAV door integration: 96 checks, including seven traffic lifecycle
  checks; map-level door tests: 444. B, mid, outer long and inner long are
  exercised in both directions with one and five actors, plus the real WASD
  handler. Motion segments and body separation are checked every simulation tick.
- Existing gameplay (285), squad routes (67) and three full autonomous seeded
  matches (6,068) pass separately. A path found by A* is never counted as a
  completed traversal.

The door repair uses the NAV agent-centre footprint rather than shrinking it by
the nominal radius twice. Map wall/clearance/sight PNG bytes remain unchanged.
Larger-than-nominal actors retain extra clearance tests. Directed portals and
whole-motion-segment checks remain active. Traffic yielding is bounded movement
along legal NAV, preserves the permanent goal/queued orders, and never teleports,
pushes actors through each other or disables body collision.

Live CS2 custom tactics and subjective RTS gameplay still require player testing.
This record does not certify Career RTS settlement or full CS2 geometry fidelity.
