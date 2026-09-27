# Data sources (pinned inputs)

| Source | Pin | License | Role |
|---|---|---|---|
| [UniMorph/deu](https://github.com/unimorph/deu) | commit `d226d2112d3490d8f04ece10d4538123d4297a39` (2024-07-24), in `vendor/unimorph-deu` | CC BY-SA 3.0 | Noun paradigms (surface forms + case/number) |
| [Wikidata lexemes](https://www.wikidata.org/wiki/Wikidata:Lexicographical_data) | dump `20260923` | CC0 | Gender per homograph; fills UniMorph's missing genders |

## Rebuild

```bash
git submodule update --init          # fetch UniMorph at the pinned commit (or clone with --recurse-submodules)
curl -s https://dumps.wikimedia.org/wikidatawiki/entities/20260923/wikidata-20260923-lexemes.json.bz2 \
  | bzcat | python pipeline/extract_wikidata.py > data/raw/wikidata-de-nouns.jsonl   # ~4 min, 188,949 lexemes
python pipeline/build_lexicon.py
python -m unittest discover tests
```

Wikimedia rotates dated dumps after a few months. If `20260923` is gone, use a newer
date, update this file, and review the evidence-count diff printed by `build_lexicon.py`.

## Known limits of the inputs

- UniMorph stores **one gender per headword**, so every homograph with a different gender
  is wrong in the raw data (das Tor, die Leiter, das Erbe…). Paradigm forms are reliable.
- ~2,000 UniMorph lemmas have no gender at all (Richtung, Störung…).
- Of single-paradigm lemmas checkable against Wikidata, ~1.6% disagree; a hand-reviewed
  sample found UniMorph wrong in nearly all clear cases (das Dach, die Gebühr, die Trauer).
  Expect a similar error rate in the ~27% of paradigms Wikidata cannot verify.
- Wikidata is not infallible either (e.g. Sellerie listed as neuter). Disagreements are
  labeled `conflict` in the lexicon, never presented as plain fact.
