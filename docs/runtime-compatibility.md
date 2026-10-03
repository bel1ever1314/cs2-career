# 人机增强兼容安装

在 3D 版的手机或电脑设置中选择已经解压的 Bot Improver 发行包，关闭 CS2 后点击“安装填写目录的人机增强”。安装器使用原包的增强配置，从各组件的官方发行页下载我们选定的配套版本，再加入生涯程序自己的朝向、战术导航和买枪修复。每个 ZIP 都先核对 SHA-256，原发行包不会被改写。这是我们维护的兼容组合，不是上游重新发布的完整人机增强包。

兼容副本与下载缓存在独立生涯目录的 `runtime-cache` 中。安装前的游戏文件备份放在 `install-backups`。全部安装成功后，设置中的增强路径切换到兼容副本；开赛和恢复饰品组件也使用这个副本，避免重新复制旧 DLL。再次安装会核验并复用缓存。

打开设置、保存路径和刷新状态不会触发下载，也不会修改游戏。首次安装下载所需组件，不下载或执行上游的桌面启动器。CSS 的配套 .NET 运行环境随官方组件安装。

## 当前组件

版本清单在 `cs2career/data/cs2_runtime_compat.json`，当前为 `windows-20261003.1`。

- [Metamod 2.0.0.1472](https://github.com/alliedmodders/metamod-source/releases/tag/2.0.0.1472)
- [CounterStrikeSharp 1.0.376](https://github.com/roflmuffin/CounterStrikeSharp/releases/tag/v1.0.376)，含 .NET 运行环境
- [BotController 0.7.0](https://github.com/XBribo/CS2-Bot-Controller/releases/tag/v0.7.0)，原生插件与 CSS API 使用同套版本，保留已经适配的 ABI22 战术保位接口
- [BotHider 0.5.1](https://github.com/XBribo/CS2-Bot-Hider/releases/tag/v0.5.1)，含身份接口和复活逻辑修正
- [BotVision 0.3.0](https://github.com/XBribo/CS2-Bot-Vision/releases/tag/v0.3.0)
- [BotRandomizer 1.3.2](https://github.com/ed0ard/CS2-Bot-Randomizer/releases/tag/v1.3.2)，使用官方更新的签名与饰品数据

这套 Windows 数据对 CS2 build 2000922 做了离线检查，59 条相关函数签名均唯一匹配。Controller 固定为已经审核的 0.7.0 原生 DLL（SHA-256 `8645168d4bb6a55ce8a8ac4246bce394496e4eecf4f56c2f2a7932a98eb75d61`），与 CareerMatch 的保位接口一致；不能只追随组件的最新版本。

安装时 CareerMatch 与 BotBuy 使用本项目 `vendor` 中的构建，最后覆盖到游戏目录，因此我们的修复不由上游发行包代替。此前本地编译的 Randomizer 来自上游尚未打包的源码；现在官方 1.3.2 已包含同样的两条 Windows 函数签名，复核后使用该发行版。

## 开发与打包

普通运行包携带兼容安装模块及版本清单；组件在玩家明确安装时从官方发行页获取，不依赖开发机器上的增强目录。下载缓存、安装备份、私人身份和存档不进入源码包。

更新组件时，同时核对官方下载地址、发布校验值、ZIP 内文件位置、依赖、当前游戏数据和本项目实际使用的接口，再修改清单版本。不要使用浮动的 `latest` 地址，也不要只替换原生 DLL 而遗漏同版本的托管 API。Controller 升级还必须核对 CareerMatch 的模块哈希和 ABI；不要仅添加新哈希绕过审核。

运行 `test_career3d_runtime_compat.py`、`test_career3d_install.py`、`test_career3d_setup_http.py` 和 `test_cs2_deployment.py` 检查缓存、安装、错误反馈与旧组件覆盖回归。
