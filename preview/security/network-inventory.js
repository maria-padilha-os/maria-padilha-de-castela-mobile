/* Castela Mobile local-network inventory contract.
 *
 * This module is deliberately dependency-free: no DOM, no timers, no network,
 * no storage, and no privileged API. It validates a target range, gates every
 * run behind an explicit authorization acknowledgement, and delegates
 * discovery to an injected provider. The provider is the only component that
 * may use Android public APIs or an explicit Termux/native helper.
 *
 * The contract never sweeps, opens raw sockets, probes ports, grabs banners,
 * brute-forces, exploits, or captures credentials. It only normalizes host,
 * address, and service-hint data that a local provider already observed.
 */

export const INVENTORY_ID = "com.castela.network-inventory";
export const INVENTORY_NAME = "Castela local-network inventory";

export const AUTHORIZATION_STATEMENT =
  "I own or am authorized to test this network, and I will inspect only devices I am permitted to test.";

export const ALLOWED_PROVIDER_KINDS = Object.freeze([
  "android-public-api",
  "termux-helper",
  "fixture",
]);

export const MAX_IPV4_TARGET_HOSTS = 1024;
export const MAX_IPV6_HOST_BITS = 64;
export const MAX_RESULTS = 512;
export const MAX_SERVICES_PER_HOST = 32;

export const SERVICE_HINTS = Object.freeze({
  22: "SSH",
  53: "DNS",
  67: "DHCP server",
  68: "DHCP client",
  80: "HTTP",
  123: "NTP",
  137: "NetBIOS name service",
  138: "NetBIOS datagram",
  139: "NetBIOS session",
  443: "HTTPS",
  445: "SMB file sharing",
  548: "AFP file sharing",
  554: "RTSP",
  631: "IPP printing",
  1900: "SSDP discovery",
  5353: "mDNS / DNS-SD",
  8080: "HTTP alternate",
  8443: "HTTPS alternate",
  9100: "Printer job queue",
});

const FORBIDDEN_PROVIDER_FLAGS = Object.freeze([
  "privileged",
  "root",
  "requiresRoot",
  "usesRoot",
  "rawSockets",
  "rawSocket",
  "credentialCapture",
  "credentialHarvesting",
  "bruteForce",
  "exploit",
  "packetCapture",
  "vpnService",
  "hiddenService",
]);

const PUBLIC_SCOPES = new Set([
  "public",
  "documentation",
  "benchmarking",
  "shared",
  "reserved",
]);

function reject(code, message) {
  return Object.freeze({ ok: false, code, message, target: null });
}

function parseIPv4(text) {
  if (typeof text !== "string") {
    return null;
  }
  const parts = text.split(".");
  if (parts.length !== 4) {
    return null;
  }
  const bytes = [];
  for (const part of parts) {
    // Reject leading zeroes so 010 cannot be read as an octal ambiguity.
    if (!/^(?:0|[1-9]\d{0,2})$/.test(part)) {
      return null;
    }
    const value = Number(part);
    if (!Number.isInteger(value) || value < 0 || value > 255) {
      return null;
    }
    bytes.push(value);
  }
  return {
    version: 4,
    bytes,
    groups: null,
    canonical: bytes.join("."),
    zone: null,
  };
}

function formatIPv6(groups) {
  let bestStart = -1;
  let bestLength = 0;
  for (let index = 0; index < groups.length; ) {
    if (groups[index] !== 0) {
      index += 1;
      continue;
    }
    let end = index;
    while (end < groups.length && groups[end] === 0) {
      end += 1;
    }
    const length = end - index;
    if (length >= 2 && length > bestLength) {
      bestStart = index;
      bestLength = length;
    }
    index = end;
  }

  const hex = groups.map((group) => group.toString(16));
  if (bestStart === -1) {
    return hex.join(":");
  }

  const head = hex.slice(0, bestStart).join(":");
  const tail = hex.slice(bestStart + bestLength).join(":");
  if (!head && !tail) {
    return "::";
  }
  if (!head) {
    return `::${tail}`;
  }
  if (!tail) {
    return `${head}::`;
  }
  return `${head}::${tail}`;
}

function parseIPv6(text) {
  if (typeof text !== "string") {
    return null;
  }
  let value = text.trim().toLowerCase();
  if (!value) {
    return null;
  }

  let zone = null;
  const zoneIndex = value.indexOf("%");
  if (zoneIndex !== -1) {
    zone = value.slice(zoneIndex + 1);
    value = value.slice(0, zoneIndex);
    if (!zone || !/^[a-z0-9_.-]+$/.test(zone)) {
      return null;
    }
  }
  if (!value || value.includes("%")) {
    return null;
  }

  const doubleIndex = value.indexOf("::");
  if (doubleIndex !== -1 && value.indexOf("::", doubleIndex + 2) !== -1) {
    return null;
  }

  const compressed = doubleIndex !== -1;
  const headText = compressed ? value.slice(0, doubleIndex) : value;
  const tailText = compressed ? value.slice(doubleIndex + 2) : "";

  function parseSide(side) {
    if (side === "") {
      return [];
    }
    const pieces = side.split(":");
    const groups = [];
    for (let index = 0; index < pieces.length; index += 1) {
      const piece = pieces[index];
      if (piece.includes(".")) {
        if (index !== pieces.length - 1) {
          return null;
        }
        const embedded = parseIPv4(piece);
        if (!embedded) {
          return null;
        }
        groups.push(
          (embedded.bytes[0] << 8) | embedded.bytes[1],
          (embedded.bytes[2] << 8) | embedded.bytes[3],
        );
      } else {
        if (!/^[0-9a-f]{1,4}$/.test(piece)) {
          return null;
        }
        groups.push(parseInt(piece, 16));
      }
    }
    return groups;
  }

  const head = parseSide(headText);
  const tail = parseSide(tailText);
  if (!head || !tail) {
    return null;
  }

  let groups;
  if (compressed) {
    const total = head.length + tail.length;
    // "::" must stand for at least one zero group.
    if (total > 7) {
      return null;
    }
    groups = [...head, ...Array(8 - total).fill(0), ...tail];
  } else {
    if (head.length !== 8) {
      return null;
    }
    groups = head;
  }
  if (groups.length !== 8) {
    return null;
  }

  return {
    version: 6,
    bytes: null,
    groups,
    canonical: formatIPv6(groups),
    zone,
  };
}

export function parseAddress(value) {
  if (typeof value !== "string") {
    return null;
  }
  const text = value.trim();
  if (!text) {
    return null;
  }
  return text.includes(":") ? parseIPv6(text) : parseIPv4(text);
}

function parsedToBigInt(parsed) {
  if (parsed.version === 4) {
    return (
      (BigInt(parsed.bytes[0]) << 24n) |
      (BigInt(parsed.bytes[1]) << 16n) |
      (BigInt(parsed.bytes[2]) << 8n) |
      BigInt(parsed.bytes[3])
    );
  }
  let value = 0n;
  for (const group of parsed.groups) {
    value = (value << 16n) | BigInt(group);
  }
  return value;
}

function bigIntToParsed(value, version) {
  if (version === 4) {
    const bytes = [
      Number((value >> 24n) & 0xffn),
      Number((value >> 16n) & 0xffn),
      Number((value >> 8n) & 0xffn),
      Number(value & 0xffn),
    ];
    return {
      version: 4,
      bytes,
      groups: null,
      canonical: bytes.join("."),
      zone: null,
    };
  }

  const groups = [];
  for (let shift = 112n; shift >= 0n; shift -= 16n) {
    groups.push(Number((value >> shift) & 0xffffn));
  }
  return {
    version: 6,
    bytes: null,
    groups,
    canonical: formatIPv6(groups),
    zone: null,
  };
}

function classifyParsed(parsed) {
  if (parsed.version === 4) {
    const [a, b, c] = parsed.bytes;
    if (a === 0) {
      return "unspecified";
    }
    if (a === 10) {
      return "private";
    }
    if (a === 172 && b >= 16 && b <= 31) {
      return "private";
    }
    if (a === 192 && b === 168) {
      return "private";
    }
    if (a === 169 && b === 254) {
      return "link-local";
    }
    if (a === 127) {
      return "loopback";
    }
    if (a >= 224 && a <= 239) {
      return "multicast";
    }
    if (a >= 240) {
      return "reserved";
    }
    if (a === 100 && b >= 64 && b <= 127) {
      return "shared";
    }
    if (a === 192 && b === 0 && c === 2) {
      return "documentation";
    }
    if (a === 198 && (b === 18 || b === 19)) {
      return "benchmarking";
    }
    if (a === 198 && b === 51 && c === 100) {
      return "documentation";
    }
    if (a === 203 && b === 0 && c === 113) {
      return "documentation";
    }
    return "public";
  }

  const groups = parsed.groups;
  const isMapped =
    groups[0] === 0 &&
    groups[1] === 0 &&
    groups[2] === 0 &&
    groups[3] === 0 &&
    groups[4] === 0 &&
    groups[5] === 0xffff;
  if (isMapped) {
    const bytes = [
      (groups[6] >> 8) & 0xff,
      groups[6] & 0xff,
      (groups[7] >> 8) & 0xff,
      groups[7] & 0xff,
    ];
    return classifyParsed({
      version: 4,
      bytes,
      groups: null,
      canonical: bytes.join("."),
      zone: null,
    });
  }

  if (groups.every((group) => group === 0)) {
    return "unspecified";
  }
  if (groups.slice(0, 7).every((group) => group === 0) && groups[7] === 1) {
    return "loopback";
  }
  if ((groups[0] & 0xfe00) === 0xfc00) {
    return "private";
  }
  if ((groups[0] & 0xffc0) === 0xfe80) {
    return "link-local";
  }
  if ((groups[0] & 0xff00) === 0xff00) {
    return "multicast";
  }
  if ((groups[0] & 0xffc0) === 0xfec0) {
    // Deprecated IPv6 site-local. It is not ULA or link-local.
    return "reserved";
  }
  if (groups[0] === 0x2001 && groups[1] === 0x0db8) {
    return "documentation";
  }
  return "public";
}

function scopeAllowed(scope, allowLoopback) {
  return (
    scope === "private" ||
    scope === "link-local" ||
    (allowLoopback && scope === "loopback")
  );
}

export function classifyAddress(value, { allowLoopback = true } = {}) {
  const parsed = parseAddress(value);
  if (!parsed) {
    return Object.freeze({
      ok: false,
      code: "invalid-address",
      message: "Enter a valid IPv4 or IPv6 address.",
      address: null,
      canonical: null,
      scope: null,
      allowed: false,
      parsed: null,
    });
  }
  const scope = classifyParsed(parsed);
  return Object.freeze({
    ok: true,
    code: "ok",
    message: null,
    address: value,
    canonical: parsed.canonical,
    scope,
    allowed: scopeAllowed(scope, allowLoopback),
    parsed,
  });
}

function targetContains(target, parsed) {
  if (!target || parsed.version !== target.version) {
    return false;
  }
  const first = parseAddress(target.first);
  const last = parseAddress(target.last);
  if (!first || !last || first.version !== parsed.version) {
    return false;
  }
  const value = parsedToBigInt(parsed);
  return (
    value >= parsedToBigInt(first) && value <= parsedToBigInt(last)
  );
}

export function validateTarget(input, options = {}) {
  const allowLoopback = options.allowLoopback !== false;
  const maxIPv4Hosts =
    Number.isInteger(options.maxIPv4Hosts) && options.maxIPv4Hosts > 0
      ? Math.min(options.maxIPv4Hosts, MAX_IPV4_TARGET_HOSTS)
      : MAX_IPV4_TARGET_HOSTS;

  if (typeof input !== "string" || input.trim() === "") {
    return reject(
      "invalid-target",
      "Enter a private or link-local CIDR range, for example 192.168.1.0/24.",
    );
  }

  const text = input.trim();
  const slash = text.indexOf("/");
  if (slash !== -1 && text.indexOf("/", slash + 1) !== -1) {
    return reject("invalid-target", "A target may contain only one CIDR prefix.");
  }

  const addressText = slash === -1 ? text : text.slice(0, slash);
  const prefixText = slash === -1 ? null : text.slice(slash + 1);
  if (!addressText || (prefixText !== null && prefixText === "")) {
    return reject("invalid-target", "A target needs an address and an optional prefix.");
  }
  if (addressText.includes("%")) {
    return reject(
      "invalid-target",
      "CIDR targets cannot include an IPv6 zone identifier.",
    );
  }

  const parsed = parseAddress(addressText);
  if (!parsed) {
    return reject("invalid-target", "Enter a valid IPv4 or IPv6 address.");
  }

  const bits = parsed.version === 4 ? 32 : 128;
  let prefix = bits;
  if (prefixText !== null) {
    if (!/^(?:0|[1-9]\d{0,2})$/.test(prefixText)) {
      return reject("invalid-prefix", "The CIDR prefix must be a whole number.");
    }
    prefix = Number(prefixText);
    if (prefix < 0 || prefix > bits) {
      return reject(
        "invalid-prefix",
        `The CIDR prefix for IPv${parsed.version} must be between 0 and ${bits}.`,
      );
    }
  }

  const hostBits = bits - prefix;
  const hostMask = hostBits === 0 ? 0n : (1n << BigInt(hostBits)) - 1n;
  const value = parsedToBigInt(parsed);
  const firstValue = value & ~hostMask;
  const lastValue = firstValue | hostMask;
  const first = bigIntToParsed(firstValue, parsed.version);
  const last = bigIntToParsed(lastValue, parsed.version);
  const scope = classifyParsed(first);
  const lastScope = classifyParsed(last);

  if (scope !== lastScope) {
    return reject(
      "public-range",
      "That range crosses a private or link-local boundary. Choose a range entirely inside one private/link-local block.",
    );
  }

  if (!scopeAllowed(scope, allowLoopback)) {
    if (PUBLIC_SCOPES.has(scope)) {
      return reject(
        "public-range",
        "Public, documentation, shared, reserved, multicast, and unspecified ranges are refused. Use a private or link-local range.",
      );
    }
    return reject(
      "not-allowed-range",
      "Only private, link-local, and loopback ranges are available. Public ranges are refused.",
    );
  }

  if (parsed.version === 4 && hostBits > 10) {
    return reject(
      "range-too-large",
      `IPv4 inventory is limited to ${maxIPv4Hosts} addresses. Choose a narrower private range, such as /24.`,
    );
  }
  if (parsed.version === 6 && hostBits > MAX_IPV6_HOST_BITS) {
    return reject(
      "range-too-large",
      "IPv6 inventory is limited to /64 or narrower. The provider reads the neighbor table; it does not sweep.",
    );
  }

  const addressCount =
    parsed.version === 4 ? 2 ** hostBits : null;
  const addressCountText =
    parsed.version === 4
      ? `${addressCount} address${addressCount === 1 ? "" : "es"}`
      : hostBits === 0
        ? "1 address"
        : `2^${hostBits} addresses (neighbor-table scope, no sweep)`;

  return Object.freeze({
    ok: true,
    code: "ok",
    message: null,
    target: Object.freeze({
      input: text,
      canonical: `${first.canonical}/${prefix}`,
      version: parsed.version,
      prefix,
      first: first.canonical,
      last: last.canonical,
      scope,
      addressCount,
      addressCountText,
      neighborTable: parsed.version === 6,
      sweep: false,
    }),
  });
}

export function serviceHintFor(port) {
  const value = Number(port);
  if (!Number.isInteger(value) || value < 1 || value > 65535) {
    return "Unclassified service";
  }
  return SERVICE_HINTS[value] ?? "Unclassified service";
}

function sanitizeLabel(value, maxLength = 253) {
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

function normalizeServices(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  const seen = new Set();
  const services = [];
  for (const item of value) {
    let port = null;
    let protocol = "unknown";

    if (typeof item === "number" || typeof item === "string") {
      port = Number(item);
    } else if (item && typeof item === "object" && !Array.isArray(item)) {
      port = Number(item.port ?? item.number);
      const rawProtocol = item.protocol ?? item.proto;
      if (typeof rawProtocol === "string") {
        protocol = rawProtocol.trim().toLowerCase();
      }
    }

    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      continue;
    }
    if (protocol !== "tcp" && protocol !== "udp") {
      protocol = "unknown";
    }

    const key = `${protocol}:${port}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    services.push(
      Object.freeze({
        port,
        protocol,
        hint: serviceHintFor(port),
      }),
    );
    if (services.length >= MAX_SERVICES_PER_HOST) {
      break;
    }
  }
  return services;
}

function displayAddress(parsed) {
  return parsed.zone ? `${parsed.canonical}%${parsed.zone}` : parsed.canonical;
}

function normalizeHost(raw, target) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return [];
  }

  const rawAddresses = [];
  if (typeof raw.address === "string") {
    rawAddresses.push(raw.address);
  }
  if (typeof raw.ip === "string") {
    rawAddresses.push(raw.ip);
  }
  if (Array.isArray(raw.addresses)) {
    for (const value of raw.addresses) {
      if (typeof value === "string") {
        rawAddresses.push(value);
      }
    }
  }

  const hostname = sanitizeLabel(raw.hostname ?? raw.host ?? raw.name);
  const services = normalizeServices(raw.services ?? raw.openPorts ?? raw.ports);
  const records = [];
  const seen = new Set();

  for (const rawAddress of rawAddresses) {
    const parsed = parseAddress(rawAddress);
    if (!parsed) {
      continue;
    }
    const scope = classifyParsed(parsed);
    if (!scopeAllowed(scope, true)) {
      continue;
    }
    if (!targetContains(target, parsed)) {
      continue;
    }
    if (seen.has(parsed.canonical)) {
      continue;
    }
    seen.add(parsed.canonical);
    records.push({
      host: hostname ?? "Unknown host",
      address: displayAddress(parsed),
      services: services.map((service) => ({ ...service })),
    });
  }

  return records;
}

function cloneHosts(hosts) {
  return hosts.map((host) => ({
    host: host.host,
    address: host.address,
    services: host.services.map((service) => ({ ...service })),
  }));
}

function freezeHosts(hosts) {
  return Object.freeze(
    hosts.map((host) =>
      Object.freeze({
        host: host.host,
        address: host.address,
        services: Object.freeze(
          host.services.map((service) => Object.freeze({ ...service })),
        ),
      }),
    ),
  );
}

function inspectProviderValue(provider) {
  if (!provider || typeof provider !== "object" || Array.isArray(provider)) {
    return Object.freeze({
      ok: false,
      code: "provider-missing",
      message:
        "No local network-inventory provider is configured. Inject an Android-safe or explicit Termux/native provider.",
      kind: null,
      label: null,
      provider: null,
      discover: null,
    });
  }

  for (const flag of FORBIDDEN_PROVIDER_FLAGS) {
    if (provider[flag]) {
      return Object.freeze({
        ok: false,
        code: "unsafe-provider",
        message: `The provider declares ${flag}. This inventory refuses root, raw sockets, credential capture, brute force, exploitation, packet capture, and hidden services.`,
        kind: null,
        label: null,
        provider: null,
        discover: null,
      });
    }
  }

  if (
    typeof provider.kind !== "string" ||
    !ALLOWED_PROVIDER_KINDS.includes(provider.kind)
  ) {
    return Object.freeze({
      ok: false,
      code: "unapproved-provider",
      message: `The provider kind must be one of: ${ALLOWED_PROVIDER_KINDS.join(", ")}.`,
      kind: null,
      label: null,
      provider: null,
      discover: null,
    });
  }

  const discover = provider.discover ?? provider.inventory ?? provider.scan;
  if (typeof discover !== "function") {
    return Object.freeze({
      ok: false,
      code: "provider-missing",
      message:
        "The local provider has no discover, inventory, or scan function.",
      kind: provider.kind,
      label: sanitizeLabel(provider.label, 80) ?? provider.kind,
      provider: null,
      discover: null,
    });
  }

  return Object.freeze({
    ok: true,
    code: "ok",
    message: null,
    kind: provider.kind,
    label: sanitizeLabel(provider.label, 80) ?? provider.kind,
    provider,
    discover,
  });
}

export function inspectProvider(provider) {
  try {
    return inspectProviderValue(provider);
  } catch (error) {
    const detail =
      error instanceof Error && error.message ? error.message : String(error);
    return Object.freeze({
      ok: false,
      code: "provider-inspection-failed",
      message: `The local provider could not be inspected safely (${detail}).`,
      kind: null,
      label: null,
      provider: null,
      discover: null,
    });
  }
}

/**
 * Create an in-memory inventory session. Construction does not run a provider,
 * read a file, or touch the network. Only authorize() and scan() have effects.
 */
export function createNetworkInventory({
  provider = null,
  now = () => new Date().toISOString(),
} = {}) {
  const providerInfo = inspectProvider(provider);

  let authorized = false;
  let session = null;
  let hosts = [];
  let lastTarget = null;
  let lastFinishedAt = null;
  let lastStoppedAt = null;
  let sessionSequence = 0;

  function snapshot() {
    return Object.freeze({
      id: INVENTORY_ID,
      authorized,
      session: session ? Object.freeze({ ...session }) : null,
      provider: providerInfo.ok
        ? Object.freeze({ kind: providerInfo.kind, label: providerInfo.label })
        : null,
      providerStatus: Object.freeze({
        ok: providerInfo.ok,
        code: providerInfo.code,
        message: providerInfo.message,
      }),
      target: lastTarget ? Object.freeze({ ...lastTarget }) : null,
      hosts: freezeHosts(hosts),
      lastFinishedAt,
      lastStoppedAt,
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

  function authorize({ acknowledged = false } = {}) {
    if (authorized) {
      return { ok: true, code: "already-authorized", state: snapshot() };
    }
    if (acknowledged !== true) {
      return {
        ok: false,
        code: "acknowledgement-required",
        message: AUTHORIZATION_STATEMENT,
        state: snapshot(),
      };
    }

    sessionSequence += 1;
    session = {
      id: `inventory-${sessionSequence}`,
      authorizedAt: now(),
      statement: AUTHORIZATION_STATEMENT,
      scope: "user-authorized private/link-local network",
    };
    authorized = true;
    lastStoppedAt = null;
    return { ok: true, code: "authorized", state: snapshot() };
  }

  function stopAndClear() {
    const wasAuthorized = authorized;
    authorized = false;
    session = null;
    hosts = [];
    lastTarget = null;
    lastFinishedAt = null;
    lastStoppedAt = now();
    return {
      ok: true,
      code: "stopped",
      cleared: true,
      wasAuthorized,
      state: snapshot(),
    };
  }

  function scan(input, { maxHosts = MAX_RESULTS } = {}) {
    if (!authorized) {
      return fail(
        "not-authorized",
        "Authorize lab mode and confirm you own or are authorized to test this network before any inventory runs.",
      );
    }

    const validated = validateTarget(input);
    if (!validated.ok) {
      return fail(validated.code, validated.message);
    }

    if (!providerInfo.ok) {
      return fail(providerInfo.code, providerInfo.message);
    }

    const target = validated.target;
    const context = Object.freeze({
      target,
      authorized: true,
      acknowledgement: true,
      session: session.id,
      mode: target.neighborTable ? "neighbor-table" : "local-inventory",
    });

    let raw;
    try {
      raw = providerInfo.discover.call(providerInfo.provider, context);
    } catch (error) {
      const detail =
        error instanceof Error && error.message ? error.message : String(error);
      return fail(
        "scan-failed",
        `The local provider failed safely: ${detail}`,
      );
    }

    if (raw && typeof raw.then === "function") {
      return fail(
        "async-provider-unsupported",
        "This contract expects a synchronous local provider. Resolve the provider result before calling scan().",
      );
    }

    let candidates;
    if (Array.isArray(raw)) {
      candidates = raw;
    } else if (raw && typeof raw === "object" && Array.isArray(raw.hosts)) {
      candidates = raw.hosts;
    } else {
      return fail(
        "invalid-provider-result",
        "The local provider returned no host array. Nothing was stored.",
      );
    }

    const limit =
      Number.isInteger(maxHosts) && maxHosts > 0
        ? Math.min(maxHosts, MAX_RESULTS)
        : MAX_RESULTS;

    const normalized = [];
    const seen = new Set();
    let ignored = 0;
    let truncated = raw && raw.truncated === true;

    for (const candidate of candidates) {
      if (normalized.length >= limit) {
        truncated = true;
        break;
      }
      const records = normalizeHost(candidate, target);
      if (records.length === 0) {
        ignored += 1;
        continue;
      }
      for (const record of records) {
        if (seen.has(record.address)) {
          continue;
        }
        if (normalized.length >= limit) {
          truncated = true;
          break;
        }
        seen.add(record.address);
        normalized.push(record);
      }
    }

    normalized.sort((left, right) => {
      const leftParsed = parseAddress(left.address.split("%")[0]);
      const rightParsed = parseAddress(right.address.split("%")[0]);
      if (!leftParsed || !rightParsed) {
        return left.address.localeCompare(right.address);
      }
      if (leftParsed.version !== rightParsed.version) {
        return leftParsed.version - rightParsed.version;
      }
      const leftValue = parsedToBigInt(leftParsed);
      const rightValue = parsedToBigInt(rightParsed);
      if (leftValue < rightValue) {
        return -1;
      }
      if (leftValue > rightValue) {
        return 1;
      }
      return 0;
    });

    hosts = normalized;
    lastTarget = target;
    lastFinishedAt = now();

    return {
      ok: true,
      code: "complete",
      target,
      hosts: cloneHosts(hosts),
      truncated,
      ignored,
      finishedAt: lastFinishedAt,
      state: snapshot(),
    };
  }

  return Object.freeze({
    id: INVENTORY_ID,
    authorize,
    stopAndClear,
    scan,
    snapshot,
    hasProvider: () => providerInfo.ok,
    getProviderStatus: () =>
      Object.freeze({
        ok: providerInfo.ok,
        code: providerInfo.code,
        message: providerInfo.message,
        kind: providerInfo.kind,
        label: providerInfo.label,
      }),
    listHosts: () => freezeHosts(hosts),
  });
}
