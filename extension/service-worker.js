chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const actions = {
    captureJob: captureActiveJob,
    scanForm: scanActiveForm,
    fillForm: () => fillActiveForm(message.actions || []),
  };
  const action = actions[message.action];
  if (!action) return false;

  action()
    .then(sendResponse)
    .catch((error) => sendResponse({ error: error.message }));
  return true;
});

async function captureActiveJob() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url || !/^https?:/.test(tab.url)) {
    throw new Error("Open a job page in the active tab first.");
  }

  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: extractJobFromPage,
  });
  return result.result;
}

async function scanActiveForm() {
  const tab = await getActiveHttpTab();
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: extractFormFields,
  });
  return { page_url: tab.url, fields: result.result };
}

async function fillActiveForm(actions) {
  const tab = await getActiveHttpTab();
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: applyFormFillPlan,
    args: [actions],
  });
  return result.result;
}

async function getActiveHttpTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url || !/^https?:/.test(tab.url)) {
    throw new Error("Open an application form in the active tab first.");
  }
  return tab;
}

function extractFormFields() {
  const controls = [...document.querySelectorAll("input, textarea, select")].filter((control) => {
    const type = (control.type || "").toLowerCase();
    return !control.disabled && !["hidden", "submit", "button", "reset", "image"].includes(type);
  });

  return controls.map((control, index) => {
    const applypilotId = `ap-${index}`;
    control.dataset.applypilotId = applypilotId;
    const explicitLabel = control.id
      ? document.querySelector(`label[for="${CSS.escape(control.id)}"]`)?.textContent
      : "";
    const wrappingLabel = control.closest("label")?.textContent || "";
    const legend = control.closest("fieldset")?.querySelector("legend")?.textContent || "";
    const label = [legend, explicitLabel || wrappingLabel]
      .filter(Boolean)
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
    const fallbackLabel =
      control.getAttribute("aria-label") ||
      control.getAttribute("placeholder") ||
      control.name ||
      control.id ||
      `Field ${index + 1}`;
    const tag = control.tagName.toLowerCase();
    let fieldType = tag === "textarea" ? "textarea" : tag === "select" ? "select" : control.type || "text";
    if (!["text", "email", "tel", "url", "number", "textarea", "select", "checkbox", "radio", "file", "password"].includes(fieldType)) {
      fieldType = "other";
    }
    const options = tag === "select"
      ? [...control.options]
          .filter((option) => option.value || option.textContent.trim())
          .map((option) => ({ value: option.value, label: option.textContent.trim() }))
      : [];

    return {
      id: applypilotId,
      label: (label || fallbackLabel).replace(/\s+/g, " ").trim(),
      name: control.name || "",
      field_type: fieldType,
      required: control.required || control.getAttribute("aria-required") === "true",
      value: fieldType === "checkbox" || fieldType === "radio"
        ? (control.checked ? control.value || "true" : "")
        : control.value || "",
      options,
    };
  });
}

function applyFormFillPlan(actions) {
  let filled = 0;
  const errors = [];
  const dispatch = (control) => {
    control.dispatchEvent(new Event("input", { bubbles: true }));
    control.dispatchEvent(new Event("change", { bubbles: true }));
    control.dispatchEvent(new Event("blur", { bubbles: true }));
  };

  for (const action of actions) {
    const control = document.querySelector(`[data-applypilot-id="${CSS.escape(action.field_id)}"]`);
    if (!control || control.disabled) {
      errors.push(`${action.field_id}: field is no longer available`);
      continue;
    }

    try {
      const type = (control.type || control.tagName).toLowerCase();
      if (type === "file" || type === "password") continue;
      if (type === "checkbox") {
        control.checked = ["true", "yes", "1", "on"].includes(String(action.value).toLowerCase());
      } else if (type === "radio") {
        const target = String(action.value).toLowerCase();
        control.checked = [control.value, control.labels?.[0]?.textContent || ""]
          .some((value) => String(value).trim().toLowerCase() === target);
      } else if (control.tagName === "SELECT") {
        const target = String(action.value).toLowerCase();
        const option = [...control.options].find((candidate) =>
          [candidate.value, candidate.textContent].some(
            (value) => String(value).trim().toLowerCase() === target,
          ),
        );
        if (!option) throw new Error("matching option not found");
        control.value = option.value;
      } else {
        const prototype = Object.getPrototypeOf(control);
        const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
        if (descriptor?.set) descriptor.set.call(control, action.value);
        else control.value = action.value;
      }
      dispatch(control);
      filled += 1;
    } catch (error) {
      errors.push(`${action.field_id}: ${error.message}`);
    }
  }

  return { filled, errors, submit_clicked: false };
}

function extractJobFromPage() {
  const text = (selector) => document.querySelector(selector)?.textContent?.trim() || "";
  const meta = (name) =>
    document.querySelector(`meta[name="${name}"], meta[property="${name}"]`)?.content || "";
  const clean = (value) => value.replace(/\s+/g, " ").trim();

  let structured = {};
  for (const node of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const parsed = JSON.parse(node.textContent);
      const candidates = Array.isArray(parsed) ? parsed : parsed["@graph"] || [parsed];
      const posting = candidates.find((item) => item?.["@type"] === "JobPosting");
      if (posting) {
        structured = posting;
        break;
      }
    } catch {
      // Ignore malformed third-party structured data.
    }
  }

  const organization = structured.hiringOrganization || {};
  const address = structured.jobLocation?.address || structured.applicantLocationRequirements || {};
  const selectors = {
    title: ["h1", ".job-details-jobs-unified-top-card__job-title", "[data-automation-id='jobPostingHeader']"],
    company: [
      ".job-details-jobs-unified-top-card__company-name",
      "[data-automation-id='jobPostingCompany']",
      ".company-name",
    ],
    location: [
      ".job-details-jobs-unified-top-card__primary-description-container",
      "[data-automation-id='locations']",
      ".location",
    ],
    description: [
      ".jobs-description-content__text",
      "#job-details",
      "[data-automation-id='jobPostingDescription']",
      ".job-description",
      "main",
    ],
  };
  const firstText = (names) => {
    for (const selector of names) {
      const value = text(selector);
      if (value) return clean(value);
    }
    return "";
  };

  const htmlToText = (html) => {
    if (!html) return "";
    const container = document.createElement("div");
    container.innerHTML = html;
    return clean(container.textContent || "");
  };

  const locationParts = [address.addressLocality, address.addressRegion, address.addressCountry]
    .filter(Boolean)
    .map((item) => (typeof item === "string" ? item : item.name));

  return {
    source_url: location.href,
    title: clean(structured.title || firstText(selectors.title) || meta("og:title")),
    company: clean(organization.name || firstText(selectors.company)),
    location: clean(locationParts.join(", ") || firstText(selectors.location)),
    description: htmlToText(structured.description) || firstText(selectors.description),
    company_application_url: structured.url || "",
  };
}
