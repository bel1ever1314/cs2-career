/* Exercise the actual modal function without starting the app/network. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'..','cs2career','web','static','app.js'),'utf8');
const code=source.slice(source.indexOf('function paintStory()'),source.indexOf('function playerFace(row)'));
let box=null,locale='zh-CN',writes=0,revealsStopped=0;const listeners={};
function modal(){let html='';return {dataset:{},set innerHTML(value){html=value;writes++;},get innerHTML(){return html;},
  querySelector:()=>({}),querySelectorAll:()=>[],remove:()=>{box=null;}};}
const row={id:'exit-final-1',title:'归途',title_en:'The journey home',text:'收好键盘。',text_en:'Pack up your keyboard.',
  choices:[{id:'continue',label:'继续',label_en:'Continue'}]};
const context={STORY_Q:[row],STORY_BUSY:false,revealNext:null,$:()=>box,
  document:{createElement:modal,body:{appendChild:value=>{box=value;}},addEventListener:(key,fn)=>{listeners[key]=fn;}},
  stopReveal:()=>{revealsStopped++;},ackStory(){},esc:String,
  CareerI18n:{getLocale:()=>locale,field:(record,key)=>locale==='en'?(record[key+'_en']??record[key]):record[key]}};
context.window=context;vm.runInNewContext(code,context);
context.paintStory();assert.match(box.innerHTML,/收好键盘/);assert.equal(writes,1);
context.paintStory();assert.equal(writes,1,'Regular polling cannot restart the same modal');
locale='en';listeners['career:language']();assert.equal(writes,2);assert.match(box.innerHTML,/Pack up your keyboard/);
assert.match(box.innerHTML,/The journey home/);assert.match(box.innerHTML,/>Continue</);
context.paintStory();assert.equal(writes,2);assert.equal(revealsStopped,2);
locale='zh-CN';listeners['career:language']();assert.equal(writes,3);assert.match(box.innerHTML,/归途/);
assert.equal(context.STORY_Q[0],row,'Switching language must not acknowledge or replace the story');
context.STORY_Q=[];listeners['career:language']();assert.equal(writes,3);
console.log('PASS: live bilingual story modal, stable same-language polling, no implicit acknowledgment.');
