"""Build the ArtikelFinder lexicon from UniMorph/deu + Wikidata lexemes.

    python pipeline/build_lexicon.py

Inputs
  vendor/unimorph-deu/deu              UniMorph noun paradigms (forms are trusted)
  data/raw/wikidata-de-nouns.jsonl     from extract_wikidata.py (gender cross-check)

Outputs (build/)
  lexicon.json         {"paradigms": [...], "index": {surface: [[paradigm_id, [cell, ...]], ...]}}
  gender_report.tsv    one row per paradigm whose gender is not a clean two-source agreement

Gender policy. UniMorph stores one gender per headword, so it is wrong by
construction for homographs (das Tor / der Tor). Every paradigm is therefore
matched to a Wikidata lexeme by overlap of (case, number, form) cells, and
gets an evidence label:
  agree        both sources give the same gender set
  filled       UniMorph has no gender; Wikidata's is used
  wikidata     lemma has several paradigms (UniMorph gender unreliable), and
               a Wikidata lexeme matched on forms; Wikidata's is used
  conflict     single-paradigm lemma, sources disagree; Wikidata's is used
               (UniMorph was wrong in nearly every hand-checked case) and
               UniMorph's claim is kept so the UI can show lower confidence
  unverified   no usable Wikidata match; UniMorph's gender kept as-is
  wikidata_only  not in UniMorph at all; forms and gender from Wikidata alone
  unknown      no gender from either source
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from unimorph import load_paradigms  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UNIMORPH = ROOT / "vendor/unimorph-deu/deu"
WIKIDATA = ROOT / "data/raw/wikidata-de-nouns.jsonl"
OUT = ROOT / "build"

# When a lemma has several Wikidata lexemes (homographs), the best-matching one
# must reach MIN_SCORE (Jaccard over (case, number, form) cells) and beat the
# runner-up by MIN_MARGIN; otherwise we refuse to guess which homograph it is.
MIN_SCORE = 0.3
MIN_MARGIN = 0.1


def cell_name(case, number):
    return f"{case}.{number}"


def paradigm_cells(p):
    return {(c, n, f) for (c, n), forms in p.slots.items() for f in forms}


def lexeme_cells(lex):
    out = set()
    for f in lex["forms"]:
        case = next((x for x in f["feats"] if x in ("NOM", "GEN", "DAT", "ACC")), None)
        number = next((x for x in f["feats"] if x in ("SG", "PL")), None)
        if case and number:
            out.add((case, number, f["form"]))
    return out


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def load_wikidata(path):
    by_lemma = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            lex = json.loads(line)
            lex["cells"] = lexeme_cells(lex)
            by_lemma[lex["lemma"]].append(lex)
    return by_lemma


def match_lexemes(group, wd_lexemes):
    """Match the paradigms of one lemma one-to-one to its Wikidata lexemes.

    Returns [(lexeme or None, score)] aligned with `group`; score is None for a
    lemma-only match. An absolute threshold does not work: spelling variants
    (Lichter / Lichte) drag true matches down, while homographs (der See /
    die See) share most cells and score high. So this is an assignment
    problem: take pairs best-first, use each paradigm and lexeme at most once
    (a lone der Reis, rice, must not also claim das Reis / Reiser, twig), and
    refuse a pair when a still-open rival for either side is within MIN_MARGIN.
    Groups are tiny (at most 4 x 4), so greedy is exact enough and readable.
    """
    if not wd_lexemes:
        return [(None, 0.0)] * len(group)
    if len(group) == 1 and len(wd_lexemes) == 1 and not wd_lexemes[0]["cells"]:
        # Nothing to compare, but one word on each side: same word by lemma.
        return [(wd_lexemes[0], None)]
    ambiguous_homograph = len(group) > 1 or len(wd_lexemes) > 1
    scores = {(i, j): jaccard(paradigm_cells(p), lex["cells"])
              for i, p in enumerate(group) for j, lex in enumerate(wd_lexemes)}
    best_seen = [max(scores[i, j] for j in range(len(wd_lexemes))) for i in range(len(group))]
    out = [(None, s) for s in best_seen]
    open_p, open_l = set(range(len(group))), set(range(len(wd_lexemes)))
    for (i, j), s in sorted(scores.items(), key=lambda kv: -kv[1]):
        if i not in open_p or j not in open_l:
            continue
        if s <= 0 or (ambiguous_homograph and s < MIN_SCORE):
            break
        rivals = [scores[i, k] for k in open_l if k != j] + [scores[k, j] for k in open_p if k != i]
        if any(s - r < MIN_MARGIN for r in rivals):
            # Too close to call; leave both sides open for other pairs.
            continue
        out[i] = (wd_lexemes[j], s)
        open_p.discard(i)
        open_l.discard(j)

    # Fallback for lexemes too sparse to match on forms (Tonart, Geschwulst):
    # if no lexeme was assigned yet, every lexeme gives the same gender, none
    # has a plural the paradigms lack, and the paradigms look like variants of
    # one word (one shared gender claim), it is the same word; match by lemma.
    # "No lexeme assigned yet" matters: once der Reis (rice) matched on forms,
    # the leftover das Reis / Reiser (twig) is a different word, not a variant.
    gender_sets = {tuple(sorted(lex["genders"])) for lex in wd_lexemes if lex["genders"]}
    if (len(open_l) == len(wd_lexemes) and len(gender_sets) == 1
            and len({p.genders for p in group}) == 1
            and not any(nom_plurals(lex["cells"]) - group_plurals(group) for lex in wd_lexemes)):
        lex = next(lex for lex in wd_lexemes if lex["genders"])
        for i in open_p:
            out[i] = (lex, None)
    return out


def nom_plurals(cells):
    return {f for c, n, f in cells if (c, n) == ("NOM", "PL")}


def group_plurals(group):
    return {f for p in group for f in p.slots.get(("NOM", "PL"), [])}


def resolve_gender(p, siblings, match):
    """Return (genders, evidence, detail) for one UniMorph paradigm."""
    um = tuple(sorted(p.genders))
    best, best_score = match

    detail = {"um": list(um), "score": best_score}
    if best is None or not best["genders"]:
        if best is not None:
            detail["wd_id"] = best["id"]
        return (list(um), "unverified", detail) if um else ([], "unknown", detail)

    wd = tuple(sorted(best["genders"]))
    detail.update(wd_id=best["id"], wd=list(wd))
    if not um:
        return list(wd), "filled", detail
    if um == wd:
        return list(um), "agree", detail
    if siblings > 1 and best_score is not None:
        return list(wd), "wikidata", detail
    # Hand review of a random sample of conflicts found UniMorph wrong in nearly
    # every clear case (das Dach, die Gebühr, die Trauer), so Wikidata wins, but
    # the label stays so the UI can show reduced confidence.
    return list(wd), "conflict", detail


def add_wikidata_only(out_paradigms, wd, matches):
    """Append Wikidata lexemes that no UniMorph paradigm accounts for.

    UniMorph misses core vocabulary (Euro, Kritik, Internet; see eval/), so
    Wikidata lexemes are added as single-source paradigms. For a lemma that
    UniMorph already has, an unmatched lexeme is added only if it brings a
    gender that lemma lacks (a missing homograph), never a near-copy of a
    paradigm we already show.
    """
    matched_ids = {lex["id"] for lex, _ in matches.values() if lex is not None}
    genders_by_lemma = defaultdict(set)
    plurals_by_lemma = defaultdict(set)
    for p in out_paradigms:
        genders_by_lemma[p["lemma"]].update(p["genders"])
        plurals_by_lemma[p["lemma"]].update(p["cells"].get("NOM.PL", []))
    added, skipped = defaultdict(int), defaultdict(int)
    seen = set()
    for lemma in sorted(wd):
        for lex in wd[lemma]:
            if lex["id"] in matched_ids:
                continue
            # Drop genders German does not have (one Dutch-tagged lexeme uses "common").
            genders = sorted(set(lex["genders"]) & {"MASC", "FEM", "NEUT"})
            cells = defaultdict(list)
            for c, n, f in sorted(lex["cells"]):
                cells[cell_name(c, n)].append(f)
            key = (lemma, tuple(genders), tuple(sorted((k, tuple(v)) for k, v in cells.items())))
            if key in seen:
                skipped["duplicate"] += 1
                continue
            seen.add(key)
            if lemma in genders_by_lemma:
                # A true missing homograph has its own gender *and* its own
                # plural (das Tag / Tags next to der Tag / Tage). Without a new
                # plural it is the same word UniMorph already shows.
                if set(genders) <= genders_by_lemma[lemma]:
                    skipped["same_gender"] += 1
                    continue
                if not nom_plurals(lex["cells"]) - plurals_by_lemma[lemma]:
                    skipped["no_new_plural"] += 1
                    continue
                added["new_gender"] += 1
            else:
                added["new_lemma"] += 1
            out_paradigms.append({
                "id": len(out_paradigms),
                "lemma": lemma,
                "genders": genders,
                "evidence": "wikidata_only" if genders else "unknown",
                "cells": dict(sorted(cells.items())),
            })
    return added, skipped


def build_index(out_paradigms):
    """surface form -> [[paradigm_id, [cells]]].

    Every paradigm is findable by its lemma. Some Wikidata lexemes have no
    forms, or an incomplete set without the nominative (Torr, Deut); their
    lemma is indexed with an empty cell list (case and number unknown)
    rather than a guessed NOM.SG."""
    index = defaultdict(list)
    for p in out_paradigms:
        by_form = defaultdict(list)
        for cell, forms in p["cells"].items():
            for f in forms:
                by_form[f].append(cell)
        by_form.setdefault(p["lemma"], [])
        for f, cs in by_form.items():
            index[f].append([p["id"], sorted(cs)])
    return index


def main():
    paradigms, dupes = load_paradigms(UNIMORPH)
    wd = load_wikidata(WIKIDATA)
    groups = defaultdict(list)
    for pid, p in enumerate(paradigms):
        groups[p.lemma].append(pid)
    siblings = {lemma: len(pids) for lemma, pids in groups.items()}
    matches = {}
    for lemma, pids in groups.items():
        for pid, m in zip(pids, match_lexemes([paradigms[i] for i in pids], wd.get(lemma, []))):
            matches[pid] = m

    out_paradigms = []
    report = []
    for pid, p in enumerate(paradigms):
        genders, evidence, detail = resolve_gender(p, siblings[p.lemma], matches[pid])
        out_paradigms.append({
            "id": pid,
            "lemma": p.lemma,
            "genders": genders,
            "evidence": evidence,
            "cells": {cell_name(c, n): forms for (c, n), forms in sorted(p.slots.items())},
        })
        if evidence in ("conflict", "wikidata"):
            out_paradigms[-1]["unimorph_genders"] = detail["um"]
        if evidence != "agree":
            report.append((p.lemma, pid, evidence, detail))

    added, skipped = add_wikidata_only(out_paradigms, wd, matches)
    index = build_index(out_paradigms)

    OUT.mkdir(exist_ok=True)
    with open(OUT / "lexicon.json", "w", encoding="utf-8") as fh:
        json.dump({"paradigms": out_paradigms, "index": dict(sorted(index.items()))},
                  fh, ensure_ascii=False, separators=(",", ":"))
    with open(OUT / "gender_report.tsv", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("lemma\tparadigm_id\tevidence\tunimorph\twikidata\twd_id\tmatch_score\tsiblings\n")
        for lemma, pid, evidence, d in sorted(report, key=lambda r: (r[2], r[0], r[1])):
            score = "" if d.get("score") is None else f"{d['score']:.2f}"
            fh.write(f"{lemma}\t{pid}\t{evidence}\t{'+'.join(d['um'])}\t{'+'.join(d.get('wd', []))}"
                     f"\t{d.get('wd_id', '')}\t{score}\t{siblings[lemma]}\n")

    counts = defaultdict(int)
    for p in out_paradigms:
        counts[p["evidence"]] += 1
    print(f"paradigms: {len(out_paradigms)} (UniMorph exact duplicates dropped: {dupes})")
    print(f"  Wikidata-only added: {added['new_lemma']} new lemmas, "
          f"{added['new_gender']} homographs with a gender UniMorph lacks")
    print(f"  Wikidata-only skipped: {skipped['duplicate']} duplicates, "
          f"{skipped['same_gender']} same-gender and {skipped['no_new_plural']} no-new-plural variants of UniMorph lemmas")
    print(f"surface forms: {len(index)}")
    for k in ("agree", "filled", "wikidata", "conflict", "unverified", "wikidata_only", "unknown"):
        print(f"  {k:<14}{counts[k]:>7}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
