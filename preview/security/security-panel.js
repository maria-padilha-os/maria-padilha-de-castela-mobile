/* Castela Mobile security-panel contract.
 *
 * This module is deliberately dependency-free: no DOM, no timers, no network,
 * no storage, and no privileged Android API. The browser front-end imports it,
 * and the Python test suite exercises it through Node.
 *
 * The panel is an ordinary app surface. It can only use what a normal Android
 * app can see, plus data the user explicitly selects. It must never claim
 * kernel, baseband, or privileged visibility.
 */

export const PANEL_ID = "com.castela.security";
export const PANEL_NAME = "Padilha Security Panel";

export const LAB_MODE = Object.freeze({
  LOCKED: "locked",
  AUTHORIZED: "authorized",
});

/**
 * The four tabs are part of the registration contract. Their order is stable
 * so the UI can build the tab list without duplicating state in markup.
 */
export const PANEL_TABS = Object.freeze([
  Object.freeze({
    id: "network",
    label: "Network inventory",
    icon: "network",
    capability: "networkInventory",
    actionLabel: "Start local inventory",
    missingTitle: "No local network-inventory provider",
    missingDetail:
      "No inventory provider is installed. Inject an Android-safe or explicit Termux/native provider; this panel does not scan, open raw sockets, or request privileged network access.",
    scope:
      "Hosts, addresses, and service hints from a local provider, limited to validated private/link-local ranges. Not other apps' traffic, kernel sockets, or baseband data.",
  }),
  Object.freeze({
    id: "capture",
    label: "Capture review",
    icon: "capture",
    capability: "captureReview",
    actionLabel: "Review selected capture",
    missingTitle: "No local pcap parser",
    missingDetail:
      "No capture parser is installed. Capture review stays offline and disabled until a user-selected file and a local parser are both available.",
    scope:
      "Read-only review of a file the user explicitly selects. Captures may contain personal data and are never uploaded.",
  }),
  Object.freeze({
    id: "permissions",
    label: "Permission audit",
    icon: "key",
    capability: "permissionAudit",
    actionLabel: "Run permission audit",
    missingTitle: "No permission-audit provider",
    missingDetail:
      "Usage-access and package-visibility data are unavailable here. A real build requests user-granted access only when an audit starts.",
    scope:
      "App-visible permission state and user-granted usage access. Not other users, hidden system packages, or privileged policy state.",
  }),
  Object.freeze({
    id: "integrity",
    label: "Device integrity",
    icon: "shield",
    capability: "deviceIntegrity",
    actionLabel: "Run integrity check",
    missingTitle: "No local integrity verifier",
    missingDetail:
      "No integrity verifier is installed. Ordinary apps cannot read verified-boot state, baseband details, or kernel attestation.",
    scope:
      "App-visible signer and configuration facts, clearly labelled. The panel never presents itself as an OS or hardware attestation tool.",
  }),
]);

export const REQUIRED_TAB_IDS = Object.freeze(PANEL_TABS.map((tab) => tab.id));
const TAB_BY_ID = new Map(PANEL_TABS.map((tab) => [tab.id, tab]));

function unavailable(reason, extra = {}) {
  return Object.freeze({
    available: false,
    status: "unavailable",
    reason,
    tool: null,
    version: null,
    ...extra,
  });
}

function available(tool, version, extra = {}) {
  return Object.freeze({
    available: true,
    status: "available",
    reason: null,
    tool: typeof tool === "string" && tool.trim() ? tool.trim() : null,
    version: typeof version === "string" && version.trim() ? version.trim() : null,
    ...extra,
  });
}

/**
 * Normalize a declared capability. Only explicit truthy values count as
 * available; unknown values fail closed to a graceful missing-tool state.
 */
export function normalizeCapability(value, tabOrId) {
  const tab = typeof tabOrId === "string" ? TAB_BY_ID.get(tabOrId) : tabOrId;
  if (!tab) {
    return unavailable("Unknown security-panel capability.");
  }

  if (value === true) {
    return available(tab.capability, null);
  }

  if (value && typeof value === "object") {
    const reason =
      typeof value.reason === "string" && value.reason.trim()
        ? value.reason.trim()
        : tab.missingDetail;

    if (value.available === true && value.privileged === true) {
      return unavailable(
        "This build refuses privileged providers. Use a public-API provider with explicit user action.",
        { rejected: "privileged-provider" },
      );
    }

    if (value.available === true) {
      return available(value.tool, value.version);
    }

    return unavailable(
      reason,
      typeof value.rejected === "string" && value.rejected
        ? { rejected: value.rejected }
        : {},
    );
  }

  return unavailable(tab.missingDetail);
}

/**
 * Inspect an optional local-tool probe. A missing or throwing probe is a normal
 * state, not an exception: every tab still renders with an explanation.
 */
export function detectCapabilities(probe = {}) {
  const capabilities = {};

  for (const tab of PANEL_TABS) {
    const candidate = probe?.[tab.capability];
    if (typeof candidate !== "function") {
      capabilities[tab.id] = unavailable(tab.missingDetail);
      continue;
    }

    try {
      capabilities[tab.id] = normalizeCapability(candidate(), tab);
    } catch (error) {
      const detail =
        error instanceof Error && error.message ? error.message : String(error);
      capabilities[tab.id] = unavailable(
        `${tab.missingTitle}: the capability probe failed safely (${detail}).`,
        { rejected: "probe-failed" },
      );
    }
  }

  return Object.freeze(capabilities);
}

/**
 * Accept already-detected capabilities keyed by tab id (preferred) or by
 * capability name. Missing entries become graceful unavailable states.
 */
export function normalizeCapabilities(capabilities = {}) {
  const normalized = {};
  for (const tab of PANEL_TABS) {
    const value = capabilities?.[tab.id] ?? capabilities?.[tab.capability];
    normalized[tab.id] = normalizeCapability(value, tab);
  }
  return Object.freeze(normalized);
}

export function securityPanelDefinition() {
  return Object.freeze({
    id: PANEL_ID,
    name: PANEL_NAME,
    version: "1.0.0",
    kind: "security-panel",
    requiresLabMode: true,
    autoRun: false,
    backgroundScanning: false,
    hiddenService: false,
    privileged: false,
    tabs: PANEL_TABS,
  });
}

export function validatePanel(panel) {
  const errors = [];

  if (!panel || typeof panel !== "object") {
    return { ok: false, errors: ["panel must be an object"] };
  }
  if (typeof panel.id !== "string" || !/^[a-z][a-z0-9]*(\.[a-z0-9_-]+)+$/.test(panel.id)) {
    errors.push("panel id must be a reverse-domain identifier");
  }
  if (typeof panel.name !== "string" || panel.name.trim() === "") {
    errors.push("panel name must be a non-empty string");
  }
  if (!Array.isArray(panel.tabs) || panel.tabs.length === 0) {
    errors.push("panel must declare at least one tab");
  } else {
    const seen = new Set();
    for (const tab of panel.tabs) {
      if (!tab || typeof tab !== "object") {
        errors.push("each tab must be an object");
        continue;
      }
      if (typeof tab.id !== "string" || tab.id.trim() === "") {
        errors.push("each tab needs a non-empty id");
      } else if (seen.has(tab.id)) {
        errors.push(`duplicate tab id: ${tab.id}`);
      } else {
        seen.add(tab.id);
      }
      if (typeof tab.label !== "string" || tab.label.trim() === "") {
        errors.push(`tab ${tab.id ?? "(unknown)"} needs a non-empty label`);
      }
    }
  }
  if (panel.autoRun === true) {
    errors.push("automatic execution is not permitted");
  }
  if (panel.backgroundScanning === true) {
    errors.push("background scanning is not permitted");
  }
  if (panel.hiddenService === true) {
    errors.push("hidden services are not permitted");
  }
  if (panel.privileged === true) {
    errors.push("privileged panels are not permitted");
  }

  return { ok: errors.length === 0, errors };
}

export function createPanelRegistry(initialPanels = []) {
  const panels = new Map();

  const registry = {
    register(panel) {
      const validation = validatePanel(panel);
      if (!validation.ok) {
        const error = new Error(`invalid panel: ${validation.errors.join("; ")}`);
        error.code = "invalid-panel";
        throw error;
      }
      if (panels.has(panel.id)) {
        const error = new Error(`panel already registered: ${panel.id}`);
        error.code = "duplicate-panel";
        throw error;
      }
      const registered = Object.freeze(panel);
      panels.set(panel.id, registered);
      return registered;
    },
    get(id) {
      return panels.get(id) ?? null;
    },
    has(id) {
      return panels.has(id);
    },
    list() {
      return Array.from(panels.values());
    },
    get size() {
      return panels.size;
    },
  };

  for (const panel of initialPanels) {
    registry.register(panel);
  }

  return Object.freeze(registry);
}

export function registerSecurityPanel(
  registry = createPanelRegistry(),
  definition = securityPanelDefinition(),
) {
  const validation = validatePanel(definition);
  if (!validation.ok) {
    const error = new Error(`invalid security panel: ${validation.errors.join("; ")}`);
    error.code = "invalid-panel";
    throw error;
  }

  const tabIds = definition.tabs.map((tab) => tab.id);
  const missing = REQUIRED_TAB_IDS.filter((id) => !tabIds.includes(id));
  if (missing.length > 0 || tabIds.length !== REQUIRED_TAB_IDS.length) {
    const error = new Error(
      `security panel must register exactly these tabs: ${REQUIRED_TAB_IDS.join(", ")}`,
    );
    error.code = "missing-required-tabs";
    throw error;
  }
  if (definition.requiresLabMode !== true) {
    const error = new Error("security panel must require authorized lab mode");
    error.code = "lab-mode-required";
    throw error;
  }

  return registry.register(definition);
}

/**
 * Create an in-memory panel session. Nothing runs on construction: the only
 * side effects are the explicit authorize, stop/clear, select, and run calls.
 */
export function createSecurityPanel({
  definition = securityPanelDefinition(),
  probe = {},
  capabilities = null,
  actions = {},
  now = () => new Date().toISOString(),
} = {}) {
  const resolvedCapabilities = capabilities
    ? normalizeCapabilities(capabilities)
    : detectCapabilities(probe);

  let labMode = LAB_MODE.LOCKED;
  let session = null;
  let activeTab = PANEL_TABS[0].id;
  let lastStoppedAt = null;
  let sessionSequence = 0;
  const results = Object.create(null);

  function snapshot() {
    return Object.freeze({
      panelId: definition.id,
      labMode,
      authorized: labMode === LAB_MODE.AUTHORIZED,
      session: session ? Object.freeze({ ...session }) : null,
      activeTab,
      tabs: Object.freeze(
        PANEL_TABS.map((tab) =>
          Object.freeze({ ...tab, capability: resolvedCapabilities[tab.id] }),
        ),
      ),
      results: Object.freeze({ ...results }),
      lastStoppedAt,
    });
  }

  function authorize({ acknowledged = false } = {}) {
    if (labMode === LAB_MODE.AUTHORIZED) {
      return { ok: true, code: "already-authorized", state: snapshot() };
    }
    if (acknowledged !== true) {
      return {
        ok: false,
        code: "acknowledgement-required",
        message:
          "Confirm that you own the network or have written permission to inspect it before authorizing lab mode.",
        state: snapshot(),
      };
    }

    sessionSequence += 1;
    session = {
      id: `lab-${sessionSequence}`,
      authorizedAt: now(),
      scope: "user-authorized local lab",
    };
    labMode = LAB_MODE.AUTHORIZED;
    lastStoppedAt = null;
    return { ok: true, code: "authorized", state: snapshot() };
  }

  function stopAndClear() {
    const wasAuthorized = labMode === LAB_MODE.AUTHORIZED;
    labMode = LAB_MODE.LOCKED;
    session = null;
    lastStoppedAt = now();
    for (const key of Object.keys(results)) {
      delete results[key];
    }
    return {
      ok: true,
      code: "stopped",
      cleared: true,
      wasAuthorized,
      state: snapshot(),
    };
  }

  function selectTab(tabId) {
    if (!TAB_BY_ID.has(tabId)) {
      return {
        ok: false,
        code: "unknown-tab",
        message: `Unknown tab: ${String(tabId)}`,
        state: snapshot(),
      };
    }
    activeTab = tabId;
    return { ok: true, code: "selected", state: snapshot() };
  }

  function run(tabId) {
    const tab = TAB_BY_ID.get(tabId);
    if (!tab) {
      return {
        ok: false,
        code: "unknown-tab",
        message: `Unknown tab: ${String(tabId)}`,
        state: snapshot(),
      };
    }
    if (labMode !== LAB_MODE.AUTHORIZED) {
      return {
        ok: false,
        code: "not-authorized",
        message: "Authorize lab mode before running this tab.",
        state: snapshot(),
      };
    }

    const capability = resolvedCapabilities[tab.id];
    if (!capability.available) {
      return {
        ok: false,
        code: "capability-unavailable",
        message: capability.reason,
        state: snapshot(),
      };
    }

    const action = actions[tab.id];
    if (typeof action !== "function") {
      return {
        ok: false,
        code: "no-action",
        message: "No local action is registered for this tab.",
        state: snapshot(),
      };
    }

    try {
      const data = action({
        tabId: tab.id,
        authorized: true,
        session: session ? session.id : null,
        scope: session ? session.scope : null,
      });
      results[tab.id] = {
        status: "complete",
        data: data ?? null,
        finishedAt: now(),
      };
      return { ok: true, code: "complete", data: data ?? null, state: snapshot() };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      results[tab.id] = {
        status: "failed",
        reason: message,
        finishedAt: now(),
      };
      return { ok: false, code: "action-failed", message, state: snapshot() };
    }
  }

  return Object.freeze({
    definition,
    snapshot,
    authorize,
    stopAndClear,
    selectTab,
    run,
    hasAction: (tabId) => typeof actions[tabId] === "function",
    getCapabilities: () => resolvedCapabilities,
  });
}
