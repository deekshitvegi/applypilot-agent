/*
 * Which theme to draw in.
 *
 * Kept in the browser's own storage rather than the profile: it is a display
 * preference, nothing about the applicant, and both the panel and the settings
 * page need it before either has spoken to the service. Applied as an attribute
 * on the root element, which the stylesheets read; with nothing saved, the
 * browser's own setting decides, exactly as before.
 */

const THEME_KEY = "theme";

function paintTheme(choice) {
  const root = document.documentElement;
  if (choice === "light" || choice === "dark") root.setAttribute("data-theme", choice);
  else root.removeAttribute("data-theme");
}

async function loadTheme() {
  try {
    const saved = await chrome.storage.local.get(THEME_KEY);
    const choice = saved[THEME_KEY] || "system";
    paintTheme(choice);
    return choice;
  } catch (err) {
    paintTheme("system");
    return "system";
  }
}

async function saveTheme(choice) {
  paintTheme(choice);
  try {
    await chrome.storage.local.set({ [THEME_KEY]: choice });
  } catch (err) {
    /* the preference simply does not persist */
  }
}

// A change made in Settings reaches the panel without either being reopened.
try {
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes[THEME_KEY]) paintTheme(changes[THEME_KEY].newValue);
  });
} catch (err) {
  /* not in an extension page */
}

loadTheme();
