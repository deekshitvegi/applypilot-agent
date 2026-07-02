const DEFAULT_API_BASE = "http://127.0.0.1:8765";

const elements = {
  connection: document.querySelector("#connection"),
  offlineCard: document.querySelector("#offline-card"),
  retryConnection: document.querySelector("#retry-connection"),
  advancedSettings: document.querySelector("#advanced-settings"),
  question: document.querySelector("#question"),
  progress: document.querySelector("#progress"),
  refresh: document.querySelector("#refresh"),
  settings: document.querySelector("#settings"),
  providerCard: document.querySelector("#provider-card"),
  providerForm: document.querySelector("#provider-form"),
  providerSelect: document.querySelector("#provider-select"),
  providerKey: document.querySelector("#provider-key"),
  providerKeyLabel: document.querySelector("#provider-key-label"),
  providerKeyRow: document.querySelector("#provider-key-row"),
  providerModel: document.querySelector("#provider-model"),
  providerHelp: document.querySelector("#provider-help"),
  providerPrivacy: document.querySelector("#provider-privacy"),
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
  loginAssistance: document.querySelector("#login-assistance"),
  automationWarning: document.querySelector("#automation-warning"),
  downloadHistory: document.querySelector("#download-history"),
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
  includeOptionalQuestions: document.querySelector("#include-optional-questions"),
  formStatus: document.querySelector("#form-status"),
  formResult: document.querySelector("#form-result"),
  unknownAnswerForm: document.querySelector("#unknown-answer-form"),
  unknownProgress: document.querySelector("#unknown-progress"),
  unknownQuestion: document.querySelector("#unknown-question"),
  unknownAnswer: document.querySelector("#unknown-answer"),
  unknownChoice: document.querySelector("#unknown-choice"),
  draftUnknown: document.querySelector("#draft-unknown"),
  skipUnknown: document.querySelector("#skip-unknown"),
  saveUnknown: document.querySelector("#save-unknown"),
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
  resume: null,
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
  applicationSteps: 0,
  applicationStarted: false,
  lastStepFingerprint: "",
  minimumFit: 60,
  siteAccessGranted: false,
  loginAssistance: false,
  questionnaireActive: false,
  questionnaireTotal: 0,
  skippedFieldIds: new Set(),
  lastActivity: "",
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
  ollama: {
    label: "Ollama",
    model: "qwen3:4b",
    keyRequired: false,
    help: "Runs privately with no API key or usage limits. Qwen3 4B is the balanced low-memory default; image attachments use local gemma3:4b.",
  },
  gemini: {
    label: "Google Gemini",
    model: "gemini-2.5-flash",
    keyRequired: true,
    help: "Create a key in Google AI Studio. Gemini offers a limited free tier.",
  },
  openai: {
    label: "OpenAI",
    model: "gpt-5-mini",
    keyRequired: true,
    help: "Use an OpenAI Platform API key. ChatGPT subscriptions do not include API usage.",
  },
  anthropic: {
    label: "Anthropic Claude",
    model: "claude-sonnet-4-20250514",
    keyRequired: true,
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
  await persistJobContext();
  return state.application;
}

async function persistJobContext() {
  if (!state.job) return;
  await chrome.runtime.sendMessage({
    action: "saveJobContext",
    context: {
      job: state.job,
      route: state.route,
      application: state.application,
      sourceTabId: state.sourceTabId,
      jobQueue: state.jobQueue,
      applicationStarted: state.applicationStarted,
    },
  });
}

async function restoreJobContext() {
  const context = await chrome.runtime.sendMessage({ action: "loadJobContext" });
  if (context.error || !context.job) return;
  state.job = context.job;
  state.route = context.route || null;
  state.application = context.application || null;
  state.sourceTabId = context.sourceTabId || null;
  state.jobQueue = context.jobQueue || [];
  state.applicationStarted = context.applicationStarted === true;
  elements.jobTitle.textContent = state.job.title || "Captured job";
  elements.jobCompany.textContent = [state.job.company, state.job.location].filter(Boolean).join(" · ");
  elements.chatContext.textContent = state.job.title || "Active job";
  elements.openApplication.disabled = !state.route?.target_url;
  elements.tailorResume.disabled = !(state.localMode && state.provider?.configured);
  elements.analyzeFit.disabled = !(state.localMode && state.provider?.configured);
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
    document.body.classList.remove("agent-offline");
    elements.offlineCard.classList.add("hidden");
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
    await restoreJobContext();
  } catch (error) {
    elements.connection.textContent = "Agent is offline";
    document.body.classList.add("agent-offline");
    elements.offlineCard.classList.remove("hidden");
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
    loginAssistance: false,
  });
  state.automationPolicy = saved.automationPolicy;
  state.resumePolicy = saved.resumePolicy === "always_attach" ? "always_tailored" : saved.resumePolicy;
  state.minimumFit = saved.minimumFit;
  elements.automationPolicy.value = saved.automationPolicy;
  elements.resumePolicy.value = state.resumePolicy;
  elements.minimumFit.value = String(saved.minimumFit);
  elements.continueNext.checked = saved.continueNext;
  state.loginAssistance = saved.loginAssistance;
  elements.loginAssistance.checked = saved.loginAssistance;
  renderAutomationPolicy();
}

function renderAutomationPolicy() {
  const automatic = state.automationPolicy === "always_allow";
  elements.automationWarning.classList.toggle("hidden", !automatic);
  elements.startAutomation.textContent = automatic ? "Start automatic run" : "Start applying";
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

async function changeLoginAssistance() {
  if (elements.loginAssistance.checked) {
    const confirmed = window.confirm(
      "Allow ApplyPilot to wait for your browser password manager, click unique Sign in/Next controls, and resume the application automatically? It never reads or stores credentials and cannot bypass CAPTCHA, MFA, verification codes, or security checks.",
    );
    if (!confirmed) {
      elements.loginAssistance.checked = false;
      return;
    }
  }
  state.loginAssistance = elements.loginAssistance.checked;
  await chrome.storage.local.set({ loginAssistance: state.loginAssistance });
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
  const localReady = Boolean(state.localMode);
  const aiReady = Boolean(state.localMode && state.provider?.configured);
  elements.chatInput.disabled = !localReady;
  elements.chatButton.disabled = !localReady;
  elements.chatImages.disabled = !aiReady;
  elements.attachImageLabel.classList.toggle("disabled", !aiReady);
  elements.chatInput.placeholder = aiReady
    ? "Ask ApplyPilot…"
    : "Try “fill this page” or connect an AI provider for questions";
}

function renderProvider() {
  const provider = state.provider || {
    provider: elements.providerSelect.value,
    model: PROVIDERS[elements.providerSelect.value].model,
    configured: false,
    source: "none",
  };
  const providerDefinition = PROVIDERS[provider.provider] || PROVIDERS.ollama;
  elements.providerSelect.value = provider.provider;
  elements.providerModel.value = provider.model || providerDefinition.model;
  elements.providerKeyLabel.classList.toggle("hidden", !providerDefinition.keyRequired);
  elements.providerKeyRow.classList.toggle("hidden", !providerDefinition.keyRequired);
  elements.providerPrivacy.textContent = providerDefinition.keyRequired
    ? "Your key is encrypted by the local agent and never saved in the extension."
    : "Runs on this computer with no API key or cloud quota.";
  elements.providerKey.value = "";
  elements.providerKey.placeholder = provider.configured
    ? "Saved key is active — paste only to replace it"
    : "Paste a newly generated key";
  elements.providerTitle.textContent = provider.configured
    ? providerDefinition.label
    : "Connect a model";
  elements.providerBadge.textContent = provider.configured ? "Connected" : "Not configured";
  elements.providerBadge.classList.toggle("connected", provider.configured);
  elements.disconnectProvider.disabled = !provider.configured || provider.source === "environment";
  elements.providerHelp.textContent = provider.configured
    ? provider.provider === "ollama"
      ? `AI features run locally with ${provider.model}. No API key or cloud quota is used.`
      : `AI features are active with ${provider.model}. ${provider.source === "environment" ? "Loaded from the local environment." : "The saved key is encrypted in your local ApplyPilot database."}`
    : providerDefinition.help;
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
  if ((!apiKey && PROVIDERS[provider].keyRequired) || !model) {
    elements.providerHelp.textContent = PROVIDERS[provider].keyRequired
      ? "Enter both an API key and model name."
      : "Enter the installed Ollama model name.";
    return;
  }
  elements.providerHelp.textContent = provider === "ollama"
    ? "Connecting to the local Ollama model…"
    : "Encrypting and saving locally…";
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
  elements.providerKeyLabel.classList.toggle("hidden", !PROVIDERS[provider].keyRequired);
  elements.providerKeyRow.classList.toggle("hidden", !PROVIDERS[provider].keyRequired);
  elements.providerPrivacy.textContent = PROVIDERS[provider].keyRequired
    ? "Your key is encrypted by the local agent and never saved in the extension."
    : "Runs on this computer with no API key or cloud quota.";
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
    state.resume = resume;
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
    state.resume = resume;
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
    state.formPlan = null;
    state.formScan = null;
    elements.fitResult.classList.add("hidden");
    elements.artifactActions.classList.add("hidden");
    state.submitClicked = false;
    elements.approveSubmit.classList.add("hidden");
    elements.approveSubmit.disabled = false;
    elements.approveSubmit.textContent = "Approve and submit application";
    elements.formStatus.textContent = "Open the employer application form first.";
    elements.formResult.classList.add("hidden");
    elements.unknownAnswerForm.classList.add("hidden");
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
        external_apply_available: captured.external_apply_available,
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
    } else if (state.route.route === "company_button") {
      elements.openApplication.textContent = "Open employer application";
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
    await persistJobContext();
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
  const updateApplicationState = options?.transition !== false;
  if (!state.route?.target_url) return;
  elements.openApplication.disabled = true;
  try {
    const result = state.route.route === "company_button"
      ? await chrome.runtime.sendMessage({ action: "openExternalApply" })
      : await chrome.runtime.sendMessage({
        action: "openApplication",
        url: state.route.target_url,
      });
    if (result.error) throw new Error(result.error);
    elements.openApplication.textContent = "Company application opened";
    if (updateApplicationState) {
      await transitionApplication("filling", "Opened the company application route.");
    }
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
    state.formPlan = null;
    state.formScan = null;
    elements.approveSubmit.classList.add("hidden");
    elements.unknownAnswerForm.classList.add("hidden");
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
    body: JSON.stringify({
      ...state.formScan,
      source_url: state.job?.source_url || "",
    }),
  });
  const reviewUnknown = unresolvedUnknowns();
  const requiredUnknown = unresolvedRequiredUnknowns();
  const optionalUnknown = (state.formPlan.unknown_fields || []).filter((field) => !field.required);
  const requiredBlocked = state.formPlan.blocked_fields.filter((field) => field.required);
  if (state.questionnaireActive && state.questionnaireTotal === 0) {
    state.questionnaireTotal = reviewUnknown.length;
  }
  elements.formStatus.textContent = `${state.formScan.fields.length} fields found · ${state.formPlan.actions.length} known`;
  elements.formResult.innerHTML = `
    <strong>${state.formPlan.actions.length} fields ready</strong>
    <p>${requiredUnknown.length} required question${requiredUnknown.length === 1 ? "" : "s"} need review.</p>
    <p>${optionalUnknown.length} optional blank field${optionalUnknown.length === 1 ? " is" : "s are"} ${elements.includeOptionalQuestions.checked ? "included for review" : "left untouched"}.</p>
    <p>${state.formPlan.blocked_fields.length} sensitive/authentication fields will be left alone.</p>
    <p>The final Submit button will not be clicked.</p>
  `;
  elements.fillForm.disabled = state.formPlan.actions.length === 0;
  updateAttachButton();

  if (reviewUnknown.length) {
    const [firstUnknown] = reviewUnknown;
    const scanned = state.formScan?.fields.find((field) => field.id === firstUnknown.field_id);
    elements.unknownAnswerForm.classList.remove("hidden");
    const unreadable = /^(field\s+\d+|unlabeled)/i.test(firstUnknown.label);
    elements.unknownQuestion.textContent = unreadable
      ? "Highlighted question on the page"
      : firstUnknown.label;
    elements.unknownAnswerForm.dataset.fieldId = firstUnknown.field_id;
    elements.unknownAnswerForm.dataset.unreadable = String(unreadable);
    elements.unknownAnswerForm.dataset.question = firstUnknown.label;
    elements.unknownAnswerForm.dataset.fieldType = scanned?.field_type || "text";
    const answered = Math.max(0, state.questionnaireTotal - reviewUnknown.length);
    elements.unknownProgress.textContent = `Question ${answered + 1} of ${Math.max(state.questionnaireTotal, reviewUnknown.length)}`;
    elements.unknownAnswer.value = "";
    elements.unknownAnswer.inputMode = scanned?.field_type === "number" ? "numeric" : "text";
    const options = uniqueQuestionOptions(scanned);
    const multiChoice = scanned?.field_type === "checkbox" && options.length > 2;
    const useChoice = options.length > 0 && !multiChoice;
    elements.unknownAnswer.placeholder = multiChoice
      ? `Enter one or more choices separated by commas: ${options.map((option) => option.label).join(", ")}`
      : "Enter your answer";
    elements.unknownChoice.classList.toggle("hidden", !useChoice);
    elements.unknownAnswer.classList.toggle("hidden", useChoice);
    elements.unknownChoice.replaceChildren();
    if (useChoice) {
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Select an answer";
      elements.unknownChoice.append(placeholder);
      options.forEach((option) => {
        const item = document.createElement("option");
        item.value = option.label;
        item.textContent = option.label;
        elements.unknownChoice.append(item);
      });
      elements.unknownChoice.value = "";
    }
    elements.draftUnknown.classList.toggle("hidden", !isNarrativeUnknown(firstUnknown));
    elements.draftUnknown.disabled = !state.provider?.configured;
    elements.saveUnknown.textContent = reviewUnknown.length === 1
      ? "Save answer and fill page"
      : "Save answer and continue";
    chrome.runtime.sendMessage({
      action: "highlightField",
      fieldId: firstUnknown.field_id,
      frameId: state.formScan?.frame_id ?? 0,
    }).catch(() => {});
    if (firstUnknown.required) {
      await transitionApplication("blocked", "A required question needs a verified answer.", {
        question: firstUnknown.label,
      });
    }
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

function uniqueQuestionOptions(scanned) {
  let options = scanned?.options || [];
  if (!options.length && ["checkbox", "radio"].includes(scanned?.field_type)) {
    options = [{ value: "Yes", label: "Yes" }, { value: "No", label: "No" }];
  }
  const seen = new Set();
  return options.filter((option) => {
    const label = String(option.label || option.value || "").replace(/\s+/g, " ").trim();
    const key = label.toLowerCase();
    if (!label || /^(select|select\.\.\.|choose|please select)$/i.test(label) || seen.has(key)) return false;
    seen.add(key);
    option.label = label;
    return true;
  });
}

function isNarrativeUnknown(unknown) {
  const scanned = state.formScan?.fields.find((field) => field.id === unknown.field_id);
  return scanned?.field_type === "textarea" && /why|interest|motivat|describe|tell us|cover letter/i.test(unknown.label);
}

async function requestApplicationAnswer(question) {
  return api("/api/questions/draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, job: state.job }),
  });
}

async function draftUnknownAnswer() {
  const question = elements.unknownAnswerForm.dataset.question || elements.unknownQuestion.textContent.trim();
  elements.draftUnknown.disabled = true;
  elements.draftUnknown.textContent = "Drafting…";
  try {
    const draft = await requestApplicationAnswer(question);
    elements.unknownAnswer.value = draft.answer;
    elements.unknownAnswer.focus();
  } catch (error) {
    elements.formStatus.textContent = error.message;
  } finally {
    elements.draftUnknown.disabled = false;
    elements.draftUnknown.textContent = "Draft with AI";
  }
}

async function resolveNarrativeUnknowns() {
  if (!state.provider?.configured) return;
  const narrative = unresolvedRequiredUnknowns().filter(isNarrativeUnknown).slice(0, 3);
  for (const unknown of narrative) {
    const draft = await requestApplicationAnswer(unknown.label);
    const result = await chrome.runtime.sendMessage({
      action: "fillForm",
      frameId: state.formScan?.frame_id ?? 0,
      actions: [
        {
          field_id: unknown.field_id,
          value: draft.answer,
          source: "ai.job_specific",
          confidence: 0.9,
        },
      ],
    });
    if (result.error) throw new Error(result.error);
  }
  if (narrative.length) await scanForm({ throwOnError: true });
}

function unresolvedRequiredUnknowns() {
  return (state.formPlan?.unknown_fields || []).filter((field) => {
    if (!field.required) return false;
    const scanned = state.formScan?.fields.find((candidate) => candidate.id === field.field_id);
    return !(scanned?.field_type === "file" && state.artifact);
  });
}

function unresolvedUnknowns() {
  const seenRadioGroups = new Set();
  return (state.formPlan?.unknown_fields || []).filter((field) => {
    if (state.skippedFieldIds.has(field.field_id)) return false;
    if (!field.required && !elements.includeOptionalQuestions.checked) return false;
    const scanned = state.formScan?.fields.find((candidate) => candidate.id === field.field_id);
    if (scanned?.field_type !== "radio") return true;
    const group = scanned.name || normalizeQuestion(field.label);
    if (seenRadioGroups.has(group)) return false;
    seenRadioGroups.add(group);
    return true;
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
    frameId: state.formScan?.frame_id ?? 0,
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

async function attachOriginalResume(options = {}) {
  const throwOnError = options?.throwOnError === true;
  const fileField = state.formScan?.fields.find((field) => field.field_type === "file");
  if (!fileField || !state.resume) return false;
  const result = await chrome.runtime.sendMessage({
    action: "attachResume",
    fieldId: fileField.id,
    frameId: state.formScan?.frame_id ?? 0,
    url: `${state.apiBase}/api/resumes/active/file`,
    filename: state.resume.filename,
  });
  if (result.error || !result.attached) {
    elements.formStatus.textContent = result.error || "The original résumé could not be attached.";
    if (throwOnError) throw new Error(elements.formStatus.textContent);
    return false;
  }
  elements.formStatus.textContent = `${result.filename} attached as the original résumé.`;
  return true;
}

async function maybeAttachResume() {
  const fileField = state.formScan?.fields.find((field) => field.field_type === "file");
  if (!fileField) return true;
  let choice = state.resumePolicy;
  if (choice === "ask_each") {
    choice = window.confirm(
      "Use the job-specific tailored résumé? Choose Cancel to use your original uploaded résumé.",
    ) ? "always_tailored" : "always_original";
  }
  if (choice === "always_tailored") {
    if (!state.artifact) {
      throw new Error("A tailored résumé is unavailable. Change the résumé preference to original or retry AI preparation.");
    }
    return attachTailoredResume({ throwOnError: true });
  }
  return attachOriginalResume({ throwOnError: true });
}

async function saveUnknownAnswer(event) {
  event.preventDefault();
  const answer = elements.unknownChoice.classList.contains("hidden")
    ? elements.unknownAnswer.value.trim()
    : elements.unknownChoice.value.trim();
  const question = elements.unknownAnswerForm.dataset.question || elements.unknownQuestion.textContent.trim();
  if (!answer || !question) return;
  if (elements.unknownAnswerForm.dataset.unreadable === "true") {
    const result = await chrome.runtime.sendMessage({
      action: "fillForm",
      frameId: state.formScan?.frame_id ?? 0,
      actions: [
        {
          field_id: elements.unknownAnswerForm.dataset.fieldId,
          value: answer,
          source: "user.current_page",
          confidence: 1,
        },
      ],
    });
    if (result.error) throw new Error(result.error);
    await scanForm();
    await continueQuestionnaire();
    return;
  }
  const existing = state.answers.find(
    (item) => normalizeQuestion(item.question) === normalizeQuestion(question),
  );
  const id = existing?.id || crypto.randomUUID();
  const scannedType = elements.unknownAnswerForm.dataset.fieldType || "text";
  const fieldType = scannedType === "number"
    ? "number"
    : ["select", "radio", "checkbox"].includes(scannedType) ? "choice" : "text";
  await api(`/api/answers/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, question, answer, field_type: fieldType, sensitive: false }),
  });
  state.answers = await api("/api/answers");
  await replanForm();
  await continueQuestionnaire();
}

function normalizeQuestion(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

async function skipUnknownQuestion() {
  const fieldId = elements.unknownAnswerForm.dataset.fieldId;
  if (!fieldId) return;
  state.skippedFieldIds.add(fieldId);
  await replanForm();
  await continueQuestionnaire();
}

async function continueQuestionnaire() {
  if (unresolvedUnknowns().length) return;
  state.questionnaireActive = false;
  elements.unknownAnswerForm.classList.add("hidden");
  elements.formStatus.textContent = "Answers collected. Filling the page…";
  if (state.formPlan?.actions.length) await fillForm({ throwOnError: true });
  if (state.automationRunning) await completeAutomationApplication();
}

async function startGuidedAnalysis() {
  state.questionnaireActive = true;
  state.questionnaireTotal = 0;
  state.skippedFieldIds = new Set();
  let plan = await scanForm();
  if (plan?.actions.length) {
    elements.formStatus.textContent = "Filling saved profile answers before asking questions…";
    await fillForm({ throwOnError: true });
    plan = await scanForm();
  }
  if (plan && !unresolvedUnknowns().length) await continueQuestionnaire();
}

async function fillForm(options = {}) {
  const throwOnError = options?.throwOnError === true;
  if (!state.formPlan) return;
  elements.fillForm.disabled = true;
  elements.fillForm.textContent = "Filling…";
  try {
    const result = await chrome.runtime.sendMessage({
      action: "fillForm",
      frameId: state.formScan?.frame_id ?? 0,
      actions: state.formPlan.actions,
    });
    if (result.error) throw new Error(result.error);
    elements.formStatus.textContent = `${result.filled} fields filled for your review.`;
    const fillErrors = humanizeFillErrors(result.errors || []);
    elements.formResult.innerHTML = `
      <strong>Review the page carefully</strong>
      ${fillErrors.length
        ? `<ul class="error-list">${fillErrors.map((error) => `<li>${escapeHtml(error)}</li>`).join("")}</ul>`
        : "<p>All mapped fields were filled successfully.</p>"}
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

function humanizeFillErrors(errors) {
  return errors.map((error) => {
    if (typeof error === "string") {
      const match = error.match(/^(ap-\d+):\s*(.*)$/);
      if (!match) return error;
      const field = state.formScan?.fields.find((candidate) => candidate.id === match[1]);
      return `${field?.label || "A form field"}: ${match[2]}`;
    }
    const field = state.formScan?.fields.find((candidate) => candidate.id === error.field_id);
    return `${field?.label || "A form field"}: ${error.message || "Could not fill this field."}`;
  });
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
      const result = await chrome.runtime.sendMessage({
        action: "submitApplication",
        frameId: state.formScan?.frame_id ?? 0,
      });
      if (result.error || !result.clicked) {
        throw new Error(result.error || "Submission was not completed.");
      }
      state.submitClicked = true;
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }

    const verification = await chrome.runtime.sendMessage({
      action: "verifySubmission",
      frameId: state.formScan?.frame_id ?? 0,
    });
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
  if (message) reportActivity(message);
}

function downloadApplicationHistory() {
  chrome.tabs.create({ url: `${state.apiBase}/api/applications.csv`, active: false });
  reportActivity("Exporting the local application history as CSV...");
}

function reportActivity(message) {
  if (!message) return;
  elements.automationStatus.textContent = message;
  if (state.lastActivity === message) return;
  state.lastActivity = message;
  appendMessage(message, "agent-message activity-message");
}

async function startAutomation() {
  if (state.automationRunning) return;
  const activeTab = await chrome.runtime.sendMessage({ action: "getActiveTab" });
  const resumeCapturedJob = Boolean(
    state.job?.description && activeTab.url &&
    normalizeJobUrl(activeTab.url) !== normalizeJobUrl(state.job.source_url),
  );
  state.jobsProcessed = 0;
  state.applicationsSubmitted = 0;
  state.seenJobUrls = new Set();
  if (!resumeCapturedJob) state.jobQueue = [];
  setAutomationRunning(
    true,
    resumeCapturedJob
      ? `Continuing ${state.job.title || "the captured job"} on this application page…`
      : "Starting from the active job page…",
  );
  try {
    await requireSiteAccess();
    if (resumeCapturedJob) await runCurrentApplicationPage();
    else await runAutomationCycle();
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
  state.applicationSteps = 0;
  state.applicationStarted = false;
  state.lastStepFingerprint = "";
  reportActivity("Reading the current job and company route…");
  const captured = await captureJob({ throwOnError: true });
  state.seenJobUrls.add(normalizeJobUrl(captured.source_url));
  state.jobQueue = state.jobQueue.filter(
    (url) => !state.seenJobUrls.has(normalizeJobUrl(url)),
  );

  const target = state.route?.target_url || "";
  let companyRouteReady = false;
  if (state.route?.route === "company_button") {
    reportActivity("Opening the employer application from this job page...");
    const opened = await openApplication({ throwOnError: true, transition: false });
    await waitForTabReady(opened.tab_id);
    companyRouteReady = true;
  } else if (["company_site", "manual_review"].includes(state.route?.route) && target) {
    companyRouteReady = true;
    if (normalizeJobUrl(target) !== normalizeJobUrl(captured.source_url)) {
      reportActivity("Opening the company application...");
      const opened = await openApplication({ throwOnError: true, transition: false });
      await waitForTabReady(opened.tab_id);
    }
  }
  if (companyRouteReady) {
    const entry = await chrome.runtime.sendMessage({ action: "openApplicationForm" });
    if (entry.clicked) {
      state.applicationStarted = true;
      await persistJobContext();
      reportActivity("Opening the employer's application form...");
      await waitForTabReady(entry.tab_id);
    }
  }

  if (state.provider?.configured) {
    reportActivity("Analyzing fit and preparing a job-specific résumé…");
    try {
      await prepareJobMaterials();
      if (
        state.automationPolicy === "always_allow" &&
        state.fitAnalysis &&
        state.fitAnalysis.score < state.minimumFit
      ) {
        await transitionApplication(
          "blocked",
          "Application paused because the fit score is below the automatic-application minimum.",
          { score: String(state.fitAnalysis.score), minimum: String(state.minimumFit) },
        );
        setAutomationRunning(
          false,
          `Paused: fit score ${state.fitAnalysis.score}% is below your ${state.minimumFit}% minimum. No application was submitted and the queue did not advance.`,
        );
        return;
      }
    } catch (error) {
      reportActivity(`${error.message} Continuing with free deterministic autofill.`);
    }
  }
  if (!state.automationRunning) return;

  if (companyRouteReady) {
    await transitionApplication("filling", "Opened the company application route.");
  } else if (state.route?.route === "easy_apply") {
    reportActivity("Opening LinkedIn Easy Apply fallback…");
    const easyApply = await chrome.runtime.sendMessage({ action: "openEasyApply" });
    if (easyApply.error || !easyApply.opened) {
      throw new Error(easyApply.error || "Easy Apply could not be opened.");
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  } else {
    throw new Error("No employer application route was found for this job.");
  }

  await runCurrentApplicationPage();
}

async function runCurrentApplicationPage() {
  if (!state.applicationStarted) {
    const entry = await chrome.runtime.sendMessage({ action: "openApplicationForm" });
    if (entry.error && !entry.already_form) {
      reportActivity(`${entry.error} Checking the current page for a form…`);
      const planned = await planAndClickPageAction(
        "Open or start this job application. Do not submit the application.",
      );
      if (planned?.clicked) {
        state.applicationStarted = true;
        await persistJobContext();
        reportActivity(`AI page planner selected “${planned.label}”. Observing the changed page…`);
        await new Promise((resolve) => setTimeout(resolve, 750));
      }
    } else if (entry.clicked) {
      state.applicationStarted = true;
      await persistJobContext();
      reportActivity("Opening the employer application form…");
      await waitForTabReady(entry.tab_id);
    } else if (entry.already_form) {
      state.applicationStarted = true;
      await persistJobContext();
    }
  }

  const login = await continueConsentedLogin();
  if (login.login_page) {
    throw new Error(login.error || "Login requires your attention.");
  }
  if (login.clicked) {
    reportActivity("Browser-assisted login completed; resuming the application…");
  }

  reportActivity("Scanning and filling known fields from your profile…");
  state.questionnaireActive = true;
  state.questionnaireTotal = 0;
  state.skippedFieldIds = new Set();
  let plan;
  try {
    plan = await scanApplicationFormWithRetry();
    state.applicationStarted = true;
    await persistJobContext();
  } catch (error) {
    if (!/no fillable fields/i.test(error.message)) throw error;
    state.formScan = { page_url: "", fields: [], adapter: "generic" };
    state.formPlan = { actions: [], unknown_fields: [], blocked_fields: [] };
    await completeAutomationApplication();
    return;
  }
  if (plan.actions.length) {
    await fillForm({ throwOnError: true });
    plan = await scanForm({ throwOnError: true });
  }
  try {
    await resolveNarrativeUnknowns();
  } catch (error) {
    elements.formStatus.textContent = `${error.message} You can answer the open questions manually.`;
  }
  plan = state.formPlan;
  const unknown = unresolvedUnknowns();
  const blocked = plan.blocked_fields.filter((field) => field.required);
  if (unknown.length) {
    elements.automationStatus.textContent =
      `Answer ${unknown.length} application question${unknown.length === 1 ? "" : "s"}; ApplyPilot will then continue automatically.`;
    return;
  }
  if (blocked.length) {
    throw new Error(`User action required: ${blocked[0].label}`);
  }
  if (plan.actions.length) await fillForm({ throwOnError: true });

  await completeAutomationApplication();
}

async function continueConsentedLogin() {
  let clicked = false;
  let last = { clicked: false, login_page: false };
  for (let attempt = 0; attempt < 24; attempt += 1) {
    last = await chrome.runtime.sendMessage({
      action: "assistLogin",
      allowClick: state.loginAssistance,
    });
    if (last.error && /captcha|mfa|verification/i.test(last.error)) return last;
    if (!last.login_page) return { ...last, clicked };
    if (!state.loginAssistance) return last;
    if (last.clicked) {
      clicked = true;
      reportActivity("Submitted a password-manager-filled login step; observing the next page…");
      await new Promise((resolve) => setTimeout(resolve, 750));
      continue;
    }
    if (last.error && !/password manager|fill the login fields/i.test(last.error)) return last;
    reportActivity("Waiting for the browser password manager to fill the login fields…");
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return {
    ...last,
    clicked,
    login_page: true,
    error: "Login fields were not filled after waiting for the browser password manager.",
  };
}

async function scanApplicationFormWithRetry() {
  let lastError = new Error("No fillable fields were found on this page.");
  for (let attempt = 0; attempt < 16; attempt += 1) {
    try {
      return await scanForm({ throwOnError: true });
    } catch (error) {
      lastError = error;
      if (!/no fillable fields/i.test(error.message) || attempt === 15) throw error;
      reportActivity("Waiting for the employer application form...");
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  throw lastError;
}

async function completeAutomationApplication() {
  const requiredUnknown = unresolvedRequiredUnknowns();
  const blocked = (state.formPlan?.blocked_fields || []).filter((field) => field.required);
  if (requiredUnknown.length || blocked.length) {
    setAutomationRunning(
      false,
      `Paused: ${requiredUnknown[0]?.label || blocked[0]?.label} requires your attention.`,
    );
    return;
  }
  if (state.formScan?.fields?.some((field) => field.field_type === "file")) {
    reportActivity("Selecting the résumé configured for this application…");
    const attached = await maybeAttachResume();
    if (!attached && state.automationPolicy === "always_allow") {
      throw new Error("Tailored résumé attachment was not approved.");
    }
  }

  const step = await chrome.runtime.sendMessage({
    action: "advanceApplication",
    frameId: state.formScan?.frame_id ?? 0,
  });
  if (step.error && step.intermediate) throw new Error(step.error);
  if (step.clicked) {
    if (step.fingerprint && step.fingerprint === state.lastStepFingerprint) {
      throw new Error("The page did not change after the previous action, so ApplyPilot stopped the repeated step.");
    }
    state.lastStepFingerprint = step.fingerprint || "";
    state.applicationSteps += 1;
    if (state.applicationSteps > 15) {
      throw new Error("Application paused after 15 form steps to prevent an unintended loop.");
    }
    reportActivity(`Opening the next application step (${step.label})...`);
    state.formPlan = null;
    state.formScan = null;
    state.questionnaireTotal = 0;
    state.skippedFieldIds = new Set();
    await new Promise((resolve) => setTimeout(resolve, 750));
    await runCurrentApplicationPage();
    return;
  }
  if (!step.final_ready) {
    const planned = await planAndClickPageAction(
      "Advance to the next safe step of this job application. Never submit the application.",
    );
    if (planned?.clicked) {
      state.applicationSteps += 1;
      state.lastStepFingerprint = planned.fingerprint || state.lastStepFingerprint;
      reportActivity(`AI page planner selected “${planned.label}”. Observing the next step…`);
      state.formPlan = null;
      state.formScan = null;
      await new Promise((resolve) => setTimeout(resolve, 750));
      await runCurrentApplicationPage();
      return;
    }
    throw new Error(planned?.error || step.error || "No safe next action was found on this page.");
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

  reportActivity("Submitting automatically under Always allow…");
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
  reportActivity("Submission confirmed. Moving to the next queued LinkedIn job…");
  const opened = await chrome.runtime.sendMessage({
    action: "openQueuedJob",
    tabId: state.sourceTabId,
    url: nextUrl,
  });
  if (opened.error) throw new Error(opened.error);
  await runAutomationCycle();
}

async function planAndClickPageAction(goal) {
  if (!state.provider?.configured) return null;
  try {
    const snapshot = await chrome.runtime.sendMessage({ action: "inspectPageActions" });
    if (snapshot.error || !snapshot.controls?.length) return null;
    const decision = await api("/api/page-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal, ...snapshot }),
    });
    if (decision.intent !== "click" || !decision.action_id) {
      return { clicked: false, error: decision.explanation };
    }
    const fingerprint = `${snapshot.page_title}|${snapshot.controls.map((control) => control.label).join("|")}`;
    if (fingerprint === state.lastStepFingerprint) {
      return { clicked: false, error: "The observed page has not changed since the previous planned action." };
    }
    const selectedControl = snapshot.controls.find(
      (control) => control.id === decision.action_id,
    );
    if (!selectedControl) {
      return { clicked: false, error: "The model selected a control that was not in the page snapshot." };
    }
    const result = await chrome.runtime.sendMessage({
      action: "clickPageAction",
      actionId: decision.action_id,
      expectedLabel: selectedControl.label,
      expectedKind: selectedControl.kind,
      frameId: snapshot.frame_id ?? 0,
    });
    return { ...result, fingerprint, explanation: decision.explanation };
  } catch (error) {
    return { clicked: false, error: error.message };
  }
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
    if (await handlePageActionCommand(message)) return;
    if (!state.provider?.configured) {
      appendMessage(
        "AI chat is off because no provider key is saved. Common-field scanning and filling still work without AI.",
        "agent-message",
      );
      return;
    }
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

async function handlePageActionCommand(message) {
  if (/\b(are you applying|what are you doing|what is happening|application status|current status)\b/i.test(message)) {
    const status = elements.automationStatus.textContent.trim() || "No application run is active.";
    const job = state.job?.title ? ` for ${state.job.title}` : "";
    appendMessage(
      `${state.automationRunning ? "Yes, I am working" : "The runner is currently paused"}${job}. ${status}`,
      "agent-message",
    );
    return true;
  }
  const remembered = message.match(
    /^(?:remember|set|use)\s+(?:that\s+)?(.+?)(?:\s+is|\s+to|:)\s+(.+)$/i,
  );
  if (remembered) {
    const requested = remembered[1].replace(/^my\s+/i, "").trim();
    const answer = remembered[2].trim();
    if (/password|passcode|captcha|verification code|one[- ]time code|mfa|social security|ssn|bank|credit card/i.test(requested)) {
      appendMessage("I will not store credentials, verification codes, CAPTCHA answers, or financial identifiers.", "agent-message");
      return true;
    }
    const requestedKey = normalizeQuestion(requested);
    const scanned = state.formScan?.fields.find((field) => {
      const label = normalizeQuestion(field.label);
      return label.includes(requestedKey) || requestedKey.includes(label);
    });
    const question = scanned?.label || requested;
    const existing = state.answers.find(
      (item) => normalizeQuestion(item.question) === normalizeQuestion(question),
    );
    const answerId = existing?.id || crypto.randomUUID();
    const fieldType = scanned?.field_type === "number"
      ? "number"
      : ["select", "radio", "checkbox"].includes(scanned?.field_type) ? "choice" : "text";
    const sensitive = /race|ethnicity|gender|disability|veteran|hispanic|latino/i.test(question);
    await api(`/api/answers/${answerId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: answerId,
        question,
        answer,
        field_type: fieldType,
        sensitive,
      }),
    });
    state.answers = await api("/api/answers");
    if (state.formScan) {
      await replanForm();
      if (state.formPlan.actions.length) await fillForm({ throwOnError: true });
    }
    appendMessage(`Saved “${question}” as “${answer}” and applied it to the current page when matched.`, "agent-message");
    return true;
  }
  const explicitFillRequest = /(fill|complete|apply).*(everything|fields|form|page)/i.test(message)
    || /^(?:then\s+)?(?:please\s+)?(?:fill|complete|apply)\s+(?:it|that|this|those|that\s+part|this\s+part|the\s+field|the\s+fields)\b/i.test(message);
  if (!explicitFillRequest) return false;
  let plan = await scanForm({ throwOnError: true });
  await resolveNarrativeUnknowns();
  plan = state.formPlan;
  let result = { filled: 0, errors: [] };
  if (plan.actions.length) result = await fillForm({ throwOnError: true });
  const unknown = unresolvedRequiredUnknowns();
  const blocked = plan.blocked_fields.filter((field) => field.required);
  const details = [`Filled ${result.filled} known field${result.filled === 1 ? "" : "s"}.`];
  if (unknown.length) {
    details.push(`I still need your answer for: ${unknown.map((field) => field.label).join("; ")}.`);
  }
  if (blocked.length) {
    details.push(`You must complete: ${blocked.map((field) => field.label).join("; ")}.`);
  }
  const errors = humanizeFillErrors(result.errors || []);
  if (errors.length) details.push(`Could not fill: ${errors.join("; ")}.`);
  if (!unknown.length && !blocked.length && !errors.length) {
    details.push("The form is ready for your configured résumé and submission policy.");
  }
  appendMessage(details.join("\n"), "agent-message");
  return true;
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
  copy.className = "message-copy";
  if (className === "agent-message") renderFormattedMessage(copy, text);
  else copy.textContent = text;
  message.append(copy);
  elements.messages.append(message);
  message.scrollIntoView({ behavior: "smooth", block: "end" });
}

function renderFormattedMessage(container, text) {
  const lines = String(text || "").split(/\r?\n/);
  let list = null;
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      list = null;
      continue;
    }
    const bullet = line.match(/^[-*]\s+(.*)$/);
    if (bullet) {
      if (!list) {
        list = document.createElement("ul");
        container.append(list);
      }
      const item = document.createElement("li");
      appendInlineFormatting(item, bullet[1]);
      list.append(item);
      continue;
    }
    list = null;
    const paragraph = document.createElement("p");
    appendInlineFormatting(paragraph, line);
    container.append(paragraph);
  }
}

function appendInlineFormatting(container, text) {
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g);
  parts.filter(Boolean).forEach((part) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = part.slice(2, -2);
      container.append(strong);
    } else {
      container.append(document.createTextNode(part.replace(/^\*\s*/, "")));
    }
  });
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
elements.downloadHistory.addEventListener("click", downloadApplicationHistory);
elements.scanForm.addEventListener("click", startGuidedAnalysis);
elements.fillForm.addEventListener("click", fillForm);
elements.includeOptionalQuestions.addEventListener("change", async () => {
  if (!state.formPlan) return;
  state.questionnaireActive = true;
  state.questionnaireTotal = 0;
  state.skippedFieldIds = new Set();
  try {
    await replanForm();
    if (!unresolvedUnknowns().length) await continueQuestionnaire();
  } catch (error) {
    elements.formStatus.textContent = error.message;
  }
});
elements.unknownAnswerForm.addEventListener("submit", saveUnknownAnswer);
elements.draftUnknown.addEventListener("click", draftUnknownAnswer);
elements.skipUnknown.addEventListener("click", skipUnknownQuestion);
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
elements.loginAssistance.addEventListener("change", changeLoginAssistance);
elements.startAutomation.addEventListener("click", startAutomation);
elements.stopAutomation.addEventListener("click", stopAutomation);
elements.toggleKey.addEventListener("click", () => {
  const showing = elements.providerKey.type === "text";
  elements.providerKey.type = showing ? "password" : "text";
  elements.toggleKey.textContent = showing ? "Show" : "Hide";
});
elements.refresh.addEventListener("click", loadState);
elements.retryConnection.addEventListener("click", loadState);
elements.settings.addEventListener("click", () => {
  elements.advancedSettings.open = true;
  elements.advancedSettings.scrollIntoView({ behavior: "smooth", block: "start" });
  elements.providerSelect.focus();
});
loadState();
