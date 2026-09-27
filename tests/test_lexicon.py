"""Hand-verified spot checks against the built lexicon.

    python pipeline/build_lexicon.py && python -m unittest discover tests

Expected values are German grammar facts, written independently of what the
pipeline outputs. A failure means the data or the pipeline is wrong, not the test.
"""
import json
import re
import unittest
from pathlib import Path

LEXICON = Path(__file__).resolve().parent.parent / "build/lexicon.json"


def setUpModule():
    global PARADIGMS, INDEX
    if not LEXICON.exists():
        raise unittest.SkipTest(f"{LEXICON} missing; run pipeline/build_lexicon.py first")
    data = json.loads(LEXICON.read_text(encoding="utf-8"))
    PARADIGMS = data["paradigms"]
    INDEX = data["index"]


def lookup(surface):
    """[(lemma, genders, cells)] for a surface form."""
    return [(PARADIGMS[pid]["lemma"], tuple(PARADIGMS[pid]["genders"]), set(cells))
            for pid, cells in INDEX.get(surface, [])]


def genders_for(surface, lemma):
    return {g for l, gs, _ in lookup(surface) if l == lemma for g in gs}


def readings(surface, lemma):
    """{(gender, cell)} for single-gender paradigms of `lemma` containing `surface`."""
    return {(gs[0], c) for l, gs, cells in lookup(surface) if l == lemma and len(gs) == 1
            for c in cells}


class RegularNouns(unittest.TestCase):
    def assertReading(self, surface, lemma, gender, cell):
        hits = [(gs, cells) for l, gs, cells in lookup(surface) if l == lemma]
        self.assertTrue(hits, f"{surface} not mapped to {lemma}")
        self.assertTrue(any(gs == (gender,) and cell in cells for gs, cells in hits),
                        f"{surface}: expected {lemma} {gender} {cell}, got {hits}")

    def test_tisch(self):
        self.assertReading("Tisch", "Tisch", "MASC", "NOM.SG")
        self.assertReading("Tische", "Tisch", "MASC", "NOM.PL")
        self.assertReading("Tischen", "Tisch", "MASC", "DAT.PL")
        self.assertReading("Tisches", "Tisch", "MASC", "GEN.SG")

    def test_kind(self):
        self.assertReading("Kind", "Kind", "NEUT", "NOM.SG")
        self.assertReading("Kinder", "Kind", "NEUT", "NOM.PL")
        self.assertReading("Kindern", "Kind", "NEUT", "DAT.PL")
        self.assertReading("Kindes", "Kind", "NEUT", "GEN.SG")

    def test_umlaut_plural(self):
        self.assertReading("Mäuse", "Maus", "FEM", "NOM.PL")
        self.assertReading("Mäusen", "Maus", "FEM", "DAT.PL")

    def test_lampe(self):
        self.assertReading("Lampe", "Lampe", "FEM", "NOM.SG")
        self.assertReading("Lampen", "Lampe", "FEM", "NOM.PL")

    def test_gender_missing_in_unimorph_is_filled(self):
        # UniMorph ships these without any gender.
        for word in ("Richtung", "Störung", "Abteilung"):
            with self.subTest(word=word):
                self.assertEqual(genders_for(word, word), {"FEM"})


class Ambiguity(unittest.TestCase):
    def test_zero_plural_keeps_both_numbers(self):
        (_, gs, cells), = [h for h in lookup("Spanner") if h[0] == "Spanner"]
        self.assertEqual(gs, ("MASC",))
        self.assertTrue({"NOM.SG", "NOM.PL", "ACC.SG", "ACC.PL"} <= cells)

    def test_weak_noun_syncretism(self):
        # Studenten fills every cell except NOM.SG.
        (_, gs, cells), = [h for h in lookup("Studenten") if h[0] == "Student"]
        self.assertEqual(gs, ("MASC",))
        self.assertEqual(cells, {"GEN.SG", "DAT.SG", "ACC.SG",
                                 "NOM.PL", "GEN.PL", "DAT.PL", "ACC.PL"})

    def test_see(self):
        self.assertEqual(genders_for("See", "See"), {"MASC", "FEM"})
        self.assertEqual(genders_for("Sees", "See"), {"MASC"})

    def test_erbe(self):
        self.assertEqual(genders_for("Erbe", "Erbe"), {"MASC", "NEUT"})
        self.assertEqual(genders_for("Erbes", "Erbe"), {"NEUT"})
        self.assertEqual(genders_for("Erben", "Erbe"), {"MASC"})


class HomographsWrongInUniMorph(unittest.TestCase):
    """UniMorph stamps one gender on all paradigms of a headword; these must be corrected."""

    # Note the dative plurals: "Leitern" is die Leitern *and* den Leitern (der
    # Leiter). The homograph that owns the form in every other cell is the
    # distinguishing one, so assert per cell, not per surface form.

    def test_tor(self):
        self.assertEqual(readings("Tore", "Tor"),                            # das Tor
                         {("NEUT", "NOM.PL"), ("NEUT", "GEN.PL"), ("NEUT", "ACC.PL"),
                          ("NEUT", "DAT.SG")})                               # archaic dem Tore
        self.assertEqual(readings("Toren", "Tor"),
                         {("NEUT", "DAT.PL"),                                # den Toren (gates)
                          ("MASC", "GEN.SG"), ("MASC", "DAT.SG"), ("MASC", "ACC.SG"),
                          ("MASC", "NOM.PL"), ("MASC", "GEN.PL"), ("MASC", "DAT.PL"),
                          ("MASC", "ACC.PL")})                               # der Tor (fool), weak

    def test_leiter(self):
        self.assertEqual(readings("Leitern", "Leiter"),
                         {("FEM", "NOM.PL"), ("FEM", "GEN.PL"), ("FEM", "DAT.PL"), ("FEM", "ACC.PL"),
                          ("MASC", "DAT.PL")})
        self.assertEqual(genders_for("Leiters", "Leiter"), {"MASC"})
        self.assertEqual(genders_for("Leiter", "Leiter"), {"MASC", "FEM"})

    def test_kiefer(self):
        self.assertEqual({g for g, c in readings("Kiefern", "Kiefer") if c == "NOM.PL"}, {"FEM"})
        self.assertIn("FEM", genders_for("Kiefer", "Kiefer"))
        self.assertIn("MASC", genders_for("Kiefers", "Kiefer"))

    def test_band(self):
        self.assertEqual(genders_for("Bänder", "Band"), {"NEUT"})  # das Band, ribbon
        self.assertEqual(genders_for("Bände", "Band"), {"MASC"})   # der Band, volume
        self.assertIn("FEM", genders_for("Bands", "Band"))         # die Band, music group


class Regressions(unittest.TestCase):
    def test_unimorph_gender_errors_corrected(self):
        # UniMorph single-paradigm errors, corrected from Wikidata but still flagged.
        for lemma, gender in (("Dach", "NEUT"), ("Gebühr", "FEM"), ("Trauer", "FEM")):
            with self.subTest(lemma=lemma):
                (p,) = [p for p in PARADIGMS if p["lemma"] == lemma]
                self.assertEqual(p["genders"], [gender])
                self.assertEqual(p["evidence"], "conflict")

    def test_lone_lexeme_does_not_claim_sibling_paradigm(self):
        # Wikidata has only der Reis (rice); it must not relabel das Reis / Reiser (twig).
        self.assertNotIn("MASC", genders_for("Reiser", "Reis"))


class WikidataOnlyNouns(unittest.TestCase):
    """Step C: core vocabulary UniMorph lacks (found missing by eval/measure_coverage.py)."""

    def test_core_vocabulary_found(self):
        for surface, lemma, gender in (("Euro", "Euro", "MASC"), ("Millionen", "Million", "FEM"),
                                       ("Kritik", "Kritik", "FEM"), ("Internet", "Internet", "NEUT"),
                                       ("Medien", "Medium", "NEUT"), ("Koalition", "Koalition", "FEM")):
            with self.subTest(surface=surface):
                self.assertEqual(genders_for(surface, lemma), {gender})

    def test_nominalized_adjective_keeps_both_genders(self):
        # der/die Jugendliche: gender follows the person, so both must survive.
        self.assertEqual(genders_for("Jugendlichen", "Jugendliche"), {"MASC", "FEM"})

    def test_missing_homograph_added_by_distinct_plural(self):
        # "Tags" is also des Tags (genitive of der Tag), so check the plural cell only.
        self.assertEqual({g for g, c in readings("Tags", "Tag") if c == "NOM.PL"}, {"NEUT"})  # das Tag
        self.assertEqual({g for g, c in readings("Tage", "Tag") if c == "NOM.PL"}, {"MASC"})  # der Tag

    def test_sparse_lexeme_fixes_same_word_instead_of_duplicating_it(self):
        # Wikidata's Geschwulst has no forms; it must correct UniMorph's das, not add a second noun.
        self.assertEqual(genders_for("Geschwulst", "Geschwulst"), {"FEM"})
        self.assertEqual(genders_for("Tonart", "Tonart"), {"FEM"})  # UniMorph had no gender


class Invariants(unittest.TestCase):
    def test_every_paradigm_findable_by_lemma(self):
        # Includes Wikidata lexemes with no or incomplete forms (Torr, Deut).
        bad = [p["lemma"] for p in PARADIGMS
               if not any(pid == p["id"] for pid, _ in INDEX.get(p["lemma"], []))]
        self.assertEqual(bad, [])

    def test_index_round_trips(self):
        for p in PARADIGMS:
            for cell, forms in p["cells"].items():
                for f in forms:
                    self.assertIn(cell, next(c for pid, c in INDEX[f] if pid == p["id"]))

    def test_no_packed_variants(self):
        # Wikidata sometimes writes "Monstren, Monstra" in one form; each must be its own entry.
        self.assertEqual([f for f in INDEX if re.search(r"[^\W\d_],\s*[^\W\d_]", f)], [])
        self.assertIn("Monstra", INDEX)
        self.assertIn("0,2-Liter-Flasche", INDEX)  # decimal comma is part of the word

    def test_known_genders_only(self):
        self.assertLessEqual({g for p in PARADIGMS for g in p["genders"]}, {"MASC", "FEM", "NEUT"})


if __name__ == "__main__":
    unittest.main()
