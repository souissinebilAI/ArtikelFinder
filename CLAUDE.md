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
  - Open: coverage vs. real text is unmeasured (no frequency list yet); 188k Wikidata lexemes vs 28k in UniMorph — adding Wikidata-only nouns is a possible 6× coverage gain, undecided.
- Then Step 4: repo structure + Milestone 1 scope (select word → lookup → display article, no accounts/AI/backend).
- Then Step 5: implement Milestone 1, testing as we go.

The original cloud chat session couldn't bulk-download the UniMorph data file directly (its network sandbox blocks raw.githubusercontent.com/huggingface.co) — that's why this moved to a local/Code environment with real git access. If the `deu` file isn't already in this project folder, `git clone https://github.com/unimorph/deu.git vendor/unimorph-deu` is the next concrete action.
