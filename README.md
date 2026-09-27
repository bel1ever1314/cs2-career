# CS2 Career

[简体中文](#简体中文) · [English](#english)

## 简体中文

一个非官方的 CS2 选手生涯模拟器。你可以从无名选手开始，也可以接管职业选手，在训练、转会、比赛与人生选择中，走出自己的职业生涯。

以“选手生涯＋适度经营”为核心：既能在桌面里模拟赛季，也能进入 CS2 本地人机比赛，亲自打出属于自己的战绩。

[下载发行版](https://github.com/bel1ever1314/cs2-career/releases) · [玩家 FAQ](开始游玩-FAQ.txt) · [更新日志](RELEASE_NOTES.md) · [反馈问题](https://github.com/bel1ever1314/cs2-career/issues)

> 当前源码面向 **1.6.0 公开测试版**，提供 Windows 64 位桌面程序。下载时请以 Release 标签和说明为准，仓库中的新改动不一定已发布。独立 Bot Lab 的沙二视角／团队 AI 实验**不包含在本版中**。

### 开始游玩

1. 前往 [Releases](https://github.com/bel1ever1314/cs2-career/releases)，下载名称带 `windows-x64.zip` 的玩家包，而不是 `Source code`。
2. 完整解压到可写入的文件夹，不要直接在压缩包里运行。
3. 双击 `Launch-CS2Career.cmd`（便携启动器），或运行 `CS2Career.exe`。无需安装 Python，也不会默认打开浏览器。
4. 选择年代与角色，开始生涯；界面语言可在侧栏或设置中切换为中文／English。

桌面窗口需要微软 [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)。若提示缺失，请从微软官方安装。不要为了运行程序关闭安全软件。

**只玩生涯模拟，不需要启动 CS2 或安装游戏插件。** 亲自上场和自定义观战的配置见下文。

### 你可以做什么

- **成为职业选手：** 选择 2024／2025／2026 年代，接管职业选手，或以路人、青训、天才三种起点创建角色。调整位置、培养属性、管理状态，争取转会与荣誉。
- **经历完整赛季：** 报名比赛、查看晋级过程，点击战队与选手浏览阵容、近期表现和历史战报；查看年度 Top20、MVP、EVP 与五位置最佳阵容。
- **作出自己的选择：** 恋爱、转会、队内关系、伤病与退役等剧情影响生涯。经营提供取舍，工资和奖金自动结算，不必去邮箱逐封领钱。
- **收藏虚拟饰品：** 市场、库存、装备与开箱动画。全部使用游戏内虚拟资金，饰品不进入 Steam 库存，也不能兑现。
- **扩展自己的世界：** 使用纯数据内容包添加剧情、事件、赛事、饰品图片与局内聊天，不必把所有内容写进程序代码。

### 1.6.0 的主要变化

#### 更轻松地体验赛季

快速模式按队伍层次、档期与积分收益处理赛事邀请，减少重复参加低收益比赛。在一屏观赛台连续模拟本季，无需滚动长赛程：逐图揭晓比分，胜负改变背景颜色，整场结束突出玩家战绩，停留后自动继续。

决赛、需要选择的剧情、合同与 Major 休赛期仍会暂停，不会替玩家作决定。模式在季初／季末选择；普通模式的赛事自动模拟也不再逐场询问非决赛。快速模式不推送月报，其他纯通知尽量归档。

#### Major 后的生涯故事

主线集中在 Major 正式结束后的休赛窗口；普通生涯的恋爱线从首个 Major 结束后开始，假赛等比赛事件仍可在赛中触发。新增 **18 套 Major 出局故事**，覆盖六种出局阶段与不同实力预期。参加的 Major 仍展示 MVP、EVP 和最佳阵容。

生日等日历事件不等休赛期：队友生日当天出现选择，回应当天记录。快速模拟与跳过赛程遇到生日时暂停，处理后继续。

快速模式的属性点先积累，Major 后再集中分配；普通模式仍可随时加点。

#### 本地天梯与自定义对战

**Rank／FPL 是同一个本地 Bot 天梯，不是联网匹配，也不连接 FACEIT。** 固定使用当前生涯角色，按积分匹配另外九人；本局积分最高的两位担任队长，选人、禁图，再进入 CS2。选人完成后，按五位置能力为每队分配一名主狙、突破手、自由人、步枪手和指挥，不改变生涯位置。天梯积分与记录独立，不改变生涯 VRS、奖金或属性点。

自定义模式可安排双方各五名选手：控制其中一人，或作为观察者观看十名 Bot 比赛。自定义不计天梯分。

#### 评分、日历与英文

- 调整游戏内简化 VRS，减少重复低价值比赛的收益；修正切换位置造成不合理高评分的问题。
- 2024—2026 使用有来源的真实赛事选集；2027 起允许生成标明虚构的未来日历。不是现实赛程、阵容与规则的完整复刻，比赛结果由游戏产生。
- 核心界面及内置剧情提供英文；未翻译的第三方扩展、玩家改写文本和部分旧记录保留原文。

详细规则与可修改文件见 [1.6.0 指南](V1.6.0_GUIDE.md)。

### 亲自进入 CS2

需要 Steam、CS2，以及 [CS2 Bot Improver 的 Windows 运行包](https://github.com/ed0ard/CS2-Bot-Improver/releases)。换肤为可选功能；相关桥接插件随玩家 EXE 提供，完整人机增强运行包需另外获取。

1. 完全退出 CS2，在生涯的“游戏设置”保存游戏与增强包路径，按提示安装。
2. 从生涯比赛或对战大厅准备并启动比赛，再按提示进入指定地图。
3. 等待正式终场与完整十人战绩回传，再确认录入；不要仅因一方到 13 分就立即退出。

真人参赛时按本场阵容生成九名 Bot；自定义观察者模式生成十名。使用增强的 Low／Medium／High 基础预设，再结合生涯能力、位置与状态生成个人档案，不同步原增强的完整选手数据库。

局内教练与队友对白是**聊天框文字，不是真人语音或合成音频**。

仅用于 **`-insecure` 本地人机对局**，不要将这个插件环境用于官方匹配或联网服务器。安装会修改游戏插件及本场 Bot 资料；CS2 更新可能使插件失效，请核对对应版本的兼容说明，不要混装实验 DLL。完整配置与排错见 [玩家 FAQ](开始游玩-FAQ.txt)。

### 存档与已知限制

- 存档在 EXE 旁的 `save/`，个人扩展在 `extensions/`。更新前关闭生涯程序与 CS2，备份这两个文件夹；不同解压目录各用自己的存档，不要同时运行两个版本写同一份数据。
- 支持读取 1.5 的新版存档；更旧格式以程序提示为准，不要改格式强行载入。确认新版正常前保留旧目录与备份。
- 历史资料仍有简化和缺项，Career Rating 与 VRS 是游戏模型，不是 HLTV 或 Valve 官方完整算法。
- 战绩回传、接管归属、插件兼容性和长期平衡仍需持续实测。校验失败时保留现场与提示，不要立即开启下一场；缺失战绩不会用零填充，也不会根据比分猜测个人数据。
- 独立 Bot Lab 仍在研发，不是本版的安装前置，也不代表全图 Bot 行为已完成。

反馈请提交 [Issue](https://github.com/bel1ever1314/cs2-career/issues)，附版本、重现步骤、错误提示及截图。发送日志前检查个人信息；不要公开整个存档、Steam 配置、登录信息或私人路径。自动测试通过不等于全部实际 CS2 场景已验证。

### 开发与内容扩展

在 Windows 上使用 Python 3.12+，从源码根目录运行：

```powershell
py -3 -m pip install -r requirements-desktop.txt
py -3 main.py
```

源码默认同样打开独立桌面窗口，需要 WebView2。修改源码或内置资源后，已有 EXE 不会自动更新，需要重新打包；放在 EXE 旁 `extensions/` 的内容包可重启后在工坊启用，无需重编译。

- [开发者指南](DEVELOPER_GUIDE.zh-CN.md)：模块、状态与数据流；历史记录以其后修正为准。
- [扩展架构](EXTENSION_ARCHITECTURE.zh-CN.md)与[内容包模板](extensions/_templates)：剧情、事件、比赛阶段、赛事及饰品扩展。
- [英文翻译指南](ENGLISH_LOCALIZATION.md)：界面、故事和扩展文本的本地化。
- [构建与发布](PUBLISHING.md)：EXE、对应源码及不包含私人数据的发行包。
- [CS2 联调记录](CS2_INTEGRATION.zh-CN.md)：游戏接入与验证边界。

Python 测试入口是 `py -3 tools/run_tests.py`，会先隔离存档与扩展。纯 C# 回归位于 `tools/identity-tests`，不能代替实机测试。大部分开发文档目前为中文。

### 授权与致谢

本项目新增与维护的生涯代码采用 **AGPL-3.0-only**，见 [LICENSE](LICENSE)。原有 MIT 权利及第三方许可保留，详见 [第三方声明](THIRD_PARTY_NOTICES.md)。

感谢 ed0ard 与 CS2 Bot Improver 贡献者提供的模板及 BotBuy，Ian Lucas 的 Inventory Simulator，以及 Metamod、CounterStrikeSharp 和相关插件作者。历史换肤组件的源码恢复与重编译限制见 [恢复源码说明](RECOVERED_SOURCE.md)。

本项目与 Valve、FACEIT、相关赛事、战队及选手无官方关联。相关名字、商标和美术归各自权利人。发布玩家程序时请同时提供对应源码并保留许可说明；不要把个人存档、私人扩展、日志或缓存打进公开包。

---

## English

An unofficial CS2 player-career simulator. Start as an unknown prospect or take over a professional player, then build your career through training, transfers, matches, and choices off the server.

The focus is **a player's career with light club management**: simulate seasons in a standalone desktop app, or enter local CS2 bot matches and play for yourself.

[Download](https://github.com/bel1ever1314/cs2-career/releases) · [Player FAQ — Chinese](开始游玩-FAQ.txt) · [Changelog — Chinese](RELEASE_NOTES.md) · [Report an issue](https://github.com/bel1ever1314/cs2-career/issues)

> This source tree targets the **1.6.0 public beta**, with a Windows x64 desktop build. Check each Release's tag and notes: repository changes may not have been published yet. The separate Bot Lab experiments for Dust2 movement, crosshair placement, and team AI are **not included in this release**.

### Getting started

1. Open [Releases](https://github.com/bel1ever1314/cs2-career/releases) and download the player archive ending in `windows-x64.zip`, not `Source code`.
2. Extract the entire archive into a writable folder. Do not run it from inside the ZIP.
3. Launch `Launch-CS2Career.cmd` (the portable launcher), or run `CS2Career.exe`. Python is not required, and the app does not open a browser by default.
4. Choose an era and a player to begin. Switch to **English** using the sidebar language control or Settings (`设置` → `界面语言`).

The desktop window requires Microsoft's [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/). If it is missing, install it from Microsoft. Do not disable security software to run the app.

**Career simulation does not require launching CS2 or installing game plugins.** Playing or spectating actual CS2 matches requires the setup described below.

### What you can do

- **Build a player's career.** Choose the 2024, 2025, or 2026 era. Take over a pro, or create a player with an amateur, academy, or prodigy start. Develop attributes, try different roles, manage form, and pursue transfers and honors.
- **Follow a living season.** Enter tournaments and follow their progress. Open team and player profiles to inspect rosters, recent performances, and saved match reports. Follow the annual Top 20, MVPs, EVPs, and positional best teams.
- **Make choices off the server.** Experience romance, transfers, team relationships, injuries, and retirement stories. Management supports the career: wages and prize money settle automatically, without collecting payments from individual emails.
- **Collect virtual skins.** Browse the market, manage your inventory, equip items, and open cases. All funds and items are fictional; nothing enters your Steam inventory or can be cashed out.
- **Create content packs.** Extend stories, incidents, tournaments, skin images, and in-game chat through data-only packs rather than embedding all content in code.

### What's new in 1.6.0

#### A faster way to experience a season

Fast mode handles invitations according to team level, scheduling, and ranking value, reducing repetitive low-value tournaments. Its single-screen match viewer progresses through the season without a scrolling event list: map scores are revealed gradually, the background reflects wins and losses, and each series ends with a report highlighting your player before automatically continuing.

Finals, consequential story choices, contracts, and Major off-season windows still pause for your input. Choose the mode at the start or end of a season. Normal mode's tournament auto-simulation also stops asking about every non-final match. Fast mode suppresses monthly reports, while routine notifications are generally archived.

#### Stories around the Major off-season

Main stories arrive after a Major officially concludes. In a standard career, the romance storyline begins after the first Major; match-specific incidents, such as match-fixing approaches, can still occur during competition. **18 Major elimination stories** cover six exit stages and different expectations of your team's strength. Majors you participate in retain MVP, EVP, and positional best-team presentations.

Calendar occasions do not wait for an off-season: teammate birthdays and their responses occur on the day. Fast simulation and schedule jumps pause at a birthday for your choice, then continue.

In fast mode, attribute points accumulate during the season and can be spent after Majors. Normal mode still allows allocation at any time.

#### Local ladder and custom matches

**Rank/FPL is one local bot ladder, not online matchmaking or a FACEIT connection.** Ranked matches use your current career player and match you with nine others based on ladder points. The two highest-rated players become captains, draft teams, and veto maps before entering CS2. Each drafted team is assigned one AWPer, entry, lurker, rifler, and IGL based on role-specific ability, without changing career positions. Ladder results are independent of career VRS, rewards, and attribute points.

Custom matches let you select both five-player rosters. Control one participant or spectate all ten bots. Custom matches do not award ladder points.

#### Ratings, calendars, and English support

- Revised the simplified in-game VRS model to limit repetitive low-value wins, and corrected inflated ratings caused by switching roles.
- The 2024–2026 calendars use a sourced selection of real events. From 2027 onward, generated future events are labeled fictional. Calendars, rosters, and rules are not an exhaustive historical recreation; match outcomes are simulated.
- Core UI and built-in story content have English text. Untranslated third-party packs, player-edited text, and some older records retain their original language.

See the [1.6.0 guide — Chinese](V1.6.0_GUIDE.md) for detailed rules and editable files.

### Playing in CS2

You need Steam, CS2, and a compatible [CS2 Bot Improver Windows runtime package](https://github.com/ed0ard/CS2-Bot-Improver/releases). Skin changing is optional. Related bridge plugins ship with the player executable; the complete Bot Improver runtime must be obtained separately.

1. Fully exit CS2. In Game Settings, configure the game and Bot Improver package paths, then follow the installation prompts.
2. Prepare and launch a match from your career or the match lobby, then follow the instructions to enter the specified map.
3. Wait for the official match end and complete ten-player statistics before confirming the result. Do not quit merely because one team reaches 13 rounds.

A player-controlled match generates nine bots from its roster; custom spectator matches generate ten. Low/Medium/High use the enhancement's base presets, with individual profiles informed by career ability, role, and form. The original enhancement's full player database is not synchronized.

Coach and teammate dialogue appears as **chat-box text, not recorded or synthesized voice audio**.

Use this setup only for **local bot matches with `-insecure`**, not official matchmaking or online servers. Installation changes game plugins and match-specific bot data. CS2 updates can break compatibility: consult the relevant release notes and avoid mixing experimental DLLs. The [player FAQ](开始游玩-FAQ.txt) contains the full setup and troubleshooting instructions in Chinese.

### Saves and known limitations

- Saves live in `save/` beside the EXE; personal packs live in `extensions/`. Before updating, close Career and CS2 and back up both folders. Different extraction directories have separate saves. Do not run two versions against the same save simultaneously.
- New-format 1.5 saves remain readable. For older formats, follow the app's compatibility message rather than forcing a load by editing the schema. Keep your old folder and backups until the new version works.
- Historical data has gaps and simplifications. Career Rating and VRS are game models, not the complete official HLTV or Valve algorithms.
- Result import, bot takeover attribution, plugin compatibility, and long-term balance still need ongoing real-game testing. If validation fails, preserve the message and files before starting another match. Missing statistics are not filled with zeroes or guessed from the score.
- The separate Bot Lab remains experimental. It is not required to install this release and does not represent completed full-map bot behavior.

To report a problem, open an [Issue](https://github.com/bel1ever1314/cs2-career/issues) with the version, reproduction steps, exact error, and screenshots. Review logs for personal information first; do not upload entire saves, Steam configuration, credentials, or private paths. Passing automated tests does not establish that every live CS2 scenario works.

### Development and content packs

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

### License and credits

New and maintained career code is licensed under **AGPL-3.0-only**; see [LICENSE](LICENSE). Existing MIT rights and third-party licenses are retained in [Third-party notices — Chinese](THIRD_PARTY_NOTICES.md).

Thanks to ed0ard and the CS2 Bot Improver contributors for the templates and BotBuy, Ian Lucas for Inventory Simulator, and the authors of Metamod, CounterStrikeSharp, and the related plugins. See [Recovered source notes — Chinese](RECOVERED_SOURCE.md) for the historical skin components and their rebuild limitations.

This project is not affiliated with Valve, FACEIT, tournaments, teams, or players. Names, trademarks, and artwork belong to their respective rights holders. Distribute corresponding source with player builds and retain license notices. Keep personal saves, private packs, logs, and caches out of public archives.
