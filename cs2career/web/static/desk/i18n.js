/* Presentation-only localisation. Saves, player names and command values stay
 * in their original form. Exact phrases and explicit templates are translated;
 * there is no word replacement inside arbitrary stories or extension text.
 * Add dictionaries with CareerI18n.register('en', {phrases, patterns}).
 * Story packs may supply {zh: '...', en: '...'} and use localized(value).
 */
((root) => {
  'use strict';
  const key = 'cs2career.language';
  let locale = 'zh-CN';
  try { locale = root.localStorage?.getItem(key) === 'en' ? 'en' : 'zh-CN'; } catch (_) {}
  const dictionaries = new Map(), originals = new WeakMap(), originalAttrs = new WeakMap();
  const localizedNodes = new WeakMap();
  let identityNames = new Set(), observer = null, scheduled = false;
  const pending = new Set();
  const attributes = ['title', 'placeholder', 'aria-label'];
  const protectedSelector = '[data-no-i18n], [translate="no"], script, style, code, pre, textarea, input, [contenteditable="true"], [data-open-player], [data-open-team], .js-player, .js-team, .tm, .crest, .player-name';
  const dictionariesFor = lang => dictionaries.get(lang) || {phrases: {}, patterns: []};
  function register(lang, data) {
    if (!data || typeof data !== 'object') return;
    const old = dictionariesFor(lang);
    dictionaries.set(lang, {
      phrases: {...old.phrases, ...(data.phrases || {})},
      patterns: [...old.patterns, ...(data.patterns || [])],
    });
    if (root.document?.body) apply(root.document.body);
  }
  function t(value, language = locale) {
    if (value == null) return '';
    const text = String(value);
    if (language !== 'en') return text;
    const trimmed = text.trim(), data = dictionariesFor(language);
    if (!trimmed) return text;
    let result = Object.prototype.hasOwnProperty.call(data.phrases, trimmed) ? data.phrases[trimmed] : undefined;
    if (result === undefined) {
      for (const [pattern, replacement] of data.patterns) {
        pattern.lastIndex = 0;
        if (pattern.test(trimmed)) { pattern.lastIndex = 0; result = trimmed.replace(pattern, replacement); break; }
      }
    }
    if (result === undefined) return text;
    return text.slice(0, text.indexOf(trimmed)) + result + text.slice(text.indexOf(trimmed) + trimmed.length);
  }
  function localized(value, language = locale) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return String(value[language] ?? value[language === 'zh-CN' ? 'zh' : 'en'] ?? value.zh ?? value['zh-CN'] ?? value.en ?? '');
    }
    return t(value, language);
  }
  function field(record, name, language = locale) {
    return localized(language === 'en' && record?.[name + '_en'] != null ? record[name + '_en'] : record?.[name], language);
  }
  function protectedNode(element) {
    return !!element?.closest?.(protectedSelector);
  }
  function textNode(node) {
    if (protectedNode(node.parentElement)) return;
    const current = node.nodeValue || '', saved = originals.get(node);
    // A renderer may change a reused text node; do not restore stale content.
    const source = saved && current === saved.translated ? saved.source : current;
    const translated = identityNames.has(source.trim()) ? source : t(source);
    originals.set(node, {source, translated});
    if (current !== translated) node.nodeValue = translated;
  }
  function elementAttrs(element) {
    if (!element?.getAttribute) return;
    const value = localizedNodes.get(element);
    if (value !== undefined && element.textContent !== localized(value)) element.textContent = localized(value);
    if (element.closest?.('[data-no-i18n], [translate="no"]')) return;
    const saved = originalAttrs.get(element) || {};
    for (const attribute of attributes) {
      if (!element.hasAttribute(attribute)) { delete saved[attribute]; continue; }
      const current = element.getAttribute(attribute), record = saved[attribute];
      const source = record && record.translated === current ? record.source : current;
      const translated = t(source);
      saved[attribute] = {source, translated};
      if (current !== translated) element.setAttribute(attribute, translated);
    }
    originalAttrs.set(element, saved);
    if (element.matches?.('[data-career-language]')) element.value = locale;
  }
  function apply(host) {
    if (!host) return;
    if (host.nodeType === 3) { textNode(host); return; }
    if (host.nodeType !== 1 && host.nodeType !== 11 && host.nodeType !== 9) return;
    const walk = root.document?.createTreeWalker?.(host, 1 | 4);
    if (!walk) return;
    if (host.nodeType === 1) elementAttrs(host);
    for (let node = walk.nextNode(); node; node = walk.nextNode()) {
      if (node.nodeType === 3) textNode(node); else elementAttrs(node);
    }
  }
  function setLocale(value) {
    locale = value === 'en' ? 'en' : 'zh-CN';
    try { root.localStorage?.setItem(key, locale); } catch (_) {}
    if (root.document) {
      root.document.documentElement.lang = locale;
      apply(root.document.body);
      root.document.dispatchEvent(new root.CustomEvent('career:language', {detail: {locale}}));
    }
    return locale;
  }
  function setIdentityNames(values) {
    identityNames = new Set((values || []).map(String));
  }
  function bindLocalized(element, value) {
    // Explicit multilingual content, supplied as data and never evaluated as HTML.
    localizedNodes.set(element, value);
    element.setAttribute('data-no-i18n', '');
    element.textContent = localized(value);
  }
  function start() {
    const doc = root.document;
    if (!doc?.body || observer) return;
    doc.documentElement.lang = locale;
    apply(doc.body);
    doc.addEventListener('change', event => {
      if (event.target.matches?.('[data-career-language]')) setLocale(event.target.value);
    });
    observer = new root.MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'childList') for (const node of record.addedNodes) pending.add(node);
        else pending.add(record.target);
      }
      if (scheduled) return;
      scheduled = true;
      root.queueMicrotask(() => {
        scheduled = false;
        const nodes = [...pending]; pending.clear();
        // Only touched subtrees, not a whole-page poll. Translation edits are
        // idempotent, preserve nodes/focus/listeners and settle on the next pass.
        for (const node of nodes) if (node.isConnected) apply(node);
      });
    });
    observer.observe(doc.body, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: attributes});
  }
  root.CareerI18n = {t, localized, field, register, setLocale, setIdentityNames, bindLocalized, apply, getLocale: () => locale};
  for (const [lang, data] of Object.entries(root.CareerLocales || {})) register(lang, data);
  if (root.document) {
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start);
    else start();
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = root.CareerI18n;
})(typeof window !== 'undefined' ? window : globalThis);
