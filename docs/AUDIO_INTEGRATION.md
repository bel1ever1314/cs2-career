# 声音接入记录 · 2026-10-06

范围：3D 客户端（`work/career3d_redesign`）。全部为本项目原创：乐器用 GeneralUser GS 2.0.3 音源渲染，观众声为程序合成，没有录音或采样人声。生成脚本在 `tools/audio`，素材说明在 `work/career3d_redesign/assets/audio/README.md`。

## 已接入

**场馆氛围**
- Major 内场：预渲染的两条无缝观众循环（低声交谈 / 活跃欢呼）替换原来每次进场现算的噪声；两条按“观众情绪”交叉混合，按场次人数缩放（10000 / 1000 / 100）。100 人场只有小规模声势。
- LAN：小房间交谈、键盘鼠标声，偶尔几个人欢呼。
- 颁奖厅：大厅低语和礼貌掌声；典礼进行时自动压低，结束后恢复。
- 打开手机/电脑、暂停时环境声降低而不是中断。

**Major 入场音乐与观众音轨对齐**
- 千人／万人场馆的正式比赛与直接参观统一使用“决赛开场”（128 BPM）。十台电脑线下场地和百人小场馆不播放入场音乐，只保留按规模混合的环境声。音乐和观众是两条独立音轨，用 `AudioStreamSynchronized` 同步播放，观众音量单独随人数变化。
- `assets/audio/major_final_cue.json` 记录节拍与关键点：保持小节、爆点前静音拍、爆点、两次重击、终结重击。
- 队伍集合完毕即开始播放。走得慢时，铺垫最后一小节在原小节线上重复，直到离通道口约 8 米；走出通道口时若还没到爆点，直接跳到静音拍，爆点落在出通道那一刻；等太久会把音乐压低。
- 灯光读 cue：铺垫期轻微脉动，静音拍舞台和观众席灯压暗，爆点闪亮，之后按 128 BPM 加强重音。场内小鸡的欢呼动作跟随观众情绪。
- 入座后音乐淡出，观众环境声保留。直接参观时，进入通道开始铺垫，走进内场接爆点，同一次参观来回走动不重播。旧 112 BPM 管弦与 136 BPM 合成入场曲不再调用；观众音轨缺失时仍放新曲，音乐缺失时仅保留环境声，不回退旧曲。

**日常音乐**（autoload `Music`，`scripts/music_director.gd`）
- 俱乐部：白天 06:00–19:00 播“俱乐部的午后”，晚上播“训练后的夜晚”。家里晚上播“窗边夜灯”，家里白天暂不放。场馆里淡出，让给场馆声音。
- 2 秒交叉淡化；手机/电脑降到 50%，报纸/颁奖展示降到 25%；每播两遍休息 20–40 秒。
- 手机设置新增“音乐”音量；总音量、静音、音乐音量保存到 `user://audio_settings.cfg`（以前不保存）。

## 文件
- 新增：`scripts/audio_assets.gd`、`scripts/music_director.gd`、`scripts/venue_ambience.gd`、`tests/audio_integration_test.gd/.tscn`，`assets/audio` 下 10 个 ogg、cue json、GeneralUser GS 授权。
- 修改：`arena_atmosphere.gd`、`major_walk.gd`、`small_venue_base.gd`、`lan_venue.gd`、`awards_venue.gd`、`career_phone.gd`、`project.godot`（autoload）、`ui_messages.json`（`device.music`）、`locale_en.json`（音乐 → Music）、`tests/venue_match_flow_test.gd`（入场改为 128 BPM 同步音轨，并检查爆点）。
- 打包脚本只复制 `assets/audio` 顶层的 ogg/json/txt/md，新文件都放在顶层；授权文件会被复制到包内 licenses。

## 验证
- `audio_integration_test`：54 项（选曲与昼夜、场馆不放日常音乐、循环加载、压低、设置持久化、交叉淡化、cue 节拍、同步音轨与人数缩放、保持小节重复、直接参观和正式入场、来回不重播、小场馆无入场曲，以及新曲缺失不回退旧曲）。
- 比赛入场流程测试新增：入场为两条同步音轨；走出通道后爆点确实发生。
- Godot 全量回归与改前源码基线逐项对比（结果见本次交付说明）。
- 重新渲染全部素材与此前试听版本逐样本一致：`python -B tools/audio/build_game_audio.py --sf2 <GeneralUser-GS-2.0.3.sf2>`。

## 未做 / 后续
- 家里白天的曲子待定；05 赛前热身、06 颁奖之夜、07 场馆暖场未接入。
- 比赛结束后的欢呼、冠军典礼仍用原有音效。
- 真实声卡下的响度需要在本机听一遍再微调（云端测试为静音驱动）。
