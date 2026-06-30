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
  openApplication: document.querySelector("#open-application"),
  tailorResume: document.querySelector("#tailor-resume"),
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
  chatButton: document.querySelector("#chat-form button"),
  messages: document.querySelector("#messages"),
};

const state = {
  apiBase: DEFAULT_API_BASE,
  profile: null,
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
    state.artifact = null;
    elements.artifactActions.classList.add("hidden");
    state.submitClicked = false;
    elements.approveSubmit.classList.add("hidden");
    elements.approveSubmit.disabled = false;
    elements.approveSubmit.textContent = "Approve and submit application";
    elements.jobTitle.textContent = captured.title || "Captured job";
    elements.jobCompany.textContent = [captured.company, captured.location].filter(Boolean).join(" · ");
    elements.tailorResume.disabled = !(state.localMode && state.provider?.configured);
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
  } catch (error) {
    elements.jobCompany.textContent = error.message;
  } finally {
    elements.captureJob.disabled = false;
    elements.captureJob.textContent = "Capture this job";
  }
}

async function openApplication() {
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
  } catch (error) {
    elements.jobCompany.textContent = error.message;
    elements.openApplication.disabled = false;
  }
}

async function tailorResume() {
  if (!state.job) return;
  elements.tailorResume.disabled = true;
  elements.tailorResume.textContent = "Tailoring with evidence…";
  elements.tailorResult.classList.remove("hidden");
  elements.tailorResult.textContent = "Gemini is matching the job to verified résumé facts.";
  try {
    state.artifact = await api("/api/tailored", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job: state.job, application_id: state.application?.id || "" }),
    });
    const tailored = state.artifact.tailored;
    const warnings = tailored.warnings.length
      ? `<p><strong>Warnings:</strong> ${escapeHtml(tailored.warnings.join(" "))}</p>`
      : "";
    elements.tailorResult.innerHTML = `
      <strong>${escapeHtml(tailored.headline)}</strong>
      <p>${escapeHtml(tailored.summary)}</p>
      <p><strong>Skills:</strong> ${escapeHtml(tailored.skills.join(", "))}</p>
      ${warnings}
    `;
    elements.artifactActions.classList.remove("hidden");
    updateAttachButton();
    await transitionApplication("materials_ready", "Created an evidence-grounded tailored draft.");
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
    state.formScan = scan;
    await transitionApplication("filling", "Application form fields detected.", {
      adapter: scan.adapter,
      field_count: String(scan.fields.length),
    });
    await replanForm();
  } catch (error) {
    elements.formStatus.textContent = error.message;
    elements.formResult.textContent = "Nothing was changed on the page.";
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
  const requiredUnknown = state.formPlan.unknown_fields.filter((field) => field.required);
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

async function attachTailoredResume() {
  const fileField = state.formScan?.fields.find((field) => field.field_type === "file");
  if (!state.artifact || !fileField) return;
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
    return;
  }
  elements.formStatus.textContent = `${result.filename} attached for review.`;
  elements.attachResume.textContent = "Tailored résumé attached";
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
  await replanForm();
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
    const requiredUnknown = state.formPlan.unknown_fields.some((field) => field.required);
    const requiredBlocked = state.formPlan.blocked_fields.some((field) => field.required);
    if (!requiredUnknown && !requiredBlocked) {
      await transitionApplication(
        "review_required",
        "Known fields were filled; final user review is required.",
      );
      elements.approveSubmit.classList.remove("hidden");
    }
  } catch (error) {
    elements.formStatus.textContent = error.message;
  } finally {
    elements.fillForm.disabled = false;
    elements.fillForm.textContent = "Fill known fields";
  }
}

async function approveAndSubmit() {
  try {
    if (!state.submitClicked) {
      const confirmed = window.confirm(
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
      return;
    }
    await transitionApplication(
      "submitted",
      "The user approved submission and the employer site displayed confirmation.",
      { signal: verification.signal },
    );
    elements.approveSubmit.textContent = "Submission confirmed";
  } catch (error) {
    elements.formStatus.textContent = error.message;
    elements.approveSubmit.disabled = false;
    elements.approveSubmit.textContent = state.submitClicked
      ? "Verify site result"
      : "Approve and submit application";
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
elements.openApplication.addEventListener("click", openApplication);
elements.tailorResume.addEventListener("click", tailorResume);
elements.downloadDocx.addEventListener("click", () => openArtifact("docx"));
elements.downloadPdf.addEventListener("click", () => openArtifact("pdf"));
elements.attachResume.addEventListener("click", attachTailoredResume);
elements.scanForm.addEventListener("click", scanForm);
elements.fillForm.addEventListener("click", fillForm);
elements.unknownAnswerForm.addEventListener("submit", saveUnknownAnswer);
elements.approveSubmit.addEventListener("click", approveAndSubmit);
elements.chatForm.addEventListener("submit", sendChat);
elements.refresh.addEventListener("click", loadState);
elements.settings.addEventListener("click", () => chrome.runtime.openOptionsPage());
loadState();
