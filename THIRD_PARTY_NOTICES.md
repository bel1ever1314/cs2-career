# 授权、来源与发布边界

本次新增与维护的 CS2 Career 生涯代码，按作者确认采用 **AGPL-3.0-only**，全文见 LICENSE。
原有 MIT 授权部分的版权与许可保留在 licenses/CS2Career-MIT-legacy.txt；
这不撤回已经授出的 MIT 权利，也不宣称拥有第三方商标或素材版权。

## 随包内容

- orjson：ijl / orjson 贡献者，原生 JSON 编码用于降低保存与响应延迟。
  保留上游包所附 MIT、Apache-2.0 和 MPL-2.0 许可文本于 licenses/runtime/orjson/。

- CS2 Bot Improver：ed0ard 与原项目贡献者，AGPL-3.0。
  https://github.com/ed0ard/CS2-Bot-Improver
  复用的内容是 botprofile_presets 匿名模板、Medium 参数规律、1.4.5 匿名 Rush 行为脚本及 vendor/BotBuy 源码。
  原1700人名单及增强整包不随发行包分发。模板来源哈希在 presets.json；
  匿名行为脚本的来源、规范化方式与哈希在 botprofile_behavior/resources.json；
  BotBuy 生涯修改是延迟实体校验及阻止生涯 SSG08 随机改成冲锋枪。
  AGPL 全文见根目录 LICENSE。
- InventorySimulator：Ian Lucas，MIT；本地 DLL 是历史项目已有的修改版本。
  https://github.com/ianlucas/cs2-css-inventory-simulator
  授权见 licenses/InventorySimulator-MIT.txt；恢复源码和验证限制见 RECOVERED_SOURCE.md。
- InvsimCareer：CS2 Career 历史桥接插件；保留原有 MIT 许可记录，源码恢复见上述文档。
- 饰品匹配元数据参考 ByMykel/CSGO-API，MIT，licenses/CSGO-API-MIT.txt。
  元数据引用与固定提交在 skin_art.json。饰品美术归 Valve 等权利人，不属于本项目 AGPL；
  3D Release 按固定清单附带展示用图片，不携带玩家的库存或整个下载缓存目录。
- 贴纸目录与模型限值参考 ByMykel/CSGO-API 和 Ian Lucas 的 cs2-lib（MIT）。
  固定提交、模型范围及出处保存在 data/stickers.json，许可见 licenses/cs2-lib-MIT.txt。
  检视 ID 与 HD／legacy 模型范围固定于 data/inspect_catalog.json。
  不打包上游网站、渲染器源码或 Valve 模型素材。
  3D 在线检视的嵌入协议参考 ianlucas/cs2-inventory-simulator（MIT），
  固定提交 15223361b2f7ebc6d8d03fca2ef435e85911f3d9；
  许可见 licenses/cs2-inventory-simulator-web-MIT.txt。
  https://3d.cstrike.app 是独立在线服务，不属于本项目的 AGPL 源码；
  默认关闭，需要玩家在设置中启用并主动打开才发送单件匿名外观，
  受其网络、支持范围与用量限制；无需下载上游项目才能使用服务。
  “外部插件配装”模式允许玩家自行获取、配置原换肤插件和自定义库存，
  生涯保留本地收藏，但不再同步配装或管理该外部插件与签名。
  已有生涯修改版仍保留原作者的 MIT 授权，不宣称为独立重写。
  四位选手配装的公开记录来自 HLTV，来源与核对日期逐项保存在
  data/public_pro_loadouts.json；只收录武器／涂装事实，不复制报道全文。
  账号关联目录的出处独立记录（Skinory 标示 CC BY-SA 4.0），不视为选手认证。
  精确磨损、图案和贴纸未知的模板采用明确标记的模拟默认值。
- 3D 版真实队标来自 Juknum/counter-strike-icons，固定提交
  85ec43bd170d0622db8eadf160e666c161976375；逐项来源和哈希保存在
  media/teams/team-media.json，原始声明见 licenses/counter-strike-icons-LICENSE.txt。
  CS2 Bot 头像的 64×64 PNG 由同一批 SVG 转换，来源及转换后哈希保存在
  cs2career/data/team_logo_avatars/manifest.json，不另行联网获取头像。
  上游 MIT 只覆盖其代码和工具，不覆盖游戏图标；图标及名字的权利仍归
  Valve 及相应权利人。没有队标的条目使用项目生成的字母图案。
- 地图战术画板使用 Valve 的游戏雷达素材，经 MurkyYT/cs2-map-icons 转为 PNG。
  地图版权属于 Valve，不适用本项目的 AGPL；来源、坐标参数、核对日期和内容哈希
  保存在 data/tactical_map_dust2.json 与 data/tactical_maps.json。新增地图素材固定于
  提交 55828fc236d97b99cda0e8cb7561b8dd543bee3d，包含 Nuke／Train／Vertigo 的下层雷达。
  雷达图片不是可行走区域或碰撞数据。
  战术编辑与执行代码由本项目实现，没有复制未标明许可的战术画板源码。
- Python、pywebview、pythonnet、clr-loader、cffi、pycparser、bottle、typing_extensions
  使用各自许可，全文见 licenses/runtime/。proxy_tools 的包元数据声明 MIT
  （Jonathan Tushman，https://github.com/jtushman/proxy_tools）。
- PyInstaller 使用 GPL 加 bootloader 分发例外；全文见 licenses/runtime/PyInstaller.txt。
  WebView2 组件来自 pywebview，按 Microsoft 的组件许可使用：
  https://www.nuget.org/packages/Microsoft.Web.WebView2/ ；
  Edge WebView2 Runtime 需由玩家安装，不复制玩家电脑的 Runtime 目录。
- Godot：Godot Engine 贡献者，MIT。3D Windows 包附带官方 4.7.2 运行器，
  引擎 LICENSE 与 COPYRIGHT 位于 legal/Godot，不包含 Steam 或 CS2 本体。
- ChillRoundF 字体：保留字体目录中的 OFL.txt，不将字体许可改为项目 AGPL。
- 模型的原创生成源码位于 work/career3d_redesign/source。原创配乐采用
  GeneralUser GS 音色渲染，其许可与出处在音频目录和 licenses 中保留。

## 外部运行依赖

3D 版的地图展示背景从 CS2 游戏资源提取，不使用雷达图代替。
资源准备脚本可调用 ValveResourceFormat / Source 2 Viewer 的 Source2Viewer-CLI：
https://github.com/ValveResourceFormat/ValveResourceFormat 。本地验证使用 20.0，
工具不随生涯源码或 Release 捆绑；若另行分发工具需保留其上游许可。
地图展示图和饰品图片属于 Valve 等权利人，不适用本项目 AGPL；
来源、资源路径、工具版本和图片哈希保存在随包媒体清单。
3D 界面的年度颁奖舞台为原创布局，不包含 HLTV 标志或上游典礼录像。

沙二自然动作试验使用 XBribo/CS2-Bot-Controller 的 ABI 20 移动输入接口。
接口定义参考 https://github.com/XBribo/CS2-Bot-Controller （AGPL-3.0）；不打包或替换其原生 DLL。
本地 Demo 派生动作包放在测试版 natural_routes 目录，不随公开源码或标准 Release 分发。

进入 CS2 需要 Steam、CS2、Metamod、CounterStrikeSharp、BotHider 和 Bot Improver 的运行组件，
玩家从官方/上游发行页获取。这些完整产品不包含在本发行包中，不受本项目 LICENSE 重新授权。
CounterStrikeSharp 的许可说明：
https://github.com/roflmuffin/CounterStrikeSharp/blob/main/LICENSE

请把对应源码 ZIP 和 Windows ZIP 放在同一个 GitHub Release，并保留全部许可及修改说明。
1.7.0-preview.1 的公开包为普通 3D 运行包；外部增强组件的固定版本和获取链接
见 docs/external-runtime-pins.json。公开包不包含整合候选中的 HL2SDK 镜像附件。
