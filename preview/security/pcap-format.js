/* Castela Mobile offline pcap/pcapng summary contract.
 *
 * This module is deliberately dependency-free: no DOM, no timers, no network,
 * no storage, and no privileged API. It reads bytes that the caller explicitly
 * supplies, extracts only packet metadata, and never returns payload contents.
 *
 * Supported inputs:
 *   - classic pcap, microsecond and nanosecond, both byte orders;
 *   - pcapng, both byte orders, with IDB timestamp resolution.
 *
 * The summary keeps addresses, ports, protocol names, counters, and size
 * totals. It never keeps usernames, passwords, tokens, banners, or raw frames.
 */

export const PCAP_REVIEW_ID = "com.castela.pcap-review";
export const MAX_PACKETS = 100000;
export const MAX_CONVERSATIONS = 20;
export const MAX_ENDPOINTS = 20;
export const MAX_PORTS = 20;

export const SENSITIVE_PAYLOAD_WARNING =
  "This capture includes packet payloads. Payloads can contain passwords, tokens, cookies, private messages, and third-party personal data. Keep the file local, do not upload it, and delete it when finished.";

export const CAPTURE_METADATA_WARNING =
  "Packet captures reveal who communicated with whom even when payloads are not shown. Treat this file as sensitive personal data.";

export const PLAINTEXT_PORTS = Object.freeze({
  21: "FTP",
  23: "Telnet",
  25: "SMTP",
  80: "HTTP",
  110: "POP3",
  143: "IMAP",
  389: "LDAP",
  1433: "MSSQL",
  3306: "MySQL",
  5432: "PostgreSQL",
  6379: "Redis",
  8080: "HTTP alternate",
});

const ETHERNET_TYPES = Object.freeze({
  0x0800: "ipv4",
  0x0806: "arp",
  0x86dd: "ipv6",
});

const VLAN_TYPES = new Set([0x8100, 0x88a8, 0x9100]);

function fail(code, message) {
  return Object.freeze({
    ok: false,
    code,
    message,
    summary: null,
  });
}

function toBytes(input) {
  if (input instanceof Uint8Array) {
    return input;
  }
  if (typeof ArrayBuffer !== "undefined" && input instanceof ArrayBuffer) {
    return new Uint8Array(input);
  }
  if (
    typeof ArrayBuffer !== "undefined" &&
    ArrayBuffer.isView &&
    ArrayBuffer.isView(input)
  ) {
    return new Uint8Array(input.buffer, input.byteOffset, input.byteLength);
  }
  if (Array.isArray(input)) {
    try {
      return Uint8Array.from(input);
    } catch {
      return null;
    }
  }
  return null;
}

function u16(bytes, offset, little = false) {
  return little
    ? bytes[offset] | (bytes[offset + 1] << 8)
    : (bytes[offset] << 8) | bytes[offset + 1];
}

function u32(bytes, offset, little = false) {
  if (little) {
    return (
      (bytes[offset] |
        (bytes[offset + 1] << 8) |
        (bytes[offset + 2] << 16) |
        (bytes[offset + 3] << 24)) >>>
      0
    );
  }
  return (
    ((bytes[offset] << 24) |
      (bytes[offset + 1] << 16) |
      (bytes[offset + 2] << 8) |
      bytes[offset + 3]) >>>
    0
  );
}

function formatIPv4(bytes, offset) {
  return `${bytes[offset]}.${bytes[offset + 1]}.${bytes[offset + 2]}.${
    bytes[offset + 3]
  }`;
}

function formatIPv6(bytes, offset) {
  const groups = [];
  for (let index = 0; index < 8; index += 1) {
    groups.push(u16(bytes, offset + index * 2));
  }

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

function createAggregator() {
  const protocols = {
    tcp: 0,
    udp: 0,
    icmp: 0,
    ipv4: 0,
    ipv6: 0,
    arp: 0,
    other: 0,
  };
  const endpoints = new Map();
  const conversations = new Map();
  const ports = new Map();
  const plaintextPorts = new Map();
  const unsupportedLinkTypes = new Set();
  let payloadBytes = 0;
  let payloadPackets = 0;

  function addEndpoint(address, bytes) {
    const current = endpoints.get(address);
    if (current) {
      current.packets += 1;
      current.bytes += bytes;
      return;
    }
    endpoints.set(address, { address, packets: 1, bytes });
  }

  function addConversation(protocol, source, destination, sourcePort, destinationPort, bytes) {
    const left = `${source}:${sourcePort ?? ""}`;
    const right = `${destination}:${destinationPort ?? ""}`;
    const ordered = left <= right ? [left, right] : [right, left];
    const key = `${protocol}|${ordered[0]}|${ordered[1]}`;
    const current = conversations.get(key);
    if (current) {
      current.packets += 1;
      current.bytes += bytes;
      return;
    }
    conversations.set(key, {
      protocol,
      source,
      sourcePort: sourcePort ?? null,
      destination,
      destinationPort: destinationPort ?? null,
      packets: 1,
      bytes,
    });
  }

  function addPort(protocol, port) {
    const key = `${protocol}:${port}`;
    const current = ports.get(key);
    if (current) {
      current.packets += 1;
    } else {
      ports.set(key, { protocol, port, packets: 1 });
    }
    const label = PLAINTEXT_PORTS[port];
    if (label) {
      plaintextPorts.set(label, (plaintextPorts.get(label) ?? 0) + 1);
    }
  }

  function addPayload(length) {
    if (length > 0) {
      payloadBytes += length;
      payloadPackets += 1;
    }
  }

  function parseTransport(data, network, capturedBytes) {
    const offset = network.transportOffset;
    const available = Math.max(0, data.length - offset);
    if (network.protocol === 6) {
      protocols.tcp += 1;
      if (available < 20) {
        return;
      }
      const sourcePort = u16(data, offset);
      const destinationPort = u16(data, offset + 2);
      const headerLength = (data[offset + 12] >> 4) * 4;
      if (headerLength < 20) {
        return;
      }
      addConversation(
        "tcp",
        network.source,
        network.destination,
        sourcePort,
        destinationPort,
        capturedBytes,
      );
      addPort("tcp", sourcePort);
      addPort("tcp", destinationPort);
      const payload = Math.max(
        0,
        Math.min(
          network.payloadLength - headerLength,
          data.length - (offset + headerLength),
        ),
      );
      addPayload(payload);
      return;
    }

    if (network.protocol === 17) {
      protocols.udp += 1;
      if (available < 8) {
        return;
      }
      const sourcePort = u16(data, offset);
      const destinationPort = u16(data, offset + 2);
      addConversation(
        "udp",
        network.source,
        network.destination,
        sourcePort,
        destinationPort,
        capturedBytes,
      );
      addPort("udp", sourcePort);
      addPort("udp", destinationPort);
      const udpLength = u16(data, offset + 4);
      const declared = udpLength >= 8 ? udpLength - 8 : 0;
      const payload = Math.max(
        0,
        Math.min(declared, data.length - (offset + 8)),
      );
      addPayload(payload);
      return;
    }

    if (network.protocol === 1 || network.protocol === 58) {
      protocols.icmp += 1;
      addPayload(Math.max(0, network.payloadLength - 4));
      return;
    }

    protocols.other += 1;
    addPayload(network.payloadLength);
  }

  function parseIPv4(data, offset, capturedBytes) {
    if (data.length < offset + 20) {
      return false;
    }
    const version = data[offset] >> 4;
    const headerLength = (data[offset] & 0x0f) * 4;
    if (version !== 4 || headerLength < 20 || data.length < offset + headerLength) {
      return false;
    }

    protocols.ipv4 += 1;
    const totalLength = u16(data, offset + 2);
    const protocol = data[offset + 9];
    const source = formatIPv4(data, offset + 12);
    const destination = formatIPv4(data, offset + 16);
    addEndpoint(source, capturedBytes);
    addEndpoint(destination, capturedBytes);

    const available = Math.max(0, data.length - (offset + headerLength));
    const declared =
      totalLength >= headerLength ? totalLength - headerLength : available;
    const payloadLength = Math.min(declared, available);
    parseTransport(
      data,
      {
        protocol,
        source,
        destination,
        transportOffset: offset + headerLength,
        payloadLength,
      },
      capturedBytes,
    );
    return true;
  }

  function parseIPv6(data, offset, capturedBytes) {
    if (data.length < offset + 40) {
      return false;
    }
    if (data[offset] >> 4 !== 6) {
      return false;
    }

    protocols.ipv6 += 1;
    const source = formatIPv6(data, offset + 8);
    const destination = formatIPv6(data, offset + 24);
    addEndpoint(source, capturedBytes);
    addEndpoint(destination, capturedBytes);

    const declaredLength = u16(data, offset + 4);
    let nextHeader = data[offset + 6];
    let cursor = offset + 40;
    let remaining = declaredLength;
    const extensions = new Set([0, 43, 44, 51, 60]);

    for (let guard = 0; guard < 8 && extensions.has(nextHeader); guard += 1) {
      if (data.length < cursor + 2) {
        return true;
      }
      if (nextHeader === 44) {
        if (data.length < cursor + 8) {
          return true;
        }
        nextHeader = data[cursor];
        cursor += 8;
        remaining = Math.max(0, remaining - 8);
        continue;
      }
      const extensionLength =
        nextHeader === 51
          ? (data[cursor + 1] + 2) * 4
          : (data[cursor + 1] + 1) * 4;
      if (extensionLength < 8 || data.length < cursor + extensionLength) {
        return true;
      }
      nextHeader = data[cursor];
      cursor += extensionLength;
      remaining = Math.max(0, remaining - extensionLength);
    }

    if (extensions.has(nextHeader)) {
      protocols.other += 1;
      return true;
    }

    const available = Math.max(0, data.length - cursor);
    parseTransport(
      data,
      {
        protocol: nextHeader,
        source,
        destination,
        transportOffset: cursor,
        payloadLength: Math.min(remaining, available),
      },
      capturedBytes,
    );
    return true;
  }

  function processPacket(linkType, data, capturedBytes) {
    let offset = 0;
    let etherType = null;

    if (linkType === 1) {
      if (data.length < 14) {
        protocols.other += 1;
        return;
      }
      etherType = u16(data, 12);
      offset = 14;
      for (let guard = 0; guard < 2 && VLAN_TYPES.has(etherType); guard += 1) {
        if (data.length < offset + 4) {
          protocols.other += 1;
          return;
        }
        etherType = u16(data, offset + 2);
        offset += 4;
      }
    } else if (linkType === 113) {
      if (data.length < 16) {
        protocols.other += 1;
        return;
      }
      etherType = u16(data, 14);
      offset = 16;
    } else if (linkType === 276) {
      if (data.length < 20) {
        protocols.other += 1;
        return;
      }
      etherType = u16(data, 0);
      offset = 20;
    } else if (linkType === 0 || linkType === 108) {
      if (data.length < 4) {
        protocols.other += 1;
        return;
      }
      const version = data[0] >> 4;
      offset = version === 4 || version === 6 ? 0 : 4;
    } else if (linkType !== 101 && linkType !== 228 && linkType !== 229) {
      protocols.other += 1;
      unsupportedLinkTypes.add(linkType);
      return;
    }

    if (etherType === 0x0800) {
      if (!parseIPv4(data, offset, capturedBytes)) {
        protocols.other += 1;
      }
      return;
    }
    if (etherType === 0x86dd) {
      if (!parseIPv6(data, offset, capturedBytes)) {
        protocols.other += 1;
      }
      return;
    }
    if (etherType === 0x0806) {
      protocols.arp += 1;
      return;
    }

    const version = data.length > offset ? data[offset] >> 4 : 0;
    if (version === 4) {
      if (!parseIPv4(data, offset, capturedBytes)) {
        protocols.other += 1;
      }
      return;
    }
    if (version === 6) {
      if (!parseIPv6(data, offset, capturedBytes)) {
        protocols.other += 1;
      }
      return;
    }
    if (etherType !== null && ETHERNET_TYPES[etherType]) {
      protocols.other += 1;
      return;
    }
    protocols.other += 1;
  }

  return {
    protocols,
    endpoints,
    conversations,
    ports,
    plaintextPorts,
    unsupportedLinkTypes,
    processPacket,
    payloadBytes: () => payloadBytes,
    payloadPackets: () => payloadPackets,
  };
}

function topEntries(map, limit, comparator) {
  return Array.from(map.values())
    .sort(comparator)
    .slice(0, limit)
    .map((entry) => Object.freeze({ ...entry }));
}

function buildSummary({
  format,
  packetCount,
  capturedBytes,
  originalBytes,
  truncatedPackets,
  firstTimestamp,
  lastTimestamp,
  aggregator,
  parseErrors,
  maxPackets,
  reachedLimit,
}) {
  const endpoints = topEntries(
    aggregator.endpoints,
    MAX_ENDPOINTS,
    (left, right) =>
      right.packets - left.packets ||
      right.bytes - left.bytes ||
      left.address.localeCompare(right.address),
  );
  const conversations = topEntries(
    aggregator.conversations,
    MAX_CONVERSATIONS,
    (left, right) =>
      right.packets - left.packets ||
      right.bytes - left.bytes ||
      `${left.source}${left.sourcePort}${left.destination}${left.destinationPort}`.localeCompare(
        `${right.source}${right.sourcePort}${right.destination}${right.destinationPort}`,
      ),
  );
  const ports = topEntries(
    aggregator.ports,
    MAX_PORTS,
    (left, right) =>
      right.packets - left.packets ||
      left.port - right.port ||
      left.protocol.localeCompare(right.protocol),
  );

  const payloadBytes = aggregator.payloadBytes();
  const payloadPackets = aggregator.payloadPackets();
  const plaintextServices = Array.from(aggregator.plaintextPorts.keys()).sort();
  const warnings = [
    Object.freeze({
      code: "capture-metadata-sensitive",
      message: CAPTURE_METADATA_WARNING,
    }),
  ];

  if (payloadPackets > 0) {
    warnings.push(
      Object.freeze({
        code: "sensitive-payload",
        message: SENSITIVE_PAYLOAD_WARNING,
      }),
    );
  }
  if (plaintextServices.length > 0) {
    warnings.push(
      Object.freeze({
        code: "plaintext-service",
        message: `Plaintext or weakly protected service ports were observed (${plaintextServices.join(
          ", ",
        )}). These protocols can expose credentials and content in payloads.`,
      }),
    );
  }
  if (packetCount === 0) {
    warnings.push(
      Object.freeze({
        code: "empty-capture",
        message: "The capture contains no packets. Check that the file is complete.",
      }),
    );
  }
  if (truncatedPackets > 0) {
    warnings.push(
      Object.freeze({
        code: "truncated-packets",
        message: `${truncatedPackets} packet${
          truncatedPackets === 1 ? "" : "s"
        } were truncated by the capture length. The summary only covers captured bytes.`,
      }),
    );
  }
  if (aggregator.unsupportedLinkTypes.size > 0) {
    warnings.push(
      Object.freeze({
        code: "unsupported-link-type",
        message: `Unsupported link-layer type${
          aggregator.unsupportedLinkTypes.size === 1 ? "" : "s"
        }: ${Array.from(aggregator.unsupportedLinkTypes).join(", ")}. Those packets are counted but not decoded.`,
      }),
    );
  }
  if (parseErrors > 0) {
    warnings.push(
      Object.freeze({
        code: "parse-errors",
        message: `${parseErrors} malformed packet record${
          parseErrors === 1 ? "" : "s"
        } were skipped safely.`,
      }),
    );
  }
  if (reachedLimit) {
    warnings.push(
      Object.freeze({
        code: "packet-limit",
        message: `Review stopped at the local limit of ${maxPackets} packets. The summary covers only the first records.`,
      }),
    );
  }

  const first = Number.isFinite(firstTimestamp) ? firstTimestamp : null;
  const last = Number.isFinite(lastTimestamp) ? lastTimestamp : null;
  const duration =
    first !== null && last !== null ? Math.max(0, last - first) : null;

  return Object.freeze({
    ok: true,
    id: PCAP_REVIEW_ID,
    format: Object.freeze({ ...format }),
    packetCount,
    capturedBytes,
    originalBytes,
    truncatedPackets,
    firstTimestamp: first,
    lastTimestamp: last,
    durationSeconds: duration,
    protocols: Object.freeze({ ...aggregator.protocols }),
    endpoints: Object.freeze(endpoints),
    conversations: Object.freeze(conversations),
    ports: Object.freeze(ports),
    payload: Object.freeze({
      packets: payloadPackets,
      bytes: payloadBytes,
    }),
    sensitive: Object.freeze({
      hasPayload: payloadPackets > 0,
      plaintextServices: Object.freeze(plaintextServices),
      risk:
        payloadPackets > 0 ? "high" : plaintextServices.length > 0 ? "medium" : "low",
      warning:
        payloadPackets > 0
          ? SENSITIVE_PAYLOAD_WARNING
          : CAPTURE_METADATA_WARNING,
    }),
    warnings: Object.freeze(warnings),
    parseErrors,
    limits: Object.freeze({ maxPackets, reached: reachedLimit }),
  });
}

function parseClassicPcap(bytes, maxPackets) {
  if (bytes.length < 24) {
    return fail("invalid-pcap", "The pcap file is shorter than its 24-byte global header.");
  }

  const magic = [bytes[0], bytes[1], bytes[2], bytes[3]];
  let little;
  let resolution;
  if (magic[0] === 0xd4 && magic[1] === 0xc3 && magic[2] === 0xb2 && magic[3] === 0xa1) {
    little = true;
    resolution = "microsecond";
  } else if (
    magic[0] === 0xa1 &&
    magic[1] === 0xb2 &&
    magic[2] === 0xc3 &&
    magic[3] === 0xd4
  ) {
    little = false;
    resolution = "microsecond";
  } else if (
    magic[0] === 0x4d &&
    magic[1] === 0x3c &&
    magic[2] === 0xb2 &&
    magic[3] === 0xa1
  ) {
    little = true;
    resolution = "nanosecond";
  } else if (
    magic[0] === 0xa1 &&
    magic[1] === 0xb2 &&
    magic[2] === 0x3c &&
    magic[3] === 0x4d
  ) {
    little = false;
    resolution = "nanosecond";
  } else {
    return fail("unsupported-format", "The pcap magic number is not supported.");
  }

  const versionMajor = u16(bytes, 4, little);
  const versionMinor = u16(bytes, 6, little);
  const linkType = u32(bytes, 20, little) & 0xffff;
  const aggregator = createAggregator();
  const denominator = resolution === "nanosecond" ? 1e9 : 1e6;

  let offset = 24;
  let packetCount = 0;
  let capturedBytes = 0;
  let originalBytes = 0;
  let truncatedPackets = 0;
  let parseErrors = 0;
  let firstTimestamp = null;
  let lastTimestamp = null;
  let reachedLimit = false;

  while (offset + 16 <= bytes.length) {
    if (packetCount >= maxPackets) {
      reachedLimit = true;
      break;
    }
    const seconds = u32(bytes, offset, little);
    const fraction = u32(bytes, offset + 4, little);
    const capturedLength = u32(bytes, offset + 8, little);
    const originalLength = u32(bytes, offset + 12, little);

    if (capturedLength > bytes.length - (offset + 16)) {
      parseErrors += 1;
      break;
    }

    const start = offset + 16;
    const packet = bytes.subarray(start, start + capturedLength);
    aggregator.processPacket(linkType, packet, capturedLength);
    packetCount += 1;
    capturedBytes += capturedLength;
    originalBytes += originalLength;
    if (capturedLength < originalLength) {
      truncatedPackets += 1;
    }
    const timestamp = seconds + fraction / denominator;
    if (firstTimestamp === null || timestamp < firstTimestamp) {
      firstTimestamp = timestamp;
    }
    if (lastTimestamp === null || timestamp > lastTimestamp) {
      lastTimestamp = timestamp;
    }
    offset = start + capturedLength;
  }

  if (offset < bytes.length && !reachedLimit) {
    const remaining = bytes.length - offset;
    if (remaining > 0) {
      parseErrors += 1;
    }
  }

  return buildSummary({
    format: {
      name: "pcap",
      version: `${versionMajor}.${versionMinor}`,
      byteOrder: little ? "little" : "big",
      timestampResolution: resolution,
      linkType,
    },
    packetCount,
    capturedBytes,
    originalBytes,
    truncatedPackets,
    firstTimestamp,
    lastTimestamp,
    aggregator,
    parseErrors,
    maxPackets,
    reachedLimit,
  });
}

function parsePcapngOptions(bytes, start, end, little) {
  let offset = start;
  let timestampResolution = 6;
  let timestampOffset = 0;

  while (offset + 4 <= end) {
    const code = u16(bytes, offset, little);
    const length = u16(bytes, offset + 2, little);
    offset += 4;
    if (code === 0) {
      break;
    }
    if (offset + length > end) {
      break;
    }
    if (code === 9 && length >= 1) {
      timestampResolution = bytes[offset];
    } else if (code === 14 && length >= 8) {
      const low = u32(bytes, offset, little);
      const high = u32(bytes, offset + 4, little);
      const raw = (BigInt(high) << 32n) | BigInt(low);
      const signed = raw & (1n << 63n) ? raw - (1n << 64n) : raw;
      timestampOffset = Number(signed);
    }
    offset += length + ((4 - (length % 4)) % 4);
  }

  return { timestampResolution, timestampOffset };
}

function resolutionDenominator(value) {
  if (value & 0x80) {
    return 2 ** (value & 0x7f);
  }
  return 10 ** value;
}

function parsePcapng(bytes, maxPackets) {
  if (bytes.length < 28) {
    return fail("invalid-pcapng", "The pcapng file is shorter than its section header.");
  }

  const aggregator = createAggregator();
  let offset = 0;
  let little = true;
  let endianKnown = false;
  let versionMajor = 1;
  let versionMinor = 0;
  let sections = 0;
  let interfaces = [];
  let packetCount = 0;
  let capturedBytes = 0;
  let originalBytes = 0;
  let truncatedPackets = 0;
  let parseErrors = 0;
  let firstTimestamp = null;
  let lastTimestamp = null;
  let reachedLimit = false;

  while (offset + 12 <= bytes.length) {
    const isSectionHeader =
      bytes[offset] === 0x0a &&
      bytes[offset + 1] === 0x0d &&
      bytes[offset + 2] === 0x0d &&
      bytes[offset + 3] === 0x0a;

    if (isSectionHeader && offset + 12 <= bytes.length) {
      const bom =
        (bytes[offset + 8] << 24) |
        (bytes[offset + 9] << 16) |
        (bytes[offset + 10] << 8) |
        bytes[offset + 11];
      if (bom === 0x1a2b3c4d) {
        little = false;
      } else if (bom === 0x4d3c2b1a) {
        little = true;
      } else {
        return fail(
          "invalid-pcapng",
          "A pcapng section header has an unknown byte-order magic.",
        );
      }
      endianKnown = true;
    } else if (!endianKnown) {
      return fail(
        "invalid-pcapng",
        "The pcapng stream does not start with a section header block.",
      );
    }

    const blockType = u32(bytes, offset, little);
    const blockLength = u32(bytes, offset + 4, little);
    if (
      blockLength < 12 ||
      blockLength % 4 !== 0 ||
      offset + blockLength > bytes.length
    ) {
      parseErrors += 1;
      break;
    }
    const trailingLength = u32(bytes, offset + blockLength - 4, little);
    if (trailingLength !== blockLength) {
      parseErrors += 1;
      break;
    }

    const bodyStart = offset + 8;
    const bodyEnd = offset + blockLength - 4;

    if (blockType === 0x0a0d0d0a) {
      sections += 1;
      interfaces = [];
      versionMajor = u16(bytes, offset + 12, little);
      versionMinor = u16(bytes, offset + 14, little);
    } else if (blockType === 0x00000001) {
      if (bodyEnd - bodyStart < 8) {
        parseErrors += 1;
      } else {
        const linkType = u16(bytes, offset + 8, little);
        const options = parsePcapngOptions(bytes, offset + 16, bodyEnd, little);
        interfaces.push({
          linkType,
          timestampResolution: options.timestampResolution,
          timestampOffset: options.timestampOffset,
        });
      }
    } else if (blockType === 0x00000006 || blockType === 0x00000002) {
      if (packetCount >= maxPackets) {
        reachedLimit = true;
        break;
      }
      const enhanced = blockType === 0x00000006;
      const interfaceId = enhanced
        ? u32(bytes, offset + 8, little)
        : u16(bytes, offset + 8, little);
      const timestampHigh = u32(bytes, offset + 12, little);
      const timestampLow = u32(bytes, offset + 16, little);
      const capturedLength = u32(bytes, offset + 20, little);
      const originalLength = u32(bytes, offset + 24, little);
      const dataStart = offset + 28;
      const iface = interfaces[interfaceId];

      if (
        !iface ||
        dataStart + capturedLength > bodyEnd ||
        capturedLength > bytes.length
      ) {
        parseErrors += 1;
        offset += blockLength;
        continue;
      }

      const packet = bytes.subarray(dataStart, dataStart + capturedLength);
      aggregator.processPacket(iface.linkType, packet, capturedLength);
      packetCount += 1;
      capturedBytes += capturedLength;
      originalBytes += originalLength;
      if (capturedLength < originalLength) {
        truncatedPackets += 1;
      }

      const ticks = (BigInt(timestampHigh) << 32n) | BigInt(timestampLow);
      const timestamp =
        Number(ticks) / resolutionDenominator(iface.timestampResolution) +
        iface.timestampOffset;
      if (firstTimestamp === null || timestamp < firstTimestamp) {
        firstTimestamp = timestamp;
      }
      if (lastTimestamp === null || timestamp > lastTimestamp) {
        lastTimestamp = timestamp;
      }
    } else if (blockType === 0x00000003) {
      if (packetCount >= maxPackets) {
        reachedLimit = true;
        break;
      }
      const originalLength = u32(bytes, offset + 8, little);
      const capturedLength = Math.min(originalLength, bodyEnd - (offset + 12));
      const iface = interfaces[0];
      if (!iface || offset + 12 + capturedLength > bodyEnd) {
        parseErrors += 1;
        offset += blockLength;
        continue;
      }
      const packet = bytes.subarray(offset + 12, offset + 12 + capturedLength);
      aggregator.processPacket(iface.linkType, packet, capturedLength);
      packetCount += 1;
      capturedBytes += capturedLength;
      originalBytes += originalLength;
      if (capturedLength < originalLength) {
        truncatedPackets += 1;
      }
    }

    offset += blockLength;
  }

  if (offset < bytes.length && !reachedLimit && bytes.length - offset > 0) {
    parseErrors += 1;
  }

  const linkType = interfaces.length > 0 ? interfaces[0].linkType : null;
  return buildSummary({
    format: {
      name: "pcapng",
      version: `${versionMajor}.${versionMinor}`,
      byteOrder: little ? "little" : "big",
      timestampResolution: "per-interface",
      linkType,
      sections,
      interfaces: interfaces.length,
    },
    packetCount,
    capturedBytes,
    originalBytes,
    truncatedPackets,
    firstTimestamp,
    lastTimestamp,
    aggregator,
    parseErrors,
    maxPackets,
    reachedLimit,
  });
}

export function summarizeCapture(input, { maxPackets = MAX_PACKETS } = {}) {
  const bytes = toBytes(input);
  if (!bytes) {
    return fail(
      "invalid-input",
      "Pass the capture as a Uint8Array, ArrayBuffer, typed array, or byte array.",
    );
  }
  if (bytes.length === 0) {
    return fail("empty-input", "The selected capture file is empty.");
  }

  const limit =
    Number.isInteger(maxPackets) && maxPackets > 0
      ? Math.min(maxPackets, MAX_PACKETS)
      : MAX_PACKETS;

  const isPcapng =
    bytes.length >= 4 &&
    bytes[0] === 0x0a &&
    bytes[1] === 0x0d &&
    bytes[2] === 0x0d &&
    bytes[3] === 0x0a;
  if (isPcapng) {
    return parsePcapng(bytes, limit);
  }
  return parseClassicPcap(bytes, limit);
}
