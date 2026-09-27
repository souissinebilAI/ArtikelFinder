// Runtime lexicon reader. Mirrors pipeline/runtime_format.py (the format spec and
// Python reference reader); extension/test/lexicon.test.js checks both agree.

export const FORMAT_VERSION = 1;

/**
 * FNV-1a over UTF-16 code units, the same numbers Python gets from utf-16-le.
 * @param {string} text
 * @returns {number} unsigned 32-bit hash
 */
export function fnv1a32(text) {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h = Math.imul(h ^ text.charCodeAt(i), 0x01000193) >>> 0;
  }
  return h;
}

/**
 * @typedef {Object} Candidate
 * @property {number} id
 * @property {string} lemma
 * @property {string[]} genders          subset of meta.genders, in der/die/das order
 * @property {string} evidence           one of meta.evidence
 * @property {Object<string, string[]>} cells   full paradigm, e.g. {"NOM.SG": ["Tisch"], ...}
 * @property {string[]} surfaceCells     cells the looked-up form fills; [] if unknown
 * @property {string[]} [unimorphGenders] the other source's gender, when it was overridden
 */

export class Lexicon {
  /**
   * @param {(relPath: string) => Promise<any>} loadJson  e.g. "i/143.json" -> parsed JSON
   * @param {{maxCachedShards?: number}} [options]
   */
  static async open(loadJson, options = {}) {
    const [meta, patterns] = await Promise.all([loadJson("meta.json"), loadJson("patterns.json")]);
    if (meta.format !== FORMAT_VERSION) {
      throw new Error(`unsupported lexicon format ${meta.format}, expected ${FORMAT_VERSION}`);
    }
    return new Lexicon(loadJson, meta, patterns, options.maxCachedShards ?? 16);
  }

  constructor(loadJson, meta, patterns, maxCachedShards) {
    this.loadJson = loadJson;
    this.meta = meta;
    this.patterns = patterns;
    this.maxCachedShards = maxCachedShards;
    /** @type {Map<string, Promise<any>>} insertion order = least recently used first */
    this.cache = new Map();
  }

  /**
   * Candidates for an exact surface form (caller NFC-normalizes); [] if unknown.
   * @param {string} surface
   * @returns {Promise<Candidate[]>}
   */
  async lookup(surface) {
    const index = await this.shard(`i/${fnv1a32(surface) % this.meta.indexShards}.json`);
    if (!Object.hasOwn(index, surface)) return [];
    const entry = index[surface];
    const ids = Array.isArray(entry) ? entry : [entry];
    return Promise.all(ids.map(async (id) => {
      const shard = await this.shard(`p/${Math.floor(id / this.meta.paradigmsPerShard)}.json`);
      const candidate = this.decode(shard[id % this.meta.paradigmsPerShard]);
      candidate.id = id;
      candidate.surfaceCells = Object.keys(candidate.cells)
        .filter((cell) => candidate.cells[cell].includes(surface));
      return candidate;
    }));
  }

  /** @returns {Candidate} without id / surfaceCells */
  decode([lemma, genderMask, evidence, patternId, overriddenMask]) {
    const cells = {};
    const pattern = this.patterns[patternId];
    pattern.forEach((entry, i) => {
      if (entry === 0) return;
      const codes = Array.isArray(entry) ? entry : [entry];
      cells[this.meta.cells[i]] = codes.map((code) => this.decodeForm(lemma, code));
    });
    const candidate = { lemma, genders: this.genders(genderMask), evidence: this.meta.evidence[evidence], cells };
    if (overriddenMask !== undefined) candidate.unimorphGenders = this.genders(overriddenMask);
    return candidate;
  }

  decodeForm(lemma, code) {
    const strip = this.meta.stripAlphabet.indexOf(code[0]);
    return lemma.slice(0, lemma.length - strip) + code.slice(1);
  }

  genders(mask) {
    return this.meta.genders.filter((_, i) => mask & (1 << i));
  }

  /** Loads a shard once; concurrent requests share the same promise. */
  shard(relPath) {
    let promise = this.cache.get(relPath);
    if (promise) {
      this.cache.delete(relPath); // re-insert below: now most recently used
    } else {
      promise = this.loadJson(relPath);
      promise.catch(() => this.cache.delete(relPath)); // do not cache failures
    }
    this.cache.set(relPath, promise);
    if (this.cache.size > this.maxCachedShards) {
      this.cache.delete(this.cache.keys().next().value);
    }
    return promise;
  }
}
