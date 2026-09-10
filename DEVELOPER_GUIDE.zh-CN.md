# CS2 Career 1.5.0 开发者接手指南

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
