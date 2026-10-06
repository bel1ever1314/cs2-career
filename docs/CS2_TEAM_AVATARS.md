# CS2 中的选手队标头像

天梯和自定义对局按每名 Bot 的俱乐部显示队标，不把临时 Team A／Team B 当俱乐部。九个 Bot 加真人、十个 Bot 加观察者都走相同的头像通道。真人仍用自己的 Steam 头像。

匹配或创建房间时，阵容快照记录 club／club_id。开赛请求的 avatar_teams 按 player_id 冻结这些归属；切换开局阵营、分配位置、改难度和重建 BotProfile 都不丢失绑定。旧房间只有 club 名称也能使用现成队标。没有对应队标或自由选手继续显示原来的默认 Bot 头像。新房间根据生涯当前名单读取转会后的队伍，已开的房间不追着后来的转会改。

常规生涯比赛继续按比赛队伍设置头像，优先使用现有真实队标；玩家自定义的合格小 PNG 仍优先。头像改变不改能力、武器模板、比赛名单、合成 SteamID 或真人 Steam 资料。

## 离线素材与现有接口

48 个队标复用已收集的本地 SVG，预处理为 64×64、最多 16 KiB 的 PNG，存于 cs2career/data/team_logo_avatars。运行时只读取文件并检查哈希；缺失或损坏就沿用默认头像，不下载图片、不在 Tick 内转图。

素材生成器：tools/build_team_logo_avatars.gd。使用 Godot 的 SVG 渲染器，在空目录（不启动游戏 autoload）执行：

`Godot --headless --path <空目录> --script <源码>/tools/build_team_logo_avatars.gd -- --manifest=<team-media.json> --output=<源码>/cs2career/data/team_logo_avatars`

manifest.json 逐项记录来源、SVG 哈希和生成 PNG 哈希。素材仍按原队标声明处理，见 THIRD_PARTY_NOTICES.md 与 licenses/counter-strike-icons-LICENSE.txt，不把队标宣称为原创。

游戏内头像统一使用灰黑半透明底（`#202428`，约 70% 不透明度），不再按队标亮度铺米白色底。队标原色不变；很深的队标只在轮廓边缘补一像素浅色描边。生成 PNG 保留 RGBA，传给 BotHider 的也是原始 PNG，不做白底合成。实际透明混合由 CS2 客户端的头像控件决定，不修改游戏 HUD。

prepare_game 在生成比赛清单前把头像写入 CareerMatch/avatars；按图片内容复用文件，同一队标不重复写十份。CareerMatch 校验路径和哈希后直接调用 BotHider 的共享 API（SetBotAvatar），不经控制台指令。随后读取 HasBotAvatar，区分待接收、已提交、已应用和未确认；每个身份最多提交五次，确认后不再重复读取图片。身份和战绩绑定不变，真人永远不提交头像。

游戏插件目录的 avatar_status.json 记录本场 nonce、请求是否启用、API 是否就绪，以及每个 Bot 的应用状态。该文件只在状态变化时更新，不包含真人 Steam 信息；断开、换图和插件重新加载会清除旧状态。文件存在或请求发送成功本身不代表客户端已显示。

[BotHider 官方接口说明](https://github.com/XBribo/CS2-Bot-Hider#custom-bot-avatars)区分 TAB 记分板和顶部小头像的缓存；TAB 使用本地覆盖，顶部可能不会立即刷新。这里不改客户端文件或真人 Steam 头像来绕过缓存。

## 验证

`python -B tools/run_tests.py test_team_logo_avatars.py`

`dotnet run --project tools/avatar-tests/AvatarTests.csproj` 验证共享接口绑定、确认状态、有限重试、换队标、断开和身份变化；需 .NET 10 运行环境。

覆盖 48 个素材格式／尺寸／来源、混合俱乐部、无队标回退、用户头像优先、九人／十人唯一身份、旧房间、修改难度后保留头像、转会快照和打包资源。新头像与旧默认头像生成的 BotProfile VPK 内容及合成身份一致，仅头像及包含头像哈希的清单变化。
