// background.js against a fake `chrome` API: what it asks Chrome to do for a
// right-click or the shortcut. Real-browser checks are in docs/MANUAL_TEST.md.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const EXT = fileURLToPath(new URL("../", import.meta.url));
const manifest = JSON.parse(readFileSync(EXT + "manifest.json", "utf8"));

test("manifest keeps the least-privilege promise", () => {
  assert.equal(manifest.manifest_version, 3);
  assert.deepStrictEqual([...manifest.permissions].sort(), ["activeTab", "contextMenus", "scripting"]);
  for (const key of ["host_permissions", "optional_host_permissions", "content_scripts", "web_accessible_resources"]) {
    assert.equal(manifest[key], undefined, `${key} must not be declared`);
  }
  assert.equal(manifest.commands["lookup-selection"].suggested_key.default, "Alt+Shift+A");
  assert.ok(existsSync(EXT + manifest.background.service_worker));
  assert.ok(existsSync(EXT + "src/bubble.js"));
});

const skip = existsSync(EXT + "data/meta.json") ? false : "run export_runtime.py --out extension/data";

/** Minimal fake of the chrome.* APIs background.js uses; records executeScript calls. */
function fakeChrome({ failFrames = [] } = {}) {
  const listeners = {};
  const on = (name) => ({ addListener: (fn) => { listeners[name] = fn; } });
  const calls = [];
  const chrome = {
    runtime: { onInstalled: on("installed"), getURL: (p) => `ext://${p}` },
    contextMenus: {
      onClicked: on("menu"),
      removeAll: (cb) => cb(),
      create: (item) => calls.push({ menu: item }),
    },
    commands: { onCommand: on("command") },
    scripting: {
      executeScript: async (details) => {
        calls.push(details);
        if (details.target.frameIds && failFrames.includes(details.target.frameIds[0])) {
          throw new Error("Cannot access contents of the page");
        }
        if (details.func && !details.args) return [{ result: "Tischen" }]; // selection read by the shortcut
        return [{ result: undefined }];
      },
    },
  };
  return { chrome, listeners, calls };
}

async function loadBackground(fake) {
  globalThis.chrome = fake.chrome;
  globalThis.fetch = async (url) => {
    const body = await readFile(EXT + "data/" + url.replace("ext://data/", ""), "utf8");
    return { ok: true, status: 200, json: async () => JSON.parse(body) };
  };
  // A fresh module instance per test (query string busts the ESM cache).
  await import(`../src/background.js?${Math.random()}`);
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 200));
const shows = (calls) => calls.filter((c) => c.args);

test("install creates the selection context menu", { skip }, async () => {
  const fake = fakeChrome();
  await loadBackground(fake);
  fake.listeners.installed();
  assert.deepStrictEqual(fake.calls[0].menu, { id: "artikel-lookup", title: "Artikel für „%s“", contexts: ["selection"] });
});

test("right-click: looks up the selection and shows the bubble in that frame", { skip }, async () => {
  const fake = fakeChrome();
  await loadBackground(fake);
  fake.listeners.menu({ menuItemId: "artikel-lookup", selectionText: "Tischen", frameId: 3 }, { id: 7 });
  await settle();
  const [inject, show] = fake.calls;
  assert.deepStrictEqual(inject, { target: { tabId: 7, frameIds: [3] }, files: ["src/bubble.js"] });
  assert.deepStrictEqual(show.target, { tabId: 7, frameIds: [3] });
  const [view, options] = show.args;
  assert.equal(view.entries[0].article + " " + view.entries[0].lemma, "der Tisch");
  assert.deepStrictEqual(options, { anchorToSelection: true });
});

test("shortcut: reads the selection from the page first", { skip }, async () => {
  const fake = fakeChrome();
  await loadBackground(fake);
  await fake.listeners.command("lookup-selection", { id: 9 });
  await settle();
  assert.deepStrictEqual(fake.calls[0].target, { tabId: 9 });
  assert.equal(shows(fake.calls)[0].args[0].entries[0].lemma, "Tisch");
});

test("frame we may not script: falls back to the top frame, unanchored", { skip }, async () => {
  const fake = fakeChrome({ failFrames: [3] });
  await loadBackground(fake);
  fake.listeners.menu({ menuItemId: "artikel-lookup", selectionText: "Tischen", frameId: 3 }, { id: 7 });
  await settle();
  const show = shows(fake.calls).at(-1);
  assert.deepStrictEqual(show.target, { tabId: 7, frameIds: [0] });
  assert.deepStrictEqual(show.args[1], { anchorToSelection: false });
});

test("unknown word still gets an honest bubble", { skip }, async () => {
  const fake = fakeChrome();
  await loadBackground(fake);
  fake.listeners.menu({ menuItemId: "artikel-lookup", selectionText: "Xyzzyplotz", frameId: 0 }, { id: 1 });
  await settle();
  assert.equal(shows(fake.calls)[0].args[0].kind, "error");
});
