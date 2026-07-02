const statusPill = document.querySelector("#service-status");
const routeForm = document.querySelector("#route-form");
const routeResult = document.querySelector("#route-result");

const routeNames = {
  company_site: "Company application",
  company_button: "Employer application button",
  easy_apply: "Easy Apply fallback",
  manual_review: "Manual verification required",
  unavailable: "No application route found",
};

async function checkService() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("Health check failed");
    const health = await response.json();
    statusPill.textContent = `${health.mode === "demo" ? "Demo" : "Local"} service online`;
    statusPill.classList.remove("offline");
  } catch {
    statusPill.textContent = "Service offline";
    statusPill.classList.add("offline");
  }
}

routeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = routeForm.querySelector("button");
  button.disabled = true;
  button.textContent = "Planning…";

  const payload = {
    source_url: document.querySelector("#source-url").value,
    company_application_url: document.querySelector("#company-url").value,
    company_url_verified: document.querySelector("#verified").checked,
    easy_apply_available: document.querySelector("#easy-apply").checked,
  };

  try {
    const response = await fetch("/api/application-route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("Route planning failed");
    const decision = await response.json();
    routeResult.classList.toggle(
      "review",
      decision.route === "manual_review" || decision.route === "unavailable",
    );
    routeResult.innerHTML = `
      <p class="result-label">PLANNED ROUTE</p>
      <strong>${routeNames[decision.route]}</strong>
      <p>${decision.reason}${decision.target_url ? `<br>${decision.target_url}` : ""}</p>
    `;
  } catch (error) {
    routeResult.classList.add("review");
    routeResult.innerHTML = `
      <p class="result-label">SERVICE ERROR</p>
      <strong>Could not plan the route</strong>
      <p>${error.message}</p>
    `;
  } finally {
    button.disabled = false;
    button.textContent = "Plan application route";
  }
});

checkService();
