# 3D 开发入口

规范源码是本仓库。旧版本解压目录只用于游玩，不在那里直接改代码。

## 新功能放在哪里

- 游戏规则：cs2career/career、league、engine。规则不认识 Godot、HTTP 和打包工具。
- 操作协调：cs2career/services。这里决定提交边界、会话切换、回执和外部任务。
- CS2 适配：cs2career/cs2。游戏路径、安装、结果读取、进程守护与环境恢复在这一层。
- HTTP：tools/career3d_service.py。负责鉴权、输入、调用服务与输出；不要把新业务放进路由。
- 手机／电脑：career_phone.gd、career_computer.gd 是宿主。device_pages.gd 接数据、发信号，不直接调用后台或更改宿主。
- 共用投影：device_page_data.gd；数字：ui_format.gd；主题：ui_theme.gd；样式构件：phone_ui.gd、computer_ui.gd、ui_kit.gd。

tools/career3d_* 的旧导入多数是兼容别名。新业务从 cs2career.services 导入，不从 tools 导入。退出守护独立运行，不加载生涯和 HTTP。

## 写入约定

普通业务操作交给 ApplicationState.operation。可以在内部多次声明保存，一次请求只提交一次。persist 只负责落盘，settle 才会推进自动安排和剧情。

已经提交但文件还没替换完会抛出 CommitPending。它不是可以忽略的普通文件错误。后台发送 storage_recovery_required，由恢复流程补全；不能再执行原命令。

Steam 启动与插件安装使用意图 → 外部操作 → 结果三步。不能自动重放。可以重新生成的战术文件与退役请求进入 external_effects，提交后执行。

重复请求查询中央回执；没有记录是“未知”，不是“未执行”。前端不自动重发写请求。读请求不能带保存、随机数消耗或收取比赛战绩等副作用。

## 比赛扩展

模拟、RTS、CS2 共用 engine/sessions.py 的身份和 data/match_rules.json 的规则，不共用物理实现。BO 系列每张图提交；换模式作废旧会话，不能覆盖已结算地图。

## 文案与页面

新设备文案加到 work/career3d_redesign/data/ui_messages.json，保留语义 ID，不从中文实时生成 ID。

- 每次重建的片段用 Locale.message(id, arguments)。
- 常驻原生控件用 Locale.source(id)，让语言切换自动更新已存在的按钮和工具栏。
- 改文案后运行 tools/build_career3d_locale.py --patch，审核并应用补丁；测试会检查占位符、双语完整性和目录是否同步。
- 玩家姓名、战队身份、保存的消息和协议参数不是翻译键，不能按展示文本执行操作。

旧目录保留给历史剧情和专用子页兼容。新页面不要继续添加依赖完整中文原文的查找。

## 验证与打包

后端测试必须通过 tools/run_tests.py，先隔离存档路径再导入应用。Godot 测试用 --no-service，不连接玩家后台。

tools/package_career3d.py --ordinary-only 从当前源码重新冻结后台和整理 Godot 运行包；不要用只覆盖文档的旧包工具代替构建。

解压后运行 tools/verify_career3d_distribution.py --backend <解压包的后台 EXE> --qa <新目录> --workflows。它验证实际二进制，不依赖开发电脑的 Python 源码。真实 CS2 插件兼容性仍须进入本地对局验证，不能用模拟结果代替。
