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
  settingsBackdrop: document.querySelector("#settings-backdrop"),
  settingsDrawer: document.querySelector("#settings-drawer"),
  closeSettings: document.querySelector("#close-settings"),
  preferencesTab: document.querySelector("#preferences-tab"),
  profileTab: document.querySelector("#profile-tab"),
  preferencesPane: document.querySelector("#preferences-pane"),
  profilePane: document.querySelector("#profile-pane"),
  manualWorkflow: document.querySelector(".manual-workflow"),
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
  reasoningProviderSettings: document.querySelector("#reasoning-provider-settings"),
  reasoningProviderKey: document.querySelector("#reasoning-provider-key"),
  reasoningProviderModel: document.querySelector("#reasoning-provider-model"),
  reasoningProviderHelp: document.querySelector("#reasoning-provider-help"),
  saveReasoningProvider: document.querySelector("#save-reasoning-provider"),
  disconnectReasoningProvider: document.querySelector("#disconnect-reasoning-provider"),
  siteAccessBadge: document.querySelector("#site-access-badge"),
  enableSiteAccess: document.querySelector("#enable-site-access"),
  automationPolicy: document.querySelector("#automation-policy"),
  resumePolicy: document.querySelector("#resume-policy"),
  coverLetterPolicy: document.querySelector("#cover-letter-policy"),
  previewGeneratedCoverLetter: document.querySelector("#preview-generated-cover-letter"),
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
  coverLetterFile: document.querySelector("#cover-letter-file"),
  coverLetterStatus: document.querySelector("#cover-letter-status"),
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
  chatQuestionSlot: document.querySelector("#chat-question-slot"),
};

const state = {
  apiBase: DEFAULT_API_BASE,
  profile: null,
  answers: [],
  onboarding: null,
  provider: null,
  reasoningProvider: null,
  job: null,
  route: null,
  application: null,
  artifact: null,
  resume: null,
  resumeFileAvailable: false,
  coverLetter: null,
  generatedCoverLetter: null,
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
  coverLetterPolicy: "never",
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
  lastSavedAnswer: null,
  lastPageAnswer: null,
  pendingAgentQuestion: "",
  lastReferencedFieldLabel: "",
};

const SITE_ORIGINS = ["https://*/*", "http://*/*"];

function setupSimpleLayout() {
  elements.advancedSettings.open = true;
  elements.manualWorkflow.open = true;
  elements.preferencesPane.append(elements.advancedSettings);
  elements.profilePane.append(elements.manualWorkflow);
  elements.chatQuestionSlot.append(elements.unknownAnswerForm);

  const workflow = elements.manualWorkflow.querySelector(".workflow");
  const steps = [...workflow.querySelectorAll(":scope > .workflow-step")];
  if (steps.length > 2) {
    const troubleshooting = document.createElement("details");
    troubleshooting.className = "troubleshooting-tools";
    const summary = document.createElement("summary");
    summary.textContent = "Troubleshooting tools";
    const help = document.createElement("p");
    help.className = "field-help";
    help.textContent = "Manual job capture and form controls for diagnosing an unsupported page.";
    troubleshooting.append(summary, help, ...steps.slice(2));
    workflow.append(troubleshooting);
  }
}

function showSettingsPane(name) {
  const preferences = name === "preferences";
  elements.preferencesPane.classList.toggle("hidden", !preferences);
  elements.profilePane.classList.toggle("hidden", preferences);
  elements.preferencesTab.classList.toggle("active", preferences);
  elements.profileTab.classList.toggle("active", !preferences);
  elements.preferencesTab.setAttribute("aria-selected", String(preferences));
  elements.profileTab.setAttribute("aria-selected", String(!preferences));
}

function openSettings() {
  elements.settingsDrawer.classList.remove("hidden");
  elements.settingsBackdrop.classList.remove("hidden");
  elements.settingsDrawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("drawer-open");
  showSettingsPane("preferences");
  elements.closeSettings.focus();
}

function closeSettings() {
  elements.settingsDrawer.classList.add("hidden");
  elements.settingsBackdrop.classList.add("hidden");
  elements.settingsDrawer.setAttribute("aria-hidden", "true");
  document.body.classList.remove("drawer-open");
  elements.settings.focus();
}

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

    [state.provider, state.reasoningProvider] = await Promise.all([
      api("/api/provider"),
      api("/api/provider/reasoning"),
    ]);
    renderProvider();
    renderReasoningProvider();
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
    await refreshCoverLetterStatus();
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
    coverLetterPolicy: "never",
    minimumFit: 60,
    continueNext: true,
    loginAssistance: false,
  });
  state.automationPolicy = saved.automationPolicy;
  state.resumePolicy = saved.resumePolicy === "always_attach" ? "always_tailored" : saved.resumePolicy;
  state.coverLetterPolicy = saved.coverLetterPolicy === "always_attach"
    ? "always_saved"
    : saved.coverLetterPolicy;
  state.minimumFit = saved.minimumFit;
  elements.automationPolicy.value = saved.automationPolicy;
  elements.resumePolicy.value = state.resumePolicy;
  elements.coverLetterPolicy.value = state.coverLetterPolicy;
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

async function changeCoverLetterPolicy() {
  state.coverLetterPolicy = elements.coverLetterPolicy.value;
  await chrome.storage.local.set({ coverLetterPolicy: state.coverLetterPolicy });
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
  const hybridReasoning = provider.provider === "ollama" && provider.reasoning_provider === "gemini";
  elements.providerTitle.textContent = provider.configured
    ? hybridReasoning ? "Ollama + Gemini assist" : providerDefinition.label
    : "Connect a model";
  elements.providerBadge.textContent = provider.configured ? "Connected" : "Not configured";
  elements.providerBadge.classList.toggle("connected", provider.configured);
  elements.disconnectProvider.disabled = !provider.configured || provider.source === "environment";
  elements.providerHelp.textContent = provider.configured
    ? provider.provider === "ollama"
      ? hybridReasoning
        ? `Routine chat runs locally with ${provider.model}. ${provider.reasoning_model} is used selectively for résumé tailoring and unfamiliar page decisions, with Ollama fallback.`
        : `AI features run locally with ${provider.model}. No API key or cloud quota is used.`
      : `AI features are active with ${provider.model}. ${provider.source === "environment" ? "Loaded from the local environment." : "The saved key is encrypted in your local ApplyPilot database."}`
    : providerDefinition.help;
}

function renderReasoningProvider() {
  const ollamaSelected = elements.providerSelect.value === "ollama";
  elements.reasoningProviderSettings.classList.toggle("hidden", !ollamaSelected);
  if (!ollamaSelected) return;
  const configured = Boolean(state.reasoningProvider?.configured);
  elements.reasoningProviderModel.value = state.reasoningProvider?.model || "gemini-2.5-flash";
  elements.reasoningProviderKey.value = "";
  elements.reasoningProviderKey.placeholder = configured
    ? "Saved Gemini key is active — paste only to replace it"
    : "Paste a Gemini API key";
  elements.reasoningProviderHelp.textContent = configured
    ? "Gemini assist is connected. If it is rate-limited or unavailable, ApplyPilot falls back to Ollama."
    : "Optional. Routine autofill and chat remain free and local.";
  elements.disconnectReasoningProvider.disabled = !configured
    || state.reasoningProvider?.source === "environment";
}

async function saveReasoningProvider() {
  const apiKey = elements.reasoningProviderKey.value.trim();
  const model = elements.reasoningProviderModel.value.trim();
  if (!apiKey || !model) {
    elements.reasoningProviderHelp.textContent = "Enter a Gemini key and model name.";
    return;
  }
  elements.reasoningProviderHelp.textContent = "Encrypting and connecting Gemini assist…";
  try {
    state.reasoningProvider = await api("/api/provider/reasoning", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: "gemini", api_key: apiKey, model }),
    });
    state.provider = await api("/api/provider");
    renderProvider();
    renderReasoningProvider();
    appendMessage("Gemini assist is connected. Ollama remains the local primary and fallback.", "agent-message");
  } catch (error) {
    elements.reasoningProviderHelp.textContent = error.message;
  } finally {
    elements.reasoningProviderKey.value = "";
  }
}

async function disconnectReasoningProvider() {
  state.reasoningProvider = await api("/api/provider/reasoning", { method: "DELETE" });
  state.provider = await api("/api/provider");
  renderProvider();
  renderReasoningProvider();
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
    renderReasoningProvider();
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
    renderReasoningProvider();
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
  renderReasoningProvider();
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
    const [resume, fileStatus] = await Promise.all([
      api("/api/resumes/active"),
      api("/api/resumes/active/file-status"),
    ]);
    state.resume = resume;
    state.resumeFileAvailable = fileStatus.available === true;
    elements.resumeStatus.textContent = state.resumeFileAvailable
      ? `${resume.filename} · ${resume.extracted_text.length.toLocaleString()} characters extracted`
      : `${resume.filename} · saved text will be reconstructed as ATS-readable DOCX`;
  } catch (error) {
    if (!error.message.includes("No resume")) throw error;
    state.resumeFileAvailable = false;
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
    state.resumeFileAvailable = true;
    elements.resumeStatus.textContent = `${resume.filename} uploaded and encrypted locally.`;
  } catch (error) {
    elements.resumeStatus.textContent = error.message;
  } finally {
    elements.resumeFile.value = "";
  }
}

async function refreshCoverLetterStatus() {
  try {
    const document = await api("/api/cover-letters/active");
    state.coverLetter = document;
    elements.coverLetterStatus.textContent = `${document.filename} saved locally`;
  } catch (error) {
    if (!error.message.includes("No cover letter")) throw error;
    state.coverLetter = null;
    elements.coverLetterStatus.textContent = "No cover letter saved";
  }
}

async function uploadCoverLetter() {
  const [file] = elements.coverLetterFile.files;
  if (!file) return;
  elements.coverLetterStatus.textContent = "Saving cover letter…";
  const body = new FormData();
  body.append("file", file);
  try {
    state.coverLetter = await api("/api/cover-letters", { method: "POST", body });
    elements.coverLetterStatus.textContent = `${state.coverLetter.filename} uploaded and encrypted locally.`;
  } catch (error) {
    elements.coverLetterStatus.textContent = error.message;
  } finally {
    elements.coverLetterFile.value = "";
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
    state.generatedCoverLetter = null;
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
    const modelWillReviewUnknown = state.automationRunning && state.provider?.configured;
    if (!modelWillReviewUnknown && elements.unknownAnswerForm.dataset.announcedFieldId !== firstUnknown.field_id) {
      appendMessage(
        `I need one answer before I can continue:\n**${firstUnknown.label}**\n\nReply with the answer, or ask me a question if you need help.`,
        "agent-message",
      );
      elements.unknownAnswerForm.dataset.announcedFieldId = firstUnknown.field_id;
    }
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
    delete elements.unknownAnswerForm.dataset.announcedFieldId;
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
  return ["text", "textarea"].includes(scanned?.field_type)
    && /why|interest|motivat|describe|tell us|explain|project you|experience with|additional information|cover letter/i.test(unknown.label);
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
  if (!state.provider?.configured) return 0;
  const narrative = (state.formPlan?.unknown_fields || [])
    .filter((unknown) => !state.skippedFieldIds.has(unknown.field_id))
    .filter(isNarrativeUnknown)
    .slice(0, 3);
  let filled = 0;
  for (const unknown of narrative) {
    try {
      const draft = await requestApplicationAnswer(unknown.label);
      if (!draft.answer || /^(?:n\/?a|unknown|not provided|insufficient information)$/i.test(draft.answer.trim())) continue;
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
      if (result.error) continue;
      if ((result.filled_ids || []).includes(unknown.field_id)) filled += 1;
    } catch {
      // The structured form planner and user-question fallback still run below.
    }
  }
  if (filled) {
    reportActivity(`AI drafted and verified ${filled} job-specific response${filled === 1 ? "" : "s"}.`);
    await scanForm({ throwOnError: true });
  }
  return filled;
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
  const fileField = findResumeFileField();
  elements.attachResume.disabled = !(state.artifact && fileField);
}

function fileFieldText(field) {
  return normalizeQuestion(`${field?.label || ""} ${field?.name || ""}`);
}

function findCoverLetterField() {
  return state.formScan?.fields.find((field) => (
    field.field_type === "file" && /cover letter/.test(fileFieldText(field))
  ));
}

function findResumeFileField() {
  const files = state.formScan?.fields.filter((field) => field.field_type === "file") || [];
  return files.find((field) => /resume|curriculum vitae|\bcv\b/.test(fileFieldText(field)))
    || files.find((field) => !/cover letter/.test(fileFieldText(field)))
    || null;
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
  const fileField = findResumeFileField();
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
  const fileField = findResumeFileField();
  if (!fileField || !state.resume) return false;
  const result = await chrome.runtime.sendMessage({
    action: "attachResume",
    fieldId: fileField.id,
    frameId: state.formScan?.frame_id ?? 0,
    url: state.resumeFileAvailable
      ? `${state.apiBase}/api/resumes/active/file`
      : `${state.apiBase}/api/resumes/active/reconstructed.docx`,
    filename: state.resumeFileAvailable
      ? state.resume.filename
      : `${state.resume.filename.replace(/\.[^.]+$/, "")}-reconstructed.docx`,
  });
  if (result.error || !result.attached) {
    elements.formStatus.textContent = result.error || "The original résumé could not be attached.";
    if (throwOnError) throw new Error(elements.formStatus.textContent);
    return false;
  }
  elements.formStatus.textContent = state.resumeFileAvailable
    ? `${result.filename} attached as the original résumé.`
    : `${result.filename} reconstructed from the saved résumé text and attached.`;
  return true;
}

async function maybeAttachResume() {
  const fileField = findResumeFileField();
  if (!fileField) return true;
  if (fileField.value) return true;
  if (!state.resumeFileAvailable) {
    reportActivity(
      "The older original file is unavailable; creating an ATS-readable DOCX from the saved résumé text instead…",
    );
  }
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

async function maybeAttachCoverLetter() {
  const fileField = findCoverLetterField();
  if (!fileField || fileField.value || state.coverLetterPolicy === "never") return true;
  let mode = state.coverLetterPolicy;
  if (mode === "ask_each") {
    if (state.coverLetter && window.confirm(
      `Attach your saved cover letter (${state.coverLetter.filename})? Choose Cancel to consider generating one instead.`,
    )) {
      mode = "always_saved";
    } else if (state.provider?.configured && window.confirm(
      "Generate and attach a truthful job-specific cover letter from your saved résumé?",
    )) {
      mode = "always_generate";
    } else {
      return true;
    }
  }
  if (mode === "always_saved" && !state.coverLetter) {
    throw new Error("No saved cover letter is available. Upload one or choose job-specific generation in Settings.");
  }
  if (mode === "always_generate" && !state.provider?.configured) {
    throw new Error("Connect Gemini or Ollama before generating a job-specific cover letter.");
  }
  if (mode === "always_generate" && !state.generatedCoverLetter) {
    reportActivity("Generating a truthful job-specific cover letter from your saved résumé…");
    state.generatedCoverLetter = await api("/api/cover-letters/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job: state.job }),
    });
    elements.previewGeneratedCoverLetter.classList.remove("hidden");
  }
  const generated = mode === "always_generate";
  const result = await chrome.runtime.sendMessage({
    action: "attachResume",
    fieldId: fileField.id,
    frameId: state.formScan?.frame_id ?? 0,
    url: generated
      ? `${state.apiBase}/api/cover-letters/generated/${state.generatedCoverLetter.id}.docx`
      : `${state.apiBase}/api/cover-letters/active/file`,
    filename: generated
      ? `${state.job?.company || "job"}-cover-letter.docx`
      : state.coverLetter.filename,
  });
  if (result.error || !result.attached) {
    throw new Error(result.error || "The saved cover letter could not be attached.");
  }
  reportActivity(`${result.filename} attached as the ${generated ? "generated job-specific" : "saved"} cover letter.`);
  if (generated) {
    reportActivity("You can read it from Settings → Preview generated cover letter.");
  }
  return true;
}

async function attachConfiguredApplicationFiles() {
  if (findResumeFileField()) {
    reportActivity("Selecting the résumé configured for this application…");
    await maybeAttachResume();
  }
  try {
    await maybeAttachCoverLetter();
  } catch (error) {
    reportActivity(`Cover letter was not attached: ${error.message} Continuing with the application form…`);
  }
}

async function saveUnknownAnswer(event) {
  event.preventDefault();
  const answer = elements.unknownChoice.classList.contains("hidden")
    ? elements.unknownAnswer.value.trim()
    : elements.unknownChoice.value.trim();
  await persistUnknownAnswer(answer);
}

async function persistUnknownAnswer(answer, options = {}) {
  const question = elements.unknownAnswerForm.dataset.question || elements.unknownQuestion.textContent.trim();
  if (!answer || !question) return;
  const appendUser = options.appendUser !== false;
  const scannedType = elements.unknownAnswerForm.dataset.fieldType || "text";
  const formattedAnswer = await formatApplicationAnswer(question, answer, scannedType);
  if (elements.unknownAnswerForm.dataset.unreadable === "true") {
    const result = await chrome.runtime.sendMessage({
      action: "fillForm",
      frameId: state.formScan?.frame_id ?? 0,
      actions: [
        {
          field_id: elements.unknownAnswerForm.dataset.fieldId,
          value: formattedAnswer,
          source: "user.current_page",
          confidence: 1,
        },
      ],
    });
    if (result.error) throw new Error(result.error);
    if (appendUser) appendMessage(answer, "user-message");
    appendMessage("Got it. I filled that answer on this page.", "agent-message");
    await scanForm();
    await continueQuestionnaire();
    return;
  }
  const existing = state.answers.find(
    (item) => normalizeQuestion(item.question) === normalizeQuestion(question),
  );
  const id = existing?.id || crypto.randomUUID();
  const fieldType = scannedType === "number"
    ? "number"
    : ["select", "radio", "checkbox"].includes(scannedType) ? "choice" : "text";
  await api(`/api/answers/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, question, answer: formattedAnswer, field_type: fieldType, sensitive: false }),
  });
  state.lastSavedAnswer = { id, question, answer: formattedAnswer, fieldType };
  if (appendUser) appendMessage(answer, "user-message");
  appendMessage(
    `Saved “${formattedAnswer}” for “${question}”. I’ll reuse it next time. To correct it, say “change my last answer to …”.`,
    "agent-message",
  );
  state.answers = await api("/api/answers");
  await replanForm();
  await continueQuestionnaire();
}

async function formatApplicationAnswer(question, answer, fieldType) {
  const normalizedQuestion = normalizeQuestion(question);
  const normalizedAnswer = normalizeQuestion(answer);
  if (state.provider?.configured && fieldType === "textarea") {
    try {
      const refined = await api("/api/questions/refine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, user_answer: answer, job: state.job }),
      });
      if (refined.answer?.trim()) return refined.answer.trim();
    } catch {
      // Use the narrow deterministic formatter below when the model is unavailable.
    }
  }
  if (
    /security tool experience/.test(normalizedQuestion)
    && /0|zero/.test(normalizedAnswer)
    && /all|them|mentioned|none/.test(normalizedAnswer)
  ) {
    return "SIEM: 0 months; SOAR: 0 months; UEBA: 0 months; EDR: 0 months; OS logs: 0 months.";
  }
  return answer;
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
  const frameRetry = options?.frameRetry === true;
  if (!state.formPlan) return;
  elements.fillForm.disabled = true;
  elements.fillForm.textContent = "Filling…";
  try {
    const result = await chrome.runtime.sendMessage({
      action: "fillForm",
      frameId: state.formScan?.frame_id ?? 0,
      actions: state.formPlan.actions.map((action) => {
        const field = state.formScan?.fields.find((candidate) => candidate.id === action.field_id);
        return {
          ...action,
          expected_label: field?.label || "",
          expected_type: field?.field_type || "",
        };
      }),
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
    if (!frameRetry && /no frame with id|frame was removed|cannot find frame/i.test(error.message)) {
      reportActivity("The application frame changed; rescanning the current form before continuing…");
      await new Promise((resolve) => setTimeout(resolve, 250));
      const refreshed = await scanForm({ throwOnError: true });
      if (refreshed?.actions?.length) {
        return fillForm({ throwOnError, frameRetry: true });
      }
      return { filled: 0, errors: [] };
    }
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
  await attachConfiguredApplicationFiles();
  if (findResumeFileField() || findCoverLetterField()) {
    plan = await scanForm({ throwOnError: true });
    if (plan.actions.length) {
      await fillForm({ throwOnError: true });
      plan = await scanForm({ throwOnError: true });
    }
  }
  plan = state.formPlan;
  let unknown = unresolvedUnknowns();
  if (unknown.length && state.provider?.configured) {
    try {
      await runModelAutomationPass();
      plan = state.formPlan;
      unknown = unresolvedUnknowns();
    } catch (error) {
      reportActivity(`The AI field planner could not finish this pass (${error.message}). Asking only for the remaining verified unknowns.`);
    }
  }
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
  await attachConfiguredApplicationFiles();

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
    if (message && !images.length && await handleModelFormCommand(message)) return;
    if (message && !images.length && await handleAnswerConversation(message)) return;
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

function pendingQuestionVisible() {
  return Boolean(
    state.questionnaireActive
    && !elements.unknownAnswerForm.classList.contains("hidden")
    && elements.unknownAnswerForm.dataset.fieldId,
  );
}

function looksLikeChatQuestion(message) {
  const normalized = message.trim().toLowerCase();
  return normalized.endsWith("?")
    || /^(what|why|how|where|when|who|which)\b/.test(normalized)
    || /^(can|could|would|do|does|did|is|are|should|will|may)\b/.test(normalized)
    || /^(explain|help me|tell me)\b/.test(normalized)
    || /\b(i do not understand|i don't understand|i (?:want|need) to (?:know|ask|understand)|not sure what|what do you mean|does that mean)\b/.test(normalized);
}

function correctionValue(message) {
  const match = message.trim().match(
    /^(?:please\s+)?(?:change|correct|update|replace)\s+(?:my\s+)?(?:last\s+)?answer(?:\s+(?:to|as)|\s*:\s*)\s*(.+)$/i,
  );
  return match?.[1]?.trim() || "";
}

async function correctLastSavedAnswer(answer) {
  const saved = state.lastSavedAnswer;
  if (!saved) {
    appendMessage(
      "I don’t have a just-saved answer to correct in this session. Open Settings → Profile & résumé → Saved answers to edit an older answer.",
      "agent-message",
    );
    return;
  }
  await api(`/api/answers/${saved.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id: saved.id,
      question: saved.question,
      answer,
      field_type: saved.fieldType,
      sensitive: false,
    }),
  });
  state.lastSavedAnswer = { ...saved, answer };
  state.answers = await api("/api/answers");
  appendMessage(
    `Corrected. “${saved.question}” is now saved as “${answer}”.`,
    "agent-message",
  );
  if (state.formScan) {
    await replanForm();
    if (state.formPlan?.actions.length) await fillForm({ throwOnError: true });
  }
}

async function handleAnswerConversation(message) {
  if (
    state.lastSavedAnswer
    && /\b(?:answer|rewrite|format)\b.*\b(?:properly|professionally|clearly)\b/i.test(message)
  ) {
    const improved = await formatApplicationAnswer(
      state.lastSavedAnswer.question,
      state.lastSavedAnswer.answer,
      "textarea",
    );
    await correctLastSavedAnswer(improved);
    return true;
  }
  const correction = correctionValue(message);
  if (correction) {
    await correctLastSavedAnswer(correction);
    return true;
  }
  if (!pendingQuestionVisible()) return false;
  const explicit = message.trim().match(/^(?:\/answer|answer\s*:|my answer is)\s*(.+)$/i);
  if (explicit?.[1]) {
    await persistUnknownAnswer(explicit[1].trim(), { appendUser: false });
    return true;
  }
  if (looksLikeChatQuestion(message)) return false;
  await persistUnknownAnswer(message, { appendUser: false });
  return true;
}

function escapeRegularExpression(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeChoicePhrase(value) {
  return normalizeQuestion(value).replace(/\bexpereinced\b/g, "experienced");
}

async function savePageAnswer(question, answer, fieldType = "choice") {
  const existing = state.answers.find(
    (item) => normalizeQuestion(item.question) === normalizeQuestion(question),
  );
  const id = existing?.id || crypto.randomUUID();
  await api(`/api/answers/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, question, answer, field_type: fieldType, sensitive: false }),
  });
  state.lastPageAnswer = { question, answer, fieldType };
}

async function saveCanonicalProfileAnswer(field, value) {
  if (!state.profile) return false;
  const label = normalizeQuestion(field.group_label || field.label);
  const booleanValue = ["true", "yes", "1", "on"].includes(normalizeQuestion(value));
  let key = "";
  let savedValue = value;
  if (/\b(?:full|legal) name\b/.test(label)) key = "legal_name";
  else if (/\bemail\b/.test(label)) key = "email";
  else if (/\b(?:phone|mobile)\b/.test(label) && !/country code/.test(label)) key = "phone";
  else if (/\blinkedin\b/.test(label)) key = "linkedin_url";
  else if (/\bgithub\b/.test(label)) key = "github_url";
  else if (/\b(?:portfolio|personal website)\b/.test(label)) key = "portfolio_url";
  else if (/\bcurrent (?:job )?(?:title|position)\b/.test(label)) key = "current_title";
  else if (/\byears of experience\b/.test(label)) key = "years_of_experience";
  else if (/authorized to work|work authorization/.test(label)) key = "work_authorization";
  else if (/sponsor|sponsorship/.test(label)) {
    key = "requires_sponsorship";
    savedValue = booleanValue;
  } else if (/background check/.test(label)) {
    key = "background_check_consent";
    savedValue = booleanValue;
  } else if (/relocat/.test(label) && !field.option_label) {
    key = "willing_to_relocate";
    savedValue = booleanValue;
  } else if (/\btravel\b/.test(label)) {
    key = "willing_to_travel";
    savedValue = booleanValue;
  }
  if (!key) return false;
  state.profile = { ...state.profile, [key]: savedValue };
  state.profile = await api("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.profile),
  });
  return true;
}

function shouldUseFormAgent(message) {
  if (!state.localMode || !state.provider?.configured) return false;
  if (state.pendingAgentQuestion) return true;
  return /\b(fill|complete|apply|add|select|check|choose|include|set|change|update|answer|do it|put|reviewed|relocate|authorized|authorization|sponsor|sponsorship|this field|this part|in the form|in the application|it is|it was)\b/i.test(message);
}

async function persistVerifiedAgentActions(actions, filledIds, fields) {
  const verified = actions.filter((action) => filledIds.has(action.field_id));
  const checkboxGroups = new Map();
  for (const field of fields.filter((candidate) => candidate.field_type === "checkbox")) {
    const question = field.group_label || field.label.replace(field.option_label || "", "").trim();
    if (!checkboxGroups.has(question)) checkboxGroups.set(question, new Set());
    if (field.value) checkboxGroups.get(question).add(field.option_label || field.label);
  }
  const savedCheckboxGroups = new Set();
  for (const action of verified) {
    if (action.remember === false) continue;
    const field = fields.find((candidate) => candidate.id === action.field_id);
    if (!field) continue;
    if (await saveCanonicalProfileAnswer(field, action.value)) continue;
    const question = field.group_label || field.label;
    if (field.field_type === "checkbox") {
      const choices = checkboxGroups.get(question) || new Set();
      const option = field.option_label || field.label;
      if (String(action.value).toLowerCase() === "true") choices.add(option);
      else choices.delete(option);
      checkboxGroups.set(question, choices);
      if (savedCheckboxGroups.has(question)) continue;
      savedCheckboxGroups.add(question);
      const groupActions = verified.filter((candidate) => {
        const groupedField = fields.find((fieldCandidate) => fieldCandidate.id === candidate.field_id);
        return groupedField?.field_type === "checkbox"
          && (groupedField.group_label || groupedField.label) === question;
      });
      for (const groupedAction of groupActions) {
        const groupedField = fields.find((candidate) => candidate.id === groupedAction.field_id);
        const groupedOption = groupedField?.option_label || groupedField?.label;
        if (!groupedOption) continue;
        if (String(groupedAction.value).toLowerCase() === "true") choices.add(groupedOption);
        else choices.delete(groupedOption);
      }
      await savePageAnswer(question, [...choices].join(", "));
    } else {
      const fieldType = field.field_type === "number" ? "number" : "choice";
      await savePageAnswer(question, action.value, fieldType);
    }
  }
  if (verified.some((action) => action.remember !== false)) {
    state.answers = await api("/api/answers");
  }
  return verified;
}

function unresolvedFieldsForAgent() {
  const unknown = unresolvedUnknowns();
  if (!unknown.length) return [];
  const unknownIds = new Set(unknown.map((field) => field.field_id));
  const unknownLabels = new Set(unknown.map((field) => normalizeQuestion(field.label)));
  return (state.formScan?.fields || []).filter((field) => (
    unknownIds.has(field.id)
    || unknownLabels.has(normalizeQuestion(field.group_label || field.label))
  ));
}

async function requestFormAgentDecision(message, previousErrors = [], origin = "chat", fields = null) {
  return api("/api/forms/agent-plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_message: message,
      origin,
      page_url: state.formScan?.page_url || "",
      source_url: state.job?.source_url || "",
      fields: fields || state.formScan?.fields || [],
      adapter: state.formScan?.adapter || "generic",
      job: state.job,
      pending_question: state.pendingAgentQuestion,
      previous_errors: previousErrors,
    }),
  });
}

async function executeFormAgentDecision(message, decision, repairAttempt = 0, origin = "chat") {
  if (decision.question && !decision.actions.length) {
    if (renderChoiceCardsForMessage(message, decision.question)) {
      state.pendingAgentQuestion = decision.question;
      return true;
    }
    state.pendingAgentQuestion = decision.question;
    appendMessage(decision.question, "agent-message");
    return true;
  }
  if (!decision.actions.length) {
    return false;
  }
  const fields = [...(state.formScan?.fields || [])];
  const result = await chrome.runtime.sendMessage({
    action: "fillForm",
    frameId: state.formScan?.frame_id ?? 0,
    actions: decision.actions.map((action) => ({
      field_id: action.field_id,
      value: action.value,
      source: `agent.${action.grounding}`,
      confidence: action.confidence,
      expected_label: fields.find((field) => field.id === action.field_id)?.label || "",
      expected_type: fields.find((field) => field.id === action.field_id)?.field_type || "",
    })),
  });
  if (result.error) throw new Error(result.error);
  const filledIds = new Set(result.filled_ids || []);
  const verified = await persistVerifiedAgentActions(decision.actions, filledIds, fields);
  const failed = decision.actions.filter((action) => !filledIds.has(action.field_id));
  if (failed.length && repairAttempt === 0) {
    await scanForm({ throwOnError: true });
    const repairErrors = failed.map((action) => {
      const field = fields.find((candidate) => candidate.id === action.field_id);
      const error = (result.errors || []).find((candidate) => candidate.field_id === action.field_id);
      return `${field?.label || action.field_id}: requested ${action.value}; ${error?.message || "not verified"}`;
    });
    const repairFields = (state.formScan?.fields || []).filter((field) => (
      failed.some((action) => action.field_id === field.id)
    ));
    const repair = await requestFormAgentDecision(message, repairErrors, origin, repairFields);
    if (repair.actions?.length) return executeFormAgentDecision(message, repair, 1, origin);
  }
  state.pendingAgentQuestion = "";
  await scanForm({ throwOnError: true });
  const verifiedLabels = verified.map((action) => {
    const field = fields.find((candidate) => candidate.id === action.field_id);
    return `${field?.group_label || field?.label || action.field_id} → ${action.value}`;
  });
  const failedLabels = failed.map((action) => (
    fields.find((candidate) => candidate.id === action.field_id)?.group_label
    || fields.find((candidate) => candidate.id === action.field_id)?.label
    || action.field_id
  ));
  if (origin === "automation") {
    reportActivity(
      `AI resolved and verified ${verifiedLabels.length} field${verifiedLabels.length === 1 ? "" : "s"}${failedLabels.length ? `; ${failedLabels.length} still need another pass` : ""}.`,
    );
  } else {
    appendMessage(
      `${decision.explanation || "I interpreted the current form and applied the requested answers."}\n\nVerified:\n${verifiedLabels.length ? verifiedLabels.map((label) => `- ${label}`).join("\n") : "- None"}${failedLabels.length ? `\n\nStill unresolved:\n${failedLabels.map((label) => `- ${label}`).join("\n")}` : ""}`,
      "agent-message",
    );
  }
  return true;
}

async function handleModelFormCommand(message) {
  if (!shouldUseFormAgent(message)) return false;
  try {
    await scanForm({ throwOnError: true });
    const normalizedMessage = normalizeQuestion(message);
    const referenced = (state.formScan?.fields || []).filter((field) => {
      const label = normalizeQuestion(field.group_label || field.label);
      return label.length >= 5 && normalizedMessage.includes(label);
    });
    if (referenced.length === 1) {
      state.lastReferencedFieldLabel = referenced[0].group_label || referenced[0].label;
    }
    const focusedValue = message.trim().match(
      /^(?:please\s+)?(?:change|correct|update|set)\s+(?:it|this|that|the answer)\s+(?:to|as)\s+(.+)$/i,
    )?.[1]?.trim() || message.trim().match(/^(?:it|the answer)\s+(?:is|was)\s+(.+)$/i)?.[1]?.trim();
    if (focusedValue && state.lastReferencedFieldLabel) {
      const field = state.formScan?.fields.find(
        (candidate) => normalizeQuestion(candidate.group_label || candidate.label)
          === normalizeQuestion(state.lastReferencedFieldLabel),
      );
      if (field) {
        return executeFormAgentDecision(message, {
          handled: true,
          actions: [{
            field_id: field.id,
            value: focusedValue,
            grounding: "user_message",
            confidence: 1,
            remember: true,
          }],
          question: "",
          explanation: `Updated ${field.group_label || field.label} from your explicit correction.`,
        });
      }
    }
    const broadFill = /\bfill(?:\s+out)?\b.*\b(?:everything|whole thing|all fields|form|page)\b/i.test(message);
    let deterministicFilled = 0;
    if (broadFill && state.formPlan?.actions?.length) {
      const deterministic = await fillForm({ throwOnError: true });
      deterministicFilled = deterministic?.filled || 0;
      await scanForm({ throwOnError: true });
    }
    const decision = await requestFormAgentDecision(message);
    const handled = await executeFormAgentDecision(message, decision);
    if (!handled && renderChoiceCardsForMessage(message)) return true;
    if (!handled && deterministicFilled) {
      appendMessage(
        `Filled and verified ${deterministicFilled} known fields from your saved profile. I found no additional model-grounded changes to make.`,
        "agent-message",
      );
      return true;
    }
    return handled;
  } catch (error) {
    appendMessage(`The AI form planner could not complete this step (${error.message}). I’m trying the deterministic fallback.`, "agent-message");
    return false;
  }
}

async function runModelAutomationPass() {
  if (!state.localMode || !state.provider?.configured || !state.formScan?.fields?.length) {
    return false;
  }
  const drafted = await resolveNarrativeUnknowns();
  if (!unresolvedFieldsForAgent().length) return drafted > 0;
  reportActivity("Resolving the remaining questions from your verified profile, résumé, and job context…");
  const instruction = [
    "Complete every supplied unresolved job-application field using only grounded facts from the",
    "saved profile, reusable answers, resume, captured source URL, and current visible options.",
    "Draft truthful concise responses for open-ended questions when the evidence is sufficient.",
    "Do not change a correct value. After resolving everything supported by evidence, ask exactly",
    "one focused question only if a required answer is genuinely unknown.",
  ].join(" ");
  let madeProgress = drafted > 0;
  for (let pass = 0; pass < 3; pass += 1) {
    const fields = unresolvedFieldsForAgent();
    if (!fields.length) return madeProgress;
    const before = unresolvedUnknowns().length;
    const decision = await requestFormAgentDecision(instruction, [], "automation", fields);
    if (decision.actions?.length) {
      await executeFormAgentDecision(instruction, decision, 0, "automation");
      const after = unresolvedUnknowns().length;
      madeProgress = madeProgress || after < before;
      if (after >= before) break;
      continue;
    }
    if (decision.question) {
      state.pendingAgentQuestion = decision.question;
      if (!renderChoiceCardsForMessage(decision.question, fields[0]?.group_label || fields[0]?.label || "")) {
        appendMessage(`${decision.question}\n\nReply with your answer, or ask me what the question means.`, "agent-message");
      }
      return true;
    }
    break;
  }
  const remaining = unresolvedFieldsForAgent();
  if (!remaining.length) return madeProgress;
  const first = remaining[0];
  const question = first.group_label || first.label;
  state.pendingAgentQuestion = question;
  if (!renderChoiceCardsForMessage(question, question)) {
    appendMessage(
      `I couldn't verify an answer for **${question}** from your profile or résumé. What should I enter?\n\nYou can also ask me what this question means.`,
      "agent-message",
    );
  }
  return true;
}

async function executeExplicitPageAnswers(message) {
  const normalizedMessage = normalizeQuestion(message);
  const knownOptions = (state.formScan?.fields || []).flatMap((field) => field.options || []);
  const normalizedChoiceMessage = normalizeChoicePhrase(message);
  const knownVisibleOption = knownOptions.some((option) => (
    normalizeChoicePhrase(option.label || option.value) === normalizedChoiceMessage
  ));
  const namedVisibleOption = knownOptions.some((option) => {
    const optionText = normalizeChoicePhrase(option.label || option.value);
    return optionText.length >= 2 && normalizedChoiceMessage.includes(optionText);
  });
  const answerOptionInstruction = /\banswer\b/i.test(message) && namedVisibleOption;
  const valueStatementInstruction = /\bit\s+is\b/i.test(message) && namedVisibleOption;
  const actionable = /\b(add|select|check|choose|include|set|change|update|reviewed|authorized|authorization|sponsor|sponsorship|relocate|relocation|for this one)\b/i.test(message)
    || answerOptionInstruction
    || valueStatementInstruction;
  const possibleOptionReply = normalizedMessage.split(" ").length <= 5
    && knownVisibleOption
    && !looksLikeChatQuestion(message);
  if ((!actionable && !possibleOptionReply) || !state.localMode) return false;
  await scanForm({ throwOnError: true });
  const fields = state.formScan?.fields || [];
  const updates = new Map();
  const selectedCheckboxes = new Map();
  if (/\b(?:add|apply|fill|put)\s+(?:that|it)\s+(?:in|to|on)\s+(?:the\s+)?(?:job\s+)?(?:application|form|page)\b/i.test(message) && state.lastPageAnswer) {
    await replanForm();
    const result = await fillForm({ throwOnError: true });
    appendMessage(
      `Reapplied “${state.lastPageAnswer.answer}” for “${state.lastPageAnswer.question}”. ${result?.filled || 0} mapped fields were refreshed.`,
      "agent-message",
    );
    return true;
  }
  for (const field of fields.filter((candidate) => candidate.field_type === "checkbox")) {
    const group = field.group_label || field.label.replace(field.option_label || "", "").trim();
    if (field.value) {
      const current = selectedCheckboxes.get(group) || new Set();
      current.add(field.option_label || field.label);
      selectedCheckboxes.set(group, current);
    }
    const option = field.option_label || field.label;
    const requested = new RegExp(
      `\\b(?:add|select|check|choose|include)\\b[^.;\\n]{0,45}\\b${escapeRegularExpression(option)}\\b`,
      "i",
    ).test(message);
    if (requested) {
      const current = selectedCheckboxes.get(group) || new Set();
      current.add(option);
      selectedCheckboxes.set(group, current);
      updates.set(field.id, { field, value: "true", question: group });
    }
  }

  const sourceField = fields.find((field) => /how did you (?:find|hear)|source of application/i.test(field.label));
  if (sourceField && /(?:(?:for this one|source)[^.!?\n]{0,60}(?:it'?s|is)\s+linkedin|change[^.!?\n]{0,60}(?:answer\s+)?to\s+linkedin|answer[^.!?\n]{0,30}linkedin)/i.test(message)) {
    updates.set(sourceField.id, { field: sourceField, value: "LinkedIn", question: sourceField.label });
  }
  const authorization = fields.find((field) => /authorized to work|work authorization/i.test(field.label));
  if (authorization && /(?:yes\s+for\s+(?:authorized|authorization)|authorized[^.!?\n]{0,50}\byes\b)/i.test(message)) {
    updates.set(authorization.id, { field: authorization, value: "Yes", question: authorization.label });
  }
  const sponsorship = fields.find((field) => /sponsor|sponsorship/i.test(field.label));
  if (sponsorship && /(?:no\s+for\s+(?:future\s+)?sponsor|sponsor(?:ship)?[^.!?\n]{0,50}\bno\b)/i.test(message)) {
    updates.set(sponsorship.id, { field: sponsorship, value: "No", question: sponsorship.label });
  }

  if (/\b(?:can|willing to)\s+relocate\s+(?:anywhere|anywhere in (?:the )?u\.?s\.?)\b/i.test(message)) {
    const relocationFields = fields.filter((field) => (
      field.field_type === "checkbox" && /relocat|assisted relocation package/i.test(field.group_label || field.label)
    ));
    for (const field of relocationFields) {
      const unable = /unable|cannot|only work remotely/i.test(field.option_label || field.label);
      updates.set(field.id, {
        field,
        value: unable ? "false" : "true",
        question: field.group_label || field.label,
      });
      if (!unable) {
        const group = field.group_label || field.label;
        const current = selectedCheckboxes.get(group) || new Set();
        current.add(field.option_label || field.label);
        selectedCheckboxes.set(group, current);
      }
    }
  }

  const reviewedPolicy = fields.find((field) => (
    /background check policy/i.test(`${field.group_label || ""} ${field.label || ""}`)
    && /reviewed/i.test(`${field.option_label || ""} ${(field.options || []).map((option) => option.label).join(" ")}`)
  ));
  if (reviewedPolicy && /(?:i\s+have\s+reviewed|reviewed)\s+(?:the\s+)?background check policy/i.test(message)) {
    const reviewedOption = (reviewedPolicy.options || []).find((option) => /reviewed/i.test(option.label || option.value));
    updates.set(reviewedPolicy.id, {
      field: reviewedPolicy,
      value: reviewedPolicy.field_type === "checkbox" ? "true" : reviewedOption?.label || "I have reviewed the Background Check Policy",
      question: reviewedPolicy.group_label || reviewedPolicy.label,
    });
  }

  const directOptionMatches = [];
  const shortReply = normalizedChoiceMessage.split(" ").length <= 5;
  for (const field of fields.filter((candidate) => ["radio", "select"].includes(candidate.field_type))) {
    for (const option of field.options || []) {
      const visibleOption = String(option.label || option.value || "").trim();
      if (!visibleOption) continue;
      const escaped = escapeRegularExpression(visibleOption);
      const explicitlyNamed = new RegExp(
        `(?:\\banswer\\s*(?:is|:|-)?\\s*["']?${escaped}\\b|\\b${escaped}\\b\\s+is\\s+the\\s+answer\\b|\\b(?:set|select|choose|use)\\s+(?:it\\s+to\\s+)?${escaped}\\b)`,
        "i",
      ).test(message);
      const exactShortReply = shortReply && normalizeQuestion(message) === normalizeQuestion(visibleOption);
      const normalizedVisibleOption = normalizeChoicePhrase(visibleOption);
      const correctedShortReply = shortReply && normalizedChoiceMessage === normalizedVisibleOption;
      const valueStatement = new RegExp(
        `\\b(?:it|answer)\\s+is\\s+${escapeRegularExpression(normalizedVisibleOption)}\\b`,
        "i",
      ).test(normalizedChoiceMessage);
      if (explicitlyNamed || exactShortReply || correctedShortReply || valueStatement) {
        directOptionMatches.push({ field, value: visibleOption });
      }
    }
  }
  const uniqueDirectFields = new Map();
  for (const match of directOptionMatches) {
    if (!uniqueDirectFields.has(match.field.id)) uniqueDirectFields.set(match.field.id, match);
    else uniqueDirectFields.set(match.field.id, null);
  }
  const unambiguousDirect = [...uniqueDirectFields.values()].filter(Boolean);
  if (unambiguousDirect.length === 1) {
    const { field, value } = unambiguousDirect[0];
    updates.set(field.id, {
      field,
      value,
      question: field.group_label || field.label,
    });
  }

  if (!updates.size) return false;
  const savedGroups = new Set();
  for (const update of updates.values()) {
    const { field, value, question } = update;
    if (field.field_type === "checkbox") {
      if (savedGroups.has(question)) continue;
      savedGroups.add(question);
      const choices = [...(selectedCheckboxes.get(question) || [])];
      await savePageAnswer(question, choices.join(", "));
    } else {
      await savePageAnswer(question, value);
    }
  }
  state.answers = await api("/api/answers");
  await replanForm();
  const result = await fillForm({ throwOnError: true });
  const filledIds = new Set(result?.filled_ids || []);
  const verified = [...updates.keys()].filter((fieldId) => filledIds.has(fieldId));
  const unverified = [...updates.values()].filter((update) => !filledIds.has(update.field.id));
  appendMessage(
    `Saved ${updates.size} explicit page answer${updates.size === 1 ? "" : "s"} and verified ${verified.length} on the page.${unverified.length ? ` Still not applied: ${unverified.map((update) => update.question).join("; ")}.` : ""}`,
    "agent-message",
  );
  return true;
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
  if (await executeExplicitPageAnswers(message)) return true;
  if (/\b(?:ask|show|give)\s+me\b.*\b(?:remaining\s+)?questions?\b/i.test(message)) {
    state.questionnaireActive = true;
    state.questionnaireTotal = 0;
    state.skippedFieldIds = new Set();
    await startGuidedAnalysis();
    appendMessage(
      unresolvedUnknowns().length
        ? "I’ll ask each unanswered application question here, one at a time."
        : "I rescanned the page and found no unanswered application questions.",
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
  const explicitFillRequest = /(fill(?:\s+out)?|complete|apply).*(everything|whole thing|all fields|fields|form|page)/i.test(message)
    || /^\s*(?:do|apply|fill)\s+(?:it|that)\s*[.!]*$/i.test(message)
    || /\banswer\s+(?:these|them)\b/i.test(message)
    || /^(?:then\s+)?(?:please\s+)?(?:fill(?:\s+out)?|complete)\s+(?:the\s+)?(?:rest|next|remaining fields?|whole thing)\b/i.test(message)
    || /^(?:then\s+)?(?:please\s+)?(?:fill(?:\s+out)?|complete|apply)\s+(?:it|that|this|those|that\s+part|this\s+part|the\s+field|the\s+fields)\b/i.test(message);
  if (!explicitFillRequest) return false;
  state.questionnaireActive = true;
  state.questionnaireTotal = 0;
  state.skippedFieldIds = new Set();
  let plan = await scanForm({ throwOnError: true });
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

function visibleChoiceGroups() {
  const groups = new Map();
  for (const field of state.formScan?.fields || []) {
    if (field.field_type === "checkbox") {
      const label = field.group_label || field.label;
      const key = `checkbox:${normalizeQuestion(label)}`;
      if (!groups.has(key)) groups.set(key, { key, label, multiple: true, choices: [] });
      groups.get(key).choices.push({
        label: field.option_label || field.label,
        selected: Boolean(field.value),
      });
    } else if (["radio", "select"].includes(field.field_type) && field.options?.length) {
      const label = field.group_label || field.label;
      const key = `${field.field_type}:${normalizeQuestion(label)}`;
      groups.set(key, {
        key,
        label,
        multiple: false,
        choices: field.options.map((option) => ({
          label: option.label || option.value,
          selected: normalizeChoicePhrase(field.value)
            === normalizeChoicePhrase(option.label || option.value),
        })),
      });
    }
  }
  return [...groups.values()].filter((group) => group.choices.length);
}

function relevantChoiceGroups(message, hint = "") {
  const text = normalizeQuestion(`${message} ${hint}`);
  const words = new Set(text.split(" ").filter((word) => word.length >= 4));
  return visibleChoiceGroups()
    .map((group) => {
      const label = normalizeQuestion(group.label);
      const labelWords = new Set(label.split(" ").filter((word) => word.length >= 4));
      let score = [...labelWords].filter((word) => words.has(word)).length;
      score += group.choices.filter((choice) => (
        text.includes(normalizeQuestion(choice.label))
      )).length * 3;
      if (
        state.lastReferencedFieldLabel
        && normalizeQuestion(state.lastReferencedFieldLabel) === label
      ) score += 5;
      return { group, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, 4)
    .map((item) => item.group);
}

async function applyChoiceGroup(group, selectedLabels, card) {
  await scanForm({ throwOnError: true });
  const normalizedGroup = normalizeQuestion(group.label);
  const current = (state.formScan?.fields || []).filter((field) => (
    normalizeQuestion(field.group_label || field.label) === normalizedGroup
  ));
  let actions = [];
  if (group.multiple) {
    const selected = new Set(selectedLabels.map(normalizeQuestion));
    actions = current.map((field) => ({
      field_id: field.id,
      value: selected.has(normalizeQuestion(field.option_label || field.label)) ? "true" : "false",
      grounding: "user_message",
      confidence: 1,
      remember: true,
    }));
  } else {
    const field = current[0];
    if (field && selectedLabels[0]) {
      actions = [{
        field_id: field.id,
        value: selectedLabels[0],
        grounding: "user_message",
        confidence: 1,
        remember: true,
      }];
    }
  }
  if (!actions.length) throw new Error("The question is no longer visible on the page.");
  card.classList.add("choice-card-complete");
  card.querySelectorAll("button, input").forEach((control) => { control.disabled = true; });
  await executeFormAgentDecision(
    `Selected ${selectedLabels.join(", ")} for ${group.label}`,
    {
      handled: true,
      actions,
      question: "",
      explanation: `Applied your selection for ${group.label}.`,
    },
  );
}

function renderChoiceCard(group) {
  const card = document.createElement("div");
  card.className = "message agent-message choice-card";
  const question = document.createElement("p");
  question.className = "choice-card-question";
  question.textContent = group.label;
  card.append(question);
  const options = document.createElement("div");
  options.className = "choice-card-options";
  if (group.multiple) {
    for (const choice of group.choices) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = choice.label;
      input.checked = choice.selected;
      label.append(input, document.createTextNode(choice.label));
      options.append(label);
    }
    const actions = document.createElement("div");
    actions.className = "choice-card-actions";
    const selectAll = document.createElement("button");
    selectAll.type = "button";
    selectAll.className = "secondary-button";
    selectAll.textContent = "Select all";
    selectAll.addEventListener("click", () => {
      options.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        input.checked = true;
      });
    });
    const apply = document.createElement("button");
    apply.type = "button";
    apply.textContent = "Apply selected";
    apply.addEventListener("click", async () => {
      const selected = [...options.querySelectorAll('input[type="checkbox"]:checked')]
        .map((input) => input.value);
      try {
        await applyChoiceGroup(group, selected, card);
      } catch (error) {
        appendMessage(error.message, "agent-message");
      }
    });
    actions.append(selectAll, apply);
    card.append(options, actions);
  } else {
    for (const choice of group.choices) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = choice.selected ? "choice-option selected" : "choice-option";
      button.textContent = choice.label;
      button.addEventListener("click", async () => {
        try {
          await applyChoiceGroup(group, [choice.label], card);
        } catch (error) {
          appendMessage(error.message, "agent-message");
        }
      });
      options.append(button);
    }
    card.append(options);
  }
  elements.messages.append(card);
  card.scrollIntoView({ behavior: "smooth", block: "end" });
}

function renderChoiceCardsForMessage(message, hint = "") {
  const groups = relevantChoiceGroups(message, hint);
  if (!groups.length) return false;
  groups.forEach(renderChoiceCard);
  return true;
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

setupSimpleLayout();

elements.answerForm.addEventListener("submit", saveOnboardingAnswer);
elements.editProfile.addEventListener("click", openProfileEditor);
elements.profileEditor.addEventListener("submit", saveProfile);
elements.cancelProfile.addEventListener("click", () => elements.profileEditor.classList.add("hidden"));
elements.resumeFile.addEventListener("change", uploadResume);
elements.coverLetterFile.addEventListener("change", uploadCoverLetter);
elements.captureJob.addEventListener("click", captureJob);
elements.openApplication.addEventListener("click", openApplication);
elements.tailorResume.addEventListener("click", tailorResume);
elements.analyzeFit.addEventListener("click", analyzeJobFit);
elements.downloadDocx.addEventListener("click", () => openArtifact("docx"));
elements.downloadPdf.addEventListener("click", () => openArtifact("pdf"));
elements.attachResume.addEventListener("click", attachTailoredResume);
elements.downloadHistory.addEventListener("click", downloadApplicationHistory);
elements.scanForm.addEventListener("click", () => {
  startGuidedAnalysis().catch((error) => {
    elements.formStatus.textContent = error.message;
    appendMessage(`I couldn't continue the form scan: ${error.message}`, "agent-message");
  });
});
elements.fillForm.addEventListener("click", () => {
  fillForm().catch((error) => {
    elements.formStatus.textContent = error.message;
    appendMessage(`I couldn't fill the current form: ${error.message}`, "agent-message");
  });
});
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
elements.chatInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  if (!elements.chatButton.disabled) elements.chatForm.requestSubmit();
});
elements.chatImages.addEventListener("change", addChatImages);
elements.providerForm.addEventListener("submit", saveProvider);
elements.disconnectProvider.addEventListener("click", disconnectProvider);
elements.providerSelect.addEventListener("change", changeProvider);
elements.saveReasoningProvider.addEventListener("click", saveReasoningProvider);
elements.disconnectReasoningProvider.addEventListener("click", disconnectReasoningProvider);
elements.enableSiteAccess.addEventListener("click", async () => {
  try {
    await requestSiteAccess();
  } catch (error) {
    elements.automationStatus.textContent = error.message;
  }
});
elements.automationPolicy.addEventListener("change", changeAutomationPolicy);
elements.resumePolicy.addEventListener("change", changeResumePolicy);
elements.coverLetterPolicy.addEventListener("change", changeCoverLetterPolicy);
elements.previewGeneratedCoverLetter.addEventListener("click", () => {
  if (!state.generatedCoverLetter?.body) return;
  closeSettings();
  appendMessage(
    `Generated cover letter preview:\n\n${state.generatedCoverLetter.body}`,
    "agent-message",
  );
});
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
elements.settings.addEventListener("click", openSettings);
elements.closeSettings.addEventListener("click", closeSettings);
elements.settingsBackdrop.addEventListener("click", closeSettings);
elements.preferencesTab.addEventListener("click", () => showSettingsPane("preferences"));
elements.profileTab.addEventListener("click", () => showSettingsPane("profile"));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !elements.settingsDrawer.classList.contains("hidden")) {
    closeSettings();
  }
});
loadState();
