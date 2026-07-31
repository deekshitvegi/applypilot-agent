/*
 * The panel.
 *
 * It talks to the local service over http://127.0.0.1 and to the page only by
 * asking the service worker. It never injects anything itself.
 *
 * There is no code here that types a password into a page, and that is on
 * purpose. What exists instead is the part that decides whether a sign-in could
 * ever be released -- exact host match, confirmed sign-in form, never a
 * registration page -- and the hand-off: the panel says which page wants you
 * signed in, you sign in with your password manager, and the run picks up from
 * whatever the page looks like afterwards. Sign-in is only ever reported as
 * done when the sign-in form is no longer there.
 *
 * If session-scoped details are added later they belong in a variable in this
 * file and nowhere else: not in storage, not in the service, not in a log.
 */

const SERVICE = "http://127.0.0.1:8765";
const EXTENSION_VERSION = chrome.runtime.getManifest().version;

const el = (id) => document.getElementById(id);

const state = {
  tab: null,
  observation: null,
  plan: null,
  running: false,
  questionIndex: 0,
  lastFingerprint: "",
  serviceVersion: "",
  onboarding: null,
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

/** Ask the service worker to do something in the tab. Never done from here. */
function browser(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (reply) => {
      if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
      if (!reply || !reply.ok) return reject(new Error((reply && reply.error) || "no reply"));
      resolve(reply.value);
    });
  });
}

/* --------------------------------------------------------------------- chat */

function say(text, tone) {
  if (!text) return;
  const line = document.createElement("div");
  line.className = "line" + (tone ? " " + tone : "");
  line.textContent = text;
  el("log").appendChild(line);
  el("log").scrollTop = el("log").scrollHeight;
}

function youSaid(text) {
  const line = document.createElement("div");
  line.className = "line you";
  line.textContent = "you: " + text;
  el("log").appendChild(line);
  el("log").scrollTop = el("log").scrollHeight;
}

function activity(text) {
  el("activity").textContent = text;
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
    state.serviceVersion = health.version;
    el("versions").textContent = `panel ${EXTENSION_VERSION} · service ${health.version}`;
    el("applications").textContent = health.applications.total
      ? `${health.applications.total} applications tracked`
      : "";

    el("alerts").innerHTML = "";
    if (health.version !== EXTENSION_VERSION) {
      // A running service keeps serving the code it started with.
      alert_(
        `The service is running ${health.version} but this panel is ${EXTENSION_VERSION}. ` +
          "Restart the service, then reload the extension -- otherwise you are testing " +
          "code that is not the code on disk.",
        "bad"
      );
    }
    if (!health.model_configured) {
      alert_(
        "No model key yet. Matching works without one; wording and free-text answers do not.",
        "warn",
        "Open Settings",
        () => chrome.runtime.openOptionsPage()
      );
    }
    return health;
  } catch (err) {
    el("versions").textContent = `panel ${EXTENSION_VERSION} · service not running`;
    alert_(
      "The local service is not answering on 127.0.0.1:8765. Start it with " +
        "scripts\\start.ps1 and this panel will pick it up.",
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
  state.onboarding = data;
  const card = el("onboarding");
  if (data.complete) {
    card.classList.add("hidden");
    return data;
  }
  card.classList.remove("hidden");
  el("onboarding-progress").textContent =
    `${data.answered} of ${data.total} answered. Answer these once and applications stop asking.`;
  el("onboarding-notes").innerHTML = "";
  for (const note of data.notes) {
    const p = document.createElement("p");
    p.className = "muted tiny";
    p.textContent = note;
    el("onboarding-notes").appendChild(p);
  }
  renderOnboardingStep(data.next);
  return data;
}

function renderOnboardingStep(step) {
  const host = el("onboarding-step");
  host.innerHTML = "";
  if (!step) return;

  const heading = document.createElement("p");
  heading.className = "muted tiny";
  heading.textContent = step.group_title;
  host.appendChild(heading);

  const label = document.createElement("label");
  label.className = "question-label";
  label.textContent = step.prompt;
  label.setAttribute("for", "onboarding-value");
  host.appendChild(label);

  const control = buildControl("onboarding-value", step.kind, step.choices || [], step.value);
  host.appendChild(control.node);

  const row = document.createElement("div");
  row.className = "row";
  const save = document.createElement("button");
  save.className = "primary";
  save.textContent = "Save";
  save.addEventListener("click", async () => {
    await post("/onboarding/answer", { key: step.key, value: control.read() });
    await refreshOnboarding();
  });
  row.appendChild(save);

  if (step.optional) {
    const skip = document.createElement("button");
    skip.className = "ghost";
    skip.textContent = "Prefer not to answer";
    skip.addEventListener("click", async () => {
      await post("/onboarding/answer", {
        key: step.key,
        value: step.kind === "choice" ? "I don't wish to answer" : "",
      });
      await refreshOnboarding();
    });
    row.appendChild(skip);
  }
  host.appendChild(row);
}

/** One control for a question, whatever shape the question is. */
function buildControl(id, kind, choices, value) {
  if (choices && choices.length) {
    const wrap = document.createElement("div");
    wrap.className = "choices";
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
    return { node: wrap, read: () => picked };
  }
  const input = document.createElement(kind === "textarea" ? "textarea" : "input");
  input.id = id;
  if (input.tagName === "INPUT") input.type = "text";
  input.value = value || "";
  return { node: input, read: () => input.value.trim() };
}

/* -------------------------------------------------------------------- pages */

async function scan() {
  const tab = await browser({ type: "activeTab" });
  if (!tab) throw new Error("no tab is in focus");
  state.tab = tab;
  activity("Reading the page…");
  const observation = await browser({ type: "scan", tabId: tab.id });
  if (!observation) throw new Error("nothing could be read from that tab");
  state.observation = observation;
  return observation;
}

async function planPage() {
  const observation = state.observation;
  const plan = await post("/plan", observation);
  state.plan = plan;
  state.questionIndex = 0;

  el("page-kind").textContent = describeKind(observation, plan);
  el("page-detail").textContent = [plan.host_reason, ...(plan.notes || [])].join(" · ");
  say(plan.narration);
  for (const note of plan.notes || []) {
    if (/CAPTCHA|stopped|missing/i.test(note)) say(note, "warn");
  }
  renderChecklist(plan.checklist);
  renderQuestion();
  return plan;
}

function describeKind(observation, plan) {
  const names = {
    application: "Application form",
    listing: "Job posting",
    board: "List of jobs",
    search: "Search results",
    sign_in: "Sign-in page",
    registration: "Account creation page",
    confirmation: "Confirmation page",
    unknown: "Unrecognised page",
  };
  const adapter = plan.adapter && plan.adapter !== "generic" ? ` · ${plan.adapter}` : "";
  return `${names[observation.kind] || observation.kind}${adapter}`;
}

/* --------------------------------------------------------------- checklists */

function renderChecklist(items) {
  const list = el("checklist");
  list.innerHTML = "";
  const counts = {};
  for (const item of items || []) counts[item.state] = (counts[item.state] || 0) + 1;
  el("checklist-count").textContent = (items || []).length
    ? Object.entries(counts)
        .map(([k, v]) => `${v} ${k.replace("_", " ")}`)
        .join(" · ")
    : "";

  for (const item of items || []) {
    const row = document.createElement("li");
    row.title = "Show me on the page";

    const dot = document.createElement("span");
    dot.className = "dot " + item.state;
    row.appendChild(dot);

    const label = document.createElement("span");
    label.className = "item-label";
    const strong = document.createElement("strong");
    strong.textContent = item.label + (item.required ? " *" : "");
    label.appendChild(strong);
    const detail = document.createElement("span");
    detail.className = "item-detail";
    detail.textContent = [item.value, item.detail].filter(Boolean).join(" — ");
    label.appendChild(detail);
    row.appendChild(label);

    const badge = document.createElement("span");
    badge.className = "state";
    badge.textContent = item.state.replace("_", " ");
    row.appendChild(badge);

    row.addEventListener("click", () =>
      browser({ type: "highlight", tabId: state.tab.id, fingerprint: item.fingerprint }).catch(
        (err) => say(String(err.message), "bad")
      )
    );
    list.appendChild(row);
  }
}

/* --------------------------------------------------------------- questions */

function currentQuestion() {
  const questions = (state.plan && state.plan.questions) || [];
  return questions[state.questionIndex] || null;
}

function renderQuestion() {
  const card = el("question");
  const question = currentQuestion();
  if (!question) {
    card.classList.add("hidden");
    return;
  }
  card.classList.remove("hidden");
  el("question-label").textContent = question.label;
  el("question-reason").textContent = question.reason;
  el("question-remaining").textContent =
    `${state.plan.questions.length - state.questionIndex - 1} more after this one.`;

  const host = el("question-input");
  host.innerHTML = "";
  const choices = (question.options || []).map((o) => o.label).filter(Boolean);
  const control = buildControl(
    "question-value",
    choices.length ? "choice" : question.control === "textarea" ? "textarea" : "text",
    choices,
    ""
  );
  host.appendChild(control.node);
  host.dataset.ready = "1";
  card._read = control.read;
}

async function answerQuestion(value) {
  const question = currentQuestion();
  if (!question) return;
  if (value) {
    await applyAndReport({
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
    if (question.fact_key) {
      const profile = await service("/profile");
      profile.facts[question.fact_key] = value;
      await put("/profile", profile);
    } else {
      await post("/learn", {
        field: fieldFor(question.fingerprint) || { fingerprint: question.fingerprint, label: question.label },
        value: value,
        host: new URL(state.observation.url).host,
        page_labels: (state.observation.fields || []).map((f) => f.label),
      });
    }
  }
  state.questionIndex += 1;
  renderQuestion();
}

function fieldFor(fingerprint) {
  return (state.observation.fields || []).find((f) => f.fingerprint === fingerprint) || null;
}

/* ----------------------------------------------------------------- filling */

async function applyAndReport(action) {
  const result = await browser({ type: "perform", tabId: state.tab.id, action: action });
  state.lastFingerprint = action.fingerprint;
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
    say(`${label}: attempted but not verified — ${result.evidence}. Please check it.`, "warn");
  } else {
    say(`${label}: failed — ${result.evidence}`, "bad");
  }
}

async function fillPage() {
  if (!state.plan) await planPage();
  const actions = state.plan.actions || [];
  if (!actions.length) {
    say("Nothing on this page can be filled from what you have saved.");
    return;
  }

  const results = [];
  for (const action of actions) {
    activity(`Filling ${actions.indexOf(action) + 1} of ${actions.length}…`);
    try {
      results.push(await applyAndReport(action));
    } catch (err) {
      say(String(err.message), "bad");
    }
  }

  // Choosing a country can rebuild the whole address block and throw away work
  // done seconds earlier. Look again, and re-fill only what the page no longer
  // holds -- filling is idempotent, so nothing already correct is touched.
  const loose = (text) => String(text || "").trim().toLowerCase();
  const after = await scan();
  const replan = await post("/plan", after);
  const onPage = new Map((after.fields || []).map((f) => [f.fingerprint, f]));
  const lost = (replan.actions || []).filter((action) => {
    const wanted = action.option_label || action.value;
    const field = onPage.get(action.fingerprint);
    const wasVerified = results.some(
      (r) => r.fingerprint === action.fingerprint && r.outcome === "verified"
    );
    return wasVerified && field && loose(field.value) !== loose(wanted);
  });
  if (lost.length) {
    say(`The page rebuilt itself and dropped ${lost.length} field(s). Filling them again.`, "warn");
    for (const action of lost) {
      try {
        results.push(await applyAndReport(action));
      } catch (err) {
        say(String(err.message), "bad");
      }
    }
  }

  const summary = await post("/results", { observation: state.observation, results: results });
  activity(summary.summary);
  renderChecklist(summary.checklist);
  state.plan = await post("/plan", state.observation);
  state.questionIndex = 0;
  renderQuestion();

  for (const item of summary.unverified) {
    say(`Not verified: ${item.label} — ${item.evidence}`, "warn");
  }
}

/* -------------------------------------------------------------------- wiring */

el("run").addEventListener("click", async () => {
  state.running = !state.running;
  el("run").textContent = state.running ? "Stop" : "Start";
  el("run").classList.toggle("running", state.running);
  if (!state.running) {
    await post("/run", { command: "stop" });
    activity("Stopped.");
    return;
  }
  try {
    const observation = await scan();
    await post("/run", { command: "start", url: observation.url });
    await planPage();
    if (observation.kind === "application") await fillPage();
  } catch (err) {
    say(String(err.message), "bad");
    activity("Stopped after an error.");
    state.running = false;
    el("run").textContent = "Start";
    el("run").classList.remove("running");
  }
});

el("rescan").addEventListener("click", async () => {
  try {
    await scan();
    await planPage();
  } catch (err) {
    say(String(err.message), "bad");
  }
});

el("fill").addEventListener("click", async () => {
  try {
    if (!state.observation) await scan();
    await fillPage();
  } catch (err) {
    say(String(err.message), "bad");
  }
});

el("settings").addEventListener("click", () => chrome.runtime.openOptionsPage());
el("onboarding-skip").addEventListener("click", () => el("onboarding").classList.add("hidden"));

el("question-save").addEventListener("click", async () => {
  const read = el("question")._read;
  try {
    await answerQuestion(read ? read() : "");
  } catch (err) {
    say(String(err.message), "bad");
  }
});
el("question-skip").addEventListener("click", () => answerQuestion(""));
el("question-show").addEventListener("click", () => {
  const question = currentQuestion();
  if (question) {
    browser({ type: "highlight", tabId: state.tab.id, fingerprint: question.fingerprint });
  }
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
      "Check them in Settings -- I only took what the document said.";
    for (const note of body.notes) say(note, "warn");
    await refreshOnboarding();
  } catch (err) {
    el("resume-result").textContent = String(err.message);
  }
});

el("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = el("chat-input").value.trim();
  if (!text) return;
  el("chat-input").value = "";
  youSaid(text);
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
  }
});

function renderChoiceCard(outcome) {
  const wrap = document.createElement("div");
  wrap.className = "line choices";
  for (const option of outcome.options) {
    const button = document.createElement("button");
    button.textContent = option.label;
    button.addEventListener("click", async () => {
      wrap.remove();
      await applyAndReport({
        kind: "choose",
        fingerprint: outcome.fingerprint,
        option_label: option.label,
        value: option.label,
      });
      await planPage();
    });
    wrap.appendChild(button);
  }
  el("log").appendChild(wrap);
  el("log").scrollTop = el("log").scrollHeight;
}

/* --------------------------------------------------------------------- boot */

(async function start() {
  const health = await refreshHealth();
  if (!health) return;
  await refreshOnboarding();
  try {
    await scan();
    await planPage();
  } catch (err) {
    activity("Open a job page and press Rescan.");
  }
})();
