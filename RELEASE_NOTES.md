# 1.7.2（2026-10-07 更新）

这次把最近的修改整理回 1.7.2，直接更新原来的下载包，不再增加版本后缀。

- **一场比赛，逐图决定怎么玩。** 在电脑里点“推进”才开始，创建人物后不会直接开赛。可以先模拟一图，下一图自己进 CS2 或切到 RTS；图间保留战报和选择时间，随时暂停去处理日常。
- **退出后接着打。** 修复反复读取战绩时旧战报挤掉比赛入口，以及改用模拟后下一图仍显示“未完成”的问题。已完成地图保留，当前图可以重新进入、模拟或切换 RTS。
- **练出自己的强图。** 专项练图、训练赛和正式比赛会逐渐改变队伍的地图表现，长时间不打也会生疏；BP 会参考双方最新的强弱图。准备、选图和战术页补上地图实景展示。
- **补齐三个年代的开年阵容。** 2024、2025、2026 数据包清理占位选手，以开年首次完整阵容补齐名单，并显示实际阵容日期。新生涯使用新名单，旧档不改队伍和赛果。
- **队标和开局更完整。** 补充俱乐部队标，自建队伍可以上传队标与游戏内头像；抽取能力时能对照当前数值，启动画面也换成了生涯自己的界面。
- **场馆、声音与配枪。** 保留新的界面和配乐，小型十台电脑场地关闭背景音乐，修正自己的机位被占用；队友发枪按位置优先照顾主狙，进入 CS2 后降低后台 3D 场景的运行开销。Bot 姓名一直显示，隐藏 Bot 身份，不再来回切换。

上一轮 1.7.2 的更新也全部保留：

- **游戏内队标头像。** 天梯和自定义里的 Bot 使用所属俱乐部的队标，改用深色底；没有队标的保持原样，真人仍用自己的 Steam 头像。
- **更新战术兼容。** 适配这次 CS2 更新后的导航与朝向接口，修复有战术却提示接口未就绪的问题。
- **退出后继续比赛。** 修复已退出的 CS2 进程残留导致重新启动被拦住的问题，并调整队标头像的同步。
- **训练赛可以亲自打。** 补上进入 CS2、退出后继续和比赛回传的衔接，战报也调整为适应电脑界面的宽度。
- **配乐和场馆声音。** 加入俱乐部、宿舍和大场馆的新配乐；小型线下赛场保留环境声，不播放入场音乐。
- **整理存档与比赛流程。** 存档统一提交，断线后重新连接；系列赛逐图保存，加时打到胜负确定就结束。手机和电脑的共用页面也做了整理。

此前 1.7.2 的修改继续保留：

- **不同地图的战术分开加载。** 同名、同编号的战术可以在不同地图使用，切图时读取对应地图的战术库。
- **调整到点保位的兼容检查。** 支持已兼容接口的重新构建版本；生涯配套插件需要更新时，在进入比赛前提示安装。
- **可以选择自己的 VPK 模板。** 在设置中选择“我的 VPK 模板”，填写自己的 `botprofile.vpk`。读取其中的 Default／Template 参数，本场选手身份仍由生涯管理；比赛使用单独生成的 `career_botprofile.vpk`，不覆盖原文件。
- **Rating 不再封顶 2.5。** 新比赛按原公式计算，旧战绩保持不变。
- **修复比赛回传记录选择。** 完整的终场战绩不会再被退出后的残缺记录覆盖，同场同比分有完整副本时优先使用完整记录。

下载 `CS2Career-1.7.2-windows.zip`，完整解压后运行 `开始游戏.cmd`。继续旧生涯时，保留并复制原来的 `game/runtime/career/save/` 到新包同一位置。

**进入 CS2 前，关闭 CS2，在设置中点一次“安装填写目录的人机增强”，更新本版配套插件。已有完整人机增强包可离线安装。**

## English

The existing 1.7.2 downloads have been refreshed; no extra version suffix is used.

- Choose how to play each map: simulate, enter CS2, or command in RTS. Progression starts when you choose it at the computer, not immediately after creating a player.
- Fixed repeated result checks replaying old reports and stale CS2 exit state blocking the next map after simulation. Completed maps remain saved.
- Map practice, scrims, match results and inactivity shape team map form, which also informs veto decisions. Preparation, veto and tactic pages show map artwork.
- Completed the opening rosters for 2024, 2025 and 2026, removed placeholder players and added actual roster dates. Existing careers keep their rosters and results.
- Added more club logos, custom-team logo and avatar uploads, ability comparisons during the opening draw, and Career's own startup screen.
- Retained the new visuals and music, disabled background music in small ten-PC LAN rooms, reserved the player's seat, improved role-aware AWP drops, and reduced background 3D rendering while CS2 runs. Bot names stay visible while bot identity stays hidden.

The previous 1.7.2 refresh is also included:

- Club-logo bot avatars in ladder and custom matches now use a dark background, with default avatars retained for clubs without artwork. Human Steam avatars stay unchanged.
- Updated tactical navigation and look interfaces for the latest reviewed CS2 build.
- Fixed stale exited CS2 processes blocking match relaunch and improved avatar delivery.
- Added the CS2 handoff, recovery and result flow for booked scrims, with responsive match reports.
- Added club, home and large-arena music. Small LAN rooms use ambience without entrance music.
- Consolidated save commits, backend reconnection and per-map series progress; overtime stops when a winner is decided. Shared phone and computer pages were also reorganized.

Earlier 1.7.2 changes remain included:

- Tactics load from the current map's library. Names and IDs can be reused across maps.
- Updated hold-position compatibility checks for supported interfaces. Outdated Career companion plugins are detected before entering a match.
- Settings now accept your own VPK templates. Default/Template parameters are imported while Career manages match identities. A separate `career_botprofile.vpk` is generated without overwriting your source file.
- Removed the 2.5 Rating cap for new matches; the formula and existing records are unchanged.
- Complete final results are retained when later disconnect snapshots are incomplete, with complete copies preferred for the same match and score.

Download `CS2Career-1.7.2-windows.zip`, extract it and run `Launch-CS2Career.cmd`. Copy your previous `game/runtime/career/save/` into the same location to continue your career. Close CS2 and run the installer in Settings once to update the bundled companion plugins. Installation from a complete local Bot Improver package remains offline.

---

# 1.7.1（购买、发枪与战术更新，2026-10-04）

最近几轮的调整整理到 1.7.1，不再继续叠加很长的热修版本号。

- **买枪按位置来。** 步枪手和狙击手使用人机增强的 RiflePro／SniperPro 购买模板，保留道具购买与经济判断，不改选手能力。修正消音 M4 在模板里排在前面、实际却被跳过的问题；保下来的枪和捡来的枪不强换。
- **补上队友之间的发枪。** 冻结时间内持续检查队友的现有武器与余额，有余钱且已经有主枪的 Bot 可以给缺枪队友配枪，不再只在开局检查一次。发枪使用赠送者的钱，不动真人的钱。
- **战术可以守在终点。** 每个槽位可选择自动、守住终点或交回原生 AI。自动模式下 CT 到位后守点，T 继续推进；无线电、交火和下包按各自规则接手。
- **受伤时能先避险。** 执行路线或等待时受到伤害、需要躲避道具的队员会脱离当前导航，不再被旧节点拉回危险位置。
- **少一些无用提示。** 游戏内战术提示保留 `play <id>`，去掉下包后的“战术执行完毕”等多余消息。
- 保留离线安装已有官方人机增强、插件一键切换与退出恢复、比赛中断后继续或改用模拟／RTS、游戏内换肤与丢刀等功能，并整理个人设置与准星配置的保留逻辑。

下载 `CS2Career-1.7.1-windows.zip`，完整解压后运行 `开始游戏.cmd`。
继续旧生涯时，把原来的 `game/runtime/career/save/` 复制到新包同一位置。需要进入 CS2 的玩家，关闭 CS2 后在设置中重新执行一次“安装填写目录的人机增强”，带上这次的配套插件。

## English

1.7.1 brings the recent fixes together under one version number.

- Rifle and sniper roles use Bot Improver's RiflePro / SniperPro buying templates, preserving utility purchases, economy decisions and player abilities. Fixed the M4A1-S being skipped despite its template priority; carried and picked-up weapons stay untouched.
- Teammate drops now check current weapons and balances throughout freeze time, rather than only once at round start. Armed bots with spare money can equip an unarmed teammate. Human players' money is never spent.
- Each tactic slot can choose automatic behavior, hold its final position, or return control to native AI. Automatic mode holds for CT and continues native play for T, with radio, combat and bomb objectives handled separately.
- Damage and grenade avoidance can release an affected bot from tactical navigation instead of pulling it back into danger.
- Simplified tactic hints to `play <id>` and removed unnecessary completion messages after planting.
- Retained offline installation, plugin switching and automatic restoration, interrupted-match recovery, simulation / RTS alternatives, cosmetics and knife dropping, with personal settings and crosshair preservation improvements.

Download `CS2Career-1.7.1-windows.zip`, extract everything and run `Launch-CS2Career.cmd`. Copy your previous `game/runtime/career/save/` into the same location to continue your career. For CS2 play, close CS2 and run the installer from Settings again to apply this release's bundled companion plugins.

---

# 1.7.0-preview.3-hotfix.7（买枪补购修正，2026-10-04）

这次修正了人机有钱却没买主武器的情况。

- 正常购买后仍没有主枪、预算足够的队员，会补买 AK／M4；预算较低时保留 FAMAS、加利尔等选择。
- 狙位买不起 AWP 时会改用可负担的主枪，不再只等狙击枪预算。
- 买枪后检查武器是否真正进入该队员的库存，失败时不扣款，并尝试下一种可负担武器。
- 保留原生购买的时间窗口、手枪局、经济局、保枪与捡枪；冻结结束前再检查一次遗漏。
- 买枪诊断记录本回合的选择、预算和结果，不逐帧刷日志。

## English

- Bots left without a primary after normal buying now purchase an affordable AK/M4, with economical rifles available on lower budgets.
- Assigned snipers choose an affordable primary when an AWP is beyond their budget.
- Weapon delivery is checked before charging. A failed purchase can fall back to another affordable weapon.
- Native buying gets the first opportunity. Pistol rounds, eco budgets and carried weapons are preserved, with a final check before freeze time ends.
- Purchase diagnostics record choices, budgets and outcomes without per-frame logging.

---

# 1.7.0-preview.3-hotfix.6（换肤与丢刀修复，2026-10-04）

- 更新游戏内换肤签名，继续使用玩家已经装备的 CT／T 饰品。
- 将旧签名备份移出自动加载目录，开赛时避免旧缓存覆盖兼容签名；安装和开赛不需要联网。
- 本地比赛补回丢刀设置，换肤仍需在设置中手动开启。
- 保留插件一键切换、退出恢复、比赛接续和此前的买枪调整。

## English

- Updated in-game cosmetic signatures for your equipped CT/T loadouts.
- Kept old signature backups out of the automatic loader and prevented stale caches from replacing compatible signatures. Installation and match preparation remain offline.
- Restored knife dropping in local matches. Cosmetic switching remains opt-in.
- Retained plugin switching, automatic recovery, match resumption and the purchasing improvements.

---

# 1.7.0-preview.3-hotfix.5（插件切换与购买调整，2026-10-04）

这次把退出比赛、插件切换和人机买枪一起整理好了。

- 设置里可以一键开启插件或恢复普通 CS2 环境，从生涯程序进入对局后，退出 CS2 会自动恢复。
- 中途退出可以继续原来的比赛，也可以改用逐图模拟或 RTS，不需要重新安排名单和地图。
- 补齐瞄准方式、道具频率、人机身份显示和局内对话选项，保留原来的难度设置。
- 经济足够时优先购买 AK／M4，经济不足时仍可选择 FAMAS、加利尔等主枪；保枪与捡枪不强换，狙位和队友配枪继续保留。
- 修正拿刀时被误判没有主枪，以及赠送装备花掉自己必要预算的问题。

完整解压 Windows 包，运行 `开始游戏.cmd`。继续旧生涯时，保留原来的 `game/runtime/career/save/`。

## English

This update brings together match recovery, plugin switching and bot purchasing.

- Enable local plugins or restore normal CS2 with one click. Career also restores the normal environment after its CS2 match exits.
- Resume an interrupted match with the existing roster and maps, or finish it through map-by-map simulation or RTS.
- Added separate aim, utility, identity and match-chat settings alongside difficulty.
- Bots prefer AK/M4 purchases when affordable, keep economical alternatives, and preserve carried weapons, pickups, sniper roles and team drops.
- Fixed primary-weapon detection while holding a knife and kept essential personal equipment budgets out of teammate gifts.

Extract the complete Windows archive and run `Launch-CS2Career.cmd`. Keep your previous `game/runtime/career/save/` to continue your career.

---

# 1.7.0-preview.3-hotfix.4（3D 游玩流程修正版，2026-10-03）

这次把朋友试玩时遇到的安装、鼠标和进场馆问题一起整理了一下。

- 安装人机增强直接使用已经下载好的完整官方发行包，战术、比赛回传和兼容组件随程序提供。安装无需联网，原发行包也不会被改动。
- 检查上游更新改为独立按钮，只在主动点击时联网，不自动下载或替换插件。
- 调整便携版后台启动与开局流程，让完整解压后的程序能连接本地生涯后台，并先完成角色创建。
- 游戏内换肤默认关闭；文本框使用清晰的箭头指针，输入和选中文字时不再丢失鼠标。
- 从门口前往比赛时显示准备状态；有待处理事项可直接打开手机，处理后继续出发，场馆与比赛准备之间的提示更清楚。
- 保留新版人机增强、无线电接手自定义战术、比赛回传和已有存档。

完整解压 Windows 包，运行 `开始游戏.cmd`。继续旧生涯时，将原来的 `game/runtime/career/save/` 复制到新包的同一位置。

[下载本次更新](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.7.0-preview.3-hotfix.4)

## English

This update brings together the installation, cursor and venue-entry fixes from recent playtests.

- Install directly from a complete official Bot Improver release you have already downloaded. Career's tactics, result reporting and compatibility components are included, so installation works offline and leaves the original release unchanged.
- Checking upstream updates is now an explicit action and never downloads or replaces plugins automatically.
- Updated portable backend startup and the opening flow, including character creation before entering the career.
- In-game skins start disabled. Text fields retain a visible pointer for typing and selection.
- Doorway travel shows match-preparation progress and lets you open pending replies on the phone before continuing to the venue.
- Existing bot-runtime support, radio handoff, match reporting and saves are retained.

Extract the entire Windows archive and run `Launch-CS2Career.cmd`. Copy `game/runtime/career/save/` from your previous package to the same location to continue your career.

---

# 1.7.0-preview.3（人机增强兼容与无线电指挥，2026-10-03）

这次接上了新版人机增强，也把玩家无线电和自定义战术之间的交接补好了。

- 安装流程适配 Bot Improver 1.4.5，更新行为、瞄准、状态和道具组件，保留生涯自己的买枪、战术导航与朝向接口。
- 自定义战术执行中，队友可以响应玩家的行动无线电。比如本来要守 20 秒，收到“跟随我”“撤退”等有效指令后，会立即结束旧战术和等待。
- 无线电接手后，旧节点、延迟回调和守包任务不会再把队友拉回去；下一回合可以重新选择战术。普通报点、确认与庆祝消息不取消路线。
- 比赛仍按当前九人或十人名单生成档案，加入新版匿名行为资源，不使用上游的固定职业选手名单。
- 整理源码包、普通 Windows 包与朋友测试整合包。整合包随附人机增强，通过设置里的安装按钮准备真实 CS2 对局。

普通 Windows 包完整解压后运行 `开始游戏.cmd`。进入真实 CS2 时，在设置中填写 Steam、CS2 和已解压的人机增强目录，再点击安装。更新时保留 `game/runtime/career/save/`，就能继续原来的生涯。

[下载本次更新](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.7.0-preview.3)

## English

This update adds Bot Improver 1.4.5 compatibility and connects action radio commands with custom tactics.

- Updated behavior, aim, state and utility components while preserving Career's purchasing, navigation and look controls.
- Accepted action radio commands immediately end the team's old tactic, including waypoint waits. Information and acknowledgement calls do not interrupt it.
- Old tasks and deferred callbacks no longer reclaim bots after a radio handoff. Tactics can be selected again in the next round.
- Match profiles keep the current nine- or ten-bot roster and include the new anonymous behavior resources.

Extract the Windows archive and run `Launch-CS2Career.cmd`. Keep `game/runtime/career/save/` when updating to continue your career.

---

# 1.7.0-preview.2（3D 预览修正版，2026-10-03）

谢谢大家这两天的试玩。这次主要把进入比赛、返回场馆和使用自定义战术的流程接顺了一些。

- 中途退出 CS2 后，可以回到原来的比赛场馆，保留之前的名单、地图 BP 和比赛状态。
- 战术保存后，在 CS2 关闭时会同步到当前已经准备的对局；战术室显示本场快照，并提供手动同步按钮。不用重新画路线或重置比赛。
- 更新导航与朝向兼容检查：不再只因版本或整个文件变化就拒绝启动，会核对实际需要的接口与相关依赖。
- 补充战术保存、复制指令和同步状态的反馈及英文显示。
- RTS 补上 Nuke、Vertigo 的分层地图与楼层通路。
- 增加青训、普通、豪门俱乐部及不同规模场馆，俱乐部可以购买设施升级，自己的房间可以购买和摆放家具、调整墙面与地板。
- 补充 3D 英文界面，调整对话框、按钮反馈、赛事到场提示和俱乐部冠军陈列。

下载 Windows 包后完整解压，运行 `开始游戏.cmd`。继续旧生涯时，将原包的 `game/runtime/career/save/` 复制到新包的同一位置；手动存档也保留在这个目录里。旧包和旧存档可以先留着。

[下载本次更新](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.7.0-preview.2)

## English

This update smooths out returning to an arena and using custom match tactics.

- Return to the original arena after leaving CS2, keeping the roster, map veto and match state.
- Saved tactics sync to the prepared match while CS2 is closed. The tactics editor shows the match snapshot and includes a manual sync button.
- Navigation and look compatibility checks now inspect the required interfaces and dependencies instead of relying only on a whole-file version match.
- Added clearer save, copy and synchronization feedback, including English text.

Extract the Windows archive and run `Launch-CS2Career.cmd`. To continue your career, copy `game/runtime/career/save/` from the old package to the same location in the new one. Keep your old copy as a backup.

---

# 1.7.0-preview.1（第一次走进 3D 生涯，2026-10-02）

这一版把生涯搬进了小鸡的宿舍、俱乐部和赛场。拿起手机看看队友的消息，坐到电脑前安排比赛，到了比赛日再走向自己的机位。想先让这些日常和比赛连起来，慢慢长成一个可以住进去的职业生涯。

这是首次 3D 预览版；1.6.0-hotfix.1 桌面正式版继续单独提供下载。

## 角色和俱乐部生活

- 新开局可以选择年代、抽取队伍与选手能力，也可以接管职业选手。小鸡形象支持羽毛、腹部、喙、鸡冠与队服配色，调整时实时预览。
- 宿舍与俱乐部支持走动、使用电脑和物品，与队友、教练及工作人员交流；靠近门口选择目的地，前往不同场所。
- 手机接入邮件、聊天、日历、赛事、个人资料、属性加点与设置。生日选择后的故事和队友回复可以留在联系人的聊天里。
- 日历推进增加睡觉过场；电脑接入手动存档与读档，方便按自己的节奏继续生涯。

## 电脑、战术和比赛

- 电脑接入职业比赛、快速赛季、赛事与选手资料、战报和新闻、饰品市场、经营、转会、阵容合同、训练、职业榜单与扩展工坊。
- 本地天梯使用当前生涯角色，展示队长选人、地图 BP 和开场阵营。自定义可以安排双方五人、控制选手或观战；两者均保留各自的对局记录。
- 职业比赛支持地图 BP、逐图模拟和真实 CS2 开赛与战绩回传。比分逐步揭晓，战报展示双方十人数据并突出自己的角色。
- 会议室白板接入多地图战术编辑：五个槽位的路线、顺序、停留、观察方向、跑动和静步，以及缩放、平移、复制和导入导出。
- RTS 接入职业、本地天梯和自定义，支持 Dust2、Mirage、Inferno、Ancient、Anubis、Overpass、Train、Cache 八张地图；可以在指挥、本人操作和观战之间切换。

## 场馆与荣誉

- 小型 LAN 和大型场馆接入到场、队友入座与玩家机位流程。
- 冠军、MVP、EVP、最佳阵容及年度 Top20 以赛事新闻和报纸形式展示。
- 年度颁奖厅展示 Top20 与前三名登台领奖；自己的角色入围时，可以亲自走上舞台。

## 下载与继续游玩

- Windows 运行包：`CS2Career-1.7.0-preview.1-windows.zip`，随包提供 Godot 与 Python 后台，解压后运行 `开始游戏.cmd` 或 `Launch-CS2Career.cmd`。
- 对应源码包：`CS2Career-1.7.0-preview.1-source.zip`，包括生涯内核、Godot 客户端、RTS、资源生成源码、测试与许可。
- 生涯模拟和 RTS 可直接游玩。进入真实 CS2 需要自行安装 Steam、CS2，并另行获取兼容的人机增强运行包，插件用于 `-insecure` 本地人机对局。
- 存档位于 `game/runtime/career/save/`，手动存档在其 `manual/` 目录；更新前备份自己的进度。
- 饰品 3D 检视与直接贴纸编辑提供默认关闭的可选接口，需要玩家另装对应工具和适配器。
- 更新中英文首页和启动说明，方便第一次来的玩家找到下载和操作入口。

[下载 3D 预览版](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.7.0-preview.1) · [下载 1.6.0 正式版](https://github.com/bel1ever1314/cs2-career/releases/tag/v1.6.0-hotfix.1)

---

# 1.6.0（生涯节奏与 Major 休赛期）

## 1.6.0-hotfix.1：生日触发与天梯分工修正版（2026-09-27）

- 队友生日恢复为当天触发，回应当天记录；普通推进、跳到下一赛事和快速模拟跨越生日时，先停在当天等待选择。
- 主线恋爱、NA 挑战等仍在 Major 后的休赛期进行。生日选择带来的属性点照常获得，快速模式仍只能在休赛期使用。
- 已被错误延后的生日提醒解除延后并保留原日期；已完成的选择不重演，不自动发放或重复结算奖励。伤病和恢复通知按发生日期记录。
- 同步此前的天梯角色绑定和五位置分工修复：天梯使用当前生涯角色，双方各分配五个不同位置；自定义保持自由选择。
- 保留中文在上、英文在下的主页说明，补充 FAQ 与对应源码。此修正版不改 CS2 插件，也不接入独立 Bot Lab。
- 生日与关联流程 95 项定向测试、桌面 EXE 隔离自检通过；不代表新增 CS2 实机或长期平衡验证。

## 天梯角色绑定与五位置分工（2026-09-27）

- 天梯固定使用当前生涯角色，移除临时换人入口，后端同时校验身份；自定义仍可自由选人或旁观。
- 选人结束后，按每名选手的五位置能力给每队分配不同位置，最大化队伍整体适配，不按队长身份强制指挥。
- 大厅显示本场位置，CS2 Bot 档案与战报沿用同一分配；不修改生涯位置、属性、积分或既有战绩。
- 旧待回传房间保留原身份、位置和比赛标识；新旧生涯身份不一致时不能再开赛，但仍可录入已有结果或关闭房间。

## 队内对话与开局恢复（2026-09-27）

- 离线暖身显式启用并等待双方名单就绪；冻结结束时复查首回合初始化，解决 `round_start` 早于真人入队后漏记第一回合的问题。同一回合不重复重置账本。
- 比分可靠时仍可播放手枪局和落后鼓励；个人统计不可靠时跳过五杀、残局和引用个人数据的台词，不清除战绩录入错误或伪造缺失数据。
- 接收者按已绑定的真人身份确定，不依赖可变的 Bot 外观标记。日志增加对白加载、跳过原因、规则命中和发送槽位；终场及换回合取消旧对白。
- 回归与打包检查通过不代表实机验证完成；请在新对局检查第一回合结束时的队内文字。

## BotHider 身份兼容修复（2026-09-27）

- CareerMatch 首次绑定选手时只接受本场唯一的内部 BotProfile 名称，不再优先采用可能随机分配的虚拟 SteamID。完成绑定后，昵称、头像、换边和接管不改变该身份。
- 暖身阶段核对双方具体五人名单；只有人数正确但成员串队时，不再放行正式比赛。记录初次绑定来源、观察到的名字与阵营，便于排查插件兼容问题。
- 增加虚拟身份错配、延迟命名、重复档案名、观察者及换边回归。旧失败回传不自动修补或计入；新对局仍需实机验证。

## 独立对战大厅与终场对话修复

- Rank／FPL 合并为同一个本地天梯：使用当前生涯角色，按分段随机匹配九人。本局积分最高的两人担任队长，蛇形选人后交替禁图、选择阵营；只有你当队长时才需手动决策。
- 积分绑定选手身份；职业角色有独立初始分，自建路人／青训／天才分别为 1400／2200／3000。匹配后冻结积分与名单，刷新不会重抽；旧天梯文件备份后合并，保留历史及待回传比赛。
- 重做对战大厅：个人积分卡、双队阵容、选人进度和地图 BP 卡片；中英文与小窗口适配，局部更新避免选择框闪动。
- 新增自定义双方五人阵容；可控制其中一人，或以观察者身份看十名 Bot。自定义只记录战绩，不发天梯积分。
- 观察者比赛使用专用十人 BotProfile、十人身份清单和旁观者安排；原生涯仍是真人＋九名 Bot。
- 正式终场取消所有尚未播放的过程对白；新回合也不续播上回合队列，避免打完还收到教练过程提示。
- 自动检查覆盖房间恢复、重复录入、比分队伍归属、观察者身份、中英文界面与存档隔离；实际十 Bot 对局及终场聊天仍需新对局实测。

## 快速模式胜负反馈与全场战报

- 每张地图结束，以玩家所在队伍为准切换绿色／红色背景，同时显示胜负文字。
- 系列赛结束自动显示双方十人全场战绩，按稳定 ID 高亮玩家行，并用金色摘要突出玩家 K/D/A、ADR 和 Rating。全场数据从各图原始统计汇总，不平均各图 Rating。
- 战报默认停留 6 秒后自动继续，可跳过或暂停；决赛、剧情、Major 颁奖仍需处理，不会被自动回答。
- 本季战绩增加绿胜红负圆点，每个系列赛一个点，按先后排列；刷新不重复计数，转会不继承新队以前的比赛。

## 快速模式一屏观赛台

- 快速模式不再展示需要滚轮浏览的全年赛事长列表；固定显示当前对阵、比分、赛季进度、上一场和下一站，自动切换比赛。
- 保留逐图慢速揭晓、暂停与跳过动画；决赛、必要剧情和 Major 颁奖仍暂停等待玩家。普通模式保留完整赛程浏览。
- 中英文与小窗口使用同一套紧凑布局，不因赛事数量增加而拉长页面。

## 快速模式比分节奏

- 本队比分由立即显示终场改为逐图揭晓，每图间隔约 1.2 秒，最终比分停留约 1.8 秒。
- 可跳过本场比分动画或立即暂停推进；比分播放只展示已保存结果，不重复模拟或结算。
- 决赛、剧情和 Major 颁奖仍需玩家处理；播放中不刷新整张赛程，避免提前泄露终场和反复闪动。

## 剧情英文与 Major 颁奖补充

- 内置恋爱、NA 留学生、队内争执、舆论、生日、伤病、转会、里程碑与退役剧情补上英文正文、标题和选项；家书与事件反应同步补译。
- 英文显示不改变分支、奖励或概率。可识别的旧记录只做显示翻译，不重写存档；玩家改写和未翻译扩展保留原文。
- 参加的 Major 仍弹出 MVP、EVP 和五位置最佳阵容，正常与快速模式均保留；其他赛事纯通知继续归档。不会因颁奖重复发奖励，也不会追弹转会前的冠军记录。

## 整季模拟修订

- 快速模式一次推进到本季结束，使用一屏观赛台；只在季初／季末选择模式，取消邮箱里的模式入口。
- 普通模式与快速模式的自动比赛均只询问决赛；有后果的剧情选择与Major培养窗口仍保留。
- 快速模式不推送月报、不新增月报邮件；正常月报按分区展示。其他纯通知不再逐个弹窗确认，奖励照常结算，不能因忽略通知重复获得。
- Major剧情删除直白的“赛前预测／符合预期”台词，保留后台实力判断和18套不同场景。
- 补齐月报、Major新闻和常见动态的英文显示；正文翻译与赛季状态保持一致。

## 基础升级

- 新增快速生涯：按队伍层次、档期与积分收益处理邀请；减少重复 CCT，遇到选择性剧情、决赛和 Major 休赛期暂停。
- 快速模式属性点累计保留，仅 Major 后休赛期允许手动／自动使用；普通模式保持随时加点。
- 恋爱线改在首个 Major 结束后的休赛窗口启动，主线统一在该时段投递；假赛等比赛事件仍即时触发。
- 新增 18 套 Major 出局场景，按六个出局阶段与赛前实力预期区分，并提供中英文文本。
- 调整简化 VRS，限制重复低价值胜场贡献；归一化位置评分，修复换位置虚增能力。
- 2024／2025／2026 改用带来源的真实赛事选集，未来虚构日历明确标记；已完成比赛不重写。
- 增加可扩展的系列赛／地图阶段接口、阶段剧情示例、长选项换行与主要界面英文切换。
- 不包含未完成的沙二视角增强；独立 Bot Lab 与 Career 发布版本继续分开。

本节以下为旧实验版记录，不表示对应 AI 实验被加入 1.6.0。实际 CS2 对局与长期平衡需另行实测。

# 1.5.0-natural-clips.1（连续短动作执行器试验）

- 新增独立的连续动作数据契约和执行层：任务选择原位片段，逐帧匹配移动与视角，不替换难度、身份或战绩逻辑。
- 修复速度在归一化中被自身抵消的问题；使用真实速度反馈和450原生命令标尺。视角从动作起点接管，而不是到位后才接管。
- 保留引擎碰撞与重力，不使用DemoTracer整包的强制位置回放。场景变化、接敌、接管或偏离时释放动作。
- 五张Demo重提B洞/中路快照，另核对17张的中门窗口，产生125段候选动作。11段合格跳跃均为持刀样本，不强套拿枪Bot。
- 接入一次有助跑的明确跳跃输入，取消同动作重复起跳；原生随机跳跃脱困策略与动作控制权分离。
- 新增数据、数学回归及运行时失败原因日志。实机碰撞/视角控制权/起跳和观感尚待验证；不宣称全图已职业化。
- D盘独立试验EXE，不自动迁移或改写玩家存档，不更新GitHub正式版。

# 1.5.0-natural-corners.1（B洞成套动作实验版）

- 沙二自然模式新增B上层洞柱子与B洞出口的配对动作，区分朝B进攻与从B返回。
- 从17份现有Demo重新提取短动作：保留实际起点、观察目标、横向移动与真实退回，不再把平均位移配给任意瞄点。
- B洞用对准、横移、停稳观察、下一角或退回的顺序执行；晃身与逐角搜点分开。近处有队友时让路，移动受阻时取消。
- 新动作采用有限时间转向与稳定世界坐标预瞄。枪法和难度继续交给原生增强AI；只在局部动作期间接管视角与移动。
- 通行检查使用导航脚印覆盖与实际位移监测，尚未包含物理射线/完整身体碰撞扫描，不能据此保证所有掩体与视线正确。
- 按用户要求，仅生成资源、编译并打包；未执行自动回归、EXE自检或CS2实机验证。

# 1.5.0-natural-phase.1（沙二阶段与任务重构测试版）

- 自然行为改为“团队阶段 → 个人任务 → 原生寻路 → 到位后预瞄/peek”，阵型分配现在实际驱动Bot前往岗位。
- 出生区是经过区域，不再从附近随机选择架枪点；只有距离、速度和连续停稳均通过后才锁定视角。
- 沙二双方按开局展开、中期渗透/防守、后期守包/回防/残局切换；T方按A控、B控或默认控图分配任务。
- 职业节点先与当前地图导航网格核对。长距离移动交给CS2寻路，插件只在节点附近控制最后48单位，任务停滞或超时会释放。
- 预瞄使用Bot实际眼睛高度；移动到位前保留原生视角，避免瞄墙慢慢挪动。
- 辅助感知以全队区域情报共享：可见、交火、伤亡、声音和炸弹进入威胁板；跨区调人仍需两名确认敌人、炸弹或防守者阵亡。
- 真人接管只释放对应Bot的自然控制，不再关闭整回合所有Bot的任务系统。
- 本测试版关闭CT主动深推；完成可达的出发与撤退路径后再恢复小比例双人前压。

# 1.5.0-natural-ct.4（沙二 CT 威胁通道测试版）

- 使用 17 张职业 Dust2 Demo 的真实 attacker→victim 事件生成 schema v3 聚合行为包。
- 职业节点改用真实样本代表站位，加入预瞄通道、暴露通道、团队覆盖和安全退回关系。
- 自然控制只在当前掩体附近最多微调 48 单位；单一 B 区信息不会无故拉走中路防守者。
- 视野、交火、伤亡、声音和炸弹信息按公平时限共享；跨区支援需要两名敌人、炸弹或防守者阵亡。
- CT 主动前压仅在无警报时允许两个具有深区目标的 Bot；其他 CT 深推继续拦截。
- 本候选先启用 CT 防守，T 方暂用经典增强行为，等待 CT 实机观察后再加入顺序清点。

# 1.5.0-assistchat.1（生涯助攻规则与场内台词，公开测试版）

- 经玩家确认，多候选伤害助攻采用最高累计伤害、同分先达到者规则；每个引擎助攻事件只记一人。闪光冲突和证据缺失仍禁止猜测，不承诺完全还原引擎助攻。
- 新增五杀四人夸奖剧情、上下半场手枪局胜负台词、存活赢下1vX的残局夸奖，以及落后6分的三条教练随机台词。
- 扩展接口增加场景 `distinct_speakers`、条件 `clutch` 和占位符 `clutch_player`；保留旧包行为。
- 171项C#检查和26项Python测试通过；新EXE内置插件和台词已核验。实际CS2新对局尚待验证，旧失败回传未改动。

# 1.5.0-assistfix.1（接管后的助攻候选修正，本地候选）

- 助攻归属先排除已确认的击杀者和死者，再判断候选是否唯一。修正“先控制A打伤、后控制B击杀同一敌人”将最后一枪也计为助攻候选、错误阻止整场录入的问题。
- 保留Bot被接管前的贡献和同回合先后控制过的选手索引；引擎以原Bot或真人控制器报告助攻时可查到同一份实际贡献。索引不是计数，不会重复加助攻。
- 只剩击杀者的贡献不发放助攻；仍有多个非击杀者候选或缺失接管贡献证据时继续阻止猜测归属。击杀、死亡、伤害和比分映射不变。
- 增加 assist 审计日志，记录原始助攻控制器、击杀者、死者、闪光标记、贡献候选及判定结果。旧日志未保存原始助攻字段，不声称能据此无损恢复此前失败对局。
- 新增19项助攻回归，加上原有身份/接管/阵容/聊天共156项纯C#检查，在游戏所用.NET 10.0.3运行时通过；插件编译通过。仍需新的CS2实际对局验收，不自动发布到GitHub，不修改旧回传或玩家存档。

# 1.5.0-steady.1（原位刷新与保留模拟面板，本地候选）

- 新增 desk/dom.js 页面局部更新器，概览、阵容、经营、邮件、日历、排名、资料、战报、赛事、饰品、训练与设置的常规刷新复用原有节点；不改写全局 innerHTML 行为。按稳定键保留邮件、饰品和比赛节点，未变化的图片 src 不重写。
- 模拟途中遇到剧情，保留整个观赛面板与赛程图，将待选择剧情放在上层。选择继续后复用同一面板；亲自打、稍后决定、结束、错误或非剧情阻塞才退出。未选择期间不推进比赛，不重画后方主页面。
- 新增下一轮时原位加入比赛节点，保留旧节点、队标、缩放和平移。同一个剧情不会重复重建、打断揭晓动画；新剧情仍正常切换。
- 页面重新绑定操作事件，避免复用按钮时残留旧命令；模拟窗口存在时禁用后台导航和推进快捷键，仍保留当前窗口的停止及剧情选择。
- 7个定向前端脚本、全部桌面脚本语法检查及隔离 Chromium DOM 回归通过。浏览器回归包含20次连续刷新、图片/节点身份、输入焦点/光标、控件状态、重排、新增赛事节点、剧情层级及连续暂停/继续。未宣称完成成品 EXE/WebView2 的主观视觉验收，仍需玩家确认实际观感。
- 不修改存档、比赛统计、平衡数值或作者剧情内容；新 EXE 与旧版并存。

# 1.5.0-smooth.1（本队路径与减少闪动，本地候选）

- 自动模拟图只显示本队参加的系列赛、每场直接对手及本队晋级/败者路径。不展开对手参加的其他比赛，不虚构未产生的对阵。普通赛事资料页仍可查看完整晋级图。
- 每图大比分变化原位更新数字和胜者标记；不重建节点、队标图片或整张图。本队新增对阵才更新布局，保留缩放和平移；其他队伍赛果更新不重绘本队路径。
- 自动模拟请求仅更新内存状态和剧情队列，不再反复刷新遮罩后面的比赛/赛事主页面。结束或暂停后统一显示最新页面。
- 资料刷新不先清空内容或反复显示加载占位；同页刷新保留当前滚动，切换资料期间旧内容不可点击，过时请求不再影响后来打开的页面。
- 避免重复读取现代战报详情，侧栏内容无变化时保留原有节点与队标，减少不必要的重绘。
- 6个定向前端脚本通过，覆盖本队过滤、数字原位更新、图视角保留、加载期间保留内容、模拟顺序和暂停、赛事图、历史资料、CS2轮询及剧情确认。未声称完成成品桌面的视觉实测，最终观感由玩家确认。

# 1.5.0-assist.1（邀请/属性点辅助与赛事自动模拟，本地候选）

- 邮箱增加按Major、Premier、T1、T2、CCT、预选赛/RMR分类的手动/自动接受/自动拒绝规则，默认手动；保存后处理现有未回复邀请，后续发出的邀请也按规则处理。合同、假赛来信、原战队邀请不自动回答，已作决定不追改。
- 个人属性面板增加指定维度或均衡补短板的自动加点。立即投入现有点数，并在后续写操作结算新点数；复用手动加点的上限和能力刷新，不增加奖励、不改变费用。方向满100后自动关闭、弹窗提示、保留剩余点数。
- 比赛页和赛事页增加“自动模拟本届赛事/继续”。复用赛事分支图，高亮本人战队，按真实保存的地图胜者依次展示系列赛比分（例如0:1、1:1、2:1）。赛果先保存、后播放，不重抽。
- 每次只执行一个有限业务步骤。普通事件、未处理合同/假赛/债务、暂停参赛、其他赛事等待本人比赛、已有CS2待回传时停止。事件由玩家确认；处理完本次队列后可继续自动模拟。停止或关闭窗口不继续在后台推进。
- 本队生死战（瑞士轮两负、GSL淘汰/决胜局、淘汰赛）及决赛，在开赛前弹剧情窗口：亲自打、仅模拟当前这一场、稍后决定。单场授权按年份/赛事/比赛/当前战队绑定，不延伸到下一场生死战。选择稍后不会跳过该场。
- 新增data/tournament_moments.json文案接口，沿用story_queue与ack_story确认通道；Career.assist为可选schema_version=2字段，旧档默认关闭辅助。API使用现有会话校验和写锁，并通过步骤编号和请求回执防重放推进。
- 42项后端定向检查通过（包括实际四队赛事业务循环），4项前端脚本通过（大比分顺序、串行请求、暂停/继续、剧情确认、半场观赛、图表）。未代玩家进行成品桌面和CS2实际游玩测试。

# 1.5.0-matchday.1（分半场观赛与Major分阶段，本地候选）

- “跳过按数值结算”入口改为模拟观赛：每图逐回合跳分，第12回合半场休息，点击后继续下半场；加时每3回合休息，支持暂停、2倍/4倍速及跳到战报。
- 先生成并保存唯一赛果，前端只揭晓保存的round_end记录。播放期间不提前展示终场比分、奖励或剧情；关闭/跳过不会重新抽取或重复结算。原CS2实战地图保留，不重新模拟。
- T1与Major的新决赛统一BO5（游戏规则，包括历史年代）；补齐五图BAN/PICK和三图获胜结束条件，T2/CCT/预选赛不改。
- 2025起Major为32队：末16种子进入第一阶段，9—16种子进入第二阶段，前8种子进入第三阶段。各阶段16队、三胜晋级/三负淘汰，各晋级8队，再进八强淘汰赛。2024年代为24队、两个瑞士阶段。
- Major各阶段独立战绩/对手记录，常规BO1、晋级或淘汰局BO3。赛历从原决赛日期向前展开18天（2024为13天）；这是游戏日程安排，不宣称复刻现实逐日赛程。
- 赛事页可切换第一/二/三阶段与淘汰赛，只显示已生成的配对。历史归档保留各阶段参赛名单与状态。
- 存档里未开始的Major更新；已经开打或完结的赛事不重排、不重算。未开始的T1/Major决赛可更新为BO5，已加载CS2/保存地图的决赛保持原赛制。
- 本次8项Python定向检查通过，覆盖40个固定种子/年代组合完整Major赛程、BO5实际模拟、保存后返回观赛数据及重复提交拒绝；前端观赛、图表、CS2轮询3个脚本通过。未代替玩家完成桌面/CS2实际对局体验。
- 额外执行的67项扩展回归有65项通过，2项旧剧情测试未通过：NA冠军夹具缺少team_id；伴侣安慰断言固定短语，与现有多版本文案不匹配。未为通过测试覆盖作者剧情文本，这两项不计入本次通过结论。

# 本次一并打包：Major决赛失利与普通退役文案

- 在career_arcs.json的chapters.major_final_loss新增可编辑章节；只在本人正式出战并输掉Major决赛后触发，同届不重复，排除弃权。
- 普通主动退役文案与判定迁入data/career_retirement.json。老将默认需同时达到28岁、首张已保存正式地图起满5周年、5个活跃参赛年份、200张正式地图。
- 单个冠军不再等于老将；有荣誉但未满足年资条件使用独立离场文案，普通文案不再虚构漫长征战或衰老。
- 保留用户自行修改的恋爱等文案。这批源码现随Matchday版一起打包；自行打包说明见“自己改剧情和打包.txt”。

# 1.5.0-storage.1（未来备份压缩，本地候选）

- 新安全快照改为流式gzip无损压缩，逐文件核对SHA-256和原始大小，完全相同的连续快照复用。
- 旧备份、活动存档、历史战报、库存与扩展不改动，不做旧备份迁移或自动删除。
- 中断操作和失败回滚同时支持旧JSON与新JSON.GZ备份；整对文件全部验证成功后才开始替换。
- 移除旧Tk建档入口的重复备份；活动JSON格式与schema_version=2不变。
- 10项隔离存储检查通过，包含损坏保护、旧备份恢复、重复快照、建档备份及转会失败/中断恢复。未跑玩家生涯或CS2对局。
- 这是磁盘占用优化，不是运行内存的历史数据懒加载。已有备份按玩家要求全部保留，旧目录不会立即变小。

# 1.5.0-stories.2（新闻、家书与NA双条件，本地候选）

- NA首次考核对A/B统一使用个人数据与冠军两条独立标准。默认20张正式地图、地图平均Career Rating至少1.00；认可冠军为T2/预选赛/T1/Major。
- 有冠军：支持家书＋LVG邀请；只有个人数据达标：劝返家书＋LVG邀请；两项都未达标：劝返家书，确认后回国自建队，不直接坏结局。
- 无冠军且拒绝LVG邀请仍回国组队；有冠军可拒绝后继续当前道路。邀请等待目标队赛事结束，考核截止时间不顺延。
- Major冠军专栏及失望/预期内/激动三类赛后观察改为长文，引用实际名次和已保存个人数据，存入邮箱和故事档案。
- 每月世界摘要记录冠军/MVP、名单变化、多冠队伍、排名升降、个人战绩及后续赛历。只报告存档事实，升级前未记录转会不回填。
- 长剧情选项改为纵向自适应按钮、文字换行，正文和按钮区域各自可滚动。
- 转会记录加盟前已结束赛事，旧存档用转会日期排除；阻止补弹新东家旧奖杯，也拦住对应的历史奖金/属性点补结算。不追扣已经发放的旧奖励。
- 新增data/career_news.json与news-pack外置模板；NA门槛/期限/认可赛事和报道标题/正文可用arc_overrides配置。
- 本轮按玩家要求不代替进行游玩测试，也未运行完整回归或CS2对局；仅作静态语法/配置检查和桌面构建。待玩家实测，不沿用上一版通过数量。

# 1.5.0-stories.1（职业与生活剧情，本地候选）

- 新增三种虚构成年伴侣的恋爱线、热恋/克制、180天出国抉择及二次确认的退役结局。
- 认真职业选项默认 +2 自由属性点；NA留学生作为独立自建开局，额外 +3，接两条一年挑战、LVG邀请和归国重组。
- Major冠军专栏向玩家开放，按开赛阵容实力预期评价赛果；个人舆论设样本门槛与冷却，稳定伴侣会安慰玩家。
- 固定阵容长期明显失利可触发队内斗争；目标成功反击则其余四人离队，玩家自由身仍能按原概率/冷却主动申请。
- 伤病8类、24套文案，随年龄增加概率；每次减少1—2点能力维度并有临时负状态，不扣未使用的自由点。
- 生日两种选择、面对旧队的赛前选择均有回应；新增分页故事档案，原文与选择保留在存档，不重新结算。
- 复用 incidents 接口，新增 arc_overrides，提供中文TXT和可验证模板。自定义后续随排队决定冻结，防重抽/重复领点，拒绝新增循环引用。
- 转队/退役使用双存档事务；纯文案/奖励不深拷贝和重写整个赛季。没有调整比赛胜率公式或起始经济。
- 后端216项、前端5组回归通过。独立桌面测试EXE已实测NA建档、+3/+2入账、截止日提示与故事回看；最终集成EXE另做资源/保存/九人三档自检。
- 仍未逐条手玩全部多年结局，未重测实际CS2完整对局、全DPI布局或50岁退役平衡；不把自动测试等同于可玩性结论。

# 1.5.0-transfer.2（转会流程与性能修复，本地候选）

- 邀请绑定收件战队；转会后立即发出新队邀请。旧版无队伍标记的邀请在备份后重新确认，不动已打赛果。
- 恢复签约选手的位置切换；仍不能支配俱乐部买人、改队标或解散俱乐部。
- 三种告别各有外界回应，并只发放一次技能点 +1。
- 参加的正赛结束后揭晓 MVP / EVP / 五位置最佳阵容，不再仅冠军有弹窗；资格赛保持原奖励规则。
- 生涯 incidents 新增 skill_points 和 competition_pause；仍经统一校验、选择确认和存档幂等边界，模板默认不启用。
- 主界面不再传输全部历史回合记录；详情按需读取，存档保留完整数据。使用原生 JSON 编码与二进制原子保存，schema_version 仍为 2。
- 在约39 MB存档副本上，实际加点含保存/响应约215 ms，下一阶段含4场比赛约307 ms（单次带性能采样，不含桌面绘制，不保证所有赛季均低于1秒）。
- 隔离测试188项通过，前端4套回归通过；界面实际验证新队邀请、参赛入口、位置对调、技能点及告别回应。
- 界面跳过比赛的确认框被自动化工具阻塞，未记为实测通过；后端转会→参赛→十人战绩流程通过。未重新实测CS2对局。

# 1.5.0-dialogue.2（本地候选，未发布到 GitHub）

- 普通比赛文字改为每回合教练一句、选手一句；取消跨角色全场总额与全局冷却。
- 新增 scenes/sequence，多角色按顺序延时播放，优先于普通聊天，旧 rules 包兼容。
- 同级按扩展/文件/数组顺序挑选；场内剧情与生涯事件 incidents 分开。
- 延迟播放在换图、重启、冻结结束或身份异常时取消，不保留原生事件或控制器对象。
- 单独提供 match-scene-pack 的固定回合验证与中文说明；尚未实测本版游戏内播放。

# 1.5.0-dialogue.1（本地候选，未发布到 GitHub）

- 正式回合结束时可触发队友／教练文字：分差、连胜败、个人累计数据、本回合击杀。
- 设置支持内置＋扩展、仅扩展、关闭；全场最多八条，至少间隔两回合；不影响统计和比赛随机数。
- 新增 match_chat JSON 包和 incidents 生涯事件包；events 仍然专指赛事日历。
- 生涯事件支持触发条件、选项、资金／心态效果、包内标记和后续事件链，拒绝脚本和未知效果。
- 内置假赛、教练缺席等事件可改弹窗文案／选项标签，原业务概率、惩罚不变。
- 两份中文 TXT 扩展教程与可复制示例位于 extensions/_templates。
- 尚未进行本版 CS2 实机聊天测试；单元测试不代表 HUD 字体／颜色／联网行为已经验收。
- 当前教练事件使用标记和心态表达影响，不是完整教练合同系统；没有真实配音或独立 HUD。

# 1.5.0-rc.20260910.4

这是供公开测试的 Release Candidate，不是已完成全部实战验收的稳定版。

## 开赛就绪状态与聊天精简（.4）

- 忽略生涯请求/插件设置尚未完成时的初始化round_start。
- 十人暂未绑定使用独立的RosterReadiness等待状态，不再写入永久StatisticsError。
  十人恢复且未漏掉计分回合时解除等待；等待期间比分增长或中断已跟踪回合仍拒绝录入。
  阵容恢复不会清除其他击杀/伤害身份错误。记录roster_waiting的槽位和比分证据。
- 删除插件自加的“接管某选手，战绩记入该选手”聊天提示；后台接管记录仍然保留。
- 新增10项就绪状态回归，覆盖0:0加载恢复、漏掉首回合、中途缺人及其他错误保留。
- 不修改难度、已有存档或失败回传，不把旧结果的错误文字直接删除来强行录入。

本版仍需实际CS2新对局验证；自动化状态机检查不等于已完成原生实战验收。

## 换边比分与误拦截修复（.3）

真实 Ancient 对局证据：上一版14次接管均已解析，两个接管击杀正确归属队友，
但整场仍报笼统身份错误。旧日志未记录被拒绝事件，因此不能宣称已确定唯一触发原因。

- 修正换边比分：依据稳定选手ID的当前阵营，将结束时CT/T分数映射回开局战队。
  不按回合数猜换边；FUT以当前CT拿13分时，不再写成开局CT的FURIA获胜。
- 以当前比分确定正式回合序号，避免暖身重复round_start把22回合误当23回合计算ADR。
- 接管以 OriginalControllerOfCurrentPawn 直接控制关系为主；实测发现Pawn句柄不随接管变化，
  初始物理Pawn归属不能替代此关系。仅无直接关系时查反向关系。
- 删除“死亡选手造成伤害就是身份不明”的误判；补齐烟雾弹、诱饵弹碰撞伤害分类。
- 补齐Bot接管前投掷、接管后由真人控制器发出伤害/闪光通知时的道具来源查询。
- 闪光通知与投掷通知本身不增加统计，不再仅因该通知缺少来源就拒绝整场；
  真正计入击杀、伤害或助攻的事件仍须确认归属，不猜数或补零。
- 拒绝事件现在记录控制者、武器、当前归属、待确认状态；投掷与比分映射也记录到日志。

14条真实控制快照脱敏后加入回归语料；它们不是完整战斗事件记录，不能用于重建旧场次。
比分映射、误判路径及新增回归通过不等于CS2原生事件已全量验收；仍需实际新对局确认。
这次不变更难度、买枪或经济，不强行录入/改写已有失败结果。

## 接管热修复（.2）

上一候选版的接管修复被真实对局证伪：接管校验失败后仍把后续事件计到真人行。
本版修复事件适配层，不改难度、买枪、经济或玩家数据：

- 不再依赖 bot_takeover.Botid 必定是 Bot。使用回合初始 Pawn 归属、控制器的
  OriginalControllerOfCurrentPawn 及反向控制关系交叉确认；支持两个事件 ID 都指向真人。
- 绑定未完成时暂停该控制者记账，并禁用 MatchStats 兜底，不能静默算给真人。
- 接管成功时聊天提示“接管某选手，战绩记入该选手”；事件跟随被接管选手，昵称维护不变。
- 回传增加 identity_resolver_version=round_pawn_control_v2；游戏插件 identity_traces
  目录保留带 nonce 的接管快照及伤害/死亡归属明细。每个地图会话最多记录5000条。
- 新增16项复现测试：同ID事件、控制器互换、无法确认、连续接管、击杀/伤害/死亡分配、下回合复位。
  这些是隔离回放，不是实际 CS2 验收。仍须新对局核对接管提示、两名选手数据及日志。

CS2 原生 TAB 计分板仍由引擎维护，本补丁负责生涯回传账本，不强改原生计分板数字。
旧场次没有逐事件身份依据，不能凭比分或击杀合计逆推修正。
上游同类事件问题：[CounterStrikeSharp #1102](https://github.com/roflmuffin/CounterStrikeSharp/discussions/1102)。

## 本轮保留的改动

- High 恢复原包的特殊加速度原文；仅允许固定来源的精确 token，不接受任意字符串。
- Medium 把原数据库的重复参数提炼成匿名微调模板，按生涯当前位置能力＋半数状态选档。
  65/75/85/90 为 Rank/Slow/Steady/Fast或Precise/Top 分界，Top 瞄准另按90/95/98分组；
  这些分界是生涯映射，不声称原作者也用同一评分尺度。难度不修改个人评分。
- 突破保留 RusherPersonality，但使用步枪优先的 RiflePro。
- BotBuy 增加延迟实体检查；生涯内保留 SSG08，不再随机换为 SMG。
- 接管后的战绩按被接管选手计入；保留真人先前数据。处理连续接管、旧助攻、闪光、
  延迟投掷物和重连。发生接管后禁用容易混入真人控制数据的 MatchStats 零行兜底。
- 回传增加 stat_identity_policy 与 takeover_events，方便核对控制者和实际选手。
- 本次不修改经济、模拟胜率、已有赛果、存档或饰品库存。

## 已知限制／必须实测

原包特殊加速度的 CS2 内部解析含义未知；恢复的是字节文本，不是证明它代表无限或某个确定数值。
新 High／Medium、买枪分布、实际接管回传仍需在 CS2 完整对局验证。
同一控制者在接管前后，对同一敌人留下多名角色的助攻贡献，或同回合多个角色投掷同类延迟道具时，
现有事件字段不足以唯一归属，程序会明确拒绝该战绩，而不是猜测。
恢复的换肤源码只通过编译，尚未验证重编译版与历史 DLL 的实战等价；默认不更新它们。

## 快速验收

保存退出桌面和 CS2 → 打开更新后的 EXE → 生成新比赛 → 查看聊天
“原版增强参数 + 生涯个人微调”、所选难度、9/9 和哈希。
分别测试 Medium 与 High；观察长枪局突破位装备。
真人死亡后接管队友完成击杀，再核对真人与该队友两行战绩；
保留游戏目录 CareerMatch 的请求、结果及控制日志用于复核。
旧场次只有聚合数据，不能无依据倒推修正；本次不覆盖旧赛果。
# 1.5.0-transfer.1（本地测试候选，未发布到 GitHub）

- 新增个人转会：战队详情申请、位置能力修正 D20、明确概率与冷却、邮箱主动邀约。
- 失败全局30天/同队90天，申请成功90天，正式加盟锁定180天；年度主动邀约最多4份。
- 自建队离队后切换签约选手模式，原队继续参赛，经营权、金库和银行债务留在原队。
- 新队与原队始终五人；原队优先按原有身价签下负担得起的同位置自由选手，无候选时协商由新队被替换者补位，无额外现金交易。
- 个人借款保留原债权队伍；个人余额、饰品、成长和历史战报不转移给俱乐部。
- 新增五种去留/告别文案、七个转会事件触发点与 JSON 选择链示例。
- 转会命令备份双存档、延后内部写入并用恢复记录保护中断；显示骰点前已保存，重试不重掷。
- 保留 dialogue.2 的双角色聊天额度与有序剧情，本次不改 CS2 插件和比赛难度。
- 本次验收是隔离自动测试与共享界面测试，不代表长期转会平衡或新版本 CS2 实战已经验收。
