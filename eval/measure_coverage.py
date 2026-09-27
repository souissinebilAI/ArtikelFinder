"""Measure how much of the nouns in real German text the lexicon knows.

    python eval/measure_coverage.py data/raw/deu_news_2023_100K/deu_news_2023_100K-sentences.txt

Input: a Leipzig Corpora Collection sentences file (`id \\t sentence`). Used for
evaluation only; never bundled or committed.

Noun detection relies on German capitalization: a capitalized token that does
not start a sentence is a noun or a proper name. Tokens split on hyphens,
because double-clicking "Gepäck-Verspätung" in a browser selects one part.
Misses are bucketed so the numbers say *what* is missing, not just how much.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEXICON = ROOT / "build/lexicon.json"
WIKIDATA = ROOT / "data/raw/wikidata-de-nouns.jsonl"

WORD = re.compile(r"[A-Za-zÄÖÜäöüß]+")
# A token right after one of these starts a new sentence or quote: capitalized for syntax.
BOUNDARY = re.compile(r"(?:^|[.!?:;\"„“»«)(\[\]–—]\s*)$")

# Weakest-link order: a token is only as certain as its least certain candidate.
EVIDENCE_RANK = {"agree": 0, "filled": 0, "wikidata": 0, "wikidata_only": 1, "conflict": 2,
                 "unverified": 3, "unknown": 4}
EVIDENCE_NAME = ["verified (2 sources / Wikidata)", "Wikidata only", "conflict (flagged)",
                 "UniMorph only", "no gender"]


def noun_candidates(sentence):
    for m in WORD.finditer(sentence):
        tok = m.group()
        if not tok[0].isupper() or tok.isupper() or len(tok) < 2:
            continue  # lowercase, acronym (CDU, USA) or single letter
        if BOUNDARY.search(sentence[:m.start()]):
            continue
        yield tok


def compound_head(tok, index):
    """Longest known right-hand element (>= 3 letters) of an unknown compound, or None."""
    for i in range(2, len(tok) - 2):
        head = tok[i].upper() + tok[i + 1:]
        if head in index:
            return head
    return None


def main(path):
    lex = json.loads(LEXICON.read_text(encoding="utf-8"))
    index, paradigms = lex["index"], lex["paradigms"]
    wd_forms = set()
    with open(WIKIDATA, encoding="utf-8") as fh:
        for line in fh:
            lexeme = json.loads(line)
            wd_forms.add(lexeme["lemma"])
            wd_forms.update(f["form"] for f in lexeme["forms"])

    counts = Counter()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            _, _, sentence = line.rstrip("\n").partition("\t")
            counts.update(noun_candidates(sentence))

    total = sum(counts.values())
    buckets = Counter()
    evidence = Counter()
    misses = Counter()
    for tok, n in counts.items():
        if tok in index:
            rank = max(EVIDENCE_RANK[paradigms[pid]["evidence"]] for pid, _ in index[tok])
            buckets["found"] += n
            evidence[rank] += n
        else:
            misses[tok] = n
            if tok in wd_forms:
                buckets["missing, Wikidata has it"] += n
            elif compound_head(tok, index):
                buckets["missing, compound head known"] += n
            else:
                buckets["missing, other (names etc.)"] += n

    print(f"{path}\n  capitalized non-initial tokens: {total:,} ({len(counts):,} distinct)")
    for k in ("found", "missing, Wikidata has it", "missing, compound head known",
              "missing, other (names etc.)"):
        print(f"  {k:<32}{buckets[k]:>9,}  {buckets[k] / total:6.1%}")
    print("  gender certainty of found tokens:")
    for rank, name in enumerate(EVIDENCE_NAME):
        print(f"    {name:<34}{evidence[rank]:>9,}  {evidence[rank] / buckets['found']:6.1%}")

    top = [t for t, _ in counts.most_common(5000)]
    known = sum(1 for t in top if t in index)
    print(f"  top-5000 distinct candidates found: {known / len(top):.1%}")

    out = ROOT / "build" / f"misses_{Path(path).stem}.tsv"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("token\tcount\tbucket\tcompound_head\n")
        for tok, n in misses.most_common():
            bucket = ("wikidata" if tok in wd_forms else
                      "compound" if compound_head(tok, index) else "other")
            fh.write(f"{tok}\t{n}\t{bucket}\t{compound_head(tok, index) or ''}\n")
    print(f"  misses written to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
