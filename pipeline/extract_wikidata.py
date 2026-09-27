"""Filter a Wikidata lexeme dump down to German nouns.

Reads the decompressed dump (one JSON entity per line) from stdin and writes
one compact JSON object per German noun lexeme to stdout. Usage:

    curl -s "$WIKIDATA_DUMP_URL" | bzcat | python pipeline/extract_wikidata.py > data/raw/wikidata-de-nouns.jsonl

We stream instead of storing the dump: it is ~475 MB compressed and covers
every language, but we keep only a few percent of it.
"""
import json
import sys

GERMAN = "Q188"
NOUN = "Q1084"
GRAMMATICAL_GENDER = "P5185"

# Only the features the pipeline needs; anything else is kept as a raw QID.
FEATURES = {
    "Q131105": "NOM", "Q146233": "GEN", "Q145599": "DAT", "Q146078": "ACC",
    "Q110786": "SG", "Q146786": "PL",
}
GENDERS = {"Q499327": "MASC", "Q1775415": "FEM", "Q1775461": "NEUT"}


def claim_ids(entity, prop):
    out = []
    for claim in entity.get("claims", {}).get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict) and "id" in value:
            out.append(value["id"])
    return out


def main():
    kept = 0
    for line in sys.stdin:
        # Cheap substring check first: json.loads on every lexeme in every
        # language dominates runtime otherwise.
        if GERMAN not in line or NOUN not in line:
            continue
        line = line.rstrip().rstrip(",")
        if not line.startswith("{"):
            continue
        entity = json.loads(line)
        if entity.get("language") != GERMAN or entity.get("lexicalCategory") != NOUN:
            continue
        lemma = entity.get("lemmas", {}).get("de", {}).get("value")
        if not lemma:
            continue
        genders = [GENDERS.get(q, q) for q in claim_ids(entity, GRAMMATICAL_GENDER)]
        forms = []
        for form in entity.get("forms", []):
            rep = form.get("representations", {}).get("de", {}).get("value")
            if rep:
                feats = [FEATURES.get(q, q) for q in form.get("grammaticalFeatures", [])]
                forms.append({"form": rep, "feats": feats})
        json.dump({"id": entity["id"], "lemma": lemma, "genders": genders, "forms": forms},
                  sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        kept += 1
    print(f"kept {kept} German noun lexemes", file=sys.stderr)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    main()
