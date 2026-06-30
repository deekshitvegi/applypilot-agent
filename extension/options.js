const DEFAULT_API_BASE = "http://127.0.0.1:8765";
const form = document.querySelector("#settings-form");
const input = document.querySelector("#api-base");
const result = document.querySelector("#result");
const useLocal = document.querySelector("#use-local");
const diagnostics = document.querySelector("#diagnostics");
const diagnosticFields = {
  service: document.querySelector("#diag-service"),
  mode: document.querySelector("#diag-mode"),
  provider: document.querySelector("#diag-provider"),
  model: document.querySelector("#diag-model"),
  adapters: document.querySelector("#diag-adapters"),
};
const providerHelp = document.querySelector("#provider-help");

async function restore() {
  const stored = await chrome.storage.sync.get({ apiBase: DEFAULT_API_BASE });
  input.value = stored.apiBase;
}

async function saveAndTest(event) {
  event.preventDefault();
  result.textContent = "Requesting access and testing…";
  result.classList.remove("error");

  try {
    const apiBase = new URL(input.value).origin;
    const pattern = `${apiBase}/*`;
    const local = apiBase === DEFAULT_API_BASE;
    const granted = local || (await chrome.permissions.request({ origins: [pattern] }));
    if (!granted) throw new Error("Connection permission was not granted.");

    const response = await fetch(`${apiBase}/health`);
    if (!response.ok) throw new Error("The service did not pass its health check.");
    const health = await response.json();
    const [providerResponse, capabilitiesResponse] = await Promise.all([
      fetch(`${apiBase}/api/provider`),
      fetch(`${apiBase}/api/capabilities`),
    ]);
    if (!providerResponse.ok || !capabilitiesResponse.ok) {
      throw new Error("The service diagnostics endpoints are unavailable.");
    }
    const provider = await providerResponse.json();
    const capabilities = await capabilitiesResponse.json();

    await chrome.storage.sync.set({ apiBase });
    input.value = apiBase;
    renderDiagnostics(health, provider, capabilities);
    if (health.mode === "local" && !provider.configured) {
      result.textContent = "Local service connected, but Gemini is not configured.";
      result.classList.add("error");
    } else {
      result.textContent = `Connected to the ${health.mode} service.`;
    }
  } catch (error) {
    result.textContent = error.message;
    result.classList.add("error");
  }
}

function renderDiagnostics(health, provider, capabilities) {
  diagnostics.classList.remove("hidden");
  diagnosticFields.service.textContent = `ApplyPilot ${health.version || "unknown"}`;
  diagnosticFields.mode.textContent = health.mode;
  diagnosticFields.provider.textContent = provider.configured
    ? `${provider.provider} (configured)`
    : `${provider.provider} (missing key)`;
  diagnosticFields.model.textContent = provider.model;
  diagnosticFields.adapters.textContent = (capabilities.supported_adapters || []).join(", ");
  providerHelp.textContent = health.mode === "demo"
    ? "The hosted demo intentionally disables personal data and AI calls. Use the local service to apply."
    : provider.configured
      ? "The AI provider is ready. The key remains inside the local backend."
      : "Add a newly generated GEMINI_API_KEY to the local .env file, then restart ApplyPilot.";
}

form.addEventListener("submit", saveAndTest);
useLocal.addEventListener("click", () => {
  input.value = DEFAULT_API_BASE;
  form.requestSubmit();
});
restore();
