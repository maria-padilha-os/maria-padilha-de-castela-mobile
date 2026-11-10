/* Dedicated security-panel front-end.
 *
 * All work is local and event-driven. This file has no timers, no workers, no
 * network calls, no storage, and no automatic scan. The pure contract lives in
 * security-panel.js so it can be tested without a browser.
 */

import {
  PANEL_TABS,
  createPanelRegistry,
  createSecurityPanel,
  registerSecurityPanel,
} from "./security-panel.js";
import {
  AUTHORIZATION_STATEMENT,
  createNetworkInventory,
  validateTarget,
} from "./network-inventory.js";
import {
  CAPTURE_CONSENT_STATEMENT,
  MAX_REVIEW_BYTES,
  createPcapCapture,
} from "./pcap-capture.js";

const registry = createPanelRegistry();
const definition = registerSecurityPanel(registry);
const networkProvider =
  globalThis.CASTELA_NETWORK_PROVIDER &&
  typeof globalThis.CASTELA_NETWORK_PROVIDER === "object"
    ? globalThis.CASTELA_NETWORK_PROVIDER
    : null;
const inventory = createNetworkInventory({ provider: networkProvider });
const inventoryReady = inventory.hasProvider();
const captureProvider =
  globalThis.CASTELA_CAPTURE_PROVIDER &&
  typeof globalThis.CASTELA_CAPTURE_PROVIDER === "object"
    ? globalThis.CASTELA_CAPTURE_PROVIDER
    : null;
const capture = createPcapCapture({ provider: captureProvider });

const tools =
  globalThis.CASTELA_SECURITY_TOOLS &&
  typeof globalThis.CASTELA_SECURITY_TOOLS === "object"
    ? globalThis.CASTELA_SECURITY_TOOLS
    : {};

const probe = { ...tools };
if (inventoryReady) {
  probe.networkInventory = () => ({
    available: true,
    tool: inventory.getProviderStatus().label,
  });
} else if (networkProvider) {
  probe.networkInventory = () => ({
    available: false,
    reason: inventory.getProviderStatus().message,
    rejected: "provider-rejected",
  });
}

// The offline pcap parser is built in, so capture review never depends on an
// installed tool. Live capture still requires an explicit local provider.
probe.captureReview = () => ({
  available: true,
  tool: "local-pcap-parser",
  version: "1.0",
});

let selectedCapture = null;
let pendingReviewBytes = null;

const actions = {};
if (inventoryReady) {
  actions.network = () => inventory.scan(inventoryTarget?.value ?? "");
}
actions.capture = () => {
  if (!selectedCapture) {
    throw new Error("Choose a capture file before reviewing it.");
  }
  if (!pendingReviewBytes) {
    throw new Error("Read the selected capture before reviewing it.");
  }
  const result = capture.reviewCapture(pendingReviewBytes, {
    fileName: selectedCapture.name,
    size: selectedCapture.size,
  });
  pendingReviewBytes = null;
  return result;
};

const panel = createSecurityPanel({ definition, probe, actions });

const banner = document.querySelector("#lab-banner");
const labTitle = document.querySelector("#lab-title");
const labStatus = document.querySelector("#lab-status");
const labChip = document.querySelector("#lab-chip");
const acknowledgement = document.querySelector("#lab-ack");
const authorizeButton = document.querySelector("#authorize-lab");
const stopButton = document.querySelector("#stop-clear");
const sessionNote = document.querySelector("#lab-session");
const labFeedback = document.querySelector("#lab-feedback");
const capabilitySummary = document.querySelector("#capability-summary");
const captureFile = document.querySelector("#capture-file");
const captureConsent = document.querySelector("#capture-consent");
const captureStartButton = document.querySelector("#capture-start");
const captureStopButton = document.querySelector("#capture-stop");
const captureClearButton = document.querySelector("#capture-clear");
const captureProviderStatus = document.querySelector("#capture-provider-status");
const captureProviderReason = document.querySelector("#capture-provider-reason");
const captureIndicator = document.querySelector("#capture-indicator");
const captureIndicatorLabel = document.querySelector("#capture-indicator-label");
const captureIndicatorDetail = document.querySelector("#capture-indicator-detail");
const captureIndicatorStop = document.querySelector("#capture-indicator-stop");
const captureSummary = document.querySelector("#capture-summary");
const captureSummaryBadge = document.querySelector("#capture-summary-badge");
const captureStats = document.querySelector("#capture-stats");
const captureWarnings = document.querySelector("#capture-warnings");
const captureConversationRows = document.querySelector("#capture-conversation-rows");
const captureSummaryNote = document.querySelector("#capture-summary-note");
const inventoryTarget = document.querySelector("#inventory-target");
const inventoryTargetStatus = document.querySelector("#inventory-target-status");
const inventoryResults = document.querySelector("#inventory-results");
const inventorySummary = document.querySelector("#inventory-summary");
const inventoryRows = document.querySelector("#inventory-rows");
const inventoryNote = document.querySelector("#inventory-note");
const tabList = document.querySelector('[role="tablist"]');
const tabButtons = Array.from(document.querySelectorAll("[data-tab]"));
const runButtons = Array.from(document.querySelectorAll("[data-run-tab]"));

let feedback = {
  message: "Lab mode is locked. No collection, capture, or audit is running.",
  kind: null,
};

if (acknowledgement) {
  acknowledgement.title = AUTHORIZATION_STATEMENT;
}

function setFeedback(message, kind = null) {
  feedback = { message, kind };
}

function findTab(tabId) {
  return panel.snapshot().tabs.find((tab) => tab.id === tabId);
}

function formatBytes(size) {
  if (!Number.isFinite(size) || size < 0) {
    return "size unavailable";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  const units = ["KiB", "MiB", "GiB", "TiB"];
  let value = size / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && value >= 1024; index += 1) {
    value /= 1024;
    unit = units[index];
  }
  return `${value.toFixed(1)} ${unit}`;
}

function renderTargetStatus() {
  if (!inventoryTargetStatus || !inventoryTarget) {
    return;
  }

  const value = inventoryTarget.value.trim();
  inventoryTargetStatus.classList.remove("is-accepted", "is-rejected");

  if (!value) {
    inventoryTargetStatus.textContent = inventoryReady
      ? "Choose a private or link-local range. Nothing runs automatically."
      : "No local provider is installed. Range validation works here, but discovery is disabled.";
    return;
  }

  const result = validateTarget(value);
  if (!result.ok) {
    inventoryTargetStatus.textContent = result.message;
    inventoryTargetStatus.classList.add("is-rejected");
    return;
  }

  inventoryTargetStatus.textContent = inventoryReady
    ? `Validated ${result.target.scope} ${result.target.canonical}: ${result.target.addressCountText}.`
    : `Validated ${result.target.scope} ${result.target.canonical}, but no local provider is installed, so discovery stays disabled.`;
  inventoryTargetStatus.classList.add("is-accepted");
}

function renderInventory(snapshot) {
  if (
    !inventoryResults ||
    !inventoryRows ||
    !inventorySummary ||
    !inventoryNote
  ) {
    return;
  }

  const result = snapshot.results.network;
  const data = result?.status === "complete" ? result.data : null;
  const current = validateTarget(inventoryTarget?.value ?? "");

  if (
    !data ||
    data.ok !== true ||
    !current.ok ||
    current.target.canonical !== data.target.canonical
  ) {
    inventoryResults.hidden = true;
    inventoryRows.replaceChildren();
    inventoryNote.textContent = "";
    return;
  }

  inventoryResults.hidden = false;
  inventorySummary.textContent = `${data.hosts.length} host${
    data.hosts.length === 1 ? "" : "s"
  }`;
  inventoryRows.replaceChildren();

  if (data.hosts.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.textContent = `No devices were returned for ${data.target.canonical}.`;
    row.append(cell);
    inventoryRows.append(row);
  } else {
    for (const host of data.hosts) {
      const row = document.createElement("tr");

      const hostCell = document.createElement("td");
      hostCell.textContent = host.host;

      const addressCell = document.createElement("td");
      addressCell.textContent = host.address;

      const serviceCell = document.createElement("td");
      if (host.services.length === 0) {
        serviceCell.textContent = "No service hints observed";
      } else {
        serviceCell.textContent = host.services
          .map(
            (service) =>
              `${service.hint} (${service.protocol}/${service.port})`,
          )
          .join(", ");
      }

      row.append(hostCell, addressCell, serviceCell);
      inventoryRows.append(row);
    }
  }

  const notes = [`Range ${data.target.canonical} (${data.target.scope}).`];
  if (data.truncated) {
    notes.push("Results were truncated at the local limit.");
  }
  if (Number(data.ignored) > 0) {
    notes.push(
      `${data.ignored} provider entr${
        data.ignored === 1 ? "y was" : "ies were"
      } ignored because it was invalid, public, or outside the range.`,
    );
  }
  notes.push("No port scan, exploit, or credential capture ran.");
  inventoryNote.textContent = notes.join(" ");
}

function formatTimestamp(seconds) {
  if (!Number.isFinite(seconds)) {
    return "unavailable";
  }
  try {
    return new Date(seconds * 1000).toISOString();
  } catch {
    return String(seconds);
  }
}

function endpointText(address, port) {
  if (port === null || port === undefined) {
    return address;
  }
  return address.includes(":") ? `[${address}]:${port}` : `${address}:${port}`;
}

function addCaptureStat(label, value) {
  if (!captureStats) {
    return;
  }
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value;
  captureStats.append(term, description);
}

function renderCapture(snapshot) {
  const state = capture.snapshot();
  const provider = state.providerStatus;

  if (captureIndicator) {
    captureIndicator.hidden = !state.indicator.visible;
    if (captureIndicatorLabel) {
      captureIndicatorLabel.textContent = state.indicator.label;
    }
    if (captureIndicatorDetail) {
      captureIndicatorDetail.textContent = state.indicator.detail;
    }
    if (captureIndicatorStop) {
      captureIndicatorStop.disabled = state.state !== "capturing";
    }
  }

  if (captureProviderStatus) {
    captureProviderStatus.textContent = provider.ok
      ? "Live capture ready"
      : "Live capture unavailable";
    captureProviderStatus.classList.toggle("is-rejected", !provider.ok);
  }
  if (captureProviderReason) {
    captureProviderReason.textContent = provider.ok
      ? `${state.provider.label} is configured. Nothing starts until lab mode is authorized, capture consent is checked, and you press Start capture.`
      : `${provider.message} Offline review still works on a user-selected file.`;
  }

  if (captureConsent) {
    captureConsent.disabled =
      !snapshot.authorized || state.state === "capturing";
  }
  if (captureStartButton) {
    captureStartButton.disabled =
      !snapshot.authorized ||
      !state.authorized ||
      !provider.ok ||
      !captureConsent?.checked ||
      state.state === "capturing";
    captureStartButton.title = provider.ok
      ? "Start a user-authorized live capture with a persistent indicator."
      : provider.message;
  }
  if (captureStopButton) {
    captureStopButton.disabled = state.state !== "capturing";
  }
  if (captureClearButton) {
    captureClearButton.disabled =
      !state.canClear || state.state === "capturing";
    captureClearButton.title =
      state.state === "capturing"
        ? "Stop the live capture before clearing capture files."
        : state.canClear
          ? "Delete captured files through the local capture provider."
          : "No capture provider with a verified clear function is configured.";
  }

  if (!captureSummary) {
    return;
  }

  const review = state.review;
  if (!review) {
    captureSummary.hidden = true;
    captureStats?.replaceChildren();
    captureWarnings?.replaceChildren();
    captureConversationRows?.replaceChildren();
    if (captureSummaryNote) {
      captureSummaryNote.textContent = "";
    }
    return;
  }

  const summary = review.summary;
  captureSummary.hidden = false;
  if (captureSummaryBadge) {
    captureSummaryBadge.textContent = `${summary.packetCount} packet${
      summary.packetCount === 1 ? "" : "s"
    } · ${formatBytes(summary.capturedBytes)}`;
  }

  captureStats?.replaceChildren();
  addCaptureStat("File", review.fileName);
  addCaptureStat("Size", `${formatBytes(review.size)} (${review.size} bytes)`);
  addCaptureStat(
    "Format",
    `${summary.format.name} ${summary.format.version ?? ""} · ${
      summary.format.byteOrder
    }-endian · link type ${summary.format.linkType ?? "unknown"}`,
  );
  addCaptureStat("Packets", String(summary.packetCount));
  addCaptureStat(
    "Captured / original bytes",
    `${summary.capturedBytes} / ${summary.originalBytes}`,
  );
  addCaptureStat(
    "Time range",
    summary.firstTimestamp !== null && summary.lastTimestamp !== null
      ? `${formatTimestamp(summary.firstTimestamp)} → ${formatTimestamp(
          summary.lastTimestamp,
        )} (${Number(summary.durationSeconds ?? 0).toFixed(3)} s)`
      : "Timestamps unavailable",
  );
  const protocolText =
    Object.entries(summary.protocols)
      .filter(([, count]) => count > 0)
      .map(([name, count]) => `${name} ${count}`)
      .join(", ") || "none decoded";
  addCaptureStat("Protocols", protocolText);
  addCaptureStat(
    "Payload",
    summary.payload.packets > 0
      ? `${summary.payload.packets} packet${
          summary.payload.packets === 1 ? "" : "s"
        }, ${formatBytes(summary.payload.bytes)} (contents not displayed)`
      : "No payload bytes observed",
  );
  addCaptureStat(
    "Sensitivity",
    summary.sensitive.hasPayload
      ? "High: payloads may contain credentials or personal data"
      : "Treat as sensitive metadata",
  );

  captureWarnings?.replaceChildren();
  for (const warning of summary.warnings) {
    const line = document.createElement("p");
    line.className = "capture-warning-line";
    if (warning.code === "sensitive-payload" || warning.code === "plaintext-service") {
      line.classList.add("is-sensitive");
    }
    line.textContent = warning.message;
    captureWarnings?.append(line);
  }

  captureConversationRows?.replaceChildren();
  if (summary.conversations.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No decodable TCP, UDP, or ICMP conversations.";
    row.append(cell);
    captureConversationRows?.append(row);
  } else {
    for (const conversation of summary.conversations) {
      const row = document.createElement("tr");

      const protocolCell = document.createElement("td");
      protocolCell.textContent = conversation.protocol.toUpperCase();

      const sourceCell = document.createElement("td");
      sourceCell.textContent = endpointText(
        conversation.source,
        conversation.sourcePort,
      );

      const destinationCell = document.createElement("td");
      destinationCell.textContent = endpointText(
        conversation.destination,
        conversation.destinationPort,
      );

      const packetsCell = document.createElement("td");
      packetsCell.textContent = `${conversation.packets} / ${formatBytes(
        conversation.bytes,
      )}`;

      row.append(protocolCell, sourceCell, destinationCell, packetsCell);
      captureConversationRows?.append(row);
    }
  }

  const endpoints = summary.endpoints
    .slice(0, 5)
    .map((endpoint) => `${endpoint.address} (${endpoint.packets})`)
    .join(", ");
  const ports = summary.ports
    .slice(0, 5)
    .map((port) => `${port.protocol}/${port.port} (${port.packets})`)
    .join(", ");
  const notes = [
    `Top endpoints: ${endpoints || "none decoded"}.`,
    `Top ports: ${ports || "none decoded"}.`,
    "Payload contents are never displayed. The file was read locally and nothing was uploaded.",
  ];
  if (summary.limits.reached) {
    notes.push(
      `Review stopped at the local limit of ${summary.limits.maxPackets} packets.`,
    );
  }
  if (captureSummaryNote) {
    captureSummaryNote.textContent = notes.join(" ");
  }
}

function renderCapabilityStatus(tab, capability) {
  const status = document.querySelector(`[data-capability-status="${tab.id}"]`);
  if (!status) {
    return;
  }
  status.replaceChildren();

  const icon = document.createElement("span");
  icon.className = `icon ${capability.available ? "icon-check" : "icon-warning"}`;
  icon.setAttribute("aria-hidden", "true");

  const label = document.createElement("span");
  label.textContent = capability.available ? "Tool ready" : "Tool unavailable";

  status.className = `status ${
    capability.available ? "status-pass" : "status-fail"
  }`;
  status.append(icon, label);
}

function renderEmptyState(tab, capability, snapshot) {
  const empty = document.querySelector(`[data-empty-state="${tab.id}"]`);
  if (!empty) {
    return;
  }

  const result = snapshot.results[tab.id];
  if (tab.id === "capture") {
    const captureState = capture.snapshot();
    if (captureState.review) {
      empty.textContent = `${captureState.review.fileName} was reviewed locally: ${captureState.review.summary.packetCount} packet${
        captureState.review.summary.packetCount === 1 ? "" : "s"
      }. Review the sensitive-data warnings below, then clear the capture when finished.`;
      return;
    }
    if (result?.status === "complete" && result.data?.ok === false) {
      empty.textContent = result.data.message;
      return;
    }
    if (result?.status === "failed") {
      empty.textContent = `${tab.label} failed safely: ${result.reason}`;
      return;
    }
    if (captureState.state === "capturing") {
      empty.textContent =
        "A live capture is running and its indicator stays visible until you stop it. The file list is managed by the local capture provider.";
      return;
    }
    if (!snapshot.authorized) {
      empty.textContent =
        "Offline review is ready, but lab mode is locked. Authorize lab mode before selecting and reading a capture.";
      return;
    }
    if (selectedCapture) {
      empty.textContent = `${selectedCapture.name} (${formatBytes(
        selectedCapture.size,
      )}) is selected locally. Nothing has been parsed or uploaded.`;
      return;
    }
    empty.textContent =
      "No capture selected. The panel never opens a file automatically.";
    return;
  }

  if (result?.status === "complete") {
    if (tab.id === "network" && result.data?.ok === false) {
      empty.textContent = result.data.message;
      return;
    }
    if (tab.id === "network" && result.data?.ok === true) {
      const count = result.data.hosts.length;
      empty.textContent =
        count === 0
          ? `Inventory completed for ${result.data.target.canonical}: no devices were returned.`
          : `${count} device${count === 1 ? "" : "s"} listed below for ${result.data.target.canonical}. Review the data, then stop and clear when finished.`;
      return;
    }
    empty.textContent = `${tab.label} completed locally in session ${snapshot.session?.id ?? "unknown"}. Review the data below, then stop and clear when finished.`;
    return;
  }
  if (result?.status === "failed") {
    empty.textContent = `${tab.label} failed safely: ${result.reason}`;
    return;
  }
  if (!capability.available) {
    empty.textContent = `${capability.reason} No substitute tool is started, and nothing is sent off the device.`;
    return;
  }
  if (!snapshot.authorized) {
    empty.textContent =
      "The local tool is ready, but lab mode is locked. Authorize lab mode before starting.";
    return;
  }
  if (tab.id === "network") {
    empty.textContent = inventoryTarget?.value.trim()
      ? "No inventory has run for this range. Starting it is an explicit, foreground action."
      : "Enter a private or link-local range, then start the local inventory.";
    return;
  }
  empty.textContent = `No ${tab.label.toLowerCase()} has run. Starting it is an explicit, foreground action.`;
}

function renderCaptureField(snapshot, capability) {
  if (!captureFile) {
    return;
  }
  captureFile.disabled = !snapshot.authorized || !capability.available;
}

function renderRunButton(tab, capability, snapshot) {
  const button = document.querySelector(`[data-run-tab="${tab.id}"]`);
  if (!button) {
    return;
  }

  const reason = document.querySelector(
    `[data-capability-reason="${tab.id}"]`,
  );
  const requiresSelection = tab.id === "capture" && !selectedCapture;
  const hasAction = panel.hasAction(tab.id);
  button.disabled =
    !snapshot.authorized ||
    !capability.available ||
    requiresSelection ||
    !hasAction;
  button.setAttribute("aria-describedby", reason ? reason.id : "");

  if (!snapshot.authorized) {
    button.title = "Authorize lab mode before running this tab.";
  } else if (!capability.available) {
    button.title = capability.reason;
  } else if (requiresSelection) {
    button.title = "Choose a capture file before reviewing it.";
  } else if (!hasAction) {
    button.title = "No local action is registered for this tab.";
  } else {
    button.removeAttribute("title");
  }
}

function renderTabs(snapshot) {
  for (const button of tabButtons) {
    const tabId = button.dataset.tab;
    const selected = tabId === snapshot.activeTab;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;

    const tabPanel = document.querySelector(`[data-tab-panel="${tabId}"]`);
    if (tabPanel) {
      tabPanel.hidden = !selected;
    }
  }
}

function renderLabMode(snapshot) {
  if (!banner || !labTitle || !labStatus || !labChip) {
    return;
  }

  if (snapshot.authorized) {
    banner.dataset.state = "authorized";
    labChip.dataset.state = "authorized";
    labChip.textContent = "Authorized";
    labTitle.textContent = "Lab mode authorized";
    labStatus.textContent = `Session ${snapshot.session.id} is active. Nothing runs until you press a tab's own action.`;
    sessionNote.textContent = `Session ${snapshot.session.id} · authorized ${snapshot.session.authorizedAt}`;
    acknowledgement.checked = true;
    acknowledgement.disabled = true;
    authorizeButton.disabled = true;
    stopButton.disabled = false;
  } else {
    banner.dataset.state = "locked";
    labChip.dataset.state = "locked";
    labChip.textContent = "Locked";
    labTitle.textContent = "Lab mode is locked";
    labStatus.textContent =
      "Nothing is scanned automatically. Inspection starts only after you authorize lab mode and press a tab's own action.";
    sessionNote.textContent = snapshot.lastStoppedAt
      ? `Stopped ${snapshot.lastStoppedAt}; session data cleared`
      : "No active session";
    acknowledgement.disabled = false;
    authorizeButton.disabled = !acknowledgement.checked;
    stopButton.disabled = true;
  }

  labFeedback.textContent = feedback.message;
  labFeedback.classList.toggle("is-accepted", feedback.kind === "accepted");
  labFeedback.classList.toggle("is-rejected", feedback.kind === "rejected");
}

function render() {
  const snapshot = panel.snapshot();
  const available = snapshot.tabs.filter((tab) => tab.capability.available);

  if (capabilitySummary) {
    capabilitySummary.textContent = `${available.length}/${snapshot.tabs.length} tools ready`;
  }

  renderLabMode(snapshot);
  renderTabs(snapshot);
  renderTargetStatus();
  renderInventory(snapshot);
  renderCapture(snapshot);

  for (const tab of snapshot.tabs) {
    const capability = tab.capability;
    const reason = document.querySelector(
      `[data-capability-reason="${tab.id}"]`,
    );
    if (reason) {
      reason.textContent = capability.available
        ? `${tab.scope}${capability.tool ? ` Provider: ${capability.tool}.` : ""}`
        : capability.reason;
    }
    renderCapabilityStatus(tab, capability);
    renderEmptyState(tab, capability, snapshot);
    renderRunButton(tab, capability, snapshot);
    if (tab.id === "capture") {
      renderCaptureField(snapshot, capability);
    }
  }

  if (captureFile && !selectedCapture) {
    captureFile.value = "";
  }
}

function activateTab(tabId, { focus = false } = {}) {
  const result = panel.selectTab(tabId);
  if (!result.ok) {
    return;
  }
  render();
  if (focus) {
    document.querySelector(`[data-tab="${tabId}"]`)?.focus();
  }
}

function authorizeLabMode() {
  const result = panel.authorize({ acknowledged: acknowledgement.checked });
  if (!result.ok) {
    setFeedback(result.message, "rejected");
  } else {
    const inventoryResult = inventory.authorize({ acknowledged: true });
    const captureResult = capture.authorize({ acknowledged: true });
    setFeedback(
      inventoryResult.ok && captureResult.ok
        ? `Lab mode authorized in session ${result.state.session.id}. Nothing has run yet.`
        : inventoryResult.message || captureResult.message,
      inventoryResult.ok && captureResult.ok ? "accepted" : "rejected",
    );
  }
  render();
}

function stopAndClear() {
  const result = panel.stopAndClear();
  inventory.stopAndClear();
  const captureResult = capture.stopAndClear();
  selectedCapture = null;
  pendingReviewBytes = null;
  if (captureFile) {
    captureFile.value = "";
  }
  if (captureConsent) {
    captureConsent.checked = false;
  }
  if (inventoryTarget) {
    inventoryTarget.value = "";
  }
  if (inventoryTargetStatus) {
    inventoryTargetStatus.textContent = "";
    inventoryTargetStatus.classList.remove("is-accepted", "is-rejected");
  }
  if (acknowledgement) {
    acknowledgement.checked = false;
  }
  setFeedback(
    captureResult.ok
      ? result.wasAuthorized
        ? "Lab mode stopped. Capture access was revoked; session results, the selected capture, capture files, and inventory results were cleared."
        : "Lab mode is already locked; session results, the selected capture, capture files, and inventory results were cleared."
      : captureResult.message,
    captureResult.ok ? "accepted" : "rejected",
  );
  render();
}

function runTab(tabId) {
  const tab = findTab(tabId);
  if (!tab) {
    return;
  }
  const result = panel.run(tabId);
  if (result.ok) {
    if (tabId === "network" && result.data?.ok === false) {
      setFeedback(
        result.data.message || "The range was refused safely.",
        "rejected",
      );
    } else if (tabId === "network" && result.data?.ok === true) {
      const count = result.data.hosts.length;
      setFeedback(
        `Local inventory complete: ${count} host${
          count === 1 ? "" : "s"
        } in ${result.data.target.canonical}.`,
        "accepted",
      );
    } else if (tabId === "capture" && result.data?.ok === false) {
      setFeedback(
        result.data.message || "The capture was refused safely.",
        "rejected",
      );
    } else if (tabId === "capture" && result.data?.ok === true) {
      const summary = result.data.summary;
      setFeedback(
        `Capture reviewed locally: ${summary.packetCount} packet${
          summary.packetCount === 1 ? "" : "s"
        }, ${formatBytes(summary.capturedBytes)}. Nothing was uploaded.`,
        "accepted",
      );
    } else {
      setFeedback(`${tab.label} completed locally.`, "accepted");
    }
  } else {
    setFeedback(result.message || "The action was refused safely.", "rejected");
  }
  render();
}

async function reviewSelectedCapture() {
  if (!panel.snapshot().authorized) {
    setFeedback(
      "Authorize lab mode before reading a capture file.",
      "rejected",
    );
    render();
    return;
  }
  if (!selectedCapture?.file) {
    setFeedback("Choose a capture file before reviewing it.", "rejected");
    render();
    return;
  }
  if (selectedCapture.size > MAX_REVIEW_BYTES) {
    setFeedback(
      `The selected capture is larger than the local review limit of ${MAX_REVIEW_BYTES} bytes. Choose a smaller file or use the explicit desktop helper.`,
      "rejected",
    );
    render();
    return;
  }

  try {
    const buffer = await selectedCapture.file.arrayBuffer();
    pendingReviewBytes = new Uint8Array(buffer);
    runTab("capture");
  } catch (error) {
    pendingReviewBytes = null;
    const detail =
      error instanceof Error && error.message ? error.message : String(error);
    setFeedback(
      `The selected capture could not be read locally (${detail}).`,
      "rejected",
    );
    render();
  }
}

function startCapture() {
  const result = capture.start({ acknowledged: captureConsent?.checked === true });
  if (result.ok) {
    setFeedback(
      `Live capture started: ${result.capture.label}. Its persistent indicator stays visible until you stop it.`,
      "accepted",
    );
  } else {
    setFeedback(result.message || "The capture was refused safely.", "rejected");
  }
  render();
}

function stopCapture() {
  const result = capture.stop();
  setFeedback(
    result.ok
      ? "Live capture stopped. The persistent indicator was cleared."
      : result.message || "The capture reported a stop failure.",
    result.ok ? "accepted" : "rejected",
  );
  render();
}

function clearCaptures() {
  const result = capture.clearCaptures({ confirmed: true });
  setFeedback(
    result.ok
      ? "Capture files were cleared through the local provider."
      : result.message || "Capture files could not be fully cleared.",
    result.ok ? "accepted" : "rejected",
  );
  render();
}

for (const button of tabButtons) {
  button.addEventListener("click", () => activateTab(button.dataset.tab));
  button.addEventListener("keydown", (event) => {
    const currentIndex = PANEL_TABS.findIndex(
      (tab) => tab.id === button.dataset.tab,
    );
    let nextIndex = null;

    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % PANEL_TABS.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex =
        (currentIndex - 1 + PANEL_TABS.length) % PANEL_TABS.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = PANEL_TABS.length - 1;
    }

    if (nextIndex !== null) {
      event.preventDefault();
      activateTab(PANEL_TABS[nextIndex].id, { focus: true });
    }
  });
}

tabList?.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    activationTarget()?.focus();
  }
});

function activationTarget() {
  return document.querySelector(
    `[data-tab="${panel.snapshot().activeTab}"]`,
  );
}

acknowledgement?.addEventListener("change", () => {
  authorizeButton.disabled = !acknowledgement.checked;
});

authorizeButton?.addEventListener("click", authorizeLabMode);
stopButton?.addEventListener("click", stopAndClear);

for (const button of runButtons) {
  button.addEventListener("click", () => {
    if (button.dataset.runTab === "capture") {
      reviewSelectedCapture();
    } else {
      runTab(button.dataset.runTab);
    }
  });
}

captureConsent?.addEventListener("change", () => render());
captureStartButton?.addEventListener("click", startCapture);
captureStopButton?.addEventListener("click", stopCapture);
captureIndicatorStop?.addEventListener("click", stopCapture);
captureClearButton?.addEventListener("click", clearCaptures);

if (captureConsent) {
  captureConsent.title = CAPTURE_CONSENT_STATEMENT;
}

captureFile?.addEventListener("change", () => {
  const file = captureFile.files?.[0] ?? null;
  selectedCapture = file
    ? {
        file,
        name: typeof file.name === "string" && file.name ? file.name : "selected capture",
        size: file.size,
      }
    : null;
  pendingReviewBytes = null;
  setFeedback(
    selectedCapture
      ? "Capture file selected. Nothing has been read, parsed, or uploaded."
      : "Capture selection cleared.",
    null,
  );
  render();
});

inventoryTarget?.addEventListener("input", () => {
  render();
});

render();
