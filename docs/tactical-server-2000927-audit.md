# CS2 2000927 tactical adapter

Local file review, 2026-10-06. Game version 1.41.8.9, revision 11087167,
build date Oct 05 2026. `server.dll` SHA256:
`C98CC7EA3095A32683FC37FEA804537B3EA6D89836FD4F5E55D593A82BB54EE3`.

The real match log rejected navigation and observation with
`feature_section_layout_not_audited:.data`. The Mirage playbook was present;
this was not a missing tactic or a map-name conflict. The new file changes
`.data` virtual size from 6371316 to 6371284 and `.reloc` size from 567376
to 567380. Several complete instruction bodies also differ, so removing
the section check alone would not make the adapter compatible.

## Reviewed native contract

- MoveTo and Idle wrappers still tail-call SetState at `0x2DE010`, with
  the same argument widths, state/goal fields and native ownership.
- ComputePath (`0x2BAFA0`, 1758 bytes) retains the Win64 vector/route/cost/
  rate-limited-output contract. The repath timer remains at `+0x4F08`,
  rejected rate-limited requests do not overwrite the accepted path,
  and the fifth argument remains an optional byte output.
- MoveTo OnEnter (`0x32A630`, 151 bytes) still calls ComputePath and
  selects native route 1/2. OnUpdate (`0x330E90`, 3133 bytes), OnExit
  (`0x32AAF0`, 33 bytes) and the three entry predicates were inspected.
- Constructor at `0x2AF070` retains Idle at `+0x218`, MoveTo at `+0x2E0`.
  Its LEAs at `0x2AF19F`, `0x2AF233`, `0x2AF283` now publish vtables
  `0x17AD950`, `0x17AD708`, `0x17AD798`: 32 bytes before the old tables.
  Reading the old MoveTo table would read the string `MoveTo`, not a
  callback. These are now selected by the audited file profile.
- Bot Run/Walk slots remain `+0x28/+0x30`, pointing to `0x2DCAB0` and
  `0x2E7A00`. Their complete code is unchanged. MoveTo slots still point
  to OnEnter/OnUpdate/OnExit, now at the relocated table.
- SetLookAt (`0x2DDA40`, 347 bytes) retains bot/descriptor/vector/priority
  and float/byte stack parameters. Request state `+0x535C`, target
  `+0x5360`, priority `+0x536C`, descriptor `+0x5380` are unchanged.
- ClearLookAt (`0x2FC1D0`, 20 bytes) still clears only state/descriptor.
  Consumer (`0x2E6D30`, 1500 bytes) retains enemy-aim bypass, alignment
  transition 1 to 2, and duration measured from alignment.
- The exact BotAI six-NOP defuse visibility patch remains at `0x33185B`.
  The COS/SIN zero-drift patches remain at `0x2E729B/0x2E72C8`.
  No other loaded-code changes are accepted.

## Admission and regression

`TacticalServer927` is a separate exact-file profile. It does not weaken
the existing bounded 2000924 feature profile, approve future files, or
mix function bodies between builds. Complete current bodies are pinned;
loaded snapshots stay frozen and checked during execution.

Navigation regression tests cover the actual installed file, 12,631
complete-body/variant/state-layout checks, and 23 new-file/layout checks.
Observation tests cover 47 file/lease checks and the same 23 layout checks.
The relocated-vtable test uses allocated non-executable data and calls
the same layout validator as the live adapter. These tests never load
or execute the game DLL; in-match movement still requires a play session.

Failures before route creation now enter `identity_traces`; bind/command
status is written to `tactical_status.json`. Neither contains account
credentials. No career save, playbook, game DLL or BotController binary
is modified by this fix.
