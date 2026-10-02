# CS2 Career 1.5.0 开发者接手指南

## storage.1：仅优化未来的安全备份

`save_backups.py` 统一创建、校验与恢复备份：新快照包含 `season.json.gz`、`career.json.gz` 和
`snapshot.json`（原始字节数及SHA-256）。gzip level 1以1 MiB块流式处理，校验解压后的字节一致；
完整且内容完全相同的最近快照可复用，不再重复创建。未提交清单、缺文件或校验失败的快照不复用。
旧备份不压缩、不迁移、不清理；没有保留数量上限。活动存档仍是原有schema_version=2普通JSON。
`ApplicationState.backup`、中断事务恢复和建档失败恢复均走此接口；旧Tk入口不再额外复制一次。
恢复先把整对文件解压校验到临时文件，再替换；事务日志仅在恢复成功后移除。支持旧的未压缩快照。
改动涉及磁盘备份，不是历史战报懒加载；`Season.history`仍在内存中，不能声称解决了多年运行内存增长。
只做隔离的备份/损坏保护/成对回滚检查，不因这些检查通过而宣称生涯流程或可玩性已验证。

## stories.1：职业与生活剧情

当前桌面主入口是 `desktop/webview_app.py` 的 pywebview + WebView2，不是后文早期记录中的 Tk。
剧情状态仅存在 `Career.incident_state['arcs']`，仍随 schema_version=2 保存；不要另建全局剧情状态。
`career/arcs.py` 是已有 incidents 的适配器，负责条件/章节/白名单业务动作，不运行扩展脚本。
`data/career_arcs.json` 放规则、对白、选项、伤病文本、结局；作者通过 incidents JSON 的 `arc_overrides` 覆盖。
`web/static/desk/arcs.js` 只负责状态提示和档案分页，决定仍经现有 story/ack；写操作同一 ApplicationState 锁，
转队/退役决定沿用 personal_command 的双存档备份/恢复事务（包含失败回滚）；纯文案、标记和奖励只原子保存career，
不深拷贝并重写整个赛季历史。新增白名单动作若修改世界，必须加入arcs.changes_world。

触发点：Career.create 初始化；Season._finalize_human 在记战绩后、结束赛事前登记正式系列赛；
open_event 冻结参赛阵容实力预期；finish_event 写Major报道和赛事评价；Career.tick 处理日期、NA期限、伤病；
gate_match 调用 before_match，应用临时状态并排入旧队赛前选择。GET接口不抽奖、不发点、不推进日期。
训练、轮空和弃权不触发首次比赛恋爱线；正式CS2和模拟共用 _finalize_human。
NA是自建开局 scenario=na_student（赛区 AM，但不是自动认定所有AM都是NA）。
有名单锁或已排队决定时，不弹会阻止赛事结束的NA转队决定；考核截止日不跟着延期。

随机数使用存档内独立seed及事件键的SHA256，不消费比赛RNG。行内冻结概率结果、奖励、规则、后续自定义章节；
重复ack无效果，退役返回确认不重抽。next和branches校验引用、拒绝新增循环；扩展只允许continue/finish自定义动作。
人物姓名与私人故事均为虚构，不按选手姓名解锁隐藏情节。

`world.ability.effective_form_delta()` 合并 form_delta 与 story_form_delta 并限幅；模拟和CS2请求均使用，
赛后 form 更新只读原始 form_delta，防止临时热恋/伤病永久叠加。真人在CS2中的枪法不受程序强制削弱。
伤病按每个实际到达的新月份检查一次，不补算跳过月份；同月不会通过重复操作重新抽。
每年上限3次、间隔45天、持续21天，年龄概率与参数可覆盖。未进行完整长期退役平衡验证。

档案全文永久保存在career，公共状态只给最近30段；`GET /api/story-history?page=1`每页20段按需取，
防止重新把全部历史放入每次响应。历史只读原文，不调用随机剧情生成器重造过去。
`tests/test_career_arcs.py` 覆盖分支/幂等/转队/回滚/模板/历史，必须用 tools/run_tests.py 隔离路径；
`tools/test_career_arcs_ui.cjs` 验证纯展示、HTML转义、分页和过时响应防护。
普通玩家说明见 `剧情扩展说明.txt`，作者模板见 `extensions/_templates/career-arcs-pack`。

## transfer.2 性能边界与回归入口

`Season.records(include_matches=False)` 供首页、荣誉、榜单使用；详情仍走原数据接口。
默认 `records()` 和 `awards.make_record()` 保留完整历史，跨年快照不能调用摘要模式。
不要把几十 MB 的历史事件再次放回 `/api/state` 或每次写操作的响应。
`json_bytes.encode` 用 orjson 输出UTF-8字节；桌面构建显式收集该依赖，缺依赖的源码环境可回退标准JSON。
存档仍先写同目录临时文件再原子替换，不用异步保存制造“按钮快、数据没落盘”。
`tools/profile_commands.py <存档目录>` 先复制 season/career 到临时目录，再实际加点与推进；从不改传入目录。
`tests/test_transfer_flow_fixes.py` 覆盖转会后邀请/参赛、岗位、告别幂等、非冠军颁奖、事件奖励/暂停、模板链与历史保存。
测试总入口仍为 `tools/run_tests.py`，必须在模块导入前隔离路径和关闭CS2操作。

这份文档面向下一位维护者，回答三件事：三个项目如何配合、程序从哪里启动、每个目录和源码文件负责什么。

> 当前主线就是此目录。`E:\1.4.1`、Bot Improver 和 Inventory Simulator 原项目都是只读参考，不应从 1.5 反向修改。

## 1.5 核心数据流

`build_request()` 保留双方球员完整身份 → `generate_match_vpk()` 计算难度与状态后的有效强度 → 生成“只读模板 + 9 个 C2C 档案” → 原子覆盖活动 VPK并写清单 → CareerMatch 校验 nonce/哈希/9 人后才建 Bot → 以槽位绑定 `player_id` 并显示真实昵称 → 逐回合事件账本导出 schema v2 → Python 严格匹配十人后使用 Career Rating v2 录入。

不要重新引入以下旧逻辑：1700 人名单覆盖率、Low/Medium/High 三份人物库、`applied_difficulty`、缺失战绩补 0、按队伍排名折损个人能力、固定 10% 超大爆发。

关键新文件：

- `cs2career/data/botprofile_templates.db`：仅含 Default、档位、武器和性格模板，禁止加入选手名单。
- `cs2career/cs2/profiles.py`：强度公式、9 人档案、VPK、nonce、头像哈希和完整性契约。
- `vendor/CareerMatch/CareerMatch.cs`：服务器槽位身份和正式回合事件账本。
- `cs2career/engine/rating.py`：真实/模拟唯一 Rating 实现。
- `cs2career/engine/match.py`：逐回合模拟事件流和 80/12/4/4 队伍实力。
- `cs2career/world/eras.py`：年代包版本、完整性验证、历史缺失槽位估算规则。
- `tests/test_v15_core.py`：边界、单调性、9 人 VPK、战绩守恒、年代包和固定种子回归。
- `tools/regression_v15.py`：100 个固定种子完整赛季的可复现平衡验收；发布前使用 `--enforce`。

开档排名只用于缺失团队上下文数据的同年代估算：初始化赛训、心态和地图适应。它不会修改个人长期总评，也不会在排名变化后实时加成；比赛仍只使用 80% 五人有效实力、12% 赛训、4% 心态和 4% 地图适应。

## 1. 三个项目的边界

### CS2 Career（本项目）

这是总控程序，也是唯一保存“生涯世界状态”的组件。它负责建档、赛历、赛事赛制、VRS 排名、比赛模拟、转会、经济、剧情、荣誉和个人皮肤库存。

程序本身是 Python 标准库桌面应用：默认由 Tk 桌面界面调用 UI 无关的 `ApplicationState`。旧 HTTP/浏览器界面只作为 `--web` 兼容入口保留，不能拥有另一套玩法规则。即使不安装任何 CS2 插件，玩家仍能用数值模拟完成整个生涯。

### CS2 Bot Improver（人机增强）

这是游戏内 AI 和插件运行环境，来源目录是旁边的 `CS2-Bot-Improver/`；`CS2BotImprover/` 是它的已编译发行包。它提供 Metamod、CounterStrikeSharp、BotHider、BotController、BotVision、BotAI、BotAimImprover、NadeSystem、BotBuy、BotRandomizer 等组件，以及 Low/Medium/High 三档 `botprofile.vpk`。

生涯程序不会重写人机增强的源码。安装时，`cs2career/cs2/launch.py` 只复制它的运行环境和增强插件，明确跳过人物数据库。每场比赛在 CS2 关闭时，由本项目的只读模板生成“模板＋9人”的 nonce VPK；瞄准和道具强度仍通过插件命令设置，Low/Medium/High 只参与有效强度计算。

### Inventory Simulator（皮肤换肤）

这是 CounterStrikeSharp 的 C# 插件，完整参考源码位于单独的 `csinventorysimulator` 工作区。本项目只在 `vendor/InventorySimulator/` 内携带可运行的 DLL、依赖清单、语言和 gamedata。

生涯内的皮肤商店、开箱和装备逻辑属于本项目；Inventory Simulator 只负责把生涯导出的装备映射应用到 CS2 实体。`InvsimCareer.dll` 是衔接用的辅助插件，目前仓库内只有编译产物，没有源码。

## 2. 运行时数据流

```text
desktop/app.py（默认）       web/app.js（兼容）
    │  Python 调用               │ GET/POST /api/*
    └──────────────┬──────────────┘
    ▼
application.py ── ApplicationState ── career/Career + league/Season
                               │              │
                               │              ├─ engine/：纯比赛、心态、rating
                               │              └─ world/：队伍、选手、年代、能力
                               │
                               └─ career/skins.py：个人库存与装备

玩家选择“按实力出战” ───────────────► engine/match.py 直接结算

玩家选择“自己打”
    └─ cs2/launch.py
         ├─ 安装/配置 CS2 Bot Improver
         ├─ 写 match_request.json 与 career_rules.cfg
         ├─ 启动带 -insecure 的 CS2
         ├─ CareerMatch.dll 写回 match_result.json
         └─ cs2/result.py 转换为生涯比赛记录

开启游戏内换肤
    └─ career/skins.py 导出 inventories.json
         └─ InventorySimulator.dll 在本地局中应用装备
```

最重要的状态所有权规则：

- `Career` 保存玩家本人、所属队伍、金钱、转会、邮件、剧情、皮肤和结局。
- `Season` 保存世界队伍、日期、赛事、比赛、VRS、选手统计和年度榜单。
- 桌面或网页只保存临时 UI 状态，不是真实数据源；应以 `ApplicationState` 为准。
- CS2 只是某张地图的可选结算器，不拥有生涯状态。

## 3. 根目录文件与生成目录

| 路径 | 职责 | 维护提示 |
| --- | --- | --- |
| `main.py` | 开发版入口；默认启动桌面 UI，`--web` 才启动兼容网页。 | 桌面模式会先处理中文路径下的 Tcl 运行库。 |
| `build_exe.py` | 用 PyInstaller 打单文件 EXE，并把说明、静态资源和三个 vendor 插件打进发布包。 | 会清理并重建 `build/`、`dist/` 和对应 release 目录。 |
| `README.md` | 安装、运行、三项目关系和版本更新说明。 | 面向首次使用者，避免放内部实现细节。 |
| `游玩说明.txt` | 玩家手册。 | 面向发行包，保持无剧透。 |
| `添加人机增强.txt` | Bot Improver 安装、路径填写、难度与常见问题。 | 游戏插件或目录结构变化时同步更新。 |
| `.gitignore` | 排除存档、缓存和构建产物，同时对白名单 vendor DLL 例外。 | 新增敏感存档时先更新这里。 |
| `LICENSE` | 本项目 MIT 许可证。 | 第三方组件仍服从各自许可证。 |
| `save/` | 运行时存档和机器相关配置。 | 不提交、不公开；详见“存档文件”。 |
| `build/`、`build-*` | PyInstaller 中间目录和 `.spec`。 | 均可重新生成；多个后缀目录是历史试打包结果。 |
| `dist/`、`dist-new/` | 未组装的 EXE 输出。 | 不在这里改代码。 |
| `release/` | 给玩家分发的文件夹和 ZIP。 | 应由打包脚本生成。 |
| `__pycache__/` | Python 字节码缓存。 | 可删除、不可作为源码。 |

## 4. Python 包总览

### `cs2career/`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 包元信息和版本号。发布前要确认这里与 README、打包名一致。当前为 `1.5.0`。 |
| `application.py` | UI 无关的状态、存档和命令边界；桌面与兼容网页必须共用。 |
| `paths.py` | 统一解析“只读资源”和“可写存档”的路径，兼容源码运行与 PyInstaller 冻结运行。其他模块不应自行猜测 EXE 目录。 |

桌面界面位于 `cs2career/desktop/`，扩展扫描器位于 `cs2career/content/`。自建三开局
集中定义在 `cs2career/career/origins.py`。扩展作者与维护者还应阅读
`EXTENSION_ARCHITECTURE.zh-CN.md`，不要在 Tk 按钮回调里加入经济或比赛公式。

### `cs2career/career/`：玩家生涯层

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 导出生涯层的公共入口。 |
| `career.py` | 最大的业务聚合对象 `Career`。负责建档/入队/自建队、转会市场、训练、参赛报名、经济危机、借款、合同、青训补人、属性成长、退役、邮件、剧情触发、假赛支线、皮肤操作及对前端的公开 payload。 |
| `economy.py` | 纯经济公式：工资、生活费、俱乐部月开支、奖金分成、利息和借款上限。尽量让数字规则留在这里，不要散进 HTTP 层。 |
| `mail.py` | 邀请、出线和合同等可操作邮件的文案与统一结构；奖金/赞助函仅为旧存档兼容保留，新流程由 `career.py` 自动入账并写入经营页流水。 |
| `plot.py` | 稀有生涯事件与结局文案，包括假赛、禁赛、债务违约等剧情参数。玩家手册不要泄露这里的细节。 |
| `skins.py` | 两部分职责：模拟层的皮肤目录/市场/开箱/报价，以及集成层的 Inventory Simulator payload、库存文件写入和即时同步。 |
| `story.py` | 数据驱动的普通剧情引擎；读取 `stories.json`，按上下文过滤、渲染并保证剧情只触发一次。 |
| `verse.py` | 年度 Top 20 的标题和短评，包含年代/选手的特殊文本。 |

`career.py` 很大，修改时先定位现有分区：storage、lookups、create、ticking、actions、mail/points/roles、stories、payload。新增独立公式或文案应优先拆到相邻小模块，不要继续扩大 HTTP handler。

### `cs2career/engine/`：纯比赛计算

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 汇总并导出比赛、心态和 rating 公共函数。 |
| `match.py` | 地图/系列赛模拟、地图池和 veto、逐回合事件流、守恒战绩与赛后 rating。输入是两队快照，输出是 schema v2 比赛结果。 |
| `morale.py` | 心态倍率，以及休息、旅行、连胜连败和赛事结束后的心态变化。心态只轻推结果，不应压倒能力。 |
| `rating.py` | Career Rating v2 的唯一公式、能力档位、预期 rating、期望死亡率及整数分配工具。 |

这层应尽量保持无文件 I/O、无 HTTP、无 CS2 路径依赖，便于单独测试数值。

### `cs2career/league/`：赛事与赛季

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 导出赛季、赛历、VRS、赛制和奖项公共入口。 |
| `season.py` | 世界级状态机 `Season`。负责赛事邀请/选队、开赛与推进、玩家场次暂停、模拟或 CS2 战绩录入、统计累积、年度滚动、存取档及前端 payload。 |
| `formats.py` | 纯赛制推进：单败、瑞士轮加淘汰赛、GSL 小组加淘汰赛；还负责避免重复对阵和生成下一轮。 |
| `vrs.py` | Valve 风格积分的初始种子、时间衰减、赛果入账和排名表。 |
| `awards.py` | 单站 MVP/EVP、年度 Top 20、个人/队伍荣誉汇总。赛事结束后转成稳定 record，跨年度保存。 |

`Season.next_stage()` 是日程推进主循环；`Season.roll_year()` 是跨年边界。涉及“为什么卡在玩家比赛”时，先查 `your_series()`、`yours_ready()` 和 `try_ingest_pending_cs2()`。

### `cs2career/world/`：静态世界与选手建模

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 汇总世界层公共数据和构造函数。 |
| `teams.py` | 49 支队伍、地图池、地区/梯队、slug，以及从年代快照构建可变队伍对象。 |
| `eras.py` | 2024/2025/2026 的开档元信息、历史阵容和初始排名。 |
| `pool.py` | 自由人、老将、青训/路人池、生日和年龄推导、初始队友生成。 |
| `roles.py` | 位置字典、已知选手位置、年代 IGL 例外，以及确保每队只有一个主狙和一个指挥的校正逻辑。 |
| `ability.py` | 独立长期总评、Rating→总评标尺、60/25/15 历史窗口与小样本收缩、七项打法属性、指挥和缺失属性生成。 |
| `aging.py` | 年度枪法年龄曲线、IGL 指挥成长和全队跨年老化。 |
| `academy.py` | 年末青训补人，从固定名字池生成普通新人与定期天才。 |
| `brand.py` | 队伍品牌色、短标签、内置 SVG 队徽和用户 PNG 覆盖。 |

注意：`TEAMS`、`ERA_ROSTERS` 等常量是开档模板；真正会被比赛和转会修改的是 `Season.teams` 的深拷贝。

### `cs2career/cs2/`：游戏桥接层

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 对外暴露 CS2 安装、设置、启动、结果读取和地图名转换。 |
| `launch.py` | 机器路径发现、设置存取、人机增强插件安装、每场 VPK 调度与9个唯一 BotHider 合成身份、换肤插件与 gamedata 安装、CFG、进程检测和 Steam 启动。所有会改 `game/csgo` 的操作集中在这里。 |
| `profiles.py` | 从内置只读模板生成单场恰好 9 人的 `botprofile.vpk`，计算档位/有效强度/安全参数，并维护 nonce、清单与 SHA-256 契约。 |
| `result.py` | 严格校验 schema v2、nonce、地图、十个 `player_id` 和两边各五人，再把 CS2 逐回合账本映射为统一地图结果。 |
| `sync_overrides.py` | 兼容入口；1.5 会明确返回“人物库同步已停用”，真正档案在每场开赛时生成。 |

CS2 集成的关键约束：

- 改 DLL、VPK 或挂载配置前必须完全退出 CS2；游戏启动后不会自动重载这些内容。
- `launch.py` 启动 CS2 时带 `-insecure`，只用于离线机器人/私人环境，不能用于官方匹配。
- 对局请求写入 `CareerMatch/match_request.json`；插件持续写 `match_result.json` 和质量更高的 `match_result.best.json`。
- `career_rules.cfg` 可以在换边时重复执行，因此不能把会踢 bot 或重置阵营的命令放进去。
- `botprofile.vpk` 里的名字必须唯一，否则 CS2 可能拒绝加入或换成别的人名。

### `cs2career/web/`：本地 API 与界面

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 导出端口选择和启动函数。 |
| `server.py` | 标准库 HTTP 服务、全局 `State`、静态文件服务和全部 JSON API。还在 `127.0.0.1:18768` 开一个只读皮肤 API，供本地 Inventory Simulator 请求当前 SteamID 的装备。 |
| `static/index.html` | 单页应用骨架：顶部栏、侧边导航、主内容容器和弹层挂载点。 |
| `static/app.js` | 整个前端控制器：网络请求、客户端临时状态、各页面渲染、事件绑定、CS2 结果轮询、剧情/年度榜单动画。没有前端框架和构建步骤。 |
| `static/style.css` | 全局主题、布局、卡片、赛事、表单、邮件、检查面板和响应式样式。 |
| `static/crests/*.svg` | 现实队伍的内置队徽静态资源；文件名必须与 `teams.slug()` / `brand.crest()` 约定一致。 |

`server.py` 的 POST 路由采用约定式分发：`/api/series/launch` 会对应 `post_api_series_launch()`。新增接口时要同时更新后端方法和 `app.js` 调用，并确认响应仍包含前端需要的最新 state。

## 5. 数据文件（JSON 本身不能写注释）

| 文件 | 数据结构与用途 |
| --- | --- |
| `data/calendar.json` | `season/start/note/events`；基准赛季的 48 个赛事模板。未来年份由 `calendar_for()` 平移日期。 |
| `data/player_stats.json` | 以选手名为键的能力数据；每人保存角色、年龄/生日来源、七项轴和指挥等字段。名字大小写有实际意义，当前同时存在如 `MATYS`/`matys` 的键，处理时不要用大小写不敏感字典误合并。 |
| `data/skins.json` | `cases/market/skins`；箱子、商店陈列和饰品定义，含槽位、稀有度、价格区间、paint/definition 信息。 |
| `data/stories.json` | `_how_to_add/stories`；普通剧情的触发时机、过滤条件、模板和选项。新增剧情优先改这里。 |
| `data/academy_names.json` | 年度青训生成器使用的固定未占用名字池。 |

修改 JSON 后至少执行一次 JSON 解析检查。因为 JSON 不允许注释，字段解释应继续维护在本节，而不是加入 `//` 或 `/* */` 导致运行失败。

## 6. `vendor/` 第三方与游戏插件

| 路径 | 职责 |
| --- | --- |
| `vendor/CareerMatch/CareerMatch.cs` | 本项目自有 CounterStrikeSharp 插件源码：读取请求、建双方机器人、处理热身/阵营/难度、连续抓取记分板并写回最佳结果。 |
| `vendor/CareerMatch/CareerMatch.csproj` | CareerMatch 的 .NET 工程与依赖版本。 |
| `vendor/CareerMatch/CareerMatch.dll` | 打包和安装时真正复制进游戏的插件。改 C# 后必须重新编译并替换它。 |
| `vendor/CareerMatch/CareerMatch.deps.json` | DLL 的运行时依赖清单。 |
| `vendor/InventorySimulator/plugins/InventorySimulator/*` | 换肤插件 DLL、依赖清单与语言。这里没有完整源码；完整源码在独立工作区。 |
| `vendor/InventorySimulator/gamedata/inventory-simulator.json` | CS2 原生函数签名/偏移。CS2 更新后最容易失效，可由训练赛页更新到 `save/skins_gamedata/` 覆盖。 |
| `vendor/InvsimCareer/*` | 生涯换肤辅助插件的 DLL 和依赖清单，目前无源码。升级前应补齐其源码来源或可重建说明。 |

不要直接编辑 `.dll`、`.deps.json` 或生成目录来“修功能”。应改对应源码、编译、替换 vendor 产物，再做一次真实 CS2 离线局验证。

## 7. 存档文件

`save/` 由 `paths.save_root()` 决定：源码运行时在项目旁，EXE 运行时在 EXE 旁。

| 文件/目录 | 所有者 | 内容 |
| --- | --- | --- |
| `career.json` | `Career` | 玩家、队伍归属、经济、剧情、邮件、皮肤、合同与结局。 |
| `season.json` | `Season` | 日期、队伍、赛事、比赛、VRS、统计、历史和年度 Top 20。 |
| `cs2.json` | `cs2/launch.py` | 本机 Steam/CS2/人机增强路径和游戏内难度设置。 |
| `cs2_last.json` | `cs2/launch.py` | 最近一次可用的 CS2 地图结果缓存。 |
| `cs2_matches.json` | `cs2/launch.py` | 已归档的 CS2 对局历史。 |
| `logos/` | `world/brand.py` | 用户上传的队标覆盖。 |
| `skins_gamedata/inventory-simulator.json` | `cs2/launch.py` | 从上游下载的新版换肤签名，优先于 vendor 内置版本。 |

1.5 的 `career.json` 和 `season.json` 都是 `schema_version=2`。1.4 存档只改名备份并提示新建生涯，不做字段迁移；以后增加 v2 字段仍要在初始化、序列化和缺省值三处保持一致。

## 8. 外部项目中与本项目最相关的目录

### `CS2-Bot-Improver/`

- `Panel/`：React + TypeScript + Vite + Tauri 的 Windows 配置面板，不参与生涯网页 UI。
- `addons/counterstrikesharp/plugins/`：各项 AI、购买、投掷物、皮肤随机化和战绩插件源码/产物。
- `addons/BotHider`、`BotController`、`BotVision`：较底层的游戏插件及 gamedata。
- `cfg/`：各种游戏模式和机器人购买配置。生涯安装时会在部分模式文件尾部挂接自己的 CFG。
- `overrides/Low|Medium|High/`：Bot Improver 自己的普通人机人物库；1.5 安装时跳过，不作为生涯数据源。
- `backup/Online|WithBots/gameinfo.gi`：在线/机器人模式的挂载切换文件。

### `cs2-css-inventory-simulator-3.1.0/`

- `InventorySimulator.cs` 与四个 `InventorySimulator.*.cs`：partial 主插件，拆分加载、核心实体事件、比赛事件、命令和 native hook。
- `Services/`：配置变量、API、本地库存加载、运行时引用和规则。
- `Models/`：API 与库存 JSON 数据结构。
- `Extensions/`：把换肤行为封装为 CounterStrikeSharp/CS2 实体扩展方法。
- `Natives/`、`Schemas/`、`Structs/`：对 CS2 原生函数、内存 schema 和非托管结构的封装；最依赖游戏版本。
- `Helpers/`：选手、物品、队伍、类型、URL 和 schema 辅助函数。
- `gamedata/`：原生函数签名；CS2 更新后需要优先核对。
- `lang/`：本地化文案。

本项目使用的是 Inventory Simulator 的“本地文件模式”：`career/skins.py` 写 `inventories.json`，插件按 SteamID 读入，而不是要求玩家拥有真实 Steam 库存。生涯内置的 `127.0.0.1:18768` API 还可提供 Equipped V5 结构。

## 9. 常见改动应该从哪里开始

| 需求 | 首查文件 |
| --- | --- |
| 调整能力、比赛比分或 rating | `world/ability.py`、`engine/match.py`、`engine/rating.py` |
| 调整赛事、邀请或赛制 | `data/calendar.json`、`league/season.py`、`league/formats.py` |
| 调整 VRS 或奖项 | `league/vrs.py`、`league/awards.py` |
| 调整转会、经济、合同或培养 | `career/career.py`、`career/economy.py` |
| 新增剧情 | `data/stories.json`；特殊长支线才改 `career/plot.py` |
| 调整皮肤经济/目录 | `data/skins.json`、`career/skins.py` |
| 改页面 | `web/static/app.js`、`style.css`，必要时再改 `index.html` |
| 新增 API | `web/server.py` 与 `web/static/app.js` |
| 修复游戏安装或启动 | `cs2/launch.py` |
| 修复人名/难度映射 | `cs2/profiles.py`、`data/player_stats.json` |
| 修复 CS2 战绩导入 | `vendor/CareerMatch/CareerMatch.cs`、`cs2/result.py`、`league/season.py` |
| 修复游戏内换肤 | `career/skins.py`、`cs2/launch.py`、Inventory Simulator 源码和 gamedata |

## 10. 修改后的最低验证

本仓库当前没有自动化测试目录，至少执行以下检查：

1. `py -3 -m compileall -q main.py cs2career`：Python 语法和导入编译。
2. 逐个解析 `cs2career/data/*.json`：防止数据文件格式错误。
3. `py -3 main.py`：确认首页可打开，`/api/state` 返回 JSON。
4. 用临时或备份存档验证一次：建档、下一天、模拟一场、保存并重启读取。
5. 改 CS2 桥接时，再验证一次完全退出 CS2 后的安装、启动、13 分结束和战绩录入。
6. 改换肤时，用 17 位 SteamID 验证 CT/T 武器、刀和手套，并确认不开启换肤时 BotRandomizer 仍然工作。
7. 发布前运行 `build_exe.py`，在没有 Python 的环境检查 EXE 与 `save/` 路径。

不要用真实主存档做破坏性迁移试验；先复制 `save/`，或者在独立目录运行源码。
# 2026-09-10 发布补充

最新发布入口与白名单打包流程见 PUBLISHING.md，版本已知限制见 RELEASE_NOTES.md。
BotProfile 参数读取在 cs2career/cs2/improver_presets.py，匿名原参数资源在 data/botprofile_presets。
Medium 按生涯评分挑选个人微调，High 保留精确原始特殊 token，不作浮点转换。
CareerMatch.Events.cs 处理事件适配，ActorOwnership.cs 负责纯身份归属；
控制者昵称绑定与被控制身体的统计身份是两套不同映射，禁止混用。
BotBuy 生涯补丁源码在 vendor/BotBuy；每场准备会校验复制 CareerMatch 与 BotBuy。
旧换肤源码恢复说明在 RECOVERED_SOURCE.md，未经实战等价验证不得自动换掉历史 DLL。

## 接管适配层（1.5.0-rc.20260910.2）

TakeoverResolver.cs 接收十人控制器快照，使用回合初始 Pawn、正反向
OriginalControllerOfCurrentPawn 关系确认被接管者。不要相信 bot_takeover.Botid
一定是 Bot：上游 #1102 报告它与 Userid 都能指向真人。
CareerMatch.Events.cs 负责读取原生字段、下一帧重试和 identity_traces 诊断；
ActorOwnership.cs 负责确认后的统计归属，AwaitTakeover 表示未知，不能默认归还真人。
IdentityBindings.cs 仍只管昵称/头像/槽位，禁止为修统计而换掉这层身份。
OnRoundStart 与 OnRoundFreezeEnd 记录未交换身体；新回合、重启、断线清理临时控制关系。
失败接管也关闭 MatchStats 兜底。无法唯一归属继续阻止录入，而不是把缺失者补零。

运行 tools/run_tests.py（先隔离保存路径）；纯C#入口为 tools/identity-tests，
TakeoverRegression.cs 覆盖重复事件ID和连续接管三人数据分配。
本节取代早期“没有自动化测试目录”的描述。回放测试不等价于原生CS2验收，
发布时必须保留 RELEASE_NOTES.md 的实测限制。

### .3 实测后的修正

上一段的初始物理Pawn归属不再作为接管候选：真实14条快照显示接管时句柄不变。
TakeoverResolver优先读取真人控制器OriginalControllerOfCurrentPawn，再使用反向关系。
TeamScoreMapping把当前CT/T分数映射回请求开局战队，十人阵营暂时不齐时保持最后有效映射；
不要在前端简单对调数字，也不要按12回合硬编码换边。正式回合序号用比分推导。
闪光/投掷是贡献证据，不直接产生统计；只有被真正计分的事件无法归属才拒绝录入。
日志identity_rejected必须保留具体字段，不能仅保存一条笼统错误。
tests/fixtures/takeover_control_snapshots.json为真实控制快照的脱敏语料，不含原始存档或比赛日志。

### .4 就绪状态

RosterReadiness.cs专门跟踪十人绑定等待和漏记风险；不得把可恢复的初始化等待写入
SessionHealth.StatisticsError，也不得在阵容恢复时清除整个StatisticsError。
等待时记下比分，恢复前已有计分增长表示可能漏记正式回合，不能仅凭终场十人齐全放行。
ReadinessRegression.cs覆盖这些状态转换。用户要求隐藏接管成功聊天，但日志必须保留。
## 个人转会模块（transfer.1 补充）

- `cs2career/career/player_transfers.py`：D20 报价、申请/签约事务、补强邀约、冷却、告别、原队财务与转会剧情通知。
- `cs2career/web/static/desk/personal-transfers.js`：个人转会页面与结果揭晓；不得在前端产生业务骰点。
- `ApplicationState.personal_command`：备份、双文件恢复日志与延迟提交，HTTP 返回前完成保存。
- `tests/test_personal_transfers.py`：隔离单元与真实本地 HTTP 命令回归。
- `tools/transfer_ui_fixture.py`：临时目录运行共享界面与真实创建命令，不读取正式存档、不连接 CS2。

邀约策略：每月最多评估一次，60%的固定生涯抽签机会；只有对应位置至少补强3分的球队进入候选，优先实力最高的有意球队。全年最多4份、同队不重复、同一时刻最多一份未处理合同，有效30天；拒绝不退年度额度。自由身也可主动申请，不依赖保底邀约。

转会后原队被标记为 AI 管理，保留金库、银行借款与欠款。原队按原工资/生活费标准结算，负担不起的开支记欠款，不扣玩家口袋；暂未做 AI 破产清算/出售俱乐部。签约玩家的个人债务仍由玩家承担，向原债权球队付款。不得通过清空 loan 来免除个人借款。

## 沙二战术画板与游戏执行（tactics.2 试验）

- `cs2career/tactics.py`：纯数据验证、雷达坐标转换及独立战术库事务；不依赖 `Career`，不写生涯存档。
- `data/tactical_map_dust2.json`、`web/static/tactical_maps/de_dust2.png`：实际雷达、坐标参数和来源。图片仅供编辑，不决定可走区域。
- `data/tactical_playbook.json`：只读 T／CT 示例。用户第一次保存后使用 `save/tactics.json`；删除全部不会重新灌入示例。
- `web/static/desk/tactics.js`、`tactics.css`：地图、五槽步骤及导入导出，局部更新，后台生涯刷新不重建表单。
- `web/server.py`：`GET /api/tactics`；会话校验后的 `POST /api/tactics/save`、`delete`、`import`。编辑接口不部署游戏文件，不推进生涯。
- `cs2/launch.py`：只有退出 CS2 后的安装／开赛准备才将规范库写到 `CareerMatch/tactical_playbook.json`。库错误在生成比赛档案之前报告，不静默覆盖或丢弃。
- `vendor/CareerMatch/TacticalPlaybook.cs`：跨语言协议、稳定槽位、NAV 层级投射和逐步等待计时。
- `vendor/CareerMatch/CareerMatch.CustomTactics.cs`：准备阶段命令与原生导航执行，战斗／炸弹优先的暂停和接续。

协议：`schema_version:1`，`map:de_dust2`，最多 20 个战术；每个战术含 `id/name/side/slots`。
五槽固定为 1＝真人（仅参考），2–5＝开场请求中我方四名 Bot 的顺序；不按动态实体列表、昵称、死亡或换边重新排序。
每槽最多 12 步，含二维世界 `position`、`level:auto/upper/lower`、到点后 `wait:0..30` 秒和可空 `look_at`。
地图向世界转换为 `x=pos_x+pixel_x*scale`、`y=pos_y-pixel_y*scale`，显示缩放不改变原始像素坐标。

`tactic <id>`／`战术 <id>` 只在正式准备阶段选择本阵营战术；`default` 取消，旧 Rush 指令保留。
运行时以当前地图 NAV 生成落点，再交原生寻路绕墙，不把图片连线当作可穿越路径。
等待使用现有 BotController 的可释放移动令牌；不得把原生 Idle 冒充持续保位，不压制攻击／使用。
赶路时接敌、受伤、闪光、道具和炸弹动作交回原生执行；到点等待的优先级见下方 tactics.6。
已下包后暂停剩余赶路；已经开始的到点等待完成后释放，回合结束统一清理。
方向字段可编辑保存，但本次没有接通已验证的朝向接口，执行时明确提醒，不猜写未知视角内存。
这不是职业全图 AI 或完整道具编排；实机验证需覆盖导航、等待、交火接续、换边、接管和回传。

### tactics.3 到点等待兼容修正

当前 BotController 0.7.0（451c7ba）接口为 ABI22，不是早期实验室 ABI20。
`TacticalHoldControls` 按经过核验的 DLL 哈希逐个绑定预期 ABI，不以 `>=20` 放开未知版本。
六个保位相关导出的 Cdecl 参数及返回值已与该提交 `src/bridge/exports.cpp` 对照；保留旧 ABI20 支持。
预检失败同时写插件日志与 `tactic_preflight_rejected` 身份诊断，聊天不再把保位接口失败统称为地图路线错误。

### tactics.4 自定义赶路与回位修正

实机 `tactics.3` 已记录四人启动／发出 MoveTo、一人到点等待，但随后发生进展超时；这不能算完整执行通过。
自定义路线现在通过 `TacticalMoveMaintenance` 在拥有同一目标时续期原生 HurryTimer，保持与 Rush 指令相同的赶路意图；不反复启动同一 MoveTo，也不注入速度或方向键。
交火位移后返回，以及等待点漂离后的返回，不再沿用此前接近目标的最小距离，避免回程被旧进展记录提前判停。
`tactic_custom_progress` 每三秒记录位置、距离、层高差、速度、原生目标所有权和赶路计时；`tactic_custom_stalled_native_fallback` 在取消前保留同一现场。
这些诊断用于区分真正没动、绕路、原生提前到达或高度错误；离线维护分支回归不能替代下一局实测。

### tactics.5 / CS2 1.41.8.8 游戏布局更新

Steam build 25640462 把旧 csgo_core / csgo_imported 的配置并入主 gameinfo.gi。
旧版启动器在 prepare_game 尾部复制 WithBots 整份 GI，会回装旧 LayeredOnMod 并导致启动失败；现改用 cs2/gameinfo.py 对当前文件做最小挂载补丁。
安装和开赛均先验证当前 GI，只添加 BotProfile VPK 与 Metamod 搜索路径；不复制 mod 根目录或 backup 下的 GI，保存旧内容校验备份且重复调用不重写。
本机恢复工具 tools/repair_gameinfo_20261001.py 使用固定游戏源码快照，CRLF 内容必须匹配已安装 Steam depot 的 SHA1 e45233adb00dd6906b3f92ec8319da0ccd0a2225 / 25985 bytes；它不修改插件 DLL、名单、战术或存档。
导航新 server.dll SHA256 3541E46A3193FCF1151E97CE19CD4DAF86C5FDB2889033C2BAB1D4CC7F555B9C 的 MoveTo / Idle / SetState 以及状态构造和官方控制台 callback 已重新静态交叉核对。移动行为和私有字段偏移未改；仅接受重新审定的当前版本。
文件签名、配置和自检通过仍不等于插件加载与实机对局通过，需下次启动验证。

### tactics.6 / 指定时间保位

实机 tactics.5 记录 25 次等待后让渡，其中 23 次只间隔 21/22 tick；首次伤害之前就已反复发生。
旧循环把原生的跳跃意图等同于应放开移动，而保位只过滤最终输入、不清原生意图，因此可触发自解除。
现在 `TacticalWaitPolicy` 区分赶路让渡与到点保位：在目标范围内保持移动令牌直到等待计时结束，敌人可见、开火、手持道具或下包不自行解除；原生瞄准、射击、使用按钮始终不压制。
取得保位后用较宽的水平/层高容差避免边缘抖动；实际被推离范围时释放移动令牌并回位，回程不消耗剩余等待。
`TacticalTravelProgress` 同时检查实际 XY 位移与目标接近；不再把仍在绕墙跑动的 Bot 按十秒直线最小距离规则误判为卡死。
每三秒 `tactic_custom_hold_progress` 记录持有状态、位置、速度和剩余时间，位移超界记录 `tactic_custom_hold_displaced`，不逐 tick 写日志。
静态复核表明当前原生 SetState 会调用退出/进入，MoveTo 进入也使用新目标请求路径，没有依据添加“先 Idle 再 MoveTo”的重置；原生寻路接口及底层 DLL 不改。
保位与绕路的离线回归只验证状态规则；实际 15/20 秒保位、再前进和完整 A/B 导航仍由下一局实测确认。

### tactics.7 / 自定义路线先提交真实路径

实机 tactics.6 的 `74521A91DEE31091` 记录：冻结结束 7 tick 后已登记 A 区目标，前三秒仍向中门行进，九秒时仍在下中路；因此不能归因于聊天指令晚发。两名队友随后分别完成约 15.19 / 20.38 秒的到点保位，上一轮的等待修正已获得现场证据。

当前原生 `MoveTo.OnEnter`（RVA 32a630）不消费 wrapper 的 route 字段，普通任务使用 SAFEST=2；`ComputePath`（2bafa0）也可能因原生 repath timer 限流返回 false，且不清旧路径。旧版本仅查同状态/同目标，误把这个状态当成新路线已经建立。静态证据支持两个风险，但旧日志没记录真正的 path/限流，不能断言该场唯一根因。

`TacticalNativeNavigation.TryShortestPath` 借用已加载且 SHA256 锁定的当前游戏函数，Windows x64 参数为 `bot, float[3]*, route=1, float=100, bool*rateLimited`、单字节返回值；FASTEST=1 / SAFEST=2 经本机 BT parser 与路径成本分支核对，不沿用旧 CSGO 枚举。文件与载入代码同时核对唯一 41 字节函数签名，不加载第二份 server.dll，不新增 Hook，不写 task、timer、人物位置或速度。

`TacticalDirectMove` 把原生目标登记与实际路径提交分开：先取得独立准备移动令牌，再进入原生 MoveTo，限流时每 0.25 秒重试真实 ComputePath，最久三秒。限流依据原生 bool 输出，不比较未经确认的 world/server 时间，不直接清 repath timer。路径成功后释放准备令牌，后续只续 Hurry；丢失目标、交火恢复或下一步骤必须重新提交。

准备令牌与到点令牌分开，不能因准备期停止而消耗站位等待。接敌、受伤、闪光、道具、死亡、接管、回合结束等仍清理准备控制；另一控制器占用时，在改变原生目标/路径之前拒绝。路径不可达或准备超时时，仅释放相应队友并明确提示，其余路线继续。

`tactic_custom_path_pending` / `tactic_custom_move`（`route:native_fastest,pathAccepted:true`）/ `tactic_custom_path_rejected` 区分等待、原生接受和失败，不把返回 true 等同于到达。三秒位置诊断增加 `pathPreparationHeld`。旧 rusha/rushb 行为、底层 DLL、存档、战术 JSON 与 gameinfo.gi 不变。

回归覆盖原生接受失败不能报成功、限流不会重入 OnEnter、准备控制与到点计时隔离、目标被换掉后重提交、所有权拒绝、战斗让权和超时清理。文件审计/编译通过不能证明游戏内路线已正确；本轮仍需从出生点到指定 A/B 点的实测。

### 自定义五位置与本场购买策略（2026-10-01）

`arena_roles.assign_lobby_positions` 同时用于 rank/fpl/custom。自定义创建房间时分配；旧房间仅在 ready 阶段补分配。starting/launched 的 nonce、角色与身份快照不可重分。使用现有五位置能力求分工，不修改世界中的选手或职业阵容。

`cs2/improver_presets.py` 只在生成模板时移除 AUG/SCAR20/G3SG1 购买偏好，保留归档数据库及 Low/Medium/High 能力参数；有效模板参与原来的哈希校验。`vendor/BotBuy/CareerWeaponPolicy.cs` 是纯购买策略，`BotBuy.cs` 每回合缓存请求中的 SteamID→role，不依昵称猜位置。项目对局不运行 Big Advantage 随机连狙，加时仅 awp 位请求 AWP。购买阶段的新购禁枪凭购买事件、唯一实体和可退款状态纠正；捡来的、上回合留下的武器不按名称删除。真人、接管、换 pawn、换图和过期计时器禁止修改装备。

部署时 `tools/install_tactical_commands.py --with-botbuy` 成套备份/替换 BotBuy、CareerMatch 与桌面程序，校验打包插件哈希，并更新恢复资源包的文件清单；原生 DLL、战术 JSON、存档与库存保持不变。纯策略参数组合和打包测试不代表真实购买事件已经实测。

该次指定朝向尚未接通；后续的 tactics.8 在下面补齐原生请求取消。不得复用旧 ABI20 LabView 或写 EyeAngles 来掩盖接口缺口。

### tactics.8 观察、开局与下包任务（2026-10-01）

- `TacticalNativeLook.cs`：仅到点停稳、`wait>0` 时申请原生观察请求，二维箭头对应实际眼位高度的水平观察方向，不是三维锁头。当前 server 哈希与 SetLookAt／ClearLookAt／consumer 完整字节均核验；只借用已加载模块，不新增 Hook、不换底层 DLL。
- 原生 SetLookAt 保留描述符指针，且观察持续时间在对准后才开始。每个 lease 使用唯一、进程生命周期的持久描述符；取消只在同 pawn／Bot、当前描述符仍归自己时，清除已确证的两个请求字段，不写 EyeAngles、坐标或速度。其他 owner 或更高优先级的请求保留。没有对准时另有 2 秒托管超时，不靠 native duration 猜测撤销。
- 看到敌人、攻击、受伤、闪光、道具、拆包与接管立即让出观察。移动保位规则不变，等待、换点、下包与退出都会结束旧观察。原生请求的静态证据和纯 lease 测试不代表实机转头通过。
- `CareerMatch.OpeningTactics.cs`：正式准备阶段接受指令后，为相关 Bot 取得独立 JUMP-only 抑制令牌；新原生路径建立后短暂保留，最迟开局 1.25 秒释放。没有强制落地、瞬移或速度写入；不是全程禁跳。已有的路径准备／到点等待抑制仍按各自 lease 结束。
- `CareerMatch.PostPlantTactics.cs`：下包无条件结束本回合已接受战术的剩余路线、等待与观察，实际 `planted_c4` 坐标与包点触发体确定 A／B，不按 `EventBombPlanted.Site==1` 猜 B 点。已完成的开局指令仍保留本回合意图，直到取消或回合重置，以便下包后正确切换职责。
- T 在包点保留当前位置；外部队友由 NAV 分配不同落点后守住。守包使用可释放的移动保位，原生视野／射击／道具保留；战斗期间释放，安静后回守包位置，不接续旧开局。CT 到实际下包位置后交原生交火／拆包，不套 T 的守位令牌。
- 只处理真人本队已绑定 Bot，不控制真人、敌方、已接管、死亡或换 pawn 的队员。换图、终场、炸弹结束与回合重启清理新令牌；普通原生任务不可被过期取消覆盖。
- `TacticalObjectivePolicy.cs`、`tools/identity-tests/TacticalObjectiveRegression.cs`：纯阵营／到点／战斗规则与开局抑制生命周期回归。构建、缓存与备份在 D 盘；部署校验正式存档、库存、战术库及原生 DLL 保持不变。实机由玩家联合验证，未声称通过。

### tactics.9 / 原生观察与已安装漂移补丁兼容（2026-10-01）

实机 tactics.8 已加载，但预检被 `look_loaded_code_differs_from_audited_file` 阻止；不是战术画板数据错误。当前 server 的三段审计代码没有 PE 重定位项；BotController 的 Upkeep、UpdateLookAngles 等 Hook 也不落在这三段内。实际冲突是 BotAI 已记录成功应用的 `Upkeep_BotCOS_ZeroDrift` 和 `Upkeep_BotSIN_ZeroDrift`：consumer 内 RVA `2e729b`、`2e72c8` 的两个五字节 call 被改成 `0F 57 C0 90 90`，清零漂移，不改观察请求状态和优先级。

观察适配器只识别这两处已审定修改，其他字节仍逐一核对；SetLookAt 与 ClearLookAt 的完整字节检查不放宽。绑定后锁定实际通过的完整代码快照，后续未知修改继续拒绝。失败原因增加具体函数和首个差异 RVA，便于区分新游戏版本、补丁变化和未知 Hook。

此修复不更换 BotAI／BotController，不新增 Hook，也不改存档、库存、战术库、购买分工、开局抑制和下包规则。离线测试覆盖原版、已知补丁、未知修改与观察 lease；通过不等于游戏内转头已实测。

### tactics.10 / 多地图编辑与执行（2026-10-01）

本节取代早期的 Dust2-only 范围说明，执行规则沿用 tactics.7–9。支持 Dust II、Mirage、Inferno、Nuke、Ancient、Anubis、Overpass、Train、Vertigo、Cache；不修改赛事/天梯地图池，也不扩大旧 Natural 模式的支持范围。

- `data/tactical_maps.json`：十张地图的统一只读投影目录、雷达层、图片哈希和固定来源提交。官方雷达素材仍属 Valve，见 THIRD_PARTY_NOTICES。图片只作画板背景，不能证明路径可走。
- `tactics.py`：API 输入使用严格的规范地图名；启动器边界的 `canonical_map` 兼容比赛请求中的短名。Dust2 沿用 `save/tactics.json`，其余为 `save/tactics_de_<name>.json`；库格式仍是 schema_version=1，每份仅含一张图。非 Dust2 没有伪造示例点位。
- `GET /api/tactics?map=de_nuke` 返回指定库、投影和支持列表。save/delete body 增加 map；import 的 query 显式限定当前地图。旧 Dust2 调用仍可用。完整库和单项包装的地图不一致时整体拒绝，不重标数据或半写入。
- `desk/tactics.js`：地图选择、未保存确认、按图导出文件名；失败读库保留原地图与草稿。多层雷达仅改显示，不能隐式改已有 `step.level`。地图菜单、选项与焦点在后台刷新中保持原 DOM，避免闪动。
- `cs2/launch.py`：开赛只加载实际比赛地图对应的库，退出 CS2 后部署这一份快照；不把十张图合并成同一文件。
- `vendor/CareerMatch/TacticalMapCatalog.cs`：构建时嵌入同一份投影目录，运行时只解析一次。投影边界以 double 计算、最后单次转换为引擎 float，与 JSON 点位舍入一致，避免 Anubis/Overpass 边缘误拒绝。当前 Server.MapName、请求 Map 与 playbook Map 必须相同。Nuke/Train/Vertigo 显式上下层以官方雷达 altitude_min/max 过滤 NAV 候选，选定层不存在就拒绝，不悄悄回退另一层；auto 和单层图仍沿用原投射规则。真正的走法、Z 仍由当前地图 NAV 判断，不新增地图专用内存接口。

原有到点等待、水平观察、开局抑制、战斗让权和下包 T 守包/CT 回防不变；包点由地图实体取得，不套沙二坐标。本次离线验收包括十图坐标往返、十三张本地图片哈希、同 ID 分图保存、跨图导入拒绝、菜单稳定性及插件边界/地图匹配。其他地图的实际导航、等待朝向、多层与下包处理尚需逐张游戏测试，不能把编译与打包自检当成实机通过。

### tactics.11 / 连续路标、职责匹配与双狙（2026-10-01）

- 保留 schema_version=1，新增可选 tactic.assignment（roster/ability）、human_slot（1–5）及 slot.duty（auto/awp/entry/lurk/rifle/igl）。旧库无字段时仍按名单顺序、真人槽1、自动职责；Python 校验保留旧 JSON 形状。只有能力模式允许换真人槽；职责允许重复，不要求五个独特生涯位置。
- arena_roles.tactical_abilities 在副本上复用五位置算法；请求 Bot 增加 tactical_abilities，真人增加 human_tactical_abilities。资料界面不显示五套评分。profiles 传递元数据，但不改变 Profile、VPK 或既有清单契约哈希；不修改存档、原有能力或角色。
- TacticalSlotAssignment 对完整五人先做全局最优一对一匹配：锁定真人槽，枚举剩余四人排列，以职责适配能力求最大和；同分用稳定 ID 顺序。旧请求缺能力元数据时使用有限的已保存强度回退和原角色同分倾向。选择成功后固化本回合映射，再过滤阵亡/接管/未绑定 Bot，绝不压缩剩余槽；半场换边保持原队伍身份。
- TacticalWaypointPolicy 只把 Advanced 且 wait==0 的中间点判为 transit。不调用额外 TryIdle，释放本动作的附属 lease，重置 DirectMove 并在同 tick 为下一单目标走原有 PathHold→MoveTo→ComputePath 接受流程。每 actor 每 tick 最多推进一个点；重叠下一点不强求空路径。正数等待与最终点保留原释放和停稳规则。不合并路线、不跳过绕路，不改 native DLL、坐标或速度。原生寻路限流仍可能产生短暂准备等待。
- BotBuy 1.0.12-career.3 提供 `career:tactical-buy:v1` 的官方 PluginCapability 通道，跨插件类型仅为 System.Func<string,string>，严格 JSON 传递 nonce/map/正式回合号/当前阵营/四名 Bot 的 SteamID 与职责。无新 shared DLL、控制台命令注入或逐 tick 文件读取。接口缺失/拒绝时显示购买未生效，路线仍可独立执行。机制出处：<https://docs.cssharp.dev/docs/features/shared-plugin-api.html>。
- BotBuy 重核唯一当前控制器、当前 pawn、实际购买区、冻结阶段及未被真人接管；阵营按实时 TeamNum 校验，不能用请求的开局 ct/t 判断换边后购买。明确主狙职责允许正常购买 AWP，资金不足不发枪。换购仅限本回合确认购买的唯一实体、可退款、非回合初携带武器；保留捡来/携带枪，真人不自动购买。不撤销已完成购买；取消/换战术只更新后续偏好，回合结束/卸载清理。新偏好重试用回合/版本号防止旧定时任务生效。
- 回归覆盖重复职责最优匹配、缺位置回退、真人槽、死亡/接管稳定映射、换边购买、nonce/地图/阶段拒绝、经济边界及携带/捡枪保护。编辑器控件仍稳定，不随后台刷新重建。构建与 EXE 自检都使用 D 盘隔离目录；上述规则通过离线检查不等于连续路线、双狙经济和 Capability 的游戏内集成已实测。

### tactics.12 / 自定义路点的跳跃交接（2026-10-01）

实机 tactics.11 记录了零等待路点完成后等待原生新路径接受的短暂停顿；旧开局跳跃令牌此时通常已结束。但旧日志没有跳跃按键或原生脱困计时，不能据此证明玩家看到的每次跳跃都是同一种原因。

- `TacticalPathJumpGuard` 为每个自定义路线 actor 持有独立的 JUMP-only 抑制令牌，复用已审计的 `OpeningLease`，不锁移动、不压制瞄准/射击/蹲伏，也不写原生 stuck 字段、坐标或速度。其他控制者的令牌不取消。
- 下一路点或实际重新建立路径时 `Begin` 一次；准备阶段与 `PathHold` 重叠。原生接受路径后，先 `Committed` 再释放准备移动令牌，避免同一帧重新放开 JUMP。提交后固定 0.75 游戏秒到期；赶路 Hurry 续期和限流重试不能延长宽限。未提交最多 4 游戏秒，原来的 DirectMove 3 秒准备超时仍保留。
- 正数等待转场只保留下一段的跳跃令牌，不保留旧移动/观察令牌；零等待经过点仍同 tick 接续。最终完成、路径失败、另一控制者占用、接敌/受伤/闪光/道具、接管/死亡/换 pawn/换边以及回合、地图和插件退出均释放。接敌判断在保位分支前处理，不能因移动仍在按时保位而遗漏跳跃让权。
- `custom_jump_handoff_begin/committed/released` 记录生命周期；`custom_airborne_started` 与三秒位置诊断记录实际离地、Z 速度、原生 IsStuck 和本 actor 的准备/跳跃令牌状态，不逐 tick 写盘。离地也可能是走下台阶，并非必然按了跳跃，不能只凭 Z 变化断言脱困。

有限窗口旨在消除换点起步补跳；正常越障在窗口后仍由原生处理。不改变 Rush、下包职责、购买、战术库格式或存档，也不更换底层 DLL。令牌与生命周期离线测试通过不能替代新对局的实际跳跃验证。

### tactics.13 / 连续途经点与逐段步态（2026-10-01）

tactics.12 的 `B3D32F4E914FE023` 仍显示零秒路点后的 `custom_path_pending,movementHeld:true`，有约 40 tick 的准备停顿。上一轮修的是跳跃交接，不是这段人为停止，本节取代早期“每点先持有准备令牌”的执行方式。

- schema_version 仍为 1，`step.movement` 可选 run/walk，语义是前往该目的地的路段，wait 是抵达后的等待。缺失默认 run；Python 不给旧步骤补写字段，显式值经保存、导入导出和启动快照保留。未知值拒绝。前端选择器保持原 DOM 与焦点，重排、复制与地图切换不丢设置。
- 零等待中间点须实际进入原来的到达范围，再由 `TacticalContinuousMove` 请求接续；不扩大半径、不合并路点、不按一条直线穿墙。只有上一段已经提交且仍拥有当前原生 MoveTo 目标时使用原子接续：`ComputePath(next) → MoveTo(next)`，均在同一服务器线程同步调用。限流时保持旧目标和路径，不创建 PathHold，不推进时钟阶段；每 0.125 秒重试，最多 3 秒。失败不能冒充成功，非限流的不可达会清旧路径，故立即释放该队员并提示。
- 首次出发、目标被替换、交火后的重建仍用原来的准备门；正数等待、重叠路点与最终完成按原规则处理。成功接续只推进一次并 `AdoptCommitted`，不重新进入准备暂停。旧目标在限流期间若自行完成，仍可能出现原生减速/Idle；不能据此承诺任何路口绝不减速。
- 当前 server 文件哈希保持原审定值。新增完整的 ComputePath、MoveTo Enter/Exit/Update、SetState、退出观察重置和入口条件查询静态摘要，以及运行时完整函数摘要、ASLR 后虚表指针与 Run/Walk 代码核对。实测环境之外的未知 Hook 不放行。ComputePath 的限流返回在 path invalidation 之前，成功时更新 repath timer；MoveTo OnEnter 的同帧限流不清掉新路径，OnExit/SetState 不清路径。只读取 schema RepathTimer，要求正常 Timescale=1、成功后的有限 Timestamp 和 0.4–0.6 秒 Duration，不比较错误时间源、不清原生 timer。成功后重新核对 pawn/状态/原目标，再换目标并检查新目标归属。
- `TacticalTravelGait` 使用已审计 BotController ABI20/22 的现有 SPEED 按钮接口，不更换 DLL。run 持有独立 SPEED suppression；walk 用 500ms 有限 SPEED injection，每 0.25 游戏秒或单调时钟秒续期，以先到者为准；每 tick 维护，不按 0.9 秒 Hurry 周期维护。续期先建立新 token 再取消旧 token，无持续累积；run/walk 切换先释放相反模式。有效 owned token 的 injection 取消返回 -1 表示已经过期/清理，不把它当成全队技术错误。未知返回和真正错误仍明确报告。
- 步态只控制是否静步，不注入 W/侧向移动，不写人物速度、视角、原生路径或 Hurry/stuck 状态；方向、转弯、碰撞仍由原生导航提供。首次 PathHold、正等待、接敌/受伤/闪光/道具、接管/死亡/换边/换 pawn、下包、回合/地图/插件退出释放 owned gait。空路线和真人不控制。新诊断记录步态与原子接续的 pending/committed/rejected，不逐 tick 写盘。

本轮改变默认赶路步态和零秒接续，不改变战术职责、双狙经济、下包守包、地图库或存档。纯步态/时钟测试、完整函数文件审计、编译和打包自检不能证明真人观感或实际多 Bot 路线已经通过，需新对局联合验证。
