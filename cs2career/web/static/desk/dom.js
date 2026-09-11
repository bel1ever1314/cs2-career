/* Patch presentation DOM instead of replacing a whole page on every command.
 * Painters still bind their onclick/onchange handlers after painting. Keys are
 * presentation identities, never game state. No global DOM setters are patched. */
window.CareerDOM = (() => {
  const key = n => n.nodeType === 1 ? n.getAttribute('data-ui-key') || n.id ||
    (n.hasAttribute('data-skin-detail') ? 'skin:'+n.dataset.kind+':'+n.dataset.skinDetail : '') : '';
  const compatible = (a,b) => a && a.nodeType === b.nodeType && a.nodeName === b.nodeName && key(a) === key(b);
  function patch(a,b) {
    if(a.nodeType !== 1) {if(a.nodeValue !== b.nodeValue)a.nodeValue=b.nodeValue;return;}
    const focused = a === document.activeElement;
    const opened = a.tagName === 'DETAILS' ? a.open : null;
    // Old closures must not survive when a reused button changes meaning.
    // All page painters bind property handlers after paint; delegated document
    // handlers are unaffected. Keeping the node must not keep an old command.
    for(const event of ['onclick','onchange','oninput','onkeydown','onkeyup','ontoggle','onpointerdown','onpointermove','onpointerup','onpointercancel'])
      if(a[event])a[event]=null;
    // Attribute comparison matters: rewriting an unchanged image src can reload
    // it; rewriting all children would also discard focus and graph scroll.
    for(const attr of [...a.attributes])if(!b.hasAttribute(attr.name))a.removeAttribute(attr.name);
    for(const attr of [...b.attributes])if(a.getAttribute(attr.name)!==attr.value)a.setAttribute(attr.name,attr.value);
    children(a,b);
    if(opened !== null)a.open=opened;
    if(a.tagName === 'INPUT') {
      if(!focused && a.value !== b.value)a.value=b.value;
      a.checked=b.checked;
    } else if(['SELECT','TEXTAREA'].includes(a.tagName) && !focused && a.value !== b.value)a.value=b.value;
  }
  function children(parent,next) {
    const old=[...parent.childNodes], keyed=new Map(old.filter(key).map(n=>[key(n),n])), used=new Set();
    let cursor=parent.firstChild;
    for(const fresh of [...next.childNodes]) {
      const k=key(fresh);
      let node=k?keyed.get(k):cursor;
      if(used.has(node)||!compatible(node,fresh))node=null;
      if(!node){node=fresh;parent.insertBefore(node,cursor);}
      else {if(node!==cursor)parent.insertBefore(node,cursor);patch(node,fresh);}
      used.add(node);cursor=node.nextSibling;
    }
    for(const node of old)if(!used.has(node))node.remove();
  }
  function paint(host,html) {
    const next=document.createElement('div');next.innerHTML=html;
    // Unlike a global innerHTML interception, this only accepts page markup;
    // script elements are never inserted into the live document.
    next.querySelectorAll('script').forEach(n=>n.remove());
    children(host,next);
  }
  return {paint};
})();
