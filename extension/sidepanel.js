const DEFAULT_API_BASE = "http://127.0.0.1:8765";

const elements = {
  connection: document.querySelector("#connection"),
  question: document.querySelector("#question"),
  progress: document.querySelector("#progress"),
  refresh: document.querySelector("#refresh"),
  settings: document.querySelector("#settings"),
  providerCard: document.querySelector("#provider-card"),
  providerForm: document.querySelector("#provider-form"),
  providerSelect: document.querySelector("#provider-select"),
  providerKey: document.querySelector("#provider-key"),
  providerModel: document.querySelector("#provider-model"),
  providerHelp: document.querySelector("#provider-help"),
  providerTitle: document.querySelector("#provider-title"),
  providerBadge: document.querySelector("#provider-badge"),
  disconnectProvider: document.querySelector("#disconnect-provider"),
  toggleKey: document.querySelector("#toggle-key"),
  siteAccessBadge: document.querySelector("#site-access-badge"),
  enableSiteAccess: document.querySelector("#enable-site-access"),
  automationPolicy: document.querySelector("#automation-policy"),
  resumePolicy: document.querySelector("#resume-policy"),
  minimumFit: document.querySelector("#minimum-fit"),
  continueNext: document.querySelector("#continue-next"),
  automationWarning: document.querySelector("#automation-warning"),
  startAutomation: document.querySelector("#start-automation"),
  stopAutomation: document.querySelector("#stop-automation"),
  automationStatus: document.querySelector("#automation-status"),
  answerForm: document.querySelector("#answer-form"),
  answerInput: document.querySelector("#answer-input"),
  answerChoice: document.querySelector("#answer-choice"),
  editProfile: document.querySelector("#edit-profile"),
  profileEditor: document.querySelector("#profile-editor"),
  profileFields: document.querySelector("#profile-fields"),
  savedAnswers: document.querySelector("#saved-answers"),
  cancelProfile: document.querySelector("#cancel-profile"),
  resumeFile: document.querySelector("#resume-file"),
  resumeStatus: document.querySelector("#resume-status"),
  captureJob: document.querySelector("#capture-job"),
  openApplication: document.querySelector("#open-application"),
  tailorResume: document.querySelector("#tailor-resume"),
  analyzeFit: document.querySelector("#analyze-fit"),
  fitResult: document.querySelector("#fit-result"),
  tailorResult: document.querySelector("#tailor-result"),
  artifactActions: document.querySelector("#artifact-actions"),
  downloadDocx: document.querySelector("#download-docx"),
  downloadPdf: document.querySelector("#download-pdf"),
  attachResume: document.querySelector("#attach-resume"),
  jobTitle: document.querySelector("#job-title"),
  jobCompany: document.querySelector("#job-company"),
  scanForm: document.querySelector("#scan-form"),
  fillForm: document.querySelector("#fill-form"),
  formStatus: document.querySelector("#form-status"),
  formResult: document.querySelector("#form-result"),
  unknownAnswerForm: document.querySelector("#unknown-answer-form"),
  unknownQuestion: document.querySelector("#unknown-question"),
  unknownAnswer: document.querySelector("#unknown-answer"),
  approveSubmit: document.querySelector("#approve-submit"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  chatButton: document.querySelector("#chat-send"),
  chatImages: document.querySelector("#chat-images"),
  imagePreviews: document.querySelector("#image-previews"),
  attachImageLabel: document.querySelector("#attach-image-label"),
  chatContext: document.querySelector("#chat-context"),
  messages: document.querySelector("#messages"),
};

const state = {
  apiBase: DEFAULT_API_BASE,
  profile: null,
  answers: [],
  onboarding: null,
  provider: null,
  job: null,
  route: null,
  application: null,
  artifact: null,
  submitClicked: false,
  formScan: null,
  formPlan: null,
  localMode: false,
  chatImages: [],
  sourceTabId: null,
  jobQueue: [],
  automationRunning: false,
  automationPolicy: "review_each",
  resumePolicy: "ask_each",
  fitAnalysis: null,
  seenJobUrls: new Set(),
  jobsProcessed: 0,
  applicationsSubmitted: 0,
  minimumFit: 60,
  siteAccessGranted: false,
};

const SITE_ORIGINS = ["https://*/*", "http://*/*"];

const PROFILE_FIELDS = [
  { section: "Personal information", key: "legal_name", label: "Full legal name" },
  { key: "preferred_name", label: "Preferred name" },
  { key: "pronouns", label: "Pronouns" },
  { key: "email", label: "Email", type: "email" },
  { key: "phone", label: "Phone", type: "tel" },
  { section: "Address", key: "address_line_1", label: "Address line 1" },
  { key: "address_line_2", label: "Address line 2" },
  { key: "city", label: "City" },
  { key: "region", label: "State / region" },
  { key: "postal_code", label: "Postal / ZIP code" },
  { key: "country", label: "Country" },
  { section: "Professional", key: "current_title", label: "Current title" },
  { key: "years_of_experience", label: "Years of experience" },
  { key: "linkedin_url", label: "LinkedIn URL", type: "url" },
  { key: "github_url", label: "GitHub URL", type: "url" },
  { key: "portfolio_url", label: "Portfolio URL", type: "url" },
  { key: "notice_period", label: "Notice period" },
  { key: "desired_salary", label: "Desired salary" },
  { section: "Eligibility", key: "work_authorization", label: "Work authorization" },
  { key: "requires_sponsorship", label: "Requires sponsorship", type: "boolean" },
  { key: "willing_to_relocate", label: "Willing to relocate", type: "boolean" },
  { key: "willing_to_travel", label: "Willing to travel", type: "boolean" },
  { key: "age_18_or_older", label: "At least 18 years old", type: "boolean" },
  { key: "background_check_consent", label: "Background check consent", type: "boolean" },
  {
    key: "remote_preference",
    label: "Work arrangement",
    type: "choice",
    choices: ["", "remote", "hybrid", "onsite", "flexible"],
  },
  { section: "Voluntary self-identification", key: "gender_identity", label: "Gender identity" },
  { key: "race_ethnicity", label: "Race / ethnicity" },
  { key: "veteran_status", label: "Veteran status" },
  { key: "disability_status", label: "Disability status" },
];

const PROVIDERS = {
  gemini: {
    label: "Google Gemini",
    model: "gemini-2.5-flash",
    help: "Create a key in Google AI Studio. Gemini offers a limited free tier.",
  },
  openai: {
    label: "OpenAI",
    model: "gpt-5-mini",
    help: "Use an OpenAI Platform API key. ChatGPT subscriptions do not include API usage.",
  },
  anthropic: {
    label: "Anthropic Claude",
    model: "claude-sonnet-4-20250514",
    help: "Use a key from the Anthropic Console. Claude API usage is billed separately.",
  },
};

async function api(path, options = {}) {
  const response = await fetch(`${state.apiBase}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `${response.status} ${response.statusText}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

async function transitionApplication(status, message, metadata = {}) {
  if (!state.application || state.application.status === status) return state.application;
  state.application = await api(`/api/applications/${state.application.id}/transition`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, message, metadata }),
  });
  return state.application;
}

async function loadState() {
  await loadAutomationSettings();
  await refreshSiteAccess();
  elements.connection.textContent = "Connecting to agent…";
  elements.connection.classList.remove("connected");

  try {
    const stored = await chrome.storage.sync.get({ apiBase: DEFAULT_API_BASE });
    state.apiBase = stored.apiBase.replace(/\/$/, "");
    const health = await api("/health");
    state.localMode = health.mode === "local";
    elements.connection.textContent = `${health.mode === "local" ? "Local" : "Demo"} agent connected`;
    elements.connection.classList.add("connected");

    state.provider = await api("/api/provider");
    renderProvider();
    updateChatAvailability();

    if (!state.localMode) {
      showDemoMode();
      return;
    }

    [state.profile, state.onboarding, state.answers] = await Promise.all([
      api("/api/profile"),
      api("/api/onboarding"),
      api("/api/answers"),
    ]);
    renderOnboarding();
    renderProfileEditor();
    await refreshResumeStatus();
  } catch (error) {
    elements.connection.textContent = "Agent is offline";
    elements.question.textContent = "Start the ApplyPilot service, then refresh.";
    elements.progress.textContent = error.message;
    elements.answerForm.classList.add("hidden");
    state.localMode = false;
    updateChatAvailability();
  }
}

async function loadAutomationSettings() {
  const saved = await chrome.storage.local.get({
    automationPolicy: "review_each",
    resumePolicy: "ask_each",
    minimumFit: 60,
    continueNext: true,
  });
  state.automationPolicy = saved.automationPolicy;
  state.resumePolicy = saved.resumePolicy;
  state.minimumFit = saved.minimumFit;
  elements.automationPolicy.value = saved.automationPolicy;
  elements.resumePolicy.value = saved.resumePolicy;
  elements.minimumFit.value = String(saved.minimumFit);
  elements.continueNext.checked = saved.continueNext;
  renderAutomationPolicy();
}

function renderAutomationPolicy() {
  const automatic = state.automationPolicy === "always_allow";
  elements.automationWarning.classList.toggle("hidden", !automatic);
  elements.startAutomation.textContent = automatic ? "Start automatic run" : "Run current job";
}

async function refreshSiteAccess() {
  const granted = await chrome.permissions.contains({ origins: SITE_ORIGINS });
  state.siteAccessGranted = granted;
  elements.siteAccessBadge.textContent = granted ? "Access enabled" : "Access needed";
  elements.siteAccessBadge.classList.toggle("connected", granted);
  elements.enableSiteAccess.textContent = granted ? "Job-site access enabled" : "Enable job-site access";
  return granted;
}

async function requestSiteAccess() {
  const granted = await chrome.permissions.request({ origins: SITE_ORIGINS });
  await refreshSiteAccess();
  if (!granted) throw new Error("Job-site access was not granted.");
  elements.automationStatus.textContent = "Site access enabled. ApplyPilot can read and fill job pages.";
  return true;
}

async function requireSiteAccess() {
  if (state.siteAccessGranted) return true;
  return requestSiteAccess();
}

async function changeAutomationPolicy() {
  const selected = elements.automationPolicy.value;
  if (selected === "always_allow") {
    const confirmed = window.confirm(
      "Always allow lets ApplyPilot fill, submit, and continue to queued jobs without asking again. Login, CAPTCHA, MFA, missing answers, and ambiguous submit buttons still pause. Enable automatic mode?",
    );
    if (!confirmed) {
      elements.automationPolicy.value = state.automationPolicy;
      return;
    }
  }
  state.automationPolicy = selected;
  await chrome.storage.local.set({ automationPolicy: selected });
  renderAutomationPolicy();
}

async function changeContinueNext() {
  await chrome.storage.local.set({ continueNext: elements.continueNext.checked });
}

async function changeResumePolicy() {
  state.resumePolicy = elements.resumePolicy.value;
  await chrome.storage.local.set({ resumePolicy: state.resumePolicy });
}

async function changeMinimumFit() {
  const value = Math.max(0, Math.min(100, Number(elements.minimumFit.value) || 0));
  state.minimumFit = value;
  elements.minimumFit.value = String(value);
  await chrome.storage.local.set({ minimumFit: value });
}

function updateChatAvailability() {
  const ready = Boolean(state.localMode && state.provider?.configured);
  elements.chatInput.disabled = !ready;
  elements.chatButton.disabled = !ready;
  elements.chatImages.disabled = !ready;
  elements.attachImageLabel.classList.toggle("disabled", !ready);
}

function renderProvider() {
  const provider = state.provider || {
    provider: elements.providerSelect.value,
    model: PROVIDERS[elements.providerSelect.value].model,
    configured: false,
    source: "none",
  };
  elements.providerSelect.value = provider.provider;
  elements.providerModel.value = provider.model || PROVIDERS[provider.provider].model;
  elements.providerKey.value = "";
  elements.providerKey.placeholder = provider.configured
    ? "Paste a new key to replace the saved key"
    : "Paste a newly generated key";
  elements.providerTitle.textContent = provider.configured
    ? PROVIDERS[provider.provider].label
    : "Connect a model";
  elements.providerBadge.textContent = provider.configured ? "Connected" : "Not configured";
  elements.providerBadge.classList.toggle("connected", provider.configured);
  elements.disconnectProvider.disabled = !provider.configured || provider.source === "environment";
  elements.providerHelp.textContent = provider.configured
    ? `Using ${provider.model}. The key is ${provider.source === "environment" ? "loaded from the local environment" : "encrypted locally"}.`
    : PROVIDERS[provider.provider].help;
}

async function saveProvider(event) {
  event.preventDefault();
  const apiKey = elements.providerKey.value.trim();
  const provider = elements.providerSelect.value;
  const model = elements.providerModel.value.trim();
  if (!state.localMode) {
    elements.providerHelp.textContent = "Start the local ApplyPilot service before saving a key.";
    return;
  }
  if (!apiKey || !model) {
    elements.providerHelp.textContent = "Enter both an API key and model name.";
    return;
  }
  elements.providerHelp.textContent = "Encrypting and saving locally…";
  try {
    state.provider = await api("/api/provider", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: apiKey, model }),
    });
    renderProvider();
    updateChatAvailability();
    appendMessage(`${PROVIDERS[provider].label} is connected.`, "agent-message");
  } catch (error) {
    elements.providerHelp.textContent = error.message;
  } finally {
    elements.providerKey.value = "";
  }
}

async function disconnectProvider() {
  if (!state.localMode || !state.provider?.configured) return;
  try {
    state.provider = await api("/api/provider", { method: "DELETE" });
    renderProvider();
    updateChatAvailability();
  } catch (error) {
    elements.providerHelp.textContent = error.message;
  }
}

function changeProvider() {
  const provider = elements.providerSelect.value;
  elements.providerModel.value = PROVIDERS[provider].model;
  elements.providerHelp.textContent = PROVIDERS[provider].help;
}

function showDemoMode() {
  elements.question.textContent = "The hosted demo does not accept personal data.";
  elements.progress.textContent = "Switch to the local service in settings to onboard and apply.";
  elements.answerForm.classList.add("hidden");
  elements.resumeStatus.textContent = "Résumé upload is disabled in public demo mode.";
}

function renderOnboarding() {
  const onboarding = state.onboarding;
  if (onboarding.complete) {
    elements.question.textContent = "Reusable application profile complete.";
    elements.progress.textContent = "Saved locally and reused across job pages. Choose Edit saved profile to correct anything.";
    elements.answerForm.classList.add("hidden");
    return;
  }

  const current = onboarding.next_question;
  elements.question.textContent = current.prompt;
  elements.progress.textContent = `${onboarding.missing_count} required answers remaining`;
  elements.answerForm.classList.remove("hidden");
  elements.answerForm.dataset.key = current.key;
  elements.answerForm.dataset.type = current.input_type;

  if (current.input_type === "boolean") {
    setChoices(["Yes", "No"]);
  } else if (current.input_type === "choice") {
    setChoices(current.choices);
  } else {
    elements.answerChoice.classList.add("hidden");
    elements.answerInput.classList.remove("hidden");
    elements.answerInput.value = "";
    elements.answerInput.focus();
  }
}

function renderProfileEditor() {
  if (!state.profile) return;
  const nodes = [];
  for (const field of PROFILE_FIELDS) {
    if (field.section) {
      const heading = document.createElement("h3");
      heading.textContent = field.section;
      nodes.push(heading);
    }
    const label = document.createElement("label");
    label.htmlFor = `profile-${field.key}`;
    label.textContent = field.label;
    let control;
    if (field.type === "boolean") {
      control = document.createElement("select");
      [
        ["", "Not provided"],
        ["true", "Yes"],
        ["false", "No"],
      ].forEach(([value, text]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = text;
        control.append(option);
      });
      const current = state.profile[field.key];
      control.value = current === true ? "true" : current === false ? "false" : "";
    } else if (field.type === "choice") {
      control = document.createElement("select");
      field.choices.forEach((choice) => {
        const option = document.createElement("option");
        option.value = choice;
        option.textContent = choice || "Not provided";
        control.append(option);
      });
      control.value = state.profile[field.key] || "";
    } else {
      control = document.createElement("input");
      control.type = field.type || "text";
      control.value = state.profile[field.key] || "";
      control.autocomplete = "off";
    }
    control.id = `profile-${field.key}`;
    control.dataset.profileKey = field.key;
    control.dataset.profileType = field.type || "text";
    nodes.push(label, control);
  }
  elements.profileFields.replaceChildren(...nodes);
  renderSavedAnswers();
}

function renderSavedAnswers() {
  const heading = document.createElement("h3");
  heading.textContent = "Saved custom application answers";
  if (!state.answers.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "Answers to unfamiliar questions will appear here after you save them.";
    elements.savedAnswers.replaceChildren(heading, empty);
    return;
  }
  const rows = state.answers.map((answer) => {
    const row = document.createElement("div");
    row.className = "saved-answer";
    const label = document.createElement("label");
    label.htmlFor = `saved-answer-${answer.id}`;
    label.textContent = answer.question;
    const input = document.createElement("input");
    input.id = `saved-answer-${answer.id}`;
    input.value = answer.answer;
    const actions = document.createElement("div");
    actions.className = "button-row";
    const save = document.createElement("button");
    save.type = "button";
    save.textContent = "Update";
    save.addEventListener("click", async () => {
      const updated = { ...answer, answer: input.value.trim() };
      await api(`/api/answers/${answer.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updated),
      });
      state.answers = await api("/api/answers");
      renderSavedAnswers();
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary-button";
    remove.textContent = "Delete";
    remove.addEventListener("click", async () => {
      if (!window.confirm(`Delete the saved answer for: ${answer.question}?`)) return;
      await api(`/api/answers/${answer.id}`, { method: "DELETE" });
      state.answers = await api("/api/answers");
      renderSavedAnswers();
    });
    actions.append(save, remove);
    row.append(label, input, actions);
    return row;
  });
  elements.savedAnswers.replaceChildren(heading, ...rows);
}

function openProfileEditor() {
  renderProfileEditor();
  elements.profileEditor.classList.remove("hidden");
  elements.answerForm.classList.add("hidden");
  elements.profileEditor.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function saveProfile(event) {
  event.preventDefault();
  const updated = { ...state.profile };
  elements.profileFields.querySelectorAll("[data-profile-key]").forEach((control) => {
    const key = control.dataset.profileKey;
    const type = control.dataset.profileType;
    if (type === "boolean") {
      updated[key] = control.value === "" ? null : control.value === "true";
    } else {
      updated[key] = control.value.trim();
    }
  });
  state.profile = await api("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updated),
  });
  state.onboarding = await api("/api/onboarding");
  elements.profileEditor.classList.add("hidden");
  renderOnboarding();
  renderProfileEditor();
  elements.progress.textContent = "Saved. These values will be reused on future application pages.";
}

function setChoices(choices) {
  elements.answerInput.classList.add("hidden");
  elements.answerChoice.classList.remove("hidden");
  elements.answerChoice.replaceChildren(
    ...choices.map((choice) => {
      const option = document.createElement("option");
      option.value = choice;
      option.textContent = choice;
      return option;
    }),
  );
}

async function saveOnboardingAnswer(event) {
  event.preventDefault();
  const key = elements.answerForm.dataset.key;
  const type = elements.answerForm.dataset.type;
  let value = type === "text" ? elements.answerInput.value.trim() : elements.answerChoice.value;
  if (!value) return;
  if (type === "boolean") value = value === "Yes";

  state.profile[key] = value;
  state.profile = await api("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.profile),
  });
  state.onboarding = await api("/api/onboarding");
  renderOnboarding();
}

async function refreshResumeStatus() {
  try {
    const resume = await api("/api/resumes/active");
    elements.resumeStatus.textContent = `${resume.filename} · ${resume.extracted_text.length.toLocaleString()} characters extracted`;
  } catch (error) {
    if (!error.message.includes("No resume")) throw error;
  }
}

async function uploadResume() {
  const [file] = elements.resumeFile.files;
  if (!file) return;
  elements.resumeStatus.textContent = "Extracting résumé…";
  const body = new FormData();
  body.append("file", file);
  try {
    const resume = await api("/api/resumes", { method: "POST", body });
    elements.resumeStatus.textContent = `${resume.filename} uploaded and encrypted locally.`;
  } catch (error) {
    elements.resumeStatus.textContent = error.message;
  } finally {
    elements.resumeFile.value = "";
  }
}

async function captureJob(options = {}) {
  const throwOnError = options?.throwOnError === true;
  elements.captureJob.disabled = true;
  elements.captureJob.textContent = "Reading page…";
  try {
    await requireSiteAccess();
    const captured = await chrome.runtime.sendMessage({ action: "captureJob" });
    if (captured.error) throw new Error(captured.error);
    if (!captured.description || captured.description.length < 80) {
      throw new Error("Could not find a complete job description on this page.");
    }
    state.job = captured;
    state.sourceTabId = captured.tab_id;
    state.artifact = null;
    state.fitAnalysis = null;
    elements.fitResult.classList.add("hidden");
    elements.artifactActions.classList.add("hidden");
    state.submitClicked = false;
    elements.approveSubmit.classList.add("hidden");
    elements.approveSubmit.disabled = false;
    elements.approveSubmit.textContent = "Approve and submit application";
    elements.jobTitle.textContent = captured.title || "Captured job";
    elements.jobCompany.textContent = [captured.company, captured.location].filter(Boolean).join(" · ");
    elements.chatContext.textContent = captured.title || "Active job";
    elements.tailorResume.disabled = !(state.localMode && state.provider?.configured);
    elements.analyzeFit.disabled = !(state.localMode && state.provider?.configured);
    state.route = await api("/api/application-route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_url: captured.source_url,
        company_application_url: captured.company_application_url,
        company_url_verified: captured.company_url_verified,
        easy_apply_available: captured.easy_apply_available,
      }),
    });
    state.application = await api("/api/applications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job: captured, route: state.route }),
    });
    await transitionApplication("analyzed", "Job and application route analyzed.", {
      adapter: captured.adapter,
    });
    if (state.route.route === "company_site") {
      elements.openApplication.textContent = "Open company application";
      elements.openApplication.disabled = false;
    } else if (state.route.route === "manual_review") {
      elements.openApplication.textContent = "Review external application";
      elements.openApplication.disabled = false;
    } else if (state.route.route === "easy_apply") {
      elements.openApplication.textContent = "Easy Apply fallback available";
      elements.openApplication.disabled = true;
    } else {
      elements.openApplication.textContent = "No application route found";
      elements.openApplication.disabled = true;
    }
    if (captured.adapter === "linkedin") {
      const queue = await chrome.runtime.sendMessage({
        action: "collectJobQueue",
        tabId: captured.tab_id,
      });
      if (!queue.error) state.jobQueue = queue.urls;
    }
    return captured;
  } catch (error) {
    elements.jobCompany.textContent = error.message;
    if (throwOnError) throw error;
    return null;
  } finally {
    elements.captureJob.disabled = false;
    elements.captureJob.textContent = "Capture this job";
  }
}

async function openApplication(options = {}) {
  const throwOnError = options?.throwOnError === true;
  if (!state.route?.target_url) return;
  elements.openApplication.disabled = true;
  try {
    const result = await chrome.runtime.sendMessage({
      action: "openApplication",
      url: state.route.target_url,
    });
    if (result.error) throw new Error(result.error);
    elements.openApplication.textContent = "Company application opened";
    await transitionApplication("filling", "Opened the company application route.");
    return result;
  } catch (error) {
    elements.jobCompany.textContent = error.message;
    elements.openApplication.disabled = false;
    if (throwOnError) throw error;
    return null;
  }
}

async function analyzeJobFit(options = {}) {
  const throwOnError = options?.throwOnError === true;
  if (!state.job) return null;
  elements.analyzeFit.disabled = true;
  elements.analyzeFit.textContent = "Analyzing fit…";
  elements.fitResult.classList.remove("hidden");
  elements.fitResult.textContent = "Comparing verified résumé evidence with the job requirements.";
  try {
    state.fitAnalysis = await api("/api/jobs/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job: state.job }),
    });
    const fit = state.fitAnalysis;
    renderFitAnalysis(fit);
    return fit;
  } catch (error) {
    elements.fitResult.textContent = error.message;
    if (throwOnError) throw error;
    return null;
  } finally {
    elements.analyzeFit.disabled = false;
    elements.analyzeFit.textContent = "Analyze job fit";
  }
}

function renderFitAnalysis(fit) {
  elements.fitResult.classList.remove("hidden");
  elements.fitResult.innerHTML = `
    <strong>${fit.score}% match · ${escapeHtml(fit.verdict)}</strong>
    <p>${escapeHtml(fit.summary)}</p>
    <p><strong>Strengths:</strong> ${escapeHtml(fit.strengths.join(" · ") || "None verified")}</p>
    <p><strong>Gaps:</strong> ${escapeHtml(fit.gaps.join(" · ") || "No material gaps identified")}</p>
    <p><strong>Recommendation:</strong> ${escapeHtml(fit.recommendation)}</p>
  `;
}

async function tailorResume(options = {}) {
  const throwOnError = options?.throwOnError === true;
  if (!state.job) return;
  elements.tailorResume.disabled = true;
  elements.tailorResume.textContent = "Tailoring with evidence…";
  elements.tailorResult.classList.remove("hidden");
  elements.tailorResult.textContent = `${PROVIDERS[state.provider.provider].label} is matching the job to verified résumé facts.`;
  try {
    state.artifact = await api("/api/tailored", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job: state.job, application_id: state.application?.id || "" }),
    });
    renderTailoredArtifact();
    await transitionApplication("materials_ready", "Created an evidence-grounded tailored draft.");
    return state.artifact;
  } catch (error) {
    elements.tailorResult.textContent = error.message;
    if (throwOnError) throw error;
    return null;
  } finally {
    elements.tailorResume.disabled = false;
    elements.tailorResume.textContent = "Tailor résumé";
  }
}

function renderTailoredArtifact() {
  const tailored = state.artifact.tailored;
  const warnings = tailored.warnings.length
    ? `<p><strong>Warnings:</strong> ${escapeHtml(tailored.warnings.join(" "))}</p>`
    : "";
  elements.tailorResult.classList.remove("hidden");
  elements.tailorResult.innerHTML = `
    <strong>${escapeHtml(tailored.headline)}</strong>
    <p>${escapeHtml(tailored.summary)}</p>
    <p><strong>Skills:</strong> ${escapeHtml(tailored.skills.join(", "))}</p>
    ${warnings}
  `;
  elements.artifactActions.classList.remove("hidden");
  updateAttachButton();
}

async function prepareJobMaterials() {
  const prepared = await api("/api/jobs/prepare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job: state.job, application_id: state.application?.id || "" }),
  });
  state.fitAnalysis = prepared.analysis;
  state.artifact = prepared.artifact;
  renderFitAnalysis(state.fitAnalysis);
  renderTailoredArtifact();
  await transitionApplication("materials_ready", "Analyzed fit and created a verified job-specific résumé.");
  return prepared;
}

async function scanForm(options = {}) {
  const throwOnError = options?.throwOnError === true;
  elements.scanForm.disabled = true;
  elements.scanForm.textContent = "Analyzing fields…";
  elements.formResult.classList.remove("hidden");
  try {
    await requireSiteAccess();
    const scan = await chrome.runtime.sendMessage({ action: "scanForm" });
    if (scan.error) throw new Error(scan.error);
    if (!scan.fields.length) throw new Error("No fillable fields were found on this page.");
    state.formScan = scan;
    await transitionApplication("filling", "Application form fields detected.", {
      adapter: scan.adapter,
      field_count: String(scan.fields.length),
    });
    await replanForm();
    return state.formPlan;
  } catch (error) {
    elements.formStatus.textContent = error.message;
    elements.formResult.textContent = "Nothing was changed on the page.";
    if (throwOnError) throw error;
    return null;
  } finally {
    elements.scanForm.disabled = false;
    elements.scanForm.textContent = "Analyze visible fields";
  }
}

async function replanForm() {
  state.formPlan = await api("/api/forms/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.formScan),
  });
  const requiredUnknown = unresolvedRequiredUnknowns();
  const requiredBlocked = state.formPlan.blocked_fields.filter((field) => field.required);
  elements.formStatus.textContent = `${state.formScan.fields.length} fields found · ${state.formPlan.actions.length} known`;
  elements.formResult.innerHTML = `
    <strong>${state.formPlan.actions.length} fields ready</strong>
    <p>${requiredUnknown.length} required questions need your answer.</p>
    <p>${state.formPlan.blocked_fields.length} sensitive/authentication fields will be left alone.</p>
    <p>The final Submit button will not be clicked.</p>
  `;
  elements.fillForm.disabled = state.formPlan.actions.length === 0;
  updateAttachButton();

  if (requiredUnknown.length) {
    const [firstUnknown] = requiredUnknown;
    elements.unknownAnswerForm.classList.remove("hidden");
    elements.unknownQuestion.textContent = firstUnknown.label;
    elements.unknownAnswer.value = "";
    await transitionApplication("blocked", "A required question needs a verified answer.", {
      question: firstUnknown.label,
    });
  } else {
    elements.unknownAnswerForm.classList.add("hidden");
    if (requiredBlocked.length) {
      await transitionApplication("blocked", "A required authentication field needs the user.", {
        field: requiredBlocked[0].label,
      });
    } else if (state.application?.status === "blocked") {
      await transitionApplication("filling", "All required questions now have verified answers.");
    }
  }
}

function unresolvedRequiredUnknowns() {
  return (state.formPlan?.unknown_fields || []).filter((field) => {
    if (!field.required) return false;
    const scanned = state.formScan?.fields.find((candidate) => candidate.id === field.field_id);
    return !(scanned?.field_type === "file" && state.artifact);
  });
}

function updateAttachButton() {
  const fileField = state.formScan?.fields.find((field) => field.field_type === "file");
  elements.attachResume.disabled = !(state.artifact && fileField);
}

function openArtifact(extension) {
  if (!state.artifact) return;
  chrome.tabs.create({
    url: `${state.apiBase}/api/tailored/${state.artifact.id}.${extension}`,
    active: false,
  });
}

async function attachTailoredResume(options = {}) {
  const throwOnError = options?.throwOnError === true;
  const fileField = state.formScan?.fields.find((field) => field.field_type === "file");
  if (!state.artifact || !fileField) return false;
  elements.attachResume.disabled = true;
  const result = await chrome.runtime.sendMessage({
    action: "attachResume",
    fieldId: fileField.id,
    url: `${state.apiBase}/api/tailored/${state.artifact.id}.docx`,
    filename: "tailored-resume.docx",
  });
  if (result.error || !result.attached) {
    elements.formStatus.textContent = result.error || "The tailored resume could not be attached.";
    elements.attachResume.disabled = false;
    if (throwOnError) throw new Error(elements.formStatus.textContent);
    return false;
  }
  elements.formStatus.textContent = `${result.filename} attached for review.`;
  elements.attachResume.textContent = "Tailored résumé attached";
  return true;
}

async function maybeAttachTailoredResume() {
  const fileField = state.formScan?.fields.find((field) => field.field_type === "file");
  if (!state.artifact || !fileField) return true;
  const allowed = state.resumePolicy === "always_attach" || window.confirm(
    "Attach the job-specific tailored résumé to this application? Your original résumé will not be changed.",
  );
  if (!allowed) return false;
  return attachTailoredResume({ throwOnError: true });
}

async function saveUnknownAnswer(event) {
  event.preventDefault();
  const answer = elements.unknownAnswer.value.trim();
  const question = elements.unknownQuestion.textContent.trim();
  if (!answer || !question) return;
  const id = crypto.randomUUID();
  await api(`/api/answers/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, question, answer, field_type: "text", sensitive: false }),
  });
  state.answers = await api("/api/answers");
  await replanForm();
}

async function fillForm(options = {}) {
  const throwOnError = options?.throwOnError === true;
  if (!state.formPlan) return;
  elements.fillForm.disabled = true;
  elements.fillForm.textContent = "Filling…";
  try {
    const result = await chrome.runtime.sendMessage({
      action: "fillForm",
      actions: state.formPlan.actions,
    });
    if (result.error) throw new Error(result.error);
    elements.formStatus.textContent = `${result.filled} fields filled for your review.`;
    elements.formResult.innerHTML = `
      <strong>Review the page carefully</strong>
      <p>${result.errors.length ? escapeHtml(result.errors.join(" ")) : "No fill errors detected."}</p>
      <p>ApplyPilot did not submit the application.</p>
    `;
    const requiredUnknown = unresolvedRequiredUnknowns().length > 0;
    const requiredBlocked = state.formPlan.blocked_fields.some((field) => field.required);
    if (!requiredUnknown && !requiredBlocked) {
      await transitionApplication(
        "review_required",
        "Known fields were filled; final user review is required.",
      );
      elements.approveSubmit.classList.remove("hidden");
    }
    return result;
  } catch (error) {
    elements.formStatus.textContent = error.message;
    if (throwOnError) throw error;
    return null;
  } finally {
    elements.fillForm.disabled = false;
    elements.fillForm.textContent = "Fill known fields";
  }
}

async function approveAndSubmit(options = {}) {
  const automatic = options?.automatic === true;
  const throwOnError = options?.throwOnError === true;
  try {
    if (!state.submitClicked) {
      const confirmed = automatic || window.confirm(
        "ApplyPilot will click the final Submit button now. Confirm that you reviewed every field.",
      );
      if (!confirmed) return;

      elements.approveSubmit.disabled = true;
      elements.approveSubmit.textContent = "Submitting…";
      const result = await chrome.runtime.sendMessage({ action: "submitApplication" });
      if (result.error || !result.clicked) {
        throw new Error(result.error || "Submission was not completed.");
      }
      state.submitClicked = true;
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }

    const verification = await chrome.runtime.sendMessage({ action: "verifySubmission" });
    if (verification.error || !verification.confirmed) {
      elements.formStatus.textContent =
        verification.error || "Submit was clicked, but site confirmation is not visible yet.";
      elements.approveSubmit.disabled = false;
      elements.approveSubmit.textContent = "Verify site result";
      return false;
    }
    await transitionApplication(
      "submitted",
      "The user approved submission and the employer site displayed confirmation.",
      { signal: verification.signal },
    );
    elements.approveSubmit.textContent = "Submission confirmed";
    if (!automatic && state.automationRunning) {
      await advanceAutomationQueue({ submitted: true });
    }
    return true;
  } catch (error) {
    elements.formStatus.textContent = error.message;
    elements.approveSubmit.disabled = false;
    elements.approveSubmit.textContent = state.submitClicked
      ? "Verify site result"
      : "Approve and submit application";
    if (throwOnError) throw error;
    return false;
  }
}

function setAutomationRunning(running, message) {
  state.automationRunning = running;
  elements.startAutomation.disabled = running;
  elements.stopAutomation.disabled = !running;
  if (message) elements.automationStatus.textContent = message;
}

async function startAutomation() {
  if (state.automationRunning) return;
  state.jobsProcessed = 0;
  state.applicationsSubmitted = 0;
  state.seenJobUrls = new Set();
  state.jobQueue = [];
  setAutomationRunning(true, "Starting from the active job page…");
  try {
    await requireSiteAccess();
    await runAutomationCycle();
  } catch (error) {
    setAutomationRunning(false, `Paused: ${error.message}`);
  }
}

function stopAutomation() {
  setAutomationRunning(false, "Stopped by you.");
}

async function runAutomationCycle() {
  if (!state.automationRunning) return;
  if (state.jobsProcessed >= 10) {
    setAutomationRunning(false, "Run complete: reached the 10-job per-run safety limit.");
    return;
  }

  state.job = null;
  state.route = null;
  state.application = null;
  state.formPlan = null;
  state.formScan = null;
  state.artifact = null;
  state.submitClicked = false;
  elements.automationStatus.textContent = "Reading the current job and company route…";
  const captured = await captureJob({ throwOnError: true });
  state.seenJobUrls.add(normalizeJobUrl(captured.source_url));
  state.jobQueue = state.jobQueue.filter(
    (url) => !state.seenJobUrls.has(normalizeJobUrl(url)),
  );

  if (state.provider?.configured) {
    elements.automationStatus.textContent = "Analyzing fit and preparing a job-specific résumé…";
    await prepareJobMaterials();
    if (
      state.automationPolicy === "always_allow" &&
      state.fitAnalysis &&
      state.fitAnalysis.score < state.minimumFit
    ) {
      elements.automationStatus.textContent =
        `Skipped ${state.job.title || "job"}: ${state.fitAnalysis.score}% is below your ${state.minimumFit}% minimum.`;
      await advanceAutomationQueue({ submitted: false });
      return;
    }
  }
  if (!state.automationRunning) return;

  const target = state.route?.target_url || "";
  if (["company_site", "manual_review"].includes(state.route?.route) && target) {
    if (normalizeJobUrl(target) !== normalizeJobUrl(captured.source_url)) {
      elements.automationStatus.textContent = "Opening the company application…";
      const opened = await openApplication({ throwOnError: true });
      await waitForTabReady(opened.tab_id);
    }
  } else if (state.route?.route === "easy_apply") {
    elements.automationStatus.textContent = "Opening LinkedIn Easy Apply fallback…";
    const easyApply = await chrome.runtime.sendMessage({ action: "openEasyApply" });
    if (easyApply.error || !easyApply.opened) {
      throw new Error(easyApply.error || "Easy Apply could not be opened.");
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  elements.automationStatus.textContent = "Scanning and filling known fields from your profile…";
  const plan = await scanForm({ throwOnError: true });
  const unknown = unresolvedRequiredUnknowns();
  const blocked = plan.blocked_fields.filter((field) => field.required);
  if (unknown.length) {
    throw new Error(`Answer required: ${unknown[0].label}`);
  }
  if (blocked.length) {
    throw new Error(`User action required: ${blocked[0].label}`);
  }
  if (plan.actions.length) await fillForm({ throwOnError: true });

  if (state.artifact && state.formScan.fields.some((field) => field.field_type === "file")) {
    elements.automationStatus.textContent = "Selecting the job-specific tailored résumé…";
    const attached = await maybeAttachTailoredResume();
    if (!attached && state.automationPolicy === "always_allow") {
      throw new Error("Tailored résumé attachment was not approved.");
    }
  }

  if (state.application?.status !== "review_required") {
    await transitionApplication(
      "review_required",
      "All known fields and the selected résumé are ready for final review.",
    );
  }

  if (state.automationPolicy === "review_each") {
    elements.approveSubmit.classList.remove("hidden");
    elements.automationStatus.textContent =
      "Ready for review. Approve submission to send this application and continue.";
    return;
  }

  elements.automationStatus.textContent = "Submitting automatically under Always allow…";
  const submitted = await approveAndSubmit({ automatic: true, throwOnError: true });
  if (!submitted) throw new Error("The employer site did not confirm submission.");
  await advanceAutomationQueue({ submitted: true });
}

async function advanceAutomationQueue({ submitted = false } = {}) {
  state.jobsProcessed += 1;
  if (submitted) state.applicationsSubmitted += 1;
  if (!state.automationRunning) return;
  if (!elements.continueNext.checked || !state.jobQueue.length || !state.sourceTabId) {
    setAutomationRunning(
      false,
      `Run complete: ${state.applicationsSubmitted} submitted, ${state.jobsProcessed - state.applicationsSubmitted} skipped or paused.`,
    );
    return;
  }
  const nextUrl = state.jobQueue.shift();
  elements.automationStatus.textContent = "Moving to the next queued LinkedIn job…";
  const opened = await chrome.runtime.sendMessage({
    action: "openQueuedJob",
    tabId: state.sourceTabId,
    url: nextUrl,
  });
  if (opened.error) throw new Error(opened.error);
  await runAutomationCycle();
}

async function waitForTabReady(tabId) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    if (!state.automationRunning) return;
    const tab = await chrome.runtime.sendMessage({ action: "getTab", tabId });
    if (tab.error) throw new Error(tab.error);
    if (tab.status === "complete") return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("The application page took too long to load.");
}

function normalizeJobUrl(value) {
  try {
    const url = new URL(value);
    url.search = "";
    url.hash = "";
    return url.href;
  } catch {
    return value || "";
  }
}

async function sendChat(event) {
  event.preventDefault();
  const message = elements.chatInput.value.trim();
  if (!message && !state.chatImages.length) return;
  const images = [...state.chatImages];
  appendMessage(message || "Analyze the attached image.", "user-message", images);
  elements.chatInput.value = "";
  state.chatImages = [];
  renderImagePreviews();
  elements.chatButton.disabled = true;

  try {
    let activeJob = state.job;
    if (!activeJob) {
      try {
        await requireSiteAccess();
        const context = await chrome.runtime.sendMessage({ action: "readPageContext" });
        if (!context.error && context.text) {
          activeJob = {
            source_url: context.url,
            title: context.title || "Current page",
            company: "",
            location: "",
            description: context.text,
            adapter: "generic",
          };
        }
      } catch {
        // Chat can still answer without page context.
      }
    }
    const response = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message || "Analyze the attached image in the context of this application.",
        job: activeJob,
        images: images.map(({ filename, mediaType, dataBase64 }) => ({
          filename,
          media_type: mediaType,
          data_base64: dataBase64,
        })),
      }),
    });
    appendMessage(response.answer, "agent-message");
  } catch (error) {
    appendMessage(error.message, "agent-message");
  } finally {
    updateChatAvailability();
  }
}

function appendMessage(text, className, images = []) {
  const message = document.createElement("div");
  message.className = `message ${className}`;
  if (images.length) {
    const imageRow = document.createElement("div");
    imageRow.className = "message-images";
    images.forEach((image) => {
      const thumbnail = document.createElement("img");
      thumbnail.src = `data:${image.mediaType};base64,${image.dataBase64}`;
      thumbnail.alt = image.filename;
      imageRow.append(thumbnail);
    });
    message.append(imageRow);
  }
  const copy = document.createElement("div");
  copy.textContent = text;
  message.append(copy);
  elements.messages.append(message);
  message.scrollIntoView({ behavior: "smooth", block: "end" });
}

async function addChatImages() {
  const files = [...elements.chatImages.files];
  elements.chatImages.value = "";
  for (const file of files) {
    if (state.chatImages.length >= 3) {
      appendMessage("You can attach up to 3 images per message.", "agent-message");
      break;
    }
    if (file.size > 4 * 1024 * 1024) {
      appendMessage(`${file.name} is larger than 4 MB.`, "agent-message");
      continue;
    }
    if (!["image/png", "image/jpeg", "image/webp", "image/gif"].includes(file.type)) {
      appendMessage(`${file.name} is not a supported image type.`, "agent-message");
      continue;
    }
    const dataUrl = await readFileAsDataUrl(file);
    state.chatImages.push({
      filename: file.name,
      mediaType: file.type,
      dataBase64: dataUrl.split(",", 2)[1],
    });
  }
  renderImagePreviews();
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function renderImagePreviews() {
  elements.imagePreviews.classList.toggle("hidden", state.chatImages.length === 0);
  elements.imagePreviews.replaceChildren(
    ...state.chatImages.map((image, index) => {
      const wrapper = document.createElement("div");
      wrapper.className = "image-preview";
      const thumbnail = document.createElement("img");
      thumbnail.src = `data:${image.mediaType};base64,${image.dataBase64}`;
      thumbnail.alt = image.filename;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.title = `Remove ${image.filename}`;
      remove.addEventListener("click", () => {
        state.chatImages.splice(index, 1);
        renderImagePreviews();
      });
      wrapper.append(thumbnail, remove);
      return wrapper;
    }),
  );
}

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = value;
  return element.innerHTML;
}

elements.answerForm.addEventListener("submit", saveOnboardingAnswer);
elements.editProfile.addEventListener("click", openProfileEditor);
elements.profileEditor.addEventListener("submit", saveProfile);
elements.cancelProfile.addEventListener("click", () => elements.profileEditor.classList.add("hidden"));
elements.resumeFile.addEventListener("change", uploadResume);
elements.captureJob.addEventListener("click", captureJob);
elements.openApplication.addEventListener("click", openApplication);
elements.tailorResume.addEventListener("click", tailorResume);
elements.analyzeFit.addEventListener("click", analyzeJobFit);
elements.downloadDocx.addEventListener("click", () => openArtifact("docx"));
elements.downloadPdf.addEventListener("click", () => openArtifact("pdf"));
elements.attachResume.addEventListener("click", attachTailoredResume);
elements.scanForm.addEventListener("click", scanForm);
elements.fillForm.addEventListener("click", fillForm);
elements.unknownAnswerForm.addEventListener("submit", saveUnknownAnswer);
elements.approveSubmit.addEventListener("click", approveAndSubmit);
elements.chatForm.addEventListener("submit", sendChat);
elements.chatImages.addEventListener("change", addChatImages);
elements.providerForm.addEventListener("submit", saveProvider);
elements.disconnectProvider.addEventListener("click", disconnectProvider);
elements.providerSelect.addEventListener("change", changeProvider);
elements.enableSiteAccess.addEventListener("click", async () => {
  try {
    await requestSiteAccess();
  } catch (error) {
    elements.automationStatus.textContent = error.message;
  }
});
elements.automationPolicy.addEventListener("change", changeAutomationPolicy);
elements.resumePolicy.addEventListener("change", changeResumePolicy);
elements.minimumFit.addEventListener("change", changeMinimumFit);
elements.continueNext.addEventListener("change", changeContinueNext);
elements.startAutomation.addEventListener("click", startAutomation);
elements.stopAutomation.addEventListener("click", stopAutomation);
elements.toggleKey.addEventListener("click", () => {
  const showing = elements.providerKey.type === "text";
  elements.providerKey.type = showing ? "password" : "text";
  elements.toggleKey.textContent = showing ? "Show" : "Hide";
});
elements.refresh.addEventListener("click", loadState);
elements.settings.addEventListener("click", () => {
  elements.providerCard.scrollIntoView({ behavior: "smooth", block: "start" });
  elements.providerSelect.focus();
});
loadState();
