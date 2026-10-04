CS2 Career 1.7.0-preview.3-hotfix.7

这次可以走进自己的宿舍和俱乐部了。打开手机看消息、日历和个人资料，
坐到电脑前安排比赛、设计战术，也可以进入场馆亲自打下一场。

本次更新接入 Bot Improver 1.4.5，保留生涯自己的战术、朝向和买枪功能。
游戏内换肤默认关闭；需要时在设置里手动开启。
文本框使用清晰的箭头指针，手机和电脑都可正常输入与选中文字。
门口前往比赛会显示准备进度；有待处理事项时，可以直接打开手机查看。
执行战术的队友可以响应玩家无线电，守点等待中也能立即改为跟随、撤退等任务。
中途退出后返回场馆、保存和同步战术等已有功能继续保留。

这次补上了设置里的插件一键开关。从生涯程序进入 CS2 对局时开启插件，
退出 CS2 后自动恢复普通游戏环境。中途退出也可以继续原来的比赛，
或改用逐图模拟、RTS 完成这一场。
瞄准方式、道具频率、人机难度、身份显示和局内对话可以分别设置。
购买逻辑也一起调整了：经济足够优先 AK／M4，经济不足仍能用便宜主枪；
保下来的枪和捡来的枪不会强制换掉，狙击职责与队友配枪继续保留。
更新了游戏内换肤的函数签名，整理旧签名备份和缓存的加载顺序。
本地对局补回丢刀设置，手动开启换肤后沿用已装备的饰品。
补齐没有主武器时的购买：预算足够会补买 AK／M4，狙位买不起 AWP 时
也会选择合适的主枪。保留正常手枪局、经济局和已有武器，不重复扣款买枪。

开始游玩
完整解压，双击“开始游戏.cmd”或 Launch-CS2Career.cmd。
Python 和 Godot 已随包提供，无需另外安装。
显卡兼容问题可使用“兼容显卡启动.cmd”。

比赛可以自己打，也可以逐图模拟，或进入 RTS 观赛台指挥队员。
天梯有队长选人和地图 BP；自定义对局可以自由安排双方阵容。
想轻松推进赛季，可以在手机或电脑里开启快速模式。

进入 CS2
先安装 Steam 和 CS2。朋友整合包已附带人机增强，
在设置里核对游戏路径，关闭 CS2 后点击“安装随包人机增强”即可。
普通运行包则选择自己下载并解压好的 CS2 Bot Improver Windows 发行包。
https://github.com/ed0ard/CS2-Bot-Improver/releases
在手机或电脑的设置里填写 Steam、游戏与增强包路径，关闭 CS2 后点击
“安装填写目录的人机增强”，程序会检查本地文件，连同本项目自带的组件一起安装并备份，
再从生涯比赛、天梯或自定义大厅启动比赛。
人机插件用于 -insecure 本地对局。设置里可一键恢复普通 CS2 环境，
退出本项目启动的 CS2 对局后也会自动恢复；普通匹配不加载这些插件。

存档
当前进度自动保存，也可以在界面里手动存档和读档。
保存位置：game/runtime/career/save；手动存档在其中的 manual 目录。
更新或移动目录时，保留自己的存档文件夹。

饰品工具
3D 检视与贴纸编辑留有可选接口；想使用时自行配置外部工具和适配器。

遇到问题，可以在 GitHub 留言，附操作步骤、截图和 game/runtime/game.log。
源码、素材出处和许可随包保留。感谢所有提供开源组件和反馈的朋友。

原发行包不变，首次安装也无需联网。想查看上游新版，
可以主动点击“检查人机增强更新”；它不会自动下载或替换现有组件。

English
Extract the whole folder and run Launch-CS2Career.cmd. Python and Godot are included.
For actual CS2 matches, install Steam and CS2. The friends all-in-one includes
Bot Improver: check your paths in Settings and select Install bundled Bot Improver.
For an ordinary package, choose your extracted official Windows release instead.
Installation is offline and includes this project's bundled components.
In-game skins start disabled; enable them in Settings only if you want to use them.
Bots without a primary now buy an affordable rifle, including snipers who cannot
afford an AWP. Pistol rounds, eco budgets and carried weapons are preserved.
Check for updates only contacts GitHub when clicked and never replaces plugins.
Your original release folder stays unchanged;
later matches use the compatible runtime copy.
Settings include a one-click plugin switch. Career enables plugins for local CS2
matches and restores the normal game environment after CS2 exits.
Aim, utility, difficulty, bot identity and match chat have separate options.
Bots prioritize AK/M4 purchases when affordable, retain economical choices,
and preserve carried weapons, pickups, sniper assignments and team drops.
Updated cosmetic function signatures and prevented stale signature caches and
backups from overriding the compatible copy. Knife dropping is enabled in
Career's local matches; skins still follow your explicit setting and loadout.
Saves are in game/runtime/career/save.
The optional 3D skin viewer/sticker editor uses a separately configured adapter.
