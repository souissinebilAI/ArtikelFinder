// Selected text -> lexicon keys to try, and the lookup that uses them.

const MAX_LENGTH = 100; // longest lemma is 67 characters
// Soft hyphen (sites insert it for line breaking), zero-width space/joiners, word joiner, BOM.
const INVISIBLE = /[\u00AD\u200B-\u200D\u2060\uFEFF]/g;
const EDGE_NON_WORD = /^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu;

/**
 * @typedef {{key: string, caseChanged: boolean}} LookupKey
 * @typedef {{query: string, keys: LookupKey[], ssAmbiguous: boolean}
 *         | {query: string, error: "empty" | "too-long"}} KeyPlan
 */

/**
 * Turn raw selected text into the keys to try, most faithful first.
 * Case is only adjusted for all-lower or all-upper input. "STRASSE" is not
 * mapped to "Straße" because SS may be ß (Maße) or ss (Masse); instead
 * ssAmbiguous tells the UI to say so (STRASSE really does find der Strass).
 * @param {string} selection
 * @returns {KeyPlan}
 */
export function lookupKeys(selection) {
  const query = selection
    .normalize("NFC")
    .replace(INVISIBLE, "")
    .replace(/\s+/g, " ")
    .replace(EDGE_NON_WORD, "");
  if (!query) return { query, error: "empty" };
  if (query.length > MAX_LENGTH) return { query, error: "too-long" };

  const keys = [{ key: query, caseChanged: false }];
  const lower = query.toLowerCase();
  const upper = query.toUpperCase();
  if (query === lower && query !== upper) {
    keys.push({ key: query[0].toUpperCase() + query.slice(1), caseChanged: true });
  } else if (query === upper && query !== lower && query.length > 1) {
    keys.push({ key: query[0] + query.slice(1).toLowerCase(), caseChanged: true });
  }
  return {
    query,
    keys: keys.filter((k, i) => keys.findIndex((o) => o.key === k.key) === i),
    ssAmbiguous: query === upper && query.includes("SS"),
  };
}

/**
 * @typedef {{query: string, key: string, caseChanged: boolean, ssAmbiguous: boolean,
 *            candidates: import("./lexicon.js").Candidate[]}} Found
 * @typedef {{query: string, error: "empty" | "too-long" | "multi-word" | "not-found"}} NotFound
 */

/**
 * Look up a selection: first key with candidates wins.
 * @param {import("./lexicon.js").Lexicon} lexicon
 * @param {string} selection
 * @returns {Promise<Found | NotFound>}
 */
export async function resolveSelection(lexicon, selection) {
  const plan = lookupKeys(selection);
  if ("error" in plan) return plan;
  for (const { key, caseChanged } of plan.keys) {
    const candidates = await lexicon.lookup(key);
    if (candidates.length) return { query: plan.query, key, caseChanged, ssAmbiguous: plan.ssAmbiguous, candidates };
  }
  // A few multi-word nouns exist (Pommes frites), so those were tried above;
  // otherwise tell the user what went wrong instead of a bare "not found".
  return { query: plan.query, error: plan.query.includes(" ") ? "multi-word" : "not-found" };
}
