const DEFAULT_API_BASE = "http://127.0.0.1:8765";

const elements = {
  connection: document.querySelector("#connection"),
  question: document.querySelector("#question"),
  progress: document.querySelector("#progress"),
  refresh: document.querySelector("#refresh"),
  settings: document.querySelector("#settings"),
  answerForm: document.querySelector("#answer-form"),
  answerInput: document.querySelector("#answer-input"),
  answerChoice: document.querySelector("#answer-choice"),
  resumeFile: document.querySelector("#resume-file"),
  resumeStatus: document.querySelector("#resume-status"),
  captureJob: document.querySelector("#capture-job"),
  tailorResume: document.querySelector("#tailor-resume"),
  tailorResult: document.querySelector("#tailor-result"),
  jobTitle: document.querySelector("#job-title"),
  jobCompany: document.querySelector("#job-company"),
  scanForm: document.querySelector("#scan-form"),
  fillForm: document.querySelector("#fill-form"),
  formStatus: document.querySelector("#form-status"),
  formResult: document.querySelector("#form-result"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  chatButton: document.querySelector("#chat-form button"),
  messages: document.querySelector("#messages"),
};

const state = {
  apiBase: DEFAULT_API_BASE,
  profile: null,
  onboarding: null,
  provider: null,
  job: null,
  formPlan: null,
  localMode: false,
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

async function loadState() {
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
    const chatReady = state.localMode && state.provider.configured;
    elements.chatInput.disabled = !chatReady;
    elements.chatButton.disabled = !chatReady;

    if (!state.localMode) {
      showDemoMode();
      return;
    }

    [state.profile, state.onboarding] = await Promise.all([
      api("/api/profile"),
      api("/api/onboarding"),
    ]);
    renderOnboarding();
    await refreshResumeStatus();
  } catch (error) {
    elements.connection.textContent = "Agent is offline";
    elements.question.textContent = "Start the ApplyPilot service, then refresh.";
    elements.progress.textContent = error.message;
    elements.answerForm.classList.add("hidden");
  }
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
    elements.progress.textContent = "You can edit answers through chat or profile settings.";
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

async function captureJob() {
  elements.captureJob.disabled = true;
  elements.captureJob.textContent = "Reading page…";
  try {
    const captured = await chrome.runtime.sendMessage({ action: "captureJob" });
    if (captured.error) throw new Error(captured.error);
    if (!captured.description || captured.description.length < 80) {
      throw new Error("Could not find a complete job description on this page.");
    }
    state.job = captured;
    elements.jobTitle.textContent = captured.title || "Captured job";
    elements.jobCompany.textContent = [captured.company, captured.location].filter(Boolean).join(" · ");
    elements.tailorResume.disabled = !(state.localMode && state.provider?.configured);
  } catch (error) {
    elements.jobCompany.textContent = error.message;
  } finally {
    elements.captureJob.disabled = false;
    elements.captureJob.textContent = "Capture this job";
  }
}

async function tailorResume() {
  if (!state.job) return;
  elements.tailorResume.disabled = true;
  elements.tailorResume.textContent = "Tailoring with evidence…";
  elements.tailorResult.classList.remove("hidden");
  elements.tailorResult.textContent = "Gemini is matching the job to verified résumé facts.";
  try {
    const tailored = await api("/api/tailor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job: state.job }),
    });
    const warnings = tailored.warnings.length
      ? `<p><strong>Warnings:</strong> ${escapeHtml(tailored.warnings.join(" "))}</p>`
      : "";
    elements.tailorResult.innerHTML = `
      <strong>${escapeHtml(tailored.headline)}</strong>
      <p>${escapeHtml(tailored.summary)}</p>
      <p><strong>Skills:</strong> ${escapeHtml(tailored.skills.join(", "))}</p>
      ${warnings}
    `;
  } catch (error) {
    elements.tailorResult.textContent = error.message;
  } finally {
    elements.tailorResume.disabled = false;
    elements.tailorResume.textContent = "Tailor résumé";
  }
}

async function scanForm() {
  elements.scanForm.disabled = true;
  elements.scanForm.textContent = "Analyzing fields…";
  elements.formResult.classList.remove("hidden");
  try {
    const scan = await chrome.runtime.sendMessage({ action: "scanForm" });
    if (scan.error) throw new Error(scan.error);
    if (!scan.fields.length) throw new Error("No fillable fields were found on this page.");
    state.formPlan = await api("/api/forms/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(scan),
    });
    const requiredUnknown = state.formPlan.unknown_fields.filter((field) => field.required);
    elements.formStatus.textContent = `${scan.fields.length} fields found · ${state.formPlan.actions.length} known`;
    elements.formResult.innerHTML = `
      <strong>${state.formPlan.actions.length} fields ready</strong>
      <p>${requiredUnknown.length} required questions need your answer.</p>
      <p>${state.formPlan.blocked_fields.length} sensitive/authentication fields will be left alone.</p>
      <p>The final Submit button will not be clicked.</p>
    `;
    elements.fillForm.disabled = state.formPlan.actions.length === 0;
  } catch (error) {
    elements.formStatus.textContent = error.message;
    elements.formResult.textContent = "Nothing was changed on the page.";
  } finally {
    elements.scanForm.disabled = false;
    elements.scanForm.textContent = "Analyze visible fields";
  }
}

async function fillForm() {
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
  } catch (error) {
    elements.formStatus.textContent = error.message;
  } finally {
    elements.fillForm.disabled = false;
    elements.fillForm.textContent = "Fill known fields";
  }
}

async function sendChat(event) {
  event.preventDefault();
  const message = elements.chatInput.value.trim();
  if (!message) return;
  appendMessage(message, "user-message");
  elements.chatInput.value = "";
  elements.chatButton.disabled = true;

  try {
    const response = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, job: state.job }),
    });
    appendMessage(response.answer, "agent-message");
  } catch (error) {
    appendMessage(error.message, "agent-message");
  } finally {
    elements.chatButton.disabled = false;
  }
}

function appendMessage(text, className) {
  const paragraph = document.createElement("p");
  paragraph.className = className;
  paragraph.textContent = text;
  elements.messages.append(paragraph);
  paragraph.scrollIntoView({ behavior: "smooth", block: "end" });
}

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = value;
  return element.innerHTML;
}

elements.answerForm.addEventListener("submit", saveOnboardingAnswer);
elements.resumeFile.addEventListener("change", uploadResume);
elements.captureJob.addEventListener("click", captureJob);
elements.tailorResume.addEventListener("click", tailorResume);
elements.scanForm.addEventListener("click", scanForm);
elements.fillForm.addEventListener("click", fillForm);
elements.chatForm.addEventListener("submit", sendChat);
elements.refresh.addEventListener("click", loadState);
elements.settings.addEventListener("click", () => chrome.runtime.openOptionsPage());
loadState();
