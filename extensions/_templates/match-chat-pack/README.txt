比赛聊天包制作示例

把整个 match-chat-pack 文件夹复制到正在运行的 EXE 旁的 extensions 目录。
不要只复制 example.json；_templates 里的内容默认不加载。
进入扩展工坊重新扫描，校验通过后，完全退出 CS2，再准备下一场比赛。

改文字：打开 match_chat/example.json，修改 text 数组中的台词。
改人物：speaker 可写 teammate（本队 Bot）、opponent（对手 Bot）、coach（教练）。
指定选手：添加 speaker_id，填写 match_request.json 中的 player_id，不填则选一位符合阵营的 Bot。
对手必须使用 channel: all；team 仅本队真人可见，all 所有人可见。
颜色 color 可用 default、green、blue、gold。不接受自定义控制字符。
dialogue.2：普通聊天每回合最多教练一句、选手一句（队友/对手共用选手额度）。
priority 越大越先检查；同级按扩展加载、文件名及数组顺序选择。
不再共用全场八条和两回合冷却；每条规则自己的冷却与次数上限仍然有效。
优先级最高的是 scenes 场内剧情：整段按 sequence 顺序播放，触发回合不混普通聊天。
多人剧情示例与字段说明见相邻 match-scene-pack 文件夹。

条件 conditions 内，各项同时满足才触发。
数字条件写成 {"min": 最小值, "max": 最大值}，可以只写一端。
可用数字：round（已完成回合数）、score_for、score_against、lead（本队分差）、
kills、deaths、assists、damage、round_kills（真人角色本回合击杀）、win_streak、loss_streak。
可用精确文字条件：result（win/loss）、map（如 de_mirage）、player_id、speaker_id、team_id。
player_id 指真人扮演的原角色；接管 Bot 的数据不放到此人身上。

文本可写 {player}、{speaker}、{team}、{opponent}，也可使用上述条件字段作为占位符。
probability 为 0 到 1；cooldown_rounds 为该规则冷却；max_per_match 为该规则每场次数。
max_per_match 最大200，默认2；cooldown_rounds 默认4。probability:1 不会绕过额度或冷却。
内置规则继续存在，使用更高 priority 可以优先播放你的内容。
要完全用自己的文字，到游戏设置将比赛对话选择为“仅扩展包”。
规则存进下一场的请求快照，运行中改文件不影响当前比赛。

这不是语音合成，也不是可移动的独立字幕窗口，使用的是 CS2 原生聊天框。
台词带有“生涯”标识，不伪装成真人实际发送的消息。
人物名场面请核实原文，虚构台词请注明游戏演绎。
