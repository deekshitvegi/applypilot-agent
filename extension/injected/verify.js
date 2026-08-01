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

  /* Controls the executor typed into purely to narrow a list. Whatever is in
   * them came from this agent, so it can never be evidence of anything. */
  const typedAsFilter = new WeakSet();

  const PLACEHOLDER = /^(|-+|\.+|_+|no selection|none selected|nothing selected|not selected|select\b.*|please select.*|choose\b.*|pick one|--.*--|\(.*\)|click to select.*|type to search.*|start typing.*|please enter.*|enter \d+ or more.*|no results.*|no matches.*|loading.*|searching.*|search\.\.\.|n\/?a|tbd|optional|required)$/i;

  const STATE_CLASS = /(^|[\s_-])(is-)?(selected|checked|active|chosen|on)($|[\s_-])/i;
  const STATE_ATTRS = ["data-value", "data-selected", "data-state", "data-checked", "data-selected-value"];
  const VALUE_NODE =
    "[class*='singleValue' i],[class*='single-value' i],[class*='selectedValue' i]," +
    "[class*='selected-value' i],[class*='selected-option' i],[data-selected-value]";

  function isPlaceholder(text) {
    return PLACEHOLDER.test(D.normalise(text || ""));
  }

  function same(a, b) {
    const left = D.normalise(a || "");
    const right = D.normalise(b || "");
    if (!left || !right) return false;
    if (left === right) return true;
    const squash = (s) => s.replace(/[^a-z0-9]/g, "");
    return squash(left) === squash(right);
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

  function backingInput(el) {
    const widget = widgetOf(el);
    if (!widget) return null;
    const hidden = D.deepQuery("input[type='hidden']", widget).find((node) => node.value);
    return hidden || null;
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

    const filtering = typedAsFilter.has(el) || D.isComboboxInput(el);

    if (!filtering && (tag === "input" || tag === "textarea")) {
      return { value: el.value || "", signal: "native_value" };
    }

    /* Everything below is for a widget the page draws itself. */

    const hidden = backingInput(el);
    if (hidden) {
      const label = labelForBackingValue(el, hidden.value);
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
    markTypedAsFilter: (el) => typedAsFilter.add(el),
    observe,
    renderedValue,
    same,
    typedAsFilter,
    widgetOf,
  };
})();
