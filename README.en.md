# CS2 Career

[简体中文](README.md#简体中文) · [English](#cs2-career)

An unofficial CS2 player-career game. The idea is to give each match a story of your own: grow from a newcomer into a pro, train, transfer, get to know your teammates, and take your player onto the stage.

The career now has a 3D world to walk around in. You're a chicken with a dorm room, a club, a phone, and a computer. Develop your player and plan the season between matches; on match day, simulate the series, command your team in RTS, or enter CS2 and play it yourself.

[Download the 1.7.0 3D preview](https://github.com/bel1ever1314/cs2-career/releases/latest) · [Download the 1.6.0 desktop release](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.6.0-hotfix.1) · [Changelog — Chinese](RELEASE_NOTES.md) · [Feedback](https://github.com/bel1ever1314/cs2-career/issues)

The current version is **1.7.0-preview.3-hotfix.4, the 3D play-flow update**. The **1.6.0-hotfix.1** desktop version remains available separately.

## Getting started

1. Open the [latest release](https://github.com/bel1ever1314/cs2-career/releases/latest) and download `CS2Career-1.7.0-preview.3-hotfix.4-windows.zip`.
2. Extract the entire archive into a writable folder. Run `Launch-CS2Career.cmd` or `开始游戏.cmd`.
3. Follow the opening flow to create a player, draft abilities, and customize your chicken, or choose an era and take over a professional player.
4. In your dorm, walk to the computer and press `E`, or press `P` to take out your phone.

Godot and the Python backend are bundled; you don't need development tools. If you run into graphics compatibility issues, try `兼容显卡启动.cmd`. Career simulation and RTS run inside the app. For actual CS2 matches, see the setup below.

Controls: `WASD` to walk, right-mouse drag to rotate the club view, `E` to use objects, `F` to talk to nearby characters, `P` for your phone, and `Esc` to go back. At a doorway, use the mouse wheel to choose a destination, then press `E` or `Enter` to travel.

## Life in the career

- **Start with your own player.** Choose the 2024, 2025, or 2026 era, draw teams and player abilities, and customize feathers, comb, beak, and jersey colors. You can also start by taking over a pro.
- **Spend time around the club.** Walk through the dorm and club and talk to teammates, coaches, and staff. Read email and chats on your phone, check the calendar and your stats, and allocate attribute points. A sleep transition takes you into the next day.
- **Plan the season at your computer.** Enter tournaments, browse teams and players, read reports and news, manage rosters and contracts, handle club finances and transfers, schedule practice, or start a fast season.
- **Choose how to play a match.** Simulate career series map by map, play them in CS2, or command your team in RTS. RTS lets you switch between command, player control, and spectating. The local ladder and custom rooms have their own player drafts and map vetoes.
- **Draw your tactics.** Use the meeting-room board to set routes, pauses, observation directions, and running or walking for five slots, then save them for matches. Zoom, pan, and import or export tactics.
- **Visit the stage and collect honors.** Enter a small LAN room or a large venue and continue the match from your seat. Follow championships, MVPs, EVPs, positional best teams, and the annual Top 20. If your player makes the annual top three, walk up to collect the award.
- **Collect and equip skins.** Browse the market, manage inventory, equip items, and open cases using fictional in-game funds. These items do not enter your Steam inventory.
- **Continue at your own pace.** Use manual saves and loads, or follow a fast season through matches, story choices, and off-season windows.

The local ladder uses your current career player. The two highest-rated participants captain the teams, draft players, and veto maps. Ladder points are separate from career VRS, prize money, and attribute points. Custom rooms let you arrange both five-player rosters, control one participant, or watch ten bots.

## Playing in CS2

Install and sign into Steam and CS2, and obtain a compatible [CS2 Bot Improver Windows runtime](https://github.com/ed0ard/CS2-Bot-Improver/releases). The public 3D package includes Career and its bridge components; the complete bot enhancement is obtained separately.

1. Fully exit CS2. Open Settings on the phone or computer, set the Steam, CS2 and extracted bot-enhancement paths, then choose “安装填写目录的人机增强” (Install from the configured folder). The installer checks your local release and installs it together with Career's bundled tactics, result reporting and compatibility components, backing up existing files. Your original release folder stays unchanged; later matches use the compatible runtime copy. Once you have the complete official package, installation works offline.
2. Prepare a career, ladder, or custom match, complete the player draft and map veto, then launch CS2.
3. Finish the official match and return to the career computer to review and import the result.

On match day, you can also travel to the assigned venue from the doorway. Preparation progress is shown, and pending replies can be opened on the phone before continuing.

“Check for bot-enhancement updates” only contacts GitHub when you click it and never downloads or replaces components automatically. In-game skin swapping starts disabled; enable it in Settings if you want to use it.

This version supports Bot Improver 1.4.5. Accepted action radio commands such as Follow Me or Fall Back interrupt your team's custom tactics, including waypoint waits. Ordinary information calls keep the tactic running.

Use these plugins for **local bot matches with `-insecure`**. Before returning to official matchmaking, disable or remove the plugins following their instructions and check your Steam launch options.

Skin loadouts can come from Career or a separately configured plugin such as [Inventory Simulator](https://github.com/ianlucas/cs2-css-inventory-simulator/releases). 3D skin inspection and direct sticker editing are optional interfaces, disabled by default, and require a separate tool and adapter. An external inspector is not bundled.

## Saves and feedback

The 3D package stores saves in `game/runtime/career/save/`, with manual saves in its `manual/` folder. Back up your saves before updating; moving the whole extracted folder also keeps your progress with it. The 1.6 desktop version keeps its saves in its original directory.

Share experiences and suggestions in [Issues](https://github.com/bel1ever1314/cs2-career/issues). For a problem, include the version, what you were doing, and a screenshot. Logs are in `game/runtime/game.log`; check them for personal information before posting.

## Source and content packs

The 3D client is in `work/career3d_redesign/`, the career backend in `cs2career/`, and the packaging entry point is `tools/package_career3d.py`. Source development uses Godot and Python; see the [3D packaging notes — Chinese](docs/3d-preview-packaging.zh-CN.txt) for entry points and asset preparation.

- [Developer guide — Chinese](DEVELOPER_GUIDE.zh-CN.md): modules, state, and data flow.
- [Extension architecture — Chinese](EXTENSION_ARCHITECTURE.zh-CN.md) and [pack templates](extensions/_templates): stories, incidents, tournaments, skins, and in-game chat.
- [Build and publishing guide — Chinese](PUBLISHING.md): source, runtime packages, and publishing.
- [English localization guide](ENGLISH_LOCALIZATION.md): UI and content translations.
- [1.6.0 guide](V1.6.0_GUIDE.md) and [player FAQ](开始游玩-FAQ.txt), both in Chinese: desktop-version rules and CS2 setup.

Run Python tests with `py -3 tools/run_tests.py`. C# checks are in `tools/identity-tests`.

## License and credits

New and maintained career code uses **AGPL-3.0-only**; see [LICENSE](LICENSE). Existing MIT rights and third-party licenses are retained in [Third-party notices — Chinese](THIRD_PARTY_NOTICES.md) and [licenses](licenses). Keep license notices and provide corresponding source when distributing builds.

Thanks to ed0ard and the CS2 Bot Improver contributors, Ian Lucas for Inventory Simulator, and the authors of Metamod, CounterStrikeSharp, the fonts, and related plugins. Historical component source notes are in [RECOVERED_SOURCE.md](RECOVERED_SOURCE.md).

This is an unofficial project, unaffiliated with Valve, FACEIT, tournaments, teams, or players. Names, trademarks, and artwork belong to their respective rights holders.
