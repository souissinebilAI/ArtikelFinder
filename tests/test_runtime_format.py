"""The sharded runtime format must answer every lookup exactly like build/lexicon.json.

    python pipeline/build_lexicon.py && python pipeline/export_runtime.py
    python -m unittest discover tests
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import runtime_format as rf  # noqa: E402

LEXICON = ROOT / "build/lexicon.json"
RUNTIME = ROOT / "build/runtime"


class Hash(unittest.TestCase):
    """Golden values: the JavaScript reader must reproduce these exactly."""

    def test_fnv1a_vectors(self):
        # "" and "a" are the published FNV-1a vectors; the rest were computed by
        # two independent implementations (per UTF-16 byte pair, per code point).
        for text, h, shard in (("", 0x811C9DC5, 197), ("a", 0xE40C292C, 44),
                               ("Mäuse", 0xE7D50A5F, 95), ("Straße", 0x05D9A0A3, 163),
                               ("Tischen", 0xF653E98F, 143)):
            with self.subTest(text=text):
                self.assertEqual(rf.fnv1a32(text), h)
                self.assertEqual(rf.index_shard(text), shard)


class FormEncoding(unittest.TestCase):
    def test_round_trip(self):
        for lemma, form, code in (("Tisch", "Tisches", "0es"), ("Maus", "Mäuse", "3äuse"),
                                  ("Tisch", "Tisch", "0"), ("Museum", "Museen", "2en"),
                                  ("Monstrum", "Monstra", "2a")):
            with self.subTest(form=form):
                self.assertEqual(rf.encode_form(lemma, form), code)
                self.assertEqual(rf.decode_form(lemma, code), form)


@unittest.skipUnless(LEXICON.exists() and (RUNTIME / "meta.json").exists(),
                     "run build_lexicon.py and export_runtime.py first")
class Equivalence(unittest.TestCase):
    def test_every_surface_form(self):
        lex = json.loads(LEXICON.read_text(encoding="utf-8"))
        paradigms = lex["paradigms"]
        rt = rf.RuntimeLexicon(RUNTIME)
        mismatches = []
        for surface, entries in lex["index"].items():
            expected = sorted(
                (pid, paradigms[pid]["lemma"], frozenset(paradigms[pid]["genders"]),
                 paradigms[pid]["evidence"], tuple(sorted(cells)))
                for pid, cells in entries)
            got = sorted(
                (c["id"], c["lemma"], frozenset(c["genders"]), c["evidence"], tuple(sorted(c["surface_cells"])))
                for c in rt.lookup(surface))
            if got != expected:
                mismatches.append((surface, expected, got))
        self.assertEqual(mismatches[:5], [], f"{len(mismatches)} mismatching surface forms")

    def test_full_paradigm_and_overrides_survive(self):
        lex = json.loads(LEXICON.read_text(encoding="utf-8"))
        rt = rf.RuntimeLexicon(RUNTIME)
        for pid, p in enumerate(lex["paradigms"]):
            shard, offset = divmod(pid, rf.PARADIGMS_PER_SHARD)
            got = rf.decode_paradigm(rt._shard(f"p/{shard}.json")[offset], rt.patterns)
            # Genders are a set; the runtime returns them in der/die/das order.
            for key in ("genders", "unimorph_genders"):
                if key in p:
                    self.assertEqual(got.pop(key), [g for g in rf.GENDERS if g in p[key]])
            self.assertEqual(got, {k: p[k] for k in ("lemma", "evidence", "cells")})

    def test_unknown_word(self):
        self.assertEqual(rf.RuntimeLexicon(RUNTIME).lookup("Xyzzyplotz"), [])


if __name__ == "__main__":
    unittest.main()
