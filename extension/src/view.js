// Lookup result -> what the bubble shows. Pure data, no DOM, so Node can test it.

const ARTICLES = {
  MASC: { NOM: "der", GEN: "des", DAT: "dem", ACC: "den" },
  FEM: { NOM: "die", GEN: "der", DAT: "der", ACC: "die" },
  NEUT: { NOM: "das", GEN: "des", DAT: "dem", ACC: "das" },
  PL: { NOM: "die", GEN: "der", DAT: "den", ACC: "die" },
};
const CASES = [["NOM", "nominative"], ["GEN", "genitive"], ["DAT", "dative"], ["ACC", "accusative"]];
const NUMBERS = [["SG", "singular"], ["PL", "plural"]];
const GENDER_NAMES = { MASC: "masculine", FEM: "feminine", NEUT: "neuter" };

const CERTAINTY = {
  agree: ["high", "2 sources agree"],
  filled: ["medium", "1 source (Wikidata)"],
  wikidata: ["medium", "1 source (Wikidata)"],
  wikidata_only: ["medium", "1 source (Wikidata)"],
  unverified: ["medium", "1 source (UniMorph)"],
  conflict: ["low", "Sources disagree"],
  unknown: ["low", "Gender unknown"],
};

const ERRORS = {
  "empty": "Select a word first.",
  "too-long": "The selection is too long. Select a single word.",
  "multi-word": "Select a single word.",
  "not-found": "is not in the dictionary. ArtikelFinder knows nouns only; names are not included.",
  "internal": "ArtikelFinder could not load its dictionary.",
};

/**
 * @typedef {{level: "high"|"medium"|"low", text: string}} Certainty
 * @typedef {{article: string, genders: string[], lemma: string, genderText: string, form: string, reading: string,
 *            plural: string|null, certainty: Certainty, notes: string[],
 *            table: {rows: [string, string, string][]} | null}} Entry
 * @typedef {{kind: "found", notes: string[], entries: Entry[]}
 *         | {kind: "error", message: string}} View
 */

/**
 * @param {import("./normalize.js").Found | import("./normalize.js").NotFound | {error: "internal"}} result
 * @returns {View}
 */
export function buildView(result) {
  if ("error" in result) {
    const message = result.error === "not-found" ? `“${result.query}” ${ERRORS["not-found"]}` : ERRORS[result.error];
    return { kind: "error", message };
  }
  const notes = [];
  if (result.caseChanged) notes.push(`Looked up as “${result.key}” (capitalization changed).`);
  if (result.ssAmbiguous) notes.push("Written in capitals: SS may stand for ß.");
  return { kind: "found", notes, entries: result.candidates.map((c) => buildEntry(c, result.key)) };
}

/** @param {import("./lexicon.js").Candidate} c */
function buildEntry(c, form) {
  const [level, text] = CERTAINTY[c.evidence];
  const notes = [];
  if (c.genders.length > 1) notes.push("Both articles are in use.");
  if (c.evidence === "conflict" && c.unimorphGenders?.length) {
    notes.push(`The other source says: ${articleOf(c.unimorphGenders)} ${c.lemma}.`);
  }
  const plural = c.cells["NOM.PL"];
  return {
    article: articleOf(c.genders),
    genders: c.genders,
    lemma: c.lemma,
    genderText: c.genders.length ? c.genders.map((g) => GENDER_NAMES[g]).join(" or ") : "gender unknown",
    form,
    reading: describeCells(c.surfaceCells),
    plural: plural ? `die ${plural.join(" / ")}` : Object.keys(c.cells).length ? "no plural listed" : null,
    certainty: { level, text },
    notes,
    table: buildTable(c),
  };
}

/** "der", "die", "das", "der/die", or "?" when the gender is unknown. */
export function articleOf(genders) {
  return genders.length ? genders.map((g) => ARTICLES[g].NOM).join("/") : "?";
}

/**
 * ["DAT.PL"] -> "dative plural"; all four cases of a number -> "all cases plural".
 * @param {string[]} cells
 */
export function describeCells(cells) {
  const parts = [];
  for (const [number, numberName] of NUMBERS) {
    const cases = CASES.filter(([c]) => cells.includes(`${c}.${number}`)).map(([, name]) => name);
    if (cases.length === CASES.length) parts.push(`all cases ${numberName}`);
    else if (cases.length) parts.push(`${cases.join(", ")} ${numberName}`);
  }
  return parts.length ? parts.join("; ") : "case and number not listed";
}

/** Rows [case, singular, plural]. Singular articles only when the gender is unambiguous. */
function buildTable(c) {
  if (!Object.keys(c.cells).length) return null;
  const singular = c.genders.length === 1 ? ARTICLES[c.genders[0]] : null;
  const cell = (key, articles) => {
    const forms = c.cells[`${key}`];
    if (!forms) return "—";
    const text = forms.join(" / ");
    return articles ? `${articles[key.slice(0, 3)]} ${text}` : text;
  };
  return {
    rows: CASES.map(([code, name]) => [
      name[0].toUpperCase() + name.slice(1),
      cell(`${code}.SG`, singular),
      cell(`${code}.PL`, ARTICLES.PL),
    ]),
  };
}
