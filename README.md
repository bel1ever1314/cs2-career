# CS2 Career

一个非官方的 CS2 选手生涯模拟器：培养角色、管理战队、经历赛季，也可以进入 CS2 本地人机比赛亲自上场。

## 普通玩家从这里开始

1. 打开 [Releases 下载页](https://github.com/bel1ever1314/cs2-career/releases)。
2. 下载名称含 **windows-x64.zip** 的玩家包，完整解压。
3. 双击 **CS2Career.exe**。使用 EXE 不需要安装 Python。
4. 遇到问题先看 [开始游玩-FAQ.txt](开始游玩-FAQ.txt)，不需要阅读开发文档。

当前候选版本：**1.5.0-steady.1**，Windows 64 位桌面程序。
这是公开测试版，不代表所有真实 CS2 回传场景已经完成验收。
最新改动和限制见 [发布说明](RELEASE_NOTES.md)。

桌面界面需要微软 [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)。
请从官方来源安装；不要为了运行本程序关闭安全软件。

## 能玩什么

- 2024／2025／2026 年代，接管职业选手或以路人、青训、天才创建角色。
- 个人成长、位置选择、状态起伏、转会、适度经营与剧情。
- 点击战队、选手、赛事和比赛查看资料与已保存战报。
- 饰品收藏、市场与开箱；全部是生涯虚拟物品，不进入 Steam 库存，不能兑现。
- 工资和奖金自动结算，经营页查看资金；邮件不需要点击领钱。
- 剧情、赛事、饰品等扩展模板。部分历史资料是估算，不等于逐项考据过的真实阵容。

## 两种比赛方式

**只玩生涯模拟：** 不必安装 CS2 插件，在生涯内推进日程和模拟比赛即可。

**亲自进入 CS2：** 需要 Steam、CS2 和 [CS2 Bot Improver 的 Windows 发行包](https://github.com/ed0ard/CS2-Bot-Improver/releases)。
先退出 CS2，在生涯的“游戏设置”保存路径并安装人机增强，再由生涯启动对应比赛。
完整步骤、换肤和回传排错都在 [FAQ](开始游玩-FAQ.txt)。

每场按当前阵容准备九名 Bot，不同步原增强项目的选手数据库。
Low／Medium／High 使用增强基础预设，个人档位再参考生涯能力、位置和状态。
换肤可选；换肤插件随玩家 EXE 提供，人机增强完整运行包需另外获取。

仅用于 **-insecure 本地人机对局**，不要用于官方匹配或联网服务器。
安装会修改游戏插件与本场人机资料。CS2 更新可能影响兼容性，不能保证任意新版上游插件都已适配。

## 存档、更新与反馈

存档在 EXE 旁的 `save/`，自装扩展在 `extensions/`。更新前关闭程序并备份这两个文件夹。
不同解压目录的 EXE 使用各自的存档；不要误删旧目录。
1.5 存档保持兼容读取；更旧格式以程序提示为准，不建议手改格式强行载入。

实战要等正式终场及完整十人战绩回传，不能看到 13 分就立即退出。
失败时保留提示和现场，不要马上开启下一场。接管成功提示已隐藏，后台记录仍保留。
当前补丁仍需持续实测；不凭比分补零、不猜测重分配旧战绩。

请到 [Issues](https://github.com/bel1ever1314/cs2-career/issues) 提供版本、操作步骤和截图。
公开上传前检查昵称、本机路径等隐私，不要提交整个存档、Steam 账号配置或登录信息。

## 给开发者与扩展作者

源码运行需要 Python 3.12+：

```powershell
py -3 -m pip install -r requirements-desktop.txt
py -3 main.py
```

- [开发者接手指南](DEVELOPER_GUIDE.zh-CN.md)：模块、数据流和历史实现说明；文末修正优先于早期记录。
- [扩展架构与示例](EXTENSION_ARCHITECTURE.zh-CN.md)：剧情、赛事和饰品图片扩展。
- [构建与发布指南](PUBLISHING.md)：Python、.NET 插件、EXE 和白名单压缩包。
- [CS2 联调记录](CS2_INTEGRATION.zh-CN.md)：问题经过与验证边界。
- 测试统一运行 `py -3 tools/run_tests.py`，它先隔离存档和扩展目录。
- 纯 C# 回归位于 `tools/identity-tests`；不要把这些回放当作真实 CS2 验收。

## 授权与致谢

生涯维护代码采用 **AGPL-3.0-only**，见 [LICENSE](LICENSE)。
历史 MIT 权利及第三方许可不被撤回，见 [第三方声明](THIRD_PARTY_NOTICES.md)。
复用了 ed0ard 的 CS2 Bot Improver 模板／BotBuy，并使用 Inventory Simulator 等组件。
历史换肤源码恢复情况及重编译限制见 [恢复源码说明](RECOVERED_SOURCE.md)。

本项目与 Valve、相关赛事、战队及选手无官方关系。相关名字、商标和美术归各自权利人。
发布时同时提供对应源码与玩家包；不包含个人存档、私人扩展、日志或图片缓存。
