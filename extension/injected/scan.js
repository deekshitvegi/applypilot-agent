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

  /**
   * A required marker that lives in its own element beside the control.
   *
   * The asterisk is skipped when reading a label -- it is not the name of a
   * field -- but it is still the only thing saying the field is required, so it
   * is looked for separately.
   */
  function hasRequiredMarker(el) {
    let node = el;
    for (let depth = 0; depth < 2 && node; depth += 1) {
      const parent = node.parentElement;
      if (!parent) return false;
      for (const child of parent.children) {
        if (child === node || child.contains(el)) continue;
        if (child.querySelector("input,select,textarea")) continue;
        const text = D.textOf(child);
        // Short and decorative: a marker, not "* indicates a required field".
        if (text && text.length <= 20 && /[*]|\b(required|mandatory)\b/i.test(text)) return true;
      }
      node = parent;
    }
    return false;
  }

  //: What a form says when it wanted an answer and did not get one.
  //: Deliberately narrow. "Please Check the box below" is what a field is
  //: called; "Please select an option" is a form saying it did not get one, and
  //: reading the first as the second made every field on a step look required.
  const VALIDATION_TEXT = new RegExp(
    "(please (select|choose|make|pick)( an?| one)? (option|selection|answer|value|choice)" +
      "|please (enter|provide|supply) (a |an |your )?(value|answer|response)" +
      "|please answer this question" +
      "|this (field|question) is required" +
      "|required field" +
      "|cannot be (blank|empty)" +
      "|(field|question|answer|response|selection) is required" +
      "|must be (selected|answered|provided|completed)" +
      "|^required$" +
      "|^this field is required" +
      ")",
    "i"
  );

  /**
   * The page complaining that this control needs an answer.
   *
   * The strongest possible evidence that a field is required: the form itself
   * has just said so, in its own words, on screen. A step whose questions were
   * all read as optional was filled, continued, and rejected -- and nothing was
   * asked, because nothing knew anything was missing.
   */
  function hasValidationComplaint(el) {
    if ((el.getAttribute("aria-invalid") || "").toLowerCase() === "true") return true;
    const described =
      D.referencedText(el, "aria-errormessage") || D.referencedText(el, "aria-describedby");
    if (described && VALIDATION_TEXT.test(described)) return true;
    // Not by class name. A form is free to render its complaint as a plain red
    // span with no class worth the name, and one real application does exactly
    // that -- which is why a step showing "Please select an option" three times
    // still reported nothing as required. What identifies it is the wording and
    // where it sits: close to this control, and not wrapped around any control
    // of its own.
    // How far up counts: as far as this control's own question reaches, and not
    // one step further. A complaint under the next question along is that
    // question's business, and climbing blindly made every field on the step
    // look required because somewhere above them all, something was in red.
    const mine = el.getAttribute("name") || "";
    let box = el.parentElement;
    while (box && box !== document.body) {
      const strangers = Array.from(box.querySelectorAll("input,select,textarea")).some(
        (other) => other !== el && (other.getAttribute("name") || "") !== mine
      );
      if (strangers) break;
      const complained = Array.from(box.querySelectorAll("*")).some((node) => {
        if (node.contains(el)) return false;
        if (node.querySelector("input,select,textarea,button")) return false;
        const text = D.textOf(node);
        if (!text || text.length > 120 || !VALIDATION_TEXT.test(text)) return false;
        return D.isVisible(node);
      });
      if (complained) return true;
      box = box.parentElement;
    }
    return false;
  }

  function isRequired(el, rawLabel) {
    if (el.required) return true;
    if ((el.getAttribute("aria-required") || "").toLowerCase() === "true") return true;
    // Before the optional marker: a form that has just asked for this outranks
    // any label decoration saying it could be skipped.
    if (hasValidationComplaint(el)) return true;
    if (OPTIONAL_MARK.test(rawLabel || "")) return false;
    if (REQUIRED_MARK.test(rawLabel || "")) return true;
    const marked = D.closestDeep(el, "[class*='required' i],[data-required='true']");
    if (marked && !/not-required|non-required/i.test(marked.className || "")) return true;
    return hasRequiredMarker(el);
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
  /**
   * Where each fingerprint was last found.
   *
   * Looking a control up meant classifying the page and then building a full
   * observation for every control on it until one matched -- a whole scan, per
   * field, and twice per field once the read-back is counted. On a form of
   * thirty questions that was most of the time the fill took.
   *
   * A remembered element is never trusted on its own. Its fingerprint is worked
   * out again from the page as it is now, and only a control that still answers
   * to the same fingerprint is used; anything else falls through to the full
   * search. A fingerprint is what identity means here, so a stale entry cannot
   * turn into the wrong control -- it can only turn into a slower lookup.
   */
  const lastSeen = new Map();

  function stillTheSame(hit, fingerprint) {
    const el = hit.element;
    if (!el || !el.isConnected) return false;
    if (hit.group) {
      if (hit.group.some((one) => !one.isConnected)) return false;
      const options = hit.group.map((one) => ({ label: optionLabel(one) }));
      const again = baseObservation(
        hit.group[0], groupLabel(hit.group), D.attributeLabel(hit.group[0]), "radio", options
      );
      return again.fingerprint === fingerprint;
    }
    const kind = controlKind(el);
    if (kind !== hit.kind) return false;
    let options = [];
    if (kind === "select" || kind === "multiselect") {
      options = Array.from(el.options || []).map((o) => ({
        label: (o.textContent || "").replace(/\s+/g, " ").trim(),
      }));
    }
    const again = baseObservation(el, D.visibleLabel(el), D.attributeLabel(el), kind, options);
    return again.fingerprint === fingerprint;
  }

  function findByFingerprint(fingerprint) {
    const remembered = lastSeen.get(fingerprint);
    if (remembered) {
      if (stillTheSame(remembered, fingerprint)) return remembered;
      lastSeen.delete(fingerprint);
    }
    const hit = searchForFingerprint(fingerprint);
    if (hit) lastSeen.set(fingerprint, hit);
    return hit;
  }

  function searchForFingerprint(fingerprint) {
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
