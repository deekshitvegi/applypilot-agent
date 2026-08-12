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

/** Controls that are answered by picking, never by typing. */
const CHOICE_CONTROLS = new Set(["radio", "select", "multiselect", "combobox", "listbox"]);

/* How a control has to be worked, when the page said so plainly enough for
   the scan to tell. It is a better answer than the element type: two controls
   both calling themselves a combobox can want opposite treatment, and one of
   them is a calendar wearing a text box. */
const PICKED_OPERATIONS = new Set([
  "list_present",
  "list_on_open",
  "type_to_search",
  "choice_group",
]);
const TYPED_OPERATIONS = new Set(["free_text", "long_text"]);

function isChoice(control, operation) {
  const how = String(operation || "").toLowerCase();
  if (PICKED_OPERATIONS.has(how)) return true;
  if (TYPED_OPERATIONS.has(how)) return false;
  return CHOICE_CONTROLS.has(String(control || "").toLowerCase());
}

/**
 * How the control behind a question has to be worked.
 *
 * A question is a message about a field; the field on the page is where the
 * answer lives. Read it from the page when it is still there, because that is
 * the thing that knows, and fall back to the question when it is not.
 */
function howOf(question) {
  if (!question) return "";
  const live = fieldFor(question.fingerprint);
  return (live && live.operation) || question.operation || "";
}

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
  autoAttach: true,
  //: How many things the panel is doing right now. The page watcher stays out
  //: of the way while any of them are in flight: filling a form changes the
  //: page, and a watcher that reacts to our own work re-plans on top of it and
  //: nothing ever finishes.
  working: 0,
  lastPlannedSignature: "",
  //: The cheap reading the watcher compares against, so a page that is not
  //: doing anything costs nothing to watch.
  lastShape: "",
  stableSignature: "",
  stableTicks: 0,
  submissionPolicy: "confirm",
  primaryResumeId: "",
  keepPageAnswers: false,
  //: Everything that happened on this page, in order, with the time.
  //:
  //: A report used to be a photograph: the state of the page at the moment
  //: somebody pressed Save. The failures worth reporting are not states. They
  //: are sequences -- a question answered three times that keeps coming back,
  //: an instruction typed into the chat that changed nothing, an answer taken
  //: and then not kept. All of those look identical to a working page in a
  //: photograph, which is why they went unreported for so long.
  journal: [],
  //: question (lowercased) -> how many times it has been put to somebody.
  asked: new Map(),
};

//: Long enough to reconstruct a session; short enough not to grow without end
//: on a form somebody leaves open all afternoon.
const JOURNAL_LIMIT = 400;

/**
 * Write down one thing that happened, for the report.
 *
 * Kept separate from the Activity log, which is prose for reading as you go.
 * This is a record with a shape, so a sequence can be counted afterwards
 * rather than read.
 */
function note(kind, what, extra) {
  state.journal.push(
    Object.assign({ at: new Date().toISOString(), kind: kind, what: what }, extra || {})
  );
  if (state.journal.length > JOURNAL_LIMIT) state.journal.shift();
}

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

/**
 * Ask the service worker to do something to the page.
 *
 * With a deadline. A reply that never comes leaves a button spinning for as
 * long as anyone is willing to watch it, and there is no way back from that
 * except reloading the extension -- which is exactly what happened: Start went
 * round and round for minutes with nothing behind it.
 */
const BROWSER_TIMEOUT = 30000;

function browser(message, timeout) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(new Error(`the page did not answer in time (${message.type})`));
    }, timeout || BROWSER_TIMEOUT);
    chrome.runtime.sendMessage(message, (reply) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
      if (!reply || !reply.ok) return reject(new Error((reply && reply.error) || "no reply"));
      resolve(reply.value);
    });
  });
}

/**
 * Wait until the page is actually on screen.
 *
 * A background tab stops laying itself out, so every control measures as
 * invisible and every action comes back "the control is no longer on the page".
 * Switching windows produced a screenful of those.
 */
async function waitForTheTab() {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try {
      const visible = await browser({ type: "visible", tabId: state.tab.id });
      if (visible) {
        if (attempt) activity("Carrying on", "");
        return true;
      }
    } catch (err) {
      return true; // cannot tell; better to try than to stall
    }
    if (!attempt) {
      activity("Waiting for that tab", "I will carry on when it is on screen again.");
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
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

/** Keep asking until it is true, or until the time is up. */
async function until(check, timeout) {
  const started = Date.now();
  for (;;) {
    if (await check()) return true;
    if (Date.now() - started > timeout) return false;
    const waited = Date.now() - started;
    await new Promise((resolve) => setTimeout(resolve, waited < 2000 ? 300 : 1000));
  }
}

/**
 * Scroll to a field and flash it.
 *
 * A courtesy, not a step of the run: it gets a short deadline and its failure
 * is never reported. Sharing the long one filled the activity list with "the
 * page did not answer in time (highlight)" while the run itself was fine.
 */
function showOnPage(fingerprint) {
  browser(
    {
      type: "highlight",
      tabId: state.tab.id,
      frameId: frameOf(fingerprint),
      fingerprint: fingerprint,
    },
    4000
  ).catch(() => {});
}

/** Run something, counting it as work in flight for as long as it takes. */
async function inFlight(fn) {
  state.working += 1;
  try {
    return await fn();
  } finally {
    state.working -= 1;
  }
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
function buildControl(kind, choices, value, many) {
  if (choices && choices.length) {
    const wrap = document.createElement("div");
    wrap.className = "choices" + (choices.length > 8 ? " many" : "");
    // "Which of these have you used?" is not a question with one answer.
    // Offering it as one meant picking OpenAI and losing Anthropic, on a
    // question whose whole point is that several are true at once.
    const picked = new Set(value ? [value] : []);
    for (const choice of choices) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = choice;
      if (picked.has(choice)) button.classList.add("picked");
      button.addEventListener("click", () => {
        if (many) {
          if (picked.has(choice)) picked.delete(choice);
          else picked.add(choice);
        } else {
          picked.clear();
          picked.add(choice);
          for (const other of wrap.children) other.classList.remove("picked");
        }
        button.classList.toggle("picked", picked.has(choice));
      });
      wrap.appendChild(button);
    }
    return {
      node: wrap,
      read: () => Array.from(picked).join(", "),
      readAll: () => Array.from(picked),
      highlight: (label) => {
        for (const other of wrap.children) {
          other.classList.toggle("suggested", other.textContent === label);
        }
      },
    };
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

async function planPage(afterContinue) {
  // Only a press of Continue can count towards the stall guard. Filling a page
  // re-plans it several times over by design.
  const where = afterContinue ? "/plan?after_continue=true" : "/plan";
  const plan = await post(where, state.observation);
  state.plan = plan;
  state.questionIndex = 0;
  state.lastPlannedSignature = state.observation.signature || "";

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

/**
 * How a question is counted across a session.
 *
 * Not by fingerprint: an application that rebuilds itself hands out new ones,
 * and the whole point is to notice the same question coming round again after
 * it was answered. Its own words are what stays the same.
 */
function askKey(question) {
  return (question.label || question.fingerprint || "").trim().toLowerCase();
}

function countAsk(question) {
  const key = askKey(question);
  if (!key) return 1;
  const seen = (state.asked.get(key) || 0) + 1;
  state.asked.set(key, seen);
  note("asked", question.label || "", {
    times: seen,
    reason: question.reason || "",
    required: Boolean(question.required),
  });
  return seen;
}

/**
 * Say when an answer was taken but not kept.
 *
 * The service declines to remember some answers, for fourteen reasons that are
 * each defensible -- a voluntary question, a value that is not one of the
 * control's own options, a number that is really an option id. All of them
 * were silent. The panel said "Saved", nothing was saved, and the next scan
 * asked the same question again: the exact loop somebody hits when they answer
 * a question three times and it keeps coming back.
 *
 * A snapshot report cannot show this, so it is written down as it happens.
 */
function noteNotRemembered(question, reason) {
  const why = reason || "no reason given";
  note("not_remembered", question.label || "", { reason: why });
  log(`answered but not remembered -- ${question.label}: ${why}`);
  showHint(
    `Filled in, but not remembered for next time: ${why}. ` +
      "It will be asked again on the next form.",
    false
  );
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

  // A form asking for the resume already on file does not need to ask anyone.
  if (
    question.control === "file" &&
    state.autoAttach &&
    state.primaryResumeId &&
    /resume|cv|curriculum/i.test(question.fact_key || question.label) &&
    !question._attached
  ) {
    question._attached = true;
    if (await attachResume(question)) return;
  }

  // Its choices may not be known yet, or the ones we saw may be stale: a
  // dependent dropdown is usually read before the field it depends on is
  // filled. Either way, open it and look again before asking anyone anything.
  const staleOptions =
    question.saved_value &&
    /options offered here match/.test(question.reason || "");
  if ((question.options_pending || staleOptions) && !question._resolved) {
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

  // How many times this exact question has been put to somebody in this
  // session. A report is a photograph of one moment: asked once and asked six
  // times look identical in it, and being asked six times is the complaint.
  // Counting here is the only place that can tell them apart.
  const asked = countAsk(question);
  const again =
    asked > 1 ? `asked ${asked} times now -- answering it is not sticking` : "";
  el("question-reason").textContent = [question.section, question.reason, again]
    .filter(Boolean)
    .join(" · ");
  el("question-reason").classList.toggle("warn-text", asked > 1);

  const host = el("question-input");
  host.innerHTML = "";
  // A choice is never handed back as a text box. If the question arrived
  // without its options -- whatever emptied them -- the control on the page
  // still has them, and they are read from there rather than giving up and
  // offering a box to type into. Typing the exact wording of a radio button
  // does not select that radio button; it does nothing at all.
  const live = fieldFor(question.fingerprint);
  let offered = (question.options || []).length
    ? question.options
    : (isChoice(question.control, howOf(question)) && live ? live.options || [] : []);
  // A tick box is answered by ticking it or not, so those are the two things
  // to offer. It has no options of its own, which sent it down the same path
  // as a free-text field -- and an agreement came back as a box to type into,
  // which is not how anyone accepts an arbitration clause.
  if (!offered.length && question.control === "checkbox") {
    offered = [{ label: "Yes" }, { label: "No" }];
  }
  const choices = offered
    .map((o) => o.label)
    .filter((label) => label && label.trim() && !isPlaceholderLabel(label));
  // A dropdown is never handed back as a text box. Where its choices could not
  // be read -- a select that holds nothing until the page fills it, a picker
  // that only answers once opened -- the honest thing is to say so and offer to
  // show you the control, because typing into a dropdown does nothing at all.
  if (isChoice(question.control, howOf(question)) && !choices.length) {
    const note = document.createElement("p");
    note.className = "sub";
    note.textContent =
      "This is a dropdown and I could not read what it offers. Open it on the " +
      "page and choose, and I will carry on from what you pick.";
    host.appendChild(note);
    card._read = () => "";
    card._readAll = () => [];
    el("question-save").classList.add("hidden");
    showOnPage(question.fingerprint);
    return;
  }
  el("question-save").classList.remove("hidden");

  const control = buildControl(
    choices.length ? "choice" : question.control === "textarea" ? "textarea" : "text",
    choices,
    "",
    question.control === "multiselect"
  );
  host.appendChild(control.node);
  card._read = control.read;
  card._readAll = control.readAll;

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

/* A control's own "Choose" row is furniture, not an answer.
 *
 * Read from the one shared list. The copy that used to live here fell behind
 * the other two and tested the label exactly as written, so the em dashes a
 * form decorates with defeated it: "— Make a Selection —" was not "make a
 * selection", matched nothing, and was offered as an answer to pick. Pressing
 * it did nothing, because it is not an answer -- it is the control asking. */
function isPlaceholderLabel(label) {
  return ApplyPilotPlaceholders.looksLikePlaceholder(label);
}

/** Put the resume on file into a file control, and verify it went in. */
async function attachResume(question) {
  try {
    const document_ = await service("/documents/" + state.primaryResumeId + "/content");
    const result = await browser({
      type: "attach",
      tabId: state.tab.id,
      frameId: frameOf(question.fingerprint),
      fingerprint: question.fingerprint,
      base64: document_.base64,
      filename: document_.filename,
      mime: document_.mime,
    });
    state.results = state.results
      .filter((r) => r.fingerprint !== question.fingerprint)
      .concat(result);
    reportOne(result);
    if (result && (result.outcome === "verified" || result.outcome === "accepted")) {
      state.questionIndex += 1;
      await renderQuestion();
      return true;
    }
  } catch (err) {
    say("I could not attach your resume: " + err.message, "bad");
  }
  return false;
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
  return inFlight(() => resolveOptionsInner(question));
}

async function resolveOptionsInner(question) {
  try {
    const opened = await browser({
      type: "openOptions",
      tabId: state.tab.id,
      frameId: frameOf(question.fingerprint),
      fingerprint: question.fingerprint,
      // A search-as-you-type control offers nothing at all until something is
      // typed into it. What we are looking for is the saved answer, so that is
      // what gets typed.
      filter: question.saved_value || "",
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
      say(`${question.label}: ${question._note}`, "warn");
    } else if (question.saved_value) {
      // Say what was actually on offer, so a mismatch is diagnosable rather
      // than just disappointing.
      const shown = question.options.slice(0, 6).map((o) => o.label).join(", ");
      say(
        `${question.label}: none of the ${question.options.length} options match ` +
          `"${question.saved_value}". Saw: ${shown}` +
          (question.options.length > 6 ? ", …" : ""),
        "warn"
      );
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
  return inFlight(() => answerQuestionInner(value, button, restoreLabel));
}

async function answerQuestionInner(value, button, restoreLabel) {
  if (state.busy) return;
  const question = currentQuestion();
  if (!question) return;

  state.busy = true;
  setBusy(button, true);
  try {
    if (value) {
      const picking = isChoice(question.control, howOf(question));
      // "Which of these have you used?" can be true of several at once, so
      // each pick is its own action against the same control. Ticking is
      // idempotent, so nothing already ticked gets toggled back off.
      const wanted =
        question.control === "multiselect" && el("question")._readAll
          ? el("question")._readAll()
          : [value];

      let result = null;
      for (const one of wanted) {
        result = await applyAndReport({
          kind: question.control === "checkbox" ? "check" : picking ? "choose" : "fill",
          fingerprint: question.fingerprint,
          value: one,
          option_label: picking ? one : "",
        });
        if (result && result.outcome === "failed") break;
      }

      note("answered", question.label || "", {
        value: value,
        outcome: (result && result.outcome) || "none",
        evidence: (result && result.evidence) || "",
      });

      if (result && result.outcome === "failed") {
        // Do not move on from something that did not go in.
        showHint("That did not go onto the page: " + result.evidence, false);
        return;
      }

      if (question.fact_key) {
        const field = fieldFor(question.fingerprint);
        try {
          await post("/profile/fact", {
            fact_key: question.fact_key,
            value: value,
            entry: (field && field.group_index) || 0,
          });
        } catch (err) {
          // A fact that will not hold this value refuses it. Silently, until
          // now: the answer went on the page, nothing was kept, and the next
          // form asked again.
          noteNotRemembered(question, String((err && err.message) || err));
        }
      } else {
        // The service can decline to remember this, and used to do it in
        // silence: fourteen reasons, all sound, none of which ever reached the
        // panel. It flashed "Saved", the next scan found nothing saved, and
        // asked the same question again -- and again, for as long as anyone
        // kept answering it. Saying so is the difference between a rule and a
        // loop.
        const kept = await post("/learn", {
          field: fieldFor(question.fingerprint) || {
            fingerprint: question.fingerprint,
            label: question.label,
          },
          value: value,
          host: new URL(state.observation.url).host,
          page_labels: (state.observation.fields || []).map((f) => f.label),
        });
        if (kept && kept.learned === false) {
          noteNotRemembered(question, kept.reason || "");
        }
      }
      flashDone(button, "Saved", restoreLabel);

      // An answer can bring a whole question into existence: choosing "No" for
      // one EEO question adds a required Race category below it. Working
      // through a list captured before the answer never sees it, and the step
      // is then continued past with a required field nobody was ever asked
      // about. Look again whenever an answer went onto the page.
      const before = state.observation.signature;
      await scan();
      if (state.observation.signature !== before) {
        await planPage();
        await renderQuestion();
        return;
      }
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

/**
 * A page's worth of actions in one trip into the page.
 *
 * Each field used to cost two messages -- one to ask whether the tab was on
 * screen, one to do the thing -- and once the work inside the page was made
 * fast, that traffic was most of what a fill cost. They still run in order,
 * through the same code, and each result is still read back from the page.
 */
async function applyAll(actions) {
  if (!actions.length) return [];
  await waitForTheTab();
  const withFrames = actions.map((action) =>
    Object.assign({}, action, { frame: frameOf(action.fingerprint) })
  );
  let results;
  try {
    results = await browser(
      { type: "performMany", tabId: state.tab.id, actions: withFrames },
      Math.max(BROWSER_TIMEOUT, actions.length * 2500)
    );
  } catch (err) {
    // Loud, and named for what it cost. "the page did not answer in time" on
    // its own reads like a hiccup; it is every field on the page not being
    // filled, and the panel went on showing them as ready to fill afterwards.
    say(
      `None of the ${actions.length} field(s) were filled: ${err.message}`,
      "bad"
    );
    activity("Nothing was filled", err.message);
    return [];
  }
  for (const result of results) {
    state.lastFingerprint = result.fingerprint;
    state.results = state.results
      .filter((r) => r.fingerprint !== result.fingerprint)
      .concat(result);
    reportOne(result);
  }
  return results;
}

/**
 * The same field after the page has rebuilt itself, or null.
 *
 * A fingerprint is derived from what a control looks like, so a page that
 * replaces its own markup mints new ones for the very same boxes. Matching on
 * what the form calls the field is the only thing left that survives, and it
 * is required to agree on the section and the kind of control too -- a page
 * with two boxes called "Type" would otherwise hand back the wrong one.
 */
function sameFieldAfterRebuild(before) {
  if (!before) return null;
  const name = (f) => (f.display_label || f.label || "").trim().toLowerCase();
  const wanted = name(before);
  if (!wanted) return null;
  const matches = ((state.observation && state.observation.fields) || []).filter(
    (f) =>
      name(f) === wanted &&
      (f.section || "") === (before.section || "") &&
      f.control === before.control &&
      (f.group_index || 0) === (before.group_index || 0)
  );
  return matches.length === 1 ? matches[0] : null;
}

async function applyAndReport(action) {
  await waitForTheTab();
  let result = await browser({
    type: "perform",
    tabId: state.tab.id,
    frameId: frameOf(action.fingerprint),
    action: action,
  });

  // A page that rebuilds itself takes every fingerprint with it.
  //
  // This form offers to read your resume and says plainly that it will replace
  // what is already in the form. When it does, everything planned beforehand
  // points at controls that no longer exist, and every attempt came back "the
  // control is no longer on the page" -- including pressing Save on a question,
  // which left the answer unsaveable however many times it was pressed.
  //
  // So look again and find the same field in the page as it is now. This is
  // not a second guess at what to do: the value is unchanged, only where it
  // goes. If the fresh scan cannot name exactly one field the same way, the
  // failure stands.
  if (result && result.outcome === "failed" && /no longer on the page/.test(result.evidence || "")) {
    const before = fieldFor(action.fingerprint);
    await scan();
    const now = sameFieldAfterRebuild(before);
    if (now && now.fingerprint !== action.fingerprint) {
      say(`The page rebuilt itself; found "${now.label}" again and retrying.`, "warn");
      action = Object.assign({}, action, { fingerprint: now.fingerprint });
      result = await browser({
        type: "perform",
        tabId: state.tab.id,
        frameId: frameOf(action.fingerprint),
        action: action,
      });
    }
  }

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
  return inFlight(fillPageInner);
}

async function fillPageInner() {
  if (!state.plan) await planPage();

  // Make room for every entry on file before filling, so the second school and
  // the earlier jobs have somewhere to go.
  try {
    await addMissingEntries();
    if (state.observation) await planPage();
  } catch (err) {
    say("I could not add the extra entries: " + err.message, "warn");
  }

  const actions = state.plan.actions || [];
  if (!actions.length) {
    activity("Nothing to fill", "None of these fields match what you have saved.");
    await renderQuestion();
    return;
  }

  activity(`Filling ${actions.length} field(s)`);
  progress(1, 3);
  const results = await applyAll(actions);
  progress(actions.length, actions.length);
  note("filled", `${actions.length} field(s)`, {
    verified: results.filter((r) => r && r.outcome === "verified").length,
    failed: results.filter((r) => r && r.outcome === "failed").length,
  });

  // A choice can bring a whole field to life: State holds nothing but "Choose"
  // until a Country is picked, and no amount of retrying State first will get
  // Texas into it. Once the choices are in, look again -- the fields that
  // depend on them have options now.
  const hadChoices = actions.some((a) => a.kind === "choose");
  if (hadChoices) {
    await scan();
    const dependent = await post("/plan", state.observation);
    const onPage = new Map((state.observation.fields || []).map((f) => [f.fingerprint, f]));
    const nowAnswerable = (dependent.actions || []).filter((action) => {
      const field = onPage.get(action.fingerprint);
      const wanted = (action.option_label || action.value || "").trim().toLowerCase();
      return field && (field.value || "").trim().toLowerCase() !== wanted;
    });
    results.push(...(await applyAll(nowAnswerable)));
  }

  // A page can change its own mind after we fill it: choosing a country
  // rebuilds the address block, and one of them set the State to the first
  // entry in the list on its own. Look again and fill whatever the page no
  // longer holds. Filling is idempotent, so anything already right is untouched
  // and an extra pass costs nothing.
  const loose = (text) => String(text || "").trim().toLowerCase();
  const refused = new Set(
    results
      .filter((r) => r && r.outcome === "failed")
      .map((r) => r.fingerprint + "|" + loose(r.requested))
  );
  for (let pass = 2; pass <= 4; pass += 1) {
    const after = await scan();
    const replan = await post("/plan", after);
    const onPage = new Map((after.fields || []).map((f) => [f.fingerprint, f]));
    const wrong = (replan.actions || []).filter((action) => {
      const field = onPage.get(action.fingerprint);
      if (!field) return false;
      const wanted = action.option_label || action.value;
      // A control that has already refused this value will refuse it again;
      // trying four more times only costs time.
      if (refused.has(action.fingerprint + "|" + loose(wanted))) return false;
      return loose(field.value) !== loose(wanted);
    });
    if (!wrong.length) break;

    activity(`Pass ${pass}: ${wrong.length} field(s) the page changed`);
    say(
      `The page changed ${wrong.length} field(s) after I filled them. Setting them again.`,
      "warn"
    );
    results.push(...(await applyAll(wrong)));
  }

  const summary = await post("/results", {
    observation: state.observation,
    results: state.results,
  });
  setChecklist(summary.checklist);
  // Whatever the page turned down is asked about rather than tried again. A
  // control that refused an answer refuses it every time, and a required field
  // failing over and over without ever being put to you is a dead end you can
  // see but cannot clear.
  const turnedDown = state.results
    .filter((r) => r && r.outcome === "failed")
    .map((r) => r.fingerprint);
  state.plan = await post(
    "/plan" + (turnedDown.length ? `?refused=${encodeURIComponent(turnedDown.join(","))}` : ""),
    state.observation
  );
  state.questionIndex = 0;
  progress(0, 0);
  activity(summary.summary, KIND_NAMES[state.observation.kind] || "");
  await renderQuestion();
}

/**
 * Press "Add another" until the page has room for every entry on file.
 *
 * A form that starts with one education block and one job will only ever hold
 * the most recent of each, however many are saved.
 */
async function addMissingEntries() {
  const profile = await service("/profile");
  const wanted = { education: profile.education.length, experience: profile.experience.length };

  for (const [kind, total] of Object.entries(wanted)) {
    if (total <= 1) continue;
    const pattern = kind === "education" ? /educat|school|degree|academic/i : /work|employ|experien|job/i;

    for (let attempt = 0; attempt < total - 1; attempt += 1) {
      const blocks = blockCount(pattern);
      if (blocks >= total) break;

      const control = (state.observation.add_controls || []).find((c) => pattern.test(c.text));
      if (!control) break;

      say(`Adding another ${kind === "education" ? "education" : "work"} entry.`);
      const added = await browser({
        type: "addRepeat",
        tabId: state.tab.id,
        text: control.text,
      });
      await scan();
      if (!added || added.outcome !== "verified" || blockCount(pattern) <= blocks) {
        say(`"${control.text}" did not add an entry, so I stopped adding.`, "warn");
        break;
      }
    }
  }
}

/** How many blocks of a given kind the page currently holds. */
function blockCount(pattern) {
  let most = 0;
  for (const field of (state.observation && state.observation.fields) || []) {
    if (!pattern.test(field.section || "")) continue;
    most = Math.max(most, (field.group_index || 0) + 1);
  }
  return most;
}

/**
 * Work through a multi-step application without being asked to press Continue.
 *
 * It stops at the first thing it cannot answer, and it never presses final
 * Submit -- that is governed separately in Settings and is not implied by this.
 */
const MAX_STEPS = 15;

async function runToCompletion() {
  return inFlight(runToCompletionInner);
}

async function runToCompletionInner() {
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

    // Give the next step time to arrive before deciding it never will. The
    // click knows the page moved, but the step's fields can still be on their
    // way -- sampling once, immediately, declared the page stuck and stopped,
    // and then the new page turned up to an empty panel with nothing driving
    // it. That is the run that "went to the next page and did nothing".
    const before = state.observation.signature;
    const arrived = await until(async () => {
      await scan();
      return state.observation.signature !== before;
    }, 20000);
    if (!arrived) {
      // A step that refuses to move on has just said why, in red, on itself.
      // That is the one moment the page states which of its questions it
      // actually wanted -- several of them say so nowhere else -- and it was
      // being thrown away: the run stopped here without looking again, so three
      // required questions stayed invisible and the panel simply announced it
      // had stopped. Look now, while the complaints are on screen.
      await planPage(true);
      const wanted = (state.plan.questions || []).length;
      say(
        wanted
          ? `"${next.text}" did not move the page on. The form is asking for ` +
              `${wanted} more answer(s) -- they are below.`
          : "The page has not changed after pressing continue, so I have stopped.",
        "warn"
      );
      await renderQuestion();
      return;
    }
    await planPage(true);
  }
  say(`Stopped after ${MAX_STEPS} steps rather than going round forever.`, "warn");
}

/* ------------------------------------------------------------------ report */

const DONE_STATES = new Set(["verified", "attempted", "planned", "skipped"]);
const MARKS = {
  verified: "✓",
  attempted: "!",
  planned: "·",
  needs_you: "!",
  failed: "×",
  skipped: "–",
};

function setChecklist(items) {
  state.checklist = items || [];
  // Set deliberately in Settings: keep every offered answer without a press.
  // Done before the rows are drawn, so a kept one never shows a Keep button.
  if (state.keepPageAnswers && state.checklist.some((i) => i.learnable)) {
    rememberAll().then((kept) => {
      if (kept) log(`kept ${kept} answer(s) already on this page`);
    });
  }
  const needs = state.checklist.filter((i) => i.state === "needs_you" || i.state === "failed");
  const done = state.checklist.filter((i) => DONE_STATES.has(i.state));

  el("review-card").classList.toggle("hidden", needs.length === 0);
  el("needs-heading").textContent = `Needs you (${needs.length})`;
  fillReport(el("needs-list"), needs);

  el("done-card").classList.toggle("hidden", done.length === 0);
  // "left blank" used to cover everything that was not verified, which lumped
  // fields with an answer ready and waiting in with fields nobody was ever
  // going to fill. Count them apart: one of those is a promise, the other is a
  // decision.
  const verified = done.filter((i) => i.state === "verified").length;
  const planned = done.filter((i) => i.state === "planned").length;
  const blank = done.length - verified - planned;
  el("done-heading").textContent =
    `Completed (${verified})` +
    (planned ? ` · ${planned} ready to fill` : "") +
    (blank ? ` · ${blank} left blank` : "");
  fillReport(el("done-list"), done);

  updateCta();
}

/**
 * Put a field that was left blank back to the applicant, on request.
 *
 * The report says what was left alone and why, and there was nothing to be
 * done about any of it. "Have you previously worked for, or been on assignment
 * with Toyota?" is optional, and nothing saved answers it, so it is correctly
 * left blank -- but it is the applicant's own answer and they are looking
 * straight at it. Pressing the row now asks the question, with whatever the
 * control itself offers to choose from.
 *
 * No fact key goes with it: a question about one employer belongs to that
 * question, not to the profile, so the answer is remembered against this
 * wording and used again wherever it is asked.
 */
function askAbout(item) {
  const live = fieldFor(item.fingerprint);
  if (!live) {
    showHint("That field is no longer on the page. Rescan and try again.", false);
    return;
  }
  const known = (live.options || []).filter(
    (option) => option && option.label && !isPlaceholderLabel(option.label)
  );
  const question = {
    fingerprint: item.fingerprint,
    label: item.label || live.label || live.attr_label || "",
    control: live.control,
    operation: live.operation,
    options: live.options || [],
    required: Boolean(item.required),
    fact_key: "",
    reason: "you asked to answer this one",
    section: item.section || "",
    frame: live.frame,
    saved_value: "",
    // A list nobody has read yet gets opened first, the same as any other.
    options_pending: isChoice(live.control, live.operation) && known.length < 2,
  };

  if (!state.plan) state.plan = { actions: [], questions: [] };
  const questions = state.plan.questions || (state.plan.questions = []);
  const already = questions.findIndex((q) => q.fingerprint === item.fingerprint);
  if (already >= 0) questions.splice(already, 1);
  questions.push(question);
  state.questionIndex = questions.length - 1;
  showOnPage(item.fingerprint);
  renderQuestion();
}

/** One row per field, showing the whole question rather than a truncation. */
/**
 * Keep an answer the page was already holding.
 *
 * Filling a form is not the only way an answer gets onto a page. People type
 * one in themselves -- because a dropdown was fiddly, because the question was
 * about this employer, because it was quicker than explaining. That answer was
 * respected and then thrown away, so the next form asked for it again, and the
 * one after that. The point of a tool that learns is that it stops asking.
 *
 * A fact goes to the profile under its own key. Anything else is remembered
 * against the question's own wording, so "How did you hear about us?" answers
 * itself next time without claiming to be a fact about the person.
 */
async function rememberAnswer(item, button) {
  const value = item.learnable;
  if (!value) return;
  const field = fieldFor(item.fingerprint);
  try {
    if (item.learn_key) {
      await post("/profile/fact", {
        fact_key: item.learn_key,
        value: value,
        entry: (field && field.group_index) || 0,
      });
    } else {
      await post("/learn", {
        field: field || { fingerprint: item.fingerprint, label: item.label },
        value: value,
        host: new URL(state.observation.url).host,
        page_labels: (state.observation.fields || []).map((f) => f.label),
      });
    }
  } catch (err) {
    // A fact that will not take this value says why, and that is worth seeing:
    // it is the guard that stops "Yes" becoming a permanent answer to "How did
    // you hear about us?".
    showHint(String((err && err.message) || err), false);
    return;
  }
  item.learnable = "";
  if (button) flashDone(button, "Kept", "Keep");
  log(`kept "${value}" for ${item.label}`);
}

/**
 * Keep every answer on this page that was offered, without asking.
 *
 * Off by default, because taking values off a page into a profile is not
 * something to start doing quietly.
 */
async function rememberAll() {
  const offered = (state.checklist || []).filter((i) => i.learnable);
  for (const item of offered) await rememberAnswer(item, null);
  if (offered.length) setChecklist(state.checklist);
  return offered.length;
}

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
    // A value on its own reads as a value the page is holding. For something
    // not carried out yet that is simply untrue, so say which it is.
    const said =
      item.state === "planned" && item.value
        ? `will fill: ${item.value}`
        : item.value || item.detail || "";
    detail.textContent = [item.section, said].filter(Boolean).join(" · ");
    label.appendChild(detail);
    row.appendChild(label);

    // An answer already sitting on the page that nothing here put there. It
    // was respected and then forgotten, so the next form asked for it again.
    // Offered rather than taken: the value is theirs, and a form can hold one
    // for reasons that have nothing to do with them.
    if (item.learnable) {
      const keep = document.createElement("button");
      keep.className = "keep";
      keep.textContent = "Keep";
      keep.title = `Remember "${item.learnable}" for next time`;
      keep.addEventListener("click", (event) => {
        event.stopPropagation();
        rememberAnswer(item, keep);
      });
      row.appendChild(keep);
    }

    // A row that is already filled is somewhere to go and look. A row that is
    // not is something to answer, so pressing it asks about it.
    row.title = item.state === "verified"
      ? "Find this field on the page"
      : "Answer this one";
    row.addEventListener("click", () => {
      if (item.state === "verified") showOnPage(item.fingerprint);
      else askAbout(item);
    });
    list.appendChild(row);
  }
}

/**
 * The one place to look for what happens next.
 *
 * It never offers to submit unless that was set deliberately in Settings.
 */
/** What the one decision needs to know. */
function ctaView() {
  return {
    observation: state.observation,
    plan: state.plan,
    outstanding: questions().filter((q) => q.required).length,
    submissionPolicy: state.submissionPolicy,
  };
}

function updateCta() {
  const cta = el("cta");
  const note = el("cta-note");
  const choice = ApplyPilotCta.decide(ctaView());
  cta.textContent = choice.label;
  cta.disabled = choice.disabled;
  cta._action = choice.action;
  note.textContent = choice.note;
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
    // Whether there is anything to fill, not what the page is called -- and
    // decided in the one place that decides it, rather than by a second rule
    // that could drift from the first.
    //
    // This used to ask for "application" exactly, so a page that wants an
    // account was scanned, planned, and then walked straight past. Silently,
    // with twenty-two answers ready and showing on screen, and the panel's own
    // header saying what it meant to do with them. That is most of the
    // account-creation forms there are.
    if (ApplyPilotCta.decide(ctaView()).action === "fill") {
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

/**
 * Everything needed to work out why a page went wrong, in one file.
 *
 * Reproducing a failure from a description costs a day and usually fails: the
 * page has moved on, the session is different, and the one detail that mattered
 * was not the one described. This is the page itself -- every control as it was
 * read, what was planned for each, what actually happened, and a picture of the
 * screen.
 *
 * What is deliberately not in it: the profile. Not one saved answer, not the
 * resume, not the API key. The values that were filled do appear, because those
 * are what went wrong, and the file stays on the applicant's own machine until
 * they choose to send it.
 */
async function saveReport() {
  const button = el("report");
  if (state.busy) return;
  setBusy(button, true);
  try {
    if (!state.observation) await scan();
    let picture = "";
    try {
      picture = await browser({ type: "screenshot", tabId: state.tab.id }, 10000);
    } catch (err) {
      /* a report without a picture is still a report */
    }

    const report = {
      saved_at: new Date().toISOString(),
      panel_version: EXTENSION_VERSION,
      page: {
        url: (state.observation && state.observation.url) || "",
        title: (state.observation && state.observation.title) || "",
        kind: (state.observation && state.observation.kind) || "",
        adapter: (state.plan && state.plan.adapter) || "",
        captcha: (state.observation && state.observation.captcha) || "",
      },
      // Every control, exactly as it was read. This is the part that finds
      // label and control-kind faults.
      fields: (state.observation && state.observation.fields) || [],
      planned: (state.plan && state.plan.actions) || [],
      asked: (state.plan && state.plan.questions) || [],
      skipped: (state.plan && state.plan.skipped) || [],
      results: state.results || [],
      checklist: state.checklist || [],
      activity: readActivity(),
      // Everything that happened here, in order. The state above says what the
      // page looks like now; this says what was done to get there -- every
      // question put to somebody and how many times, every answer and whether
      // it landed, every answer taken but not kept, and every instruction
      // typed into the chat with what came of it.
      //
      // The failures worth reporting are sequences, not states. A question
      // answered three times that keeps returning looks, in a photograph,
      // exactly like a question being asked for the first time.
      journal: state.journal || [],
      // The same thing counted, so it does not have to be counted by hand.
      asked_more_than_once: Array.from(state.asked.entries())
        .filter(([, times]) => times > 1)
        .sort((a, b) => b[1] - a[1])
        .map(([question, times]) => ({ question: question, times: times })),
    };

    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const host = (report.page.url.split("/")[2] || "page").replace(/[^a-z0-9.-]/gi, "");
    const entries = [
      {
        name: "report.json",
        bytes: new TextEncoder().encode(JSON.stringify(report, null, 1)),
      },
    ];
    const shot = bytesOfDataUrl(picture);
    if (shot) entries.push({ name: "page.jpg", bytes: shot });

    download(`applypilot-${host}-${stamp}.zip`, zipOf(entries));

    const unanswered = report.asked.length + report.skipped.length;
    say(
      `Saved one zip: ${report.fields.length} field(s) seen, ` +
        `${report.planned.length} planned, ${unanswered} not answered` +
        (shot ? ", picture included." : " (no picture -- the tab would not capture)."),
      "warn"
    );
    activity("Report saved", "One .zip in your downloads. Send that.");
  } catch (err) {
    say("Could not save the report: " + err.message, "bad");
  } finally {
    setBusy(button, false, "Save a report about this page");
  }
}

/** The activity list as plain lines, newest last. */
function readActivity() {
  return Array.from(el("log").children)
    .map((row) => (row.textContent || "").trim())
    .filter(Boolean)
    .slice(-80);
}

/** Hand a file to the browser's own download. Nothing leaves the machine. */
function download(filename, blob) {
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(href), 10000);
}

/*
 * A zip file, written by hand.
 *
 * One file to find, one file to send. Two downloads meant remembering to
 * attach both, and a report arriving without its picture is a report about a
 * page nobody can see.
 *
 * Entries are stored rather than compressed: a few hundred kilobytes of JSON
 * and one JPEG do not need deflating, and doing it by hand keeps this
 * dependency-free -- nothing is fetched to build it.
 */
const ZIP_SIGNATURE = { local: 0x04034b50, central: 0x02014b50, end: 0x06054b50 };

function crc32(bytes) {
  let table = crc32.table;
  if (!table) {
    table = crc32.table = new Uint32Array(256);
    for (let i = 0; i < 256; i += 1) {
      let value = i;
      for (let bit = 0; bit < 8; bit += 1) {
        value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
      }
      table[i] = value >>> 0;
    }
  }
  let crc = 0xffffffff;
  for (const byte of bytes) crc = table[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function zipOf(entries) {
  const encoder = new TextEncoder();
  const parts = [];
  const central = [];
  let offset = 0;

  const write = (view, values) => {
    let at = 0;
    for (const [size, value] of values) {
      if (size === 2) view.setUint16(at, value, true);
      else view.setUint32(at, value, true);
      at += size;
    }
  };

  for (const entry of entries) {
    const name = encoder.encode(entry.name);
    const body = entry.bytes;
    const sum = crc32(body);

    const header = new Uint8Array(30);
    write(new DataView(header.buffer), [
      [4, ZIP_SIGNATURE.local], [2, 20], [2, 0], [2, 0], [2, 0], [2, 0],
      [4, sum], [4, body.length], [4, body.length],
      [2, name.length], [2, 0],
    ]);
    parts.push(header, name, body);

    const record = new Uint8Array(46);
    write(new DataView(record.buffer), [
      [4, ZIP_SIGNATURE.central], [2, 20], [2, 20], [2, 0], [2, 0], [2, 0], [2, 0],
      [4, sum], [4, body.length], [4, body.length],
      [2, name.length], [2, 0], [2, 0], [2, 0], [2, 0], [4, 0], [4, offset],
    ]);
    central.push(record, name);
    offset += header.length + name.length + body.length;
  }

  const directory = central.reduce((total, part) => total + part.length, 0);
  const end = new Uint8Array(22);
  write(new DataView(end.buffer), [
    [4, ZIP_SIGNATURE.end], [2, 0], [2, 0],
    [2, entries.length], [2, entries.length],
    [4, directory], [4, offset], [2, 0],
  ]);

  return new Blob([...parts, ...central, end], { type: "application/zip" });
}

/** The bytes behind a "data:image/jpeg;base64,..." string. */
function bytesOfDataUrl(dataUrl) {
  const base64 = String(dataUrl || "").split(",")[1] || "";
  if (!base64) return null;
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

el("report").addEventListener("click", saveReport);
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
  if (question) {
    say(`Left "${question.label}" blank.`);
    note("skipped", question.label || "", { reason: question.reason || "" });
  }
  answerQuestion("", el("question-skip"), "Skip");
});

el("question-show").addEventListener("click", () => {
  const question = currentQuestion();
  if (!question) return;
  showOnPage(question.fingerprint);
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
    // What was asked for, and what came of it. An instruction that was
    // understood but changed nothing on the page is the hardest kind of
    // failure to report afterwards, because the panel answered pleasantly and
    // the page simply stayed as it was.
    note("chat", text, {
      kind: outcome.kind || "",
      reply: outcome.message || "",
      fact_key: outcome.fact_key || "",
      value: outcome.value || "",
    });

    if (outcome.kind === "action" && outcome.action) {
      state.busy = false;
      const done = await applyAndReport(outcome.action);
      note("chat_result", text, {
        outcome: (done && done.outcome) || "none",
        evidence: (done && done.evidence) || "",
      });
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

/**
 * Notice when the page changes without us.
 *
 * Pressing Continue yourself used to leave the panel showing the previous
 * step's plan, and only stopping and starting again picked the new page up.
 */
function watchThePage() {
  setInterval(async () => {
    // Anything in flight means the page is being changed by us.
    if (state.working > 0 || state.busy || !state.tab || !state.observation) {
      state.stableTicks = 0;
      return;
    }
    try {
      const tab = await browser({ type: "activeTab" });
      if (!tab || tab.id !== state.tab.id) return;

      // Ask the cheap question first. Scanning every frame of a large
      // application every couple of seconds, for as long as the panel is open,
      // was the panel making the page slow all by itself -- and it did it while
      // sitting there doing nothing.
      const shape = await browser({ type: "shape", tabId: state.tab.id });
      if (shape && shape === state.lastShape) {
        state.stableTicks = 0;
        return;
      }
      state.lastShape = shape;

      const fresh = await browser({ type: "scan", tabId: state.tab.id });
      if (!fresh || !fresh.signature) return;

      // Wait for the page to settle before acting on it: a form mid-render
      // looks different on every tick.
      if (fresh.signature !== state.stableSignature) {
        state.stableSignature = fresh.signature;
        state.stableTicks = 0;
        return;
      }
      state.stableTicks += 1;
      if (state.stableTicks < 2) return;

      // And only when it is not simply the page we already planned against.
      if (fresh.signature === state.lastPlannedSignature) return;

      state.observation = fresh;
      say("The page changed, so I have looked at it again.");
      await planPage();
    } catch (err) {
      /* the tab went away or is still loading; the next tick will do */
    }
  }, 2500);
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
    state.autoAttach = settings.auto_attach_resume !== false;
    state.keepPageAnswers = Boolean(settings.keep_page_answers);
    state.submissionPolicy = settings.submission_policy || "confirm";
    el("auto-continue").checked = state.autoContinue;
    if (state.autoContinue) {
      el("auto-note").textContent =
        "I will press Continue myself and stop at anything I cannot answer.";
    }
  } catch (err) {
    /* the health check already reported the service being down */
  }
  try {
    const documents = await service("/documents");
    state.primaryResumeId = documents.primary_resume_id || "";
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
  watchThePage();
})();
