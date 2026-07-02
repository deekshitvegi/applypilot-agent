chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const actions = {
    captureJob: captureActiveJob,
    scanForm: scanActiveForm,
    fillForm: () => fillActiveForm(message.actions || []),
    advanceApplication: advanceActiveApplication,
    openApplication: () => openApplicationRoute(message.url),
    openExternalApply: openExternalApply,
    submitApplication: submitActiveApplication,
    verifySubmission: verifyActiveSubmission,
    attachResume: () => attachResumeFile(message.fieldId, message.url, message.filename),
    getActiveTab: getActiveTabInfo,
    getTab: () => getTabInfo(message.tabId),
    readPageContext: readActivePageContext,
    inspectPageActions: inspectActivePageActions,
    clickPageAction: () => clickActivePageAction(message.actionId),
    collectJobQueue: () => collectLinkedInJobQueue(message.tabId),
    openQueuedJob: () => openQueuedJob(message.tabId, message.url),
    openEasyApply: openLinkedInEasyApply,
    highlightField: () => highlightActiveField(message.fieldId),
    saveJobContext: () => saveJobContext(message.context),
    loadJobContext,
    openApplicationForm: openActiveApplicationForm,
    assistLogin: () => assistActiveLogin(message.allowClick === true),
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

  const result = await runInTab(tab.id, extractJobFromPage);
  return { ...result, tab_id: tab.id };
}

async function scanActiveForm() {
  const tab = await getActiveHttpTab();
  const fields = await runInTab(tab.id, extractFormFields);
  return { page_url: tab.url, fields, adapter: detectAdapterFromUrl(tab.url) };
}

async function fillActiveForm(actions) {
  const tab = await getActiveHttpTab();
  return runInTab(tab.id, applyFormFillPlan, [actions]);
}

async function advanceActiveApplication() {
  const tab = await getActiveHttpTab();
  return runInTab(tab.id, clickIntermediateApplicationStep);
}

async function submitActiveApplication() {
  const tab = await getActiveHttpTab();
  return runInTab(tab.id, clickFinalSubmit);
}

async function verifyActiveSubmission() {
  const tab = await getActiveHttpTab();
  return runInTab(tab.id, detectSubmissionConfirmation);
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
  return runInTab(tab.id, applyFileToInput, [fieldId, btoa(binary), filename]);
}

async function runInTab(tabId, func, args = []) {
  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId },
      func,
      args,
    });
    if (!result) throw new Error("The page did not return a result.");
    return result.result;
  } catch (error) {
    if (/cannot access|permission|host permission/i.test(error.message)) {
      throw new Error("ApplyPilot needs site access for this page. Enable access in the side panel.");
    }
    throw error;
  }
}

async function getActiveTabInfo() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ? { id: tab.id, url: tab.url || "", title: tab.title || "", status: tab.status } : {};
}

async function getTabInfo(tabId) {
  if (!tabId) return getActiveTabInfo();
  const tab = await chrome.tabs.get(tabId);
  return { id: tab.id, url: tab.url || "", title: tab.title || "", status: tab.status };
}

async function readActivePageContext() {
  const tab = await getActiveHttpTab();
  const context = await runInTab(tab.id, extractVisiblePageContext);
  return { ...context, tab_id: tab.id, url: tab.url };
}

async function inspectActivePageActions() {
  const tab = await getActiveHttpTab();
  return runInTab(tab.id, extractPageActionControls);
}

async function clickActivePageAction(actionId) {
  const tab = await getActiveHttpTab();
  return runInTab(tab.id, clickPlannedPageAction, [actionId]);
}

async function collectLinkedInJobQueue(tabId) {
  const tab = tabId ? await chrome.tabs.get(tabId) : await getActiveHttpTab();
  if (!tab.id || !tab.url?.includes("linkedin.com")) return { tab_id: tab.id, urls: [] };
  const urls = await runInTab(tab.id, extractLinkedInJobLinks);
  return { tab_id: tab.id, urls };
}

async function openQueuedJob(tabId, url) {
  if (!tabId || !/^https:\/\/([a-z0-9-]+\.)*linkedin\.com\//i.test(url || "")) {
    throw new Error("The queued LinkedIn job is not valid.");
  }
  await chrome.tabs.update(tabId, { url, active: true });
  await waitForTabComplete(tabId);
  return getTabInfo(tabId);
}

async function waitForTabComplete(tabId, timeoutMs = 30000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === "complete") return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("The page took too long to load.");
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

async function openLinkedInEasyApply() {
  const tab = await getActiveHttpTab();
  return runInTab(tab.id, clickLinkedInEasyApply);
}

async function openExternalApply() {
  const tab = await getActiveHttpTab();
  const source = new URL(tab.url);
  const before = new Set(
    (await chrome.tabs.query({ currentWindow: true })).map((candidate) => candidate.id),
  );
  const initialSurface = await runInTab(tab.id, detectApplicationSurface);
  const result = await runInTab(tab.id, clickExternalApplyControl);
  if (!result.clicked) return { opened: false, ...result };
  let continuationTabId = null;

  for (let attempt = 0; attempt < 60; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 250));
    const tabs = await chrome.tabs.query({ currentWindow: true });
    const created = tabs.find((candidate) => {
      if (before.has(candidate.id) || !/^https?:/i.test(candidate.url || "")) return false;
      if (!/(^|\.)linkedin\.com$/i.test(source.hostname)) return true;
      return !/(^|\.)linkedin\.com$/i.test(new URL(candidate.url).hostname);
    });
    const original = tabs.find((candidate) => candidate.id === tab.id);
    if (
      original
      && /(^|\.)linkedin\.com$/i.test(source.hostname)
      && /(^|\.)linkedin\.com$/i.test(new URL(original.url || tab.url).hostname)
    ) {
      const continuation = await runInTab(tab.id, resolveLinkedInContinueApplying)
        .catch(() => ({ found: false }));
      if (continuation.href && !continuationTabId) {
        const continued = await chrome.tabs.create({ url: continuation.href, active: true });
        continuationTabId = continued.id;
      }
    }
    const originalMoved = original && /^https?:/i.test(original.url || "")
      && original.url.split("#")[0] !== tab.url.split("#")[0]
      && (
        !/(^|\.)linkedin\.com$/i.test(source.hostname)
        || !/(^|\.)linkedin\.com$/i.test(new URL(original.url).hostname)
      );
    const currentSurface = original
      ? await runInTab(tab.id, detectApplicationSurface).catch(() => ({ ready: false }))
      : { ready: false };
    const openedInline = original && !initialSurface.ready && currentSurface.ready;
    const target = created || (originalMoved || openedInline ? original : null);
    if (!target) continue;
    await chrome.tabs.update(target.id, { active: true });
    return { opened: true, tab_id: target.id, url: target.url || "" };
  }
  return {
    opened: false,
    error: "The Apply button did not open an application page. Click it once manually, then resume ApplyPilot.",
  };
}

async function saveJobContext(context) {
  await chrome.storage.session.set({ applypilotJobContext: context || null });
  return { saved: true };
}

async function loadJobContext() {
  const stored = await chrome.storage.session.get({ applypilotJobContext: null });
  return stored.applypilotJobContext || {};
}

async function openActiveApplicationForm() {
  const tab = await getActiveHttpTab();
  let result = { clicked: false, error: "The application page is still loading." };
  for (let attempt = 0; attempt < 20; attempt += 1) {
    result = await runInTab(tab.id, clickApplicationEntry);
    if (result.clicked || result.already_form || result.listing_page) break;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  if (!result.clicked) return { ...result, tab_id: tab.id };
  await new Promise((resolve) => setTimeout(resolve, 500));
  const [active] = await chrome.tabs.query({ active: true, currentWindow: true });
  return { ...result, tab_id: active?.id || tab.id, url: active?.url || tab.url };
}

async function assistActiveLogin(allowClick) {
  const tab = await getActiveHttpTab();
  return runInTab(tab.id, clickReadyLogin, [allowClick]);
}

async function highlightActiveField(fieldId) {
  const tab = await getActiveHttpTab();
  return runInTab(tab.id, highlightFormField, [fieldId]);
}

function detectAdapterFromUrl(url) {
  const host = new URL(url).hostname.toLowerCase();
  if (host === "linkedin.com" || host.endsWith(".linkedin.com")) return "linkedin";
  if (host === "greenhouse.io" || host.endsWith(".greenhouse.io")) return "greenhouse";
  if (host === "lever.co" || host.endsWith(".lever.co")) return "lever";
  if (host === "myworkdayjobs.com" || host.endsWith(".myworkdayjobs.com")) return "workday";
  return "generic";
}

function extractPageActionControls() {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden"
      && rect.width > 0 && rect.height > 0 && style.opacity !== "0";
  };
  const controls = [];
  [...document.querySelectorAll("button, a[href], [role='button']")].forEach((element, index) => {
    if (!visible(element)) return;
    const label = String(
      element.textContent || element.getAttribute("aria-label") || element.getAttribute("title") || "",
    ).replace(/\s+/g, " ").trim().slice(0, 240);
    if (!label) return;
    const id = `action-${index}`;
    element.dataset.applypilotActionId = id;
    controls.push({
      id,
      label,
      kind: element.matches("a[href]") ? "link" : element.matches("button") ? "button" : "control",
      disabled: Boolean(element.disabled || element.getAttribute("aria-disabled") === "true"),
    });
  });
  return {
    page_title: document.title,
    page_text: String(document.querySelector("main")?.innerText || document.body?.innerText || "")
      .replace(/\s+/g, " ").slice(0, 12000),
    controls: controls.slice(0, 80),
  };
}

function clickPlannedPageAction(actionId) {
  const control = document.querySelector(`[data-applypilot-action-id="${CSS.escape(actionId || "")}"]`);
  if (!control) return { clicked: false, error: "The planned control is no longer available." };
  const label = String(control.textContent || control.getAttribute("aria-label") || "")
    .replace(/\s+/g, " ").trim().toLowerCase();
  if (/submit|send application|finish application|sign in|log in|login|withdraw|delete|purchase|pay/.test(label)) {
    return { clicked: false, error: "The AI planner cannot click final or destructive controls." };
  }
  control.click();
  return { clicked: true, label };
}

async function extractFormFields() {
  const host = location.hostname.toLowerCase();
  let root;
  if (host.includes("linkedin.com")) {
    root = document.querySelector(
      ".jobs-easy-apply-modal, [data-test-modal-id='easy-apply-modal']",
    );
    if (!root) return [];
  } else if (host.includes("greenhouse.io")) {
    root = document.querySelector("#application_form, main") || document;
  } else if (host.includes("lever.co")) {
    root = document.querySelector(".application-form, main") || document;
  } else if (host.includes("myworkdayjobs.com")) {
    root = document.querySelector("[data-automation-id='applicationPage'], main") || document;
  } else {
    root = document.querySelector("main, [role='main']") || document;
  }
  const controls = [...root.querySelectorAll(
    "input, textarea, select, [role='combobox'], button[aria-haspopup='listbox'], input[aria-haspopup='listbox']",
  )].filter((control) => {
    const type = (control.type || "").toLowerCase();
    const customCombobox = control.getAttribute("role") === "combobox" || control.getAttribute("aria-haspopup") === "listbox";
    const style = getComputedStyle(control);
    const rect = control.getBoundingClientRect();
    const visible = type === "file" || (
      style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0
    );
    const popupChild = control.closest("[role='listbox'], [role='menu'], [data-radix-popper-content-wrapper]");
    return visible && !popupChild && !control.disabled && (
      customCombobox || !["hidden", "submit", "button", "reset", "image"].includes(type)
    );
  });

  const cleanText = (value) => String(value || "").replace(/\s+/g, " ").replace(/\s*\*+\s*$/, "").trim();
  const labelledByText = (control) => cleanText(
    (control.getAttribute("aria-labelledby") || "")
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent || "")
      .join(" "),
  );
  const nearbyLabel = (control) => {
    const generic = new Set(["select", "select...", "choose", "choose...", "yes", "no"]);
    let container = control.parentElement;
    for (let depth = 0; container && depth < 5; depth += 1, container = container.parentElement) {
      const candidates = [...container.querySelectorAll(
        "label, legend, [data-testid*='label'], [class*='label'], [class*='question'], p",
      )];
      for (const candidate of candidates) {
        if (candidate.contains(control)) continue;
        const value = cleanText(candidate.textContent);
        if (value.length >= 3 && value.length <= 240 && !generic.has(value.toLowerCase())) {
          return value;
        }
      }
    }
    return "";
  };
  const readableName = (control) => {
    const raw = control.name || control.id || "";
    if (!raw || /^ap-\d+$/.test(raw) || /\[\d+\]/.test(raw)) return "";
    const value = cleanText(raw.replace(/[\[\]_.-]+/g, " "));
    return /[a-z]{3}/i.test(value) ? value : "";
  };

  const collectCustomOptions = (control) => {
    const custom = control.tagName !== "SELECT" && (
      control.getAttribute("role") === "combobox" || control.getAttribute("aria-haspopup") === "listbox"
    );
    if (!custom) return [];
    const ownedIds = `${control.getAttribute("aria-controls") || ""} ${control.getAttribute("aria-owns") || ""}`
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    const popups = ownedIds.map((id) => document.getElementById(id)).filter(Boolean);
    if (!popups.length) return [];
    const candidates = popups.flatMap((popup) => [...popup.querySelectorAll(
      "[role='option'], [data-value], [data-radix-collection-item], [data-slot='select-item']",
    )]);
    const seen = new Set();
    return candidates.flatMap((candidate) => {
      const label = cleanText(candidate.textContent);
      const value = cleanText(
        candidate.getAttribute("data-value") || candidate.getAttribute("value") || label,
      );
      const key = `${value.toLowerCase()}::${label.toLowerCase()}`;
      if (!label || label.length > 240 || seen.has(key)) return [];
      seen.add(key);
      return [{ value, label }];
    });
  };

  const fields = [];
  for (const [index, control] of controls.entries()) {
    const applypilotId = `ap-${index}`;
    control.dataset.applypilotId = applypilotId;
    const explicitLabel = control.id
      ? document.querySelector(`label[for="${CSS.escape(control.id)}"]`)?.textContent
      : "";
    const nativeLabels = [...(control.labels || [])].map((label) => label.textContent).join(" ");
    const wrappingLabel = control.closest("label")?.textContent || "";
    const legend = control.closest("fieldset")?.querySelector("legend")?.textContent || "";
    const labelParts = [
      legend,
      labelledByText(control),
      explicitLabel,
      nativeLabels,
      wrappingLabel,
      nearbyLabel(control),
    ].map(cleanText).filter((part, partIndex, parts) => (
      part && part.length <= 240 && parts.findIndex((value) => value.toLowerCase() === part.toLowerCase()) === partIndex
    ));
    const tag = control.tagName.toLowerCase();
    let fieldType = tag === "textarea" ? "textarea" : tag === "select" || control.getAttribute("role") === "combobox" || control.getAttribute("aria-haspopup") === "listbox" ? "select" : control.type || "text";
    if (!["text", "email", "tel", "url", "number", "textarea", "select", "checkbox", "radio", "file", "password"].includes(fieldType)) {
      fieldType = "other";
    }
    const fallbackLabel =
      control.getAttribute("aria-label") ||
      control.getAttribute("placeholder") ||
      readableName(control);
    const label = cleanText(
      (fieldType === "radio" && legend ? legend : "") ||
      labelledByText(control) || explicitLabel || nativeLabels ||
      control.getAttribute("aria-label") || wrappingLabel || nearbyLabel(control) || fallbackLabel,
    );
    let options = tag === "select"
      ? [...control.options]
          .filter((option) => option.value || option.textContent.trim())
          .map((option) => ({ value: option.value, label: option.textContent.trim() }))
      : [];
    if (fieldType === "select" && tag !== "select") {
      options = collectCustomOptions(control);
    } else if (fieldType === "radio" && control.name) {
      options = [...root.querySelectorAll(`input[type="radio"][name="${CSS.escape(control.name)}"]`)]
        .map((radio) => ({
          value: radio.value || cleanText(radio.labels?.[0]?.textContent),
          label: cleanText(radio.labels?.[0]?.textContent || radio.value),
        }))
        .filter((option) => option.value || option.label);
    }

    const displayedValue = cleanText(
      control.getAttribute("aria-valuetext") || control.getAttribute("data-value") ||
      (fieldType === "select" && tag !== "select" ? control.textContent : ""),
    );
    const emptySelectValues = new Set(["select", "select...", "choose", "choose...", "please select"]);
    const customValue = displayedValue.length <= 160 && !emptySelectValues.has(displayedValue.toLowerCase())
      ? displayedValue
      : "";
    const requiredHint = labelParts.some((part) => /\*\s*$/.test(cleanText(part).replace(/\s+/g, " ")) || /\*/.test(part));

    fields.push({
      id: applypilotId,
      label: cleanText(label || fallbackLabel || `Unlabeled ${fieldType} field`),
      name: control.name || "",
      field_type: fieldType,
      required: control.required || control.getAttribute("aria-required") === "true" || requiredHint,
      value: fieldType === "checkbox" || fieldType === "radio"
        ? (control.checked ? control.value || "true" : "")
        : control.value || customValue,
      options,
    });
  }
  return fields;
}

async function applyFormFillPlan(actions) {
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
      errors.push({ field_id: action.field_id, message: "The field is no longer available." });
      continue;
    }

    try {
      const type = (control.type || control.tagName).toLowerCase();
      if (type === "file" || type === "password") continue;
      if (
        (control.getAttribute("role") === "combobox" || control.getAttribute("aria-haspopup") === "listbox") &&
        control.tagName !== "SELECT"
      ) {
        if (control.tagName === "INPUT") {
          control.click();
          const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(control), "value");
          if (descriptor?.set) descriptor.set.call(control, action.value);
          else control.value = action.value;
          dispatch(control);
        } else {
          control.click();
        }
        const normalize = (value) => String(value || "")
          .normalize("NFKD")
          .replace(/[^a-z0-9]+/gi, " ")
          .replace(/\s+/g, " ")
          .trim()
          .toLowerCase();
        const target = normalize(action.value);
        let option = null;
        for (let attempt = 0; attempt < 10 && !option; attempt += 1) {
          await new Promise((resolve) => setTimeout(resolve, 100));
          const ownedIds = `${control.getAttribute("aria-controls") || ""} ${control.getAttribute("aria-owns") || ""}`
            .trim()
            .split(/\s+/)
            .filter(Boolean);
          let popupRoots = ownedIds.map((id) => document.getElementById(id)).filter(Boolean);
          if (!popupRoots.length) {
            popupRoots = [...document.querySelectorAll("[role='listbox']")].filter((candidate) => {
              const style = getComputedStyle(candidate);
              const rect = candidate.getBoundingClientRect();
              return style.display !== "none" && style.visibility !== "hidden" && rect.height > 0;
            });
          }
          const selector = popupRoots.length
            ? "[role='option'], [data-value], [data-radix-collection-item], [data-slot='select-item'], li"
            : "[role='option']";
          const options = (popupRoots.length
            ? popupRoots.flatMap((popup) => [...popup.querySelectorAll(selector)])
            : [...document.querySelectorAll(selector)]
          ).filter((candidate) => {
            const style = getComputedStyle(candidate);
            const rect = candidate.getBoundingClientRect();
            return style.display !== "none" && style.visibility !== "hidden" && rect.height > 0;
          });
          option = options.find((candidate) =>
            [candidate.textContent, candidate.getAttribute("data-value"), candidate.getAttribute("value")]
              .filter(Boolean)
              .some((value) => {
                const optionValue = normalize(value);
                if (optionValue === target) return true;
                if (/^\d{1,3}$/.test(target) && optionValue.split(" ").includes(target)) return true;
                if (target.length < 3 || optionValue.length < 3) return false;
                return optionValue.startsWith(`${target} `) || target.startsWith(`${optionValue} `);
              }),
          );
        }
        if (!option) throw new Error(`No dropdown option matched "${action.value}".`);
        option.click();
        filled += 1;
        continue;
      }
      if (type === "checkbox") {
        control.checked = ["true", "yes", "1", "on"].includes(String(action.value).toLowerCase());
      } else if (type === "radio") {
        const target = String(action.value).trim().toLowerCase();
        control.checked = [control.value, control.labels?.[0]?.textContent || ""]
          .some((value) => String(value).trim().toLowerCase() === target);
      } else if (control.tagName === "SELECT") {
        const normalizeOption = (value) => String(value || "")
          .normalize("NFKD")
          .replace(/[^a-z0-9]+/gi, " ")
          .replace(/\s+/g, " ")
          .trim()
          .toLowerCase();
        const target = normalizeOption(action.value);
        const option = [...control.options].find((candidate) =>
          [candidate.value, candidate.textContent].some((value) => {
            const candidateValue = normalizeOption(value);
            if (candidateValue === target) return true;
            if (target.length < 3 || candidateValue.length < 3) return false;
            return candidateValue.startsWith(`${target} `) || target.startsWith(`${candidateValue} `);
          }),
        );
        if (!option) throw new Error(`No dropdown option matched "${action.value}".`);
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
      errors.push({ field_id: action.field_id, message: error.message });
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
  if (
    location.hostname.toLowerCase().includes("linkedin.com")
    && !document.querySelector(".jobs-easy-apply-modal, [data-test-modal-id='easy-apply-modal']")
  ) {
    return {
      clicked: false,
      error: "This is a LinkedIn listing, not an application form. Open the employer application first.",
    };
  }
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

  const root = location.hostname.toLowerCase().includes("linkedin.com")
    ? document.querySelector(".jobs-easy-apply-modal, [data-test-modal-id='easy-apply-modal']")
    : document;
  const labels = [
    "submit application",
    "submit your application",
    "submit",
    "send application",
    "finish application",
  ];
  const candidates = [...root.querySelectorAll("button, input[type='submit']")].filter((button) => {
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

function clickIntermediateApplicationStep() {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const linkedinRoot = document.querySelector(
    ".jobs-easy-apply-modal, [data-test-modal-id='easy-apply-modal']",
  );
  const formCandidates = [...document.querySelectorAll("form")]
    .map((form) => ({
      form,
      count: form.querySelectorAll("input, textarea, select, [role='combobox']").length,
    }))
    .sort((left, right) => right.count - left.count);
  const root = linkedinRoot
    || (formCandidates[0]?.count >= 2 ? formCandidates[0].form : null)
    || document.querySelector("main, [role='main']")
    || document;
  const labelOf = (element) => String(
    element.textContent || element.value || element.getAttribute("aria-label") || "",
  ).replace(/\s+/g, " ").trim().toLowerCase();
  const controls = [...root.querySelectorAll("button, input[type='submit'], [role='button']")]
    .filter(visible);
  const finalLabels = [
    "submit application",
    "submit your application",
    "submit",
    "send application",
    "finish application",
  ];
  const finalControls = controls.filter((control) => finalLabels.includes(labelOf(control)));
  if (finalControls.length === 1) {
    return { clicked: false, final_ready: true, label: labelOf(finalControls[0]) };
  }
  const intermediateLabels = [
    "next",
    "continue",
    "review",
    "review application",
    "continue to review",
    "save and continue",
  ];
  const intermediate = controls.filter((control) => {
    const label = labelOf(control);
    return intermediateLabels.includes(label)
      || /^next(?: step)?$/.test(label)
      || /^continue(?: application| to (?:the )?next step)?$/.test(label)
      || /^review (?:your )?application$/.test(label)
      || /^save (?:and|&) continue$/.test(label);
  });
  if (intermediate.length !== 1) {
    return {
      clicked: false,
      final_ready: false,
      error: intermediate.length > 1
        ? "Multiple Next or Review controls were found; choose the correct one."
        : "No Next, Review, or final Submit control was found.",
    };
  }
  const control = intermediate[0];
  const requiredFields = [...root.querySelectorAll(
    "input[required], textarea[required], select[required], [aria-required='true']",
  )].filter((field) => visible(field) && (field.type || "").toLowerCase() !== "hidden");
  const emptyRequired = requiredFields.filter((field) => {
    const type = (field.type || "").toLowerCase();
    if (["checkbox", "radio"].includes(type)) {
      const name = field.name;
      if (!name) return !field.checked;
      return ![...root.querySelectorAll(`[name="${CSS.escape(name)}"]`)].some((item) => item.checked);
    }
    if (type === "file") return !field.files?.length;
    return !String(field.value || "").trim();
  });
  if (emptyRequired.length) {
    return {
      clicked: false,
      final_ready: false,
      intermediate: true,
      error: `${emptyRequired.length} required field${emptyRequired.length === 1 ? " is" : "s are"} still empty on this step.`,
    };
  }
  if (control.disabled || control.getAttribute("aria-disabled") === "true") {
    return {
      clicked: false,
      final_ready: false,
      intermediate: true,
      error: `${labelOf(control) || "Continue"} is disabled. Review the required fields on this step.`,
    };
  }
  control.click();
  const fingerprint = `${location.href}|${controls.map(labelOf).join("|")}|${requiredFields.length}`;
  return { clicked: true, final_ready: false, label: labelOf(control), fingerprint };
}

function detectSubmissionConfirmation() {
  const text = (document.body?.innerText || "").replace(/\s+/g, " ").toLowerCase();
  const patterns = [
    "application submitted",
    "application has been submitted",
    "your application was sent",
    "application was sent",
    "application sent",
    "thank you for applying",
    "thanks for applying",
    "we received your application",
    "we've received your application",
  ];
  const matched = patterns.find((pattern) => text.includes(pattern));
  return {
    confirmed: Boolean(matched),
    signal: matched || "",
  };
}

function clickLinkedInEasyApply() {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const buttons = [...document.querySelectorAll("button")].filter((button) =>
    visible(button) && /easy apply/i.test(button.textContent || button.getAttribute("aria-label") || ""),
  );
  if (buttons.length !== 1) {
    return { opened: false, error: "A unique LinkedIn Easy Apply button was not found." };
  }
  buttons[0].click();
  return { opened: true };
}

function clickExternalApplyControl() {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const labelOf = (element) => String(
    element.textContent || element.getAttribute("aria-label") || element.getAttribute("title") || "",
  ).replace(/\s+/g, " ").trim().toLowerCase();
  const primaryLabel = (label) => (
    label === "apply"
    || label === "apply now"
    || label === "apply for this job"
    || label === "apply for this position"
    || /^apply to .+/.test(label)
    || label.includes("company website")
  );
  const preferred = [...document.querySelectorAll(
    "button.jobs-apply-button, a.jobs-apply-button, [role='button'].jobs-apply-button, button[data-testid*='apply' i], a[data-testid*='apply' i], button[data-cy*='apply' i], a[data-cy*='apply' i]",
  )].filter((element) => {
    const label = labelOf(element);
    return visible(element) && !element.disabled && primaryLabel(label)
      && !label.includes("easy apply") && !label.includes("quick apply");
  });
  const fallback = [...document.querySelectorAll("button, a[href], [role='button']")].filter((element) => {
    const label = labelOf(element);
    return visible(element) && !element.disabled && !label.includes("easy apply")
      && !label.includes("quick apply") && primaryLabel(label);
  });
  const candidates = preferred.length ? preferred : fallback;
  if (candidates.length !== 1) {
    return {
      clicked: false,
      error: candidates.length
        ? "Multiple employer Apply buttons were found; choose the correct one."
        : "The primary Apply button was not found on this job page.",
    };
  }
  candidates[0].click();
  return { clicked: true, label: labelOf(candidates[0]) || "Apply" };
}

function detectApplicationSurface() {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const roots = [...document.querySelectorAll("form, [role='dialog']")];
  const ready = roots.some((root) => {
    if (!visible(root)) return false;
    const controls = [...root.querySelectorAll("input, textarea, select, [role='combobox']")]
      .filter((control) => visible(control) && !["hidden", "search"].includes((control.type || "").toLowerCase()));
    return controls.length >= 2;
  });
  return { ready };
}

function resolveLinkedInContinueApplying() {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  if (!/job search safety reminder/i.test(document.body?.innerText || "")) {
    return { found: false };
  }
  const buttons = [...document.querySelectorAll("button, a, [role='button']")].filter((button) => {
    const label = String(button.textContent || button.getAttribute("aria-label") || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
    return visible(button) && label.startsWith("continue applying");
  });
  if (buttons.length !== 1) return { found: false };
  const control = buttons[0];
  const anchor = control.matches("a[href]") ? control : control.closest("a[href]");
  const rawUrl = anchor?.href
    || control.getAttribute("data-redirect-url")
    || control.getAttribute("data-url")
    || "";
  if (rawUrl) {
    try {
      const href = new URL(rawUrl, location.href);
      if (href.protocol === "https:" && !/(^|\.)linkedin\.com$/i.test(href.hostname)) {
        return { found: true, href: href.href, clicked: false };
      }
    } catch {
      // Fall back to the control's click handler.
    }
  }
  control.click();
  return { found: true, href: "", clicked: true };
}

function clickApplicationEntry() {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  if (
    location.hostname.toLowerCase().includes("linkedin.com")
    && !document.querySelector(".jobs-easy-apply-modal, [data-test-modal-id='easy-apply-modal']")
  ) {
    return {
      clicked: false,
      listing_page: true,
      error: "Open the employer Apply button before scanning application fields.",
    };
  }
  const formControls = [...document.querySelectorAll("input, textarea, select")].filter((control) => {
    const type = (control.type || "").toLowerCase();
    return visible(control) && !["hidden", "submit", "button"].includes(type);
  });
  const labels = ["apply now", "apply for this job", "apply for this position", "start application", "continue application"];
  const rawCandidates = [...document.querySelectorAll("a, button, [role='button']")].filter((element) => {
    if (!visible(element) || element.disabled || element.getAttribute("aria-disabled") === "true") return false;
    const label = (element.textContent || element.getAttribute("aria-label") || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
    return labels.includes(label);
  });
  let candidates = rawCandidates.filter(
    (candidate) => !rawCandidates.some(
      (other) => other !== candidate && other.contains(candidate),
    ),
  );
  if (candidates.length > 1) {
    const onScreen = candidates.filter((candidate) => {
      const rect = candidate.getBoundingClientRect();
      return rect.bottom > 0 && rect.top < innerHeight && rect.right > 0 && rect.left < innerWidth;
    });
    if (onScreen.length) candidates = onScreen;
  }
  if (candidates.length > 1) {
    const normalized = candidates.map((candidate) => (
      candidate.textContent || candidate.getAttribute("aria-label") || ""
    ).replace(/\s+/g, " ").trim().toLowerCase());
    if (new Set(normalized).size === 1) {
      candidates.sort((left, right) => {
        const leftRect = left.getBoundingClientRect();
        const rightRect = right.getBoundingClientRect();
        return rightRect.width * rightRect.height - leftRect.width * leftRect.height;
      });
      candidates = [candidates[0]];
    }
  }
  if (candidates.length === 1) {
    if (formControls.length >= 3 && candidates[0].closest("form")) {
      return { clicked: false, already_form: true };
    }
    candidates[0].click();
    return { clicked: true, label: (candidates[0].textContent || "Apply").trim() };
  }
  if (candidates.length > 1) {
    return {
      clicked: false,
      error: "Multiple Apply buttons were found; choose the correct one.",
    };
  }
  if (formControls.length >= 3) return { clicked: false, already_form: true };
  return { clicked: false, error: "No unique Apply button was found on this page." };
}

function clickReadyLogin(allowClick) {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const challenge = [...document.querySelectorAll(
    "iframe[src*='captcha'], iframe[src*='recaptcha'], iframe[src*='hcaptcha'], input[autocomplete='one-time-code']",
  )].some(visible);
  if (challenge) {
    return {
      clicked: false,
      login_page: true,
      error: "CAPTCHA, MFA, or a verification code requires you.",
    };
  }
  const password = [...document.querySelectorAll("input[type='password']")].find(visible);
  const username = [...document.querySelectorAll(
    "input[type='email'], input[autocomplete='username'], input[name*='email' i], input[name*='user' i]",
  )].find(visible);
  const loginPage = Boolean(
    password || (username && /login|log-in|sign-in|signin|auth/i.test(location.pathname)),
  );
  if (!loginPage) return { clicked: false, login_page: false };
  if ((password && !password.value) || (username && !username.value)) {
    return {
      clicked: false,
      login_page: true,
      error: "Use your browser password manager to fill the login fields; ApplyPilot never captures or stores them.",
    };
  }
  if (!allowClick) {
    return {
      clicked: false,
      login_page: true,
      error: "Login is ready. Enable browser-assisted login or sign in manually.",
    };
  }
  const labels = ["sign in", "log in", "login", "continue", "next"];
  const buttons = [...document.querySelectorAll("button, input[type='submit']")].filter((button) => {
    if (!visible(button) || button.disabled) return false;
    const label = (button.textContent || button.value || button.getAttribute("aria-label") || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
    return labels.includes(label);
  });
  if (buttons.length !== 1) {
    return { clicked: false, login_page: true, error: "A unique login button was not found." };
  }
  buttons[0].click();
  return { clicked: true, login_page: true };
}

function highlightFormField(fieldId) {
  const control = document.querySelector(`[data-applypilot-id="${CSS.escape(fieldId)}"]`);
  if (!control) return { highlighted: false };
  control.scrollIntoView({ behavior: "smooth", block: "center" });
  const previousOutline = control.style.outline;
  const previousOffset = control.style.outlineOffset;
  control.style.outline = "3px solid #f59e0b";
  control.style.outlineOffset = "3px";
  setTimeout(() => {
    control.style.outline = previousOutline;
    control.style.outlineOffset = previousOffset;
  }, 6000);
  return { highlighted: true };
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
      ".job-details-jobs-unified-top-card__job-title",
      ".jobs-unified-top-card__job-title",
      ".job-details-jobs-unified-top-card__job-title-link",
      ".posting-headline h2",
      "#header .app-title",
      "[data-automation-id='jobPostingHeader']",
      "h1",
    ],
    company: [
      ".job-details-jobs-unified-top-card__company-name",
      ".jobs-unified-top-card__company-name",
      ".job-details-jobs-unified-top-card__primary-description-container a",
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
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const onAtsPage = ["greenhouse", "lever", "workday"].includes(adapter);
  const primaryApplyLabels = ["apply", "apply now", "apply for this job", "apply for this position"];
  const externalApplyAvailable = !onAtsPage && [...document.querySelectorAll(
    ".jobs-apply-button, button, a[href], [role='button']",
  )].some((element) => {
    const label = clean(element.textContent || element.getAttribute("aria-label") || "").toLowerCase();
    return visible(element) && !element.disabled && !label.includes("easy apply")
      && !label.includes("quick apply") && (
        element.matches(".jobs-apply-button")
        || primaryApplyLabels.includes(label)
        || label.includes("company website")
      );
  });
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
    external_apply_available: externalApplyAvailable,
    easy_apply_available: easyApplyAvailable,
    adapter,
  };
}

function extractVisiblePageContext() {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  return {
    title: clean(document.querySelector("h1")?.textContent || document.title),
    text: clean(document.querySelector("main")?.innerText || document.body?.innerText).slice(0, 30000),
  };
}

function extractLinkedInJobLinks() {
  const current = location.href.split("?")[0];
  return [...new Set(
    [...document.querySelectorAll("a[href*='/jobs/view/']")]
      .map((link) => {
        try {
          const url = new URL(link.href, location.href);
          url.search = "";
          url.hash = "";
          return url.href;
        } catch {
          return "";
        }
      })
      .filter((url) => url && url.split("?")[0] !== current),
  )].slice(0, 25);
}
