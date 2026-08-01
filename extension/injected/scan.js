/*
 * Reading a page into typed observations.
 *
 * Scanning has no side effects. In particular it never opens a dropdown to see
 * what is inside: a control's options are read at the moment of choosing, from
 * the popup that control owns, so that no list of options can be assembled out
 * of unrelated things lying around the document.
 */

(function () {
  "use strict";

  const AP = (globalThis.ApplyPilot = globalThis.ApplyPilot || {});
  if (AP.scan) return;
  const D = AP.dom;
  const S = AP.surface;

  const REQUIRED_MARK = /[*]|\(\s*required\s*\)|\brequired\b/i;
  const OPTIONAL_MARK = /\(\s*optional\s*\)|\boptional\b/i;

  function frameId() {
    try {
      return window.top === window ? "top" : location.href;
    } catch (err) {
      return "frame";
    }
  }

  function controlKind(el) {
    const tag = (el.tagName || "").toLowerCase();
    if (tag === "textarea") return "textarea";
    if (tag === "select") return el.multiple ? "multiselect" : "select";
    if (tag !== "input") {
      // A widget the page drew itself. What it is comes from the role it
      // claims, because there is no element type to go on.
      const role = (el.getAttribute("role") || "").toLowerCase();
      if (role === "combobox") return "combobox";
      if (role === "checkbox" || role === "switch") return "checkbox";
      if (el.getAttribute("contenteditable") === "true") return "textarea";
      return "unknown";
    }
    const type = (el.getAttribute("type") || el.type || "text").toLowerCase();
    if (type === "checkbox") return "checkbox";
    if (type === "radio") return "radio";
    if (type === "file") return "file";
    if (type === "password") return "password";
    if (type === "email") return "email";
    if (type === "tel") return "tel";
    if (type === "number") return "number";
    if (type === "url") return "url";
    if (type === "date" || type === "month") return "date";
    if (D.isComboboxInput(el)) return "combobox";
    return "text";
  }

  function isRequired(el, rawLabel) {
    if (el.required) return true;
    if ((el.getAttribute("aria-required") || "").toLowerCase() === "true") return true;
    if (OPTIONAL_MARK.test(rawLabel || "")) return false;
    if (REQUIRED_MARK.test(rawLabel || "")) return true;
    const marked = D.closestDeep(el, "[class*='required' i],[data-required='true']");
    if (marked && !/not-required|non-required/i.test(marked.className || "")) return true;
    return false;
  }

  function commonAncestor(elements) {
    if (!elements.length) return null;
    let node = elements[0].parentElement;
    while (node) {
      if (elements.every((el) => node.contains(el))) return node;
      node = node.parentElement;
    }
    return document.body;
  }

  /**
   * The question a radio group asks.
   *
   * Never the label of one of its buttons: "Yes" is an option, not a question.
   */
  function groupLabel(elements) {
    const group = D.closestDeep(elements[0], "fieldset,[role='radiogroup'],[role='group']");
    if (group) {
      const legend = group.querySelector("legend");
      if (legend && D.textOf(legend)) return D.textOf(legend);
      const aria = (group.getAttribute("aria-label") || "").trim();
      if (aria) return aria;
      const ref = D.referencedText(group, "aria-labelledby");
      if (ref) return ref;
    }
    const container = commonAncestor(elements);
    if (!container) return "";
    let node = container;
    for (let depth = 0; depth < 4 && node; depth += 1) {
      let sibling = node.previousElementSibling;
      while (sibling) {
        const text = D.textOf(sibling);
        if (text && !sibling.querySelector("input,select,textarea") && text.length <= 300) {
          return text;
        }
        sibling = sibling.previousElementSibling;
      }
      node = node.parentElement;
    }
    return "";
  }

  function optionLabel(el) {
    return D.visibleLabel(el) || (el.getAttribute("value") || "").trim();
  }

  function fingerprintFor(parts) {
    return "f" + D.hash(parts.join(""));
  }

  function baseObservation(el, label, attrLabel, kind, options) {
    const block = D.repeatBlock(el);
    // Option labels identify a radio group, whose buttons are all present from
    // the start. They must not identify a dropdown: a form whose options load
    // only when touched changed identity the moment it was opened, and every
    // action on it afterwards reported the control as gone.
    const optionText = kind === "radio" ? (options || []).map((o) => o.label).join("|") : "";
    // The first entry of a repeating section carries no block marker, so its
    // identity does not change the moment a second entry is added beside it.
    const blockPart = block.index > 0 ? `${block.group}:${block.index}` : "";
    return {
      fingerprint: fingerprintFor([
        frameId(),
        D.normalise(label || attrLabel),
        kind,
        el.getAttribute("name") || "",
        optionText,
        blockPart,
      ]),
      frame: frameId(),
      label: label || "",
      attr_label: attrLabel || "",
      control: kind,
      name: el.getAttribute("name") || "",
      section: D.sectionOf(el),
      group: block.group,
      group_index: block.index,
      options: options || [],
      required: false,
      visible: true,
      disabled: Boolean(el.disabled),
      readonly: Boolean(el.readOnly),
      value: "",
      checked: null,
      max_length: el.maxLength && el.maxLength > 0 ? el.maxLength : null,
      accepts: el.getAttribute("accept") || "",
      // Reported so the service can write a date the shape this control asks
      // for. Never used as a label.
      placeholder: el.getAttribute("placeholder") || "",
      input_type: (el.getAttribute("type") || "").toLowerCase(),
      options_source: "none",
    };
  }

  function scanFields(root) {
    if (!root) return [];
    const controls = S.candidateControls(root);
    const fields = [];
    const consumed = new Set();

    /* Radio groups are one question with several answers. */
    const radios = controls.filter((el) => controlKind(el) === "radio");
    const byName = new Map();
    for (const el of radios) {
      const key = (el.getAttribute("name") || "") + "|" + D.repeatBlock(el).group;
      if (!byName.has(key)) byName.set(key, []);
      byName.get(key).push(el);
    }
    for (const group of byName.values()) {
      group.forEach((el) => consumed.add(el));
      const options = group.map((el) => ({
        label: optionLabel(el),
        value: el.getAttribute("value") || "",
        disabled: Boolean(el.disabled),
        selected: Boolean(el.checked),
      }));
      const rawLabel = groupLabel(group);
      const field = baseObservation(group[0], rawLabel, D.attributeLabel(group[0]), "radio", options);
      field.required = group.some((el) => isRequired(el, rawLabel));
      const picked = group.find((el) => el.checked);
      field.value = picked ? optionLabel(picked) : "";
      field.checked = Boolean(picked);
      field.options_source = "native";
      fields.push(field);
    }

    for (const el of controls) {
      if (consumed.has(el)) continue;
      const kind = controlKind(el);
      if (kind === "unknown") continue;

      const rawLabel = D.visibleLabel(el);
      const attrLabel = D.attributeLabel(el);
      let options = [];
      let optionsSource = "none";

      if (kind === "select" || kind === "multiselect") {
        options = Array.from(el.options || []).map((option) => ({
          label: (option.textContent || "").replace(/\s+/g, " ").trim(),
          value: option.value || "",
          disabled: Boolean(option.disabled),
          selected: Boolean(option.selected),
        }));
        optionsSource = "native";
      }

      const field = baseObservation(el, rawLabel, attrLabel, kind, options);
      field.options_source = optionsSource;
      field.required = isRequired(el, rawLabel);

      // What a control holds is read through the verifier, so the scanner and
      // the verifier can never disagree about whether a value is already there.
      // That agreement is what makes filling idempotent.
      if (kind === "password") {
        field.value = "";
      } else {
        const reading = AP.verify.observe(el, kind, null);
        field.value = reading.value;
        if (kind === "checkbox") field.checked = reading.value === "Yes";
      }

      fields.push(field);
    }

    return fields;
  }

  /**
   * Clues about which hiring system is serving this page.
   *
   * Some systems are served from the employer's own domain -- careers.<company>
   * .com is very common for large employers -- so the URL alone cannot identify
   * them and the page has to say. The service decides what these mean; this
   * only reports what is here.
   */
  function adapterHints() {
    const hints = [];
    for (const el of D.deepQuery("script[src],link[href]", document).slice(0, 200)) {
      const raw = el.getAttribute("src") || el.getAttribute("href") || "";
      try {
        hints.push(new URL(raw, location.href).hostname);
      } catch (err) {
        /* not a URL we can read */
      }
    }
    const markers = [
      ["[data-automation-id]", "workday"],
      ["[data-ph-at-id],[data-ph-id]", "phenom"],
      ["#grnhse_app,#grnhse_iframe", "greenhouse"],
      ["#icims_content,iframe[src*='icims']", "icims"],
      [".posting-page,.lever-application", "lever"],
      ["[class*='ashby' i],[data-testid*='ashby' i]", "ashby"],
      ["[data-sr-job-id],[class*='smartrecruiters' i]", "smartrecruiters"],
      ["[class*='whr-' i]", "workable"],
    ];
    for (const [selector, name] of markers) {
      if (D.deepQuery(selector, document).length) hints.push("marker:" + name);
    }
    return Array.from(new Set(hints)).slice(0, 40);
  }

  function pageSignature(kind, fields) {
    const parts = [location.href.split("#")[0], kind]
      .concat(fields.map((f) => f.fingerprint + ":" + (f.value ? "1" : "0")))
      .join("|");
    return D.hash(parts);
  }

  function scan() {
    const classification = S.classify();
    const kind = classification.kind;
    const root = S.scanRoot(kind);
    const fields = scanFields(root);
    const notes = classification.notes.slice();

    const onAPosting = kind === "listing" || kind === "application";
    const applyControls = onAPosting ? S.matchingControls(S.APPLY_TEXT) : [];
    if (!onAPosting && S.matchingControls(S.APPLY_TEXT).length) {
      // An apply control on a list of results belongs to some other job.
      notes.push("ignored an apply control: this page is a list, not a posting");
    }

    return {
      url: location.href,
      title: document.title || "",
      kind: kind,
      fields: fields,
      apply_controls: applyControls,
      submit_controls: kind === "application" ? S.matchingControls(S.SUBMIT_TEXT) : [],
      next_controls: kind === "application" ? S.matchingControls(S.NEXT_TEXT) : [],
      add_controls: kind === "application" ? S.matchingControls(S.ADD_TEXT) : [],
      captcha: S.captchaState(),
      hints: adapterHints(),
      signature: pageSignature(kind, fields),
      notes: notes,
    };
  }

  /**
   * The page's own confirmation that an application was received, if it says so.
   *
   * Returns "" when it does not. Nothing is ever recorded as submitted without
   * this: pressing a button is not evidence that anything arrived.
   */
  function confirmationText() {
    const body = document.body ? document.body.innerText || "" : "";
    const pattern = new RegExp(
      "[^.\\n]*(?:thank you for applying" +
        "|your application (?:has been |was )?(?:submitted|received)" +
        "|we (?:have )?received your application" +
        "|application (?:submitted|complete|received)" +
        "|thanks for applying)[^.\\n]*",
      "i"
    );
    const match = body.match(pattern);
    return match ? match[0].replace(/\s+/g, " ").trim().slice(0, 200) : "";
  }

  /** Find a control again by fingerprint. Never by position. */
  function findByFingerprint(fingerprint) {
    const classification = S.classify();
    const root = S.scanRoot(classification.kind) || document;
    const controls = S.candidateControls(root);
    for (const el of controls) {
      const kind = controlKind(el);
      if (kind === "radio") continue;
      const rawLabel = D.visibleLabel(el);
      let options = [];
      if (kind === "select" || kind === "multiselect") {
        options = Array.from(el.options || []).map((o) => ({
          label: (o.textContent || "").replace(/\s+/g, " ").trim(),
        }));
      }
      const candidate = baseObservation(el, rawLabel, D.attributeLabel(el), kind, options);
      if (candidate.fingerprint === fingerprint) return { element: el, kind: kind, group: null };
    }

    const radios = controls.filter((el) => controlKind(el) === "radio");
    const byName = new Map();
    for (const el of radios) {
      const key = (el.getAttribute("name") || "") + "|" + D.repeatBlock(el).group;
      if (!byName.has(key)) byName.set(key, []);
      byName.get(key).push(el);
    }
    for (const group of byName.values()) {
      const options = group.map((el) => ({ label: optionLabel(el) }));
      const candidate = baseObservation(group[0], groupLabel(group), D.attributeLabel(group[0]), "radio", options);
      if (candidate.fingerprint === fingerprint) {
        return { element: group[0], kind: "radio", group: group };
      }
    }
    return null;
  }

  AP.scan = {
    adapterHints,
    confirmationText,
    controlKind,
    findByFingerprint,
    groupLabel,
    isRequired,
    optionLabel,
    pageSignature,
    run: scan,
    scanFields,
  };
})();
