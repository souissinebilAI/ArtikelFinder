"""Write golden lookups for the JavaScript reader to reproduce.

    python tests/make_golden.py      # -> build/golden.json, read by extension/test/

Answers come from the Python reference reader (pipeline/runtime_format.py),
which tests/test_runtime_format.py checks against every surface form. The
sample is chosen, not just random: every evidence label, every spot-check
word, and the edge cases found so far.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import runtime_format as rf  # noqa: E402

RUNTIME = ROOT / "build/runtime"
OUT = ROOT / "build/golden.json"

HAND_PICKED = [
    # spot checks (Step 3)
    "Tisch", "Tische", "Tischen", "Tisches", "Kind", "Kindern", "Kindes", "Mäuse", "Lampen",
    "Spanner", "Studenten", "See", "Sees", "Erbe", "Erbes", "Erben", "Band", "Bänder", "Bände",
    "Bands", "Leiter", "Leitern", "Tor", "Tore", "Toren", "Kiefer", "Kiefern", "Reiser",
    # Wikidata-only and homographs (Step C)
    "Euro", "Millionen", "Medien", "Jugendliche", "Jugendlichen", "Tags", "Tage", "Geschwulst",
    # edge cases: packed variants, decimal comma, no inflected forms, known conflict
    "Monstra", "Monstren", "0,2-Liter-Flasche", "Torr", "Deut", "Dach", "Gebühr", "Straße",
    # not in the lexicon
    "Xyzzyplotz", "tisch", "TISCH", "",
]


def as_js(candidate):
    out = {
        "id": candidate["id"],
        "lemma": candidate["lemma"],
        "genders": candidate["genders"],
        "evidence": candidate["evidence"],
        "cells": candidate["cells"],
        "surfaceCells": candidate["surface_cells"],
    }
    if "unimorph_genders" in candidate:
        out["unimorphGenders"] = candidate["unimorph_genders"]
    return out


def main():
    rt = rf.RuntimeLexicon(RUNTIME)
    rng = random.Random(20260927)
    index_keys = []
    for k in range(rf.INDEX_SHARDS):
        index_keys.extend(rt._shard(f"i/{k}.json"))

    # One random surface form per sampled paradigm, stratified by evidence label.
    by_evidence = {e: [] for e in rf.EVIDENCE}
    for k in range(-(-rt.meta["paradigmCount"] // rf.PARADIGMS_PER_SHARD)):
        for offset, record in enumerate(rt._shard(f"p/{k}.json")):
            by_evidence[rf.EVIDENCE[record[2]]].append((k * rf.PARADIGMS_PER_SHARD + offset, record))
    stratified = []
    for evidence, items in by_evidence.items():
        for pid, record in rng.sample(items, min(150, len(items))):
            p = rf.decode_paradigm(record, rt.patterns)
            forms = sorted({f for fs in p["cells"].values() for f in fs}) or [p["lemma"]]
            stratified.append(rng.choice(forms))

    surfaces = list(dict.fromkeys(HAND_PICKED + stratified + rng.sample(index_keys, 2000)))
    lookups = [{"surface": s, "candidates": [as_js(c) for c in rt.lookup(s)]} for s in surfaces]
    hashes = [{"text": t, "hash": rf.fnv1a32(t), "shard": rf.index_shard(t)}
              for t in ["", "a", "Mäuse", "Straße", "Tischen", "0,2-Liter-Flasche"] + surfaces[:200]]

    OUT.write_text(json.dumps({"format": rf.FORMAT_VERSION, "hashes": hashes, "lookups": lookups},
                              ensure_ascii=False), encoding="utf-8", newline="\n")
    found = sum(1 for x in lookups if x["candidates"])
    print(f"wrote {OUT.relative_to(ROOT)}: {len(lookups)} lookups ({found} found), {len(hashes)} hashes")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
