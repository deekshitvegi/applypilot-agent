/*
 * The only thing in this extension that touches a page.
 *
 * The side panel never reaches into a tab and never runs script of its own. It
 * sends a message here; this file injects the functions in injected/ and calls
 * one of them by name. Keeping that boundary in one file is what makes it
 * possible to say, honestly, where every read and every click came from.
 */

//: What act.js says when a fingerprint resolves to nothing. Asking every frame
//: means most of them will say this about most controls, and those are not
//: results anybody wants reported.
const NO_CONTROL = "the control is no longer on the page";

const INJECTED = [
  // First: the panel loads this too, so that what counts as a control's own
  // "Choose one" row is one list rather than three that drift apart.
  "placeholders.js",
  "injected/dom.js",
  "injected/surface.js",
  "injected/verify.js",
  "injected/scan.js",
  "injected/act.js",
];

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
});

/**
 * Put the injected functions into a tab, once.
 *
 * Each file guards itself, but executeScript still fetches and evaluates all
 * five every time it is called -- and it was being called before every single
 * action. Filling one field carried the cost of loading the whole toolkit, and
 * a form took minutes instead of seconds.
 */
const injectedTabs = new Map();

function forgetTab(tabId) {
  injectedTabs.delete(tabId);
}

chrome.tabs.onUpdated.addListener((tabId, info) => {
  if (info.status === "loading") forgetTab(tabId);
});
chrome.tabs.onRemoved.addListener(forgetTab);

async function ensureInjected(tabId, allFrames) {
  const key = allFrames ? "all" : "top";
  const done = injectedTabs.get(tabId);
  if (done && done.has(key)) return;
  await chrome.scripting.executeScript({
    target: { tabId: tabId, allFrames: Boolean(allFrames) },
    files: INJECTED,
  });
  const set = done || new Set();
  set.add(key);
  // Injecting into every frame covers the top one too.
  if (allFrames) set.add("top");
  injectedTabs.set(tabId, set);
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

/**
 * Run one injected function in the frame the control actually lives in.
 *
 * Applications are very often inside a frame. Acting only on the top frame
 * meant every one of those fields came back as "no longer on the page", or
 * worse, matched something else that happened to be up there.
 */
async function callInFrame(tabId, frameId, expression, args) {
  const target = { tabId: tabId };
  if (frameId !== undefined && frameId !== null && frameId !== "") {
    target.frameIds = [Number(frameId)];
  }
  await ensureInjected(tabId, target.frameIds ? true : false);
  const [entry] = await chrome.scripting.executeScript({
    target: target,
    func: runNamed,
    args: [expression, args || []],
  });
  if (!entry || !entry.result) return null;
  if (!entry.result.ok) throw new Error(entry.result.error);
  return entry.result.value;
}

/**
 * Try every frame and take the first that succeeds.
 *
 * For controls named by their text rather than by a fingerprint, where which
 * frame holds them is not known in advance.
 */
async function callAnywhere(tabId, expression, args, accept) {
  const results = await callInFrames(tabId, expression, args);
  for (const entry of results) {
    if (!accept || accept(entry.value)) return entry.value;
  }
  return results.length ? results[0].value : null;
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
    // The frame holding the fields decides what the page is. Only "application"
    // used to count, so a form inside a frame that called itself a registration
    // -- which is what a page asking you to make an account is -- had its
    // verdict thrown away, and the empty top frame's "unknown" stood instead.
    // Thirty-three fields were then read as an unrecognised page and skipped.
    if (
      entry.frameId !== top.frameId &&
      entry.value.kind !== "unknown" &&
      (merged.kind === "unknown" || entry.value.kind === "application")
    ) {
      merged.kind = entry.value.kind;
      merged.notes.push(`the ${entry.value.kind} is inside a frame on this page`);
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
const HANDLERS = {
  async scan(message) {
    return scanTab(message.tabId);
  },
  async visible(message) {
    // Read from the page itself: a tab can be "active" in a window that is not
    // on screen, and it is the rendering that matters.
    try {
      return await callInFrame(message.tabId, 0, "act.pageIsVisible", []);
    } catch (err) {
      return true;
    }
  },
  async shape(message) {
    // A cheap "has anything moved?" for the watcher. Scanning every frame of a
    // large application every couple of seconds, forever, was the panel making
    // the page slow just by being open.
    const parts = await callInFrames(message.tabId, "act.pageShape");
    return parts.map((entry) => entry.value).join("~");
  },
  async perform(message) {
    return callInFrame(message.tabId, message.frameId, "act.perform", [message.action]);
  },
  /**
   * A page's worth of actions, one trip per frame.
   *
   * Grouped by frame because an action still has to run where its control
   * actually lives, and kept in the planned order within each frame.
   */
  async performMany(message) {
    const byFrame = new Map();
    for (const action of message.actions || []) {
      const raw = action.frame === undefined || action.frame === "" ? 0 : Number(action.frame);
      // A frame this cannot be a number for is not a frame to aim at. Sending
      // NaN to executeScript is a thrown error, and a thrown error here used to
      // take the whole page's work with it.
      const frame = Number.isFinite(raw) ? raw : 0;
      if (!byFrame.has(frame)) byFrame.set(frame, []);
      byFrame.get(frame).push(action);
    }

    const results = [];
    const failures = [];
    for (const [frame, actions] of byFrame) {
      try {
        const done = await callInFrame(message.tabId, frame, "act.performMany", [actions]);
        if (Array.isArray(done)) results.push(...done);
        continue;
      } catch (err) {
        failures.push(`frame ${frame}: ${(err && err.message) || err}`);
      }

      // The frame went away between planning and acting -- an application that
      // rebuilds itself does this, and its id does not survive. The controls
      // are still somewhere, so ask every frame: a fingerprint only resolves
      // where its control actually is, so nothing can land in the wrong place.
      try {
        const perFrame = await callInFrames(message.tabId, "act.performMany", [actions]);
        for (const entry of perFrame) {
          if (Array.isArray(entry.value)) {
            results.push(...entry.value.filter((r) => r && r.evidence !== NO_CONTROL));
          }
        }
      } catch (err) {
        failures.push(`retry: ${(err && err.message) || err}`);
      }
    }

    // One frame failing is not the page failing. Whatever did land is reported
    // either way, because a run that says nothing at all is indistinguishable
    // from one that was never started -- which is exactly how twenty-two fields
    // with answers ready came to sit under "ready to fill" after a fill.
    if (failures.length && !results.length) {
      throw new Error(failures.join("; "));
    }
    return results;
  },
  async openOptions(message) {
    return callInFrame(message.tabId, message.frameId, "act.openOptions", [
      message.fingerprint,
      message.filter || "",
    ]);
  },
  async addRepeat(message) {
    return callAnywhere(
      message.tabId,
      "act.addRepeat",
      [message.text || ""],
      (value) => value && value.outcome === "verified"
    );
  },
  async click(message) {
    return callAnywhere(
      message.tabId,
      "act.clickByText",
      [message.text],
      (value) => value && value.outcome !== "failed"
    );
  },
  async highlight(message) {
    return callInFrame(message.tabId, message.frameId, "act.highlight", [message.fingerprint]);
  },
  async signInSettled(message) {
    return callInFrame(message.tabId, 0, "act.signInSettled", [message.timeout || 8000]);
  },
  async confirmation(message) {
    return callAnywhere(message.tabId, "scan.confirmationText", [], (value) => Boolean(value));
  },
  async attach(message) {
    // The bytes are fetched here, where the origin is the extension's own, and
    // handed to the page as a File. The page never gets a way to reach the
    // local service itself.
    return callInFrame(message.tabId, message.frameId, "act.attachFile", [
      message.fingerprint,
      message.base64,
      message.filename,
      message.mime,
    ]);
  },
  /**
   * A picture of the page as it looked when something went wrong.
   *
   * Only the visible part of the tab that is already on screen, taken when
   * somebody presses "Report a problem" -- never in the background and never
   * on a schedule. It goes into a file on their own machine.
   */
  async screenshot(message) {
    try {
      const tab = await chrome.tabs.get(message.tabId);
      return await chrome.tabs.captureVisibleTab(tab.windowId, {
        format: "jpeg",
        quality: 60,
      });
    } catch (err) {
      // A screenshot is a nicety. A report without one is still a report.
      return "";
    }
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
