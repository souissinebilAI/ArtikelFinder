import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { Lexicon } from "../src/lexicon.js";
import { lookupKeys, resolveSelection } from "../src/normalize.js";

const keysOf = (text) => lookupKeys(text).keys?.map((k) => k.key);

test("strips punctuation, quotes and whitespace at the edges only", () => {
  assert.deepStrictEqual(keysOf("  „Tischen“, "), ["Tischen"]);
  assert.deepStrictEqual(keysOf("(Tisch)."), ["Tisch"]);
  assert.deepStrictEqual(keysOf("«Maus»"), ["Maus"]);
  assert.deepStrictEqual(keysOf("0,2-Liter-Flasche!"), ["0,2-Liter-Flasche"]); // inner comma and hyphens stay
});

test("removes invisible characters inside the word", () => {
  assert.deepStrictEqual(keysOf("Donau\u00ADdampf\u00ADschiff"), ["Donaudampfschiff"]); // soft hyphens
  assert.deepStrictEqual(keysOf("Ti\u200Bsch"), ["Tisch"]);
});

test("NFC-normalizes decomposed umlauts", () => {
  const decomposed = "Ma\u0308use";
  assert.notEqual(decomposed, "Mäuse");
  assert.deepStrictEqual(keysOf(decomposed), ["Mäuse"]);
});

test("adds a capitalized key for all-lower and all-upper input", () => {
  assert.deepStrictEqual(lookupKeys("tisch").keys, [
    { key: "tisch", caseChanged: false },
    { key: "Tisch", caseChanged: true },
  ]);
  assert.deepStrictEqual(keysOf("TISCHEN"), ["TISCHEN", "Tischen"]);
  assert.deepStrictEqual(keysOf("Tisch"), ["Tisch"]); // already capitalized: nothing to add
  assert.deepStrictEqual(keysOf("iPhone"), ["iPhone"]); // mixed case: leave alone
  assert.deepStrictEqual(keysOf("A"), ["A"]);
});

test("reports empty and overlong input", () => {
  assert.equal(lookupKeys("").error, "empty");
  assert.equal(lookupKeys(" „“ ").error, "empty");
  assert.equal(lookupKeys("x".repeat(101)).error, "too-long");
});

const DATA = fileURLToPath(new URL("../data/", import.meta.url));
const skip = existsSync(DATA + "meta.json") ? false : "run export_runtime.py --out extension/data";
const lexicon = skip ? null : await Lexicon.open(async (rel) => JSON.parse(await readFile(DATA + rel, "utf8")));

test("resolves real selections against the lexicon", { skip }, async () => {
  const lower = await resolveSelection(lexicon, "tischen");
  assert.equal(lower.key, "Tischen");
  assert.equal(lower.caseChanged, true);
  assert.equal(lower.candidates[0].lemma, "Tisch");

  const quoted = await resolveSelection(lexicon, "„Mäuse“");
  assert.equal(quoted.caseChanged, false);
  assert.deepStrictEqual(quoted.candidates.map((c) => [c.lemma, c.genders]), [["Maus", ["FEM"]]]);

  assert.equal((await resolveSelection(lexicon, "LAMPEN")).candidates[0].lemma, "Lampe");
});

test("fails honestly instead of guessing", { skip }, async () => {
  assert.equal((await resolveSelection(lexicon, "Xyzzyplotz")).error, "not-found");
  assert.equal((await resolveSelection(lexicon, "der Tisch")).error, "multi-word");
  assert.equal((await resolveSelection(lexicon, "…")).error, "empty");
});

test("all-caps SS is flagged, not guessed back to ß", { skip }, async () => {
  // "Strasse" is a real form (dative of der Strass, rhinestone), so this is found,
  // but the reader probably meant die Straße: the UI must say SS may stand for ß.
  const result = await resolveSelection(lexicon, "STRASSE");
  assert.deepStrictEqual(result.candidates.map((c) => c.lemma), ["Strass"]);
  assert.equal(result.ssAmbiguous, true);
  assert.equal((await resolveSelection(lexicon, "Strasse")).ssAmbiguous, false);
  assert.equal((await resolveSelection(lexicon, "MASSE")).ssAmbiguous, true);
});

test("prefers the exact form over a case-changed one", { skip }, async () => {
  // "essen" (to eat) is lower-case; the noun is "Essen". The exact key is tried first,
  // so only a miss falls through to the capitalized noun, which is then flagged.
  const result = await resolveSelection(lexicon, "essen");
  assert.equal(result.key, "Essen");
  assert.equal(result.caseChanged, true);
});
