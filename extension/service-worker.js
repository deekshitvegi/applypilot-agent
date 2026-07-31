/*
 * The only thing in this extension that touches a page.
 *
 * The side panel never reaches into a tab and never runs script of its own. It
 * sends a message here; this file injects the functions in injected/ and calls
 * one of them by name. Keeping that boundary in one file is what makes it
 * possible to say, honestly, where every read and every click came from.
 */

const INJECTED = [
  "injected/dom.js",
  "injected/surface.js",
  "injected/verify.js",
  "injected/scan.js",
  "injected/act.js",
];

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
});

/** Put the injected functions into a tab. Idempotent: each file guards itself. */
async function ensureInjected(tabId, allFrames) {
  await chrome.scripting.executeScript({
    target: { tabId: tabId, allFrames: Boolean(allFrames) },
    files: INJECTED,
  });
}

async function callInFrames(tabId, expression, args) {
  await ensureInjected(tabId, true);
  const results = await chrome.scripting.executeScript({
    target: { tabId: tabId, allFrames: true },
    func: runNamed,
    args: [expression, args || []],
  });
  return results
    .filter((entry) => entry && entry.result && entry.result.ok)
    .map((entry) => ({ frameId: entry.frameId, value: entry.result.value }));
}

async function callInTop(tabId, expression, args) {
  await ensureInjected(tabId, false);
  const [entry] = await chrome.scripting.executeScript({
    target: { tabId: tabId },
    func: runNamed,
    args: [expression, args || []],
  });
  if (!entry || !entry.result) return null;
  if (!entry.result.ok) throw new Error(entry.result.error);
  return entry.result.value;
}

/**
 * Runs inside the page's isolated world.
 *
 * Only names from the ApplyPilot namespace can be reached: the panel cannot ask
 * for arbitrary code to run in a tab.
 */
async function runNamed(path, args) {
  try {
    const parts = String(path).split(".");
    let target = globalThis.ApplyPilot;
    for (const part of parts) {
      if (!target) break;
      target = target[part];
    }
    if (typeof target !== "function") {
      return { ok: false, error: "no such injected function: " + path };
    }
    const value = await target.apply(null, args || []);
    return { ok: true, value: value };
  } catch (err) {
    return { ok: false, error: String((err && err.message) || err) };
  }
}

/**
 * A scan of every frame, merged.
 *
 * The top frame decides what kind of page this is; a child frame that holds an
 * application (an embedded ATS is the usual reason) contributes its fields.
 */
async function scanTab(tabId) {
  const perFrame = await callInFrames(tabId, "scan.run");
  if (!perFrame.length) return null;

  const top = perFrame.find((entry) => entry.frameId === 0) || perFrame[0];
  const merged = Object.assign({}, top.value);
  merged.fields = [];
  merged.notes = (top.value.notes || []).slice();

  const framesWithFields = perFrame.filter((entry) => (entry.value.fields || []).length);
  for (const entry of framesWithFields) {
    for (const field of entry.value.fields) {
      field.frame = String(entry.frameId);
      merged.fields.push(field);
    }
    if (entry.frameId !== top.frameId && entry.value.kind === "application") {
      merged.kind = "application";
      merged.notes.push("the application is inside a frame on this page");
    }
  }

  for (const key of ["apply_controls", "submit_controls", "next_controls", "add_controls"]) {
    merged[key] = perFrame.flatMap((entry) => entry.value[key] || []);
  }
  merged.captcha = perFrame.some((entry) => entry.value.captcha === "challenge")
    ? "challenge"
    : perFrame.some((entry) => entry.value.captcha === "badge_only")
      ? "badge_only"
      : "none";
  merged.hints = Array.from(new Set(perFrame.flatMap((entry) => entry.value.hints || [])));
  merged.signature = perFrame.map((entry) => entry.value.signature).join("|");
  return merged;
}

/**
 * Attach a document to a file input.
 *
 * The bytes are fetched here, where the origin is the extension's own, and
 * handed to the page as a File. The page is never given a way to reach the
 * local service itself.
 */
async function attachDocument(tabId, fingerprint, base64, filename, mime) {
  return callInTop(tabId, "act.attachFile", [fingerprint, base64, filename, mime]);
}

const HANDLERS = {
  async scan(message) {
    return scanTab(message.tabId);
  },
  async perform(message) {
    return callInTop(message.tabId, "act.perform", [message.action]);
  },
  async openOptions(message) {
    return callInTop(message.tabId, "act.openOptions", [message.fingerprint, message.filter || ""]);
  },
  async addRepeat(message) {
    return callInTop(message.tabId, "act.addRepeat", [message.text || ""]);
  },
  async click(message) {
    return callInTop(message.tabId, "act.clickByText", [message.text]);
  },
  async highlight(message) {
    return callInTop(message.tabId, "act.highlight", [message.fingerprint]);
  },
  async signInSettled(message) {
    return callInTop(message.tabId, "act.signInSettled", [message.timeout || 8000]);
  },
  async confirmation(message) {
    return callInTop(message.tabId, "scan.confirmationText", []);
  },
  async attach(message) {
    return attachDocument(
      message.tabId,
      message.fingerprint,
      message.base64,
      message.filename,
      message.mime
    );
  },
  async navigate(message) {
    await chrome.tabs.update(message.tabId, { url: message.url });
    return { ok: true };
  },
  async activeTab() {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    return tab ? { id: tab.id, url: tab.url, title: tab.title } : null;
  },
};

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const handler = HANDLERS[message && message.type];
  if (!handler) {
    sendResponse({ ok: false, error: "unknown request: " + (message && message.type) });
    return false;
  }
  handler(message)
    .then((value) => sendResponse({ ok: true, value: value }))
    .catch((err) => sendResponse({ ok: false, error: String((err && err.message) || err) }));
  return true;
});
