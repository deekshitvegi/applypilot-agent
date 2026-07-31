/*
 * Doing things to a page.
 *
 * Three rules run through all of it:
 *
 *   Idempotent. If the target already holds the value, nothing is clicked. A
 *   page that rebuilds its address block when the country changes has to be
 *   re-filled, and a retry that toggles what it already set destroys its own
 *   work.
 *
 *   Owned popups only. A dropdown's options are read from the list that
 *   dropdown points at. Scraping option-shaped elements out of the document
 *   once offered a salary chip, unrelated Yes/No buttons and an EEO race list
 *   as one question.
 *
 *   Nothing here is evidence. Every action ends by handing over to verify.js,
 *   which reads the page's own state afresh.
 */

(function () {
  "use strict";

  const AP = (globalThis.ApplyPilot = globalThis.ApplyPilot || {});
  if (AP.act) return;
  const D = AP.dom;
  const S = AP.surface;

  const OPEN_TIMEOUT = 2000;
  const GROW_TIMEOUT = 3000;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function waitFor(predicate, timeout) {
    const deadline = Date.now() + (timeout || OPEN_TIMEOUT);
    for (;;) {
      let value;
      try {
        value = predicate();
      } catch (err) {
        value = null;
      }
      if (value) return value;
      if (Date.now() > deadline) return null;
      await sleep(60);
    }
  }

  /* ------------------------------------------------------------- events */

  function setNativeValue(el, value) {
    const prototype = Object.getPrototypeOf(el);
    const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
    if (descriptor && descriptor.set) descriptor.set.call(el, value);
    else el.value = value;
  }

  function dispatch(el, type, Ctor, init) {
    try {
      el.dispatchEvent(new Ctor(type, init));
    } catch (err) {
      const event = document.createEvent("Event");
      event.initEvent(type, true, true);
      el.dispatchEvent(event);
    }
  }

  function pointerAt(el, type) {
    const rect = el.getBoundingClientRect();
    const init = {
      bubbles: true,
      cancelable: true,
      composed: true,
      view: window,
      clientX: rect.left + rect.width / 2,
      clientY: rect.top + rect.height / 2,
      button: 0,
      buttons: /down/.test(type) ? 1 : 0,
      isPrimary: true,
      pointerId: 1,
      pointerType: "mouse",
    };
    const Ctor = type.startsWith("pointer") && window.PointerEvent ? window.PointerEvent : MouseEvent;
    dispatch(el, type, Ctor, init);
  }

  /** A click a widget library will believe: the full pointer sequence. */
  function realClick(el) {
    try {
      el.scrollIntoView({ block: "center", inline: "center" });
    } catch (err) {
      /* detached or in a frame that will not scroll */
    }
    for (const type of ["pointerover", "pointerenter", "pointermove", "pointerdown", "mousedown"]) {
      pointerAt(el, type);
    }
    if (el.focus) {
      try {
        el.focus({ preventScroll: true });
      } catch (err) {
        el.focus();
      }
    }
    for (const type of ["pointerup", "mouseup", "click"]) pointerAt(el, type);
  }

  function fireInput(el) {
    dispatch(el, "input", Event, { bubbles: true, composed: true });
    dispatch(el, "change", Event, { bubbles: true, composed: true });
  }

  /* -------------------------------------------------------- primitives */

  function currentReading(found) {
    return AP.verify.observe(found.element, found.kind, found.group);
  }

  function skipResult(found, desired, reading) {
    return {
      fingerprint: "",
      requested: desired,
      outcome: "verified",
      observed: reading.value,
      signal: reading.signal,
      evidence: `already set, read back from ${reading.signal}; nothing was clicked`,
      changed: false,
    };
  }

  async function fillText(found, value) {
    const el = found.element;
    const reading = currentReading(found);
    if (AP.verify.same(reading.value, value) && reading.signal !== "none") {
      return skipResult(found, value, reading);
    }
    if (el.focus) el.focus();
    setNativeValue(el, "");
    fireInput(el);
    setNativeValue(el, value);
    fireInput(el);
    dispatch(el, "blur", FocusEvent, { bubbles: true });
    return { changed: true, previous: reading.value };
  }

  async function chooseNativeOption(found, optionLabel) {
    const el = found.element;
    const reading = currentReading(found);
    if (AP.verify.same(reading.value, optionLabel)) return skipResult(found, optionLabel, reading);

    const option = Array.from(el.options || []).find((candidate) =>
      AP.verify.same((candidate.textContent || "").trim(), optionLabel)
    );
    if (!option) {
      return {
        changed: false,
        failed: `this dropdown does not offer "${optionLabel}"`,
        previous: reading.value,
      };
    }
    if (el.focus) el.focus();
    setNativeValue(el, option.value);
    option.selected = true;
    fireInput(el);
    return { changed: true, previous: reading.value };
  }

  async function setChecked(found, wanted) {
    const el = found.element;
    const reading = currentReading(found);
    const isOn = reading.value === "Yes";
    if (isOn === wanted && reading.signal !== "none") {
      return skipResult(found, wanted ? "Yes" : "No", reading);
    }
    realClick(el);
    await sleep(60);
    if (Boolean(el.checked) !== wanted) {
      // Some forms only respond to the label that draws the box.
      const label = el.labels && el.labels[0];
      if (label) realClick(label);
    }
    return { changed: true, previous: reading.value };
  }

  async function chooseRadio(found, optionLabel) {
    const group = found.group || [found.element];
    const reading = currentReading(found);
    if (AP.verify.same(reading.value, optionLabel)) return skipResult(found, optionLabel, reading);

    const target = group.find((el) => AP.verify.same(AP.scan.optionLabel(el), optionLabel));
    if (!target) {
      return {
        changed: false,
        failed: `this question does not offer "${optionLabel}"`,
        previous: reading.value,
      };
    }
    realClick(target);
    await sleep(60);
    if (!target.checked) {
      const label = target.labels && target.labels[0];
      if (label) realClick(label);
    }
    return { changed: true, previous: reading.value };
  }

  /* --------------------------------------------------------- comboboxes */

  function comboTrigger(el) {
    const widget = AP.verify.widgetOf(el);
    if (!widget) return el;
    const trigger = D.deepQuery("[role='combobox'],[aria-haspopup],button,input", widget).find(
      (node) => D.isVisible(node)
    );
    return trigger || el;
  }

  /** The widget's own text box, when it has one. */
  function filterBox(el) {
    if ((el.tagName || "").toLowerCase() === "input") return el;
    return D.deepQuery("input", AP.verify.widgetOf(el)).find((node) => D.isVisible(node)) || null;
  }

  /**
   * Type into a widget's filter box.
   *
   * Whatever ends up in there came from this agent, so the box is marked and can
   * never afterwards be read back as evidence of a selection.
   */
  function typeFilter(box, text) {
    AP.verify.markTypedAsFilter(box);
    if (box.focus) box.focus();
    setNativeValue(box, text);
    fireInput(box);
    dispatch(box, "keyup", KeyboardEvent, { bubbles: true, key: text.slice(-1) });
  }

  /**
   * Get a control's own list open.
   *
   * Some widgets load nothing at all until something is typed, so a filter is
   * the second attempt rather than a shortcut.
   */
  async function openPopupFor(el, filterText) {
    let popup = D.ownedPopup(el);
    if (popup) return popup;

    realClick(comboTrigger(el));
    popup = await waitFor(() => D.ownedPopup(el), OPEN_TIMEOUT);
    if (popup) return popup;

    const box = filterBox(el);
    if (box && filterText) {
      typeFilter(box, filterText);
      popup = await waitFor(() => D.ownedPopup(el), OPEN_TIMEOUT);
    }
    return popup;
  }

  /**
   * Open a dropdown and read the options it owns.
   *
   * Returns an empty list rather than guessing when the control has no popup of
   * its own. An empty list is an honest "no options here"; a document-wide
   * scrape is a fabricated question.
   */
  async function openOptions(fingerprint, filterText) {
    const found = AP.scan.findByFingerprint(fingerprint);
    if (!found) return { options: [], opened: false, note: "the control is no longer on the page" };

    const el = found.element;
    if ((el.tagName || "").toLowerCase() === "select") {
      return {
        options: Array.from(el.options || []).map((option) => ({
          label: (option.textContent || "").trim(),
          value: option.value || "",
          disabled: Boolean(option.disabled),
        })),
        opened: true,
        source: "native",
        note: "",
      };
    }

    const popup = await openPopupFor(el, filterText);
    if (!popup) {
      return {
        options: [],
        opened: false,
        source: "none",
        note: "this control has no list of its own that opened; its options cannot be read",
      };
    }

    const rows = D.optionRows(popup);
    return {
      options: rows.map((row) => ({
        label: D.textOf(row),
        value: row.getAttribute("data-value") || row.getAttribute("value") || row.id || "",
        disabled: row.getAttribute("aria-disabled") === "true",
      })),
      opened: true,
      source: "owned_popup",
      note: "",
    };
  }

  async function chooseFromPopup(found, optionLabel) {
    const el = found.element;
    const reading = currentReading(found);
    if (AP.verify.same(reading.value, optionLabel)) return skipResult(found, optionLabel, reading);

    let popup = await openPopupFor(el, optionLabel);
    if (!popup) {
      return {
        changed: false,
        failed: "the control did not open a list of its own",
        previous: reading.value,
      };
    }

    let row = D.optionRows(popup).find((node) => AP.verify.same(D.textOf(node), optionLabel));
    if (!row) {
      const box = filterBox(el);
      if (box) {
        typeFilter(box, optionLabel);
        await sleep(300);
        const narrowed = D.ownedPopup(el) || popup;
        row = D.optionRows(narrowed).find((node) => AP.verify.same(D.textOf(node), optionLabel));
      }
    }
    if (!row) {
      return {
        changed: false,
        failed: `"${optionLabel}" is not among the options this control opened`,
        previous: reading.value,
      };
    }

    realClick(row);
    await sleep(150);
    return { changed: true, previous: reading.value };
  }

  /* ------------------------------------------------------ repeat blocks */

  /**
   * Press "Add another" and confirm by the form actually growing.
   *
   * A click that returns without error is not an added entry.
   */
  async function addRepeat(controlText) {
    const before = S.candidateControls(document).length;
    const button = S.clickableControls().find((el) => {
      const text = S.controlText(el);
      return text && (controlText ? AP.verify.same(text, controlText) : S.ADD_TEXT.test(text));
    });
    if (!button) {
      return { outcome: "failed", evidence: "no control on this page adds another entry" };
    }
    realClick(button);
    const grew = await waitFor(
      () => S.candidateControls(document).length > before,
      GROW_TIMEOUT
    );
    const after = S.candidateControls(document).length;
    if (!grew) {
      return {
        outcome: "failed",
        evidence: `pressed "${S.controlText(button)}" but the form still has ${after} controls`,
      };
    }
    return {
      outcome: "verified",
      evidence: `the form grew from ${before} to ${after} controls`,
    };
  }

  /* ------------------------------------------------------------- clicks */

  async function clickByText(text) {
    const button = S.clickableControls().find((el) => AP.verify.same(S.controlText(el), text));
    if (!button) return { outcome: "failed", evidence: `no control on this page reads "${text}"` };
    const before = location.href;
    const signatureBefore = AP.scan.run().signature;
    realClick(button);
    const moved = await waitFor(() => {
      if (location.href !== before) return true;
      return AP.scan.run().signature !== signatureBefore;
    }, GROW_TIMEOUT);
    return {
      outcome: moved ? "verified" : "attempted",
      evidence: moved
        ? "the page changed after the click"
        : "the click was issued but the page has not changed yet",
    };
  }

  /**
   * Sign-in never reports success from a filled-in box.
   *
   * A password field being non-empty proves only that a password field is
   * non-empty -- it once turned a password the applicant had typed themselves
   * into "signed in with the details you gave me". The only evidence that
   * counts is the sign-in form no longer being there.
   */
  async function signInSettled(timeout) {
    const gone = await waitFor(() => S.classify().kind !== "sign_in", timeout || GROW_TIMEOUT);
    if (gone) {
      return { outcome: "verified", evidence: "the sign-in form is no longer on the page" };
    }
    return {
      outcome: "failed",
      evidence: "the sign-in form is still on the page, so no sign-in has happened",
    };
  }

  function highlight(fingerprint) {
    const found = AP.scan.findByFingerprint(fingerprint);
    if (!found) return { ok: false };
    const el = found.element;
    try {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
    } catch (err) {
      /* ignore */
    }
    const previous = el.style.outline;
    el.style.outline = "3px solid #f0a500";
    el.style.outlineOffset = "2px";
    setTimeout(() => {
      el.style.outline = previous;
    }, 2500);
    return { ok: true };
  }

  /* ---------------------------------------------------------- dispatch */

  /**
   * Carry out one action and then verify it from a fresh reading.
   *
   * The action's own return value never becomes the verdict.
   */
  async function perform(action) {
    const found = AP.scan.findByFingerprint(action.fingerprint);
    if (!found) {
      return {
        fingerprint: action.fingerprint,
        requested: action.value || action.option_label || "",
        outcome: "failed",
        observed: "",
        signal: "none",
        evidence: "the control is no longer on the page",
      };
    }

    const desired = action.option_label || action.value || "";
    let step;

    switch (action.kind) {
      case "fill":
        step = await fillText(found, action.value || "");
        break;
      case "choose":
        if ((found.element.tagName || "").toLowerCase() === "select") {
          step = await chooseNativeOption(found, desired);
        } else if (found.kind === "radio") {
          step = await chooseRadio(found, desired);
        } else {
          step = await chooseFromPopup(found, desired);
        }
        break;
      case "check":
        step = await setChecked(found, /^(yes|true|on|1)$/i.test(String(action.value)));
        break;
      default:
        return {
          fingerprint: action.fingerprint,
          outcome: "failed",
          evidence: `unknown action "${action.kind}"`,
          signal: "none",
          observed: "",
          requested: desired,
        };
    }

    if (step && step.outcome === "verified" && step.changed === false) {
      step.fingerprint = action.fingerprint;
      return step;
    }
    if (step && step.failed) {
      return {
        fingerprint: action.fingerprint,
        requested: desired,
        outcome: "failed",
        observed: step.previous || "",
        signal: "none",
        evidence: step.failed,
      };
    }

    await sleep(120);
    return AP.verify.check(action.fingerprint, desired, step ? step.previous : "");
  }

  AP.act = {
    addRepeat,
    chooseFromPopup,
    chooseNativeOption,
    chooseRadio,
    clickByText,
    fillText,
    highlight,
    openOptions,
    perform,
    realClick,
    setChecked,
    setNativeValue,
    signInSettled,
    waitFor,
  };
})();
