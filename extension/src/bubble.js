// Injected into the page by background.js to draw the result bubble.
// Classic script (not a module), safe to inject repeatedly. Only draws a view
// built by view.js; all text goes in via textContent, never as HTML, because
// the dictionary data comes partly from Wikidata, which anyone can edit.
(() => {
  if (globalThis.__artikelFinder) return;

  const STYLE = `
    :host { all: initial; }
    .card {
      --bg: #ffffff; --fg: #1d1d1f; --muted: #5f6368; --line: #dadce0; --shade: rgba(0,0,0,.18);
      --masc: #1a56db; --fem: #c81e1e; --neut: #0e7a3b;
      --high: #0e7a3b; --medium: #8a5a00; --low: #c81e1e;
      box-sizing: border-box; width: max-content; min-width: 220px; max-width: min(340px, calc(100vw - 16px));
      max-height: min(420px, calc(100vh - 16px)); overflow: auto;
      background: var(--bg); color: var(--fg); border: 1px solid var(--line); border-radius: 10px;
      box-shadow: 0 6px 24px var(--shade); padding: 10px 12px 12px;
      font: 14px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; text-align: left;
    }
    @media (prefers-color-scheme: dark) {
      .card {
        --bg: #202124; --fg: #e8eaed; --muted: #9aa0a6; --line: #3c4043; --shade: rgba(0,0,0,.5);
        --masc: #8ab4f8; --fem: #f28b82; --neut: #81c995;
        --high: #81c995; --medium: #fdd663; --low: #f28b82;
      }
    }
    .top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .brand { font-size: 11px; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); }
    .close {
      all: unset; cursor: pointer; color: var(--muted); font-size: 18px; line-height: 1;
      padding: 2px 6px; border-radius: 6px;
    }
    .close:hover, .close:focus-visible { background: var(--line); color: var(--fg); }
    .note { color: var(--muted); font-size: 12px; margin: 4px 0 0; }
    .entry { margin-top: 8px; }
    .entry + .entry { border-top: 1px solid var(--line); padding-top: 8px; }
    .head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px; }
    .word { font-size: 18px; font-weight: 600; }
    .article { font-weight: 700; }
    .MASC { color: var(--masc); } .FEM { color: var(--fem); } .NEUT { color: var(--neut); }
    .badge { font-size: 11px; border: 1px solid currentColor; border-radius: 999px; padding: 0 6px; white-space: nowrap; }
    .high { color: var(--high); } .medium { color: var(--medium); } .low { color: var(--low); }
    .line { margin: 2px 0 0; }
    .muted { color: var(--muted); font-size: 13px; }
    details { margin-top: 6px; }
    summary { cursor: pointer; color: var(--muted); font-size: 13px; }
    table { border-collapse: collapse; margin-top: 4px; font-size: 13px; }
    th, td { text-align: left; padding: 2px 10px 2px 0; vertical-align: top; }
    th { color: var(--muted); font-weight: 500; }
    .error { margin: 6px 0 0; }
  `;

  const HOST_STYLE = {
    all: "initial", display: "block", position: "fixed", "z-index": "2147483647",
    top: "0", left: "0", width: "auto", height: "auto", margin: "0", padding: "0",
    border: "0", transform: "none", visibility: "hidden",
  };

  let current = null; // {host, cleanup}

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderEntry(e) {
    const box = el("div", "entry");
    const head = el("div", "head");
    const word = el("span", "word");
    const genderClass = e.genders.length === 1 ? e.genders[0] : ""; // colour only when unambiguous
    word.append(el("span", `article ${genderClass}`, e.article), ` ${e.lemma}`);
    head.append(word, el("span", `badge ${e.certainty.level}`, e.certainty.text));
    box.append(head);
    box.append(el("p", "line", `${e.form} = ${e.reading}`));
    const facts = [e.genderText];
    if (e.plural) facts.push(e.plural === "no plural listed" ? e.plural : `plural: ${e.plural}`);
    box.append(el("p", "line muted", facts.join(" · ")));
    for (const note of e.notes) box.append(el("p", "note", note));
    if (e.table) {
      const details = el("details");
      details.append(el("summary", "", "Declension"));
      const table = el("table");
      const headRow = el("tr");
      for (const h of ["", "Singular", "Plural"]) headRow.append(el("th", "", h));
      table.append(el("thead"), el("tbody"));
      table.tHead.append(headRow);
      for (const [caseName, sg, pl] of e.table.rows) {
        const row = el("tr");
        row.append(el("th", "", caseName), el("td", "", sg), el("td", "", pl));
        table.tBodies[0].append(row);
      }
      details.append(table);
      box.append(details);
    }
    return box;
  }

  function anchorRect(anchorToSelection) {
    if (!anchorToSelection) return null;
    const active = document.activeElement;
    if (active && (active.tagName === "TEXTAREA" || active.tagName === "INPUT")) {
      return active.getBoundingClientRect(); // selections in form fields have no range rect
    }
    const selection = getSelection();
    if (!selection || selection.rangeCount === 0) return null;
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    return rect.width || rect.height ? rect : null;
  }

  function place(host, card, rect) {
    const margin = 8;
    const { width, height } = card.getBoundingClientRect();
    let top;
    let left;
    if (rect) {
      top = rect.bottom + margin;
      if (top + height > innerHeight - margin && rect.top - height - margin >= margin) {
        top = rect.top - height - margin; // no room below: open above the word
      }
      left = rect.left;
    } else {
      top = margin * 2; // no usable selection position: top centre of the viewport
      left = (innerWidth - width) / 2;
    }
    host.style.setProperty("top", `${Math.max(margin, Math.min(top, innerHeight - height - margin))}px`, "important");
    host.style.setProperty("left", `${Math.max(margin, Math.min(left, innerWidth - width - margin))}px`, "important");
    host.style.setProperty("visibility", "visible", "important");
  }

  function close() {
    if (!current) return;
    current.cleanup();
    current.host.remove();
    current = null;
  }

  function show(view, options = {}) {
    close();
    // Own tag name, so page rules aimed at div/span do not match; inline !important
    // beats even !important rules in the page's stylesheets (e.g. "* {display: block !important}").
    const host = document.createElement("artikelfinder-bubble");
    for (const [prop, value] of Object.entries(HOST_STYLE)) host.style.setProperty(prop, value, "important");
    const root = host.attachShadow({ mode: "closed" });
    const style = el("style", "", STYLE);
    const card = el("div", "card");
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-label", "ArtikelFinder");

    const top = el("div", "top");
    const closeButton = el("button", "close", "×");
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", "Close");
    closeButton.addEventListener("click", close);
    top.append(el("span", "brand", "ArtikelFinder"), closeButton);
    card.append(top);

    if (view.kind === "error") {
      card.append(el("p", "error", view.message));
    } else {
      for (const note of view.notes) card.append(el("p", "note", note));
      for (const entry of view.entries) card.append(renderEntry(entry));
    }
    root.append(style, card);
    (document.body ?? document.documentElement).append(host);
    const reposition = () => place(host, card, anchorRect(options.anchorToSelection !== false));
    reposition();

    const inside = (event) => event.composedPath().includes(host);
    const onKey = (event) => { if (event.key === "Escape") close(); };
    const onPointer = (event) => { if (!inside(event)) close(); };
    const onScroll = (event) => { if (!inside(event)) close(); };
    addEventListener("keydown", onKey, true);
    addEventListener("pointerdown", onPointer, true);
    addEventListener("scroll", onScroll, { capture: true, passive: true });
    addEventListener("resize", reposition); // DevTools, rotation, zoom: follow, don't close
    current = {
      host,
      cleanup() {
        removeEventListener("keydown", onKey, true);
        removeEventListener("pointerdown", onPointer, true);
        removeEventListener("scroll", onScroll, { capture: true });
        removeEventListener("resize", reposition);
      },
    };
  }

  globalThis.__artikelFinder = { show, close };
})();
