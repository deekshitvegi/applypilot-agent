/*
 * Verification.
 *
 * "Verified" means a fresh read observed the requested value in state the page
 * itself owns. It never means a click was issued, and it never means the agent
 * read back something it wrote.
 *
 * The authoritative signals, in order of preference:
 *
 *   native checked / value      a real input's own property
 *   hidden backing input        the value the widget will actually submit
 *   ARIA checked / selected     set by the page, not by this agent
 *   aria-activedescendant       the option the page says is current
 *   page data-* state           the page's own state attribute
 *   page CSS state class        the page's own state class
 *   rendered value node         the widget's own display of its value
 *
 * A combobox's own text box is not on that list. Typing into it filters a list;
 * it is not a selection. Reading it back is how a rescan once reported
 * "verified" for an option the page had never accepted.
 */

(function () {
  "use strict";

  const AP = (globalThis.ApplyPilot = globalThis.ApplyPilot || {});
  if (AP.verify) return;
  const D = AP.dom;

  /* Controls the executor typed into purely to narrow a list, and the exact
   * text it put there.
   *
   * Whatever still reads back as that text came from this agent and can never
   * be evidence of anything. What the page has since replaced it with is a
   * different matter: a place picker handed "Denton, Texas" comes back holding
   * "Denton, Texas, United States", and nobody wrote that but the page. The
   * text is kept, rather than a bare mark, so the two can be told apart. */
  const typedAsFilter = new WeakMap();

  function echoOfOurOwnTyping(el) {
    if (!typedAsFilter.has(el)) return false;
    const typed = String(typedAsFilter.get(el) || "").trim().toLowerCase();
    const now = String(el.value || "").trim().toLowerCase();
    return !now || now === typed;
  }

  const PLACEHOLDER = /^(|-+|\.+|_+|no selection|none selected|nothing selected|not selected|select\b.*|please select.*|make a selection.*|select one.*|choose\b.*|pick one|--.*--|\(.*\)|click to select.*|type to search.*|start typing.*|please enter.*|enter \d+ or more.*|no results.*|no matches.*|loading.*|searching.*|search\.\.\.|n\/?a|tbd|optional|required)$/i;

  const STATE_CLASS = /(^|[\s_-])(is-)?(selected|checked|active|chosen|on)($|[\s_-])/i;
  const STATE_ATTRS = ["data-value", "data-selected", "data-state", "data-checked", "data-selected-value"];
  const VALUE_NODE =
    "[class*='singleValue' i],[class*='single-value' i],[class*='selectedValue' i]," +
    "[class*='selected-value' i],[class*='selected-option' i],[data-selected-value]";

  function isPlaceholder(text) {
    return PLACEHOLDER.test(D.normalise(text || ""));
  }

  /**
   * Whether two readings are the same answer.
   *
   * A form is entitled to restate what it was given. One writes a phone number
   * back as "+1 940 843 6087" after being handed "9408436087"; another lists
   * its states as "TX - Texas" and shows that once Texas is picked. In both the
   * value went in and was accepted, and in both the read-back was reported as a
   * failure -- four red crosses on a page that was correctly filled.
   *
   * This does not loosen what verified means. It is still a fresh read of state
   * the page owns, and the page still has to hold the answer that was asked
   * for. What it allows is the page's own way of writing it down.
   */
  function same(a, b) {
    const left = D.normalise(a || "");
    const right = D.normalise(b || "");
    if (!left || !right) return false;
    if (left === right) return true;

    const squash = (s) => s.replace(/[^a-z0-9]/g, "");
    if (squash(left) === squash(right)) return true;

    // A code in front of the name: "TX - Texas" is Texas, and "3 - 5 years" is
    // not 3, so only a whole part counts and never a fragment of one.
    if (partOf(left, right) || partOf(right, left)) return true;

    // A dialling code the form put on itself. Only for something long enough
    // to be a phone number, and only when the rest matches exactly.
    return sameNumber(squash(left), squash(right));
  }

  const SEPARATORS = /\s+[-–—:|/]\s+|\s*[()]\s*/;

  function partOf(whole, part) {
    if (!SEPARATORS.test(whole)) return false;
    // A word, not a number. "TX - Texas" is Texas, but "3 - 5 years" is a
    // range and 3 is one end of it, not the answer to anything.
    if (!/[a-z]{2}/.test(part)) return false;
    return whole
      .split(SEPARATORS)
      .map((piece) => piece.trim())
      .filter(Boolean)
      .some((piece) => piece === part);
  }

  function sameNumber(left, right) {
    if (!/^\d+$/.test(left) || !/^\d+$/.test(right)) return false;
    const [shorter, longer] = left.length <= right.length ? [left, right] : [right, left];
    // Long enough to be a whole number in its own right, with only a dialling
    // code in front of it. A form that shows back fewer digits than it was
    // given has dropped some, and that is not the same answer.
    if (shorter.length < 9) return false;
    if (longer.length - shorter.length > 4) return false;
    return longer.endsWith(shorter);
  }

  /**
   * The container a control lives in.
   *
   * The search starts at the parent rather than at the control: a control that
   * carries role="combobox" itself is the thing being asked about, and looking
   * inside it for its own backing input finds nothing.
   */
  function widgetOf(el) {
    if (!el) return null;
    const parent = el.parentElement || el;
    return D.closestDeep(parent, "[role='combobox'],[class*='select' i]") || parent;
  }

  /** The widget's own display of what is selected, if it has one. */
  function renderedValue(el) {
    const widget = widgetOf(el);
    if (!widget) return "";
    for (const node of D.deepQuery(VALUE_NODE, widget)) {
      if (!D.isVisible(node)) continue;
      const text = D.textOf(node);
      if (text && !isPlaceholder(text)) return text;
    }
    const tag = (el.tagName || "").toLowerCase();
    if (tag === "button" || el.getAttribute("role") === "combobox") {
      const text = D.textOf(el);
      if (text && !isPlaceholder(text)) return text;
    }
    return "";
  }

  /**
   * The control that will actually be submitted for this widget.
   *
   * Usually a hidden input, but a widget drawn over a real <select> keeps the
   * select itself, out of sight, holding the value. That select is the best
   * evidence there is -- it is what the employer receives.
   */
  function backingInput(el) {
    let scope = widgetOf(el);
    for (let up = 0; up < 3 && scope && scope.tagName !== "BODY"; up += 1) {
      const hidden = D.deepQuery("input[type='hidden']", scope).find((node) => node.value);
      if (hidden) return hidden;
      const shadowed = D.deepQuery("select", scope).find(
        (node) => node !== el && !D.isVisible(node) && node.value
      );
      if (shadowed) {
        const picked = Array.from(shadowed.selectedOptions || [])
          .map((option) => (option.textContent || "").trim())
          .filter((text) => text && !isPlaceholder(text));
        if (picked.length) return { value: picked.join(", "), _label: picked.join(", ") };
      }
      scope = scope.parentElement;
    }
    return null;
  }

  function selectedInOwnedPopup(el) {
    const popup = D.ownedPopup(el);
    if (!popup) return "";
    const chosen = D.optionRows(popup).find(
      (row) => row.getAttribute("aria-selected") === "true" || STATE_CLASS.test(row.className || "")
    );
    return chosen ? D.textOf(chosen) : "";
  }

  /**
   * Read one control's value from state the page owns.
   *
   * Returns the value and the name of the signal it came from, so a caller can
   * say honestly where its evidence is. A signal of "none" means there is
   * nothing authoritative to read and the applicant has to look.
   */
  function observe(el, kind, group) {
    if (!el) return { value: "", signal: "none" };
    const tag = (el.tagName || "").toLowerCase();

    // A choice drawn as buttons. What the page says is chosen: aria where the
    // page bothers to say, otherwise the one class the chosen button carries
    // that its siblings do not. Either way it is read from the page, never from
    // the fact that a button was clicked.
    // A "which of these" question: what is ticked, read from the boxes.
    if (kind === "ticklist" && group && group.length) {
      const ticked = group.filter((b) => b.checked).map((b) => AP.dom.visibleLabel(b));
      return { value: ticked.join(", "), signal: "native_checked" };
    }

    if (kind === "buttons" && group && group.length) {
      const picked = AP.dom.pickedButton(group);
      if (!picked) return { value: "", signal: "page_class_state" };
      const said = picked.getAttribute("aria-pressed") || picked.getAttribute("aria-checked");
      return {
        value: AP.dom.textOf(picked),
        signal: String(said).toLowerCase() === "true" ? "aria_state" : "page_class_state",
      };
    }

    if (kind === "radio" && group && group.length) {
      const picked = group.find((node) => node.checked);
      if (picked) return { value: AP.scan.optionLabel(picked), signal: "native_checked" };
      const ariaPicked = group.find(
        (node) => (node.getAttribute("aria-checked") || "") === "true"
      );
      if (ariaPicked) return { value: AP.scan.optionLabel(ariaPicked), signal: "aria_state" };
      return { value: "", signal: "native_checked" };
    }

    if (tag === "select") {
      const picked = Array.from(el.selectedOptions || [])
        .map((option) => (option.textContent || "").trim())
        .filter((text) => !isPlaceholder(text));
      return { value: picked.join(", "), signal: "native_select" };
    }

    if (tag === "input") {
      const type = (el.getAttribute("type") || el.type || "").toLowerCase();
      if (type === "checkbox" || type === "radio") {
        return { value: el.checked ? "Yes" : "No", signal: "native_checked" };
      }
      if (type === "file") {
        const files = el.files || [];
        return { value: files.length ? files[0].name : "", signal: "native_file_list" };
      }
    }

    // A box that is only a filter is not evidence -- unless the page has since
    // put something of its own in it. Choosing a suggestion is how a picker is
    // answered at all, and the widget writes the canonical wording back: that
    // reading is the page's, not ours. Every such fill was being reported
    // unverified while sitting correctly filled on screen.
    const stillOurs = echoOfOurOwnTyping(el);
    const filtering = stillOurs || (!typedAsFilter.has(el) && D.isComboboxInput(el));

    if (!filtering && (tag === "input" || tag === "textarea")) {
      return { value: el.value || "", signal: "native_value" };
    }

    /* Everything below is for a widget the page draws itself. */

    const hidden = backingInput(el);
    if (hidden) {
      const label = hidden._label || labelForBackingValue(el, hidden.value);
      return { value: label || hidden.value, signal: "hidden_backing_input" };
    }

    for (const attr of ["aria-checked", "aria-pressed", "aria-selected"]) {
      const value = el.getAttribute(attr);
      if (value === "true" || value === "false") {
        return { value: value === "true" ? "Yes" : "No", signal: "aria_state" };
      }
    }

    const active = el.getAttribute("aria-activedescendant");
    if (active) {
      const root = el.getRootNode ? el.getRootNode() : document;
      const option = root.getElementById ? root.getElementById(active) : null;
      if (option) return { value: D.textOf(option), signal: "aria_activedescendant" };
    }

    const inPopup = selectedInOwnedPopup(el);
    if (inPopup) return { value: inPopup, signal: "aria_selected_option" };

    for (const attr of STATE_ATTRS) {
      const value = el.getAttribute(attr);
      if (value && !isPlaceholder(value)) {
        const label = labelForBackingValue(el, value);
        return { value: label || value, signal: "page_data_state" };
      }
    }

    if (STATE_CLASS.test(el.className || "")) {
      const text = D.textOf(el);
      if (text && !isPlaceholder(text)) return { value: text, signal: "page_class_state" };
    }

    const rendered = renderedValue(el);
    // A widget that shows the field's own name in its value box is showing a
    // placeholder, not an answer. Reading "School / education institution" back
    // as the chosen school is exactly the kind of self-reported success this
    // whole module exists to prevent.
    if (rendered && !same(rendered, D.visibleLabel(el))) {
      return { value: rendered, signal: "rendered_value" };
    }

    if (filtering) {
      // There is a text box here, but what is in it came from this agent.
      return { value: "", signal: "none" };
    }

    return { value: "", signal: "none" };
  }

  /** Turn an option's submitted value back into the label a person reads. */
  function labelForBackingValue(el, value) {
    const widget = widgetOf(el);
    if (!widget || !value) return "";
    const match = D.deepQuery("[role='option'],option,li", widget).find(
      (row) =>
        row.getAttribute("value") === value ||
        row.getAttribute("data-value") === value ||
        row.id === value
    );
    return match ? D.textOf(match) : "";
  }

  /**
   * The verdict for one control.
   *
   * verified  the page's own state holds the value that was asked for
   * accepted  the page changed, but not to that value
   * failed    the page did not take it
   * attempted something was done and the page exposes nothing to check it by
   */
  function check(fingerprint, desired, previous) {
    const found = AP.scan.findByFingerprint(fingerprint);
    if (!found) {
      return {
        fingerprint: fingerprint,
        requested: desired || "",
        outcome: "failed",
        observed: "",
        signal: "none",
        evidence: "the control is no longer on the page",
      };
    }

    const reading = observe(found.element, found.kind, found.group);
    const label = D.visibleLabel(found.element) || AP.scan.groupLabel(found.group || [found.element]);
    const result = {
      fingerprint: fingerprint,
      label: label || "",
      requested: desired || "",
      observed: reading.value,
      signal: reading.signal,
      outcome: "attempted",
      evidence: "",
    };

    if (reading.signal === "none") {
      result.outcome = "attempted";
      result.evidence =
        "nothing this page owns reports the value of this control, so this is unverified";
      return result;
    }

    if (same(reading.value, desired)) {
      result.outcome = "verified";
      result.evidence = `read back from ${reading.signal}`;
      return result;
    }

    if (reading.value && !same(reading.value, previous || "")) {
      result.outcome = "accepted";
      result.evidence = `the page now holds "${reading.value}" (${reading.signal}), not "${desired}"`;
      return result;
    }

    result.outcome = "failed";
    result.evidence = reading.value
      ? `the page still holds "${reading.value}" (${reading.signal})`
      : `the page holds nothing for this control (${reading.signal})`;
    return result;
  }

  AP.verify = {
    check,
    isPlaceholder,
    markTypedAsFilter: (el, text) => typedAsFilter.set(el, text === undefined ? el.value : text),
    observe,
    renderedValue,
    same,
    typedAsFilter,
    widgetOf,
  };
})();
