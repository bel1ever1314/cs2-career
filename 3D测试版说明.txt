CS2 Career 1.7.0-preview.2

这次可以走进自己的宿舍和俱乐部了。打开手机看消息、日历和个人资料，
坐到电脑前安排比赛、设计战术，也可以进入场馆亲自打下一场。

本次更新：中途退出后可以返回原场馆；战术保存后会同步当前已准备对局，
战术室可以查看快照状态并手动同步；更新了 CS2 导航与朝向的兼容检查。

开始游玩
完整解压，双击“开始游戏.cmd”或 Launch-CS2Career.cmd。
Python 和 Godot 已随包提供，无需另外安装。
显卡兼容问题可使用“兼容显卡启动.cmd”。

比赛可以自己打，也可以逐图模拟，或进入 RTS 观赛台指挥队员。
天梯有队长选人和地图 BP；自定义对局可以自由安排双方阵容。
想轻松推进赛季，可以在手机或电脑里开启快速模式。

进入 CS2
先安装 Steam、CS2 与 CS2 Bot Improver Windows 运行包。
https://github.com/ed0ard/CS2-Bot-Improver/releases
在手机或电脑的设置里填写 Steam、游戏与增强包路径，关闭 CS2 后点击
“安装填写目录的人机增强”，程序会下载并校验配套组件，连同本项目的兼容修复一起安装并备份，
再从生涯比赛、天梯或自定义大厅启动比赛。
人机插件用于 -insecure 本地对局，普通匹配请使用不加载这些插件的环境。

存档
当前进度自动保存，也可以在界面里手动存档和读档。
保存位置：game/runtime/career/save；手动存档在其中的 manual 目录。
更新或移动目录时，保留自己的存档文件夹。

饰品工具
3D 检视与贴纸编辑留有可选接口；想使用时自行配置外部工具和适配器。

遇到问题，可以在 GitHub 留言，附操作步骤、截图和 game/runtime/game.log。
源码、素材出处和许可随包保留。感谢所有提供开源组件和反馈的朋友。

原发行包不变，后续开赛使用更新后的兼容副本。首次安装需联网，
之后可以复用已下载的组件；保存路径或打开设置不会自动下载。

English
Extract the whole folder and run Launch-CS2Career.cmd. Python and Godot are included.
For actual CS2 matches, install Steam, CS2 and the Bot Improver Windows runtime,
then set their paths in Settings and choose Install from the configured folder.
The installer verifies our selected upstream components and includes this project's
compatibility patches. Your original release folder stays unchanged;
later matches use the compatible runtime copy.
Saves are in game/runtime/career/save.
The optional 3D skin viewer/sticker editor uses a separately configured adapter.
