/* Explicit activity templates translate data without renaming people. */
'use strict';
const assert=require('node:assert/strict');
const api=require('../cs2career/web/static/desk/i18n.js');
api.register('en',require('../cs2career/web/static/desk/locales/en.js'));
api.setLocale('en');
const pairs=[
  ['2026 赛季开始。','Season 2026 begins.'],
  ['2025 赛季结束。年度第一：donk。2026 赛季开始。','Season 2025 ended. Player of the year: donk. Season 2026 begins.'],
  ['创建 天禄， 你是 演示。',null], // Do not guess unknown near-matches.
  ['创建 天禄，你是 演示。','Created 天禄. You are 演示.'],
  ['加入 Vitality，接管 ZywOo（96）。','Joined Vitality, playing as ZywOo (rating 96).'],
  ['IEM Cologne 开赛，32 支队伍。','IEM Cologne begins with 32 teams.'],
  ['IEM Cologne 冠军：Vitality，MVP ZywOo','IEM Cologne champion: Vitality · MVP ZywOo'],
  ['IEM Cologne 冠军：天禄','IEM Cologne champion: 天禄'],
  ['推进到 2026-06-20，进行了 12 场比赛。','Advanced to 2026-06-20 · 12 matches played.'],
  ['推进到 2026-06-20，进行了 12 场比赛。 轮到你上场：天禄 vs Vitality，BO3。','Advanced to 2026-06-20 · 12 matches played · Your match: 天禄 vs Vitality, BO3.'],
  ['2026-06-20 轮到你上场：天禄 vs Vitality，BO3。','2026-06-20 · Your match: 天禄 vs Vitality, BO3.'],
  ['接受邀请：IEM Cologne','Accepted invitation: IEM Cologne'],
  ['IEM Cologne 结束，属性点 +7（系列赛 6，冠军 +1）。今年剩余 9 点。','IEM Cologne finished · +7 attribute points (6 series, title bonus +1) · 9 points available.'],
  ['IEM Cologne 结束，属性点 +2（系列赛 2）。今年剩余 3 点。','IEM Cologne finished · +2 attribute points (2 series) · 3 points available.'],
  ['2026-06 发薪：个人 $2,000，俱乐部剩余 $40,000。','2026-06 payday: personal funds +$2,000 · Club balance $40,000.'],
  ['2026 青训营：天才 Newcomer（82，潜力 97）进入转会市场。','2026 intake: prodigy Newcomer (rating 82, potential 97) entered the market.'],
  ['投入 1 点到火力。火力 78 → 79，个人能力 81.4。剩余 3 点。','1 point assigned to Firepower: 78 → 79 · Ability 81.4 · 3 points left.'],
  ['用个人口袋 1,200 买下 AK-47 | 红线。','Purchased AK-47 | 红线 for $1,200 from personal funds.'],
  ['试训 D20：17 +2 = 19，成功。','Trial D20: 17 +2 = 19 · Passed.'],
  ['试训 D20：1 -2 = -1，未通过。','Trial D20: 1 -2 = -1 · Not passed.'],
  ['与已接受的 IEM Cologne 赛程重叠，保留原安排。','Overlaps with the accepted IEM Cologne event; keeping the existing schedule.'],
  ['本赛季采用快速模式。','Quick mode selected for this season.'],
  ['扩展作者说：冠军不等于一切。',null],
];
for(const [source,expected] of pairs)assert.equal(api.t(source),expected??source,source);
for(const label of ['全年赛程','新赛季 · 选择本季节奏','本队参赛','赛历变更','已归档','继续模拟本季'])assert.notEqual(api.t(label),label,label);
console.log(`PASS: ${pairs.length} activity templates, names, unknown text and season labels.`);
