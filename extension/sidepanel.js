const DEFAULT_API_BASE = "http://127.0.0.1:8765";

const connection = document.querySelector("#connection");
const question = document.querySelector("#question");
const progress = document.querySelector("#progress");
const refresh = document.querySelector("#refresh");
const settings = document.querySelector("#settings");

async function getApiBase() {
  const stored = await chrome.storage.sync.get({ apiBase: DEFAULT_API_BASE });
  return stored.apiBase.replace(/\/$/, "");
}

async function loadState() {
  connection.textContent = "Connecting to local agent…";
  connection.classList.remove("connected");

  try {
    const API_BASE = await getApiBase();
    const healthResponse = await fetch(`${API_BASE}/health`);
    if (!healthResponse.ok) throw new Error("Health check failed");

    const onboardingResponse = await fetch(`${API_BASE}/api/onboarding`);
    if (!onboardingResponse.ok) throw new Error("Onboarding request failed");

    const state = await onboardingResponse.json();
    connection.textContent = "Local agent connected";
    connection.classList.add("connected");

    if (state.complete) {
      question.textContent = "Your reusable application profile is complete.";
      progress.textContent = "Ready for resume import and job analysis.";
    } else {
      question.textContent = state.next_question.prompt;
      progress.textContent = `${state.missing_count} required answers remaining`;
    }
  } catch (error) {
    connection.textContent = "Local agent is offline";
    question.textContent = "Start the ApplyPilot service, then refresh.";
    progress.textContent = error.message;
  }
}

refresh.addEventListener("click", loadState);
settings.addEventListener("click", () => chrome.runtime.openOptionsPage());
loadState();
