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
  /*
   * One pass over the document is enough.
   *
   * Finding a control by fingerprint re-reads every control on the page, and
   * every read walked the document again and re-measured every ancestor. The
   * caches below live for one turn of the event loop -- long enough for a scan
   * or an action, short enough that nothing stale is ever acted on.
   */
  let documentElements = null;
  let cacheArmed = false;

  function armCache() {
    if (cacheArmed) return;
    cacheArmed = true;
    setTimeout(() => {
      documentElements = null;
      cacheArmed = false;
    }, 0);
  }

  function deepElements(root) {
    if (!root || root === document) {
      if (documentElements) return documentElements;
      const all = collectElements(document);
      documentElements = all;
      armCache();
      return all;
    }
    return collectElements(root);
  }

  function collectElements(root) {
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
    visit(root);
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

  // Visibility is deliberately not cached: a dropdown opens and closes within a
  // single turn, and a stale answer there is worse than a slow one.
  function isVisible(el) {
    if (el.hidden) return false;
    const style = getComputedStyle(el);
    if (!style) return false;
    const isFile = (el.tagName || "").toLowerCase() === "input" && (el.type || "") === "file";

    // A file input is routinely hidden outright and driven by a styled dropzone
    // beside it -- that is the whole pattern. It is still the control a document
    // gets attached to, and the attachment is verified from its own file list
    // afterwards, so being out of sight does not put it out of reach.
    if (style.display === "none" || style.visibility === "hidden") {
      if (!isFile) return false;
      const shown = ancestors(el)
        .slice(0, 5)
        .some((node) => {
          const box = node.getBoundingClientRect();
          return box.width > 1 && box.height > 1;
        });
      return shown;
    }

    // A checkbox, radio or file input is routinely drawn as a 1px transparent
    // control sitting behind a styled box. The box is what the applicant sees,
    // so that is what gets measured. What must not happen is calling such a
    // control visible outright: a wizard keeps every step in the document, and
    // treating all of their checkboxes and radios as on screen meant the panel
    // offered a veteran form and a login choice from steps that were not
    // showing, while the text fields on the step that was showing were
    // correctly judged hidden and left out.
    const tag = (el.tagName || "").toLowerCase();
    const type = (el.type || "").toLowerCase();
    const drawable = tag === "input" && (type === "checkbox" || type === "radio" || type === "file");
    const rect = el.getBoundingClientRect();

    if (!drawable) {
      if (Number(style.opacity) === 0) return false;
      if (rect.width <= 1 && rect.height <= 1) return false;
    } else if (rect.width <= 1 && rect.height <= 1) {
      const drawn = (el.labels && el.labels[0]) || el.parentElement;
      if (!drawn) return false;
      const box = drawn.getBoundingClientRect();
      if (box.width <= 1 && box.height <= 1) return false;
    }
    // Either way the ancestor checks below still apply, which is the point.
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

  /*
   * A widget's own furniture: the box showing what is selected, its placeholder,
   * its arrow, its menu.
   *
   * These sit right next to the control, so the search for a nearby label walks
   * straight into them. One picker renders the chosen school immediately before
   * its input, and that became the field's label -- which changed the control's
   * identity the moment anything was selected, so every later action reported it
   * as no longer on the page. The selection had worked; the control had simply
   * stopped being findable.
   */
  const WIDGET_CHROME =
    "[class*='singleValue' i],[class*='single-value' i],[class*='selectedValue' i]," +
    "[class*='selected-value' i],[class*='selected-option' i],[class*='placeholder' i]," +
    "[class*='indicator' i],[class*='arrow' i],[class*='caret' i],[class*='chevron' i]," +
    "[class*='clear' i],[role='listbox'],[role='option'],[role='presentation']," +
    "[class*='menu' i],[data-selected-value]";

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
      // A label belongs to a field's own row. Once the walk reaches a container
      // holding several controls it has left that row, and its neighbours are
      // other fields -- one EEO question labelled only with an asterisk took the
      // *previous* field's label and answered as that field instead.
      if (depth > 0 && visibleControlCount(node) >= 2) return "";
      let sibling = node.previousElementSibling;
      while (sibling) {
        if (sibling.matches("input,select,textarea,button")) {
          sibling = sibling.previousElementSibling;
          continue;
        }
        // A neighbour that holds a control of its own is another field's row,
        // not this field's name. One question labelled with a bare asterisk took
        // the label of the field above it and answered as that field.
        if (sibling.querySelector && sibling.querySelector("input,select,textarea")) {
          sibling = sibling.previousElementSibling;
          continue;
        }
        // The widget's own display of what is selected is not its name.
        if (sibling.matches(WIDGET_CHROME)) {
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

  /**
   * A weak, last-resort name derived from the control's own attributes.
   *
   * A name written in bracket notation puts the meaningful part last:
   * custom[eeo][race] is a question about race, and custom[education][0][school]
   * is a school. Reading the whole string matched nothing.
   */
  function lastBracketedSegment(name) {
    const parts = String(name || "").match(/\[([^\]]+)\]/g);
    if (!parts || !parts.length) return "";
    for (let i = parts.length - 1; i >= 0; i -= 1) {
      const inner = parts[i].slice(1, -1).trim();
      if (inner && !/^\d+$/.test(inner)) return inner;
    }
    return "";
  }

  function attributeLabel(el) {
    if (!el) return "";
    const candidates = [
      el.getAttribute("placeholder"),
      el.getAttribute("data-automation-id"),
      lastBracketedSegment(el.getAttribute("name")),
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
  /**
   * An index the page states outright.
   *
   * ``custom[education][1][school]`` is the second education whatever the
   * markup around it looks like. Believing the page when it says so is worth
   * more than any amount of reading its structure.
   */
  const NAME_INDEX = /\[(\d{1,3})\]|[._-](\d{1,3})(?=[._-])/g;

  function indexedName(el) {
    const name = el.getAttribute("name") || el.getAttribute("id") || "";
    if (!name) return null;
    let last = null;
    let match = null;
    NAME_INDEX.lastIndex = 0;
    while ((match = NAME_INDEX.exec(name))) {
      last = { index: Number(match[1] !== undefined ? match[1] : match[2]), at: match.index };
    }
    return last ? { index: last.index, group: name.slice(0, last.at) } : null;
  }

  /**
   * Which entry of a repeating block a control belongs to.
   *
   * The first entry of a list usually carries something the others do not --
   * "This is my most recent education" sits in the first block only. That made
   * the blocks structurally unalike, so no block ever had a twin, every entry
   * reported itself as the first one, and every entry was filled from the first
   * record on file. Two schools, both the same school, and a form that said it
   * had not added anything while entries piled up on screen.
   *
   * So: take the index the page states in the control's own name, and fall back
   * to structure only when it does not state one. Blocks that ask mostly the
   * same questions are repeats of each other -- an extra checkbox in one of them
   * does not make it a different kind of thing.
   */
  //: A repeating entry is a handful of questions. Anything holding more than
  //: this is a section of the page, and climbing past it to compare it against
  //: its siblings costs more than everything else in a scan put together --
  //: measured on a live application at 416ms per lookup, and a scan at seven
  //: and a half seconds.
  const BIGGEST_ENTRY = 24;

  /**
   * A choice drawn as a row of buttons.
   *
   * One widely used applicant tracking system renders every Yes/No question as
   * two bare <button> elements -- no role, no name, no value, not even an
   * aria-checked, only class names. Nothing about them says "control", so a
   * whole section of questions was invisible: not unanswered, never seen.
   *
   * What identifies one is the shape: a container whose children are all
   * buttons, two or more of them, each carrying a short label. Navigation is
   * excluded by name, because Back and Next sitting side by side is the same
   * shape and is not a question.
   */
  const NOT_A_CHOICE = /^(back|next|previous|continue|submit|save|cancel|close|apply|skip|add|remove|delete|edit|upload|browse)\b/i;

  function buttonChoices(root) {
    const groups = [];
    const seen = new Set();
    for (const button of deepQuery("button", root || document)) {
      const parent = button.parentElement;
      if (!parent || seen.has(parent)) continue;
      seen.add(parent);
      // A hidden input usually sits in the row beside the buttons, holding the
      // answer for the form to submit. It is part of the widget, not another
      // child to be counted -- requiring every child to be a button found
      // nothing at all on the live page.
      const children = Array.from(parent.children).filter((child) => isVisible(child));
      if (children.length < 2 || children.length > 12) continue;
      if (!children.every((child) => child.tagName === "BUTTON")) continue;
      const labels = children.map((child) => textOf(child));
      if (!labels.every((text) => text && text.length <= 40)) continue;
      if (labels.some((text) => NOT_A_CHOICE.test(text))) continue;
      if (children.some((child) => (child.getAttribute("type") || "") === "submit")) continue;
      if (!children.every(isVisible)) continue;
      groups.push({ container: parent, buttons: children });
    }
    return groups;
  }

  /**
   * Which button in the group is the chosen one.
   *
   * Said properly by aria where a page bothers, and otherwise by the one class
   * the chosen button carries that its siblings do not. Reading it back this
   * way is what makes the answer verifiable rather than merely clicked at.
   */
  function pickedButton(buttons) {
    for (const button of buttons) {
      const pressed = button.getAttribute("aria-pressed") || button.getAttribute("aria-checked");
      if (String(pressed).toLowerCase() === "true") return button;
    }
    const classes = buttons.map((b) => new Set(Array.from(b.classList || [])));
    let picked = null;
    for (let i = 0; i < buttons.length; i += 1) {
      const others = classes.filter((_, j) => j !== i);
      const extra = Array.from(classes[i]).some((c) => others.every((set) => !set.has(c)));
      if (!extra) continue;
      if (picked) return null; // more than one stands out: nothing is chosen
      picked = buttons[i];
    }
    return picked;
  }

  function repeatBlock(el) {
    const named = indexedName(el);
    // The page has stated the answer; there is nothing to work out.
    if (named) return { group: "n" + hash(named.group), index: named.index };

    let node = el.parentElement;
    while (node && node !== document.body) {
      const parent = node.parentElement;
      const controls = controlCount(node);
      if (controls > BIGGEST_ENTRY) break;
      if (parent && controls > 0) {
        const asks = blockAsks(node);
        const twins = Array.from(parent.children).filter((child) =>
          child === node ? true : alike(blockAsks(child), asks)
        );
        if (twins.length > 1) {
          return {
            group: named ? "n" + hash(named.group) : "g" + hash(asks.join(",")),
            index: named ? named.index : twins.indexOf(node),
          };
        }
      }
      node = parent;
    }
    return { group: "", index: 0 };
  }

  /**
   * What a block asks for, with any entry number taken out of the question.
   *
   * Remembered for as long as the document walk it belongs to: the same blocks
   * are asked about again for every sibling at every level, and recomputing
   * them each time was most of the cost of reading a page.
   */
  const asksCache = new WeakMap();

  function blockAsks(el) {
    if (!el || !el.tagName) return [];
    const remembered = asksCache.get(el);
    if (remembered) return remembered;
    const asks = deepQuery("input,select,textarea", el).map((c) => {
      const label = normalise(visibleLabel(c));
      if (label) return label;
      const name = c.getAttribute("name") || "";
      return name.replace(NAME_INDEX, "") || c.type || "";
    });
    asksCache.set(el, asks);
    return asks;
  }

  /**
   * Whether two blocks ask the same things.
   *
   * Not identically: the first entry of a list carries an extra checkbox, a
   * later one carries a remove button. Mostly the same is the same.
   */
  function alike(a, b) {
    if (!a.length || !b.length) return false;
    const theirs = new Set(b);
    const shared = a.filter((ask) => theirs.has(ask)).length;
    return shared >= Math.max(2, Math.min(a.length, b.length) * 0.6);
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

  /**
   * Controls a person can actually see.
   *
   * A widget's own hidden backing input is part of one field, not a second one,
   * so counting it made a picker's container look like a whole section and the
   * search for its label stopped before it started.
   */
  function visibleControlCount(el) {
    return deepQuery("input,select,textarea", el).filter(isVisible).length;
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

    // Some widgets hang their dropdown off <body> rather than keeping it inside
    // themselves, so looking within the control finds nothing at all. When this
    // control says it is open and there is exactly one open list on the page,
    // that list is this control's -- which is a long way from scraping every
    // option-shaped element in the document, because both halves must hold.
    const expanded =
      el.getAttribute("aria-expanded") === "true" ||
      Boolean(closestDeep(el, "[aria-expanded='true']"));
    if (expanded) {
      const open = deepQuery("[role='listbox'],[role='tree'],[role='grid']", document).filter(
        (node) => isVisible(node) && hasOptionRows(node)
      );
      if (open.length === 1) return open[0];
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
    WIDGET_CHROME,
    isDecoration,
    ancestors,
    attributeLabel,
    blockSignature,
    closestDeep,
    controlCount,
    visibleControlCount,
    deepElements,
    deepQuery,
    hash,
    isComboboxInput,
    lastBracketedSegment,
    isVisible,
    looksLikeQuestion,
    normalise,
    optionRows,
    ownedPopup,
    referencedText,
    buttonChoices,
    pickedButton,
    repeatBlock,
    sectionOf,
    splitIdentifier,
    textOf,
    visibleLabel,
  };
})();
