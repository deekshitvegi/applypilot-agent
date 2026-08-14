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
  //: How long a control gets to show the value before the read-back is taken
  //: as final. Reached only by a page that is actually slow; one that answers
  //: straight away is read straight away.
  const SETTLE_TIMEOUT = 1200;
  //: An application that renders a new entry, or a whole next step, from the
  //: server takes longer than anything happening in the page alone -- and three
  //: seconds reported a click that had worked as one that had done nothing.
  const SLOW_PAGE_TIMEOUT = 12000;
  //: A control that searches a remote list needs longer than one that filters
  //: a list it already holds.
  const SEARCH_TIMEOUT = 6000;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  /**
   * A cheap reading of what is on the page.
   *
   * Enough to tell that a step moved on or an entry appeared, and cheap enough
   * to ask repeatedly: no layout is forced and nothing is walked by hand.
   */
  function pageShape() {
    const body = document.body;
    return [
      location.href,
      document.querySelectorAll("input,select,textarea,button").length,
      body ? body.textContent.length : 0,
    ].join("|");
  }

  /**
   * Wait for something to become true, without holding the page down.
   *
   * Asking every sixty milliseconds for twelve seconds is two hundred passes
   * over the whole document, and on a large application that is enough to make
   * the page itself feel slow to the person using it -- the form was fine until
   * the panel started work. Answers usually arrive immediately, so ask quickly
   * at first and then ease off.
   */
  async function waitFor(predicate, timeout) {
    const started = Date.now();
    const deadline = started + (timeout || OPEN_TIMEOUT);
    for (;;) {
      let value;
      try {
        value = predicate();
      } catch (err) {
        value = null;
      }
      if (value) return value;
      if (Date.now() > deadline) return null;
      const waited = Date.now() - started;
      await sleep(waited < 600 ? 60 : waited < 2500 ? 200 : 500);
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
    for (const type of ["pointerup", "mouseup"]) pointerAt(el, type);

    // One click, not two. A native click() is the more convincing of the pair --
    // some libraries only answer to a real activation -- so it is used when it
    // exists and a dispatched event stands in when it does not. Doing both
    // pressed "Add other education" twice and added two entries.
    if (typeof el.click === "function") {
      try {
        el.click();
        return;
      } catch (err) {
        /* fall through to the dispatched click */
      }
    }
    pointerAt(el, "click");
  }

  /** Whether the page is on screen. A hidden tab stops laying anything out. */
  function pageIsVisible() {
    return document.visibilityState !== "hidden";
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
    // Only for a box that answers with a list. Say exactly what is being put
    // there, so that what the page later replaces it with can be told from our
    // own echo: a place picker handed "Denton, Texas" comes back holding
    // "Denton, Texas, United States", and nobody wrote that but the page.
    //
    // An ordinary text box is left alone. Its holding what it was given is the
    // whole of the evidence there, and marking it took that away.
    if (D.isComboboxInput(el) || suggests(el)) {
      AP.verify.markTypedAsFilter(el, value);
    }
    setNativeValue(el, value);
    fireInput(el);

    // A box that looks like a text field but answers with a list. An address
    // line that says "Enter a location" is one: type into it, look away, and it
    // throws the text out again, because nothing was chosen from what it
    // offered. Blurring is what discards it -- so where the control says it
    // suggests, its suggestions are used before looking away, and the fields it
    // fills in for itself (city, postcode, county) arrive with it.
    if (suggests(el)) {
      const picked = await pickSuggestion(el, value);
      if (picked) return { changed: true, previous: reading.value };
    }

    dispatch(el, "blur", FocusEvent, { bubbles: true });

    // Not every one of these says what it is. Some carry no role and no aria at
    // all, and the only sign is what they do: the text is gone the moment focus
    // leaves. A box that empties itself has rejected what it was given, which is
    // proof enough to try again the other way -- and it costs nothing anywhere
    // else, because a box that kept the value never gets here.
    if (value && !el.value) {
      if (el.focus) el.focus();
      setNativeValue(el, value);
      fireInput(el);
      const picked = await pickSuggestion(el, value);
      if (picked) return { changed: true, previous: reading.value };
      dispatch(el, "blur", FocusEvent, { bubbles: true });
    }

    return { changed: true, previous: reading.value };
  }

  /** Whether a text box says, in its own attributes, that it offers a list. */
  function suggests(el) {
    if (!el || !el.getAttribute) return false;
    if ((el.getAttribute("role") || "").toLowerCase() === "combobox") return true;
    for (const name of ["aria-autocomplete", "aria-controls", "aria-owns", "aria-expanded"]) {
      if (el.getAttribute(name)) return true;
    }
    return false;
  }

  /**
   * Take what the box is offering, if it offers the thing that was typed.
   *
   * Never a different suggestion: a list that comes back with somewhere else
   * entirely is not an answer, and the applicant is better told than guessed
   * at. Returns false when nothing suitable appeared, and the fill then ends
   * the ordinary way.
   */
  /*
   * What to type into a box that answers with a list.
   *
   * A filter narrows a list. A whole sentence narrows it to nothing: one form
   * offers "No, I am not a veteran under one of the classifications listed
   * above" as a row, and handed that exact text as a filter it answered "No
   * results were found" and the field stayed empty. The applicant could see
   * the answer sitting in the box and the list underneath saying there was no
   * such thing.
   *
   * So the whole answer first -- plenty of boxes take it -- and then shorter
   * and shorter beginnings of it, which is what a person types. Whatever the
   * list then offers is matched against the whole answer, never against the
   * fragment that was typed to reveal it.
   */
  function filterAttempts(value) {
    const whole = String(value || "").trim();
    const words = whole.split(/\s+/).filter(Boolean);
    const tries = [whole];
    for (const take of [3, 1]) {
      if (words.length > take) {
        const shorter = words.slice(0, take).join(" ").replace(/[,;:]$/, "");
        if (shorter && tries.indexOf(shorter) === -1) tries.push(shorter);
      }
    }
    return tries;
  }

  /** The row a list is offering that answers *value*, or nothing. */
  function matchingRow(popup, value) {
    const rows = D.optionRows(popup).filter((row) => {
      const text = D.textOf(row);
      return text && !AP.verify.isPlaceholder(text);
    });
    if (!rows.length) return null;
    const exact = rows.find((row) => AP.verify.same(D.textOf(row), value));
    if (exact) return exact;
    const wanted = D.normalise(value);
    const leading = rows.find((row) => D.normalise(D.textOf(row)).startsWith(wanted));
    if (leading) return leading;
    // The list is showing the answer in its own longer wording. Only when one
    // row does: two would be a guess, and a guess here writes an answer.
    const inside = rows.filter((row) => wanted && D.normalise(D.textOf(row)).includes(wanted));
    return inside.length === 1 ? inside[0] : null;
  }

  async function pickSuggestion(el, value) {
    for (const attempt of filterAttempts(value)) {
      if (attempt !== String(value || "").trim()) {
        // Retype: the box is still holding whatever did not work.
        if (el.focus) el.focus();
        setNativeValue(el, "");
        fireInput(el);
        setNativeValue(el, attempt);
        fireInput(el);
      }
      const popup = await waitFor(() => D.ownedPopup(el), SEARCH_TIMEOUT);
      if (!popup) continue;
      const chosen = matchingRow(popup, value);
      if (chosen) {
        realClick(chosen);
        return true;
      }
    }
    return false;
  }

  async function chooseNativeOption(found, optionLabel) {
    const el = found.element;
    const reading = currentReading(found);
    if (AP.verify.same(reading.value, optionLabel)) return skipResult(found, optionLabel, reading);

    const find = () =>
      Array.from(el.options || []).find((candidate) =>
        AP.verify.same((candidate.textContent || "").trim(), optionLabel)
      );

    let option = find();
    if (!option && realOptionCount(el) < 2) {
      // Nothing to choose from yet. Some forms only load a dropdown's contents
      // once it is touched.
      realClick(el);
      await waitFor(() => realOptionCount(el) >= 2, OPEN_TIMEOUT);
      option = find();
    }
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

  /** Options a person could actually choose, placeholder rows removed. */
  function realOptionCount(el) {
    return Array.from(el.options || []).filter(
      (option) => !option.disabled && !AP.verify.isPlaceholder(option.textContent || "")
    ).length;
  }

  /**
   * The box a widget filters by, wherever it keeps it.
   *
   * Some widgets put their search field inside the dropdown they hang off
   * <body>, so looking only within the control finds nothing to type into.
   */
  function filterBox(el) {
    if ((el.tagName || "").toLowerCase() === "input") return el;
    const inWidget = D.deepQuery("input,textarea", AP.verify.widgetOf(el)).find((node) =>
      D.isVisible(node)
    );
    if (inWidget) return inWidget;
    // The search box sits beside the results, not inside them, and often a
    // couple of levels up: a dropdown is typically laid out as
    // [search] [results [list]]. Walking up from the list finds it; stopping at
    // the list's own parent did not, which is why a picker that types perfectly
    // well was never typed into at all.
    let scope = D.ownedPopup(el);
    for (let up = 0; up < 4 && scope && scope.tagName !== "BODY"; up += 1) {
      const box = D.deepQuery("input,textarea", scope).find((node) => D.isVisible(node));
      if (box) return box;
      scope = scope.parentElement;
    }
    return null;
  }

  /**
   * Type into a widget's filter box, one character at a time.
   *
   * Setting the whole value at once and firing a single input event is enough
   * for a widget filtering a list it already has, and not enough for one that
   * runs a search per keystroke -- which is what a picker holding every
   * university in the world does. Each character gets the events a real key
   * press produces.
   *
   * Whatever ends up in the box came from this agent, so it is marked and can
   * never afterwards be read back as evidence of a selection.
   */
  function typeFilter(box, text) {
    // The exact text, so that what the page later replaces it with can be told
    // apart from our own echo of it.
    AP.verify.markTypedAsFilter(box, String(text || ""));
    if (box.focus) box.focus();
    setNativeValue(box, "");
    fireInput(box);

    const value = String(text || "");
    for (let i = 0; i < value.length; i += 1) {
      const key = value[i];
      const init = { bubbles: true, cancelable: true, composed: true, key: key };
      dispatch(box, "keydown", KeyboardEvent, init);
      setNativeValue(box, value.slice(0, i + 1));
      dispatch(box, "input", InputEvent, { bubbles: true, composed: true, data: key });
      dispatch(box, "keyup", KeyboardEvent, init);
    }
    dispatch(box, "change", Event, { bubbles: true, composed: true });
  }

  /** What a control is currently offering, as plain labels. */
  function offeredLabels(el, popup) {
    const list = popup || D.ownedPopup(el);
    if (!list) return [];
    return D.optionRows(list)
      .map((row) => D.textOf(row))
      .filter((text) => text && !AP.verify.isPlaceholder(text));
  }

  /**
   * Get a control's own list open.
   *
   * Some widgets load nothing at all until something is typed, so a filter is
   * the second attempt rather than a shortcut.
   */
  async function openPopupFor(el, filterText) {
    let popup = D.ownedPopup(el);
    if (!popup) {
      realClick(comboTrigger(el));
      popup = await waitFor(() => D.ownedPopup(el), OPEN_TIMEOUT);
    }

    // A list that has opened is not the same as a list with anything in it. One
    // picker opens saying "Please enter 1 or more characters", and returning as
    // soon as that appeared meant the filter was never typed at all -- so the
    // answer was reported missing from a list that had never been searched.
    if (filterText && (!popup || !offeredLabels(el, popup).length)) {
      const box = filterBox(el);
      if (box) {
        typeFilter(box, filterText);
        await waitFor(() => offeredLabels(el).length > 0, SEARCH_TIMEOUT);
        popup = D.ownedPopup(el) || popup;
      }
      // No box to type into means no search will happen, so there is nothing
      // to wait for. Waiting anyway cost six seconds per control, several
      // times over, and turned one page into ten minutes.
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
      // A native select is not always populated before it is touched. One held
      // nothing but its own "No Selection" row until something opened it, and a
      // required choice with no choices in it became a text box for the
      // applicant to type a dropdown answer into.
      if (realOptionCount(el) < 2) {
        realClick(el);
        await waitFor(() => realOptionCount(el) >= 2, OPEN_TIMEOUT);
      }
      return {
        options: Array.from(el.options || []).map((option) => ({
          label: (option.textContent || "").trim(),
          value: option.value || "",
          disabled: Boolean(option.disabled),
        })),
        opened: true,
        source: "native",
        note: realOptionCount(el) ? "" : "this dropdown offers nothing at all",
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

    const findRow = (list) =>
      D.optionRows(list || D.ownedPopup(el) || popup).find((node) =>
        AP.verify.same(D.textOf(node), optionLabel)
      );

    let row = findRow(popup);
    if (!row) {
      const box = filterBox(el);
      if (box) {
        typeFilter(box, optionLabel);
        // A picker that searches a remote list takes its time. Waiting a fixed
        // fraction of a second and reading once reported an option missing that
        // arrived a moment later.
        row = await waitFor(() => findRow(null), SEARCH_TIMEOUT);
      }
    }
    if (!row) {
      const seen = offeredLabels(el);
      return {
        changed: false,
        failed:
          `"${optionLabel}" is not among the options this control opened` +
          (seen.length
            ? `; it offered ${seen.length}: ${seen.slice(0, 5).join(", ")}` +
              (seen.length > 5 ? ", …" : "")
            : "; it offered nothing at all"),
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
  /**
   * Answer a question whose options are buttons, by pressing one.
   *
   * Idempotent like everything else: a group already showing the wanted answer
   * is left alone. Pressing a button that is already chosen is how a page like
   * this gets toggled back off.
   */
  async function chooseButton(found, desired) {
    const buttons = found.group || [];
    const already = D.pickedButton(buttons);
    if (already && AP.verify.same(D.textOf(already), desired)) {
      return { outcome: "verified", changed: false, previous: D.textOf(already) };
    }
    const wanted = buttons.find((button) => AP.verify.same(D.textOf(button), desired));
    if (!wanted) {
      return {
        failed:
          `"${desired}" is not one of the options here; this question offers ` +
          buttons.map((b) => D.textOf(b)).join(", "),
        previous: already ? D.textOf(already) : "",
      };
    }
    realClick(wanted);
    return { previous: already ? D.textOf(already) : "" };
  }

  /**
   * Answer a "which of these" question by ticking one of its boxes.
   *
   * Only the one asked for, and only when it is not already ticked -- ticking a
   * ticked box clears it. Anything else already ticked stays where it is,
   * because someone may have answered part of this themselves.
   */
  async function tickInList(found, desired) {
    const boxes = found.group || [];
    const ticked = () =>
      boxes.filter((b) => b.checked).map((b) => D.visibleLabel(b)).join(", ");
    const wanted = boxes.find((b) => AP.verify.same(D.visibleLabel(b), desired));
    if (!wanted) {
      const offered = boxes.map((b) => D.visibleLabel(b)).join(", ");
      return {
        failed: `"${desired}" is not one of the options here; this question offers ${offered}`,
        previous: ticked(),
      };
    }
    const before = ticked();
    if (wanted.checked) return { outcome: "verified", changed: false, previous: before };
    realClick(wanted);
    return { previous: before };
  }

  async function addRepeat(controlText) {
    const before = S.formElementCount();
    const button = S.pressable(controlText || S.ADD_TEXT);
    if (!button) {
      return { outcome: "failed", evidence: "no control on this page adds another entry" };
    }
    const name = S.controlText(button);
    realClick(button);
    const grew = await waitFor(() => S.formElementCount() > before, SLOW_PAGE_TIMEOUT);
    const after = S.formElementCount();
    if (!grew) {
      return {
        outcome: "failed",
        evidence: `pressed "${name}" but the form still has ${after} fields`,
      };
    }
    return {
      outcome: "verified",
      evidence: `the form grew from ${before} to ${after} fields`,
    };
  }

  /* ------------------------------------------------------------- clicks */

  async function clickByText(text) {
    const button = S.pressable(text);
    if (!button) return { outcome: "failed", evidence: `no control on this page reads "${text}"` };
    const before = pageShape();
    realClick(button);
    // Not a full scan: this runs on a loop, and scanning a large application
    // over and over was the extension making the page slow, not the site.
    const moved = await waitFor(() => pageShape() !== before, SLOW_PAGE_TIMEOUT);
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

  /**
   * Attach a document to a file input.
   *
   * The bytes arrive from the service worker, whose origin is the extension's
   * own; the page is never handed a way to reach the local service. Success is
   * the input's own file list naming the file, not the assignment returning.
   */
  async function attachFile(fingerprint, base64, filename, mime) {
    const found = AP.scan.findByFingerprint(fingerprint);
    if (!found) {
      return {
        fingerprint: fingerprint,
        outcome: "failed",
        signal: "none",
        observed: "",
        requested: filename,
        evidence: "the file control is no longer on the page",
      };
    }
    const el = found.element;
    const already = AP.verify.observe(el, "file", null);
    if (AP.verify.same(already.value, filename)) {
      return {
        fingerprint: fingerprint,
        outcome: "verified",
        signal: already.signal,
        observed: already.value,
        requested: filename,
        evidence: "already attached; nothing was clicked",
      };
    }

    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    const file = new File([bytes], filename, { type: mime || "application/octet-stream" });

    const transfer = new DataTransfer();
    transfer.items.add(file);
    el.files = transfer.files;
    fireInput(el);
    await sleep(200);

    const checked = AP.verify.check(fingerprint, filename, already.value);
    if (checked && checked.outcome !== "failed") return checked;

    // Uploading is not instant. The two hundred milliseconds above are enough
    // for a control that keeps its own file list, and nowhere near enough for
    // one that hands the document to a server and redraws when it comes back.
    // Checked immediately, that page has not yet said anything, and the answer
    // was a flat failure on an upload that had in fact worked.
    const settled = await waitFor(() => attachedSomewhere(filename), SLOW_PAGE_TIMEOUT);
    if (settled) return settled;

    // The control was replaced by the attachment succeeding.
    //
    // Several large systems re-render their upload as soon as a file lands,
    // which destroys the element the fingerprint pointed at. Verification then
    // reported "the control is no longer on the page" -- true, and exactly
    // backwards: the control is gone *because it worked*.
    //
    // So look again for a file input holding this file. That is still the
    // page's own state and still a fresh read; it is only the handle that
    // changed. Nothing here trusts that the assignment returned, and a page
    // holding no such file still fails.
    return checked;
  }

  /**
   * A file control anywhere on the page whose own list names *filename*.
   *
   * Returns null when none does, so a failure stays a failure.
   */
  function attachedSomewhere(filename) {
    const inputs = AP.dom.deepQuery("input[type='file']", document);
    for (const el of inputs) {
      const files = el.files;
      if (!files || !files.length) continue;
      for (const candidate of files) {
        if (AP.verify.same(candidate.name, filename)) {
          return {
            fingerprint: "",
            outcome: "verified",
            signal: "native_value",
            observed: candidate.name,
            requested: filename,
            evidence: "the page is holding this file, on a control it rebuilt",
          };
        }
      }
    }

    // The upload was taken away entirely, and the page is showing the name.
    //
    // One large system removes its file input the moment a document is
    // accepted and renders the filename in its place, so there is no input
    // left to read and nothing anywhere holds a FileList. What there is, is
    // the page's own words saying it has the file.
    //
    // Only when every file control has gone. That is what makes this a reading
    // of the page's state rather than a search for our own string: we did not
    // write this text, the page did, and it wrote it because it accepted the
    // document. While an empty upload is still sitting there, nothing has been
    // accepted and a filename printed somewhere proves nothing.
    if (inputs.length === 0 && filename) {
      const shown = (document.body && document.body.innerText) || "";
      const stem = filename.replace(/\.[a-z0-9]+$/i, "");
      if (stem.length >= 6 && shown.indexOf(stem) !== -1) {
        return {
          fingerprint: "",
          outcome: "verified",
          signal: "rendered_text",
          observed: filename,
          requested: filename,
          evidence: "the upload is gone and the page is showing this filename",
        };
      }
    }
    return null;
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
        } else if (found.kind === "ticklist") {
          step = await tickInList(found, desired);
        } else if (found.kind === "buttons") {
          step = await chooseButton(found, desired);
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

    return settled(action.fingerprint, desired, step ? step.previous : "");
  }

  /**
   * A page's worth of actions in one trip into it.
   *
   * Every action used to be its own message to the service worker, its own
   * injection target and its own reply -- and once the work inside the page was
   * made fast, that traffic was most of what was left: on a form of thirty
   * fields, six sevenths of the time was spent getting in and out rather than
   * filling anything in.
   *
   * They still run one at a time, in order, through exactly the same perform().
   * A form where one answer changes the next one still sees them in the order
   * they were planned, and every result is still the page's own state read back
   * afterwards. Nothing here decides anything; it only saves the journey.
   */
  async function performMany(actions) {
    const results = [];
    for (const action of actions || []) {
      try {
        results.push(await perform(action));
      } catch (err) {
        results.push({
          fingerprint: action.fingerprint,
          requested: action.value || action.option_label || "",
          outcome: "failed",
          observed: "",
          signal: "none",
          evidence: String((err && err.message) || err),
        });
      }
    }
    return results;
  }

  /**
   * Read the page back as soon as it has caught up, rather than after a count.
   *
   * This used to be a flat wait of 120ms before every single read-back, on the
   * reasoning that a page needs a moment to react. Most of them do not need
   * anything like that long, and a form of thirty fields was paying it thirty
   * times over -- four seconds of a fill spent waiting for pages that had
   * already finished. A page that genuinely does need longer now gets longer.
   *
   * Nothing about what counts as verified changes here: the answer still comes
   * from verify.js reading state the page owns, and a control that never takes
   * the value is still reported exactly as it was.
   */
  async function settled(fingerprint, desired, previous) {
    const deadline = Date.now() + SETTLE_TIMEOUT;
    let result = AP.verify.check(fingerprint, desired, previous);
    for (let wait = 15; result.outcome !== "verified" && Date.now() < deadline; wait *= 2) {
      await sleep(Math.min(wait, 200));
      result = AP.verify.check(fingerprint, desired, previous);
    }
    return result;
  }

  AP.act = {
    addRepeat,
    pageShape,
    performMany,
    offeredLabels,
    attachFile,
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
