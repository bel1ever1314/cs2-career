# 颁奖 / Top20 音效换成管弦版

2026-10-08

## 原因

年度颁奖典礼、快速模式的 Top20 弹窗和夺冠弹窗，原来用的是代码现算的正弦波音效（`ceremony_audio.gd` 和 `career_feedback.make_sound`）。号角是正弦泛音叠出来的，听着像玩具，太滑稽。

## 现在

用和其它配乐同一个 SoundFont（GeneralUser GS）渲染的原创管弦短曲，全部在降 B 大调。鼓点停在属音 F 上，揭晓时解决到降 B。

| 文件 | 用在哪 | 内容 |
|---|---|---|
| `ceremony_roll.ogg` | 颁奖倒数名次、Top20 前三名揭晓前 | 定音鼓 + 吊镲滚奏渐强，低音弦乐铺底，约 2.6 s |
| `ceremony_roll_long.ogg` | 颁奖领奖台揭晓前 | 同上，后半段圆号加入，约 3.8 s |
| `ceremony_hit.ogg` | 名字揭晓 | 大鼓、镲、定音鼓 + 降 B 全奏短和弦 |
| `ceremony_fanfare.ogg` | 领奖台、你自己的名次、Top20 第一名 | 76 BPM 宽广的铜管乐句，落在降 B 和弦，约 8.7 s |
| `ceremony_applause.ogg` | 揭晓后、领奖后 | 合成的会场掌声加几声欢呼 |
| `ceremony_tick.ogg` | Top20 第 20 到第 4 名逐个出现 | 轻拨弦 + 竖琴单音 |
| `ceremony_honours.ogg` | 荣誉 / Top20 弹窗打开 | 竖琴上行刮奏进温暖的弦乐和弦 |
| `ceremony_champion.ogg` | 夺冠弹窗、举杯 | 定音鼓引入铜管 + 弦乐降 B 和弦，加钟声 |

- 鼓点在揭晓时停止，改成 0.12 s 淡出，不会有爆音。
- 文件缺失时自动退回原来的合成音。地图胜负提示音保持原样，不在这次范围内。
- 生成方式：`tools/audio/ceremony.py`，`build_game_audio.py` 会一起渲染并复制到 `assets/audio`。

## 改动

- `scripts/ceremony_audio.gd`：新增 `sound(kind)`，优先读渲染好的文件；`stop` 改成淡出。
- `scripts/awards_venue.gd`：预加载改为 `Audio.sound`。
- `scripts/career_feedback.gd`：honours / champion 两个提示音优先用渲染文件。
- `tests/ceremony_audio_test`（33 项）：
  - 每个音效都用文件，长度够用，而且只播一遍；
  - 回退机制正常；
  - 淡出生效，淡出后可以重新播放；
  - 弹窗用对了文件，地图胜负仍是合成音。

## 验证

- `ceremony_audio_test`、`audio_integration_test`、`career_feedback_test` 和颁奖场馆场景测试都通过。
- Godot 全量回归和改前一致，只多了新测试。
- 云端是静音驱动，响度需要在本机试听后再微调。在代码里改 `awards_venue.gd` 和 `career_feedback.gd` 里的 dB 值就行。
