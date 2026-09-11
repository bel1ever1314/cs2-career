生涯事件包制作示例（不是赛事日历包）

把整个 incident-pack 文件夹复制到 EXE 旁的 extensions，再在扩展工坊重新扫描。
示例只为自建生涯启用一次低概率的虚构教练离队与赛后复盘事件。
示例会改变游戏资金和心态，建议用测试存档体验，别直接改自己的主存档。

events 类型是“赛事日历”；incidents 才是带选择和后果的事件。
stories 仍然是纯叙事，不执行 effects。不要混用这三种类型。

一、改写已经存在的假赛/教练事件
在 overrides 内指定 when，只能改 title、text 和 labels（选项名称）。
fix_offer：假赛邀约，accept/refuse 分别使用原本的接受/拒绝逻辑。
major_coach：Major 前教练缺席。原本触发概率和心态变化保持不变。
还可以改 fix_probe、fix_ban、teammate_birthday、loan_default、loan_flee_ban。
这里只改弹出的事件窗口；相关邮件和结局档案文字仍属于原系统。
不能通过改选项的名称来修改真正行为，不要把 accept 改写成“拒绝”。

二、新增带后果的事件
incidents 数组的每项包含 id、when、title、text、choices。
when 可以是 day（日期推进结算）、before_match（自己的正式比赛开打前）、
after_series（自己的系列赛结算后）、event_started（参加的赛事开赛）、coach_absent（原教练缺席事件发生后）。
day 指推进到的日期，不保证中间跳过的每个自然日都触发。
conditions 可用 mode（create/join）、origin、event_type 和 flags。
flags 是本包自己的布尔标记，支持“教练离队后才触发下一条事件”。

每个 choice 包含 id、label、effects。允许的效果：
mentality：amount 为 -20 到 20，全队心态变化。
pocket_money：amount 为个人余额变化，单选项累计绝对值不超过 100000。
club_money：amount 为俱乐部余额变化，同上。
flag：key 为标记名称，value 为 true/false。只对自己的扩展包生效。
至少保留一个不用花钱的选项，防止余额不足卡死。资金不够会提示，不扣部分款。

probability 是概率，cooldown_days 是触发间隔天数，max_per_career 是一份生涯里最多几次。
默认一次、至少间隔 30 天。已触发次数、选择标记和待处理事件会保存在生涯里。
移除扩展后，已经弹出的选择仍可以完成；不会按新文件偷偷替换选项。
扩展 id 和事件 id 发布后不要随便改，否则可能被认作新的事件。

目前的教练事件用标记、心态、费用表达影响，不是完整的教练合同/教练数据库系统。
新增假赛、处罚等复杂机制不能任意写代码执行；需要以后在核心明确增加新的效果类型。
严重负面情节使用虚构人物并注明虚构，不代表现实中的选手、战队发生过这些事情。
