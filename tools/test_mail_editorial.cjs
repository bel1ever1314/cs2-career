const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const els={};const win={scrollY:0,scrollTo:(_x,y)=>win.scrollY=y};
const ctx=vm.createContext({window:win,document:{body:{classList:{toggle(){}}},querySelectorAll:()=>[],addEventListener(){}},
 VIEW:'home',S:{career:{}},FOCUS:null,MATCH:null,PLAY_TIMER:null,stopSeriesPoll(){},
 $:id=>els[id]||=( {innerHTML:'',disabled:false}),esc:s=>String(s??'').replaceAll('<','&lt;').replaceAll('>','&gt;'),
 requestAnimationFrame:f=>f(),queueMicrotask:f=>f(),clearInterval(){},
 fetch:async()=>({json:async()=>({ok:true,state:{career:{stories:[]}},stories:[]})}),
 sessionStorage:{getItem:()=> 'token'},adopt(s){ctx.S=s;},toast(){},takeStories(){}});
vm.runInContext(fs.readFileSync('cs2career/web/static/desk/navigation.js','utf8'),ctx);
ctx.CareerUI=win.CareerUI;ctx.render=()=>ctx.CareerUI.render();
const app=fs.readFileSync('cs2career/web/static/app.js','utf8');
vm.runInContext(app.slice(app.indexOf('async function post('),app.indexOf('async function refreshDetail(')),ctx);
vm.runInContext(fs.readFileSync('cs2career/web/static/desk/editorial.js','utf8'),ctx);
(async()=>{
 ctx.CareerUI.go('mail');win.scrollY=850;
 await ctx.post('/api/mail/accept',{id:'invite'});
 assert.equal(win.scrollY,850,'accept must retain mailbox scroll');
 win.scrollY=1240;await ctx.post('/api/mail/decline',{id:'invite2'});
 assert.equal(win.scrollY,1240,'second action must use latest scroll, not entry position');
 ctx.CareerUI.go('home');assert.equal(win.scrollY,0,'new page still starts at top');
 const html=ctx.CareerUI.renderFeature({title:'<img onerror=alert(1)>',subtitle:'Year',sections:[{heading:'Evidence',text:'<script>bad</script>\n\nSecond paragraph'}]});
 assert.doesNotMatch(html,/<script>|<img/);assert.match(html,/&lt;script&gt;/);assert.match(html,/Second paragraph/);
 assert.match(app,/最佳\$\{ROLE\[p.role\]/);
 console.log('Mailbox scroll across repeated actions and safe annual feature rendering passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
