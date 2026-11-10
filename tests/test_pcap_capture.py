"""Pcap capture/review contract, generated fixtures, helper, and UI tests."""

from __future__ import annotations

import base64
import ipaddress
import json
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.support import read_text  # noqa: E402
from tools import pcap_review_helper as helper  # noqa: E402

SECURITY_DIR = ROOT / "preview" / "security"
FORMAT_MODULE = SECURITY_DIR / "pcap-format.js"
CAPTURE_MODULE = SECURITY_DIR / "pcap-capture.js"
HELPER = ROOT / "tools" / "pcap_review_helper.py"
NODE = shutil.which("node")
REMOTE_RE = re.compile(r"https?://", re.IGNORECASE)
REFERENCE_RE = re.compile(r'(?:href|src)="([^"]+)"')
JS_IMPORT_RE = re.compile(r"(?:from|import)\s+[\"']([^\"']+)[\"']")


def ipv4_bytes(address: str) -> bytes:
    return ipaddress.IPv4Address(address).packed


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def ipv4_packet(source: str, destination: str, protocol: int, payload: bytes) -> bytes:
    source_bytes = ipv4_bytes(source)
    destination_bytes = ipv4_bytes(destination)
    total_length = 20 + len(payload)
    header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        total_length,
        0x1234,
        0x4000,
        64,
        protocol,
        0,
        source_bytes,
        destination_bytes,
    )
    header = header[:10] + struct.pack("!H", checksum(header)) + header[12:]
    return header + payload


def tcp_segment(source_port: int, destination_port: int, payload: bytes) -> bytes:
    return (
        struct.pack(
            "!HHIIHHHH",
            source_port,
            destination_port,
            1,
            1,
            (5 << 12) | 0x18,
            65535,
            0,
            0,
        )
        + payload
    )


def udp_segment(source_port: int, destination_port: int, payload: bytes) -> bytes:
    return struct.pack(
        "!HHHH",
        source_port,
        destination_port,
        8 + len(payload),
        0,
    ) + payload


def ethernet_frame(payload: bytes, ether_type: int = 0x0800) -> bytes:
    return (
        b"\xaa\xbb\xcc\xdd\xee\xff"
        + b"\x02\x00\x00\x00\x00\x01"
        + struct.pack("!H", ether_type)
        + payload
    )


def arp_frame() -> bytes:
    return ethernet_frame(
        struct.pack(
            "!HHBBH6s4s6s4s",
            1,
            0x0800,
            6,
            4,
            1,
            b"\x02\x00\x00\x00\x00\x01",
            ipv4_bytes("10.0.0.2"),
            b"\x00\x00\x00\x00\x00\x00",
            ipv4_bytes("10.0.0.1"),
        ),
        0x0806,
    )


def classic_pcap(
    packets: list[tuple[float, bytes, int]],
    *,
    little: bool = True,
    nanosecond: bool = False,
    link_type: int = 1,
) -> bytes:
    endian = "<" if little else ">"
    if nanosecond:
        magic = b"\x4d\x3c\xb2\xa1" if little else b"\xa1\xb2\x3c\x4d"
    else:
        magic = b"\xd4\xc3\xb2\xa1" if little else b"\xa1\xb2\xc3\xd4"
    parts = [
        magic
        + struct.pack(endian + "HHIIII", 2, 4, 0, 0, 65535, link_type)
    ]
    for timestamp, frame, original_length in packets:
        seconds = int(timestamp)
        fraction = int(round((timestamp - seconds) * (1e9 if nanosecond else 1e6)))
        parts.append(
            struct.pack(
                endian + "IIII",
                seconds,
                fraction,
                len(frame),
                original_length,
            )
        )
        parts.append(frame)
    return b"".join(parts)


def pcapng(
    packets: list[tuple[float, bytes, int]],
    *,
    little: bool = True,
    link_type: int = 1,
) -> bytes:
    endian = "<" if little else ">"
    section_header_length = 28
    section = (
        struct.pack(
            endian + "IIIHHq",
            0x0A0D0D0A,
            section_header_length,
            0x1A2B3C4D,
            1,
            0,
            -1,
        )
    )
    section += struct.pack(endian + "I", section_header_length)
    interfaces = (
        struct.pack(endian + "IIHHI", 1, 20, link_type, 0, 65535)
        + struct.pack(endian + "I", 20)
    )
    blocks = [section, interfaces]
    for timestamp, frame, original_length in packets:
        padded = frame + b"\x00" * ((4 - len(frame) % 4) % 4)
        total_length = 28 + len(padded) + 4
        ticks = int(round(timestamp * 1_000_000))
        block = struct.pack(
            endian + "IIIIIII",
            0x00000006,
            total_length,
            0,
            (ticks >> 32) & 0xFFFFFFFF,
            ticks & 0xFFFFFFFF,
            len(frame),
            original_length,
        )
        block += padded + struct.pack(endian + "I", total_length)
        blocks.append(block)
    return b"".join(blocks)


def build_capture_fixture() -> tuple[bytes, dict]:
    http_request = (
        b"GET / HTTP/1.1\r\nHost: lab.local\r\n"
        b"Authorization: Bearer hunter2-secret\r\n\r\n"
    )
    dns_query = b"\x12\x34\x01\x00secret-dns-query"
    http_response = (
        b"HTTP/1.1 200 OK\r\nSet-Cookie: session=topsecret\r\n\r\n"
    )
    frames = [
        ethernet_frame(
            ipv4_packet(
                "10.0.0.2",
                "192.168.1.10",
                6,
                tcp_segment(49152, 80, http_request),
            )
        ),
        ethernet_frame(
            ipv4_packet(
                "10.0.0.2",
                "224.0.0.251",
                17,
                udp_segment(5353, 5353, dns_query),
            )
        ),
        ethernet_frame(
            ipv4_packet(
                "192.168.1.10",
                "10.0.0.2",
                6,
                tcp_segment(80, 49152, http_response),
            )
        ),
        arp_frame(),
    ]
    packets = [
        (1700000000.1, frames[0], len(frames[0])),
        (1700000000.2, frames[1], len(frames[1])),
        (1700000000.3, frames[2], len(frames[2])),
        (1700000000.4, frames[3], len(frames[3])),
    ]
    data = classic_pcap(packets)
    return data, {
        "packets": packets,
        "secrets": [
            "hunter2-secret",
            "secret-dns-query",
            "topsecret",
            "Authorization",
            "Set-Cookie",
        ],
    }


class NodeContractTestCase(unittest.TestCase):
    module = FORMAT_MODULE

    def run_js(self, body: str) -> dict:
        script = f"""import * as contract from {json.dumps(self.module.as_uri())};
try {{
  const result = await (async () => {{
{body}
  }})();
  process.stdout.write(JSON.stringify(result));
}} catch (error) {{
  process.stderr.write(String((error && error.stack) || error));
  process.exitCode = 1;
}}
"""
        result = subprocess.run(
            [NODE, "--input-type=module", "--eval", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class ClassicPcapSummary(NodeContractTestCase):
    def test_generated_fixture_is_summarized_without_payload_text(self) -> None:
        fixture, metadata = build_capture_fixture()
        encoded = base64.b64encode(fixture).decode("ascii")
        result = self.run_js(
            f"""
  const bytes = Uint8Array.from(Buffer.from({json.dumps(encoded)}, "base64"));
  const summary = contract.summarizeCapture(bytes);
  return {{
    summary,
    serialized: JSON.stringify(summary),
  }};
"""
        )
        summary = result["summary"]
        self.assertIs(summary["ok"], True)
        self.assertEqual(summary["format"]["name"], "pcap")
        self.assertEqual(summary["format"]["byteOrder"], "little")
        self.assertEqual(summary["format"]["timestampResolution"], "microsecond")
        self.assertEqual(summary["format"]["linkType"], 1)
        self.assertEqual(summary["packetCount"], 4)
        self.assertEqual(summary["protocols"]["tcp"], 2)
        self.assertEqual(summary["protocols"]["udp"], 1)
        self.assertEqual(summary["protocols"]["arp"], 1)
        self.assertEqual(summary["protocols"]["ipv4"], 3)
        self.assertEqual(summary["truncatedPackets"], 0)
        self.assertEqual(summary["sensitive"]["risk"], "high")
        self.assertIs(summary["sensitive"]["hasPayload"], True)
        self.assertIn("HTTP", summary["sensitive"]["plaintextServices"])
        warning_codes = {warning["code"] for warning in summary["warnings"]}
        self.assertIn("sensitive-payload", warning_codes)
        self.assertIn("plaintext-service", warning_codes)
        self.assertEqual(
            [endpoint["address"] for endpoint in summary["endpoints"]],
            ["10.0.0.2", "192.168.1.10", "224.0.0.251"],
        )
        self.assertEqual(len(summary["conversations"]), 2)
        self.assertEqual(summary["conversations"][0]["protocol"], "tcp")
        self.assertEqual(summary["conversations"][0]["packets"], 2)
        self.assertGreater(summary["payload"]["bytes"], 0)
        self.assertAlmostEqual(summary["firstTimestamp"], 1700000000.1, places=3)
        self.assertAlmostEqual(summary["lastTimestamp"], 1700000000.4, places=3)
        self.assertAlmostEqual(summary["durationSeconds"], 0.3, places=3)
        for secret in metadata["secrets"]:
            with self.subTest(secret=secret):
                self.assertNotIn(secret, result["serialized"])

    def test_big_endian_nanosecond_fixture_is_supported(self) -> None:
        fixture, _ = build_capture_fixture()
        # Rebuild the same frames in the other byte order and timestamp unit.
        frames = [
            (
                1700000000.123456789,
                frame,
                original_length,
            )
            for _timestamp, frame, original_length in build_capture_fixture()[1]["packets"]
        ]
        data = classic_pcap(frames, little=False, nanosecond=True)
        encoded = base64.b64encode(data).decode("ascii")
        result = self.run_js(
            f"""
  const bytes = Uint8Array.from(Buffer.from({json.dumps(encoded)}, "base64"));
  return contract.summarizeCapture(bytes).format;
"""
        )
        self.assertEqual(result["name"], "pcap")
        self.assertEqual(result["byteOrder"], "big")
        self.assertEqual(result["timestampResolution"], "nanosecond")

    def test_pcapng_fixture_is_supported(self) -> None:
        packets = build_capture_fixture()[1]["packets"]
        data = pcapng(packets[:2])
        encoded = base64.b64encode(data).decode("ascii")
        result = self.run_js(
            f"""
  const bytes = Uint8Array.from(Buffer.from({json.dumps(encoded)}, "base64"));
  const summary = contract.summarizeCapture(bytes);
  return {{ summary, serialized: JSON.stringify(summary) }};
"""
        )
        summary = result["summary"]
        self.assertIs(summary["ok"], True)
        self.assertEqual(summary["format"]["name"], "pcapng")
        self.assertEqual(summary["format"]["linkType"], 1)
        self.assertEqual(summary["packetCount"], 2)
        self.assertEqual(summary["protocols"]["tcp"], 1)
        self.assertEqual(summary["protocols"]["udp"], 1)
        self.assertNotIn("hunter2-secret", result["serialized"])
        self.assertNotIn("secret-dns-query", result["serialized"])

    def test_truncation_and_packet_limit_are_reported(self) -> None:
        packets = build_capture_fixture()[1]["packets"]
        # The first packet claims a larger original length than captured bytes.
        altered = [
            (packets[0][0], packets[0][1], packets[0][2] + 10),
            *packets[1:],
        ]
        data = classic_pcap(altered)
        encoded = base64.b64encode(data).decode("ascii")
        result = self.run_js(
            f"""
  const bytes = Uint8Array.from(Buffer.from({json.dumps(encoded)}, "base64"));
  const limited = contract.summarizeCapture(bytes, {{ maxPackets: 2 }});
  return {{
    truncatedPackets: limited.truncatedPackets,
    packetCount: limited.packetCount,
    reached: limited.limits.reached,
    warningCodes: limited.warnings.map((warning) => warning.code),
  }};
"""
        )
        self.assertEqual(result["packetCount"], 2)
        self.assertEqual(result["truncatedPackets"], 1)
        self.assertIs(result["reached"], True)
        self.assertIn("truncated-packets", result["warningCodes"])
        self.assertIn("packet-limit", result["warningCodes"])

    def test_malformed_and_empty_inputs_fail_closed(self) -> None:
        result = self.run_js(
            """
  const cases = {
    empty: contract.summarizeCapture(new Uint8Array()),
    short: contract.summarizeCapture(new Uint8Array([1, 2, 3, 4])),
    unknown: contract.summarizeCapture(Uint8Array.from(
      Array.from({ length: 32 }, (_, index) => index),
    )),
    wrongType: contract.summarizeCapture("not bytes"),
  };
  return Object.fromEntries(
    Object.entries(cases).map(([name, value]) => [
      name,
      { ok: value.ok, code: value.code, hasMessage: Boolean(value.message) },
    ]),
  );
"""
        )
        self.assertIs(result["empty"]["ok"], False)
        self.assertEqual(result["empty"]["code"], "empty-input")
        self.assertIs(result["short"]["ok"], False)
        self.assertEqual(result["short"]["code"], "invalid-pcap")
        self.assertIs(result["unknown"]["ok"], False)
        self.assertEqual(result["unknown"]["code"], "unsupported-format")
        self.assertIs(result["wrongType"]["ok"], False)
        self.assertEqual(result["wrongType"]["code"], "invalid-input")
        for value in result.values():
            self.assertIs(value["hasMessage"], True)


class PcapngFixtureBuilder(unittest.TestCase):
    def test_generated_pcapng_has_two_packets(self) -> None:
        packets = build_capture_fixture()[1]["packets"][:2]
        data = pcapng(packets)
        self.assertEqual(data[:4], b"\x0a\x0d\x0d\x0a")
        self.assertGreater(len(data), 100)


class CaptureLifecycle(NodeContractTestCase):
    module = CAPTURE_MODULE

    def test_no_capture_on_first_launch_and_explicit_consent(self) -> None:
        result = self.run_js(
            """
  const calls = { start: 0, stop: 0, clear: 0 };
  let startContext = null;
  let stopContext = null;
  let clearContext = null;
  const provider = {
    kind: "android-vpn-service",
    label: "test VpnService",
    start: (context) => {
      calls.start += 1;
      startContext = context;
      return { id: "capture-1", label: "Wi-Fi lab capture" };
    },
    stop: (context) => {
      calls.stop += 1;
      stopContext = context;
      return { stopped: true };
    },
    clear: (context) => {
      calls.clear += 1;
      clearContext = context;
      return { cleared: true };
    },
  };
  const session = contract.createPcapCapture({
    provider,
    now: () => "2026-11-10T00:00:00Z",
  });
  const initial = session.snapshot();
  const beforeAuthorization = session.start({ acknowledged: true });
  const callsAfterFirstLaunch = { ...calls };
  const refused = session.authorize({ acknowledged: false });
  const authorized = session.authorize({ acknowledged: true });
  const callsAfterAuthorize = { ...calls };
  const noConsent = session.start({ acknowledged: false });
  const callsAfterNoConsent = { ...calls };
  const started = session.start({ acknowledged: true, label: "Wi-Fi" });
  const callsAfterStart = { ...calls };
  const afterStart = session.snapshot();
  const duplicate = session.start({ acknowledged: true });
  const callsAfterDuplicate = { ...calls };
  const stopped = session.stop();
  const callsAfterStop = { ...calls };
  const afterStop = session.snapshot();
  const startedAgain = session.start({ acknowledged: true });
  const callsAfterRestart = { ...calls };
  const cleared = session.stopAndClear();
  const callsAfterClear = { ...calls };
  const afterClear = session.snapshot();
  const afterRevoke = session.start({ acknowledged: true });
  const callsAfterRevoke = { ...calls };
  return {
    initialState: initial.state,
    initialIndicator: initial.indicator,
    initialCapture: initial.capture,
    initialCalls: { start: 0, stop: 0, clear: 0 },
    beforeAuthorizationCode: beforeAuthorization.code,
    callsAfterFirstLaunch,
    refusedCode: refused.code,
    authorizedCode: authorized.code,
    callsAfterAuthorize,
    noConsentCode: noConsent.code,
    callsAfterNoConsent,
    startedCode: started.code,
    callsAfterStart,
    startContext,
    startIndicator: afterStart.indicator,
    capture: afterStart.capture,
    duplicateCode: duplicate.code,
    callsAfterDuplicate,
    stoppedCode: stopped.code,
    callsAfterStop,
    stopContext,
    stopIndicator: afterStop.indicator,
    restartCode: startedAgain.code,
    callsAfterRestart,
    clearedCode: cleared.code,
    cleared: cleared.cleared,
    wasAuthorized: cleared.wasAuthorized,
    callsAfterClear,
    afterClear,
    clearContext,
    afterRevokeCode: afterRevoke.code,
    callsAfterRevoke,
  };
"""
        )
        self.assertEqual(result["initialState"], "idle")
        self.assertIs(result["initialIndicator"]["visible"], False)
        self.assertIsNone(result["initialCapture"])
        self.assertEqual(
            result["initialCalls"], {"start": 0, "stop": 0, "clear": 0}
        )
        self.assertEqual(result["beforeAuthorizationCode"], "not-authorized")
        self.assertEqual(
            result["callsAfterFirstLaunch"], {"start": 0, "stop": 0, "clear": 0}
        )
        self.assertEqual(result["refusedCode"], "acknowledgement-required")
        self.assertEqual(result["authorizedCode"], "authorized")
        self.assertEqual(
            result["callsAfterAuthorize"], {"start": 0, "stop": 0, "clear": 0}
        )
        self.assertEqual(result["noConsentCode"], "consent-required")
        self.assertEqual(
            result["callsAfterNoConsent"], {"start": 0, "stop": 0, "clear": 0}
        )
        self.assertEqual(result["startedCode"], "capturing")
        self.assertEqual(result["callsAfterStart"]["start"], 1)
        self.assertIs(result["startContext"]["authorized"], True)
        self.assertIs(result["startContext"]["consent"], True)
        self.assertIs(result["startContext"]["persistentNotification"], True)
        self.assertIn("passwords", result["startContext"]["statement"])
        self.assertIs(result["startIndicator"]["visible"], True)
        self.assertIs(result["startIndicator"]["persistent"], True)
        self.assertEqual(result["capture"]["id"], "capture-1")
        self.assertEqual(result["capture"]["label"], "Wi-Fi lab capture")
        self.assertEqual(result["duplicateCode"], "already-capturing")
        self.assertEqual(result["callsAfterDuplicate"]["start"], 1)
        self.assertEqual(result["stoppedCode"], "stopped")
        self.assertEqual(result["callsAfterStop"]["stop"], 1)
        self.assertIs(result["stopIndicator"]["visible"], False)
        self.assertEqual(result["stopContext"]["reason"], "user-stop")
        self.assertEqual(result["restartCode"], "capturing")
        self.assertEqual(result["callsAfterRestart"]["start"], 2)
        self.assertEqual(result["clearedCode"], "stopped-and-cleared")
        self.assertIs(result["cleared"], True)
        self.assertIs(result["wasAuthorized"], True)
        self.assertEqual(result["callsAfterClear"]["stop"], 2)
        self.assertEqual(result["callsAfterClear"]["clear"], 1)
        self.assertIs(result["afterClear"]["authorized"], False)
        self.assertIsNone(result["afterClear"]["session"])
        self.assertIsNone(result["afterClear"]["review"])
        self.assertIs(result["afterClear"]["indicator"]["visible"], False)
        self.assertEqual(result["clearContext"]["confirmDelete"], True)
        self.assertEqual(result["afterRevokeCode"], "not-authorized")
        self.assertEqual(result["callsAfterRevoke"]["start"], 2)

    def test_offline_review_requires_authorization_and_keeps_no_payload(self) -> None:
        fixture, metadata = build_capture_fixture()
        encoded = base64.b64encode(fixture).decode("ascii")
        result = self.run_js(
            f"""
  const bytes = Uint8Array.from(Buffer.from({json.dumps(encoded)}, "base64"));
  const session = contract.createPcapCapture({{
    provider: null,
    now: () => "2026-11-10T00:00:00Z",
  }});
  const before = session.reviewCapture(bytes, {{ fileName: "fixture.pcap" }});
  const authorized = session.authorize({{ acknowledged: true }});
  const reviewed = session.reviewCapture(bytes, {{
    fileName: "fixture.pcap",
    size: bytes.byteLength,
  }});
  const snapshot = session.snapshot();
  const cleared = session.clearReview();
  return {{
    beforeCode: before.code,
    authorizedCode: authorized.code,
    reviewedCode: reviewed.code,
    packetCount: reviewed.summary?.packetCount ?? null,
    snapshot,
    reviewedSerialized: JSON.stringify(reviewed),
    snapshotSerialized: JSON.stringify(snapshot),
    clearedCode: cleared.code,
    reviewAfterClear: cleared.state.review,
    providerStatus: session.getProviderStatus(),
  }};
"""
        )
        self.assertEqual(result["beforeCode"], "not-authorized")
        self.assertEqual(result["authorizedCode"], "authorized")
        self.assertEqual(result["reviewedCode"], "reviewed")
        self.assertEqual(result["packetCount"], 4)
        self.assertEqual(result["snapshot"]["review"]["fileName"], "fixture.pcap")
        self.assertEqual(result["snapshot"]["review"]["summary"]["packetCount"], 4)
        self.assertIs(result["snapshot"]["providerStatus"]["ok"], False)
        for secret in metadata["secrets"]:
            with self.subTest(secret=secret):
                self.assertNotIn(secret, result["reviewedSerialized"])
                self.assertNotIn(secret, result["snapshotSerialized"])
        self.assertEqual(result["clearedCode"], "review-cleared")
        self.assertIsNone(result["reviewAfterClear"])

    def test_review_size_limit_fails_closed(self) -> None:
        fixture, _ = build_capture_fixture()
        encoded = base64.b64encode(fixture).decode("ascii")
        result = self.run_js(
            f"""
  const bytes = Uint8Array.from(Buffer.from({json.dumps(encoded)}, "base64"));
  const session = contract.createPcapCapture({{ maxReviewBytes: 32 }});
  session.authorize({{ acknowledged: true }});
  return session.reviewCapture(bytes, {{ fileName: "fixture.pcap" }});
"""
        )
        self.assertIs(result["ok"], False)
        self.assertEqual(result["code"], "capture-too-large")

    def test_clear_requires_confirmation_and_refuses_while_capturing(self) -> None:
        result = self.run_js(
            """
  const calls = { start: 0, stop: 0, clear: 0 };
  const provider = {
    kind: "non-root-helper",
    label: "explicit helper",
    start: () => {
      calls.start += 1;
      return { id: "capture-1" };
    },
    stop: () => {
      calls.stop += 1;
      return { stopped: true };
    },
    clear: () => {
      calls.clear += 1;
      return { cleared: true };
    },
  };
  const session = contract.createPcapCapture({ provider });
  session.authorize({ acknowledged: true });
  const unconfirmed = session.clearCaptures({ confirmed: false });
  const callsAfterUnconfirmed = { ...calls };
  session.start({ acknowledged: true });
  const active = session.clearCaptures({ confirmed: true });
  const callsAfterActive = { ...calls };
  session.stop();
  const confirmed = session.clearCaptures({ confirmed: true });
  return {
    unconfirmed: { code: unconfirmed.code, cleared: unconfirmed.cleared },
    callsAfterUnconfirmed,
    active: { code: active.code, cleared: active.cleared },
    callsAfterActive,
    confirmed: { code: confirmed.code, cleared: confirmed.cleared },
    callsAfterConfirmed: calls,
  };
"""
        )
        self.assertEqual(result["unconfirmed"]["code"], "confirmation-required")
        self.assertIs(result["unconfirmed"]["cleared"], False)
        self.assertEqual(
            result["callsAfterUnconfirmed"], {"start": 0, "stop": 0, "clear": 0}
        )
        self.assertEqual(result["active"]["code"], "capture-active")
        self.assertIs(result["active"]["cleared"], False)
        self.assertEqual(
            result["callsAfterActive"], {"start": 1, "stop": 0, "clear": 0}
        )
        self.assertEqual(result["confirmed"]["code"], "cleared")
        self.assertIs(result["confirmed"]["cleared"], True)
        self.assertEqual(
            result["callsAfterConfirmed"], {"start": 1, "stop": 1, "clear": 1}
        )

    def test_unsafe_and_incomplete_providers_are_rejected(self) -> None:
        result = self.run_js(
            """
  const cases = {
    missing: null,
    noKind: { start: () => true, stop: () => true },
    unknownKind: { kind: "root-shell", start: () => true, stop: () => true },
    noStart: { kind: "fixture", stop: () => true },
    noStop: { kind: "fixture", start: () => true },
    noIndicator: {
      kind: "fixture",
      persistentIndicator: false,
      start: () => true,
      stop: () => true,
    },
    privileged: { kind: "fixture", privileged: true, start: () => true, stop: () => true },
    root: { kind: "fixture", root: true, start: () => true, stop: () => true },
    raw: { kind: "fixture", rawSockets: true, start: () => true, stop: () => true },
    upload: { kind: "fixture", upload: true, start: () => true, stop: () => true },
    telemetry: { kind: "fixture", telemetry: true, start: () => true, stop: () => true },
    hidden: { kind: "fixture", hiddenService: true, start: () => true, stop: () => true },
    autoStart: { kind: "fixture", autoStart: true, start: () => true, stop: () => true },
  };
  return Object.fromEntries(
    Object.entries(cases).map(([name, provider]) => {
      const inspected = contract.inspectCaptureProvider(provider);
      return [name, { ok: inspected.ok, code: inspected.code, message: inspected.message }];
    }),
  );
"""
        )
        expected = {
            "missing": "provider-missing",
            "noKind": "unapproved-provider",
            "unknownKind": "unapproved-provider",
            "noStart": "provider-missing",
            "noStop": "provider-missing",
            "noIndicator": "indicator-required",
            "privileged": "unsafe-provider",
            "root": "unsafe-provider",
            "raw": "unsafe-provider",
            "upload": "unsafe-provider",
            "telemetry": "unsafe-provider",
            "hidden": "unsafe-provider",
            "autoStart": "unsafe-provider",
        }
        for name, code in expected.items():
            with self.subTest(name=name):
                self.assertIs(result[name]["ok"], False)
                self.assertEqual(result[name]["code"], code)
                self.assertTrue(result[name]["message"])

    def test_throwing_provider_metadata_fails_closed(self) -> None:
        result = self.run_js(
            """
  const hostile = {
    start: () => true,
    stop: () => true,
  };
  Object.defineProperty(hostile, "kind", {
    get() {
      throw new Error("metadata exploded");
    },
  });
  const inspected = contract.inspectCaptureProvider(hostile);
  const session = contract.createPcapCapture({ provider: hostile });
  const status = session.getProviderStatus();
  session.authorize({ acknowledged: true });
  const started = session.start({ acknowledged: true });
  return {
    inspected: {
      ok: inspected.ok,
      code: inspected.code,
      message: inspected.message,
    },
    status: { ok: status.ok, code: status.code },
    started: { code: started.code, message: started.message },
    hasProvider: session.hasProvider(),
    state: started.state.state,
    indicator: started.state.indicator,
  };
"""
        )
        self.assertIs(result["inspected"]["ok"], False)
        self.assertEqual(result["inspected"]["code"], "provider-inspection-failed")
        self.assertIn("metadata exploded", result["inspected"]["message"])
        self.assertIs(result["status"]["ok"], False)
        self.assertEqual(result["status"]["code"], "provider-inspection-failed")
        self.assertIs(result["hasProvider"], False)
        self.assertEqual(result["started"]["code"], "provider-inspection-failed")
        self.assertEqual(result["state"], "idle")
        self.assertIs(result["indicator"]["visible"], False)

    def test_provider_failures_and_async_results_fail_safely(self) -> None:
        result = self.run_js(
            """
  function authorized(provider) {
    const session = contract.createPcapCapture({ provider });
    session.authorize({ acknowledged: true });
    return session;
  }
  const throwing = authorized({
    kind: "fixture",
    start: () => {
      throw new Error("fixture start exploded");
    },
    stop: () => true,
  });
  const throwingResult = throwing.start({ acknowledged: true });
  const asyncResult = authorized({
    kind: "fixture",
    start: () => Promise.resolve({ id: "late" }),
    stop: () => true,
  }).start({ acknowledged: true });
  const refused = authorized({
    kind: "fixture",
    start: () => ({ started: false, reason: "no tun device" }),
    stop: () => true,
  }).start({ acknowledged: true });

  const stopFailureSession = authorized({
    kind: "fixture",
    start: () => ({ id: "capture-1" }),
    stop: () => {
      throw new Error("fixture stop exploded");
    },
  });
  stopFailureSession.start({ acknowledged: true });
  const stopFailure = stopFailureSession.stop();

  const clearFailureSession = authorized({
    kind: "fixture",
    start: () => ({ id: "capture-1" }),
    stop: () => true,
    clear: () => {
      throw new Error("fixture clear exploded");
    },
  });
  const clearFailure = clearFailureSession.clearCaptures({ confirmed: true });

  return {
    throwing: {
      code: throwingResult.code,
      state: throwingResult.state.state,
      indicator: throwingResult.state.indicator,
    },
    asyncResult: { code: asyncResult.code, state: asyncResult.state.state },
    refused: { code: refused.code, message: refused.message },
    stopFailure: {
      code: stopFailure.code,
      stopped: stopFailure.stopped,
      state: stopFailure.state.state,
      indicator: stopFailure.state.indicator,
    },
    clearFailure: {
      code: clearFailure.code,
      cleared: clearFailure.cleared,
      reviewCleared: clearFailure.reviewCleared,
    },
  };
"""
        )
        self.assertEqual(result["throwing"]["code"], "capture-start-failed")
        self.assertEqual(result["throwing"]["state"], "error")
        self.assertIs(result["throwing"]["indicator"]["visible"], False)
        self.assertEqual(result["asyncResult"]["code"], "async-provider-unsupported")
        self.assertEqual(result["asyncResult"]["state"], "error")
        self.assertEqual(result["refused"]["code"], "capture-refused")
        self.assertIn("no tun device", result["refused"]["message"])
        self.assertEqual(result["stopFailure"]["code"], "stop-failed")
        self.assertIs(result["stopFailure"]["stopped"], True)
        self.assertEqual(result["stopFailure"]["state"], "stopped")
        self.assertIs(result["stopFailure"]["indicator"]["visible"], False)
        self.assertEqual(result["clearFailure"]["code"], "clear-failed")
        self.assertIs(result["clearFailure"]["cleared"], False)


class PcapHelperTests(unittest.TestCase):
    def test_generated_fixture_summary_and_cli(self) -> None:
        fixture, metadata = build_capture_fixture()
        summary = helper.summarize(fixture)
        self.assertEqual(summary["packetCount"], 4)
        self.assertEqual(summary["format"]["name"], "pcap")
        self.assertEqual(summary["protocols"]["tcp"], 2)
        self.assertEqual(summary["protocols"]["udp"], 1)
        self.assertEqual(summary["protocols"]["arp"], 1)
        self.assertIs(summary["sensitive"]["hasPayload"], True)
        serialized = json.dumps(summary)
        for secret in metadata["secrets"]:
            with self.subTest(secret=secret):
                self.assertNotIn(secret, serialized)

        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "generated-fixture.pcap"
            path.write_bytes(fixture)
            result = subprocess.run(
                [
                    sys.executable,
                    str(HELPER),
                    "--input",
                    str(path),
                    "--pretty",
                ],
                text=True,
                capture_output=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["kind"], "pcap-review-helper")
        self.assertEqual(data["packetCount"], 4)
        self.assertNotIn("hunter2-secret", result.stdout)

    def test_helper_accepts_stdin_and_rejects_bad_input(self) -> None:
        fixture, _ = build_capture_fixture()
        result = subprocess.run(
            [sys.executable, str(HELPER)],
            input=fixture,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["packetCount"], 4)

        empty = subprocess.run(
            [sys.executable, str(HELPER)],
            input=b"",
            capture_output=True,
        )
        self.assertEqual(empty.returncode, 2)
        self.assertIn(b"empty-input", empty.stderr)

        malformed = subprocess.run(
            [sys.executable, str(HELPER)],
            input=b"not a capture",
            capture_output=True,
        )
        self.assertEqual(malformed.returncode, 2)
        self.assertIn(b"invalid-pcap", malformed.stderr)

    def test_helper_summarizes_pcapng(self) -> None:
        packets = build_capture_fixture()[1]["packets"][:2]
        summary = helper.summarize(pcapng(packets))
        self.assertEqual(summary["format"]["name"], "pcapng")
        self.assertEqual(summary["packetCount"], 2)
        self.assertEqual(summary["protocols"]["tcp"], 1)
        self.assertEqual(summary["protocols"]["udp"], 1)

    def test_helper_source_has_no_live_capture_or_network_code(self) -> None:
        text = read_text(HELPER)
        forbidden = re.compile(
            r"^\s*(?:import|from)\s+"
            r"(?:socket|ssl|http|urllib|requests|subprocess|paramiko)\b|"
            r"\bsocket\.|\bsubprocess\.|\bos\.system\s*\(",
            re.MULTILINE,
        )
        self.assertIsNone(
            forbidden.search(text), "helper contains live network or subprocess code"
        )
        self.assertIsNone(REMOTE_RE.search(text), "helper contains a remote URL")


class PcapSourceSafety(unittest.TestCase):
    def test_capture_page_has_controls_warnings_and_indicator(self) -> None:
        html = re.sub(r"\s+", " ", read_text(SECURITY_DIR / "index.html"))
        for value in (
            'id="capture-start"',
            'id="capture-stop"',
            'id="capture-clear"',
            'id="capture-consent"',
            'id="capture-indicator"',
            'id="capture-indicator-stop"',
            "Start capture",
            "Stop capture",
            "Clear captures",
            "persistent",
            "Payloads",
            "never starts a live capture",
            "No capture starts on first launch",
            "Review selected capture",
            "Not official GrapheneOS",
        ):
            with self.subTest(value=value):
                self.assertIn(value, html)

    def test_pure_contracts_have_no_dom_network_timers_or_storage(self) -> None:
        forbidden = re.compile(
            r"\bsetTimeout\s*\(|\bsetInterval\s*\(|"
            r"\brequestAnimationFrame\s*\(|\bfetch\s*\(|XMLHttpRequest|"
            r"\bWebSocket\b|\bsendBeacon\s*\(|serviceWorker|"
            r"new\s+Worker\s*\(|localStorage|sessionStorage|indexedDB|"
            r"\bnavigator\.|\bdocument\.|\bwindow\.|\bglobalThis\b|"
            r"\bchild_process\b|\bexecSync\b|\bspawnSync\b"
        )
        for path in (FORMAT_MODULE, CAPTURE_MODULE):
            text = read_text(path)
            with self.subTest(path=path.name):
                self.assertIsNone(
                    forbidden.search(text), f"{path.name} contains forbidden work"
                )
                self.assertIsNone(
                    REMOTE_RE.search(text), f"{path.name} contains a remote URL"
                )

    def test_security_page_references_are_local_and_exist(self) -> None:
        html = read_text(SECURITY_DIR / "index.html")
        for reference in REFERENCE_RE.findall(html):
            if reference.startswith(("#", "mailto:", "data:")):
                continue
            with self.subTest(reference=reference):
                self.assertIsNone(REMOTE_RE.search(reference), reference)
                target = (SECURITY_DIR / reference.split("#", 1)[0]).resolve()
                self.assertTrue(target.exists(), reference)

        for script_name in (
            "security.js",
            "security-panel.js",
            "network-inventory.js",
            "pcap-capture.js",
            "pcap-format.js",
        ):
            script = read_text(SECURITY_DIR / script_name)
            for reference in JS_IMPORT_RE.findall(script):
                if reference.startswith("."):
                    with self.subTest(js_reference=reference):
                        target = (SECURITY_DIR / reference).resolve()
                        self.assertTrue(target.exists(), reference)

    @unittest.skipUnless(NODE, "node is not installed")
    def test_javascript_syntax(self) -> None:
        for name in ("pcap-format.js", "pcap-capture.js", "security.js"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                target = pathlib.Path(directory) / f"{name}.mjs"
                target.write_text(read_text(SECURITY_DIR / name), encoding="utf-8")
                result = subprocess.run(
                    [NODE, "--check", str(target)],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


class GeneratedPcapFixture(unittest.TestCase):
    def test_fixture_is_not_committed_and_is_generated_at_test_time(self) -> None:
        fixture, _ = build_capture_fixture()
        self.assertTrue(fixture)
        tracked = subprocess.run(
            ["git", "ls-files", "*.pcap", "*.pcapng"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(tracked.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
