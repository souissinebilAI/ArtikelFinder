# Manual test in Chrome

Automated tests cover the lookup, normalization, view, and background logic
(`npm test`, fake `chrome` API) and the bubble under hostile CSS
(`extension/dev/harness.html`). This list covers what only a real browser shows.

## Setup

```bash
python pipeline/export_runtime.py --out extension/data
```

Chrome → `chrome://extensions` → Developer mode on → **Load unpacked** → select the
`extension/` folder. After code changes, press the reload icon on the extension card.

## Checklist

1. **Install warning:** the card and the details page list no "Read and change all your
   data on all websites". Permissions shown: context menus only.
2. **Right-click:** on a German page (e.g. de.wikipedia.org), select *Tischen* →
   right-click → "Artikel für „Tischen“" → bubble: der Tisch, dative plural, 2 sources agree.
3. **Shortcut:** select *Leitern*, press **Alt+Shift+A** → two entries (die Leiter / der Leiter).
   If nothing happens, check `chrome://extensions/shortcuts` (another extension may own it).
4. **Declension:** click "Declension" → table; clicking inside does not close the bubble.
5. **Close:** Esc, click elsewhere, and scrolling each close it.
6. **Unknown:** select a name like *Berlin* → "not in the dictionary".
7. **Protected pages:** on `chrome://extensions` or the Web Store nothing appears. Chrome
   forbids extensions there; the service worker console logs a warning.
8. **Iframe:** on a page with an embedded frame from another site, a lookup inside the frame
   shows the bubble at the top of the page instead of next to the word.
9. **Worker restart:** wait >30 s (the worker stops), look up again: still works.
10. **Errors:** `chrome://extensions` → ArtikelFinder → "service worker" → Console: no errors.
