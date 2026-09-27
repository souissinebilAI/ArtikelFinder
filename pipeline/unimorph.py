"""Parse UniMorph/deu noun rows into paradigms.

UniMorph is a flat `lemma \\t form \\t N;CASE;GENDER;NUMBER` table. It does not
say where one paradigm ends and the next begins, and a Wiktionary headword with
several homograph entries (der Leiter / die Leiter) comes out as one lemma with
several back-to-back paradigms, all stamped with the *same* gender. We recover
the paradigm boundaries here; gender is resolved later against Wikidata.
"""
import re
from dataclasses import dataclass, field

CASES = ("NOM", "GEN", "DAT", "ACC")
NUMBERS = ("SG", "PL")
GENDERS = ("MASC", "FEM", "NEUT")

# Both sources sometimes pack spelling variants into one form ("Monstren, Monstra",
# "Jesus,Jesu"). Only letter-comma-letter separates variants; decimal commas are
# part of the word (0,2-Liter-Flasche, 1,2,3-Propentricarbonsäure).
PACKED_VARIANTS = re.compile(r"(?<=[^\W\d_]),\s*(?=[^\W\d_])")


@dataclass
class Paradigm:
    lemma: str
    genders: tuple          # UniMorph's claim, e.g. ("MASC",), ("MASC", "NEUT"), or ()
    slots: dict = field(default_factory=dict)   # (case, number) -> [forms in file order]

    def add(self, case, number, form):
        forms = self.slots.setdefault((case, number), [])
        if form not in forms:
            forms.append(form)

    def forms(self):
        return {f for fs in self.slots.values() for f in fs}

    def key(self):
        """Identity for de-duplication: same lemma, gender claim and cells."""
        return (self.lemma, self.genders,
                tuple(sorted((k, tuple(sorted(v))) for k, v in self.slots.items())))


def parse_tag(tag):
    """'N;GEN;MASC+NEUT;SG' -> ('GEN', ('MASC', 'NEUT'), 'SG'). None for non-nouns."""
    parts = tag.split(";")
    if parts[0] != "N":
        return None
    case = next(p for p in parts if p in CASES)
    number = next(p for p in parts if p in NUMBERS)
    gender_part = next((p for p in parts[1:] if p not in CASES and p not in NUMBERS), "")
    genders = tuple(g for g in gender_part.split("+") if g)
    unknown = [g for g in genders if g not in GENDERS]
    if unknown:
        raise ValueError(f"unexpected gender value(s) {unknown} in tag {tag!r}")
    return case, genders, number


def read_paradigms(path):
    """Yield Paradigms in file order.

    Boundary rule: a new paradigm starts when the lemma changes, or when a
    NOM row arrives for a (NOM, number) cell the current paradigm already
    filled and the previous row was not that same cell. The exception keeps
    adjacent spelling variants (Tisches / Tischs) in one paradigm.
    """
    current = None
    prev_cell = None
    with open(path, encoding="utf-8", newline="") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\r\n")
            if not line:
                continue
            cols = line.split("\t")
            if len(cols) != 3:
                raise ValueError(f"{path}:{lineno}: expected 3 tab-separated columns, got {len(cols)}")
            lemma, form, tag = cols
            parsed = parse_tag(tag)
            if parsed is None:
                prev_cell = None
                continue
            case, genders, number = parsed
            cell = (case, number)
            starts_new = (
                current is None
                or lemma != current.lemma
                or genders != current.genders
                or (case == "NOM" and cell in current.slots and prev_cell != cell)
            )
            if starts_new:
                if current is not None:
                    yield current
                current = Paradigm(lemma, genders)
            for variant in PACKED_VARIANTS.split(form):
                current.add(case, number, variant)
            prev_cell = cell
    if current is not None:
        yield current


def restore_bare_dative(p):
    """Add the modern dative singular where UniMorph lists only the archaic -e form.

    UniMorph gives "dem Tische" / "dem Kinde" as the *only* dative singular of
    ~6,400 strong nouns and drops the standard "dem Tisch". Wikidata lists the
    bare form for 99.5% of the affected nouns it covers (5,418 of 5,447), so it
    is restored, first, as the usual form. Weak nouns (dem Studenten) and
    lemmas ending in -e are untouched. Returns True if p was changed.
    """
    nom = p.slots.get(("NOM", "SG"), [])
    dat = p.slots.get(("DAT", "SG"), [])
    if len(nom) == 1 and dat and not nom[0].endswith("e") and all(f == nom[0] + "e" for f in dat):
        dat.insert(0, nom[0])
        return True
    return False


def load_paradigms(path):
    """All noun paradigms with exact duplicates removed. Returns (paradigms, n_duplicates)."""
    seen = set()
    out = []
    dupes = 0
    for p in read_paradigms(path):
        restore_bare_dative(p)
        k = p.key()
        if k in seen:
            dupes += 1
            continue
        seen.add(k)
        out.append(p)
    return out, dupes
