"""Export build/lexicon.json to the sharded runtime format (see runtime_format.py).

    python pipeline/export_runtime.py
"""
import json
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import runtime_format as rf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LEXICON = ROOT / "build/lexicon.json"
OUT = ROOT / "build/runtime"


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8", newline="\n")


def main():
    lex = json.loads(LEXICON.read_text(encoding="utf-8"))
    paradigms, index = lex["paradigms"], lex["index"]
    for surface in index:
        if unicodedata.normalize("NFC", surface) != surface:
            raise ValueError(f"surface form not NFC: {surface!r}")

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "i").mkdir(parents=True)
    (OUT / "p").mkdir()

    shards = defaultdict(dict)
    for surface, entries in index.items():
        pids = [pid for pid, _ in entries]
        shards[rf.index_shard(surface)][surface] = pids[0] if len(pids) == 1 else pids
    for k in range(rf.INDEX_SHARDS):
        write_json(OUT / "i" / f"{k}.json", dict(sorted(shards[k].items())))

    for pid, p in enumerate(paradigms):
        assert p["id"] == pid, "paradigm ids must be dense and ordered"
    # Pattern ids by descending frequency, so common patterns get short ids.
    keyed = [json.dumps(rf.encode_cells(p), ensure_ascii=False) for p in paradigms]
    ranked = [k for k, _ in Counter(keyed).most_common()]
    pattern_id = {k: i for i, k in enumerate(ranked)}
    write_json(OUT / "patterns.json", [json.loads(k) for k in ranked])

    n_pshards = -(-len(paradigms) // rf.PARADIGMS_PER_SHARD)
    for k in range(n_pshards):
        lo, hi = k * rf.PARADIGMS_PER_SHARD, (k + 1) * rf.PARADIGMS_PER_SHARD
        write_json(OUT / "p" / f"{k}.json",
                   [rf.encode_paradigm(p, pattern_id[key]) for p, key in zip(paradigms[lo:hi], keyed[lo:hi])])

    write_json(OUT / "meta.json", {
        "format": rf.FORMAT_VERSION,
        "hash": "fnv1a32-utf16",
        "indexShards": rf.INDEX_SHARDS,
        "paradigmsPerShard": rf.PARADIGMS_PER_SHARD,
        "paradigmCount": len(paradigms),
        "cells": list(rf.CELLS),
        "genders": list(rf.GENDERS),
        "evidence": list(rf.EVIDENCE),
        "stripAlphabet": rf.STRIP_ALPHABET,
    })

    sizes = {d: [f.stat().st_size for f in (OUT / d).iterdir()] for d in ("i", "p")}
    total = sum(f.stat().st_size for f in OUT.rglob("*.json"))
    print(f"runtime lexicon: {total / 1e6:.1f} MB; {len(ranked)} patterns "
          f"({(OUT / 'patterns.json').stat().st_size / 1e3:.0f} KB)")
    for d, name in (("i", "index"), ("p", "paradigm")):
        s = sorted(sizes[d])
        print(f"  {name} shards: {len(s)}, median {s[len(s) // 2] / 1e3:.0f} KB, max {s[-1] / 1e3:.0f} KB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
