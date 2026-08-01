/*
 * The panel.
 *
 * It talks to the local service over http://127.0.0.1 and to the page only by
 * asking the service worker. It never injects anything itself.
 *
 * Three rules the interface has to keep:
 *
 *   A dropdown is never handed back as a text box. If a control's choices are
 *   not known yet they get opened and read first, and if a saved answer matches
 *   one of them the question does not get asked at all.
 *
 *   Every control says whether it is working, and cannot be pressed twice.
 *   Pressing Save with no feedback and no guard skipped four questions in a row.
 *
 *   An action runs in the frame its control actually lives in. Applications are
 *   very often inside one.
 *
 * There is no code here that types a password into a page, and that is on
 * purpose. What exists instead is the hand-off: the panel says which host wants
 * you signed in, you sign in with your password manager, and the run picks up
 * from whatever the page looks like afterwards.
 */

const SERVICE = "http://127.0.0.1:8765";
const EXTENSION_VERSION = chrome.runtime.getManifest().version;

const el = (id) => document.getElementById(id);

const state = {
  tab: null,
  observation: null,
  plan: null,
  results: [],
  running: false,
  busy: false,
  questionIndex: 0,
  lastFingerprint: "",
  checklist: [],
  checklistFilter: "all",
  unread: 0,
  autoContinue: false,
  submissionPolicy: "confirm",
};

/* ------------------------------------------------------------------ plumbing */

async function service(path, options) {
  const response = await fetch(SERVICE + path, Object.assign({ method: "GET" }, options));
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail || detail;
    } catch (err) {
      /* not json */
    }
    throw new Error(detail);
  }
  const type = response.headers.get("content-type") || "";
  return type.includes("json") ? response.json() : response.text();
}

const post = (path, body) =>
  service(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body || {}),
  });

const put = (path, body) =>
  service(path, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body || {}),
  });

function browser(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (reply) => {
      if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
      if (!reply || !reply.ok) return reject(new Error((reply && reply.error) || "no reply"));
      resolve(reply.value);
    });
  });
}

/** Which frame a control lives in. Applications are often inside one. */
function frameOf(fingerprint) {
  const field = (state.observation && state.observation.fields || []).find(
    (f) => f.fingerprint === fingerprint
  );
  return field && field.frame !== "" ? field.frame : 0;
}

function fieldFor(fingerprint) {
  return ((state.observation && state.observation.fields) || []).find(
    (f) => f.fingerprint === fingerprint
  ) || null;
}

/* --------------------------------------------------------------- feedback */

function setBusy(button, on, label) {
  if (!button) return;
  button.disabled = on;
  button.classList.toggle("busy", on);
  if (label !== undefined && !on) button.textContent = label;
}

function flashDone(button, label, restore) {
  if (!button) return;
  button.classList.add("done");
  button.textContent = label;
  setTimeout(() => {
    button.classList.remove("done");
    button.textContent = restore;
  }, 700);
}

function say(text, tone) {
  if (!text) return;
  const line = document.createElement("div");
  line.className = "line" + (tone ? " " + tone : "");
  line.textContent = text;
  el("log").appendChild(line);
  el("log").scrollTop = el("log").scrollHeight;
  if (el("log").classList.contains("hidden") && (tone === "warn" || tone === "bad")) {
    state.unread += 1;
    const badge = el("log-badge");
    badge.textContent = state.unread + " to look at";
    badge.classList.remove("hidden");
  }
}

function youSaid(text) {
  const line = document.createElement("div");
  line.className = "line you";
  line.textContent = text;
  el("log").appendChild(line);
  el("log").scrollTop = el("log").scrollHeight;
}

function activity(text, detail) {
  el("activity").textContent = text;
  if (detail !== undefined) el("page-detail").textContent = detail;
}

function progress(done, total) {
  const bar = el("progress");
  if (!total) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  el("progress-bar").style.width = Math.round((done / total) * 100) + "%";
}

function alert_(text, tone, actionLabel, onAction) {
  const box = document.createElement("div");
  box.className = "alert" + (tone === "bad" ? " bad" : "");
  const body = document.createElement("div");
  body.textContent = text;
  box.appendChild(body);
  if (actionLabel) {
    const button = document.createElement("button");
    button.textContent = actionLabel;
    button.addEventListener("click", () => {
      box.remove();
      onAction();
    });
    box.appendChild(button);
  }
  el("alerts").appendChild(box);
}

/* ------------------------------------------------------------------- health */

async function refreshHealth() {
  try {
    const health = await service("/health");
    el("versions").textContent = `panel ${EXTENSION_VERSION} · service ${health.version}`;
    el("applications").textContent = health.applications.total
      ? `${health.applications.total} tracked`
      : "";

    el("alerts").innerHTML = "";
    if (health.version !== EXTENSION_VERSION) {
      alert_(
        `The service is running ${health.version} but this panel is ${EXTENSION_VERSION}. ` +
          "Restart the service, then reload the extension.",
        "bad"
      );
    }
    if (!health.model_configured) {
      alert_(
        "No model key yet. I can still match your saved answers; I just cannot suggest " +
          "an answer to a question nothing covers.",
        "warn",
        "Add a key",
        () => chrome.runtime.openOptionsPage()
      );
    }
    return health;
  } catch (err) {
    el("versions").textContent = `panel ${EXTENSION_VERSION} · service not running`;
    alert_(
      "The local service is not answering on 127.0.0.1:8765. Start it with scripts\\start.ps1.",
      "bad",
      "Try again",
      refreshHealth
    );
    return null;
  }
}

/* --------------------------------------------------------------- onboarding */

async function refreshOnboarding() {
  const data = await service("/onboarding");
  const card = el("onboarding");
  if (data.complete) {
    card.classList.add("hidden");
    return data;
  }
  card.classList.remove("hidden");
  el("onboarding-progress").textContent = `${data.answered} of ${data.total}`;
  el("onboarding-note").textContent =
    data.notes[0] || "Answer these once and applications stop asking.";
  renderOnboardingStep(data.next);
  return data;
}

function renderOnboardingStep(step) {
  const host = el("onboarding-step");
  host.innerHTML = "";
  if (!step) return;

  const heading = document.createElement("p");
  heading.className = "sub tiny";
  heading.textContent = step.group_title;
  host.appendChild(heading);

  const label = document.createElement("p");
  label.className = "ask";
  label.textContent = step.prompt;
  host.appendChild(label);

  const control = buildControl(step.kind, step.choices || [], step.value);
  host.appendChild(control.node);

  const row = document.createElement("div");
  row.className = "actions";
  const save = document.createElement("button");
  save.className = "primary";
  save.textContent = "Save";
  save.addEventListener("click", async () => {
    if (state.busy) return;
    state.busy = true;
    setBusy(save, true);
    try {
      await post("/onboarding/answer", { key: step.key, value: control.read() });
      flashDone(save, "Saved", "Save");
      await refreshOnboarding();
    } catch (err) {
      say(String(err.message), "bad");
    } finally {
      state.busy = false;
      setBusy(save, false, "Save");
    }
  });
  row.appendChild(save);

  if (step.optional) {
    const skip = document.createElement("button");
    skip.className = "quiet";
    skip.textContent = "Prefer not to say";
    skip.addEventListener("click", async () => {
      if (state.busy) return;
      state.busy = true;
      try {
        await post("/onboarding/answer", {
          key: step.key,
          value: step.kind === "choice" ? "I don't wish to answer" : "",
        });
        await refreshOnboarding();
      } finally {
        state.busy = false;
      }
    });
    row.appendChild(skip);
  }
  host.appendChild(row);
}

/** One control for a question, whatever shape the question is. */
function buildControl(kind, choices, value) {
  if (choices && choices.length) {
    const wrap = document.createElement("div");
    wrap.className = "choices" + (choices.length > 8 ? " many" : "");
    let picked = value || "";
    for (const choice of choices) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = choice;
      if (choice === picked) button.classList.add("picked");
      button.addEventListener("click", () => {
        picked = choice;
        for (const other of wrap.children) other.classList.remove("picked");
        button.classList.add("picked");
      });
      wrap.appendChild(button);
    }
    return { node: wrap, read: () => picked, highlight: (label) => {
      for (const other of wrap.children) {
        other.classList.toggle("suggested", other.textContent === label);
      }
    } };
  }
  const input = document.createElement(kind === "textarea" ? "textarea" : "input");
  if (input.tagName === "INPUT") input.type = "text";
  input.value = value || "";
  return { node: input, read: () => input.value.trim(), highlight: () => {} };
}

/* -------------------------------------------------------------------- pages */

async function scan() {
  const tab = await browser({ type: "activeTab" });
  if (!tab) throw new Error("no tab is in focus");
  state.tab = tab;
  const observation = await browser({ type: "scan", tabId: tab.id });
  if (!observation) throw new Error("nothing could be read from that tab");
  state.observation = observation;
  return observation;
}

const KIND_NAMES = {
  application: "Application form",
  listing: "Job posting",
  board: "List of jobs",
  search: "Search results",
  sign_in: "Sign-in page",
  registration: "Account creation",
  confirmation: "Confirmation",
  unknown: "Unrecognised page",
};

async function planPage() {
  const plan = await post("/plan", state.observation);
  state.plan = plan;
  state.questionIndex = 0;

  const name = KIND_NAMES[state.observation.kind] || state.observation.kind;
  const adapter = plan.adapter && plan.adapter !== "generic" ? ` · ${plan.adapter}` : "";
  activity(name + adapter, plan.narration);

  for (const note of plan.notes || []) {
    if (/CAPTCHA|stopped|missing|sign in|account/i.test(note)) say(note, "warn");
  }
  setChecklist(plan.checklist);
  await renderQuestion();
  return plan;
}

/* --------------------------------------------------------------- questions */

function questions() {
  return (state.plan && state.plan.questions) || [];
}

function currentQuestion() {
  return questions()[state.questionIndex] || null;
}

async function renderQuestion() {
  const card = el("question");
  const question = currentQuestion();

  if (!question) {
    card.classList.add("hidden");
    el("idle").classList.add("hidden");
    updateCta();
    return;
  }
  card.classList.add("hidden");
  el("idle").classList.add("hidden");

  // Its choices may not be known yet. Open the control and read them before
  // asking anyone anything -- and if a saved answer fits one, do not ask at all.
  if (question.options_pending && !question._resolved) {
    question._resolved = true;
    showResolving(question);
    const settled = await resolveOptions(question);
    if (settled) return;
  }

  card.classList.remove("hidden");
  updateCta();
  el("question-remaining").textContent =
    questions().length - state.questionIndex - 1 > 0
      ? `${questions().length - state.questionIndex - 1} more`
      : "last one";
  el("question-label").textContent = question.label;
  el("question-reason").textContent = [question.section, question.reason]
    .filter(Boolean)
    .join(" · ");

  const host = el("question-input");
  host.innerHTML = "";
  const choices = (question.options || [])
    .map((o) => o.label)
    .filter((label) => label && label.trim() && !isPlaceholderLabel(label));
  const control = buildControl(
    choices.length ? "choice" : question.control === "textarea" ? "textarea" : "text",
    choices,
    ""
  );
  host.appendChild(control.node);
  card._read = control.read;

  const hint = el("question-hint");
  hint.classList.add("hidden");
  hint.classList.remove("suggested");

  if (choices.length && !question._suggested) {
    question._suggested = true;
    suggestFor(question, control);
  } else if (question._suggestion) {
    control.highlight(question._suggestion);
    showHint(question._suggestionWhy, true);
  }
}

/* A control's own "Choose" row is furniture, not an answer. */
const PLACEHOLDER_LABEL =
  /^(|-+|no selection|none selected|not selected|select|select.*|please select.*|choose|choose.*|pick one|--.*--|n\/?a)$/i;

function isPlaceholderLabel(label) {
  return PLACEHOLDER_LABEL.test(String(label || "").trim());
}

function showResolving(question) {
  const card = el("question");
  card.classList.remove("hidden");
  el("question-label").textContent = question.label;
  el("question-reason").textContent = "";
  el("question-remaining").textContent = "";
  const host = el("question-input");
  host.innerHTML = "";
  const box = document.createElement("div");
  box.className = "loading";
  box.innerHTML = '<span class="spinner"></span>';
  const text = document.createElement("span");
  text.textContent = "Opening the dropdown to read its options…";
  box.appendChild(text);
  host.appendChild(box);
  el("question-hint").classList.add("hidden");
}

function showHint(text, suggested) {
  const hint = el("question-hint");
  if (!text) {
    hint.classList.add("hidden");
    return;
  }
  hint.textContent = text;
  hint.classList.remove("hidden");
  hint.classList.toggle("suggested", Boolean(suggested));
}

/**
 * Open a control, read the options it owns, and see whether a saved answer
 * already covers one of them.
 *
 * Returns true when the question answered itself and the panel has moved on.
 */
async function resolveOptions(question) {
  try {
    const opened = await browser({
      type: "openOptions",
      tabId: state.tab.id,
      frameId: frameOf(question.fingerprint),
      fingerprint: question.fingerprint,
    });

    const ranked = await post("/options", {
      fingerprint: question.fingerprint,
      label: question.label,
      saved_value: question.saved_value || "",
      fact_key: question.fact_key || "",
      options: opened.options || [],
      source: opened.source || "none",
    });

    question.options = opened.options || [];

    if (ranked.chosen) {
      // Nothing to ask: the saved answer is one of the options this control
      // actually offers.
      say(`${question.label}: your saved answer fits — choosing "${ranked.chosen}".`);
      await applyAndReport({
        kind: "choose",
        fingerprint: question.fingerprint,
        option_label: ranked.chosen,
        value: ranked.chosen,
      });
      state.questionIndex += 1;
      await renderQuestion();
      return true;
    }

    if (!question.options.length) {
      question._note = ranked.note || "this control did not open a list of its own";
    }
  } catch (err) {
    question._note = "I could not open this control: " + err.message;
  }
  await renderQuestion();
  return true;
}

/** Ask the service for a suggestion among the page's own options. */
async function suggestFor(question, control) {
  try {
    const reply = await post("/suggest", {
      label: question.label,
      options: question.options || [],
      saved_value: question.saved_value || "",
      fact_key: question.fact_key || "",
    });
    if (currentQuestion() !== question) return;
    if (reply.suggested) {
      question._suggestion = reply.suggested;
      question._suggestionWhy =
        reply.from === "profile"
          ? `Suggested from your profile: ${reply.suggested}`
          : `Suggested: ${reply.suggested} — ${reply.why || "based on the question"}`;
      control.highlight(reply.suggested);
      showHint(question._suggestionWhy, true);
    } else if (reply.kind === "model_unavailable") {
      say(reply.why, "warn");
    } else if (reply.why) {
      showHint(reply.why, false);
    }
  } catch (err) {
    /* a suggestion is a convenience; its absence is not an error */
  }
}

async function answerQuestion(value, button, restoreLabel) {
  if (state.busy) return;
  const question = currentQuestion();
  if (!question) return;

  state.busy = true;
  setBusy(button, true);
  try {
    if (value) {
      const result = await applyAndReport({
        kind:
          question.control === "checkbox"
            ? "check"
            : (question.options || []).length
              ? "choose"
              : "fill",
        fingerprint: question.fingerprint,
        value: value,
        option_label: (question.options || []).length ? value : "",
      });

      if (result && result.outcome === "failed") {
        // Do not move on from something that did not go in.
        showHint("That did not go onto the page: " + result.evidence, false);
        return;
      }

      if (question.fact_key) {
        const field = fieldFor(question.fingerprint);
        await post("/profile/fact", {
          fact_key: question.fact_key,
          value: value,
          entry: (field && field.group_index) || 0,
        });
      } else {
        await post("/learn", {
          field: fieldFor(question.fingerprint) || {
            fingerprint: question.fingerprint,
            label: question.label,
          },
          value: value,
          host: new URL(state.observation.url).host,
          page_labels: (state.observation.fields || []).map((f) => f.label),
        });
      }
      flashDone(button, "Saved", restoreLabel);
    }
    state.questionIndex += 1;
    await renderQuestion();
  } catch (err) {
    say(String(err.message), "bad");
    showHint(String(err.message), false);
  } finally {
    state.busy = false;
    setBusy(button, false, restoreLabel);
  }
}

/* ----------------------------------------------------------------- filling */

async function applyAndReport(action) {
  const result = await browser({
    type: "perform",
    tabId: state.tab.id,
    frameId: frameOf(action.fingerprint),
    action: action,
  });
  state.lastFingerprint = action.fingerprint;
  state.results = state.results.filter((r) => r.fingerprint !== action.fingerprint).concat(result);
  reportOne(result);
  return result;
}

function reportOne(result) {
  if (!result) return;
  const label = result.label || result.fingerprint;
  if (result.outcome === "verified") {
    say(`${label}: verified — ${result.evidence}`);
  } else if (result.outcome === "accepted") {
    say(`${label}: the page took something else — ${result.evidence}`, "warn");
  } else if (result.outcome === "attempted") {
    say(`${label}: filled but not verifiable — please check it`, "warn");
  } else {
    say(`${label}: failed — ${result.evidence}`, "bad");
  }
}

async function fillPage() {
  if (!state.plan) await planPage();
  const actions = state.plan.actions || [];
  if (!actions.length) {
    activity("Nothing to fill", "None of these fields match what you have saved.");
    await renderQuestion();
    return;
  }

  const results = [];
  for (let i = 0; i < actions.length; i += 1) {
    activity(`Filling ${i + 1} of ${actions.length}`);
    progress(i, actions.length);
    try {
      results.push(await applyAndReport(actions[i]));
    } catch (err) {
      say(String(err.message), "bad");
    }
  }
  progress(actions.length, actions.length);

  // A page can change its own mind after we fill it: choosing a country
  // rebuilds the address block, and one of them set the State to the first
  // entry in the list on its own. Look again and fill whatever the page no
  // longer holds. Filling is idempotent, so anything already right is untouched
  // and an extra pass costs nothing.
  const loose = (text) => String(text || "").trim().toLowerCase();
  for (let pass = 2; pass <= 4; pass += 1) {
    const after = await scan();
    const replan = await post("/plan", after);
    const onPage = new Map((after.fields || []).map((f) => [f.fingerprint, f]));
    const wrong = (replan.actions || []).filter((action) => {
      const field = onPage.get(action.fingerprint);
      if (!field) return false;
      return loose(field.value) !== loose(action.option_label || action.value);
    });
    if (!wrong.length) break;

    activity(`Pass ${pass}: ${wrong.length} field(s) the page changed`);
    say(
      `The page changed ${wrong.length} field(s) after I filled them. Setting them again.`,
      "warn"
    );
    for (const action of wrong) {
      try {
        results.push(await applyAndReport(action));
      } catch (err) {
        say(String(err.message), "bad");
      }
    }
  }

  const summary = await post("/results", {
    observation: state.observation,
    results: state.results,
  });
  setChecklist(summary.checklist);
  state.plan = await post("/plan", state.observation);
  state.questionIndex = 0;
  progress(0, 0);
  activity(summary.summary, KIND_NAMES[state.observation.kind] || "");
  await renderQuestion();
}

/**
 * Work through a multi-step application without being asked to press Continue.
 *
 * It stops at the first thing it cannot answer, and it never presses final
 * Submit -- that is governed separately in Settings and is not implied by this.
 */
const MAX_STEPS = 15;

async function runToCompletion() {
  for (let step = 1; step <= MAX_STEPS; step += 1) {
    await fillPage();

    const outstanding = questions().filter((q) => q.required);
    if (outstanding.length) {
      activity(
        `Step ${step}: stopped for you`,
        `${outstanding.length} required question${outstanding.length > 1 ? "s" : ""} I cannot answer.`
      );
      return;
    }

    const submit = (state.observation.submit_controls || [])[0];
    const next = (state.observation.next_controls || [])[0];

    if (!next && submit) {
      if (state.submissionPolicy !== "auto") {
        activity("Ready to submit", `Everything filled. Press "${submit.text}" yourself.`);
        say(`Everything on this page is filled. Final submit is yours: "${submit.text}".`, "warn");
        return;
      }
      say(`Pressing "${submit.text}".`, "warn");
      await browser({ type: "click", tabId: state.tab.id, text: submit.text });
      const confirmation = await browser({ type: "confirmation", tabId: state.tab.id });
      say(
        confirmation
          ? `Submitted -- the page confirmed it: ${confirmation}`
          : "I pressed submit but the page showed no confirmation, so I have not recorded " +
            "this as submitted. Check the page.",
        confirmation ? undefined : "warn"
      );
      return;
    }

    if (!next) {
      activity("Nothing further to press", "This looks like the end of what I can do here.");
      return;
    }

    activity(`Step ${step}: continuing`, `Pressing "${next.text}".`);
    const moved = await browser({ type: "click", tabId: state.tab.id, text: next.text });
    if (!moved || moved.outcome === "failed") {
      say(`"${next.text}" did not move the page on: ${(moved || {}).evidence || "no change"}`, "bad");
      return;
    }

    const before = state.observation.signature;
    await scan();
    if (state.observation.signature === before) {
      // The saved run's stall guard covers the service side; this stops the
      // panel spinning on a page that will not move.
      say("The page has not changed after pressing continue, so I have stopped.", "warn");
      return;
    }
    await planPage();
  }
  say(`Stopped after ${MAX_STEPS} steps rather than going round forever.`, "warn");
}

/* ------------------------------------------------------------------ report */

const DONE_STATES = new Set(["verified", "attempted", "skipped"]);
const MARKS = {
  verified: "✓",
  attempted: "!",
  needs_you: "!",
  failed: "×",
  skipped: "–",
};

function setChecklist(items) {
  state.checklist = items || [];
  const needs = state.checklist.filter((i) => i.state === "needs_you" || i.state === "failed");
  const done = state.checklist.filter((i) => DONE_STATES.has(i.state));

  el("review-card").classList.toggle("hidden", needs.length === 0);
  el("needs-heading").textContent = `Needs you (${needs.length})`;
  fillReport(el("needs-list"), needs);

  el("done-card").classList.toggle("hidden", done.length === 0);
  const verified = done.filter((i) => i.state === "verified").length;
  el("done-heading").textContent =
    `Completed (${verified})` + (done.length > verified ? ` · ${done.length - verified} left blank` : "");
  fillReport(el("done-list"), done);

  updateCta();
}

/** One row per field, showing the whole question rather than a truncation. */
function fillReport(list, items) {
  list.innerHTML = "";
  for (const item of items) {
    const row = document.createElement("li");
    row.title = "Find this field on the page";

    const mark = document.createElement("span");
    mark.className = "mark " + item.state;
    mark.textContent = MARKS[item.state] || "·";
    row.appendChild(mark);

    const label = document.createElement("span");
    label.className = "item-label";
    label.textContent = item.label + (item.required ? " *" : "");
    const detail = document.createElement("span");
    detail.className = "item-value";
    detail.textContent = [item.section, item.value || item.detail || ""]
      .filter(Boolean)
      .join(" · ");
    label.appendChild(detail);
    row.appendChild(label);

    row.addEventListener("click", () =>
      browser({
        type: "highlight",
        tabId: state.tab.id,
        frameId: frameOf(item.fingerprint),
        fingerprint: item.fingerprint,
      }).catch((err) => say(String(err.message), "bad"))
    );
    list.appendChild(row);
  }
}

/**
 * The one place to look for what happens next.
 *
 * It never offers to submit unless that was set deliberately in Settings.
 */
function updateCta() {
  const cta = el("cta");
  const note = el("cta-note");
  cta.disabled = false;

  const outstanding = questions().filter((q) => q.required).length;
  const next = ((state.observation || {}).next_controls || [])[0];
  const submit = ((state.observation || {}).submit_controls || [])[0];

  if (!state.observation || (state.observation.fields || []).length === 0) {
    cta.textContent = "Scan this page";
    note.textContent = "";
    cta._action = "scan";
    return;
  }
  if (outstanding) {
    cta.textContent = `Answer ${outstanding} question${outstanding > 1 ? "s" : ""}`;
    note.textContent = "I have filled everything else I can.";
    cta._action = "focus";
    return;
  }
  if (!state.plan || !(state.plan.actions || []).length) {
    if (next) {
      cta.textContent = `Continue application ▸`;
      note.textContent = `Presses "${next.text}".`;
      cta._action = "next";
      return;
    }
    if (submit) {
      if (state.submissionPolicy === "auto") {
        cta.textContent = "Submit application ▸";
        note.textContent = "You set submitting to happen automatically.";
        cta._action = "submit";
      } else {
        cta.textContent = `Press "${submit.text}" yourself`;
        note.textContent = "I do not press final submit. Change that in Settings if you want to.";
        cta.disabled = true;
        cta._action = "none";
      }
      return;
    }
    cta.textContent = "Rescan this page";
    cta._action = "scan";
    note.textContent = "";
    return;
  }
  cta.textContent = "Fill this page";
  note.textContent = `${state.plan.actions.length} field(s) I can fill from what you saved.`;
  cta._action = "fill";
}

async function runCta() {
  const cta = el("cta");
  if (state.busy) return;
  const action = cta._action;
  if (action === "focus") {
    el("question").scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  state.busy = true;
  setBusy(cta, true);
  const restore = cta.textContent;
  try {
    if (action === "scan") {
      await scan();
      state.busy = false;
      await planPage();
    } else if (action === "fill") {
      state.busy = false;
      if (state.autoContinue) await runToCompletion();
      else await fillPage();
    } else if (action === "next" || action === "submit") {
      const control =
        action === "next"
          ? state.observation.next_controls[0]
          : state.observation.submit_controls[0];
      const moved = await browser({ type: "click", tabId: state.tab.id, text: control.text });
      if (action === "submit") {
        const confirmation = await browser({ type: "confirmation", tabId: state.tab.id });
        say(
          confirmation
            ? `Submitted -- the page confirmed it: ${confirmation}`
            : "I pressed submit but the page showed no confirmation, so I have not recorded " +
              "this as submitted. Check the page.",
          confirmation ? undefined : "warn"
        );
      } else if (!moved || moved.outcome === "failed") {
        say(`"${control.text}" did not move the page on.`, "bad");
      }
      state.busy = false;
      await scan();
      await planPage();
    }
  } catch (err) {
    say(String(err.message), "bad");
  } finally {
    state.busy = false;
    setBusy(cta, false, restore);
    updateCta();
  }
}

function toggle(buttonId, bodyId) {
  const button = el(buttonId);
  const body = el(bodyId);
  button.addEventListener("click", () => {
    const open = body.classList.toggle("hidden");
    button.setAttribute("aria-expanded", String(!open));
    if (bodyId === "log" && !open) {
      state.unread = 0;
      el("log-badge").classList.add("hidden");
    }
  });
}

/* -------------------------------------------------------------------- wiring */

el("run").addEventListener("click", async () => {
  if (state.busy) return;
  state.running = !state.running;
  el("run").textContent = state.running ? "Stop" : "Start";
  el("run").classList.toggle("running", state.running);
  if (!state.running) {
    await post("/run", { command: "stop" });
    activity("Stopped");
    progress(0, 0);
    return;
  }
  state.busy = true;
  setBusy(el("run"), true);
  try {
    const observation = await scan();
    await post("/run", { command: "start", url: observation.url });
    setBusy(el("run"), false, "Stop");
    state.busy = false;
    await planPage();
    if (observation.kind === "application") {
      if (state.autoContinue) await runToCompletion();
      else await fillPage();
    }
  } catch (err) {
    say(String(err.message), "bad");
    activity("Stopped after an error", String(err.message));
    state.running = false;
    el("run").textContent = "Start";
    el("run").classList.remove("running");
  } finally {
    state.busy = false;
    setBusy(el("run"), false, state.running ? "Stop" : "Start");
  }
});

el("rescan").addEventListener("click", async () => {
  const button = el("rescan");
  if (state.busy) return;
  state.busy = true;
  setBusy(button, true);
  try {
    await scan();
    await planPage();
  } catch (err) {
    say(String(err.message), "bad");
  } finally {
    state.busy = false;
    setBusy(button, false, "Rescan");
  }
});

el("fill").addEventListener("click", async () => {
  const button = el("fill");
  if (state.busy) return;
  state.busy = true;
  setBusy(button, true);
  try {
    if (!state.observation) await scan();
    state.busy = false;
    setBusy(button, false, "Fill this page");
    await fillPage();
  } catch (err) {
    say(String(err.message), "bad");
  } finally {
    state.busy = false;
    setBusy(button, false, "Fill this page");
  }
});

el("auto-continue").addEventListener("change", async (event) => {
  state.autoContinue = event.target.checked;
  el("auto-note").textContent = state.autoContinue
    ? "I will press Continue myself and stop at anything I cannot answer."
    : "I will stop at anything I cannot answer.";
  try {
    await put("/settings", { auto_advance: state.autoContinue });
  } catch (err) {
    say(String(err.message), "bad");
  }
});

el("cta").addEventListener("click", runCta);
el("settings").addEventListener("click", () => chrome.runtime.openOptionsPage());
el("onboarding-later").addEventListener("click", () => el("onboarding").classList.add("hidden"));
el("resume-file").addEventListener("click", (event) => event.stopPropagation());

el("question-save").addEventListener("click", () => {
  const read = el("question")._read;
  const value = read ? read() : "";
  if (!value) {
    showHint("Pick an option, or press Skip to leave it blank.", false);
    return;
  }
  answerQuestion(value, el("question-save"), "Save & next");
});

el("question-skip").addEventListener("click", () => {
  const question = currentQuestion();
  if (question) say(`Left "${question.label}" blank.`);
  answerQuestion("", el("question-skip"), "Skip");
});

el("question-show").addEventListener("click", () => {
  const question = currentQuestion();
  if (!question) return;
  browser({
    type: "highlight",
    tabId: state.tab.id,
    frameId: frameOf(question.fingerprint),
    fingerprint: question.fingerprint,
  }).catch((err) => say(String(err.message), "bad"));
});

el("resume-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  el("resume-result").textContent = "Reading…";
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetch(SERVICE + "/resume", { method: "POST", body: form });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "could not read that file");
    el("resume-result").textContent =
      `Read ${body.education.length} education and ${body.experience.length} work entries. ` +
      "Check them in Settings.";
    for (const note of body.notes) say(note, "warn");
    await refreshOnboarding();
  } catch (err) {
    el("resume-result").textContent = String(err.message);
  }
});

el("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = el("chat-input").value.trim();
  if (!text || state.busy) return;
  el("chat-input").value = "";
  youSaid(text);
  el("log").classList.remove("hidden");
  el("log-toggle").setAttribute("aria-expanded", "true");

  state.busy = true;
  setBusy(el("chat-send"), true);
  try {
    if (!state.observation) await scan();
    const outcome = await post("/chat", {
      text: text,
      fields: state.observation.fields || [],
      last_fingerprint: state.lastFingerprint,
      pending_fingerprint: (currentQuestion() || {}).fingerprint || "",
    });
    say(outcome.message);

    if (outcome.kind === "action" && outcome.action) {
      state.busy = false;
      await applyAndReport(outcome.action);
      await planPage();
    } else if (outcome.kind === "choices") {
      renderChoiceCard(outcome);
    } else if (outcome.kind === "control" && outcome.value === "stop") {
      state.running = false;
      el("run").textContent = "Start";
      el("run").classList.remove("running");
      await post("/run", { command: "stop" });
    }
  } catch (err) {
    say(String(err.message), "bad");
  } finally {
    state.busy = false;
    setBusy(el("chat-send"), false, "Send");
  }
});

function renderChoiceCard(outcome) {
  const wrap = document.createElement("div");
  wrap.className = "line choices";
  for (const option of outcome.options) {
    const button = document.createElement("button");
    button.textContent = option.label;
    button.addEventListener("click", async () => {
      if (state.busy) return;
      state.busy = true;
      setBusy(button, true);
      try {
        await applyAndReport({
          kind: "choose",
          fingerprint: outcome.fingerprint,
          option_label: option.label,
          value: option.label,
        });
        wrap.remove();
        await planPage();
      } finally {
        state.busy = false;
      }
    });
    wrap.appendChild(button);
  }
  el("log").appendChild(wrap);
  el("log").scrollTop = el("log").scrollHeight;
}

toggle("done-toggle", "done-body");
toggle("log-toggle", "log");

/* --------------------------------------------------------------------- boot */

(async function start() {
  const health = await refreshHealth();
  if (!health) return;
  try {
    const settings = await service("/settings");
    state.autoContinue = Boolean(settings.auto_advance);
    state.submissionPolicy = settings.submission_policy || "confirm";
    el("auto-continue").checked = state.autoContinue;
    if (state.autoContinue) {
      el("auto-note").textContent =
        "I will press Continue myself and stop at anything I cannot answer.";
    }
  } catch (err) {
    /* the health check already reported the service being down */
  }
  await refreshOnboarding();
  try {
    await scan();
    await planPage();
  } catch (err) {
    activity("Open a job page", "Then press Start, or Rescan if it is already open.");
  }
})();
