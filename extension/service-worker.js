chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const actions = {
    captureJob: captureActiveJob,
    scanForm: scanActiveForm,
    fillForm: () => fillActiveForm(message.actions || []),
    openApplication: () => openApplicationRoute(message.url),
    submitApplication: submitActiveApplication,
    verifySubmission: verifyActiveSubmission,
    attachResume: () => attachResumeFile(message.fieldId, message.url, message.filename),
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
  return { page_url: tab.url, fields: result.result, adapter: detectAdapterFromUrl(tab.url) };
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

async function submitActiveApplication() {
  const tab = await getActiveHttpTab();
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: clickFinalSubmit,
  });
  return result.result;
}

async function verifyActiveSubmission() {
  const tab = await getActiveHttpTab();
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: detectSubmissionConfirmation,
  });
  return result.result;
}

async function attachResumeFile(fieldId, url, filename) {
  const source = new URL(url);
  if (!["127.0.0.1", "localhost"].includes(source.hostname)) {
    throw new Error("Resume files can only be attached from the local ApplyPilot service.");
  }
  const response = await fetch(source.href);
  if (!response.ok) throw new Error("Could not download the tailored resume from the local agent.");
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  const tab = await getActiveHttpTab();
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: applyFileToInput,
    args: [fieldId, btoa(binary), filename],
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

async function openApplicationRoute(url) {
  const target = new URL(url);
  if (target.protocol !== "https:") {
    throw new Error("Only secure HTTPS application links can be opened.");
  }
  const tab = await chrome.tabs.create({ url: target.href, active: true });
  return { opened: true, tab_id: tab.id };
}

function detectAdapterFromUrl(url) {
  const host = new URL(url).hostname.toLowerCase();
  if (host === "linkedin.com" || host.endsWith(".linkedin.com")) return "linkedin";
  if (host === "greenhouse.io" || host.endsWith(".greenhouse.io")) return "greenhouse";
  if (host === "lever.co" || host.endsWith(".lever.co")) return "lever";
  if (host === "myworkdayjobs.com" || host.endsWith(".myworkdayjobs.com")) return "workday";
  return "generic";
}

function extractFormFields() {
  const host = location.hostname.toLowerCase();
  const root = host.includes("linkedin.com")
    ? document.querySelector(".jobs-easy-apply-modal, [role='dialog']") || document
    : host.includes("greenhouse.io")
      ? document.querySelector("#application_form, main") || document
      : host.includes("lever.co")
        ? document.querySelector(".application-form, main") || document
        : host.includes("myworkdayjobs.com")
          ? document.querySelector("[data-automation-id='applicationPage'], main") || document
          : document;
  const controls = [...root.querySelectorAll("input, textarea, select")].filter((control) => {
    const type = (control.type || "").toLowerCase();
    const style = getComputedStyle(control);
    const visible = type === "file" || (style.display !== "none" && style.visibility !== "hidden");
    return visible && !control.disabled && !["hidden", "submit", "button", "reset", "image"].includes(type);
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

function clickFinalSubmit() {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const challenge = [
    "iframe[src*='captcha']",
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "[class*='captcha']",
    "[id*='captcha']",
    "input[autocomplete='one-time-code']",
  ].some((selector) => [...document.querySelectorAll(selector)].some(visible));
  if (challenge) {
    return { clicked: false, error: "CAPTCHA or verification is present and requires the user." };
  }

  const labels = ["submit application", "submit", "send application", "finish application"];
  const candidates = [...document.querySelectorAll("button, input[type='submit']")].filter((button) => {
    if (button.disabled || !visible(button)) return false;
    const label = (button.textContent || button.value || button.getAttribute("aria-label") || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
    return labels.includes(label);
  });

  if (candidates.length !== 1) {
    return {
      clicked: false,
      error: candidates.length
        ? "Multiple final-submit controls were found; submit manually."
        : "A unique final-submit control was not found.",
    };
  }

  const label = (candidates[0].textContent || candidates[0].value || "Submit").trim();
  candidates[0].click();
  return { clicked: true, label };
}

function detectSubmissionConfirmation() {
  const text = (document.body?.innerText || "").replace(/\s+/g, " ").toLowerCase();
  const patterns = [
    "application submitted",
    "application has been submitted",
    "thank you for applying",
    "thanks for applying",
    "we received your application",
    "we've received your application",
  ];
  const urlSignal = /submitted|thank[-_]?you|confirmation/i.test(location.pathname);
  const matched = patterns.find((pattern) => text.includes(pattern));
  return {
    confirmed: Boolean(matched || urlSignal),
    signal: matched || (urlSignal ? "confirmation URL" : ""),
  };
}

function applyFileToInput(fieldId, base64, filename) {
  const input = document.querySelector(`[data-applypilot-id="${CSS.escape(fieldId)}"]`);
  if (!input || input.type !== "file") {
    return { attached: false, error: "The resume upload field is no longer available." };
  }
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const file = new File(
    [bytes],
    filename,
    { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" },
  );
  const transfer = new DataTransfer();
  transfer.items.add(file);
  input.files = transfer.files;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
  return { attached: input.files?.length === 1, filename: file.name };
}

function extractJobFromPage() {
  const text = (selector) => document.querySelector(selector)?.textContent?.trim() || "";
  const meta = (name) =>
    document.querySelector(`meta[name="${name}"], meta[property="${name}"]`)?.content || "";
  const clean = (value) => value.replace(/\s+/g, " ").trim();
  const host = location.hostname.toLowerCase();
  const adapter = host.includes("linkedin.com")
    ? "linkedin"
    : host.includes("greenhouse.io")
      ? "greenhouse"
      : host.includes("lever.co")
        ? "lever"
        : host.includes("myworkdayjobs.com")
          ? "workday"
          : "generic";

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
    title: [
      ".job-details-jobs-unified-top-card__job-title h1",
      ".posting-headline h2",
      "#header .app-title",
      "[data-automation-id='jobPostingHeader']",
      "h1",
    ],
    company: [
      ".job-details-jobs-unified-top-card__company-name",
      ".posting-headline .company",
      "#header .company-name",
      "[data-automation-id='jobPostingCompany']",
      ".company-name",
    ],
    location: [
      ".job-details-jobs-unified-top-card__primary-description-container",
      ".posting-categories .location",
      "#header .location",
      "[data-automation-id='locations']",
      ".location",
    ],
    description: [
      ".jobs-description-content__text",
      ".posting-page .section-wrapper",
      "#content .content",
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

  const atsSuffixes = [
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "icims.com",
    "smartrecruiters.com",
    "ashbyhq.com",
    "jobvite.com",
  ];
  const isRecognizedAts = (url) => {
    try {
      const parsed = new URL(url, location.href);
      return parsed.protocol === "https:" && atsSuffixes.some(
        (suffix) => parsed.hostname === suffix || parsed.hostname.endsWith(`.${suffix}`),
      );
    } catch {
      return false;
    }
  };
  const externalApply = [...document.querySelectorAll("a[href]")].find((link) => {
    const linkText = clean(link.textContent || "").toLowerCase();
    if (!linkText.includes("apply")) return false;
    try {
      const target = new URL(link.href, location.href);
      return target.protocol === "https:" && target.hostname !== location.hostname;
    } catch {
      return false;
    }
  });
  const onAtsPage = ["greenhouse", "lever", "workday"].includes(adapter);
  const companyApplicationUrl = onAtsPage
    ? location.href
    : externalApply?.href || (structured.url !== location.href ? structured.url || "" : "");
  const easyApplyAvailable = [...document.querySelectorAll("button")].some((button) =>
    clean(button.textContent || "").toLowerCase().includes("easy apply"),
  );

  return {
    source_url: location.href,
    title: clean(structured.title || firstText(selectors.title) || meta("og:title")),
    company: clean(organization.name || firstText(selectors.company)),
    location: clean(locationParts.join(", ") || firstText(selectors.location)),
    description: htmlToText(structured.description) || firstText(selectors.description),
    company_application_url: companyApplicationUrl,
    company_url_verified: onAtsPage || isRecognizedAts(companyApplicationUrl),
    easy_apply_available: easyApplyAvailable,
    adapter,
  };
}
