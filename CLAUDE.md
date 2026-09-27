# ArtikelFinder — Project Context

Carried over from planning work in Claude (chat/Cowork). Treat this as settled context for continuing the project here — not a request to redo Steps 1-2.

**What it is:** A browser extension that identifies the grammatical article (der/die/das) of a German noun selected on a webpage, including inflected forms (Tischen → der Tisch). Built as a portfolio project for CS/SWE job applications in Germany — must be technically defensible in an interview, not a tutorial toy. Acting persona for this project: senior software engineer / ruthless technical mentor — challenge weak ideas, avoid unnecessary complexity, explain trade-offs.

## Scope boundaries (decided, not open for debate without a reason)
- **No AI at the core.** Article lookup is deterministic (dictionary + morphology), never LLM-based. AI is only a possible later add-on (sentence explanations), opt-in, never the foundation.
- **No backend for the MVP.** Everything runs client-side: bundled lexicon, reverse-inflection index, decompounder. A backend is only justified later for features that are inherently backend-shaped (opt-in LLM explainer, cross-device sync) — never for basic lookup.
- **No React/DB/backend "because it looks good on a CV."** Every technology must solve a real problem here.
- **Never fake linguistic certainty.** Every result is labeled: dictionary fact / morphological analysis / heuristic / contextual inference. Ambiguous or unknown input fails gracefully, never hallucinates.
- **True context-aware case resolution (POS/dependency parsing) is explicitly out of scope for the MVP.** It requires real NLP tooling (spaCy-class), not hand-rolled regex, and isn't worth faking.

## The two core technical problems
1. **Lexical lookup** — lemma, gender/article, plural: a dictionary problem.
2. **Morphological normalization** — inflected surface form → lemma: solved via a **precomputed reverse-inflection index**, not runtime suffix-stripping. Falls back to rightmost-element decompounding, then labeled suffix heuristics, then honest "unknown."
3. **Ambiguity is real, not an edge case**: data model is `surface form → candidate[] {lemma, gender, case[], number[], confidence, source}`, never a flat 1:1 mapping. Confirmed real cases: zero-plural nouns (der/die Lehrer), weak/n-declension case syncretism (Studenten = 7 of 8 possible case/number slots), cross-homograph dative plurals (Leitern = die Leitern *or* den Leitern of der Leiter), gender-changing homographs (der See/die See, der Erbe/das Erbe, der/die/das Band).

## Data source — decided (verified against authoritative sources)
- **Primary: [UniMorph/deu](https://github.com/unimorph/deu)** — CC BY-SA 3.0 (confirmed in-repo + on the UniMorph mailing list), already the exact `lemma × surface form × {case, gender, number}` table needed. ~28,989 noun lemmas, 519,143 total inflected forms across all POS. Verified row format: `Spanner\tSpanner\tN;NOM;MASC;SG`. Derived from **English** Wiktionary's German entries (not German Wiktionary) — coverage/accuracy not yet independently validated, this is the current biggest open risk.
- **Cross-check: [Wikidata Lexemes](https://www.wikidata.org/wiki/Wikidata:Lexicographical_data)** — CC0, confirmed directly on Wikidata:Licensing ("main, property and lexeme namespaces... CC0"). Used to validate UniMorph's gender facts and fill gaps.
- **Enrichment (optional/stretch): German Wiktionary / wiktextract** — CC BY-SA 4.0/GFDL, for glosses/IPA/translations.
- **Rejected: der-artikel.de.** Educational rules/exercises site, no lookup database, no API, no discoverable license or terms.
- **Rejected: verbformen.de (Netzverb).** Content is nominally CC BY-SA 4.0, but there is no API and no bulk/download dataset — only ~160,000 individual HTML pages to scrape one at a time. Technically fragile despite the permissive license.
- **Rejected: DWDS (BBAW).** Has real APIs, but its own terms (dwds.de/d/nutzungsbedingungen) require express permission for any automated/bulk use and restrict commercial use of parts of the corpus. Revisit only with written permission, never bundle without it.
- **Excluded, confirmed via primary sources:** spaCy German models (MIT model, but trained on the non-commercial-only TIGER Corpus — and moot anyway, UniMorph covers this); GermaNet (fee-gated); Duden/LEO/PONS/dict.cc (proprietary, no usable terms).

## Architecture — decided
**Option B: fully client-only, bundled local dataset. No backend for the MVP.** This followed directly from the data source (a complete, redistributable, offline-buildable dataset already exists) — not chosen in advance. Code MIT top to bottom; bundled dictionary data is CC BY-SA (from UniMorph/Wiktionary) — needs its own `DATA_LICENSE.md` + attribution in the README and an in-extension About screen.

## Where we are / what's next
- Step 1 (stress-test) — done.
- Step 2 (data source & licensing) — done. UniMorph/deu selected as primary source; architecture confirmed as client-only/bundled.
- **Step 3 — done (2026-09-24).** Pipeline in `pipeline/` (Python, stdlib only — build-time tool, no Node on this machine, and streaming a multi-GB dump is stdlib-trivial in Python). Pins and rebuild steps in `data/SOURCES.md`. Tests: `python -m unittest discover tests` (18 hand-verified checks, all pass).
  - **Key finding: UniMorph gender is per headword, not per paradigm** — wrong by construction for every gender-changing homograph (das Tor, die Leiter, das Erbe, 4× Band all FEM). ~2,000 lemmas have no gender (Richtung!). ~1.6% of checkable single-paradigm lemmas have wrong gender (das Dach, die Gebühr). So **Wikidata is a second gender source, not a sample cross-check**: UniMorph = forms, Wikidata (188,949 German noun lexemes, per-homograph) = gender.
  - Paradigm boundaries are recovered from UniMorph's row order; 485 exact-duplicate paradigms dropped. Paradigms ↔ lexemes matched one-to-one by Jaccard over (case, number, form) cells, best-first with a margin (refuse coin flips).
  - Every paradigm carries an `evidence` label: agree 18,536 (65%) · filled 1,582 · wikidata (homograph fix) 105 · conflict 308 (Wikidata used, flagged) · unverified 7,577 (27%, UniMorph only) · unknown 396.
  - Output `build/lexicon.json`: 28,504 paradigms, 82,806 surface forms; 11.7 MB raw / 1.8 MB gzip.
- **Step B, coverage measured (2026-09-27).** `eval/measure_coverage.py` on Leipzig Corpora Collection 100K-sentence corpora (news 2023, Wikipedia 2021; evaluation only, never bundled, license not yet confirmed). Denominator = capitalized, non-sentence-initial tokens (German capitalization ≈ noun or name); hyphen splits mimic browser double-click.
  - Found 55.7% (news) / 54.4% (Wikipedia) of those tokens. Misses: ~19% are **common nouns UniMorph lacks but Wikidata has** (Euro, Millionen, Kritik, Video, Internet, Koalition, Demokratie, Unterstützung — core vocabulary); the rest is mostly names/pronouns ("Sie").
  - Hand-labeled 100 frequency-weighted non-Wikidata misses: ~20% real nouns (two-thirds compounds, rest nominalized adjectives/infinitives), ~80% names/brands/pronouns/adjectives.
  - Estimated common-noun coverage: **~69% now → ~94% with Wikidata-only nouns → ~98% with compound fallback** (sample-based, ±several points).
  - Of found tokens, gender is Wikidata-verified for ~89%, flagged conflict ~2%, UniMorph-only ~7–8%, none ~1%.
  - **Decompounding warning:** place names look like compounds (Ham|burg → "die Burg", but it is das Hamburg; Deutsch|land). The compound fallback must be labeled heuristic and should not fire on words that look like names.
  - **Nominalized adjectives** (der/die Jugendliche, Beamten, Vorsitzende, Jährige) are frequent; their gender depends on the referent. They need their own handling/label, not a single article.
  - Step C decision implied by the data: add Wikidata-only nouns (single-source gender, labeled as such). Wikidata gender agreed with UniMorph in 18,536 of 18,844 comparable paradigms, and the disagreements were mostly UniMorph errors.
- **Step C, Wikidata-only nouns added (2026-09-27).** `add_wikidata_only()` in `pipeline/build_lexicon.py`; label `wikidata_only`. 22 tests pass.
  - +167,725 new lemmas. For lemmas UniMorph already has, a Wikidata lexeme is added only if it brings a new gender **and** a new plural (a true missing homograph: das Tag/Tags beside der Tag/Tage), so near-copies of the same word are never shown twice.
  - Sparse Wikidata lexemes (few/no forms) now match by lemma alone when unambiguous (one gender, no new plural, no lexeme already assigned), fixing e.g. die Geschwulst and Tonart instead of duplicating them. The "no lexeme already assigned" condition keeps das Reis/Reiser (twig) from inheriting der Reis (rice).
  - Wikidata data defects handled: one Dutch-tagged lexeme with "common" gender (dropped to unknown); lexemes whose forms lack the nominative (Torr, Deut): their lemma is always indexed, with unknown case/number.
  - Result: 196,248 paradigms, 535,242 surface forms. Coverage of capitalized tokens 55.7% → **75.2%** (news), 54.4% → 72.5% (Wikipedia); estimated common-noun coverage ≈ 94%. Of found tokens: 66% gender verified by both sources / Wikidata match, 27% Wikidata only, 1.6% conflict, 4.4% UniMorph only, 1.2% no gender.
  - **Cost: lexicon.json is 86 MB raw / 10.8 MB gzip** (was 11.7 / 1.8). Too big to load as one JSON object in an extension; the runtime data format is the first Step D problem (the index also duplicates cell info already in the paradigms).
- **Step D1, runtime data format (2026-09-27).** Spec + reference reader: `pipeline/runtime_format.py`; export: `pipeline/export_runtime.py` → `build/runtime/`.
  - Constraint that decided it: an MV3 background worker is killed after ~30 s idle, so anything parsed at startup is re-parsed repeatedly. Chosen: **many small static JSON shards in the extension package, fetched per lookup** (no install step, no IndexedDB, no state). Rejected: one big JSON (86 MB re-parsed per worker start), IndexedDB import (install step + migrations for no gain at 1 lookup per selection), custom binary trie/FST (smallest, but lots of custom code; revisit only if size becomes a real problem).
  - Layout: `meta.json`; `patterns.json`; 256 index shards `i/<fnv1a32(UTF-16 units) % 256>.json` = `{surface: pid | [pids]}`; 192 paradigm shards `p/<pid // 1024>.json` = `[lemma, genderMask, evidence, patternId(, overriddenGenderMask)]`. Case/number cells are not stored in the index; the reader recomputes them from the paradigm.
  - Forms are stored relative to the lemma ("0es" = lemma + "es", "3äuse" = drop 3 + "äuse"), so 196k paradigms collapse into **1,201 patterns** (declension classes, in effect; top 10 cover 72%).
  - Size: 86 MB → **17.0 MB on disk, 6.5 MB compressed**; per lookup ≈ 48 KB index shard + 24 KB paradigm shard + 75 KB patterns.
  - Verified: `tests/test_runtime_format.py` looks up all 535,239 surfaces and decodes all 196,248 paradigms through the shards and compares them with lexicon.json (identical); hash golden values computed by two independent implementations, which the JS reader must reproduce. Canonical gender order in runtime = MASC, FEM, NEUT (der/die/das).
  - Also fixed during D1: both sources pack variants into one form ("Monstren, Monstra", "Jesus,Jesu"); split on letter-comma-letter only (decimal commas as in 0,2-Liter-Flasche are part of the word). 28 tests pass.
  - Rules for the JS reader: NFC-normalize input; index shard by FNV-1a over UTF-16 code units (`Math.imul`, `>>> 0`); read constants from meta.json.
- **Step D2, Milestone 1 scope + repo layout (2026-09-27): see `docs/MILESTONE1.md`.** Key decisions:
  - **Trigger = context menu + Alt+Shift+A, not auto-bubble on double-click**: needs only `activeTab` + `scripting` + `contextMenus`, so no "read all your data on all websites" install warning. Double-click mode later as opt-in via `optional_host_permissions`.
  - Lookup runs in the background service worker (data not web-accessible, so pages cannot fingerprint it); bubble injected into the page in a closed Shadow DOM, rendered with `textContent` only (Wikidata is user-editable, never insert as HTML).
  - Plain JS ES modules, no bundler/framework/TS build; JSDoc types. Tests with `node:test`, no npm dependencies. Chrome/Edge first; Firefox after M1.
  - Layout: `extension/{manifest.json, src/lexicon.js, src/normalize.js, src/background.js, src/bubble.js, about.html, data/ (generated, git-ignored), test/}`. `python pipeline/export_runtime.py --out extension/data` fills `data/` (refuses targets outside the repo, since it replaces the folder).
  - JS reader parity is tested against golden lookups written by Python.
  - Node.js 24 LTS installed via winget (`C:\Program Files\nodejs`; new shells have it on PATH).
- Then Step 5: implement Milestone 1, testing as we go.

The original cloud chat session couldn't bulk-download the UniMorph data file directly (its network sandbox blocks raw.githubusercontent.com/huggingface.co) — that's why this moved to a local/Code environment with real git access. If the `deu` file isn't already in this project folder, `git clone https://github.com/unimorph/deu.git vendor/unimorph-deu` is the next concrete action.
