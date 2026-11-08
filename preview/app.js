import { cssVariables, resolvePalette } from "./palette.js";

const state = {
  theme: "system",
  wallpaper: "dark",
  dynamicAccent: null,
};

const systemQuery = window.matchMedia("(prefers-color-scheme: dark)");
const themeColorMeta = document.querySelector('meta[name="theme-color"]');
const dynamicStatus = document.querySelector("#dynamic-status");
const contrastRows = document.querySelector("#contrast-rows");
const contrastSummary = document.querySelector("#contrast-summary");
const dynamicInput = document.querySelector("#dynamic-accent");
const resetAccent = document.querySelector("#reset-accent");
const previewDate = document.querySelector("#preview-date");

function effectiveTheme() {
  if (state.theme === "system") {
    return systemQuery.matches ? "dark" : "light";
  }
  return state.theme;
}

function setStatus(message, kind) {
  dynamicStatus.textContent = message;
  dynamicStatus.classList.remove("is-accepted", "is-rejected");
  if (kind === "accepted") {
    dynamicStatus.classList.add("is-accepted");
  } else if (kind === "rejected") {
    dynamicStatus.classList.add("is-rejected");
  }
}

function renderChecks(checks) {
  const fragment = document.createDocumentFragment();
  let failures = 0;

  for (const check of checks) {
    const row = document.createElement("tr");

    const name = document.createElement("td");
    name.textContent = check.name;

    const ratio = document.createElement("td");
    ratio.textContent = `${check.ratio.toFixed(2)}:1`;

    const result = document.createElement("td");
    const status = document.createElement("span");
    status.className = `status ${check.ok ? "status-pass" : "status-fail"}`;

    const icon = document.createElement("span");
    icon.className = `icon ${check.ok ? "icon-check" : "icon-warning"}`;
    icon.setAttribute("aria-hidden", "true");

    const label = document.createElement("span");
    label.textContent = check.ok ? "Pass" : "Fail";

    status.append(icon, label);
    result.append(status);
    row.append(name, ratio, result);
    fragment.append(row);

    if (!check.ok) {
      failures += 1;
    }
  }

  contrastRows.replaceChildren(fragment);
  contrastSummary.textContent =
    failures === 0
      ? `${checks.length}/${checks.length} pass`
      : `${failures} failing`;
}

function applyTheme() {
  const themeName = effectiveTheme();
  const { theme, meta, checks } = resolvePalette(themeName, state.dynamicAccent);

  if (!theme) {
    document.documentElement.style.colorScheme = "dark";
    setStatus("No palette data available; the preview cannot resolve safe colours.", "rejected");
    return;
  }

  for (const [name, value] of Object.entries(cssVariables(theme))) {
    document.documentElement.style.setProperty(name, value);
  }
  document.documentElement.style.colorScheme = themeName;
  document.documentElement.dataset.theme = themeName;
  document.body.classList.toggle("wallpaper-dark", state.wallpaper === "dark");
  document.body.classList.toggle("wallpaper-light", state.wallpaper === "light");

  if (themeColorMeta) {
    themeColorMeta.setAttribute("content", theme.background);
  }

  if (meta.fallback) {
    setStatus(
      "Token data was incomplete, so the built-in Padilha fallback palette is active.",
      "rejected",
    );
  } else if (state.dynamicAccent === null) {
    setStatus(
      `Fixed Padilha ${themeName} palette. Dynamic accent not applied.`,
      null,
    );
  } else if (meta.dynamic) {
    setStatus(`Dynamic accent accepted for the ${themeName} theme after contrast checks.`, "accepted");
  } else {
    setStatus(`${meta.reason}. Canonical Padilha accent kept.`, "rejected");
  }

  dynamicInput.value = theme.accent;
  renderChecks(checks);
}

function updateDate() {
  if (!previewDate) {
    return;
  }
  try {
    previewDate.textContent = new Intl.DateTimeFormat(undefined, {
      weekday: "long",
      day: "numeric",
      month: "long",
    }).format(new Date());
  } catch (error) {
    previewDate.textContent = "Padilha";
  }
}

for (const input of document.querySelectorAll('input[name="theme"]')) {
  input.addEventListener("change", () => {
    if (input.checked) {
      state.theme = input.value;
      applyTheme();
    }
  });
}

for (const input of document.querySelectorAll('input[name="wallpaper"]')) {
  input.addEventListener("change", () => {
    if (input.checked) {
      state.wallpaper = input.value;
      applyTheme();
    }
  });
}

dynamicInput.addEventListener("input", () => {
  state.dynamicAccent = dynamicInput.value;
  applyTheme();
});

resetAccent.addEventListener("click", () => {
  state.dynamicAccent = null;
  applyTheme();
});

systemQuery.addEventListener("change", () => {
  if (state.theme === "system") {
    applyTheme();
  }
});

updateDate();
applyTheme();
