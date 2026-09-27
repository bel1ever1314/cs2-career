/* Run with node tests/test_i18n.js. No browser or npm download required. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const staticDir = path.join(__dirname, '..', 'cs2career', 'web', 'static');
const catalogue = require(path.join(staticDir, 'desk', 'locales', 'en.js'));
const source = fs.readFileSync(path.join(staticDir, 'desk', 'i18n.js'), 'utf8');
const storage = new Map();
function text(value) { return {nodeType:3,nodeValue:value,parentElement:null,isConnected:true}; }
function element(tag, attributes={}, nodes=[]) {
  const e = {nodeType:1,tagName:tag.toUpperCase(),attrs:{...attributes},childNodes:nodes,parentElement:null,isConnected:true,value:'',
    matches(selector) {
      return selector.split(',').some(part=>{
        const s=part.trim();
        if(s.startsWith('.'))return (this.attrs.class||'').split(' ').includes(s.slice(1));
        const m=/^\[([^=\]]+)(?:="([^"]*)")?\]$/.exec(s);
        if(m)return Object.hasOwn(this.attrs,m[1])&&(m[2]===undefined||this.attrs[m[1]]===m[2]);
        return s.toUpperCase()===this.tagName;
      });
    },
    closest(selector) { return this.matches(selector)?this:this.parentElement?.closest(selector); },
    getAttribute(name) {return this.attrs[name]??null;}, hasAttribute(name){return Object.hasOwn(this.attrs,name);},
    setAttribute(name,value){this.attrs[name]=String(value);},
    get textContent(){return this.childNodes.map(n=>n.nodeValue??n.textContent).join('');},
    set textContent(value){const node=text(value);node.parentElement=this;this.childNodes=[node];},
  };
  for(const node of nodes)node.parentElement=e;
  return e;
}
const doc={readyState:'loading',body:null,documentElement:{},addEventListener(){},dispatchEvent(){},
  createTreeWalker(host){const all=[];const append=node=>{for(const ch of node.childNodes||[]){all.push(ch);append(ch);}};append(host);let i=0;return {nextNode:()=>all[i++]||null};}};
const context={document:doc,localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)},CareerLocales:{en:catalogue},CustomEvent:class {constructor(type,data){this.type=type;this.detail=data.detail;}},module:{exports:{}}};
context.window=context;
vm.runInNewContext(source,context);
const api=context.CareerI18n;
api.setLocale('en');
assert.equal(api.t('  开始生涯  '),'  Start career  ');
assert.equal(api.t('第2阶段 · 第4轮'),'Stage 2 · Round 4');
assert.equal(api.t('购买 $2,500'),'Buy $2,500');
assert.equal(api.t('申请 Vitality 的主狙位置？成功率 65%。本次只投一次，失败冷却30天，成功冷却90天；成功后仍可选择留下。'),'Apply to Vitality as AWPer? Success chance: 65%. One roll only. Failure: 30-day cooldown; success: 90 days. You can still choose to stay after passing.');
assert.equal(api.t('出售 AK-47 | Redline，获得 $250？'),'Sell AK-47 | Redline for $250?');
assert.equal(api.t('我的队员叫开始生涯'),'我的队员叫开始生涯','Unknown text must never undergo substring replacement');
assert.equal(api.t('<script>开始生涯</script>'),'<script>开始生涯</script>');
assert.equal(api.field({title:'回家',title_en:'Home'},'title'),'Home');
assert.equal(api.field({title:'没有英文的扩展'},'title'),'没有英文的扩展');
assert.equal(api.localized({zh:'中文',en:'English'}),'English');
const action=text('保存'), name=text('指挥'), custom=text('训练');
const body=element('div',{},[element('button',{},[action]),element('button',{'data-open-player':'p-1'},[name]),element('span',{},[custom])]);
api.setIdentityNames(['训练']);api.apply(body);
assert.equal(action.nodeValue,'Save');assert.equal(name.nodeValue,'指挥');assert.equal(custom.nodeValue,'训练');
api.apply(body);assert.equal(action.nodeValue,'Save','Second pass must be idempotent');
api.setLocale('zh-CN');api.apply(body);assert.equal(action.nodeValue,'保存','Roundtrip restores source text without rebuilding nodes');
api.setLocale('en');action.nodeValue='关闭';api.apply(body);assert.equal(action.nodeValue,'Close','Renderer update must replace cached source');
api.setLocale('zh-CN');api.apply(body);assert.equal(action.nodeValue,'关闭');
const input=element('input',{placeholder:'搜索选手'});input.value='训练';
api.setLocale('en');api.apply(input);assert.equal(input.attrs.placeholder,'Search players');assert.equal(input.value,'训练');
api.setLocale('zh-CN');api.apply(input);assert.equal(input.attrs.placeholder,'搜索选手');
const pack=element('p',{'data-no-i18n':''},[text('开始生涯')]);api.setLocale('en');api.apply(pack);assert.equal(pack.textContent,'开始生涯');
const explicit=element('p');api.bindLocalized(explicit,{zh:'原文',en:'Translated'});assert.equal(explicit.textContent,'Translated');
api.setLocale('zh-CN');api.apply(explicit);assert.equal(explicit.textContent,'原文');
api.register('en',{phrases:{'包内按钮':'Pack button'}});assert.equal(api.t('包内按钮','en'),'Pack button');
assert.equal(storage.get('cs2career.language'),'zh-CN');
const persisted={window:null,localStorage:{getItem:()=> 'en'},module:{exports:{}},CareerLocales:{en:catalogue}};persisted.window=persisted;
vm.runInNewContext(source,persisted);assert.equal(persisted.CareerI18n.getLocale(),'en');
assert.ok(Object.keys(catalogue.phrases).length>400);
console.log('PASS: English core flow, exact matching, live language switching, user content protection, persistence, extension fallbacks.');
