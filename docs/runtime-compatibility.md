# 人机增强兼容安装

在 3D 版的手机或电脑设置中选择已经解压的 Bot Improver 发行包，关闭 CS2 后点击“安装填写目录的人机增强”。安装器以官方 1.4.5 的行为、瞄准、状态、道具和游戏配置为基础，搭配我们选定的底层组件，再加入生涯程序自己的朝向、战术导航和买枪修复。填入旧发行包或上一版兼容目录，也会升级到这套版本，不会继续沿用旧的 BotAI、BotAimImprover、BotState 和 NadeSystem。每个 ZIP 都先核对 SHA-256，原发行包不会被改写。

兼容副本与下载缓存在独立生涯目录的 `runtime-cache` 中。安装前的游戏文件备份放在 `install-backups`。全部安装成功后，设置中的增强路径切换到兼容副本；开赛和恢复饰品组件也使用这个副本，避免重新复制旧 DLL。再次安装会核验并复用缓存。

打开设置、保存路径和刷新状态不会触发下载，也不会修改游戏。明确点击安装后，先复用本地已核对的组件和缓存，仅下载缺少的固定版本组件；下载失败或校验失败发生在写入游戏之前，重试会复用已完成的下载。完整随包增强仍可离线安装。完整增强 ZIP 只提取游戏运行文件，不提取或执行其中的 Panel 桌面启动器。CSS 的配套 .NET 运行环境随官方组件安装。原有 BotHider 与 BotVision 设置会保留，身份名单、库存、旧比赛请求和个人日志不复制到兼容缓存。

## 当前组件

版本清单在 `cs2career/data/cs2_runtime_compat.json`，当前为 `windows-20261015.1-cs2-2000933`。

- [CS2 Bot Improver 1.4.6](https://github.com/ed0ard/CS2-Bot-Improver/releases/tag/v1.4.6)：保留 BotAimImprover 2.1.6、BotState 1.10.2 与相关运行文件；发行 ZIP 为 73,126,151 字节，SHA-256 为 `e66a17329ccb00b340555fb64b09b0771ea4a0aa04566e7b9a915d7ad4c6f28e`
- [Metamod 2.0.0.1474](https://github.com/alliedmodders/metamod-source/releases/tag/2.0.0.1474)
- [CounterStrikeSharp 1.0.376](https://github.com/roflmuffin/CounterStrikeSharp/releases/tag/v1.0.376)，含 .NET 运行环境
- [BotController 0.7.0](https://github.com/XBribo/CS2-Bot-Controller/releases/tag/v0.7.0) 为独立组件回退版本；官方 1.4.6 中已审核的 0.7.1 原生／托管／API 组合整套保留，禁止只替换其中一项
- [BotHider 0.5.1](https://github.com/XBribo/CS2-Bot-Hider/releases/tag/v0.5.1)，含身份接口和复活逻辑修正
- [BotVision 0.3.0](https://github.com/XBribo/CS2-Bot-Vision/releases/tag/v0.3.0)
- [BotRandomizer 1.3.2](https://github.com/ed0ard/CS2-Bot-Randomizer/releases/tag/v1.3.2)，使用官方更新的签名与饰品数据

当前目标为 CS2 build 2000933；测试边界见 `CS2-2000933-测试清单.md`，此前 2000930 的核对记录保留在 `tactical-server-2000930-audit.md`。独立 Controller 0.7.0 原生 DLL 的 SHA-256 为 `8645168d4bb6a55ce8a8ac4246bce394496e4eecf4f56c2f2a7932a98eb75d61`；官方整包 0.7.1 的配套文件在 `cs2_runtime_files.json` 中整组校验，不能只追随组件的最新版本。

完整官方 1.4.6 的已校验组件优先复用，无需降级或下载。旧 1.4.5 来源在明确安装后补齐固定的 1.4.6 组件，原目录不变；146 变体校验覆盖 Controller、API、Randomizer、Aim 和 BotState 配套文件，145 变体仅保留已审核的配套组件识别，不允许旧行为 DLL 冒充 146。安装时 CareerMatch、BotBuy 与 BotAimImprover 使用本项目 `vendor` 中的构建覆盖到游戏目录；其中 Aim 的 schema 补丁对应源码与许可证也随包提供。独立 Randomizer 回退版本为官方 1.3.2。

`overrides/scripts` 中的行为资源参与复制、校验和缓存失效检查。上游的 `botprofile.vpk` 和用户生成的名单不直接复制；生涯程序仍为当前这场比赛生成对应的九人或十人名单，同时加入官方 1.4.5 的两份匿名 Rush 脚本。三档行为参数分别保留，资源来源与哈希位于 `cs2career/data/botprofile_behavior/resources.json`。

此前 BotAI 1.8.12 和 BotAimImprover 2.1.5 的 build 2000924 导航／转头审核属于历史记录。当前 Aim 为 2.1.6-career1，通过 schema 查找 `m_pBot`，不固定 pawn 偏移；CareerMatch 为 2000933 维护独立的函数体与布局校验。BotState 1.10.2 使用此前的 120° 水平／180° 垂直视野设置。玩家无线电指令由游戏确认接受后，CareerMatch 立即撤销该队旧战术和保位／朝向控制，交给原生无线电响应；纯报点与庆祝消息不取消战术。每回合重置交接状态。

## 开发与打包

普通运行包携带兼容安装模块及版本清单；组件在玩家明确安装时从官方发行页获取，不依赖开发机器上的增强目录。下载缓存、安装备份、私人身份和存档不进入源码包。

更新组件时，同时核对官方下载地址、发布校验值、ZIP 内文件位置、依赖、当前游戏数据和本项目实际使用的接口，再修改清单版本。不要使用浮动的 `latest` 地址，也不要只替换原生 DLL 而遗漏同版本的托管 API。Controller 升级还必须核对 CareerMatch 的模块哈希和 ABI；不要仅添加新哈希绕过审核。

运行 `test_career3d_runtime_compat.py`、`test_career3d_install.py`、`test_career3d_setup_http.py` 和 `test_cs2_deployment.py` 检查缓存、安装、错误反馈与旧组件覆盖回归。

## 2026-10-12 安装修复

此前发布包要求 Metamod 1474，但界面安装入口仍强制离线。完整官方 1.4.5 包携带的 Metamod 不满足此要求，新用户没有缓存时会在部署 CareerMatch 前失败。本次修复安装入口，补充空缓存安装回归，并验证打包 EXE 的实际安装过程。

该轮首次安装修复起初使用 Bot Improver 1.4.5 验证；同日后续更新已把安装基线提升到官方 1.4.6，并保留完整配套组件。2000933 更新继续保留这些修复：明确点击外部安装才下载缺失组件，完整官方包和已校验缓存优先复用；下载失败在写入游戏之前返回可读错误。

完整实战、战术到点行为和赛后回传仍待验证。RayTrace 独立插件的旧 SourceHook 接口限制未解决，不能把 CareerMatch 的离线检查视为该插件也已兼容。
