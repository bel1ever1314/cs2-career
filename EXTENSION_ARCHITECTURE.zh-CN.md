# CS2 Career 1.5 桌面版与扩展架构

## 页面原位刷新（steady.1）

`web/static/desk/dom.js` 提供 `CareerDOM.paint(host, html)`，通过 `CareerUI.paint` 供页面使用。
它只负责表现层，不发请求、不修改生涯状态、不替换全局 DOM API。常规页面刷新应使用此入口，
随后重新绑定页面的 `onclick/onchange` 等属性处理器；旧处理器会清理，避免按钮复用时执行旧命令。
重复列表建议提供稳定 `data-ui-key`；比赛节点用比赛ID、邮件用邮件ID、饰品用物品ID。
图片源没变时不重写 src，原有节点、输入焦点、展开状态尽量保留。HTML 中所有扩展文本仍须经过 esc，
不要将扩展包字段直接拼成 HTML；局部更新器不代替内容校验。脚本节点不会插入文档。

`desk/assistance.js` 的 session 只保存本次观赛面板和图视角。遇到剧情暂停保留 session，
通过原有 story_queue / ack 后继续；非剧情阻塞、手动比赛、稍后决定或结束时释放。
`app.js` 在面板存在期间不重绘背景，退出时统一更新；它不跳过任何后端结算。
验证入口为 `tools/test_steady_browser.cjs`（Playwright + 独立无头 Chrome，无正式存档）
和 `tools/test_assistance_ui.cjs`（确定性模拟命令与暂停/继续）。

## 职业生活章节（stories.1）

沿用 incidents 包、现有 story_queue 和 ack 接口；新增的 `arc_overrides` 包含 `rules`、`chapters`、`endings`。
只想改奖励：`{"schema_version":1,"arc_overrides":{"rules":{"focus_reward":2}}}`。
单项覆盖示例：`chapters.romance_pace.choices` 写 `[{"id":"focus","reward":4}]`，只改变克制选项。
内置动作不可从包内替换；新增章节只允许 continue / finish，并能通过 next 或加权 branches 接后续。
规则在content/rules.py入口校验，由career/arcs.py执行；扩展数据没有脚本权限。
见 `extensions/_templates/career-arcs-pack` 的完整可验证示例和中文TXT。
给钱/技能点/暂停比赛/条件标记仍用下面的通用 effects；游戏内聊天仍用 match_chat。

## 转会修复与选择后果（transfer.2）

复用 `incidents.emit → story_queue → Career.ack_story → incidents.resolve`，不是另建剧情引擎。
`effects` 新增 `{"type":"skill_points","amount":2}`（0—100整数）与
`{"type":"competition_pause","amount":7}`（1—365天）；暂停 amount=0 表示提前恢复。
后续剧情仍由同包 `conditions.flags` 分支。累计奖励受单选项上限校验；所有效果先验证再结算。
已确认的 story_id 不重复执行，奖励结果另排入 `incident_result` 普通弹窗。
暂停存于可选 `incident_state.competition_pause={until,reason}`，日期到期即恢复，无需作者再发恢复事件。
已有地图或 CS2 回传中的系列赛不能被暂停；每段事件须有不扣钱、不暂停的退路选项。
未来开赛报名受限制；已排比赛在推进时通过现有弃权路径结算，不补造战绩、不奖励弃权参赛点。
日常训练不受限制。作者验证包：`extensions/_templates/choice-effects-pack/`，含普通玩家可读 TXT。

邀请的 `team_id` 是收件俱乐部，不等同于当前 `Career.team_id`。转会前标记旧函、变更身份后再发新函。
旧转会存档未标记的邀请先备份并失效，重新确认新队邀请，不猜测同一天的归属，不重算过去赛事。
所有告别选择追加各自回应并发放1点；已在旧版确认的告别不会追溯重发奖励。

## 对话调度 v2（dialogue.2，优先于下方旧版描述）

作者文件仍使用 schema_version=1，新增可选 scenes 数组；场内请求 contract 升为2。
旧 contract=1 的全局单句调度保留兼容；新构建一律生成 contract=2。
v2 普通聊天分 coach 与 player 两个槽位，各自每回合最多一句，队友/对手共用 player。
不再使用全场八条/两回合全局冷却，规则仍受自身冷却、概率、次数上限控制。
`scenes[].sequence` 为有序多角色对话，优先于 rules；每回合至多一段，先预解析全部人物，
缺人整段跳过。同优先级保留 registry → file → array 顺序，未选中的剧情不进入积压队列。
`MatchDialogue.EndRoundBatch` 返回不可变文本快照和相对延时，`DialoguePlayback` 提供 epoch/索引闸门；
适配器串联服务器 timer，取消旧队列不影响事件账本。地图变更、回合重启、冻结结束或身份异常停止剩余台词。
作者可复制 match-scene-pack，其 TXT 教程含第一回合双通道和第三回合剧情测试。

## 比赛聊天与生涯事件接口（dialogue.1）

新增两类 JSON 包，均使用 `pack.json schema_version=1` 和内容 `schema_version=1`。
`match_chat/` 不是脚本：`content/rules.py` 校验 → `cs2/dialogue.py` 合并内置与扩展规则 →
`prepare_game()` 冻结到 `match_request.json.match_chat` → C# `MatchDialogue` 纯规则引擎 →
`CareerMatch.Dialogue.cs` 从原始身份账本读取正式回合快照并发送聊天，不改写统计。
旧请求缺少此字段仍兼容；无效聊天配置只停用聊天。设置开关下场生效。

`incidents/` 与原 `events/` 不同：前者是选择与后果，后者始终是赛事日历。
`career/incidents.py` 提供 emit/resolve/decorate，`Career.emit_incidents` 是核心触发接口；
扩展不能导入 Python，不能执行控制台命令，不能任意写存档属性。
待处理决策冻结在 story_queue，复用现有带会话校验的 `/api/story/ack`；
消耗记录与包内 flags 保存到 schema-v2 的可选 `incident_state` 字段。
原内置假赛、教练缺席的业务逻辑仍在 Career，overrides 只改弹窗文案，不改概率或结果。

作者可直接复制 `extensions/_templates/match-chat-pack` 或 `incident-pack`，
两包中的 README.txt 列出全部触发点、条件、占位符、效果和边界。
示例不默认加载；教练示例不代表已实现完整教练合同系统。
当前无音频、独立 HUD 布局、任意脚本效果，也没有未经核实的真人名场面内置台词。

## 分层

```text
main.py
  ├─ desktop/webview_app.py  WebView2 窗口、本地服务及退出生命周期
  ├─ web/server.py        注入唯一状态、回环 HTTP、会话校验、命令锁
  ├─ web/static/desk/     模块化桌面显示与交互，不实现玩法公式
  ├─ presentation.py      资料、历史比赛、赛事图及统计读取模型
  ├─ application.py       UI 无关的状态、存档与命令边界
  ├─ career/              生涯、经营、邮件、剧情、皮肤
  ├─ league/              日历、赛事、赛制、排名、赛季推进
  ├─ engine/              比赛事件、能力、Rating、心态等纯规则
  ├─ world/               年代、队伍、选手、角色与地图数据
  ├─ cs2/                 插件安装、九人档案、真实比赛结果
  └─ content/loader.py    JSON 扩展包扫描、校验和错误隔离
```

界面中不写玩法公式。桌面按钮调用 `ApplicationState` 或领域对象，网页兼容入口也调用
同一对象。这样新增界面不会产生第二套玩法。

## 自建开局

三种开局集中在 `cs2career/career/origins.py`，同时控制个人能力、队友区间、选手来源、
俱乐部与个人现金、属性点、指挥和心态。

- 路人：个人 60，队友 54–64，俱乐部 $120,000，3 属性点；经济宽松但比赛最难。
- 青训：个人 68，队友 60–70，俱乐部 $90,000，1 属性点；最均衡。
- 天才：个人 78，队友 54–64，俱乐部 $70,000；能扛比赛但团队和财务最脆弱。

三个选项不是简单难度档，而是即战力、阵容深度和现金之间的取舍。经营收入与支出
直接进入现金流；邮件只负责邀请、合同和剧情决定。

## 每年青训的维护入口

`world/academy.py` 负责新人身份和参数；名字来自 `data/academy_names.json`（当前80个），
不复用已生成、现役、自由市场或隐藏名单中的身份，按稳定ID的大小写规则去重。
普通跨年2人；以生涯开局为第1年，第3/7/11……年共3人，其中1名天才。
生成时16–18岁；固定池耗尽停止生成，没有无限随机补名。此处是内置资源入口，
尚未提供独立青训类型的工坊热加载接口，不要把直接修改源码资源误称为扩展包安装。

调用链为 `Season.roll_year → Career.tick → _age_year → _academy_intake → _ai_window`。
`last_age_year` 防止重复tick或重载再发一批，`academy_used` 防止已登场身份被重新生成。
`academy_year` 保存入市届别，`note` 区分academy/wonder，`potential` 参与23岁以前成长。
`_signed` 必须保留以上字段，覆盖玩家普通签约、保签和AI签约路径。
`transfers.candidates` 输出这些资料，`desk/transfers.js` 的“青训观察”跨自由/现役两池筛选，
不另造一套交易规则；现役青训仍需买断。潜力值不保证最后能成长到该数值。

专项回归在 `tests/test_academy_intake.py`。跨年用的是赛季末构造数据，
不是完整打完三季的可玩性证据；初始青训开局与每年青训补充是两个独立入口。

## 扩展包生命周期

1. `content.loader.PackRegistry` 扫描 `extensions/*/pack.json`。
2. 清单和 JSON 先校验；包内任一结构错误会拒绝整个包。
3. 按 `load_order`、包 ID、文件名稳定排序，保证同一内容可复现。
4. 剧情、皮肤可在桌面端重新扫描；赛事、战队、年代只在新生涯生效。
5. 扩展不会写回包目录、不会执行 Python，存档只保存稳定 ID。

作者入口和例子见 `extensions/README.md` 与 `_templates`。新增类型时，先在 `KINDS`
声明，再由所属领域读取 `registry.payloads(kind)`，不要让 loader 反向依赖玩法模块。

## 启动

`py -3 main.py` 打开桌面版。旧网页只保留为兼容调试入口：`py -3 main.py --web`。
发布版默认使用无控制台窗口的桌面程序。

## 新桌面模块维护（重建第一阶段）

- `desk/navigation.js`：统一资料路由、前进/返回、筛选和滚动恢复。
- `desk/profiles.js`：战队、选手、Top20及数据榜。
- `desk/competitions.js`：赛事节点、晋级连线、逐图战报与回合详情。
- `desk/collection.js`：库存/市场卡片、物品详情和开箱展示。
- `desk/economy.js`：资金预测、账本、借款/还款/捐款，不放饰品操作。
- `desk/settings.js`：游戏路径、插件、Bot参数和换肤偏好，独立于训练资格。
- `desk/setup.js`：读取后端开局目录、保留建档草稿，成功建档前不清空旧档。
- `desk/workshop.js`：扩展目录、启用/拒绝状态、具体错误及会话校验的重载入口。
- `desk.css`：以上新页面的视觉规则；兼容页面仍由原样式维护。
- `theme.css`：最后加载的 Midnight Club 配色层，统一新旧页面；不覆盖饰品稀有度含义。
- `skin_art.py` 与 `data/skin_art.json`：按编号映射、受控获取和缓存图片；不是任意 URL 图片代理。

`create_server(state)` 注入一个 `ApplicationState`。桌面窗口与游戏接口复用该对象，
网页请求在服务端锁内执行。`X-Career-Token` 校验本地 UI 请求；资源 URL 不获得脚本执行权。
新读取接口为 `/api/inspect`（kind/id/range/page）、`/api/match`、`/api/event`、`/api/events`。

### 跨年资料标识

日历的事件 ID 会逐年复用，不能直接拿它合并历史赛事。
读取模型提供 `2026::事件ID`、`2026::比赛ID` 作为带年份的浏览键。
`/api/events`、选手比赛记录、赛事图节点都输出这种键；旧的裸 ID 仍优先查询当前赛季，
没有当前结果且存在多个同 ID 历史结果时拒绝猜测。当前和往年同名赛事可同时打开。

`match.id` 仍是引擎原 ID，当前比赛按钮用它提交命令；`match.route_id` 是永久浏览键。
不要把浏览键写进邀请、赛事资格或 CS2 nonce，也不要为修复界面去改旧存档赛果。
历史详情的 `yours=false`，防止往年记录暴露当前比赛写入控件。

历史选手从已保存地图行中的 player_id 解析，不依赖现役名单仍然存在。
未记录的年龄、能力与七维属性不推算。同名身份冲突时不按名字合并战绩或授予荣誉。
归档赛事使用保存的 mvp/evp 摘要恢复荣誉显示，不能因缺少运行时 awards 字段显示为空。

扩展接口为 `GET /api/extensions`、`POST /api/extensions/reload`。坏包结构被拒绝，不执行脚本；
领域级完整参数校验仍需完善，不能把结构校验称为任意扩展都安全兼容。

## 隔离验证与存档替换

### 批量生涯与开局身份（2026-09-09）

`tools/career_matrix.py --output .qa/reports/full-season-matrix` 默认运行
2024/2025/2026 × 路人/青训/天才 × 固定种子17/29/43/71/101，共45条完整首季。
这是运行命令说明，不表示这45条已经验收。每条独立子进程通过 `playthrough.py` 的同一HTTP业务路径，
临时存档和扩展目录互不共享，默认最多同时2条，不加载用户扩展、不访问CS2。

可用 `--until first-event --seeds 17 29` 做18条短流程。短流程不计作完整首季；
`--region AS/EU/AM` 使用游戏已有赛区，而不是虚构独立的NA/SA赛历。
矩阵的 `matrix.json` 记录完成数、失败数及每条报告，单条详细结果与日志单独保存。
`--resume` 只复用同目标、同地区、同策略、同种子、同源码/数据指纹且重载验证通过的结果；
不匹配时拒绝覆盖旧报告，使用新输出目录重跑。失败样本仍保留，不能只统计成功样本。

`tools/flow_evidence.py` 只处理报告，不导入应用。计算正式比赛日期间隔时排除失败尝试与同日重复比赛，
未到下一场的尾段标注为观察未结束，不将“没有正式比赛”等同于“完全没有可做的事”。
`playthrough.py` 的 `failure_match` 保存触发完整性断言的战报，便于复现，而不是仅保留一条报错。

新建战队的 `_spawn_org` 使用当前年代所有在役姓名及玩家自定义姓名作为队友排除集。
静态自由选手池只是候选源，不代表每人在每个年代均自由；禁止克隆在役选手，候选不足时报错。
`engine.match.validate_rosters` 在比赛随机数抽取前校验双方各5人、非空且不重复的昵称，以及已提供ID的唯一性。
目前模拟事件账本仍以昵称索引，因此即使ID不同也不允许双方同昵称；不能宣称已经完全支持同名不同人。
缺ID仅为旧引擎测试数据保留兼容，正式战报和CS2身份接口仍要求完整身份。
不自动改写已经保存的错误历史战绩；已有重复名单应通过阵容编辑/转会处理，或用新生涯验证修复。

### 随机序列与排名计算（2026-09-09）

`random_state.py` 用纯JSON保存两条现有随机序列：比赛 `engine.match.RNG` 与
经营/剧情/饰品使用的 `random`。`Season.save` 记录进度，`load_or_new` 校验并恢复。
包括高斯采样缓存，不只保存最初种子；读档不重新抽下一场。schema_version仍为2，
字段 `random_state` 可选；没有该字段时无法恢复从未保存过的历史随机进度。
不使用pickle，不从扩展执行代码；两条序列都验证成功后才恢复，坏数据不静默重置。
这仍依赖“单个ApplicationState＋串行命令”的应用契约，不能让多个生涯共用同一进程并发推进。

`VRS.table` 现在一次遍历历史赛果，按日期复用衰减系数，保持各队原来的浮点求和顺序。
不维护跨请求缓存，所以比赛、日期、队伍编辑后立即可见。批量邀请复用一次排名查询，
`eligible_invite` 单独调用仍能自行查询；资格、奖金、排名公式均未变化。
回归分别位于 `tests/test_random_state.py`、`tests/test_ranking_performance.py`。

`tools/playthrough.py --until next-season-event --reload-every 50` 会实际玩到下一季首个赛事完成，
并每50条业务命令重载真实存档、核对随机序列。`--years N` 指定先完成的赛季数。
报告新增青训批次及逐队已完成赛事次数，未完成的年度显式标注，不冒充全年参赛统计。

`tools/run_tests.py` 在导入业务模块之前设置存档、扩展及禁用游戏标记，再发现测试。
`tools/playthrough.py` 在临时目录创建真实 ApplicationState，通过本地 HTTP 命令推进，
不直接修改日期/资金/属性，不加载展示赛事。它是流程探针，不是已完成的长期策略矩阵。

`Career.path()` 同时控制保存和加载路径；不能只替换查询路径却另读写固定全局路径。
单文件保存先写 pending 再替换。创建/重开先在内存验证候选生涯，备份现存两份 JSON
到 `save/backups/时间戳-随机码/` 后才替换。损坏的版本2存档报错并保留原文件。
两份 JSON 还不是可抗任意断电的单一事务；后续需要成对提交/恢复协议。
历史比赛只读快照；缺失统计不重新模拟。聚合统计依据回合数和原始计数重算。

`design_preview.py` 构造独立展示数据；不用于证明长期生涯平衡。请阅读
`DESKTOP_REBUILD_STATUS.zh-CN.md` 的未完成清单。扩展包本地图片及所有兼容页面迁移尚待完成。

功能归属原则：跨页可以提供跳转提示，但不可复制同一套写操作。开箱和待处理结果仅在
武器箱操作；市场只购买，库存只装备/出售；经营只做资金管理。新增页面应扩充
`tools/test_desktop_ownership.cjs`，避免再把功能混回旧脚本。

## 旧 Tk 桌面维护（历史实现，当前源码默认入口不再使用）

原生界面拆为六个职责清晰的模块：

- `desktop/app.py`：窗口、导航、保存、新生涯备份，以及耗时命令队列。后台线程只写队列，Tk 主线程负责更新窗口。
- `desktop/pages.py`：生涯、阵容、比赛、经营、收件箱、转会、训练、收藏、工坊和设置页面。
- `desktop/setup.py`：全页式生涯创建；草稿在切换开局时保留，提交前校验名称，取消不会清空旧档。
- `desktop/widgets.py`：滚动区、余额悬浮提示、PNG 队标、能力条与战术示意图。滚动绑定随页面销毁。
- `desktop/theme.py`：统一色彩、字体和状态文案；美术修改从这里开始。
- `desktop/skin_api.py`：CS2 使用的本机饰品接口，直接读取当前桌面生涯，避免启动第二份存档状态。

页面必须按公开数据契约读取比赛：`your_match.event` 是赛事，`your_match.match` 是对局。
不得把整个 `your_match` 当成对局对象。饰品价格使用当前 `spot`，装备操作使用库存 ID 和 `ct` / `t`。
剧情按钮由领域事件提供的 `choices` 生成，不能在界面重新猜测选项含义。

验证界面：`python tools/desktop_preview.py --smoke`。该工具生成隔离生涯，覆盖两个窗口
尺寸、全部页面、三个开局、比赛 ID 传递与购买/装备/卸下流程。省略 `--smoke` 可打开
隔离预览；`--compact` 使用小窗口。预览不会读取玩家的 career/season 存档，也不会写游戏插件。

打包器保留发布目录已有的 `save/` 和玩家扩展；分发 ZIP 排除存档及玩家安装的扩展，
只包含程序、说明和制作模板。
## 生涯年龄与训练契约（2026-09-09）

### 剧情、奖项、专栏与买断接口

故事仍由 `stories/*.json` 提供，模板见 `extensions/_templates/story-pack/`；把模板复制到 extensions
根目录的独立包文件夹后才会加载（下划线目录故意跳过）。`id` 全局唯一，`when/title/text` 使用文本；
支持 origin/class/type 等过滤与上下文占位符。工坊重载后，对应触发条件下生效；已经确认的同id不再弹。
这是数据型叙事扩展，不是任意Python脚本或通用剧情奖励执行器。first_lan / first_final 只允许大赛。
`tests/test_editorial_transfers.py` 包含可复现的成功加载/触发/确认/重载/禁用测试。

比赛选手行的 `role` 是当场位置快照，赛事累计行 `role_maps` 用于判定主要位置；最佳阵容每位置最多一人。
新年代或赛事包不要把未知旧位置补成 rifle 来凑奖项。年度前三名的 `feature` 包含 title/subtitle/sections，
只存纯文本，通过 `desk/editorial.js` 转义渲染。`verse.py` 根据存档证据生成，不调用外部模型或执行扩展脚本。

`GET /api/transfers` 按稳定ID返回普通价/概率/失败费、保签价、卖家与禁转会原因。
`POST /api/market/buy` 支持 mode=normal|guaranteed、player_id、seller_id、replace_id、fee；保签重新核价。
普通签约保持旧规则，保签在 `career/transfers.py` 集中预检查资金、五人阵容、赛事锁和同位置替补。
报价不得信任前端金额；成功扣费、移动球员、卖方补位后由 ApplicationState 保存，未知或重复请求不重复买入。
3倍/5倍阈值使用长期基准，避免临时改位置压价。工资和赛事平衡不在本模块调整。

扩展包/开局显式提供的 `player.age` 必须保留；位置整理不再按姓名和年代重写年龄。
跨年由 `world/aging.py` 推进。缺失年龄可以按当前年份估算，已有旧错误数值不能凭姓名猜测修复。

`Career.training_session` 是 schema v2 可选字段，旧档默认无待结算训练。
只有 `start_match(..., purpose='training')` 成功启动后登记训练身份；正式赛事默认 `purpose='series'` 不登记。
`finish_training` 使用请求nonce读取匹配结果，再核验日期、所属队伍、地图、十人身份与结束状态。
发奖与消费会话在同次 Career.save 保存；新入口不得绕过这个业务方法直接增加心态。
隔离测试不得使用正式存档或真实游戏目录；模拟回传夹具通过仅代表契约逻辑测试。

## 独立2025组织包与日期边界（2026-09-09）

`cs2career/data/eras/2025.json` 现与2024使用同一加载器，独立声明59个收录组织。
开局仍为1月8日，日期精度为日，纳入当天已公布的变动；不是赛季结束阵容。
以1月6日排名快照为底，补上1月7–8日SINNERS、Fluxo、ECLOT、GamerLegion及fnatic变动。
不将1月9日以后的转会预先写入。开局之后由生涯规则发展，不强制复刻现实转会。

`sources[].observed_at/published_at` 若提供，必须是有效日期且不晚于开局。
后来的公告可作为“为什么没有加入该人”的证据，须标注 `purpose: "exclusion"`；
它不能是唯一来源，也不能授权名单加入该人。具体身份与公告内容仍需要人工核验，
JSON日期校验本身不可能判断文字里的真假。

转会期名单不满五人时保留已核验核心，用明确的 `TEAM 2025 slotN` 补足游戏席位，
标记 `identity_quality: "estimated"`、队伍 `roster_quality: "partial"`。
HEROIC当日没有完整主力，整队占位标记 `estimated`；M80的k1to标记 `stand_in`，
全队为 `provisional`。不得给缺失名单加上 `verified` 来去掉界面提示。
当前41套完整名单、1套代打名单、28名占位；属性/年龄/地图仍非完整历史数据。

## 独立2024组织包（2026-09-09，覆盖下方早期说明）

最新入口是 `cs2career/data/eras/2024.json`，不是修改2026的TEAMS再重命名。
`world/era_data.py` 的 `world_manifest/validate_world/team_rows_for` 负责读取、严格校验并适配旧构造接口；
`opening_rank/roster_for/build_teams` 优先读取独立年代文件，再退回旧表。
新文件包含54个所收录组织，每个都有自己的 `id/name/region/seed/players`，其中47队五人名单核验、1队过渡代打、6队仍有空缺。
这不是全球所有组织名录，也不代表历史能力窗口已经完成。2025/2026仍是旧版资料，不能以2024修正结果替它们背书。

- `seed`：收录世界中的连续开局排序，供既有经营/赛事逻辑使用；不是完整现实世界排名。
- `source_rank`：来源中的原始名次，可不连续；`null` 为未核验，不能填游戏排序假冒现实名次。
- `observed_at/as_of`：证据时间与开局截点；未来名单拒绝加载，源页面顶部的现代资讯不作为历史证据。
- `roster_quality`：verified/provisional/partial/estimated，只有五人身份都核验才可标 verified。
- `ability_source/ability_quality`：本轮仍为旧2024目标值或同年代档位估算，不读取2026全局属性倒推。
- `is_igl`：选手可在主狙等位置兼任指挥，整理阵容时不再额外强造一名指挥。
- `allow_no_awp`：例如2024 Cloud9，允许没有专职主狙；不把最强步枪手强制改为主狙。
- `roster_status: stand_in`：代打身份，与正式签约分开。MOUZ的Brollan按2023年12月已出场代打阵容暂列，不能宣称1月8日已正式租借。

内置年代校验覆盖组织ID、连续seed、真实名次类型、五人唯一、跨队大小写别名重复、来源URL和日期、有限能力值及核验标记。
新增年代组织名单时无须和2026的49队逐一匹配。仍需更新 `ERA_META` 才会出现在开局选择中；自动发现任意内置年份尚未实现。
外部作者修改现有年份仍走下方 `teams` 扩展接口，本轮没有将整个独立manifest开放为任意用户脚本或热加载代码。
自由市场与自建队友选择按大小写折叠排除现役，避免 SunPayus/sunpayus 同时出现。

用户已确认当前为可丢弃的测试进度：本阶段不用做旧测试档迁移，不要求为占位身份维护复杂兼容。
这不授权清空配置或扩展包；新检查点用新生涯验证，未主动删除旧目录。
历史地图池、真实年龄补全、历史能力窗口、54队的全年赛事覆盖仍待独立验收；本轮没有改奖金/工资/胜率公式。

## 历史阵容补丁与核验状态（2026-09-09，早期检查点）

`world/eras.py` 的旧表是部分名单，不是完整独立历史包；其 `curated` 仅代表旧版人工表，不代表经过来源核验。
缺少名单的历史战队由 `_estimated_roster` 生成 `队名 年代 slotN` 虚构选手，不能给这些 ID 的旧战绩套上真人姓名。
旧测试只验证49队各五人、ID唯一，不是历史真实性验收；测试名称已明确这一边界。

新增 `data/era_rosters.json` 保存有日期/来源的内置阵容修正，`world/era_data.py` 校验并读取。
目前只补入2024-01-08的PARIVISION五人身份，能力继续按同年代档位估算；不是完整2024包。
`roster_for` 优先取修正名单，`build_teams` 使用修正中的位置/能力，不读取该选手的2026全局属性再倒推。
只有创建新生涯会应用修正；已有生涯、战报、转会、成长与历史身份不迁移。

每条修正包含 `era/team/as_of/announced_at/players/sources`，能力必须有限且在45–100，五人姓名唯一。
公告不得晚于该开局日期，引用必须能解析；同一年代的跨队ID重复仍由世界校验拒绝。
`era_provenance` 是存档v2可选字段，分别标明身份、能力、位置、年龄的质量。
`quality_view` 只读取对象已保存的来源，不能用今日的新包反向宣称旧档已核验。
`GET /api/setup` 增加 `data_coverage` 与各队 `data_provenance`；`GET /api/inspect` 增加 `data_provenance`。
界面显示开局核验覆盖率和占位人数，来源文本经过转义，不赋予脚本执行能力。

玩家修补现有2024/2025/2026名单：使用 `extensions/<包名>/teams/*.json`，不是重新注册同名 `eras`。
`eras` 扩展目前只添加新年代ID，已存在的ID会跳过；`teams` 载荷中的 `era: "2024"` 才是定向覆盖接口。
包清单声明 `types: ["teams"]`；数据沿用 `_templates/team-pack` 示例，顶层增加 `era`，队伍 `id` 与原战队相同，提供完整五人。
支持指定 player_id/name/role/ability/age/form_delta；位置不再被全局现代位置表覆盖，但仍要求队内有指挥和主狙。
加载扩展不自动代表历史真实性已核验，界面标为“作者提供”。扩展加载/跨年隔离/旧世界不变已由真实注册器测试覆盖。
目前外部队伍包只做原有的队内身份校验，跨队重名/ID等仍需作者审核；不要把内置补丁严格校验描述成所有扩展都已具备的保证。

## 位置能力补充（2026-09-09）

选手详情仅展示当前位置能力，不展示五位置评分矩阵。不要在扩展界面中默认公开另一套评分列表。

算法集中在 `cs2career/world/ability.py`。`stats.ability` 是校准基准，
`stats.role_reference` / `stats.role_reference_score` 是最初位置及当时未截断的加权分数；
`player.ability` 是当前位置能力，`player.long_term_ability` 是原基准位置在当前属性下的长期实力，
`form_delta` 是独立短期状态。换位置必须保留基准，调用 `refresh_player_ability`，不能重新校准。

当前位置能力 = clamp(基准能力 + (当前属性在目标位置的加权分 − 基准加权分) × 58 / 62.52, 40, 100)，保留一位小数。
步枪、突破、指挥保留旧权重，主狙保留步枪权重加 0.06 × 狙击；自由人新增独立权重：
火力24、突破8、补枪26、首杀10、残局28、狙击4（总和100）。道具仍用于队伍赛训，不重复计入个人枪法。

属性点改变七维后重算能力。跨年按长期基准计算成长/衰退，再校准新属性；不能用临时位置决定永久成长。
模拟与CS2请求均通过 `playing_ability` 读取当前能力；难度和状态在各自边界叠加，不写回基准。

年代包/青训/扩展选手在创建时校准。旧 schema v2 选手缺少参考字段时，以存档当前能力和当前位置补齐，
不猜测旧存档以前换过什么位置。应用保存新字段前备份原存档对；历史比赛快照不重算，不要求重开。
新增测试请通过 `tools/run_tests.py` 隔离运行，重点参考 `tests/test_role_ability.py`。
## 个人转会接口（1.5.0-transfer.1）

`career/player_transfers.py` 是个人加盟唯一业务入口，`career/transfers.py` 继续负责俱乐部买人。不要在 JSON 效果里直接修改名单、身份、债务或冷却。

`GET /api/player-transfers` 提供角色报价、精确成功率、阻止原因、最后一次骰点与转会历史；`POST /api/player/transfers/apply` 接收稳定 `team_id` 和 `role`，不接受客户端骰点。签约通过已有 `/api/story/ack` 决策，不另设可绕过剧情的换队接口。

存档仍为 schema 2，新增可选 `personal_transfers`，包含 attempts/offers/moves、日期冷却、pending、hooks 和 player_only。旧存档缺省为空，不要求重开。历史比赛不重写。`ApplicationState.personal_command` 在服务器锁内备份并保护 career/season 两份存档，遇到中断时在加载前根据本地恢复记录恢复整对。

剧情触发点：`transfer_offer_received`、`transfer_application_success`、`transfer_application_failed`、`transfer_stayed`、`transfer_departed`、`transfer_joined`、`transfer_former_team`。条件支持原队/新队稳定ID、位置、来源及告别选择。转会通知先冻结排队，等内置去留和告别完成再处理扩展，不阻塞尚未完成的签约。每个通知最多命中一条规则。

示例：`extensions/_templates/transfer-story-pack`。加入新队的不同选择通过包内 flag 连接到后续 day 事件；转会引擎不执行脚本。离队/加盟扩展的俱乐部效果针对**当前新队**，不跨队写旧俱乐部。
