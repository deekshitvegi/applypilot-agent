/*
 * Settings, in plain language.
 *
 * Everything here reads and writes the local service. The key, once saved, is
 * never read back out -- the page only ever learns whether one is set.
 */

const SERVICE = "http://127.0.0.1:8765";
const el = (id) => document.getElementById(id);

/* The answers worth showing as a simple grid, with the wording the panel uses. */
const FACT_FIELDS = [
  ["full_name", "Full legal name"],
  ["first_name", "First name"],
  ["middle_name", "Middle name"],
  ["last_name", "Last name"],
  ["preferred_name", "Preferred name"],
  ["email", "Email address"],
  ["phone", "Phone number"],
  ["street_address", "Street address"],
  ["address_line_2", "Apartment, suite or unit"],
  ["city", "City"],
  ["state", "State or province"],
  ["postal_code", "ZIP or postal code"],
  ["country", "Country"],
  ["linkedin", "LinkedIn URL"],
  ["github", "GitHub URL"],
  ["website", "Website or portfolio"],
  ["work_authorization", "Legally authorised to work"],
  ["requires_sponsorship", "Will require visa sponsorship"],
  ["citizenship", "Citizenship status"],
  ["over_18", "18 or older"],
  ["background_check_consent", "Consents to a background check"],
  ["willing_to_relocate", "Willing to relocate"],
  ["notice_period", "Notice period or start date"],
  ["salary_expectation", "Salary expectation"],
  ["gender", "Gender (voluntary)"],
  ["race_ethnicity", "Race / ethnicity (voluntary)"],
  ["veteran_status", "Veteran status (voluntary)"],
  ["disability_status", "Disability status (voluntary)"],
];

const EDUCATION_FIELDS = [
  ["school", "School"],
  ["degree", "Degree"],
  ["field_of_study", "Field of study"],
  ["start_date", "Start"],
  ["end_date", "End"],
  ["location", "Location"],
  ["gpa", "GPA"],
];

const EXPERIENCE_FIELDS = [
  ["company", "Company"],
  ["title", "Title"],
  ["location", "Location"],
  ["start_date", "Start"],
  ["end_date", "End"],
];

let profile = null;

async function service(path, options) {
  const response = await fetch(SERVICE + path, Object.assign({ method: "GET" }, options));
  if (!response.ok) throw new Error((await response.text()) || response.statusText);
  const type = response.headers.get("content-type") || "";
  return type.includes("json") ? response.json() : response.text();
}

const send = (method, path, body) =>
  service(path, {
    method: method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body || {}),
  });

function longField(label, value, onInput) {
  const wrap = document.createElement("div");
  wrap.className = "wide";
  const name = document.createElement("label");
  name.textContent = label;
  const box = document.createElement("textarea");
  box.rows = 5;
  box.value = value || "";
  box.addEventListener("input", () => onInput(box.value));
  wrap.appendChild(name);
  wrap.appendChild(box);
  return wrap;
}

function textField(label, value, onInput) {
  const wrap = document.createElement("div");
  const name = document.createElement("label");
  name.textContent = label;
  const input = document.createElement("input");
  input.type = "text";
  input.value = value || "";
  input.addEventListener("input", () => onInput(input.value));
  wrap.appendChild(name);
  wrap.appendChild(input);
  return wrap;
}

function renderFacts() {
  const host = el("facts");
  host.innerHTML = "";
  for (const [key, label] of FACT_FIELDS) {
    host.appendChild(
      textField(label, profile.facts[key] || "", (value) => {
        profile.facts[key] = value;
      })
    );
  }
}

function renderRecords(hostId, records, fields, extras) {
  const host = el(hostId);
  host.innerHTML = "";
  records.forEach((record, index) => {
    const card = document.createElement("div");
    card.className = "record";

    const remove = document.createElement("button");
    remove.className = "ghost remove";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      records.splice(index, 1);
      renderRecords(hostId, records, fields, extras);
    });
    card.appendChild(remove);

    const grid = document.createElement("div");
    grid.className = "grid";
    for (const [key, label] of fields) {
      grid.appendChild(
        textField(label, record[key], (value) => {
          record[key] = value;
        })
      );
    }
    card.appendChild(grid);

    if (extras && extras.description) {
      // Read out of the resume and kept: it is what a tailored resume reorders,
      // and there was no way to see or correct it.
      card.appendChild(
        longField("What you did here — one bullet point per line", record.description, (value) => {
          record.description = value;
        })
      );
    }

    if (extras && extras.current) {
      const check = document.createElement("label");
      check.className = "check";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = Boolean(record.current);
      box.addEventListener("change", () => {
        record.current = box.checked;
      });
      check.appendChild(box);
      check.appendChild(document.createTextNode(" I currently work here"));
      card.appendChild(check);
    }
    host.appendChild(card);
  });
}

async function refresh() {
  try {
    const health = await service("/health");
    el("health").textContent =
      `Service ${health.version} · data in ${health.data_dir} · key ${health.key_fingerprint}`;
  } catch (err) {
    el("health").textContent =
      "The local service is not running. Start it with scripts\\start.ps1.";
    return;
  }

  const settings = await service("/settings");
  el("key-state").textContent = settings.model_configured
    ? "A key is saved. Type a new one to replace it."
    : "No key saved yet.";
  el("submission").value = settings.submission_policy;
  el("easy-apply").checked = settings.prefer_easy_apply;
  el("demographics").checked = settings.answer_demographics;
  el("auto-attach").checked = settings.auto_attach_resume !== false;

  profile = await service("/profile");
  renderFacts();
  renderRecords("education", profile.education, EDUCATION_FIELDS);
  renderRecords("experience", profile.experience, EXPERIENCE_FIELDS, {
    current: true,
    description: true,
  });

  const learned = await service("/learned");
  const learnedBody = el("learned").querySelector("tbody");
  learnedBody.innerHTML = "";
  for (const answer of learned.answers) {
    const row = document.createElement("tr");
    const question = document.createElement("td");
    question.textContent = answer.question;
    const value = document.createElement("td");
    value.textContent = answer.value;
    const actions = document.createElement("td");
    actions.className = "actions";
    const forget = document.createElement("button");
    forget.className = "ghost";
    forget.textContent = "Forget";
    forget.addEventListener("click", async () => {
      await service("/learned?question=" + encodeURIComponent(answer.question), {
        method: "DELETE",
      });
      refresh();
    });
    actions.appendChild(forget);
    row.append(question, value, actions);
    learnedBody.appendChild(row);
  }
  if (!learned.answers.length) {
    learnedBody.innerHTML = '<tr><td class="muted">Nothing learned yet.</td></tr>';
  }

  const applications = await service("/applications");
  const appBody = el("applications").querySelector("tbody");
  appBody.innerHTML = "";
  for (const record of applications.applications) {
    const row = document.createElement("tr");
    const who = document.createElement("td");
    who.textContent = `${record.company || "(unknown)"} — ${record.role || ""}`;
    const status = document.createElement("td");
    status.textContent = record.status;
    const when = document.createElement("td");
    when.textContent = record.applied_on || "";
    row.append(who, status, when);
    appBody.appendChild(row);
  }
  if (!applications.applications.length) {
    appBody.innerHTML = '<tr><td class="muted">Nothing tracked yet.</td></tr>';
  }
}

/** Both imports behave the same way: read the file, report what came out. */
async function importFrom(path, inputId, resultId) {
  const input = el(inputId);
  const file = input.files[0];
  if (!file) return;
  el(resultId).textContent = "Reading…";
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetch(SERVICE + path, { method: "POST", body: form });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "that file could not be read");
    const parts = [
      `${body.education.length} education`,
      `${body.experience.length} work entries`,
      `${body.skills.length} skills`,
    ];
    el(resultId).textContent =
      "Read " + parts.join(", ") + ". Check them below." +
      (body.notes.length ? " " + body.notes.join(" ") : "");
    refresh();
  } catch (err) {
    el(resultId).textContent = String(err.message);
  } finally {
    input.value = "";
  }
}

el("linkedin-file").addEventListener("change", () =>
  importFrom("/import/linkedin", "linkedin-file", "linkedin-result")
);

el("resume-file").addEventListener("change", () =>
  importFrom("/resume", "resume-file", "resume-result")
);

el("save-key").addEventListener("click", async () => {
  const key = el("api-key").value.trim();
  if (!key) return;
  await send("PUT", "/settings", { model_api_key: key });
  el("api-key").value = "";
  refresh();
});

el("save-behaviour").addEventListener("click", async () => {
  await send("PUT", "/settings", {
    submission_policy: el("submission").value,
    prefer_easy_apply: el("easy-apply").checked,
    auto_attach_resume: el("auto-attach").checked,
    answer_demographics: el("demographics").checked,
  });
  refresh();
});

/** Every Save button writes the whole profile; only the wording differs. */
async function saveProfile(noteId) {
  await send("PUT", "/profile", profile);
  if (noteId) {
    el(noteId).textContent = "Saved.";
    setTimeout(() => {
      el(noteId).textContent = "";
    }, 2000);
  }
  refresh();
}

el("save-facts").addEventListener("click", () => saveProfile("facts-saved"));
el("save-education").addEventListener("click", () => saveProfile("education-saved"));
el("save-experience").addEventListener("click", () => saveProfile("experience-saved"));

el("add-education").addEventListener("click", () => {
  profile.education.push({ school: "", degree: "", field_of_study: "" });
  renderRecords("education", profile.education, EDUCATION_FIELDS);
});

el("add-experience").addEventListener("click", () => {
  profile.experience.push({ company: "", title: "", current: false, description: "" });
  renderRecords("experience", profile.experience, EXPERIENCE_FIELDS, {
    current: true,
    description: true,
  });
});

el("forget-all").addEventListener("click", async () => {
  await service("/learned", { method: "DELETE" });
  refresh();
});

el("export").addEventListener("click", async () => {
  const csv = await service("/applications/export");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "applypilot-applications.csv";
  link.click();
  URL.revokeObjectURL(url);
});

el("reset").addEventListener("click", async () => {
  if (!confirm("Erase your profile, saved answers, documents and history from this computer?")) {
    return;
  }
  await send("POST", "/reset", { confirm: "erase everything" });
  refresh();
});

refresh();
