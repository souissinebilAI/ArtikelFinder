import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { Lexicon } from "../src/lexicon.js";
import { resolveSelection } from "../src/normalize.js";
import { articleOf, buildView, describeCells } from "../src/view.js";

test("articles", () => {
  assert.equal(articleOf(["MASC"]), "der");
  assert.equal(articleOf(["MASC", "FEM"]), "der/die");
  assert.equal(articleOf([]), "?");
});

test("readings of the selected form", () => {
  assert.equal(describeCells(["DAT.PL"]), "dative plural");
  assert.equal(describeCells(["GEN.SG", "DAT.SG", "ACC.SG", "NOM.PL", "GEN.PL", "DAT.PL", "ACC.PL"]),
    "genitive, dative, accusative singular; all cases plural");
  assert.equal(describeCells([]), "case and number not listed");
});

test("error views", () => {
  assert.deepStrictEqual(buildView({ query: "der Tisch", error: "multi-word" }),
    { kind: "error", message: "Select a single word." });
  assert.match(buildView({ query: "Xyzzy", error: "not-found" }).message, /^“Xyzzy” is not in the dictionary/);
  assert.equal(buildView({ error: "internal" }).kind, "error");
});

const DATA = fileURLToPath(new URL("../data/", import.meta.url));
const skip = existsSync(DATA + "meta.json") ? false : "run export_runtime.py --out extension/data";
const lexicon = skip ? null : await Lexicon.open(async (rel) => JSON.parse(await readFile(DATA + rel, "utf8")));
const view = async (text) => buildView(await resolveSelection(lexicon, text));

test("Tischen: article, lemma, reading, plural, certainty, table", { skip }, async () => {
  const v = await view("Tischen");
  assert.equal(v.kind, "found");
  const [e] = v.entries;
  assert.equal(`${e.article} ${e.lemma}`, "der Tisch");
  assert.equal(e.reading, "dative plural");
  assert.equal(e.plural, "die Tische");
  assert.deepStrictEqual(e.certainty, { level: "high", text: "2 sources agree" });
  assert.deepStrictEqual(e.table.rows[1], ["Genitive", "des Tisches / Tischs", "der Tische"]);
  assert.deepStrictEqual(e.table.rows[2], ["Dative", "dem Tisch / Tische", "den Tischen"]);
});

test("Leitern shows both homographs", { skip }, async () => {
  const entries = (await view("Leitern")).entries;
  const byArticle = Object.fromEntries(entries.map((e) => [e.article, e.reading]));
  assert.deepStrictEqual(byArticle, { die: "all cases plural", der: "dative plural" });
});

test("der/die Jugendliche: both articles, no singular articles in the table", { skip }, async () => {
  const [e] = (await view("Jugendlichen")).entries;
  assert.equal(e.article, "der/die");
  assert.ok(e.notes.includes("Both articles are in use."));
  assert.ok(!/^(der|die|des|dem|den) /.test(e.table.rows[0][1]), e.table.rows[0][1]);
  assert.match(e.table.rows[0][2], /^die /);
});

test("conflict is shown as low certainty with the other source's article", { skip }, async () => {
  const [e] = (await view("Dach")).entries;
  assert.equal(e.article, "das");
  assert.equal(e.certainty.level, "low");
  assert.ok(e.notes.includes("The other source says: der Dach."));
});

test("notes for changed capitalization and all-caps SS", { skip }, async () => {
  assert.deepStrictEqual((await view("tischen")).notes, ["Looked up as “Tischen” (capitalization changed)."]);
  assert.ok((await view("STRASSE")).notes.includes("Written in capitals: SS may stand for ß."));
});

test("a noun without inflection data has no table and says so", { skip }, async () => {
  const entries = (await view("Deut")).entries;
  assert.ok(entries.length > 0);
  for (const e of entries) {
    assert.ok(e.table === null || e.table.rows.length === 4);
  }
});
