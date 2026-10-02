CS2 Career 1.7.0-preview.1

这次可以走进自己的宿舍和俱乐部了。打开手机看消息、日历和个人资料，
坐到电脑前安排比赛、设计战术，也可以进入场馆亲自打下一场。

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
在手机或电脑的设置里保存游戏与增强包路径，关闭 CS2 后安装配套组件，
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

English
Extract the whole folder and run Launch-CS2Career.cmd. Python and Godot are included.
For actual CS2 matches, install Steam, CS2 and the Bot Improver Windows runtime,
then set their paths in Settings. Saves are in game/runtime/career/save.
The optional 3D skin viewer/sticker editor uses a separately configured adapter.
