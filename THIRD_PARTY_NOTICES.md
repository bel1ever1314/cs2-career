# 授权、来源与发布边界

本次新增与维护的 CS2 Career 生涯代码，按作者确认采用 **AGPL-3.0-only**，全文见 LICENSE。
原有 MIT 授权部分的版权与许可保留在 licenses/CS2Career-MIT-legacy.txt；
这不撤回已经授出的 MIT 权利，也不宣称拥有第三方商标或素材版权。

## 随包内容

- orjson：ijl / orjson 贡献者，原生 JSON 编码用于降低保存与响应延迟。
  保留上游包所附 MIT、Apache-2.0 和 MPL-2.0 许可文本于 licenses/runtime/orjson/。

- CS2 Bot Improver：ed0ard 与原项目贡献者，AGPL-3.0。
  https://github.com/ed0ard/CS2-Bot-Improver
  复用的内容是 botprofile_presets 匿名模板、Medium 参数规律及 vendor/BotBuy 源码。
  原1700人名单及增强整包不随发行包分发。模板来源哈希在 presets.json；
  BotBuy 生涯修改是延迟实体校验及阻止生涯 SSG08 随机改成冲锋枪。
  AGPL 全文见根目录 LICENSE。
- InventorySimulator：Ian Lucas，MIT；本地 DLL 是历史项目已有的修改版本。
  https://github.com/ianlucas/cs2-css-inventory-simulator
  授权见 licenses/InventorySimulator-MIT.txt；恢复源码和验证限制见 RECOVERED_SOURCE.md。
- InvsimCareer：CS2 Career 历史桥接插件；保留原有 MIT 许可记录，源码恢复见上述文档。
- 饰品匹配元数据参考 ByMykel/CSGO-API，MIT，licenses/CSGO-API-MIT.txt。
  元数据引用与固定提交在 skin_art.json。饰品美术归 Valve 等权利人，不属于本项目 AGPL；
  Release 不携带玩家下载的图片缓存，只按固定清单按需显示。
- 队伍图标是项目内生成的字母色块，不声称是官方授权队标；队名、选手名和商标属于各自权利人。
- Python、pywebview、pythonnet、clr-loader、cffi、pycparser、bottle、typing_extensions
  使用各自许可，全文见 licenses/runtime/。proxy_tools 的包元数据声明 MIT
  （Jonathan Tushman，https://github.com/jtushman/proxy_tools）。
- PyInstaller 使用 GPL 加 bootloader 分发例外；全文见 licenses/runtime/PyInstaller.txt。
  WebView2 组件来自 pywebview，按 Microsoft 的组件许可使用：
  https://www.nuget.org/packages/Microsoft.Web.WebView2/ ；
  Edge WebView2 Runtime 需由玩家安装，不复制玩家电脑的 Runtime 目录。

## 外部运行依赖

进入 CS2 需要 Steam、CS2、Metamod、CounterStrikeSharp、BotHider 和 Bot Improver 的运行组件，
玩家从官方/上游发行页获取。这些完整产品不包含在本发行包中，不受本项目 LICENSE 重新授权。
CounterStrikeSharp 的许可说明：
https://github.com/roflmuffin/CounterStrikeSharp/blob/main/LICENSE

请把对应源码 ZIP 和 Windows ZIP 放在同一个 GitHub Release，并保留全部许可及修改说明。
仅发布本地候选构建，不表示上游背书、Valve 授权或本轮实战验收已经完成。
