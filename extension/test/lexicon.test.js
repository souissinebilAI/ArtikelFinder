// The JS reader must answer exactly like the Python reference reader.
// Needs: python pipeline/export_runtime.py --out extension/data && python tests/make_golden.py
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { Lexicon, fnv1a32 } from "../src/lexicon.js";

const DATA = fileURLToPath(new URL("../data/", import.meta.url));
const GOLDEN = fileURLToPath(new URL("../../build/golden.json", import.meta.url));
const missing = [DATA + "meta.json", GOLDEN].filter((p) => !existsSync(p));
const skip = missing.length ? `missing ${missing.join(", ")}; see header comment` : false;

const loadJson = async (rel) => JSON.parse(await readFile(DATA + rel, "utf8"));
const golden = skip ? null : JSON.parse(await readFile(GOLDEN, "utf8"));

test("FNV-1a published vectors", () => {
  assert.equal(fnv1a32(""), 0x811c9dc5);
  assert.equal(fnv1a32("a"), 0xe40c292c);
});

test("hashes and shards match Python", { skip }, async () => {
  const lex = await Lexicon.open(loadJson);
  for (const { text, hash, shard } of golden.hashes) {
    assert.equal(fnv1a32(text), hash, text);
    assert.equal(fnv1a32(text) % lex.meta.indexShards, shard, text);
  }
});

test("every golden lookup matches Python", { skip }, async () => {
  const lex = await Lexicon.open(loadJson);
  assert.equal(golden.format, lex.meta.format);
  for (const { surface, candidates } of golden.lookups) {
    assert.deepStrictEqual(await lex.lookup(surface), candidates, `lookup(${JSON.stringify(surface)})`);
  }
});

test("prototype keys are not words", { skip }, async () => {
  const lex = await Lexicon.open(loadJson);
  for (const word of ["constructor", "__proto__", "toString", "hasOwnProperty"]) {
    assert.deepStrictEqual(await lex.lookup(word), [], word);
  }
});

test("shard cache stays bounded and shares in-flight loads", async () => {
  let loads = 0;
  const fake = async (rel) => {
    loads++;
    if (rel === "meta.json") {
      return { format: 1, indexShards: 256, paradigmsPerShard: 1024, cells: [], genders: [], evidence: [], stripAlphabet: "0" };
    }
    return rel === "patterns.json" ? [] : {};
  };
  const lex = await Lexicon.open(fake, { maxCachedShards: 2 });
  loads = 0;
  await Promise.all([lex.shard("i/1.json"), lex.shard("i/1.json")]);
  assert.equal(loads, 1, "concurrent requests share one load");
  await lex.shard("i/2.json");
  await lex.shard("i/3.json");
  assert.equal(lex.cache.size, 2);
  assert.ok(!lex.cache.has("i/1.json"), "least recently used shard evicted");
});

test("a failed shard load is retried, not cached", async () => {
  let fail = true;
  const flaky = async (rel) => {
    if (rel === "meta.json") return { format: 1 };
    if (rel === "patterns.json") return [];
    if (fail) throw new Error("network");
    return { ok: true };
  };
  const lex = await Lexicon.open(flaky);
  await assert.rejects(lex.shard("i/5.json"));
  await new Promise((resolve) => setImmediate(resolve));
  fail = false;
  assert.deepStrictEqual(await lex.shard("i/5.json"), { ok: true });
});
