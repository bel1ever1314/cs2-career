# CS2 Career

[简体中文](#简体中文) · [English](#english)

## 简体中文

一个非官方的 CS2 选手生涯游戏。想让每场比赛多一点属于自己的故事：从新人到职业选手，训练、转会、和队友相处，再带着自己的角色走进赛场。

现在，生涯也有了一个可以走进去的 3D 世界。你是一只小鸡，有自己的宿舍、俱乐部、手机和电脑。平时培养选手、安排赛季；到了比赛日，可以模拟比赛、用 RTS 指挥队伍，也可以进入 CS2，亲自打出这场比赛。

[下载 1.7.0 3D 预览版](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.7.0-preview.1) · [下载 1.6.0 正式版](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.6.0-hotfix.1) · [更新日志](RELEASE_NOTES.md) · [交流与反馈](https://github.com/bel1ever1314/cs2-career/issues)

当前版本是 **1.7.0-preview.1，首次 3D 预览版**。原来的桌面正式版仍是 **1.6.0-hotfix.1**，两个版本分别提供下载。

### 开始游玩

1. 打开 [3D 预览版发布页](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.7.0-preview.1)，下载 `CS2Career-1.7.0-preview.1-windows.zip`。
2. 完整解压到可写入的文件夹，双击 `开始游戏.cmd` 或 `Launch-CS2Career.cmd`。
3. 按开局引导创建角色、抽取能力并调整小鸡形象，也可以选择年代接管职业选手。
4. 进入宿舍后，去电脑前按 `E` 看看今天能做什么，或按 `P` 拿出手机。

运行包已经带上 Godot 和 Python 后台，无需安装开发工具。如果遇到显卡兼容问题，可以试试包里的 `兼容显卡启动.cmd`。生涯模拟和 RTS 都可以直接在程序里游玩；亲自进入 CS2 的准备见下文。

基本操作：`WASD` 走动，鼠标右键拖动转动俱乐部视角，`E` 使用物品，`F` 和附近人物交流，`P` 打开手机，`Esc` 返回。走到门口后，用滚轮选择目的地，按 `E` 或 `Enter` 出发。

### 在这个世界里做什么

- **从自己的角色开始。** 选择 2024／2025／2026 年代，抽取队伍与选手能力，搭配羽毛、鸡冠、喙和队服颜色；也可以接管职业选手开始生涯。
- **过选手的日常。** 在宿舍和俱乐部走动，与队友、教练和工作人员交流。手机里收邮件、回聊天、看日历、查看个人数据和分配属性点；睡觉时有过场，醒来继续下一天。
- **在电脑前安排赛季。** 报名赛事、浏览选手和战队、看战报与新闻、管理阵容和合同、处理经营与转会，也可以预约训练赛或开启快速赛季。
- **选择自己的比赛方式。** 职业比赛可以逐图模拟、进入 CS2 实打，或使用 RTS 指挥。RTS 里可以切换指挥、本人操作与观战。本地天梯和自定义对局也有各自的选人与地图 BP。
- **把战术画出来。** 在会议室白板为五个槽位设计路线、停留、观察方向和跑动／静步方式，保存后供比赛使用；支持缩放、平移和战术导入导出。
- **经历赛场与荣誉。** 走进小型 LAN 或大型场馆，在自己的机位继续比赛。查看冠军、MVP、EVP、最佳阵容和年度 Top20；入围年度前三时，可以亲自走上领奖台。
- **收集与配装。** 浏览饰品市场、管理库存、装备和开箱。全部使用游戏内虚拟资金，饰品不进入 Steam 库存。
- **按自己的节奏继续。** 使用手动存档与读档，保存生涯进度；快速赛季在比赛、剧情选择和休赛期之间推进。

本地天梯使用当前生涯角色，由本场积分最高的两人担任队长，选人、禁图后开赛。天梯积分与职业生涯的 VRS、奖金和属性点分开记录。自定义可以安排双方各五名选手，亲自控制其中一人或观看十名 Bot 比赛。

### 亲自进入 CS2

需要自行安装并登录 Steam 和 CS2，以及获取兼容的 [CS2 Bot Improver Windows 运行包](https://github.com/ed0ard/CS2-Bot-Improver/releases)。公开的 3D 运行包提供生涯程序和桥接组件，完整人机增强另行获取。

1. 完全退出 CS2，在手机或电脑的“设置”中填写 CS2 与人机增强目录，按提示配置插件。
2. 从职业比赛、本地天梯或自定义对局准备比赛，完成选人与地图 BP 后启动 CS2。
3. 打完正式比赛，回到生涯电脑查看回传战绩并录入结果。

这套插件用于 **`-insecure` 本地人机对局**。恢复官方匹配前，按组件说明停用或移除插件，并检查 Steam 启动项。

换肤可以选择生涯配装，或自行配置 [Inventory Simulator](https://github.com/ianlucas/cs2-css-inventory-simulator/releases) 等外部插件。饰品的 3D 检视和直接贴纸编辑是默认关闭的可选接口，需要另装对应工具与适配器；运行包不内置外部检视器。

### 存档和反馈

3D 运行包的存档位于 `game/runtime/career/save/`，手动存档在其中的 `manual/` 目录。更新前备份自己的存档，移动整个解压目录也可以带走进度。1.6 桌面版的存档仍保存在它原来的目录中。

欢迎在 [Issues](https://github.com/bel1ever1314/cs2-career/issues) 分享体验和建议。遇到问题时，带上版本、当时的操作和截图，会更容易定位；日志在 `game/runtime/game.log`。公开日志前请检查个人信息。

### 源码与内容扩展

3D 客户端在 `work/career3d_redesign/`，生涯内核在 `cs2career/`，打包入口是 `tools/package_career3d.py`。源码开发使用 Godot 与 Python，具体入口和资源准备见 [3D 打包说明](docs/3d-preview-packaging.zh-CN.txt)。

- [开发者指南](DEVELOPER_GUIDE.zh-CN.md)：模块、状态与数据流。
- [扩展架构](EXTENSION_ARCHITECTURE.zh-CN.md)与[内容包模板](extensions/_templates)：剧情、事件、赛事、饰品和局内聊天扩展。
- [构建与发布](PUBLISHING.md)：源码、运行包与发布流程。
- [英文翻译指南](ENGLISH_LOCALIZATION.md)：界面与内容的本地化。
- [1.6.0 指南](V1.6.0_GUIDE.md)与[玩家 FAQ](开始游玩-FAQ.txt)：原桌面版的规则与 CS2 配置。

Python 测试入口是 `py -3 tools/run_tests.py`，C# 检查位于 `tools/identity-tests`。

### 授权与致谢

新增与维护的生涯代码采用 **AGPL-3.0-only**，见 [LICENSE](LICENSE)。原有 MIT 权利和第三方许可保留，见 [第三方声明](THIRD_PARTY_NOTICES.md)与 [licenses](licenses)。分发程序时请保留许可并提供对应源码。

感谢 ed0ard 与 CS2 Bot Improver 贡献者、Ian Lucas 的 Inventory Simulator，以及 Metamod、CounterStrikeSharp、字体和相关插件的作者。历史组件的源码说明见 [RECOVERED_SOURCE.md](RECOVERED_SOURCE.md)。

这是一个非官方项目，与 Valve、FACEIT、赛事、战队和选手无官方关联。相关名称、商标与素材归各自权利人所有。

---

## English

An unofficial CS2 player-career game. The idea is to give each match a story of your own: grow from a newcomer into a pro, train, transfer, get to know your teammates, and take your player onto the stage.

The career now has a 3D world to walk around in. You're a chicken with a dorm room, a club, a phone, and a computer. Develop your player and plan the season between matches; on match day, simulate the series, command your team in RTS, or enter CS2 and play it yourself.

[Download the 1.7.0 3D preview](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.7.0-preview.1) · [Download the 1.6.0 desktop release](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.6.0-hotfix.1) · [Changelog — Chinese](RELEASE_NOTES.md) · [Feedback](https://github.com/bel1ever1314/cs2-career/issues)

The current version is **1.7.0-preview.1, the first 3D preview**. The existing desktop release remains **1.6.0-hotfix.1** and is available separately.

### Getting started

1. Open the [3D preview release](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.7.0-preview.1) and download `CS2Career-1.7.0-preview.1-windows.zip`.
2. Extract the entire archive into a writable folder. Run `Launch-CS2Career.cmd` or `开始游戏.cmd`.
3. Follow the opening flow to create a player, draft abilities, and customize your chicken, or choose an era and take over a professional player.
4. In your dorm, walk to the computer and press `E`, or press `P` to take out your phone.

Godot and the Python backend are bundled; you don't need development tools. If you run into graphics compatibility issues, try `兼容显卡启动.cmd`. Career simulation and RTS run inside the app. For actual CS2 matches, see the setup below.

Controls: `WASD` to walk, right-mouse drag to rotate the club view, `E` to use objects, `F` to talk to nearby characters, `P` for your phone, and `Esc` to go back. At a doorway, use the mouse wheel to choose a destination, then press `E` or `Enter` to travel.

### Life in the career

- **Start with your own player.** Choose the 2024, 2025, or 2026 era, draw teams and player abilities, and customize feathers, comb, beak, and jersey colors. You can also start by taking over a pro.
- **Spend time around the club.** Walk through the dorm and club and talk to teammates, coaches, and staff. Read email and chats on your phone, check the calendar and your stats, and allocate attribute points. A sleep transition takes you into the next day.
- **Plan the season at your computer.** Enter tournaments, browse teams and players, read reports and news, manage rosters and contracts, handle club finances and transfers, schedule practice, or start a fast season.
- **Choose how to play a match.** Simulate career series map by map, play them in CS2, or command your team in RTS. RTS lets you switch between command, player control, and spectating. The local ladder and custom rooms have their own player drafts and map vetoes.
- **Draw your tactics.** Use the meeting-room board to set routes, pauses, observation directions, and running or walking for five slots, then save them for matches. Zoom, pan, and import or export tactics.
- **Visit the stage and collect honors.** Enter a small LAN room or a large venue and continue the match from your seat. Follow championships, MVPs, EVPs, positional best teams, and the annual Top 20. If your player makes the annual top three, walk up to collect the award.
- **Collect and equip skins.** Browse the market, manage inventory, equip items, and open cases using fictional in-game funds. These items do not enter your Steam inventory.
- **Continue at your own pace.** Use manual saves and loads, or follow a fast season through matches, story choices, and off-season windows.

The local ladder uses your current career player. The two highest-rated participants captain the teams, draft players, and veto maps. Ladder points are separate from career VRS, prize money, and attribute points. Custom rooms let you arrange both five-player rosters, control one participant, or watch ten bots.

### Playing in CS2

Install and sign into Steam and CS2, and obtain a compatible [CS2 Bot Improver Windows runtime](https://github.com/ed0ard/CS2-Bot-Improver/releases). The public 3D package includes Career and its bridge components; the complete bot enhancement is obtained separately.

1. Fully exit CS2. Open Settings on the phone or computer, set the CS2 and bot-enhancement directories, and follow the plugin setup instructions.
2. Prepare a career, ladder, or custom match, complete the player draft and map veto, then launch CS2.
3. Finish the official match and return to the career computer to review and import the result.

Use these plugins for **local bot matches with `-insecure`**. Before returning to official matchmaking, disable or remove the plugins following their instructions and check your Steam launch options.

Skin loadouts can come from Career or a separately configured plugin such as [Inventory Simulator](https://github.com/ianlucas/cs2-css-inventory-simulator/releases). 3D skin inspection and direct sticker editing are optional interfaces, disabled by default, and require a separate tool and adapter. An external inspector is not bundled.

### Saves and feedback

The 3D package stores saves in `game/runtime/career/save/`, with manual saves in its `manual/` folder. Back up your saves before updating; moving the whole extracted folder also keeps your progress with it. The 1.6 desktop version keeps its saves in its original directory.

Share experiences and suggestions in [Issues](https://github.com/bel1ever1314/cs2-career/issues). For a problem, include the version, what you were doing, and a screenshot. Logs are in `game/runtime/game.log`; check them for personal information before posting.

### Source and content packs

The 3D client is in `work/career3d_redesign/`, the career backend in `cs2career/`, and the packaging entry point is `tools/package_career3d.py`. Source development uses Godot and Python; see the [3D packaging notes — Chinese](docs/3d-preview-packaging.zh-CN.txt) for entry points and asset preparation.

- [Developer guide — Chinese](DEVELOPER_GUIDE.zh-CN.md): modules, state, and data flow.
- [Extension architecture — Chinese](EXTENSION_ARCHITECTURE.zh-CN.md) and [pack templates](extensions/_templates): stories, incidents, tournaments, skins, and in-game chat.
- [Build and publishing guide — Chinese](PUBLISHING.md): source, runtime packages, and publishing.
- [English localization guide](ENGLISH_LOCALIZATION.md): UI and content translations.
- [1.6.0 guide](V1.6.0_GUIDE.md) and [player FAQ](开始游玩-FAQ.txt), both in Chinese: desktop-version rules and CS2 setup.

Run Python tests with `py -3 tools/run_tests.py`. C# checks are in `tools/identity-tests`.

### License and credits

New and maintained career code uses **AGPL-3.0-only**; see [LICENSE](LICENSE). Existing MIT rights and third-party licenses are retained in [Third-party notices — Chinese](THIRD_PARTY_NOTICES.md) and [licenses](licenses). Keep license notices and provide corresponding source when distributing builds.

Thanks to ed0ard and the CS2 Bot Improver contributors, Ian Lucas for Inventory Simulator, and the authors of Metamod, CounterStrikeSharp, the fonts, and related plugins. Historical component source notes are in [RECOVERED_SOURCE.md](RECOVERED_SOURCE.md).

This is an unofficial project, unaffiliated with Valve, FACEIT, tournaments, teams, or players. Names, trademarks, and artwork belong to their respective rights holders.
