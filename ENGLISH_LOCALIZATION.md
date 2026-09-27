# UI localisation for 1.6

The language control is in the sidebar and Settings. It stores `cs2career.language` in local storage and supports `zh-CN` and `en`. Changing language does not change a save, player ID, API command value, name or simulation rule.

`cs2career/web/static/desk/locales/en.js` contains complete UI phrases and anchored patterns for labels with numbers. `desk/i18n.js` translates only registered phrases. Unrecognised content stays in the original language; it is never machine-guessed or replaced word by word. The mutation observer updates changed text nodes in place, preserving controls, focus and page position.

## Adding UI text

Add an exact Chinese phrase and its English equivalent to `phrases` in `desk/locales/en.js`. Use an anchored regular expression in `patterns` for a full dynamic sentence. Keep names and IDs as captured values. Do not add broad substring replacements or patterns matching arbitrary story text.

Native browser dialogs need an explicit call because they are not page DOM:

```js
const message = '确定退役？这段生涯会结束，只能重开。';
if (confirm(CareerI18n.t(message))) { /* business command */ }
```

## Bilingual narratives

Built-in romance, NA student, team dispute, personal press, injury, birthday, transfer,
retirement and milestone prose now has authored English. The original Chinese and
gameplay fields are unchanged. `career/localization.py` adds optional presentation
fields without changing saved choices, rewards, probabilities or identity.

- `data/story_locale_en.json`: English chapters, endings, injuries and milestone stories.
- `data/story_locale_sources.json`: the exact Chinese source snapshot for that overlay.
  Update the matching source field AND its translation together when revising prose.
  A changed Chinese field will not silently inherit the old overlay translation.
- `data/story_messages_en.json`: exact sentences/templates for incident and reaction text.
- `data/career_news.json`: bilingual Major reports and family letters.

Existing saved prose matching a known original can be presented in English; unknown
or player-edited text remains intact. Nothing rewrites an old save on translation.
Pack authors should provide their own `title_en`, `text_en` and choice `label_en`.

Story records may contain `title`, `text`, `choice` and the optional `title_en`, `text_en`, `choice_en`. Rendering uses `CareerI18n.field(record, 'text')`, then the usual HTML escaping. Missing translations fall back to the original content.

Pure text objects are also supported:

```js
const line = {zh: '回到训练室。', en: 'Back to the practice room.'};
CareerI18n.localized(line);
CareerI18n.bindLocalized(domElement, line); // textContent only; no HTML execution
```

`career:language` is a document event with `detail.locale`. Components rendering explicit bilingual fields may repaint on this event. Generic labels already update without repainting.

## Protecting user content

Use `data-no-i18n` or `translate="no"` for names or arbitrary user-authored content. Profile name links, crest labels, inputs, textareas and code are protected. `setIdentityNames(names)` additionally protects plain name nodes after a state load. The name registry only affects displayed text; it never changes saved data.

Extension packages remain data-only. A translated narrative belongs in the package’s JSON fields when the package schema supports them. Do not ship JavaScript inside a content pack. New UI language catalogues are source files loaded by `index.html`, not executable extension content.

## Verification and limitations

Run `node tests/test_i18n.js`, `node tests/test_news_locale.js`, and `node tests/test_story_locale.js`. Python `test_narrative_english.py` also checks built-in coverage, placeholder parity, dynamic reactions, family letters, source-edit fallback, unchanged rewards and Major award delivery in both modes. Tests cover language persistence, switching back to Chinese, changed dynamic labels, name and form-value protection, extension fallbacks, bilingual news and confirmation templates.

Core menus, setup, squad controls, match viewing, transfers, finance, collections, the season itinerary and common dialogs have English phrases. Common personal/world activity lines use anchored templates. Newly published Major reports and structured monthly reports carry explicit bilingual fields; monthly sections and their items must both include English text.

Existing saved history is not rewritten. Some historical prose, server diagnostics and third-party packs still use their original language. A dictionary count is not a claim that every possible generated sentence is translated. A Chinese-only extension overriding a built-in chapter or report must not inherit unrelated English prose from the built-in version.
