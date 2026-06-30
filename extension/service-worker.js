chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action !== "captureJob") return false;

  captureActiveJob()
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
