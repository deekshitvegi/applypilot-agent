chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const actions = {
    captureJob: captureActiveJob,
    scanForm: scanActiveForm,
    fillForm: () => fillActiveForm(message.actions || [], message.frameId),
    advanceApplication: () => advanceActiveApplication(message.frameId),
    openApplication: () => openApplicationRoute(message.url),
    openExternalApply: openExternalApply,
    submitApplication: () => submitActiveApplication(message.frameId),
    verifySubmission: () => verifyActiveSubmission(message.frameId),
    attachResume: () => attachResumeFile(
      message.fieldId,
      message.url,
      message.filename,
      message.frameId,
    ),
    getActiveTab: getActiveTabInfo,
    getTab: () => getTabInfo(message.tabId),
    readPageContext: readActivePageContext,
    inspectPageActions: inspectActivePageActions,
    clickPageAction: () => clickActivePageAction(
      message.actionId,
      message.expectedLabel,
      message.expectedKind,
      message.frameId,
    ),
    collectJobQueue: () => collectLinkedInJobQueue(message.tabId),
    openQueuedJob: () => openQueuedJob(message.tabId, message.url),
    openEasyApply: openLinkedInEasyApply,
    highlightField: () => highlightActiveField(message.fieldId, message.frameId),
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
  const frames = await runInAllFrames(tab.id, runFormPass, [null]);
  const best = frames
    .filter((frame) => Array.isArray(frame.result?.fields))
    .sort((left, right) => right.result.fields.length - left.result.fields.length)[0];
  return {
    page_url: tab.url,
    fields: best?.result?.fields || [],
    frame_id: best?.frame_id ?? 0,
    adapter: detectAdapterFromUrl(tab.url),
  };
}

async function fillActiveForm(actions, frameId) {
  const tab = await getActiveHttpTab();
  return runInFrame(tab.id, frameId, runFormPass, [actions || []]);
}

async function advanceActiveApplication(frameId) {
  const tab = await getActiveHttpTab();
  return runInFrame(tab.id, frameId, clickIntermediateApplicationStep);
}

async function submitActiveApplication(frameId) {
  const tab = await getActiveHttpTab();
  return runInFrame(tab.id, frameId, clickFinalSubmit);
}

async function verifyActiveSubmission(frameId) {
  const tab = await getActiveHttpTab();
  try {
    const selected = await runInFrame(tab.id, frameId, detectSubmissionConfirmation);
    if (selected.confirmed) return selected;
  } catch {
    // The submitted iframe may have navigated or been removed; inspect remaining frames.
  }
  const frames = await runInAllFrames(tab.id, detectSubmissionConfirmation);
  return frames.find((frame) => frame.result?.confirmed)?.result || {
    confirmed: false,
    signal: "",
  };
}

async function attachResumeFile(fieldId, url, filename, frameId) {
  const source = new URL(url);
  if (!["127.0.0.1", "localhost"].includes(source.hostname)) {
    throw new Error("Resume files can only be attached from the local ApplyPilot service.");
  }
  const response = await fetch(source.href);
  if (!response.ok) {
    let detail = "Could not download the application file from the local agent.";
    try {
      const payload = await response.json();
      if (payload?.detail) detail = payload.detail;
    } catch {
      // Keep the generic message when the local service did not return JSON.
    }
    throw new Error(detail);
  }
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  const tab = await getActiveHttpTab();
  const mediaType = response.headers.get("content-type") || "application/octet-stream";
  return runInFrame(
    tab.id,
    frameId,
    applyFileToInput,
    [fieldId, btoa(binary), filename, mediaType],
  );
}

async function runInTab(tabId, func, args = []) {
  return runInFrame(tabId, 0, func, args);
}

async function runInFrame(tabId, frameId, func, args = []) {
  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId, frameIds: [Number.isInteger(frameId) ? frameId : 0] },
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

async function runInAllFrames(tabId, func, args = []) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      func,
      args,
    });
    return results.map((item) => ({ frame_id: item.frameId, result: item.result }));
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
  const frames = await runInAllFrames(tab.id, extractPageActionControls);
  const ranked = frames
    .filter((frame) => frame.result?.controls?.length)
    .sort((left, right) => {
      const score = (frame) => {
        const labels = frame.result.controls.map((control) => control.label);
        const hasApplicationEntry = labels.some((label) => (
          /^apply$|^apply\s+now\b|^apply\s+for\s+(?:this|the)\s+(?:job|position)\b/i.test(label)
          || /^(?:start|continue)\s+(?:the\s+)?application\b/i.test(label)
        ));
        return (hasApplicationEntry ? 10000 : 0) + labels.reduce((total, label) => (
          total + (/apply|continue|next|review|start/i.test(label) ? 10 : 1)
        ), 0);
      };
      return score(right) - score(left);
    });
  const best = ranked[0];
  return best ? { ...best.result, frame_id: best.frame_id } : {
    page_title: tab.title || "",
    page_text: "",
    controls: [],
    frame_id: 0,
  };
}

async function clickActivePageAction(actionId, expectedLabel, expectedKind, frameId) {
  const tab = await getActiveHttpTab();
  return runInFrame(
    tab.id,
    frameId,
    clickPlannedPageAction,
    [actionId, expectedLabel || "", expectedKind || ""],
  );
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
    const frames = await runInAllFrames(tab.id, clickApplicationEntry, [true]);
    const clickable = frames.filter((frame) => frame.result?.clickable);
    if (clickable.length === 1) {
      const selected = clickable[0];
      result = await runInFrame(tab.id, selected.frame_id, clickApplicationEntry, [false]);
      result = { ...result, frame_id: selected.frame_id };
    } else if (clickable.length > 1) {
      result = { clicked: false, error: "Multiple Apply controls were found across the page frames." };
    } else {
      const ready = frames.find((frame) => frame.result?.already_form);
      if (ready) {
        result = { ...ready.result, frame_id: ready.frame_id };
        break;
      }
      const listing = frames.find((frame) => frame.result?.listing_page);
      const informative = frames.find((frame) => frame.result?.error);
      result = listing?.result || informative?.result || result;
    }
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

async function highlightActiveField(fieldId, frameId) {
  const tab = await getActiveHttpTab();
  return runInFrame(tab.id, frameId, highlightFormField, [fieldId]);
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
  const roots = [document];
  for (let index = 0; index < roots.length; index += 1) {
    [...roots[index].querySelectorAll("*")].forEach((element) => {
      if (element.shadowRoot && !roots.includes(element.shadowRoot)) roots.push(element.shadowRoot);
    });
  }
  const elements = roots.flatMap((root) => [...root.querySelectorAll(
    "button, a, [role='button'], input[type='button'], input[type='submit']",
  )]);
  const controls = [];
  elements.forEach((element, index) => {
    if (!visible(element)) return;
    const label = String(
      element.innerText || element.value || element.getAttribute("aria-label")
      || element.getAttribute("title") || element.textContent || "",
    ).replace(/\s+/g, " ").trim().slice(0, 240);
    if (!label) return;
    const id = `action-${index}`;
    element.dataset.applypilotActionId = id;
    const normalized = label.toLowerCase();
    const rect = element.getBoundingClientRect();
    const onScreen = rect.bottom > 0 && rect.top < innerHeight
      && rect.right > 0 && rect.left < innerWidth;
    let priority = onScreen ? 100 : 0;
    if (/^apply$|^apply\s+now\b|^apply\s+for\s+(?:this|the)\s+(?:job|position)\b/.test(normalized)) priority += 1000;
    else if (/^(?:start|continue)\s+(?:the\s+)?application\b/.test(normalized)) priority += 900;
    else if (/^(?:continue|next|review)\b/.test(normalized)) priority += 500;
    controls.push({
      id,
      label,
      kind: element.matches("a[href]") ? "link" : element.matches("button, input[type='button'], input[type='submit']") ? "button" : "control",
      disabled: Boolean(element.disabled || element.getAttribute("aria-disabled") === "true"),
      priority,
    });
  });
  controls.sort((left, right) => right.priority - left.priority);
  return {
    page_title: document.title,
    page_text: String(document.querySelector("main")?.innerText || document.body?.innerText || "")
      .replace(/\s+/g, " ").slice(0, 12000),
    controls: controls.slice(0, 80).map(({ priority: _priority, ...control }) => control),
  };
}

function clickPlannedPageAction(actionId, expectedLabel, expectedKind) {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden"
      && rect.width > 0 && rect.height > 0 && style.opacity !== "0";
  };
  const normalize = (value) => String(value || "").replace(/\s+/g, " ").trim().toLowerCase();
  const labelOf = (element) => normalize(
    element.innerText || element.value || element.getAttribute("aria-label")
    || element.getAttribute("title") || element.textContent || "",
  );
  const kindOf = (element) => element.matches("a[href]")
    ? "link"
    : element.matches("button, input[type='button'], input[type='submit']") ? "button" : "control";
  const roots = [document];
  for (let index = 0; index < roots.length; index += 1) {
    [...roots[index].querySelectorAll("*")].forEach((element) => {
      if (element.shadowRoot && !roots.includes(element.shadowRoot)) roots.push(element.shadowRoot);
    });
  }
  const elements = roots.flatMap((root) => [...root.querySelectorAll(
    "button, a, [role='button'], input[type='button'], input[type='submit']",
  )]);
  let control = roots
    .map((root) => root.querySelector(`[data-applypilot-action-id="${CSS.escape(actionId || "")}"]`))
    .find(Boolean);
  const expected = normalize(expectedLabel);
  if (!control || (expected && labelOf(control) !== expected)) {
    const matches = elements.filter((element) => (
      visible(element)
      && (!expected || labelOf(element) === expected)
      && (!expectedKind || kindOf(element) === expectedKind)
    ));
    if (matches.length !== 1) {
      return {
        clicked: false,
        error: matches.length
          ? "The page changed and multiple matching controls are now visible."
          : "The page changed and the planned control could not be safely re-identified.",
      };
    }
    [control] = matches;
  }
  const label = labelOf(control);
  if (/submit|send application|finish application|sign in|log in|login|withdraw|delete|purchase|pay/.test(label)) {
    return { clicked: false, error: "The AI planner cannot click final or destructive controls." };
  }
  control.click();
  return { clicked: true, label };
}

async function runFormPass(actions) {
  const fillMode = Array.isArray(actions);
  const cleanText = (value) => String(value || "").replace(/\s+/g, " ").replace(/\s*\*+\s*$/, "").trim();
  const normalizeText = (value) => String(value || "")
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
  const semanticChoice = (value) => {
    const normalized = normalizeText(value);
    const tokens = new Set(normalized.split(" "));
    if (normalized === "true" || normalized === "1" || tokens.has("yes")) return "yes";
    if (normalized === "false" || normalized === "0" || tokens.has("no") || normalized.includes("do not")) return "no";
    return normalized;
  };
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const dispatch = (control) => {
    control.dispatchEvent(new Event("input", { bubbles: true }));
    control.dispatchEvent(new Event("change", { bubbles: true }));
    control.dispatchEvent(new Event("blur", { bubbles: true }));
  };

  const collectRoots = () => {
    const host = location.hostname.toLowerCase();
    let scope;
    if (host.includes("linkedin.com")) {
      scope = document.querySelector(".jobs-easy-apply-modal, [data-test-modal-id='easy-apply-modal']");
      if (!scope) return [];
    } else if (host.includes("greenhouse.io")) {
      scope = document.querySelector("#application_form, main") || document;
    } else if (host.includes("lever.co")) {
      scope = document.querySelector(".application-form, main") || document;
    } else if (host.includes("myworkdayjobs.com")) {
      scope = document.querySelector("[data-automation-id='applicationPage'], main") || document;
    } else {
      scope = document.querySelector("main, [role='main']") || document;
    }
    const roots = [scope];
    for (let index = 0; index < roots.length; index += 1) {
      [...roots[index].querySelectorAll("*")].forEach((element) => {
        if (element.shadowRoot && !roots.includes(element.shadowRoot)) roots.push(element.shadowRoot);
      });
    }
    return roots;
  };

  const elementVisible = (element) => {
    if (!element) return false;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };

  const isPlainChoiceButton = (control) => {
    if (control.tagName !== "BUTTON") return false;
    const label = String(control.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
    if (!new Set(["yes", "no"]).has(label)) return false;
    let container = control.parentElement;
    for (let depth = 0; container && depth < 4; depth += 1, container = container.parentElement) {
      const choiceCount = [...container.querySelectorAll("button")].filter((candidate) => (
        ["yes", "no"].includes(String(candidate.textContent || "").trim().toLowerCase())
      )).length;
      if (choiceCount >= 2) return true;
    }
    return false;
  };

  const isYesNoBackingInput = (control) => {
    if (control.tagName !== "INPUT" || (control.type || "").toLowerCase() !== "checkbox") return false;
    const buttons = [...(control.parentElement?.querySelectorAll("button") || [])]
      .map((candidate) => String(candidate.textContent || "").trim().toLowerCase());
    return buttons.includes("yes") && buttons.includes("no");
  };

  // Selected state must come from signals the page itself owns. ApplyPilot
  // never writes checked, ARIA, data-state, data-selected, or class values,
  // so a positive signal here reflects state the page framework accepted.
  const selectionState = (control) => {
    const channels = [];
    let positive = false;
    if (control instanceof HTMLInputElement && ["checkbox", "radio"].includes((control.type || "").toLowerCase())) {
      channels.push("native");
      positive = positive || control.checked;
    }
    for (const attribute of ["aria-checked", "aria-pressed", "aria-selected"]) {
      if (control.hasAttribute(attribute)) {
        channels.push("aria");
        positive = positive || control.getAttribute(attribute) === "true";
      }
    }
    if (control.hasAttribute("data-state")) {
      channels.push("data");
      positive = positive || ["checked", "on", "selected", "active", "true"]
        .includes(String(control.getAttribute("data-state")).toLowerCase());
    }
    if (control.hasAttribute("data-selected")) {
      channels.push("data");
      positive = positive || ["true", "yes", "selected", "on"]
        .includes(String(control.getAttribute("data-selected")).toLowerCase());
    }
    const className = typeof control.className === "string" ? control.className : "";
    if (/(?:^|[\s_-])(?:selected|active|checked|chosen)(?:$|[\s_-])/i.test(className)) {
      channels.push("class");
      positive = true;
    }
    if (!channels.length) return { channel: "", selected: null };
    return { channel: channels[0], selected: positive };
  };

  const individualChoiceLabel = (control) => {
    const explicit = control.id
      ? control.getRootNode()?.querySelector?.(`label[for="${CSS.escape(control.id)}"]`)?.textContent
        || document.querySelector(`label[for="${CSS.escape(control.id)}"]`)?.textContent
      : "";
    const siblingText = [control.nextElementSibling, control.previousElementSibling]
      .map((candidate) => cleanText(candidate?.textContent))
      .find((value) => value && value.length <= 100) || "";
    const parentText = cleanText(control.parentElement?.textContent);
    return cleanText(
      [...(control.labels || [])].map((item) => item.textContent).join(" ")
      || control.closest("label")?.textContent
      || explicit
      || control.getAttribute("aria-label")
      || control.textContent
      || siblingText
      || (parentText.length <= 100 ? parentText : "")
      || control.value,
    );
  };

  const optionLabelOf = (member) => cleanText(
    member.dataset?.applypilotOptionLabel || individualChoiceLabel(member) || member.value,
  );

  const backingYesNoFor = (groupControls) => {
    for (const member of groupControls) {
      let container = member.parentElement;
      for (let depth = 0; container && depth < 4; depth += 1, container = container.parentElement) {
        const backing = [...container.querySelectorAll('input[type="checkbox"]')].find((candidate) => (
          !groupControls.includes(candidate) && !elementVisible(candidate) && isYesNoBackingInput(candidate)
        ));
        if (backing) return backing;
      }
    }
    return null;
  };

  const groupSelection = (groupControls) => {
    let readable = false;
    for (const member of groupControls) {
      const state = selectionState(member);
      if (state.selected === true) return { member, evidence: state.channel, readable: true };
      if (state.channel && state.channel !== "class") readable = true;
    }
    const backing = backingYesNoFor(groupControls);
    if (backing?.checked) {
      const yes = groupControls.find((member) => semanticChoice(optionLabelOf(member)) === "yes");
      if (yes) return { member: yes, evidence: "backing-input", readable: true };
    }
    return { member: null, evidence: "", readable };
  };

  const labelledByText = (control) => cleanText(
    (control.getAttribute("aria-labelledby") || "")
      .split(/\s+/)
      .map((id) => control.getRootNode()?.getElementById?.(id)?.textContent || document.getElementById(id)?.textContent || "")
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
  const nearbyInstructions = (control) => {
    let container = control.parentElement;
    for (let depth = 0; container && depth < 4; depth += 1, container = container.parentElement) {
      const candidates = [...container.querySelectorAll(
        "p, small, [class*='description'], [class*='instruction'], [class*='help-text'], [data-testid*='description']",
      )];
      const text = candidates
        .filter((candidate) => !candidate.contains(control))
        .map((candidate) => cleanText(candidate.textContent))
        .find((value) => value.length >= 12 && value.length <= 600);
      if (text) return text;
    }
    return "";
  };
  const readableName = (control) => {
    const raw = control.name || control.id || "";
    if (!raw || /^ap-\d+$/.test(raw) || /\[\d+\]/.test(raw)) return "";
    const value = cleanText(raw.replace(/[\[\]_.-]+/g, " "));
    return /[a-z]{3}/i.test(value) ? value : "";
  };

  const groupQuestion = (control) => {
    const fieldsetLegend = control.closest("fieldset")?.querySelector("legend")?.textContent || "";
    if (cleanText(fieldsetLegend)) {
      return { label: cleanText(fieldsetLegend), required: /\*/.test(fieldsetLegend) };
    }
    let container = control.parentElement;
    const nativeType = (control.type || "").toLowerCase();
    const choiceType = control.getAttribute("role") === "radio" || control.hasAttribute("aria-pressed") || isPlainChoiceButton(control)
      ? "radio"
      : control.getAttribute("role") === "checkbox" || control.hasAttribute("aria-checked")
        ? "checkbox"
        : nativeType;
    const groupSelector = choiceType === "radio"
      ? 'input[type="radio"], [role="radio"], button[aria-pressed], button'
      : choiceType === "checkbox"
        ? 'input[type="checkbox"], [role="checkbox"], button[aria-checked]'
        : `input[type="${CSS.escape(nativeType)}"]`;
    for (let depth = 0; container && depth < 7; depth += 1, container = container.parentElement) {
      const grouped = [...container.querySelectorAll(groupSelector)]
        .filter((candidate) => candidate.getRootNode() === control.getRootNode());
      if (grouped.length < 2) continue;
      const candidates = [
        ...container.querySelectorAll(
          "legend, h1, h2, h3, h4, h5, h6, p, strong, label, [class*='question'], [data-testid*='question'], [aria-level]",
        ),
      ];
      const question = candidates.find((candidate) => {
        if (candidate.contains(control) || candidate.querySelector("input, textarea, select")) return false;
        const text = cleanText(candidate.textContent);
        return text.length >= 4 && text.length <= 500;
      });
      if (question) {
        return {
          label: cleanText(question.textContent),
          required: /\*/.test(question.textContent || ""),
        };
      }
      let previous = container.previousElementSibling;
      while (previous) {
        const text = cleanText(previous.textContent);
        if (text.length >= 4 && text.length <= 500) {
          return { label: text, required: /\*/.test(previous.textContent || "") };
        }
        previous = previous.previousElementSibling;
      }
    }
    return { label: "", required: false };
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

  const discover = () => {
    const roots = collectRoots();
    if (!roots.length) return [];
    const queryAll = (selector) => roots.flatMap((candidate) => [...candidate.querySelectorAll(selector)]);
    const controls = queryAll(
      "input, textarea, select, button, [role='combobox'], [role='radio'], [role='checkbox'], input[aria-haspopup='listbox']",
    ).filter((control) => {
      if (isYesNoBackingInput(control)) return false;
      const type = (control.type || "").toLowerCase();
      const customCombobox = control.getAttribute("role") === "combobox" || control.getAttribute("aria-haspopup") === "listbox";
      const customChoice = ["radio", "checkbox"].includes(control.getAttribute("role"))
        || control.hasAttribute("aria-pressed")
        || control.hasAttribute("aria-checked")
        || isPlainChoiceButton(control);
      const labelledControlVisible = ["checkbox", "radio"].includes(type)
        && [...(control.labels || [])].some(elementVisible);
      const visible = type === "file" || elementVisible(control) || labelledControlVisible;
      const popupChild = control.closest("[role='listbox'], [role='menu'], [data-radix-popper-content-wrapper]");
      return visible && !popupChild && !control.disabled && (
        customCombobox || customChoice || !["hidden", "submit", "button", "reset", "image"].includes(type)
      );
    });

    const records = [];
    const seenRadioGroups = new Set();
    const fingerprintCounts = new Map();
    for (const [index, control] of controls.entries()) {
      const applypilotId = `ap-${index}`;
      const explicitLabel = control.id
        ? control.getRootNode()?.querySelector?.(`label[for="${CSS.escape(control.id)}"]`)?.textContent
          || document.querySelector(`label[for="${CSS.escape(control.id)}"]`)?.textContent
        : "";
      const nativeLabels = [...(control.labels || [])].map((label) => label.textContent).join(" ");
      const wrappingLabel = control.closest("label")?.textContent || "";
      const legend = control.closest("fieldset")?.querySelector("legend")?.textContent || "";
      const rawLabelParts = [
        legend,
        labelledByText(control),
        explicitLabel,
        nativeLabels,
        wrappingLabel,
        nearbyLabel(control),
      ];
      const tag = control.tagName.toLowerCase();
      const customRadio = control.getAttribute("role") === "radio"
        || control.hasAttribute("aria-pressed")
        || isPlainChoiceButton(control);
      const customCheckbox = control.getAttribute("role") === "checkbox"
        || (control.hasAttribute("aria-checked") && !customRadio);
      let fieldType = customRadio
        ? "radio"
        : customCheckbox
          ? "checkbox"
        : tag === "textarea" ? "textarea" : tag === "select" || control.getAttribute("role") === "combobox" || control.getAttribute("aria-haspopup") === "listbox" ? "select" : control.type || "text";
      if (!["text", "email", "tel", "url", "number", "textarea", "select", "checkbox", "radio", "file", "password"].includes(fieldType)) {
        fieldType = "other";
      }
      const fallbackLabel =
        control.getAttribute("aria-label") ||
        control.getAttribute("placeholder") ||
        readableName(control);
      const grouped = ["radio", "checkbox"].includes(fieldType)
        ? groupQuestion(control)
        : { label: "", required: false };
      const groupedQuestion = grouped.label;
      const optionLabel = individualChoiceLabel(control);
      const normalizedGroupQuestion = cleanText(groupedQuestion).toLowerCase();
      const radioGroupControls = fieldType === "radio"
        ? queryAll('input[type="radio"], [role="radio"], button[aria-pressed], button').filter((candidate) => {
            if (candidate.getRootNode() !== control.getRootNode()) return false;
            if (candidate.tagName === "BUTTON" && !candidate.hasAttribute("aria-pressed") && !isPlainChoiceButton(candidate)) return false;
            if (control.name) return candidate.name === control.name;
            return normalizedGroupQuestion
              && cleanText(groupQuestion(candidate).label).toLowerCase() === normalizedGroupQuestion;
          })
        : [];
      const radioGroupKey = fieldType === "radio"
        ? `${roots.indexOf(control.getRootNode())}:${control.name || normalizedGroupQuestion || applypilotId}`
        : "";
      if (radioGroupKey && seenRadioGroups.has(radioGroupKey)) continue;
      if (radioGroupKey) seenRadioGroups.add(radioGroupKey);
      control.dataset.applypilotId = applypilotId;
      radioGroupControls.forEach((candidate) => {
        candidate.dataset.applypilotId = applypilotId;
        candidate.dataset.applypilotChoiceKind = "radio";
        candidate.dataset.applypilotOptionLabel = individualChoiceLabel(candidate);
      });
      const baseLabel = cleanText(fieldType === "radio"
        ? groupedQuestion || legend || nearbyLabel(control) || fallbackLabel
        : fieldType === "checkbox" && groupedQuestion
          ? `${groupedQuestion} ${optionLabel}`
          : labelledByText(control) || explicitLabel || nativeLabels ||
            control.getAttribute("aria-label") || wrappingLabel || nearbyLabel(control) || fallbackLabel);
      const instructions = fieldType === "textarea" ? nearbyInstructions(control) : "";
      const label = cleanText(
        instructions && !baseLabel.toLowerCase().includes(instructions.toLowerCase())
          ? `${baseLabel} ${instructions}`
          : baseLabel,
      );
      control.dataset.applypilotFieldLabel = label;
      control.dataset.applypilotFieldType = fieldType;
      radioGroupControls.forEach((candidate) => {
        candidate.dataset.applypilotFieldLabel = label;
        candidate.dataset.applypilotFieldType = fieldType;
      });
      let options = tag === "select"
        ? [...control.options]
            .filter((option) => option.value || option.textContent.trim())
            .map((option) => ({ value: option.value, label: option.textContent.trim() }))
        : [];
      if (fieldType === "select" && tag !== "select") {
        options = collectCustomOptions(control);
      } else if (fieldType === "radio") {
        options = radioGroupControls
          .map((radio) => {
            const option = radio.dataset.applypilotOptionLabel || individualChoiceLabel(radio);
            const rawValue = cleanText(radio.value);
            return {
              value: !rawValue || rawValue.toLowerCase() === "on" ? option : rawValue,
              label: option || rawValue,
            };
          })
          .filter((option) => option.value || option.label);
      } else if (fieldType === "checkbox" && groupedQuestion) {
        options = queryAll('input[type="checkbox"], [role="checkbox"], button[aria-checked]')
          .filter((candidate) => (
            candidate.getRootNode() === control.getRootNode()
            && groupQuestion(candidate).label === groupedQuestion
          ))
          .map((candidate) => {
            const candidateLabel = individualChoiceLabel(candidate);
            return { value: candidate.value || candidateLabel, label: candidateLabel };
          })
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
      const requiredHint = grouped.required || rawLabelParts.some((part) => /\*/.test(String(part || "")));
      const radioRequired = fieldType === "radio"
        ? radioGroupControls.some((candidate) => (
            candidate.required || candidate.getAttribute("aria-required") === "true"
          ))
        : false;

      let value = "";
      let valueLabel = "";
      let valueEvidence = "";
      let stateReadable = true;
      if (fieldType === "radio") {
        const groupMembers = radioGroupControls.length ? radioGroupControls : [control];
        const selection = groupSelection(groupMembers);
        stateReadable = selection.readable;
        if (selection.member) {
          value = optionLabelOf(selection.member) || selection.member.value || "true";
          valueLabel = value;
          valueEvidence = selection.evidence;
        }
      } else if (fieldType === "checkbox") {
        const state = selectionState(control);
        stateReadable = Boolean(state.channel && state.channel !== "class");
        if (state.selected === true) {
          value = control.value || optionLabel || "true";
          valueLabel = optionLabel || value;
          valueEvidence = state.channel;
        }
      } else if (fieldType === "select" && tag === "select") {
        value = control.value;
        valueLabel = control.selectedOptions?.[0]?.textContent?.trim() || "";
        valueEvidence = "native";
      } else if (fieldType === "select") {
        value = control.value || customValue;
        valueLabel = customValue;
        valueEvidence = customValue || control.value ? "displayed" : "";
      } else {
        value = control.value || customValue;
        valueLabel = value;
        valueEvidence = "native";
      }

      const fingerprintBase = [
        fieldType,
        normalizeText(groupedQuestion || label),
        fieldType === "checkbox" ? normalizeText(optionLabel) : "",
        ["radio", "checkbox", "select"].includes(fieldType)
          ? options.map((option) => normalizeText(option.label || option.value)).sort().join("|")
          : "",
        /^ap-\d+$/.test(control.name || "") ? "" : normalizeText(control.name || ""),
      ].join("::");
      const occurrence = fingerprintCounts.get(fingerprintBase) || 0;
      fingerprintCounts.set(fingerprintBase, occurrence + 1);
      const fingerprint = occurrence ? `${fingerprintBase}#${occurrence + 1}` : fingerprintBase;
      control.dataset.applypilotFingerprint = fingerprint;

      records.push({
        control,
        groupControls: radioGroupControls,
        field: {
          id: applypilotId,
          label: cleanText(label || fallbackLabel || `Unlabeled ${fieldType} field`),
          group_label: groupedQuestion,
          option_label: fieldType === "checkbox" ? optionLabel : "",
          name: control.name || "",
          field_type: fieldType,
          required: control.required || control.getAttribute("aria-required") === "true" || radioRequired || requiredHint,
          value,
          value_label: valueLabel,
          value_evidence: valueEvidence,
          state_readable: stateReadable,
          fingerprint,
          options,
        },
      });
    }
    return records;
  };

  const records = discover();
  if (!fillMode) return { fields: records.map((record) => record.field) };

  const resolveByFingerprint = (fingerprint) => (
    fingerprint ? discover().find((record) => record.field.fingerprint === fingerprint) || null : null
  );

  const findRecord = (action) => {
    const byId = records.find((record) => record.field.id === action.field_id);
    if (byId) {
      const fingerprintOk = !action.fingerprint || byId.field.fingerprint === action.fingerprint;
      const expectedLabel = normalizeText(action.expected_label);
      const expectedType = normalizeText(action.expected_type);
      const expectedOk = (!expectedLabel || expectedLabel === normalizeText(byId.field.label))
        && (!expectedType || expectedType === normalizeText(byId.field.field_type));
      if (fingerprintOk && expectedOk && byId.control.isConnected) return byId;
    }
    return resolveByFingerprint(action.fingerprint);
  };

  const findMember = (groupControls, value) => {
    const target = normalizeText(value);
    const exact = groupControls.find((member) => (
      [member.value, optionLabelOf(member), member.getAttribute("aria-label") || ""]
        .some((text) => normalizeText(text) === target && target)
    ));
    if (exact) return exact;
    const semanticTarget = semanticChoice(value);
    return groupControls.find((member) => (
      [member.value, optionLabelOf(member), member.getAttribute("aria-label") || ""]
        .some((text) => normalizeText(text) && semanticChoice(text) === semanticTarget)
    ));
  };

  const desiredCheckboxState = (value, field) => {
    const normalized = normalizeText(value);
    if (["true", "yes", "1", "on"].includes(normalized)) return true;
    if (["false", "no", "0", "off", ""].includes(normalized)) return false;
    const optionLabel = normalizeText(field.option_label || field.label);
    return Boolean(optionLabel) && (
      optionLabel === normalized || optionLabel.includes(normalized) || normalized.includes(optionLabel)
    );
  };

  const valueMatches = (field, requested) => {
    if (field.field_type === "checkbox") {
      return Boolean(field.value) === desiredCheckboxState(requested, field);
    }
    if (["radio", "select"].includes(field.field_type)) {
      const observedTexts = [field.value, field.value_label].filter(Boolean);
      if (!observedTexts.length) return false;
      const requestedOption = (field.options || []).find((option) => (
        [option.value, option.label].some((text) => (
          normalizeText(text) === normalizeText(requested)
          || (normalizeText(text) && semanticChoice(text) === semanticChoice(requested))
        ))
      ));
      return observedTexts.some((text) => (
        normalizeText(text) === normalizeText(requested)
        || semanticChoice(text) === semanticChoice(requested)
        || (requestedOption && [requestedOption.value, requestedOption.label].some((optionText) => (
          normalizeText(optionText) && normalizeText(optionText) === normalizeText(text)
        )))
      ));
    }
    if (field.field_type === "number") {
      return Number.parseFloat(field.value) === Number.parseFloat(requested);
    }
    const observed = String(field.value || "");
    const target = String(requested || "");
    if (observed.trim() === target.trim()) return true;
    if (normalizeText(observed) && normalizeText(observed) === normalizeText(target)) return true;
    if (field.field_type === "tel") {
      const digits = (text) => text.replace(/\D+/g, "");
      return Boolean(digits(observed)) && digits(observed) === digits(target);
    }
    return false;
  };

  const observeGroupSelection = async (record, desiredLabel, timeoutMs = 1600) => {
    let group = record.groupControls.length ? record.groupControls : [record.control];
    const started = Date.now();
    let selection = groupSelection(group);
    while (Date.now() - started < timeoutMs) {
      if (!group.every((member) => member.isConnected)) {
        const fresh = resolveByFingerprint(record.field.fingerprint);
        if (!fresh) break;
        group = fresh.groupControls.length ? fresh.groupControls : [fresh.control];
      }
      selection = groupSelection(group);
      if (selection.member && normalizeText(optionLabelOf(selection.member)) === desiredLabel) {
        return { ...selection, group };
      }
      await wait(100);
    }
    return { ...selection, group };
  };

  const results = [];
  for (const action of actions) {
    const requested = String(action.value ?? "");
    const result = {
      field_id: action.field_id,
      requested_value: requested,
      status: "failed",
      observed_value: "",
      evidence: "",
      fingerprint: action.fingerprint || "",
      message: "",
    };
    results.push(result);
    const record = findRecord(action);
    if (!record || record.control.disabled) {
      result.message = "The field is no longer available on the page.";
      continue;
    }
    result.fingerprint = record.field.fingerprint;
    const control = record.control;
    const fieldType = record.field.field_type;

    try {
      if (fieldType === "file" || fieldType === "password") {
        result.status = "skipped";
        result.message = fieldType === "file"
          ? "File fields are attached separately."
          : "Password fields are never filled.";
        continue;
      }
      if (fieldType === "radio") {
        const group = record.groupControls.length ? record.groupControls : [control];
        const desired = findMember(group, requested);
        if (!desired) {
          result.message = `No visible option matched "${requested}".`;
          continue;
        }
        const desiredLabel = normalizeText(optionLabelOf(desired));
        const before = groupSelection(group);
        if (before.member && normalizeText(optionLabelOf(before.member)) === desiredLabel) {
          result.status = "verified";
          result.evidence = before.evidence;
          result.observed_value = optionLabelOf(before.member);
          result.message = "Already selected on the page; no click was needed.";
          continue;
        }
        desired.click();
        const observed = await observeGroupSelection(record, desiredLabel);
        if (observed.member && normalizeText(optionLabelOf(observed.member)) === desiredLabel) {
          result.status = "verified";
          result.evidence = observed.evidence;
          result.observed_value = optionLabelOf(observed.member);
        } else if (observed.readable && desired instanceof HTMLInputElement) {
          const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked");
          if (descriptor?.set) descriptor.set.call(desired, true);
          else desired.checked = true;
          dispatch(desired);
          const retried = groupSelection(observed.group);
          if (retried.member && normalizeText(optionLabelOf(retried.member)) === desiredLabel) {
            result.status = "verified";
            result.evidence = retried.evidence;
            result.observed_value = optionLabelOf(retried.member);
          } else {
            result.message = `The page did not accept "${requested}" for this question.`;
          }
        } else if (observed.readable) {
          result.message = observed.member
            ? `The page selected "${optionLabelOf(observed.member)}" instead of "${requested}".`
            : `The page did not mark "${requested}" as selected.`;
        } else {
          result.status = "unverified";
          result.message = "The option was clicked, but this control exposes no page-owned selected state to confirm it.";
        }
        continue;
      }
      if (fieldType === "checkbox") {
        const desired = desiredCheckboxState(requested, record.field);
        const before = selectionState(control);
        const readable = Boolean(before.channel && before.channel !== "class");
        if (readable && before.selected === desired) {
          result.status = "verified";
          result.evidence = before.channel;
          result.observed_value = desired ? (record.field.option_label || "true") : "";
          result.message = "Already in the requested state; no click was needed.";
          continue;
        }
        if (!readable && !desired) {
          result.status = "unverified";
          result.message = "This control exposes no page-owned state, so clearing it could not be confirmed safely.";
          continue;
        }
        control.click();
        const started = Date.now();
        let after = selectionState(control);
        while (Date.now() - started < 1600) {
          if (!control.isConnected) break;
          after = selectionState(control);
          if (after.channel && after.selected === desired) break;
          await wait(100);
        }
        if (after.channel && after.selected === desired) {
          result.status = "verified";
          result.evidence = after.channel;
          result.observed_value = desired ? (record.field.option_label || "true") : "";
          continue;
        }
        if (control instanceof HTMLInputElement) {
          if (control.labels?.[0] && selectionState(control).selected !== desired) control.labels[0].click();
          if (selectionState(control).selected !== desired) {
            const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked");
            if (descriptor?.set) descriptor.set.call(control, desired);
            else control.checked = desired;
            dispatch(control);
          }
          const retried = selectionState(control);
          if (retried.channel && retried.selected === desired) {
            result.status = "verified";
            result.evidence = retried.channel;
            result.observed_value = desired ? (record.field.option_label || "true") : "";
            continue;
          }
        }
        if (after.channel) {
          result.message = `The checkbox did not remain ${desired ? "selected" : "cleared"}.`;
        } else {
          result.status = "unverified";
          result.message = "The control was clicked, but it exposes no page-owned state to confirm the change.";
        }
        continue;
      }
      if (fieldType === "select" && control.tagName === "SELECT") {
        const target = normalizeText(requested);
        const option = [...control.options].find((candidate) => (
          [candidate.value, candidate.textContent].some((text) => {
            const candidateValue = normalizeText(text);
            if (candidateValue === target) return true;
            if (target.length < 3 || candidateValue.length < 3) return false;
            return candidateValue.startsWith(`${target} `) || target.startsWith(`${candidateValue} `);
          })
        ));
        if (!option) {
          result.message = `No dropdown option matched "${requested}".`;
          continue;
        }
        control.value = option.value;
        dispatch(control);
        if (control.value === option.value) {
          result.status = "verified";
          result.evidence = "native";
          result.observed_value = option.textContent.trim();
        } else {
          result.message = `The page rejected the dropdown option "${requested}".`;
        }
        continue;
      }
      if (fieldType === "select") {
        if (control.tagName === "INPUT") {
          control.click();
          const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(control), "value");
          if (descriptor?.set) descriptor.set.call(control, requested);
          else control.value = requested;
          dispatch(control);
        } else {
          control.click();
        }
        const target = normalizeText(requested);
        let option = null;
        for (let attempt = 0; attempt < 10 && !option; attempt += 1) {
          await wait(100);
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
            : "[role='option'], [data-value], [data-radix-collection-item], [data-slot='select-item'], [class*='option'], li";
          const candidates = (popupRoots.length
            ? popupRoots.flatMap((popup) => [...popup.querySelectorAll(selector)])
            : [...document.querySelectorAll(selector)]
          ).filter((candidate) => {
            const style = getComputedStyle(candidate);
            const rect = candidate.getBoundingClientRect();
            return style.display !== "none" && style.visibility !== "hidden" && rect.height > 0;
          });
          option = candidates.find((candidate) =>
            [candidate.textContent, candidate.getAttribute("data-value"), candidate.getAttribute("value")]
              .filter(Boolean)
              .some((text) => {
                const optionValue = normalizeText(text);
                if (optionValue === target) return true;
                if (/^\d{1,3}$/.test(target) && optionValue.split(" ").includes(target)) return true;
                if (target.length < 3 || optionValue.length < 3) return false;
                return optionValue.startsWith(`${target} `) || target.startsWith(`${optionValue} `);
              }),
          );
        }
        if (!option) {
          result.message = `No dropdown option matched "${requested}".`;
          continue;
        }
        option.click();
        await wait(150);
        const displayed = cleanText(
          control.getAttribute("aria-valuetext") || control.getAttribute("data-value")
          || control.value || control.textContent,
        );
        if (normalizeText(displayed) && (
          normalizeText(displayed) === target
          || normalizeText(displayed).startsWith(`${target} `)
          || target.startsWith(`${normalizeText(displayed)} `)
        )) {
          result.status = "verified";
          result.evidence = "displayed";
          result.observed_value = displayed;
        } else {
          result.status = "unverified";
          result.observed_value = displayed;
          result.message = "The option was clicked, but the displayed value could not be confirmed yet.";
        }
        continue;
      }
      // Text-like inputs and textareas.
      const prototype = Object.getPrototypeOf(control);
      const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
      if (descriptor?.set) descriptor.set.call(control, requested);
      else control.value = requested;
      dispatch(control);
      if (String(control.value) === requested) {
        result.status = "verified";
        result.evidence = "native";
        result.observed_value = control.value;
      } else {
        result.observed_value = String(control.value || "");
        result.message = `The page changed the entered value to "${result.observed_value}".`;
        result.status = result.observed_value ? "unverified" : "failed";
      }
    } catch (error) {
      result.status = "failed";
      result.message = error.message;
    }
  }

  // Authoritative post-action verification: rescan the live page and compare
  // page-owned state against every requested value. A click that the page
  // ignored is downgraded here no matter what the executor observed.
  await wait(200);
  const freshRecords = discover();
  for (const result of results) {
    if (result.status === "skipped" || !result.fingerprint) continue;
    const fresh = freshRecords.find((record) => record.field.fingerprint === result.fingerprint);
    if (!fresh) {
      if (result.status === "verified") {
        result.status = "unverified";
        result.message = "The field was replaced after the action, so the result could not be re-confirmed.";
      }
      continue;
    }
    const field = fresh.field;
    const readable = ["checkbox", "radio"].includes(field.field_type)
      ? field.state_readable || Boolean(field.value_evidence)
      : true;
    if (!readable) {
      if (result.status !== "failed") {
        result.status = "unverified";
        if (!result.message) {
          result.message = "This control exposes no page-owned selected state, so the change could not be confirmed.";
        }
      }
      continue;
    }
    result.observed_value = field.value_label || field.value;
    result.evidence = field.value_evidence || result.evidence;
    if (valueMatches(field, result.requested_value)) {
      result.status = "verified";
      if (!result.message) result.message = "Confirmed by a fresh page scan.";
    } else if (["checkbox", "radio", "select"].includes(field.field_type)) {
      result.status = "failed";
      result.message = `A fresh scan shows "${result.observed_value || "no selection"}" instead of "${result.requested_value}".`;
    } else if (!String(field.value || "").trim()) {
      result.status = "failed";
      result.message = "A fresh scan shows the field is still empty.";
    } else if (result.status === "verified") {
      result.status = "unverified";
      result.message = `A fresh scan shows "${result.observed_value}", which differs from the requested value.`;
    }
  }

  const filledIds = results.filter((result) => result.status === "verified").map((result) => result.field_id);
  const errors = results
    .filter((result) => result.status === "failed")
    .map((result) => ({ field_id: result.field_id, message: result.message }));
  return {
    filled: filledIds.length,
    filled_ids: filledIds,
    errors,
    results,
    fields: freshRecords.map((record) => record.field),
    submit_clicked: false,
  };
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
    element.textContent || element.value || element.getAttribute("aria-label") || element.getAttribute("title") || "",
  ).replace(/\s+/g, " ").trim().toLowerCase();
  const roots = [document];
  for (let index = 0; index < roots.length; index += 1) {
    [...roots[index].querySelectorAll("*")].forEach((element) => {
      if (element.shadowRoot && !roots.includes(element.shadowRoot)) roots.push(element.shadowRoot);
    });
  }
  const queryAll = (selector) => roots.flatMap((root) => [...root.querySelectorAll(selector)]);
  const primaryLabel = (label) => (
    label === "apply"
    || label === "apply now"
    || label === "apply for this job"
    || label === "apply for this position"
    || /^apply to .+/.test(label)
    || label.includes("company website")
  );
  const preferred = queryAll(
    "button.jobs-apply-button, a.jobs-apply-button, [role='button'].jobs-apply-button, button[data-testid*='apply' i], a[data-testid*='apply' i], button[data-cy*='apply' i], a[data-cy*='apply' i], input[type='button'][value*='apply' i], input[type='submit'][value*='apply' i]",
  ).filter((element) => {
    const label = labelOf(element);
    return visible(element) && !element.disabled && primaryLabel(label)
      && !label.includes("easy apply") && !label.includes("quick apply");
  });
  const fallback = queryAll(
    "button, a[href], [role='button'], input[type='button'], input[type='submit']",
  ).filter((element) => {
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

function clickApplicationEntry(inspectOnly = false) {
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
  const roots = [document];
  for (let index = 0; index < roots.length; index += 1) {
    [...roots[index].querySelectorAll("*")].forEach((element) => {
      if (element.shadowRoot && !roots.includes(element.shadowRoot)) roots.push(element.shadowRoot);
    });
  }
  const queryAll = (selector) => roots.flatMap((root) => [...root.querySelectorAll(selector)]);
  const labelsOf = (element) => [...new Set([
    element.innerText,
    element.textContent,
    element.value,
    element.getAttribute("aria-label"),
    element.getAttribute("title"),
  ].filter(Boolean).map((value) => String(value).replace(/\s+/g, " ").trim().toLowerCase()))];
  const labelOf = (element) => labelsOf(element)[0] || "";
  const formControls = queryAll("input, textarea, select, [role='combobox']").filter((control) => {
    const type = (control.type || "").toLowerCase();
    return visible(control) && !["hidden", "submit", "button", "reset", "search"].includes(type);
  });
  const applicationSignal = (control) => String([
    control.name,
    control.id,
    control.getAttribute("aria-label"),
    control.getAttribute("placeholder"),
    control.getAttribute("autocomplete"),
    control.labels?.[0]?.textContent,
  ].filter(Boolean).join(" ")).toLowerCase();
  const signalPatterns = [
    /(?:full|first|last|preferred)\s*name|\bname\b/,
    /e-?mail/,
    /phone|mobile/,
    /resume|r[eé]sum[eé]|curriculum|\bcv\b/,
    /cover\s*letter/,
    /linkedin|github|portfolio/,
    /work\s*authorization|sponsor|visa/,
  ];
  const applicationSignalCount = (controls) => signalPatterns.filter(
    (pattern) => controls.some((control) => pattern.test(applicationSignal(control))),
  ).length;
  const applicationSurface = applicationSignalCount(formControls) >= 2
    || (formControls.some((control) => (control.type || "").toLowerCase() === "file") && formControls.length >= 2);
  const applicationEntryLabel = (element) => labelsOf(element).some((label) => (
    /^apply$|^apply\s+now\b|^apply\s+for\s+(?:this|the)\s+(?:job|position)\b/.test(label)
    || /^(?:start|continue)\s+(?:the\s+)?application\b/.test(label)
  ));
  const rawCandidates = queryAll(
    "a, button, [role='button'], input[type='button'], input[type='submit']",
  ).filter((element) => {
    if (!visible(element) || element.disabled || element.getAttribute("aria-disabled") === "true") return false;
    return applicationEntryLabel(element);
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
    const normalized = candidates.map(labelOf);
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
    const candidateForm = candidates[0].closest("form");
    const candidateFormControls = candidateForm
      ? formControls.filter((control) => candidateForm.contains(control))
      : [];
    if (candidateFormControls.length >= 2 && applicationSignalCount(candidateFormControls) >= 2) {
      return { clicked: false, already_form: true };
    }
    if (inspectOnly) {
      return { clicked: false, clickable: true, label: labelOf(candidates[0]) || "Apply" };
    }
    candidates[0].click();
    return { clicked: true, label: labelOf(candidates[0]) || "Apply" };
  }
  if (candidates.length > 1) {
    return {
      clicked: false,
      error: "Multiple Apply buttons were found; choose the correct one.",
    };
  }
  if (applicationSurface) return { clicked: false, already_form: true };
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
  const roots = [document];
  for (let index = 0; index < roots.length; index += 1) {
    [...roots[index].querySelectorAll("*")].forEach((element) => {
      if (element.shadowRoot && !roots.includes(element.shadowRoot)) roots.push(element.shadowRoot);
    });
  }
  const control = roots
    .map((root) => root.querySelector(`[data-applypilot-id="${CSS.escape(fieldId)}"]`))
    .find(Boolean);
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

function applyFileToInput(fieldId, base64, filename, mediaType) {
  const roots = [document];
  for (let index = 0; index < roots.length; index += 1) {
    [...roots[index].querySelectorAll("*")].forEach((element) => {
      if (element.shadowRoot && !roots.includes(element.shadowRoot)) roots.push(element.shadowRoot);
    });
  }
  const input = roots
    .map((root) => root.querySelector(`[data-applypilot-id="${CSS.escape(fieldId)}"]`))
    .find(Boolean);
  if (!input || input.type !== "file") {
    return { attached: false, error: "The file upload field is no longer available." };
  }
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const file = new File(
    [bytes],
    filename,
    { type: mediaType || "application/octet-stream" },
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
