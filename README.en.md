# CS2 Career

[简体中文](README.md#简体中文) · **English**

An unofficial CS2 player-career simulator. Start as an unknown prospect or take over a professional player, then build your career through training, transfers, matches, and choices off the server.

The focus is **a player's career with light club management**: simulate seasons in a standalone desktop app, or enter local CS2 bot matches and play for yourself.

[Download](https://github.com/bel1ever1314/cs2-career/releases) · [Player FAQ — Chinese](开始游玩-FAQ.txt) · [Changelog — Chinese](RELEASE_NOTES.md) · [Report an issue](https://github.com/bel1ever1314/cs2-career/issues)

> This source tree targets the **1.6.0 public beta**, with a Windows x64 desktop build. Check each Release's tag and notes: repository changes may not have been published yet. The separate Bot Lab experiments for Dust2 movement, crosshair placement, and team AI are **not included in this release**.

## Getting started

1. Open [Releases](https://github.com/bel1ever1314/cs2-career/releases) and download the player archive ending in `windows-x64.zip`, not `Source code`.
2. Extract the entire archive into a writable folder. Do not run it from inside the ZIP.
3. Launch `Launch-CS2Career.cmd` (the portable launcher), or run `CS2Career.exe`. Python is not required, and the app does not open a browser by default.
4. Choose an era and a player to begin. Switch to **English** using the sidebar language control or Settings (`设置` → `界面语言`).

The desktop window requires Microsoft's [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/). If it is missing, install it from Microsoft. Do not disable security software to run the app.

**Career simulation does not require launching CS2 or installing game plugins.** Playing or spectating actual CS2 matches requires the setup described below.

## What you can do

- **Build a player's career.** Choose the 2024, 2025, or 2026 era. Take over a pro, or create a player with an amateur, academy, or prodigy start. Develop attributes, try different roles, manage form, and pursue transfers and honors.
- **Follow a living season.** Enter tournaments and follow their progress. Open team and player profiles to inspect rosters, recent performances, and saved match reports. Follow the annual Top 20, MVPs, EVPs, and positional best teams.
- **Make choices off the server.** Experience romance, transfers, team relationships, injuries, and retirement stories. Management supports the career: wages and prize money settle automatically, without collecting payments from individual emails.
- **Collect virtual skins.** Browse the market, manage your inventory, equip items, and open cases. All funds and items are fictional; nothing enters your Steam inventory or can be cashed out.
- **Create content packs.** Extend stories, incidents, tournaments, skin images, and in-game chat through data-only packs rather than embedding all content in code.

## What's new in 1.6.0

### A faster way to experience a season

Fast mode handles invitations according to team level, scheduling, and ranking value, reducing repetitive low-value tournaments. Its single-screen match viewer progresses through the season without a scrolling event list: map scores are revealed gradually, the background reflects wins and losses, and each series ends with a report highlighting your player before automatically continuing.

Finals, consequential story choices, contracts, and Major off-season windows still pause for your input. Choose the mode at the start or end of a season. Normal mode's tournament auto-simulation also stops asking about every non-final match. Fast mode suppresses monthly reports, while routine notifications are generally archived.

### Stories around the Major off-season

Main stories arrive after a Major officially concludes. In a standard career, the romance storyline begins after the first Major; match-specific incidents, such as match-fixing approaches, can still occur during competition. **18 Major elimination stories** cover six exit stages and different expectations of your team's strength. Majors you participate in retain MVP, EVP, and positional best-team presentations.

Calendar occasions do not wait for an off-season: teammate birthdays and their responses occur on the day. Fast simulation and schedule jumps pause at a birthday for your choice, then continue.

In fast mode, attribute points accumulate during the season and can be spent after Majors. Normal mode still allows allocation at any time.

### Local ladder and custom matches

**Rank/FPL is one local bot ladder, not online matchmaking or a FACEIT connection.** Ranked matches use your current career player and match you with nine others based on ladder points. The two highest-rated players become captains, draft teams, and veto maps before entering CS2. Each drafted team is assigned one AWPer, entry, lurker, rifler, and IGL based on role-specific ability, without changing career positions. Ladder results are independent of career VRS, rewards, and attribute points.

Custom matches let you select both five-player rosters. Control one participant or spectate all ten bots. Custom matches do not award ladder points.

### Ratings, calendars, and English support

- Revised the simplified in-game VRS model to limit repetitive low-value wins, and corrected inflated ratings caused by switching roles.
- The 2024–2026 calendars use a sourced selection of real events. From 2027 onward, generated future events are labeled fictional. Calendars, rosters, and rules are not an exhaustive historical recreation; match outcomes are simulated.
- Core UI and built-in story content have English text. Untranslated third-party packs, player-edited text, and some older records retain their original language.

See the [1.6.0 guide — Chinese](V1.6.0_GUIDE.md) for detailed rules and editable files.

## Playing in CS2

You need Steam, CS2, and a compatible [CS2 Bot Improver Windows runtime package](https://github.com/ed0ard/CS2-Bot-Improver/releases). Skin changing is optional. Related bridge plugins ship with the player executable; the complete Bot Improver runtime must be obtained separately.

1. Fully exit CS2. In Game Settings, configure the game and Bot Improver package paths, then follow the installation prompts.
2. Prepare and launch a match from your career or the match lobby, then follow the instructions to enter the specified map.
3. Wait for the official match end and complete ten-player statistics before confirming the result. Do not quit merely because one team reaches 13 rounds.

A player-controlled match generates nine bots from its roster; custom spectator matches generate ten. Low/Medium/High use the enhancement's base presets, with individual profiles informed by career ability, role, and form. The original enhancement's full player database is not synchronized.

Coach and teammate dialogue appears as **chat-box text, not recorded or synthesized voice audio**.

Use this setup only for **local bot matches with `-insecure`**, not official matchmaking or online servers. Installation changes game plugins and match-specific bot data. CS2 updates can break compatibility: consult the relevant release notes and avoid mixing experimental DLLs. The [player FAQ](开始游玩-FAQ.txt) contains the full setup and troubleshooting instructions in Chinese.

## Saves and known limitations

- Saves live in `save/` beside the EXE; personal packs live in `extensions/`. Before updating, close Career and CS2 and back up both folders. Different extraction directories have separate saves. Do not run two versions against the same save simultaneously.
- New-format 1.5 saves remain readable. For older formats, follow the app's compatibility message rather than forcing a load by editing the schema. Keep your old folder and backups until the new version works.
- Historical data has gaps and simplifications. Career Rating and VRS are game models, not the complete official HLTV or Valve algorithms.
- Result import, bot takeover attribution, plugin compatibility, and long-term balance still need ongoing real-game testing. If validation fails, preserve the message and files before starting another match. Missing statistics are not filled with zeroes or guessed from the score.
- The separate Bot Lab remains experimental. It is not required to install this release and does not represent completed full-map bot behavior.

To report a problem, open an [Issue](https://github.com/bel1ever1314/cs2-career/issues) with the version, reproduction steps, exact error, and screenshots. Review logs for personal information first; do not upload entire saves, Steam configuration, credentials, or private paths. Passing automated tests does not establish that every live CS2 scenario works.

## Development and content packs

On Windows with Python 3.12+, run from the source root:

```powershell
py -3 -m pip install -r requirements-desktop.txt
py -3 main.py
```

Source launches use the same standalone desktop window and require WebView2. Editing source or bundled resources does not update an existing EXE; rebuild it to include those changes. Data packs in `extensions/` beside the EXE can be enabled in the workshop after restarting, without rebuilding.

- [Developer guide — Chinese](DEVELOPER_GUIDE.zh-CN.md): modules, state, and data flow; later corrections take precedence over historical notes.
- [Extension architecture — Chinese](EXTENSION_ARCHITECTURE.zh-CN.md) and [pack templates](extensions/_templates): stories, incidents, match phases, tournaments, and skin content.
- [English localization guide](ENGLISH_LOCALIZATION.md): UI, narrative, and extension translations.
- [Build and publishing guide — Chinese](PUBLISHING.md): executables, corresponding source, and privacy-safe release archives.
- [CS2 integration notes — Chinese](CS2_INTEGRATION.zh-CN.md): integration history and validation boundaries.

Run Python tests through `py -3 tools/run_tests.py`, which first isolates saves and extensions. Pure C# regression checks are in `tools/identity-tests`; they do not replace live game testing. Most developer documentation is currently in Chinese.

## License and credits

New and maintained career code is licensed under **AGPL-3.0-only**; see [LICENSE](LICENSE). Existing MIT rights and third-party licenses are retained in [Third-party notices — Chinese](THIRD_PARTY_NOTICES.md).

Thanks to ed0ard and the CS2 Bot Improver contributors for the templates and BotBuy, Ian Lucas for Inventory Simulator, and the authors of Metamod, CounterStrikeSharp, and the related plugins. See [Recovered source notes — Chinese](RECOVERED_SOURCE.md) for the historical skin components and their rebuild limitations.

This project is not affiliated with Valve, FACEIT, tournaments, teams, or players. Names, trademarks, and artwork belong to their respective rights holders. Distribute corresponding source with player builds and retain license notices. Keep personal saves, private packs, logs, and caches out of public archives.
