/* Castela Mobile pcap capture and offline review contract.
 *
 * This module is deliberately dependency-free: no DOM, no timers, no network,
 * no storage, and no privileged API. The browser front-end binds it to the
 * page, and the Python test suite exercises it through Node.
 *
 * Live capture is delegated to an explicitly injected provider:
 *   - "android-vpn-service": the future signed app's user-started VpnService;
 *   - "non-root-helper": an explicit user-installed helper adapter;
 *   - "fixture": tests and offline previews only.
 *
 * Construction never starts a capture. Authorization, a separate capture
 * consent, and an explicit start call are all required. The contract refuses
 * root, raw sockets, hidden/background capture, and upload providers. It keeps
 * a persistent indicator state while a capture is active and delegates file
 * deletion to the provider on an explicit clear request.
 */

import {
  MAX_PACKETS,
  PCAP_REVIEW_ID,
  summarizeCapture,
} from "./pcap-format.js";

export {
  MAX_ENDPOINTS,
  MAX_PACKETS,
  MAX_PORTS,
  MAX_CONVERSATIONS,
  PCAP_REVIEW_ID,
  SENSITIVE_PAYLOAD_WARNING,
  summarizeCapture,
} from "./pcap-format.js";

export const CAPTURE_ID = "com.castela.pcap-capture";
export const CAPTURE_NAME = "Castela pcap capture and review";

export const CAPTURE_AUTHORIZATION_STATEMENT =
  "I own or am authorized to capture traffic on this network, and I will capture only traffic I am permitted to inspect.";

export const CAPTURE_CONSENT_STATEMENT =
  "I understand that this capture may contain passwords, tokens, messages, and third-party personal data, and that it will stay local until I delete it.";

export const CAPTURE_PROVIDER_KINDS = Object.freeze([
  "android-vpn-service",
  "non-root-helper",
  "fixture",
]);

export const FORBIDDEN_CAPTURE_FLAGS = Object.freeze([
  "privileged",
  "root",
  "requiresRoot",
  "usesRoot",
  "rawSockets",
  "rawSocket",
  "hiddenService",
  "backgroundCapture",
  "autoStart",
  "automaticCapture",
  "upload",
  "uploads",
  "remoteUpload",
  "telemetry",
  "cloudSync",
]);

export const MAX_REVIEW_BYTES = 64 * 1024 * 1024;
export const MAX_CAPTURE_LABEL = 80;

function sanitizeLabel(value, maxLength = MAX_CAPTURE_LABEL) {
  if (typeof value !== "string") {
    return null;
  }
  const cleaned = value
    .replace(/[\u0000-\u001f\u007f]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) {
    return null;
  }
  return cleaned.slice(0, maxLength);
}

function byteLengthOf(input) {
  if (input instanceof Uint8Array) {
    return input.byteLength;
  }
  if (typeof ArrayBuffer !== "undefined" && input instanceof ArrayBuffer) {
    return input.byteLength;
  }
  if (
    typeof ArrayBuffer !== "undefined" &&
    ArrayBuffer.isView &&
    ArrayBuffer.isView(input)
  ) {
    return input.byteLength;
  }
  if (Array.isArray(input)) {
    return input.length;
  }
  return null;
}

function inspectProviderValue(provider) {
  if (!provider || typeof provider !== "object" || Array.isArray(provider)) {
    return Object.freeze({
      ok: false,
      code: "provider-missing",
      message:
        "No live capture provider is configured. Review still works on a user-selected file; live capture needs a user-started VpnService or an explicit non-root helper adapter.",
      kind: null,
      label: null,
      provider: null,
      start: null,
      stop: null,
      clear: null,
    });
  }

  for (const flag of FORBIDDEN_CAPTURE_FLAGS) {
    if (provider[flag]) {
      return Object.freeze({
        ok: false,
        code: "unsafe-provider",
        message: `The capture provider declares ${flag}. This contract refuses privileged or root capture, raw sockets, hidden or automatic capture, and upload or telemetry paths.`,
        kind: null,
        label: null,
        provider: null,
        start: null,
        stop: null,
        clear: null,
      });
    }
  }

  if (
    typeof provider.kind !== "string" ||
    !CAPTURE_PROVIDER_KINDS.includes(provider.kind)
  ) {
    return Object.freeze({
      ok: false,
      code: "unapproved-provider",
      message: `The capture provider kind must be one of: ${CAPTURE_PROVIDER_KINDS.join(
        ", ",
      )}.`,
      kind: null,
      label: null,
      provider: null,
      start: null,
      stop: null,
      clear: null,
    });
  }

  if (
    provider.persistentIndicator === false ||
    provider.persistentNotification === false
  ) {
    return Object.freeze({
      ok: false,
      code: "indicator-required",
      message:
        "A live capture provider must keep a persistent, user-visible indicator while capture is running.",
      kind: null,
      label: null,
      provider: null,
      start: null,
      stop: null,
      clear: null,
    });
  }

  if (typeof provider.start !== "function") {
    return Object.freeze({
      ok: false,
      code: "provider-missing",
      message: "The live capture provider has no start function.",
      kind: provider.kind,
      label: sanitizeLabel(provider.label) ?? provider.kind,
      provider: null,
      start: null,
      stop: null,
      clear: null,
    });
  }

  if (typeof provider.stop !== "function") {
    return Object.freeze({
      ok: false,
      code: "provider-missing",
      message:
        "The live capture provider has no stop function, so access cannot be revoked cleanly.",
      kind: provider.kind,
      label: sanitizeLabel(provider.label) ?? provider.kind,
      provider: null,
      start: null,
      stop: null,
      clear: null,
    });
  }

  return Object.freeze({
    ok: true,
    code: "ok",
    message: null,
    kind: provider.kind,
    label: sanitizeLabel(provider.label) ?? provider.kind,
    provider,
    start: provider.start,
    stop: provider.stop,
    clear: typeof provider.clear === "function" ? provider.clear : null,
  });
}

export function inspectCaptureProvider(provider) {
  try {
    return inspectProviderValue(provider);
  } catch (error) {
    const detail =
      error instanceof Error && error.message ? error.message : String(error);
    return Object.freeze({
      ok: false,
      code: "provider-inspection-failed",
      message: `The capture provider could not be inspected safely (${detail}).`,
      kind: null,
      label: null,
      provider: null,
      start: null,
      stop: null,
      clear: null,
    });
  }
}

/**
 * Create an in-memory capture and review session. Construction does not start
 * a capture, read a file, touch the network, or start a timer.
 */
export function createPcapCapture({
  provider = null,
  now = () => new Date().toISOString(),
  maxReviewBytes = MAX_REVIEW_BYTES,
  maxPackets = MAX_PACKETS,
} = {}) {
  const providerInfo = inspectCaptureProvider(provider);
  const reviewLimit =
    Number.isInteger(maxReviewBytes) && maxReviewBytes > 0
      ? maxReviewBytes
      : MAX_REVIEW_BYTES;
  const packetLimit =
    Number.isInteger(maxPackets) && maxPackets > 0
      ? Math.min(maxPackets, MAX_PACKETS)
      : MAX_PACKETS;

  let authorized = false;
  let session = null;
  let sessionSequence = 0;
  let state = "idle";
  let capture = null;
  let captureSequence = 0;
  let review = null;
  let indicator = Object.freeze({
    visible: false,
    persistent: true,
    label: "Capture stopped",
    detail: "No live capture is running.",
  });
  let lastStartedAt = null;
  let lastStoppedAt = null;
  let lastClearedAt = null;
  let lastError = null;

  function snapshot() {
    return Object.freeze({
      id: CAPTURE_ID,
      authorized,
      session: session ? Object.freeze({ ...session }) : null,
      state,
      capture: capture ? Object.freeze({ ...capture }) : null,
      provider: providerInfo.ok
        ? Object.freeze({ kind: providerInfo.kind, label: providerInfo.label })
        : null,
      providerStatus: Object.freeze({
        ok: providerInfo.ok,
        code: providerInfo.code,
        message: providerInfo.message,
      }),
      canClear: providerInfo.ok && typeof providerInfo.clear === "function",
      indicator: Object.freeze({ ...indicator }),
      review: review
        ? Object.freeze({
            fileName: review.fileName,
            size: review.size,
            reviewedAt: review.reviewedAt,
            summary: review.summary,
          })
        : null,
      lastStartedAt,
      lastStoppedAt,
      lastClearedAt,
      lastError,
    });
  }

  function fail(code, message) {
    return {
      ok: false,
      code,
      message,
      state: snapshot(),
    };
  }

  function hideIndicator(detail = "No live capture is running.") {
    indicator = Object.freeze({
      visible: false,
      persistent: true,
      label: "Capture stopped",
      detail,
    });
  }

  function authorize({ acknowledged = false } = {}) {
    if (authorized) {
      return { ok: true, code: "already-authorized", state: snapshot() };
    }
    if (acknowledged !== true) {
      return {
        ok: false,
        code: "acknowledgement-required",
        message: CAPTURE_AUTHORIZATION_STATEMENT,
        state: snapshot(),
      };
    }

    sessionSequence += 1;
    session = {
      id: `capture-session-${sessionSequence}`,
      authorizedAt: now(),
      statement: CAPTURE_AUTHORIZATION_STATEMENT,
      scope: "user-authorized packet capture and offline review",
    };
    authorized = true;
    lastStoppedAt = null;
    return { ok: true, code: "authorized", state: snapshot() };
  }

  function start({ acknowledged = false, label = null } = {}) {
    if (!authorized) {
      return fail(
        "not-authorized",
        "Authorize capture access and confirm you own or are authorized to inspect this network before starting a capture.",
      );
    }
    if (acknowledged !== true) {
      return fail("consent-required", CAPTURE_CONSENT_STATEMENT);
    }
    if (state === "capturing" && capture) {
      return {
        ok: true,
        code: "already-capturing",
        capture: Object.freeze({ ...capture }),
        indicator: Object.freeze({ ...indicator }),
        state: snapshot(),
      };
    }
    if (!providerInfo.ok) {
      return fail(providerInfo.code, providerInfo.message);
    }

    const context = Object.freeze({
      authorized: true,
      consent: true,
      persistentNotification: true,
      session: session.id,
      statement: CAPTURE_CONSENT_STATEMENT,
      label: sanitizeLabel(label),
    });

    let raw;
    try {
      raw = providerInfo.start.call(providerInfo.provider, context);
    } catch (error) {
      const detail =
        error instanceof Error && error.message ? error.message : String(error);
      lastError = detail;
      hideIndicator("Capture did not start.");
      state = "error";
      return fail(
        "capture-start-failed",
        `The capture provider failed safely: ${detail}`,
      );
    }

    if (raw && typeof raw.then === "function") {
      lastError = "async provider";
      hideIndicator("Capture state is unknown.");
      state = "error";
      return fail(
        "async-provider-unsupported",
        "This contract expects a synchronous capture provider. Start the capture in the app service and report its status synchronously.",
      );
    }

    if (raw === false || (raw && raw.started === false)) {
      const reason =
        raw && typeof raw.reason === "string" && raw.reason.trim()
          ? raw.reason.trim()
          : "The capture provider refused to start.";
      lastError = reason;
      hideIndicator("Capture was refused.");
      state = "idle";
      return fail("capture-refused", reason);
    }

    captureSequence += 1;
    const captureId =
      raw && typeof raw.id === "string" && raw.id.trim()
        ? sanitizeLabel(raw.id)
        : `capture-${captureSequence}`;
    const captureLabel =
      sanitizeLabel(raw && raw.label) ??
      sanitizeLabel(label) ??
      "Live packet capture";
    capture = {
      id: captureId,
      providerKind: providerInfo.kind,
      providerLabel: providerInfo.label,
      label: captureLabel,
      startedAt: now(),
    };
    state = "capturing";
    lastStartedAt = capture.startedAt;
    lastError = null;
    indicator = Object.freeze({
      visible: true,
      persistent: true,
      label: "Capture active",
      detail: `${captureLabel} is running. A persistent indicator must stay visible until you press Stop capture.`,
    });

    return {
      ok: true,
      code: "capturing",
      capture: Object.freeze({ ...capture }),
      indicator: Object.freeze({ ...indicator }),
      state: snapshot(),
    };
  }

  function stop() {
    if (state !== "capturing" || !capture) {
      return {
        ok: true,
        code: "not-capturing",
        stopped: false,
        state: snapshot(),
      };
    }

    const active = capture;
    let stopFailure = null;
    if (providerInfo.ok) {
      try {
        const raw = providerInfo.stop.call(providerInfo.provider, {
          capture: Object.freeze({ ...active }),
          session: session ? session.id : null,
          reason: "user-stop",
        });
        if (raw && typeof raw.then === "function") {
          stopFailure =
            "The capture provider returned an asynchronous stop result; local capture state was cleared.";
        } else if (raw === false || (raw && raw.stopped === false)) {
          stopFailure =
            "The capture provider reported that it did not stop; local indicator state was cleared.";
        }
      } catch (error) {
        const detail =
          error instanceof Error && error.message ? error.message : String(error);
        stopFailure = `The capture provider failed safely while stopping: ${detail}`;
      }
    }

    capture = null;
    state = "stopped";
    lastStoppedAt = now();
    hideIndicator("Capture stopped. The app must remove its persistent notification.");
    if (stopFailure) {
      lastError = stopFailure;
      return {
        ok: false,
        code: "stop-failed",
        message: stopFailure,
        stopped: true,
        state: snapshot(),
      };
    }

    lastError = null;
    return {
      ok: true,
      code: "stopped",
      stopped: true,
      state: snapshot(),
    };
  }

  function clearCaptures({ confirmed = false } = {}) {
    if (confirmed !== true) {
      return {
        ...fail(
          "confirmation-required",
          "Clearing capture files requires an explicit confirmation.",
        ),
        cleared: false,
        reviewCleared: false,
      };
    }
    if (state === "capturing") {
      return {
        ...fail(
          "capture-active",
          "Stop the live capture before clearing capture files.",
        ),
        cleared: false,
        reviewCleared: false,
      };
    }

    const hadReview = review !== null;
    if (!providerInfo.ok) {
      review = null;
      return {
        ok: false,
        code: providerInfo.code,
        message: providerInfo.message,
        cleared: false,
        reviewCleared: hadReview,
        state: snapshot(),
      };
    }
    if (typeof providerInfo.clear !== "function") {
      review = null;
      return {
        ok: false,
        code: "clear-unavailable",
        message:
          "The capture provider does not expose a clear function, so captured files cannot be verified as deleted.",
        cleared: false,
        reviewCleared: hadReview,
        state: snapshot(),
      };
    }

    try {
      const raw = providerInfo.clear.call(providerInfo.provider, {
        confirmDelete: true,
        session: session ? session.id : null,
        reason: "user-clear",
      });
      if (raw && typeof raw.then === "function") {
        review = null;
        return {
          ok: false,
          code: "async-provider-unsupported",
          message:
            "This contract expects a synchronous clear result; review data was cleared locally.",
          cleared: false,
          reviewCleared: hadReview,
          state: snapshot(),
        };
      }
      if (raw === false || (raw && raw.cleared === false)) {
        review = null;
        return {
          ok: false,
          code: "clear-failed",
          message:
            "The capture provider reported that it did not clear the captures; review data was cleared locally.",
          cleared: false,
          reviewCleared: hadReview,
          state: snapshot(),
        };
      }
    } catch (error) {
      review = null;
      const detail =
        error instanceof Error && error.message ? error.message : String(error);
      return {
        ok: false,
        code: "clear-failed",
        message: `The capture provider failed safely while clearing: ${detail}`,
        cleared: false,
        reviewCleared: hadReview,
        state: snapshot(),
      };
    }

    review = null;
    lastClearedAt = now();
    lastError = null;
    return {
      ok: true,
      code: "cleared",
      cleared: true,
      reviewCleared: hadReview,
      state: snapshot(),
    };
  }

  function reviewCapture(
    input,
    { fileName = null, size = null, maxPackets: packetOption = packetLimit } = {},
  ) {
    if (!authorized) {
      return fail(
        "not-authorized",
        "Authorize capture access before reviewing a capture file.",
      );
    }

    const length = byteLengthOf(input);
    if (length !== null && length > reviewLimit) {
      return fail(
        "capture-too-large",
        `The selected capture is larger than the local review limit of ${reviewLimit} bytes. Choose a smaller file or review it with the explicit desktop helper.`,
      );
    }

    const summary = summarizeCapture(input, { maxPackets: packetOption });
    if (!summary.ok) {
      return {
        ok: false,
        code: summary.code,
        message: summary.message,
        state: snapshot(),
      };
    }

    const reviewedAt = now();
    review = Object.freeze({
      fileName: sanitizeLabel(fileName) ?? "selected capture",
      size:
        typeof size === "number" && Number.isFinite(size) && size >= 0
          ? size
          : length ?? summary.capturedBytes,
      reviewedAt,
      summary,
    });

    return {
      ok: true,
      code: "reviewed",
      summary,
      review: snapshot().review,
      state: snapshot(),
    };
  }

  function clearReview() {
    const cleared = review !== null;
    review = null;
    return {
      ok: true,
      code: cleared ? "review-cleared" : "review-empty",
      cleared,
      state: snapshot(),
    };
  }

  function stopAndClear({ clearProvider = true } = {}) {
    const wasAuthorized = authorized;
    const wasCapturing = state === "capturing";
    let stopResult = null;
    if (wasCapturing) {
      stopResult = stop();
    }

    let clearResult = null;
    if (clearProvider && providerInfo.ok && typeof providerInfo.clear === "function") {
      clearResult = clearCaptures({ confirmed: true });
    } else {
      const hadReview = review !== null;
      review = null;
      clearResult = {
        ok: true,
        code: "cleared-local",
        cleared: false,
        reviewCleared: hadReview,
      };
    }

    authorized = false;
    session = null;
    review = null;
    capture = null;
    state = "stopped";
    lastStoppedAt = now();
    hideIndicator("Capture stopped and session access revoked.");

    const ok = (stopResult === null || stopResult.ok) && clearResult.ok;
    return {
      ok,
      code: ok ? "stopped-and-cleared" : "stopped-with-clear-failure",
      cleared: clearResult.cleared === true,
      reviewCleared:
        clearResult.reviewCleared === true || clearResult.cleared === true,
      wasAuthorized,
      wasCapturing,
      message: ok
        ? "Capture access was revoked, the indicator was cleared, and capture data was cleared on request."
        : clearResult.message ?? stopResult?.message ?? "Capture data could not be fully cleared.",
      state: snapshot(),
    };
  }

  return Object.freeze({
    id: CAPTURE_ID,
    authorize,
    start,
    stop,
    clearCaptures,
    reviewCapture,
    clearReview,
    stopAndClear,
    revokeAccess: stopAndClear,
    snapshot,
    hasProvider: () => providerInfo.ok,
    canClear: () => providerInfo.ok && typeof providerInfo.clear === "function",
    getProviderStatus: () =>
      Object.freeze({
        ok: providerInfo.ok,
        code: providerInfo.code,
        message: providerInfo.message,
        kind: providerInfo.kind,
        label: providerInfo.label,
      }),
    getReviewId: () => PCAP_REVIEW_ID,
  });
}
