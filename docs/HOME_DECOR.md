# Home decoration · 2026-10-07

The bedroom keeps its authored shell, bed, bedside light and workstation. Baked-in
lounge furniture, rug, entry cabinet and loose props are hidden by `home_room.gd`;
their colliders and backend reserved footprints are removed together. The GLB and
club/venue assets are unchanged. Existing purchased furniture, placements, finishes
and wallets are preserved without rewriting a save on read.

Press B at home to decorate. Click an existing item or its list entry to move it,
click the floor to place it, use R to rotate, and Esc to cancel the move. Store one
item or confirm Store all; items remain owned. Save layout commits the draft;
leaving without saving restores the saved room. Walls and floors retain their
existing purchase/use flow.

Placement uses the same footprint, rotation and collision clearance on the client
and service. Save also checks connectivity to bed, workstation and door. All edit
controls are frozen during a write, duplicate clicks do not submit another command,
and an unfinished move cannot be silently discarded by Save. Context refreshes
preserve an unsaved draft. Closing moves the character only when a newly saved
solid would otherwise trap it.

Regression coverage: `tests/test_career3d_environment.py` and
`work/career3d_redesign/tests/environment_ui_test.gd`. Tests use isolated saves and
captured commands, cover ownership/replay/restart/discard, and check the decoration
panel and floor access at 960×540 and 1920×1080.
