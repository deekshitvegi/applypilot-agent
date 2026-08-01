/*
 * What kind of page is this, and which part of it is the application?
 *
 * Four access patterns behave completely differently and conflating them is
 * what produced phantom fields on search pages, "every application is a login
 * page", and an Apply button found on a list of search results.
 *
 * Nothing here reads the URL to decide whether a page is a sign-in. A form at
 * .../postLogin.html with an email field on it is an application, and the only
 * honest way to know that is to look at the controls.
 */

(function () {
  "use strict";

  const AP = (globalThis.ApplyPilot = globalThis.ApplyPilot || {});
  if (AP.surface) return;
  const D = AP.dom;

  /* Containers whose controls are never part of an application. */
  const FURNITURE = [
    "nav",
    "header",
    "footer",
    "aside",
    "[role='search']",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    "[role='complementary']",
    "[id*='search' i]",
    "[class*='searchbar' i]",
    "[class*='search-bar' i]",
    "[class*='search-form' i]",
    "[class*='searchform' i]",
    "[class*='facet' i]",
    "[class*='refine' i]",
    "[class*='subscribe' i]",
    "[class*='newsletter' i]",
    "[class*='cookie' i]",
    "[class*='consent' i]",
    "[class*='langu' i]",
    "[class*='locale' i]",
    "[class*='chat' i]",
  ].join(",");

  /* Controls that are a way of finding jobs, not a question about you.
   * Deliberately narrow: an application legitimately asks for a Location, so
   * that word cannot be on this list. What keeps a search page's filters out is
   * the page being a search page at all. */
  const SEARCH_NAMES = /^(q|s|kw|search|searchterm|keyword|keywords|query|sortby|sort|facet.*|filter.*)$/i;

  /* Widgets a page draws for itself instead of using a real control. */
  const CUSTOM_CONTROLS =
    "[role='combobox'],[role='checkbox'],[role='switch'],[contenteditable='true']";

  const APPLY_TEXT = /^(apply|apply now|apply here|apply for this job|apply to this job|easy apply|quick apply|start application|apply with)/i;
  const SUBMIT_TEXT = /^(submit|submit application|send application|submit my application|finish|complete application)/i;
  const NEXT_TEXT = /(save and continue|save & continue|next|continue|proceed|save and next)/i;
  const ADD_TEXT = /(add another|add more|add an(other)? entry|add education|add experience|add employment|add school|add work|add position|add degree|\+\s*add)/i;

  const CONFIRMATION_TEXT = /(thank you for applying|your application (has been )?(was )?(submitted|received)|we (have )?received your application|application (submitted|complete|received)|thanks for applying)/i;

  const REGISTER_LABEL = /(choose (a )?password|create (a )?password|retype password|re-?enter password|confirm password|verify password|create (an )?account|register|sign up)/i;
  const USERNAME_HINT = /(user\s?id|username|user name|login|logon|account id|email|e-?mail)/i;
  const SIGN_IN_TEXT = /^(sign in|log in|login|logon|next|continue|submit)$/i;

  const POSTING_HREF = /\/(job|jobs|career|careers|position|positions|opening|openings|vacancy|vacancies|opportunit)/i;

  /* A requisition id: a uuid, a long hash, or a run of digits. */
  const IDENTIFIER = /^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f-]+|[0-9a-zA-Z_-]*\d{4,}[0-9a-zA-Z_-]*|[0-9a-f]{12,})$/i;

  function insideFurniture(el) {
    return Boolean(D.closestDeep(el, FURNITURE));
  }

  function isSearchControl(el) {
    if (!el) return false;
    const type = (el.getAttribute("type") || "").toLowerCase();
    if (type === "search") return true;
    const role = (el.getAttribute("role") || "").toLowerCase();
    if (role === "searchbox") return true;
    for (const attr of ["name", "id", "aria-label", "placeholder"]) {
      const value = (el.getAttribute(attr) || "").trim();
      if (value && SEARCH_NAMES.test(value)) return true;
    }
    return false;
  }

  /** Every control that could belong to an application, furniture removed. */
  function candidateControls(root) {
    const scope = root || document;
    return D.deepQuery("input,select,textarea," + CUSTOM_CONTROLS, scope).filter((el) => {
      // A widget's own text box and the widget wrapping it are one control.
      if (D.isComboboxInput(el)) {
        const host = D.closestDeep(el.parentElement, "[role='combobox']");
        if (host && host !== el) return false;
      }
      const type = (el.getAttribute("type") || el.type || "").toLowerCase();
      if (type === "hidden" || type === "submit" || type === "button" || type === "image") {
        return false;
      }
      if (!D.isVisible(el)) return false;
      if (insideFurniture(el)) return false;
      if (isSearchControl(el)) return false;
      return true;
    });
  }

  function labelledControls(root) {
    return candidateControls(root).filter((el) => D.visibleLabel(el));
  }

  function passwordFields(root) {
    return D.deepQuery("input", root || document).filter(
      (el) => (el.getAttribute("type") || el.type || "").toLowerCase() === "password"
    );
  }

  function clickableControls() {
    return D.deepQuery("button,a,input[type='submit'],input[type='button'],[role='button']", document)
      .filter((el) => D.isVisible(el));
  }

  function controlText(el) {
    return (
      D.textOf(el) ||
      el.getAttribute("aria-label") ||
      el.getAttribute("value") ||
      el.getAttribute("title") ||
      ""
    ).trim();
  }

  function matchingControls(pattern) {
    const out = [];
    for (const el of clickableControls()) {
      const text = controlText(el);
      if (text && pattern.test(text)) out.push(describeControl(el, text));
    }
    return out;
  }

  function describeControl(el, text) {
    return {
      text: text,
      fingerprint: "btn:" + D.hash([text, el.tagName, el.getAttribute("name") || ""].join("|")),
      href: el.getAttribute("href") || "",
    };
  }

  /**
   * How many links on this page lead to a posting.
   *
   * The word "job" is not always in the path. Boards that link to
   * ``/<company>/<uuid>`` were read as having no postings at all, so their
   * filter controls became the page's "questions" -- four of them on one board,
   * five on another, eleven on a third.
   */
  function postingLinks() {
    const seen = new Set();
    for (const link of D.deepQuery("a[href]", document)) {
      if (!D.isVisible(link)) continue;
      const href = link.getAttribute("href") || "";
      const text = D.textOf(link);
      if (!href || !text || text.length > 120) continue;
      if (POSTING_HREF.test(href) || opaquePostingPath(href)) seen.add(href);
    }
    return seen.size;
  }

  /** A same-site path ending in something that reads as a requisition id. */
  function opaquePostingPath(href) {
    if (/^(https?:)?\/\//i.test(href)) {
      try {
        if (new URL(href, location.href).host !== location.host) return false;
      } catch (err) {
        return false;
      }
    } else if (href.startsWith("#") || href.startsWith("mailto:")) {
      return false;
    }
    let path;
    try {
      path = new URL(href, location.href).pathname;
    } catch (err) {
      return false;
    }
    const segments = path.split("/").filter(Boolean);
    if (segments.length < 2) return false;
    const last = segments[segments.length - 1];
    return IDENTIFIER.test(last);
  }

  /* ------------------------------------------------------------- captcha */

  /**
   * A reCAPTCHA badge is not a challenge.
   *
   * The invisible badge is a 256x60 iframe that sits on a large share of career
   * sites and asks nothing of anyone. Treating it as a challenge blocked every
   * application on every site that carries one. A challenge is a checkbox
   * waiting to be ticked or a puzzle panel on screen -- and neither of those is
   * something this agent will ever solve.
   */
  function captchaState() {
    const frames = D.deepQuery("iframe", document);
    let sawBadge = false;

    if (D.deepQuery(".grecaptcha-badge", document).length) sawBadge = true;

    for (const frame of frames) {
      const src = frame.getAttribute("src") || "";
      const isRecaptcha = /recaptcha/i.test(src);
      const isHcaptcha = /hcaptcha/i.test(src);
      if (!isRecaptcha && !isHcaptcha) continue;

      const rect = frame.getBoundingClientRect();
      const visible = D.isVisible(frame);
      const inBadge = Boolean(D.closestDeep(frame, ".grecaptcha-badge"));

      if (inBadge || (rect.width <= 260 && rect.height <= 60)) {
        sawBadge = true;
        continue;
      }
      if (!visible) continue;

      // The interactive checkbox renders around 300x78; a puzzle panel is far
      // taller. Either one needs a person.
      if (/anchor/i.test(src) && rect.width >= 280 && rect.height >= 70) return "challenge";
      if (/bframe/i.test(src) && rect.height >= 200) return "challenge";
      if (isHcaptcha && rect.width >= 280 && rect.height >= 70) return "challenge";
    }

    return sawBadge ? "badge_only" : "none";
  }

  /* ---------------------------------------------------------- page kinds */

  function registrationSignals() {
    const passwords = passwordFields().filter((el) => D.isVisible(el));
    if (passwords.length >= 2) return "two password fields";
    for (const el of passwords) {
      const label = D.visibleLabel(el) || D.attributeLabel(el);
      if (REGISTER_LABEL.test(label)) return `a password field labelled "${label}"`;
    }
    if (passwords.length) {
      const heading = D.deepQuery("h1,h2,legend", document)
        .filter((el) => D.isVisible(el))
        .map((el) => D.textOf(el))
        .find((text) => REGISTER_LABEL.test(text));
      if (heading) return `the page heading says "${heading}"`;
    }
    return "";
  }

  function signInSignals() {
    const controls = candidateControls();
    const passwords = passwordFields().filter((el) => D.isVisible(el));
    const hasFileInput = D.deepQuery("input[type='file']", document).some((el) => D.isVisible(el));
    const textareas = D.deepQuery("textarea", document).filter((el) => D.isVisible(el));

    if (passwords.length === 1 && controls.length <= 6 && !hasFileInput && !textareas.length) {
      return "one password field on a page with nothing else to fill in";
    }

    // A two-step sign-in asks for an identifier first and shows no password at
    // all. It is told apart from an application by how little else it wants.
    if (!passwords.length && controls.length <= 3 && !hasFileInput && !textareas.length) {
      const identifier = controls.find((el) => {
        const label = D.visibleLabel(el) || D.attributeLabel(el);
        const autocomplete = el.getAttribute("autocomplete") || "";
        return USERNAME_HINT.test(label) || /username|email/i.test(autocomplete);
      });
      const button = clickableControls().find((el) => SIGN_IN_TEXT.test(controlText(el)));
      if (identifier && button) {
        const label = D.visibleLabel(identifier) || D.attributeLabel(identifier);
        return `a single "${label}" field and a "${controlText(button)}" button`;
      }
    }
    return "";
  }

  function classify() {
    const notes = [];
    const controls = candidateControls();
    const labelled = labelledControls();
    const hasFileInput = D.deepQuery("input[type='file']", document).some((el) => D.isVisible(el));
    const postings = postingLinks();
    const searchBoxes = D.deepQuery("input,select", document).filter(
      (el) => D.isVisible(el) && isSearchControl(el)
    ).length;

    const registration = registrationSignals();
    if (registration) {
      notes.push("registration: " + registration);
      return { kind: "registration", notes: notes };
    }

    const signIn = signInSignals();
    if (signIn) {
      notes.push("sign-in: " + signIn);
      return { kind: "sign_in", notes: notes };
    }

    const bodyText = (document.body ? document.body.innerText || "" : "").slice(0, 4000);
    if (!controls.length && CONFIRMATION_TEXT.test(bodyText)) {
      notes.push("the page says the application was received");
      return { kind: "confirmation", notes: notes };
    }

    // Judged by the controls present, not by whether there is a <form>: a
    // complete 21-field application rendered without one was seen and refused.
    const textareas = D.deepQuery("textarea", document).filter((el) => D.isVisible(el)).length;
    const applicationShaped = labelled.length >= 5 || (hasFileInput && labelled.length >= 2);

    // A page listing dozens of other jobs, with nowhere to attach anything and
    // nothing to write in, is a list however many controls it has. Its controls
    // narrow that list; they are not questions about the applicant.
    const listOfJobs = postings >= 6 && !hasFileInput && !textareas;

    if (applicationShaped && !listOfJobs) {
      notes.push(`${labelled.length} labelled controls${hasFileInput ? " and a file input" : ""}`);
      return { kind: "application", notes: notes };
    }

    if (postings >= 6) {
      const kind = searchBoxes ? "search" : "board";
      notes.push(`${postings} posting links${searchBoxes ? " behind a search box" : ""}`);
      notes.push("controls on a list of jobs are filters, not questions");
      return { kind: kind, notes: notes };
    }

    if (searchBoxes && postings >= 1) {
      notes.push("a search box over a list of results");
      return { kind: "search", notes: notes };
    }

    if (matchingControls(APPLY_TEXT).length) {
      notes.push("a single posting with its own apply control");
      return { kind: "listing", notes: notes };
    }

    notes.push(`${controls.length} controls, ${postings} posting links`);
    return { kind: "unknown", notes: notes };
  }

  /**
   * Where scanning is allowed.
   *
   * On a list of jobs there is nothing to fill in, so nothing is offered. That
   * is what stops a set of search filters being counted as an application's
   * questions.
   */
  function scanRoot(kind) {
    if (kind === "search" || kind === "board" || kind === "confirmation") return null;
    return document;
  }

  AP.surface = {
    ADD_TEXT,
    APPLY_TEXT,
    NEXT_TEXT,
    SUBMIT_TEXT,
    candidateControls,
    captchaState,
    classify,
    clickableControls,
    controlText,
    describeControl,
    insideFurniture,
    isSearchControl,
    labelledControls,
    matchingControls,
    passwordFields,
    postingLinks,
    scanRoot,
  };
})();
