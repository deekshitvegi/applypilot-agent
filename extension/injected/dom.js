/*
 * Shared page primitives for every injected function.
 *
 * These run in the extension's isolated world in Chrome and are loaded
 * unchanged by the browser tests, so what the tests drive is what ships.
 *
 * Two things here matter more than the rest:
 *
 *   - traversal pierces shadow roots, because a sign-in form living inside a
 *     shadow root was mistaken for an application form when it was invisible to
 *     a plain querySelectorAll;
 *   - a control is identified by what it is (frame, label, kind, options,
 *     name, repeat block) and never by its position in the DOM, because a page
 *     that re-renders moves every index.
 */

(function () {
  "use strict";

  const AP = (globalThis.ApplyPilot = globalThis.ApplyPilot || {});
  if (AP.dom) return;

  const MAX_ELEMENTS = 20000;

  /* ---------------------------------------------------------------- text */

  const INTERROGATIVE = new Set([
    "do", "does", "did", "are", "is", "was", "were", "have", "has", "had",
    "will", "would", "can", "could", "may", "might", "should", "must",
    "what", "which", "why", "how", "when", "where", "who", "please", "tell",
  ]);

  // Must agree with normalise() in src/applypilot/text.py: learned answers are
  // keyed by this on both sides. tests/test_normalisation_parity.py checks it.
  function normalise(text) {
    if (!text) return "";
    let out = String(text).normalize("NFKD").replace(/[̀-ͯ]/g, "");
    out = out.replace(/[‘’]/g, "'").replace(/[‐-―]/g, "-");
    out = out.toLowerCase();
    out = out.replace(
      /(\(\s*(required|optional|opt|mandatory)\s*\)|\brequired\b|\boptional\b|[*†‡•]|\bmust\s+be\s+filled\b)/g,
      " "
    );
    out = out.replace(/&/g, " and ");
    out = out.replace(/\s+/g, " ").trim();
    return out.replace(/^[\s:*\-.,?!]+|[\s:*\-.,?!]+$/g, "");
  }

  function looksLikeQuestion(text) {
    if (!text) return false;
    if (String(text).includes("?")) return true;
    const first = normalise(text).split(" ")[0];
    return INTERROGATIVE.has(first);
  }

  function hash(text) {
    let h = 0x811c9dc5;
    const s = String(text);
    for (let i = 0; i < s.length; i += 1) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h.toString(36);
  }

  /* ----------------------------------------------------------- traversal */

  /**
   * Every element under *root*, in the order they appear on the page, stepping
   * into shadow roots as it goes.
   *
   * Document order is not a nicety: the options of a Yes/No group come back in
   * the order the applicant sees them, and a list of fields reads top to bottom.
   */
  function deepElements(root) {
    const out = [];
    const visit = (node) => {
      const kids = node && node.children ? node.children : [];
      for (const el of kids) {
        if (out.length >= MAX_ELEMENTS) return;
        out.push(el);
        if (el.shadowRoot) visit(el.shadowRoot);
        visit(el);
      }
    };
    visit(root || document);
    return out;
  }

  function deepQuery(selector, root) {
    return deepElements(root).filter((el) => {
      try {
        return el.matches(selector);
      } catch (err) {
        return false;
      }
    });
  }

  /** The chain of ancestors, stepping out of shadow roots as it goes. */
  function ancestors(el) {
    const out = [];
    let node = el;
    while (node) {
      node = node.parentElement || (node.parentNode && node.parentNode.host) || null;
      if (node) out.push(node);
    }
    return out;
  }

  function closestDeep(el, selector) {
    for (const node of [el].concat(ancestors(el))) {
      try {
        if (node.matches && node.matches(selector)) return node;
      } catch (err) {
        /* selector unsupported here */
      }
    }
    return null;
  }

  /* ---------------------------------------------------------- visibility */

  function isVisible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    if (el.hidden) return false;
    const style = getComputedStyle(el);
    if (!style) return false;
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (Number(style.opacity) === 0) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 1 && rect.height <= 1) {
      // A styled checkbox is often a 1px input behind a drawn box; the drawn
      // box is what the applicant sees, so treat it as visible.
      const tag = (el.tagName || "").toLowerCase();
      const type = (el.type || "").toLowerCase();
      if (tag === "input" && (type === "checkbox" || type === "radio" || type === "file")) {
        return Boolean(el.offsetParent) || style.position === "fixed" || true;
      }
      return false;
    }
    for (const node of ancestors(el)) {
      const s = getComputedStyle(node);
      if (!s) continue;
      if (s.display === "none" || s.visibility === "hidden") return false;
      if (node.getAttribute && node.getAttribute("aria-hidden") === "true") return false;
    }
    return true;
  }

  function textOf(el) {
    if (!el) return "";
    const text = el.innerText || el.textContent || "";
    return text.replace(/\s+/g, " ").trim();
  }

  /* --------------------------------------------------------------- labels */

  const LABEL_HINT = "label,[class*='label' i],[class*='Label'],[data-automation-id*='label' i]";

  /* Chrome around a form. Never the name of anything inside it. */
  const NAVIGATIONAL =
    "nav,header,footer,[role='tablist'],[role='tab'],[role='navigation'],[role='menu'],[role='menubar']";

  /*
   * A required marker is not a field name.
   *
   * Forms often put the asterisk in its own element between the name and the
   * control, which makes it the nearest thing before the input. A whole
   * application came back with every field labelled "*", nothing matched any
   * saved answer, and the panel reported there was nothing it could fill.
   */
  const DECORATION_ONLY =
    /^[\s*†‡•()[\]{}:;.,\-–—_|]*(required|optional|mandatory|req)?[\s*†‡•()[\]{}:;.,\-–—_|]*$/i;

  function isDecoration(text) {
    return !text || DECORATION_ONLY.test(String(text).trim());
  }

  function referencedText(el, attribute) {
    const ids = (el.getAttribute(attribute) || "").split(/\s+/).filter(Boolean);
    if (!ids.length) return "";
    const root = el.getRootNode ? el.getRootNode() : document;
    const parts = [];
    for (const id of ids) {
      const target = root.getElementById ? root.getElementById(id) : document.getElementById(id);
      if (target && target !== el) parts.push(textOf(target));
    }
    return parts.filter(Boolean).join(" ").trim();
  }

  /**
   * The label the applicant can actually read.
   *
   * Deliberately excludes name, id and placeholder: a form that calls its State
   * control `countryRegion` must not be able to argue it is a country field.
   */
  function visibleLabel(el) {
    if (!el) return "";

    // Every strategy below skips text that is only a required marker: an
    // asterisk is decoration, not the name of a field.
    if (el.labels && el.labels.length) {
      for (const label of el.labels) {
        const text = textOf(label);
        if (!isDecoration(text)) return text;
      }
    }

    const byRef = referencedText(el, "aria-labelledby");
    if (!isDecoration(byRef)) return byRef;

    const wrapping = closestDeep(el, "label");
    if (wrapping) {
      const clone = wrapping.cloneNode(true);
      clone.querySelectorAll("input,select,textarea,button").forEach((n) => n.remove());
      const text = textOf(clone);
      if (!isDecoration(text)) return text;
    }

    const aria = (el.getAttribute("aria-label") || "").trim();
    if (!isDecoration(aria)) return aria;

    // A label sitting just before the control inside the same field row: the
    // common shape when a form does not use <label for>. The walk stops as soon
    // as it meets navigation, because a tab bar several levels up is not a
    // label -- one was read as the name of a file input.
    let node = el;
    for (let depth = 0; depth < 3 && node; depth += 1) {
      let sibling = node.previousElementSibling;
      while (sibling) {
        if (sibling.matches("input,select,textarea,button")) {
          sibling = sibling.previousElementSibling;
          continue;
        }
        if (sibling.matches(NAVIGATIONAL) || sibling.querySelector("a[href]")) return "";
        const hint = sibling.matches(LABEL_HINT) ? sibling : sibling.querySelector(LABEL_HINT);
        const text = textOf(hint || sibling);
        // A lone asterisk between the name and the control is skipped over,
        // not taken as the name.
        if (text && !isDecoration(text)) return text.length <= 200 ? text : "";
        sibling = sibling.previousElementSibling;
      }
      node = node.parentElement;
    }

    const group = closestDeep(el, "fieldset,[role='group'],[role='radiogroup']");
    if (group) {
      const legend = group.querySelector("legend");
      if (legend) {
        const text = textOf(legend);
        if (text) return text;
      }
      const groupAria = (group.getAttribute("aria-label") || "").trim();
      if (groupAria) return groupAria;
      const groupRef = referencedText(group, "aria-labelledby");
      if (groupRef) return groupRef;
    }

    return "";
  }

  function splitIdentifier(text) {
    return String(text || "")
      .replace(/[[\]()<>{}]+/g, " ")
      .replace(/[_\-.]+/g, " ")
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .replace(/\s+/g, " ")
      .trim();
  }

  /** A weak, last-resort name derived from the control's own attributes. */
  function attributeLabel(el) {
    if (!el) return "";
    const candidates = [
      el.getAttribute("placeholder"),
      el.getAttribute("data-automation-id"),
      el.getAttribute("name"),
      el.getAttribute("id"),
    ];
    for (const candidate of candidates) {
      const text = splitIdentifier(candidate);
      if (text && /[a-z]/i.test(text) && text.length <= 80) return text;
    }
    return "";
  }

  /**
   * The nearest heading above the control, used to scope history fields.
   *
   * Bounded to a few levels on purpose. A heading far enough up the page to be
   * about something else can put a field in the wrong section, and the section
   * is what decides whether an employment record may answer a label.
   */
  function sectionOf(el) {
    const group = closestDeep(el, "fieldset,[role='group']");
    if (group) {
      const legend = group.querySelector("legend");
      if (legend && textOf(legend)) return textOf(legend);
    }
    let node = el;
    let depth = 0;
    while (node && depth < 5) {
      depth += 1;
      // A form is not obliged to use a heading tag. Plenty style "Education"
      // and "Work experience" as ordinary coloured divs, and reading only
      // <h1>-<h5> found no section at all -- which blocked every education and
      // employment field from resolving, on a page that had the answers.
      //
      // A plain block only counts as a heading once we have walked up to a
      // container holding several fields. Below that, the short text sitting
      // before a control is that control's own label.
      const multiField = controlCount(node) >= 2;
      let sibling = node.previousElementSibling;
      while (sibling) {
        if (sibling.matches("h1,h2,h3,h4,h5,legend,[role='heading']")) {
          const text = textOf(sibling);
          if (text) return text;
        }
        const nested = sibling.querySelector && sibling.querySelector("h1,h2,h3,h4,h5,legend");
        if (nested && !sibling.querySelector("input,select,textarea")) {
          const text = textOf(nested);
          if (text) return text;
        }
        if (multiField && !sibling.querySelector("input,select,textarea,button")) {
          const text = textOf(sibling);
          if (text && text.length <= 60 && /[a-z]/i.test(text) && !isDecoration(text)) {
            return text;
          }
        }
        sibling = sibling.previousElementSibling;
      }
      node = node.parentElement;
    }
    return "";
  }

  /**
   * Repeat blocks: "Education 1", "Education 2".
   *
   * Found by structure rather than by name -- the block is the nearest ancestor
   * that has sibling blocks built the same way and holds form controls of its
   * own. Which entry it is comes from its position among those siblings, so
   * adding an entry does not renumber the ones already filled.
   */
  function repeatBlock(el) {
    let node = el.parentElement;
    while (node && node !== document.body) {
      const parent = node.parentElement;
      if (parent) {
        const signature = blockSignature(node);
        const twins = Array.from(parent.children).filter(
          (child) => blockSignature(child) === signature
        );
        if (twins.length > 1 && controlCount(node) > 0) {
          return { group: "g" + hash(signature), index: twins.indexOf(node) };
        }
      }
      node = parent;
    }
    return { group: "", index: 0 };
  }

  /**
   * What a block is made of, judged by the questions inside it.
   *
   * Two employment entries ask the same things and are repeats of each other.
   * An education block and an employment block can be built from the same tags
   * and the same classes and are not repeats of anything -- what separates them
   * is what they ask for.
   */
  function blockSignature(el) {
    if (!el || !el.tagName) return "";
    const classes = Array.from(el.classList || [])
      .filter((c) => !/\d/.test(c))
      .sort()
      .join(".");
    const asks = deepQuery("input,select,textarea", el)
      .map((c) => normalise(visibleLabel(c)) || c.getAttribute("name") || c.type || "")
      .join(",");
    return `${el.tagName}|${classes}|${asks}`;
  }

  function controlCount(el) {
    return deepQuery("input,select,textarea", el).length;
  }

  /* ---------------------------------------------------------- combo boxes */

  /**
   * True when a text input is a widget's own filter box.
   *
   * What gets typed here narrows a list; it is not a selection. Reading it back
   * as proof of a selection is how a rescan once "verified" a value the page
   * had never accepted.
   */
  function isComboboxInput(el) {
    if (!el || (el.tagName || "").toLowerCase() !== "input") return false;
    const role = (el.getAttribute("role") || "").toLowerCase();
    if (role === "combobox" || role === "searchbox") return true;
    if (el.hasAttribute("aria-autocomplete")) return true;
    if (el.hasAttribute("aria-expanded")) return true;
    if (el.hasAttribute("aria-activedescendant")) return true;
    const controls = el.getAttribute("aria-controls") || el.getAttribute("aria-owns");
    if (controls) {
      const root = el.getRootNode ? el.getRootNode() : document;
      const target = root.getElementById ? root.getElementById(controls.split(/\s+/)[0]) : null;
      if (target && (target.getAttribute("role") || "").toLowerCase() === "listbox") return true;
    }
    const host = closestDeep(el, "[role='combobox'],[class*='select__' i],[class*='-select' i]");
    return Boolean(host && host !== el);
  }

  /**
   * The popup a control owns, or null.
   *
   * Only a list the control points at, or one inside the control's own widget,
   * counts. Scraping every option-shaped element in the document once produced
   * 27 "options" made of a salary chip, unrelated buttons and an EEO race list.
   */
  function ownedPopup(el) {
    if (!el) return null;
    const root = el.getRootNode ? el.getRootNode() : document;
    const byId = (id) => (root.getElementById ? root.getElementById(id) : null);

    for (const attr of ["aria-controls", "aria-owns"]) {
      const ids = (el.getAttribute(attr) || "").split(/\s+/).filter(Boolean);
      for (const id of ids) {
        const target = byId(id);
        if (target && isVisible(target) && hasOptionRows(target)) return target;
      }
    }

    const active = el.getAttribute("aria-activedescendant");
    if (active) {
      const option = byId(active);
      const list = option && closestDeep(option, "[role='listbox'],ul,[class*='menu' i]");
      if (list && isVisible(list)) return list;
    }

    const widget = closestDeep(el, "[role='combobox']") || el.parentElement;
    for (const container of [widget, widget && widget.parentElement]) {
      if (!container) continue;
      const list = deepQuery("[role='listbox'],[role='menu'],[class*='menu' i]", container).find(
        (node) => isVisible(node) && hasOptionRows(node)
      );
      if (list) return list;
    }
    return null;
  }

  function hasOptionRows(container) {
    return optionRows(container).length > 0;
  }

  function optionRows(container) {
    if (!container) return [];
    let rows = deepQuery("[role='option']", container);
    if (!rows.length) rows = deepQuery("li", container);
    if (!rows.length) rows = deepQuery("[class*='option' i]", container);
    return rows.filter((row) => isVisible(row) && textOf(row));
  }

  /* ----------------------------------------------------------- exporting */

  AP.dom = {
    MAX_ELEMENTS,
    isDecoration,
    ancestors,
    attributeLabel,
    blockSignature,
    closestDeep,
    controlCount,
    deepElements,
    deepQuery,
    hash,
    isComboboxInput,
    isVisible,
    looksLikeQuestion,
    normalise,
    optionRows,
    ownedPopup,
    referencedText,
    repeatBlock,
    sectionOf,
    splitIdentifier,
    textOf,
    visibleLabel,
  };
})();
