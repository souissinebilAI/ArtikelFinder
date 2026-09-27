// Service worker: context menu / shortcut -> lookup -> bubble in the page.
// Runs with activeTab only: Chrome grants access to the current tab at the moment
// the user clicks the menu entry or presses the shortcut, and at no other time.
import { Lexicon } from "./lexicon.js";
import { resolveSelection } from "./normalize.js";
import { buildView } from "./view.js";

const MENU_ID = "artikel-lookup";
const COMMAND = "lookup-selection";

chrome.runtime.onInstalled.addListener(() => {
  // removeAll first: onInstalled also fires on update, and ids must be unique.
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: MENU_ID, title: "Artikel für „%s“", contexts: ["selection"] });
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== MENU_ID || !tab?.id) return;
  lookupAndShow(tab.id, info.frameId ?? 0, info.selectionText ?? "");
});

chrome.commands.onCommand.addListener(async (command, tab) => {
  if (command !== COMMAND || !tab?.id) return;
  let text = "";
  try {
    // The shortcut carries no selection, so read it from the page (top frame only:
    // activeTab does not reach cross-origin iframes).
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => String(getSelection() ?? ""),
    });
    text = result;
  } catch (err) {
    console.warn("ArtikelFinder cannot read this page (Chrome blocks extensions here).", err);
    return;
  }
  lookupAndShow(tab.id, 0, text);
});

/** @type {Promise<Lexicon> | null} opened lazily; the worker is restarted often */
let lexiconPromise = null;

function openLexicon() {
  lexiconPromise ??= Lexicon.open(async (rel) => {
    const response = await fetch(chrome.runtime.getURL(`data/${rel}`));
    if (!response.ok) throw new Error(`${rel}: HTTP ${response.status}`);
    return response.json();
  }).catch((err) => {
    lexiconPromise = null; // let the next lookup retry
    throw err;
  });
  return lexiconPromise;
}

async function lookupAndShow(tabId, frameId, text) {
  let view;
  try {
    view = buildView(await resolveSelection(await openLexicon(), text));
  } catch (err) {
    console.error("ArtikelFinder lookup failed", err);
    view = buildView({ error: "internal" });
  }
  try {
    await showBubble(tabId, frameId, view);
  } catch (err) {
    if (frameId === 0) {
      console.warn("ArtikelFinder cannot show its bubble on this page.", err);
      return;
    }
    // Selection inside a frame we may not script: show it in the top frame instead.
    await showBubble(tabId, 0, view, { anchorToSelection: false }).catch((e) =>
      console.warn("ArtikelFinder cannot show its bubble on this page.", e));
  }
}

async function showBubble(tabId, frameId, view, options = { anchorToSelection: true }) {
  const target = { tabId, frameIds: [frameId] };
  await chrome.scripting.executeScript({ target, files: ["src/bubble.js"] });
  await chrome.scripting.executeScript({
    target,
    func: (v, o) => globalThis.__artikelFinder.show(v, o),
    args: [view, options],
  });
}
