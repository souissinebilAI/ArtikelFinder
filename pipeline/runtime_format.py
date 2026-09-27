"""Runtime lexicon format (v1): the shape the browser extension reads.

    python pipeline/export_runtime.py        # build/lexicon.json -> build/runtime/

Why this shape. A Manifest V3 background worker is stopped after ~30 s idle
and restarted on the next event, so anything parsed at startup is parsed again
and again. The format is therefore many small static JSON files: a lookup
reads one index shard and the paradigm shard(s) it points to, a few tens of
KB, and nothing is held between lookups.

Layout
  meta.json          constants below, so the reader never hard-codes them
  patterns.json      inflection patterns (see below), most frequent first
  i/<k>.json         index shard k: {surface: pid | [pid, ...]}
                     k = fnv1a32(surface as UTF-16 code units) % INDEX_SHARDS
  p/<k>.json         paradigm shard k: records for ids k*PARADIGMS_PER_SHARD ...

Paradigm record: [lemma, gender_mask, evidence, pattern] or, when a second
source disagreed, [lemma, gender_mask, evidence, pattern, overridden_gender_mask].
  gender_mask  bit 0 MASC, bit 1 FEM, bit 2 NEUT (0 = unknown); readers list
               genders in this der/die/das order
  evidence     index into EVIDENCE
  pattern      index into patterns.json

Pattern: [] when the source has no forms, else 8 entries in CELLS order; each
is 0 (cell absent), one encoded form, or a list of them. Encoded form: first
char = how many chars to drop from the end of the lemma (digit in
STRIP_ALPHABET), rest = suffix to append. "Tisch" + "0es" -> "Tisches";
"Maus" + "3äuse" -> "Mäuse"; the lemma itself is "0". Because forms are
relative to the lemma, the 196k paradigms collapse into ~1,200 patterns
(declension classes, in effect): the top 10 cover 72% of nouns.

Which cells a surface fills is not stored in the index: the reader recomputes
it from the paradigm it has to load anyway. Input must be NFC-normalized
(all lexicon data is NFC; this is checked at export).
"""

FORMAT_VERSION = 1
INDEX_SHARDS = 256
PARADIGMS_PER_SHARD = 1024
CELLS = ("NOM.SG", "GEN.SG", "DAT.SG", "ACC.SG", "NOM.PL", "GEN.PL", "DAT.PL", "ACC.PL")
GENDERS = ("MASC", "FEM", "NEUT")
EVIDENCE = ("agree", "filled", "wikidata", "conflict", "unverified", "wikidata_only", "unknown")
STRIP_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def fnv1a32(text):
    """FNV-1a over UTF-16 code units: the same numbers JS gets from charCodeAt."""
    h = 0x811C9DC5
    data = text.encode("utf-16-le")
    for i in range(0, len(data), 2):
        h ^= data[i] | (data[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def index_shard(surface):
    return fnv1a32(surface) % INDEX_SHARDS


def gender_mask(genders):
    return sum(1 << GENDERS.index(g) for g in genders)


def mask_genders(mask):
    return [g for i, g in enumerate(GENDERS) if mask & (1 << i)]


def encode_form(lemma, form):
    common = 0
    while common < min(len(lemma), len(form)) and lemma[common] == form[common]:
        common += 1
    strip = len(lemma) - common
    if strip >= len(STRIP_ALPHABET):
        raise ValueError(f"cannot encode {form!r} relative to {lemma!r}")
    return STRIP_ALPHABET[strip] + form[common:]


def decode_form(lemma, code):
    strip = STRIP_ALPHABET.index(code[0])
    return lemma[:len(lemma) - strip] + code[1:]


def encode_cells(p):
    """The paradigm's pattern: its forms relative to its lemma."""
    cells = []
    if p["cells"]:
        for name in CELLS:
            forms = [encode_form(p["lemma"], f) for f in p["cells"].get(name, [])]
            cells.append(0 if not forms else forms[0] if len(forms) == 1 else forms)
    return cells


def encode_paradigm(p, pattern_id):
    record = [p["lemma"], gender_mask(p["genders"]), EVIDENCE.index(p["evidence"]), pattern_id]
    if "unimorph_genders" in p:
        record.append(gender_mask(p["unimorph_genders"]))
    return record


def decode_paradigm(record, patterns):
    """Reference reader; extension/ must behave exactly like this."""
    lemma, mask, evidence, pattern = record[:4]
    cells = patterns[pattern]
    out = {"lemma": lemma, "genders": mask_genders(mask), "evidence": EVIDENCE[evidence], "cells": {}}
    for name, entry in zip(CELLS, cells):
        if entry != 0:
            codes = entry if isinstance(entry, list) else [entry]
            out["cells"][name] = [decode_form(lemma, c) for c in codes]
    if len(record) > 4:
        out["unimorph_genders"] = mask_genders(record[4])
    return out


def cells_of(paradigm, surface):
    """Cells of `paradigm` that `surface` fills; [] if unknown (lemma-only paradigm)."""
    return [name for name, forms in paradigm["cells"].items() if surface in forms]


class RuntimeLexicon:
    """Reference lookup over an exported directory, shard by shard, as the extension does it."""

    def __init__(self, root):
        import json
        from pathlib import Path
        self._json = json
        self.root = Path(root)
        self.meta = self._load("meta.json")
        if self.meta["format"] != FORMAT_VERSION:
            raise ValueError(f"unsupported runtime format {self.meta['format']}")
        self.patterns = self._load("patterns.json")
        self._cache = {}

    def _load(self, rel):
        return self._json.loads((self.root / rel).read_text(encoding="utf-8"))

    def _shard(self, rel):
        if rel not in self._cache:
            self._cache[rel] = self._load(rel)
        return self._cache[rel]

    def lookup(self, surface):
        """Candidates for an exact (NFC) surface form; [] if unknown."""
        entry = self._shard(f"i/{index_shard(surface)}.json").get(surface)
        if entry is None:
            return []
        out = []
        for pid in entry if isinstance(entry, list) else [entry]:
            shard, offset = divmod(pid, PARADIGMS_PER_SHARD)
            p = decode_paradigm(self._shard(f"p/{shard}.json")[offset], self.patterns)
            p["id"] = pid
            p["surface_cells"] = cells_of(p, surface)
            out.append(p)
        return out
