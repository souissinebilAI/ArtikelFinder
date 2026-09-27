# Data license

ArtikelFinder has two licenses:

| What | License |
|---|---|
| Source code (everything in this repository) | MIT, see [LICENSE](LICENSE) |
| The dictionary data the extension ships (`extension/data/`, built by `pipeline/`) | **CC BY-SA 3.0**, this file |

The dictionary is not stored in this repository; `pipeline/` builds it from the sources
below (pinned versions in [data/SOURCES.md](data/SOURCES.md)). Any copy of the built data,
including the packaged extension, is covered by this file.

## Sources

**UniMorph German (deu)**, noun paradigms (surface forms, case, number, gender).
[github.com/unimorph/deu](https://github.com/unimorph/deu), commit `d226d21`.
Licensed under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
UniMorph's German data is derived from English Wiktionary; credit goes to the UniMorph
project and the [Wiktionary contributors](https://en.wiktionary.org/).

**Wikidata lexemes**, German nouns (gender, forms), dump of 2026-09-23.
[wikidata.org](https://www.wikidata.org/wiki/Wikidata:Lexicographical_data).
Licensed under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/): no rights
reserved. Credited here anyway, with thanks to the Wikidata community.

## This data is an adaptation

ArtikelFinder's dictionary combines and changes the sources. As required by CC BY-SA, the
adaptation is released under the same license, CC BY-SA 3.0. Changes made
(details and reasons in [CLAUDE.md](CLAUDE.md) and the `pipeline/` docstrings):

- UniMorph paradigms split per homograph; exact duplicates removed.
- Gender taken from Wikidata where UniMorph's gender is missing, applies to a different
  homograph, or disagrees (disagreements stay labeled `conflict`).
- Nouns missing from UniMorph added from Wikidata.
- The standard dative singular ("dem Tisch") added where UniMorph lists only the archaic
  "-e" form.
- Spelling variants packed into one field ("Monstren, Monstra") split.
- Re-encoded into the sharded runtime format (`pipeline/runtime_format.py`).

Every entry keeps a label saying which source(s) its gender comes from; the extension
shows it with every result.

This is a summary for users of the data, not legal advice. The license texts linked above
are authoritative.
