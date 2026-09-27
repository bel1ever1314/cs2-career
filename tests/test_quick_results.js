'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const ctx={esc:s=>String(s??'').replace(/[<>&"]/g,x=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[x]))};
ctx.window=ctx;vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../cs2career/web/static/desk/quick-results.js'),'utf8'),ctx);
const ui=ctx.CareerQuickResults;
const match={id:'m',result_id:'2026:event:m',date:'2026-01-02',team_a:'A',team_b:'B',player_team:'B',player_id:'b0',
  played:true,winner:'B',winners:['A','B','B'],series:'1 : 2',report:true,data_complete:true,
  totals:['A','B'].flatMap(team=>Array.from({length:5},(_,i)=>({team,player_id:team.toLowerCase()+i,name:'<same>',k:20,d:15,a:8,damage:1800,adr:75,kast:.75,rating:1.25,data_complete:true})))};
assert.equal(ui.mapOutcome(match,0),'');
assert.equal(ui.mapOutcome(match,1),'loss');assert.equal(ui.mapOutcome(match,2),'win');
assert.equal(ui.mapOutcome({...match,player_team:undefined},1),'','No guessed player team');
const data={series_results:[{id:'old',date:'2026-01-01',won:false},{id:match.result_id,date:match.date,won:true}],summary:{wins:1,losses:1}};
const dots=ui.recordHTML(data,match);
assert.equal((dots.match(/class="result-dot /g)||[]).length,2,'Receipt and refreshed board represent one result, not two');
assert.ok(dots.indexOf('result-dot loss')<dots.indexOf('result-dot win'));
assert.equal(ui.results({series_results:[]},{...match,report:false}).length,0,'Do not reveal the result during map playback');
const html=ui.scorecard(match);
assert.equal((html.match(/<tr class=/g)||[]).length,10);
assert.equal((html.match(/class="quick-you"/g)||[]).length,1,'Same names do not cause multiple highlights');
assert.ok(html.includes('quick-player-spotlight')&&html.includes('20 / 15 / 8'));
assert.ok(!html.includes('<same>')&&html.includes('&lt;same&gt;'));
assert.ok(!ui.scorecard({...match,player_id:'missing'}).includes('quick-player-spotlight'));
assert.ok(ui.scorecard({...match,data_complete:false,totals:[]}).includes('部分历史数据缺失'));
console.log('PASS: map outcome from player side, saved series dots deduplicated, ten-player scorecard and exact ID highlight.');
