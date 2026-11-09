"""Local-network inventory contract, fixture, UI, and helper tests."""

from __future__ import annotations

import html.parser
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.support import read_text  # noqa: E402
from tools import network_inventory_helper as helper  # noqa: E402

SECURITY_DIR = ROOT / "preview" / "security"
MODULE = SECURITY_DIR / "network-inventory.js"
MODULE_URL = MODULE.as_uri()
HELPER = ROOT / "tools" / "network_inventory_helper.py"
NODE = shutil.which("node")
REMOTE_RE = re.compile(r"https?://", re.IGNORECASE)
REFERENCE_RE = re.compile(r'(?:href|src)="([^"]+)"')
JS_IMPORT_RE = re.compile(r"(?:from|import)\s+[\"']([^\"']+)[\"']")


class ReferenceParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.references.append(value)


def local_reference(reference: str) -> pathlib.Path:
    reference = reference.split("#", 1)[0].split("?", 1)[0]
    return (SECURITY_DIR / reference).resolve()


@unittest.skipUnless(NODE, "node is not installed")
class NodeContractTestCase(unittest.TestCase):
    def run_js(self, body: str) -> dict:
        script = f"""import * as inventory from {json.dumps(MODULE_URL)};
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


class RangeValidation(NodeContractTestCase):
    def test_private_link_local_loopback_and_ula_ranges_are_accepted(self) -> None:
        result = self.run_js(
            """
  const inputs = [
    "10.0.0.0/24",
    "172.16.0.0/22",
    "192.168.1.0/24",
    "169.254.10.0/24",
    "127.0.0.1/32",
    "fd00::/64",
    "fe80::1/64",
    "::1/128",
  ];
  return inputs.map((input) => {
    const validated = inventory.validateTarget(input);
    return {
      input,
      ok: validated.ok,
      code: validated.code,
      canonical: validated.target?.canonical ?? null,
      scope: validated.target?.scope ?? null,
    };
  });
"""
        )
        scopes = {
            "10.0.0.0/24": "private",
            "172.16.0.0/22": "private",
            "192.168.1.0/24": "private",
            "169.254.10.0/24": "link-local",
            "127.0.0.1/32": "loopback",
            "fd00::/64": "private",
            "fe80::1/64": "link-local",
            "::1/128": "loopback",
        }
        for item in result:
            with self.subTest(input=item["input"]):
                self.assertIs(item["ok"], True, item)
                self.assertEqual(item["code"], "ok")
                self.assertEqual(item["scope"], scopes[item["input"]])
                self.assertTrue(item["canonical"])

    def test_public_shared_documentation_and_mixed_ranges_are_rejected(self) -> None:
        cases = {
            "8.8.8.0/24": "public-range",
            "1.1.1.1/32": "public-range",
            "0.0.0.0/0": "public-range",
            "100.64.0.0/24": "public-range",
            "192.0.2.0/24": "public-range",
            "224.0.0.0/24": "not-allowed-range",
            "255.255.255.0/24": "public-range",
            "2001:db8::/32": "public-range",
            "ff02::1/128": "not-allowed-range",
            "::/0": "public-range",
            "fe80::/9": "public-range",
            "192.168.0.0/15": "public-range",
            "10.0.0.0/7": "public-range",
            "169.254.0.0/15": "public-range",
        }
        result = self.run_js(
            f"""
  const cases = {json.dumps(cases)};
  return Object.fromEntries(
    Object.entries(cases).map(([input]) => {{
      const validated = inventory.validateTarget(input);
      return [input, {{
        ok: validated.ok,
        code: validated.code,
        message: validated.message,
      }}];
    }}),
  );
"""
        )
        for target, expected_code in cases.items():
            with self.subTest(target=target):
                self.assertIs(result[target]["ok"], False)
                self.assertEqual(result[target]["code"], expected_code)
                self.assertTrue(result[target]["message"])

    def test_malformed_targets_and_oversized_ranges_fail_closed(self) -> None:
        cases = {
            "not-an-ip/24": "invalid-target",
            "192.168.1.1/33": "invalid-prefix",
            "192.168.1.1/": "invalid-target",
            "192.168.1.1/024": "invalid-prefix",
            "999.1.1.1/24": "invalid-target",
            "10.0.0.0/8": "range-too-large",
            "172.16.0.0/20": "range-too-large",
            "fd00::/63": "range-too-large",
        }
        result = self.run_js(
            f"""
  const cases = {json.dumps(cases)};
  return Object.fromEntries(
    Object.entries(cases).map(([input]) => {{
      const validated = inventory.validateTarget(input);
      return [input, {{ ok: validated.ok, code: validated.code }}];
    }}),
  );
"""
        )
        for target, expected_code in cases.items():
            with self.subTest(target=target):
                self.assertIs(result[target]["ok"], False)
                self.assertEqual(result[target]["code"], expected_code)

    def test_host_bits_are_normalized_and_size_is_explained(self) -> None:
        result = self.run_js(
            """
  const v4 = inventory.validateTarget("192.168.1.50/24");
  const v6 = inventory.validateTarget("fe80::abcd/64");
  return {
    v4: v4.target,
    v6: v6.target,
  };
"""
        )
        self.assertEqual(result["v4"]["canonical"], "192.168.1.0/24")
        self.assertEqual(result["v4"]["first"], "192.168.1.0")
        self.assertEqual(result["v4"]["last"], "192.168.1.255")
        self.assertEqual(result["v4"]["addressCount"], 256)
        self.assertIs(result["v4"]["sweep"], False)
        self.assertEqual(result["v6"]["canonical"], "fe80::/64")
        self.assertIs(result["v6"]["neighborTable"], True)
        self.assertIn("neighbor-table", result["v6"]["addressCountText"])

    def test_address_classification_handles_ipv4_mapped_ipv6(self) -> None:
        result = self.run_js(
            """
  const privateMapped = inventory.classifyAddress("::ffff:192.168.1.1");
  const publicMapped = inventory.classifyAddress("::ffff:8.8.8.8");
  return {
    privateMapped: {
      ok: privateMapped.ok,
      scope: privateMapped.scope,
      allowed: privateMapped.allowed,
      canonical: privateMapped.canonical,
    },
    publicMapped: {
      ok: publicMapped.ok,
      scope: publicMapped.scope,
      allowed: publicMapped.allowed,
      canonical: publicMapped.canonical,
    },
  };
"""
        )
        self.assertIs(result["privateMapped"]["ok"], True)
        self.assertEqual(result["privateMapped"]["scope"], "private")
        self.assertIs(result["privateMapped"]["allowed"], True)
        self.assertIs(result["publicMapped"]["ok"], True)
        self.assertEqual(result["publicMapped"]["scope"], "public")
        self.assertIs(result["publicMapped"]["allowed"], False)


class AuthorizationAndProvider(NodeContractTestCase):
    def test_no_provider_call_before_authorization_and_stop_clears(self) -> None:
        result = self.run_js(
            """
  let calls = 0;
  const provider = {
    kind: "fixture",
    label: "fixture",
    discover: () => {
      calls += 1;
      return [{ hostname: "printer", address: "192.168.1.10", services: [{ port: 631 }] }];
    },
  };
  const session = inventory.createNetworkInventory({
    provider,
    now: () => "2026-11-09T00:00:00Z",
  });
  const before = session.scan("192.168.1.0/24");
  const callsAfterCreate = calls;
  const refused = session.authorize({ acknowledged: false });
  const callsAfterRefused = calls;
  const authorized = session.authorize({ acknowledged: true });
  const callsAfterAuthorize = calls;
  const complete = session.scan("192.168.1.0/24");
  const callsAfterScan = calls;
  const stopped = session.stopAndClear();
  const afterStop = session.scan("192.168.1.0/24");
  return {
    beforeCode: before.code,
    callsAfterCreate,
    refusedCode: refused.code,
    callsAfterRefused,
    authorizedCode: authorized.code,
    sessionId: authorized.state.session.id,
    statement: authorized.state.session.statement,
    callsAfterAuthorize,
    completeCode: complete.code,
    hosts: complete.hosts,
    callsAfterScan,
    stoppedCode: stopped.code,
    cleared: stopped.cleared,
    stoppedSession: stopped.state.session,
    stoppedHosts: stopped.state.hosts,
    afterStopCode: afterStop.code,
    callsAfterStop: calls,
  };
"""
        )
        self.assertEqual(result["beforeCode"], "not-authorized")
        self.assertEqual(result["callsAfterCreate"], 0)
        self.assertEqual(result["refusedCode"], "acknowledgement-required")
        self.assertEqual(result["callsAfterRefused"], 0)
        self.assertEqual(result["authorizedCode"], "authorized")
        self.assertTrue(result["sessionId"])
        self.assertIn(
            "I own or am authorized to test this network", result["statement"]
        )
        self.assertEqual(result["callsAfterAuthorize"], 0)
        self.assertEqual(result["completeCode"], "complete")
        self.assertEqual(result["hosts"][0]["address"], "192.168.1.10")
        self.assertEqual(result["callsAfterScan"], 1)
        self.assertEqual(result["stoppedCode"], "stopped")
        self.assertIs(result["cleared"], True)
        self.assertIsNone(result["stoppedSession"])
        self.assertEqual(result["stoppedHosts"], [])
        self.assertEqual(result["afterStopCode"], "not-authorized")
        self.assertEqual(result["callsAfterStop"], 1)

    def test_public_target_is_rejected_before_the_provider_runs(self) -> None:
        result = self.run_js(
            """
  let calls = 0;
  const session = inventory.createNetworkInventory({
    provider: {
      kind: "android-public-api",
      discover: () => {
        calls += 1;
        return [];
      },
    },
  });
  session.authorize({ acknowledged: true });
  const publicRun = session.scan("8.8.8.0/24");
  const publicHost = session.scan("0.0.0.0/0");
  return {
    publicCode: publicRun.code,
    rangeCode: publicHost.code,
    calls,
    hosts: session.snapshot().hosts,
  };
"""
        )
        self.assertEqual(result["publicCode"], "public-range")
        self.assertEqual(result["rangeCode"], "public-range")
        self.assertEqual(result["calls"], 0)
        self.assertEqual(result["hosts"], [])

    def test_unsafe_or_unapproved_providers_are_rejected(self) -> None:
        result = self.run_js(
            """
  const cases = {
    missing: null,
    noKind: { discover: () => [] },
    unknownKind: { kind: "root-shell", discover: () => [] },
    noDiscover: { kind: "fixture" },
    privileged: { kind: "termux-helper", discover: () => [], privileged: true },
    privilegedString: { kind: "termux-helper", discover: () => [], privileged: "yes" },
    root: { kind: "termux-helper", discover: () => [], root: true },
    raw: { kind: "termux-helper", discover: () => [], rawSockets: true },
    credentials: { kind: "termux-helper", discover: () => [], credentialCapture: true },
    bruteForce: { kind: "termux-helper", discover: () => [], bruteForce: true },
    exploit: { kind: "termux-helper", discover: () => [], exploit: true },
    capture: { kind: "termux-helper", discover: () => [], packetCapture: true },
    hidden: { kind: "termux-helper", discover: () => [], hiddenService: true },
  };
  return Object.fromEntries(
    Object.entries(cases).map(([name, provider]) => {
      const inspected = inventory.inspectProvider(provider);
      return [name, { ok: inspected.ok, code: inspected.code, message: inspected.message }];
    }),
  );
"""
        )
        expected = {
            "missing": "provider-missing",
            "noKind": "unapproved-provider",
            "unknownKind": "unapproved-provider",
            "noDiscover": "provider-missing",
            "privileged": "unsafe-provider",
            "privilegedString": "unsafe-provider",
            "root": "unsafe-provider",
            "raw": "unsafe-provider",
            "credentials": "unsafe-provider",
            "bruteForce": "unsafe-provider",
            "exploit": "unsafe-provider",
            "capture": "unsafe-provider",
            "hidden": "unsafe-provider",
        }
        for name, code in expected.items():
            with self.subTest(name=name):
                self.assertIs(result[name]["ok"], False)
                self.assertEqual(result[name]["code"], code)
                self.assertTrue(result[name]["message"])

    def test_throwing_provider_metadata_fails_closed(self) -> None:
        result = self.run_js(
            """
  const hostile = {};
  Object.defineProperty(hostile, "kind", {
    get() {
      throw new Error("metadata exploded");
    },
  });
  const inspected = inventory.inspectProvider(hostile);
  const session = inventory.createNetworkInventory({ provider: hostile });
  session.authorize({ acknowledged: true });
  const run = session.scan("192.168.1.0/24");
  return {
    inspected: {
      ok: inspected.ok,
      code: inspected.code,
      message: inspected.message,
    },
    run: { code: run.code, message: run.message },
    providerReady: session.hasProvider(),
  };
"""
        )
        self.assertIs(result["inspected"]["ok"], False)
        self.assertEqual(result["inspected"]["code"], "provider-inspection-failed")
        self.assertIn("metadata exploded", result["inspected"]["message"])
        self.assertIs(result["providerReady"], False)
        self.assertEqual(result["run"]["code"], "provider-inspection-failed")

    def test_provider_exception_async_result_and_invalid_payload_fail_safely(self) -> None:
        result = self.run_js(
            """
  function authorizedSession(provider) {
    const session = inventory.createNetworkInventory({ provider });
    session.authorize({ acknowledged: true });
    return session;
  }
  const throwing = authorizedSession({
    kind: "fixture",
    discover: () => {
      throw new Error("fixture exploded");
    },
  }).scan("192.168.1.0/24");
  const asyncResult = authorizedSession({
    kind: "fixture",
    discover: () => Promise.resolve([]),
  }).scan("192.168.1.0/24");
  const invalid = authorizedSession({
    kind: "fixture",
    discover: () => ({ unexpected: true }),
  }).scan("192.168.1.0/24");
  return {
    throwing: { code: throwing.code, message: throwing.message },
    asyncResult: { code: asyncResult.code, message: asyncResult.message },
    invalid: { code: invalid.code, message: invalid.message },
  };
"""
        )
        self.assertEqual(result["throwing"]["code"], "scan-failed")
        self.assertIn("fixture exploded", result["throwing"]["message"])
        self.assertEqual(result["asyncResult"]["code"], "async-provider-unsupported")
        self.assertEqual(result["invalid"]["code"], "invalid-provider-result")


class HostDisplay(NodeContractTestCase):
    def test_fixture_hosts_hints_filtering_and_credential_redaction(self) -> None:
        result = self.run_js(
            """
  const provider = {
    kind: "fixture",
    label: "offline fixture",
    discover: () => ({
      hosts: [
        {
          hostname: "printer",
          address: "192.168.1.10",
          services: [
            { port: 631, protocol: "tcp", hint: "spoofed", banner: "secret banner", username: "admin" },
            { port: 5353, protocol: "udp" },
            { port: 631, protocol: "tcp" },
          ],
        },
        {
          hostname: "nas",
          address: "192.168.1.11",
          ports: [22, 445],
          credential: "hunter2",
          password: "hunter2",
        },
        {
          hostname: "public-device",
          address: "8.8.8.8",
          services: [{ port: 443 }],
        },
        {
          hostname: "outside-device",
          address: "192.168.2.5",
        },
        {
          hostname: "malformed",
          address: "999.1.1.1",
        },
        {
          hostname: "no-address",
          credentials: { token: "secret-token" },
        },
        {
          hostname: "dup",
          address: "192.168.1.10",
        },
        {
          hostname: "bad\\u0000name\\u001f",
          address: "192.168.1.12",
        },
      ],
    }),
  };
  const session = inventory.createNetworkInventory({ provider });
  session.authorize({ acknowledged: true });
  const result = session.scan("192.168.1.0/24");
  return {
    result,
    serialized: JSON.stringify(result),
  };
"""
        )
        data = result["result"]
        self.assertIs(data["ok"], True)
        self.assertEqual(
            [host["address"] for host in data["hosts"]],
            ["192.168.1.10", "192.168.1.11", "192.168.1.12"],
        )
        self.assertEqual(data["hosts"][0]["host"], "printer")
        self.assertEqual(
            data["hosts"][0]["services"],
            [
                {"port": 631, "protocol": "tcp", "hint": "IPP printing"},
                {"port": 5353, "protocol": "udp", "hint": "mDNS / DNS-SD"},
            ],
        )
        self.assertEqual(
            data["hosts"][1]["services"],
            [
                {"port": 22, "protocol": "unknown", "hint": "SSH"},
                {"port": 445, "protocol": "unknown", "hint": "SMB file sharing"},
            ],
        )
        self.assertEqual(data["hosts"][2]["host"], "bad name")
        self.assertEqual(data["ignored"], 4)
        for forbidden in (
            "hunter2",
            "secret-token",
            "secret banner",
            "admin",
            "spoofed",
            "8.8.8.8",
            "192.168.2.5",
            "999.1.1.1",
            "credentials",
            "password",
            "banner",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, result["serialized"])

    def test_ipv6_fixture_is_limited_to_the_validated_range(self) -> None:
        result = self.run_js(
            """
  const session = inventory.createNetworkInventory({
    provider: {
      kind: "fixture",
      discover: () => [
        { hostname: "sensor", address: "fd00::10", services: [{ port: 443, protocol: "tcp" }] },
        { hostname: "printer", address: "fd00::11", services: [{ port: 631, protocol: "tcp" }] },
        { hostname: "public", address: "2001:db8::1", services: [{ port: 443 }] },
        { hostname: "link-local-outside", address: "fe80::1", services: [{ port: 80 }] },
      ],
    },
  });
  session.authorize({ acknowledged: true });
  const result = session.scan("fd00::/64");
  return {
    code: result.code,
    target: result.target,
    hosts: result.hosts,
    ignored: result.ignored,
  };
"""
        )
        self.assertEqual(result["code"], "complete")
        self.assertEqual(result["target"]["canonical"], "fd00::/64")
        self.assertIs(result["target"]["neighborTable"], True)
        self.assertEqual(
            [host["address"] for host in result["hosts"]], ["fd00::10", "fd00::11"]
        )
        self.assertEqual(result["ignored"], 2)

    def test_result_truncation_is_reported(self) -> None:
        result = self.run_js(
            """
  const session = inventory.createNetworkInventory({
    provider: {
      kind: "fixture",
      discover: () => Array.from({ length: 4 }, (_, index) => ({
        hostname: `host-${index}`,
        address: `192.168.1.${10 + index}`,
      })),
    },
  });
  session.authorize({ acknowledged: true });
  const result = session.scan("192.168.1.0/24", { maxHosts: 2 });
  return {
    count: result.hosts.length,
    truncated: result.truncated,
  };
"""
        )
        self.assertEqual(result["count"], 2)
        self.assertIs(result["truncated"], True)


class InventorySourceSafety(unittest.TestCase):
    def test_security_page_has_inventory_controls_and_authorization_text(self) -> None:
        html = read_text(SECURITY_DIR / "index.html")
        for value in (
            "I own or am authorized to test this network",
            'id="inventory-target"',
            'id="inventory-results"',
            'id="inventory-rows"',
            "Start local inventory",
            "service hints",
            "Public ranges",
            "Stop and clear",
            "Not official GrapheneOS",
        ):
            with self.subTest(value=value):
                self.assertIn(value, html)

    def test_inventory_contract_has_no_dom_network_timers_or_storage(self) -> None:
        text = read_text(MODULE)
        forbidden = re.compile(
            r"\bsetTimeout\s*\(|\bsetInterval\s*\(|"
            r"\brequestAnimationFrame\s*\(|\bfetch\s*\(|XMLHttpRequest|"
            r"\bWebSocket\b|\bsendBeacon\s*\(|serviceWorker|"
            r"new\s+Worker\s*\(|localStorage|sessionStorage|indexedDB|"
            r"\bnavigator\.|\bdocument\.|\bwindow\.|\bglobalThis\b|"
            r"\bchild_process\b|\bexecSync\b|\bspawnSync\b"
        )
        self.assertIsNone(forbidden.search(text), "inventory contract has forbidden work")
        self.assertIsNone(REMOTE_RE.search(text), "inventory contract has a remote URL")

    def test_page_references_are_local_and_exist(self) -> None:
        html = read_text(SECURITY_DIR / "index.html")
        parser = ReferenceParser()
        parser.feed(html)
        self.assertTrue(parser.references)
        for reference in parser.references:
            if reference.startswith(("#", "mailto:", "data:")):
                continue
            with self.subTest(reference=reference):
                self.assertIsNone(REMOTE_RE.search(reference), reference)
                self.assertTrue(local_reference(reference).exists(), reference)

        for script_name in ("security.js", "security-panel.js", "network-inventory.js"):
            script = read_text(SECURITY_DIR / script_name)
            for reference in JS_IMPORT_RE.findall(script):
                if reference.startswith("."):
                    with self.subTest(js_reference=reference):
                        self.assertTrue(local_reference(reference).exists())

    @unittest.skipUnless(NODE, "node is not installed")
    def test_javascript_syntax(self) -> None:
        for name in ("network-inventory.js", "security.js", "security-panel.js"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                target = pathlib.Path(directory) / f"{name}.mjs"
                target.write_text(read_text(SECURITY_DIR / name), encoding="utf-8")
                result = subprocess.run(
                    [NODE, "--check", str(target)],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


class TermuxHelperTests(unittest.TestCase):
    def test_helper_validates_private_targets_and_rejects_public(self) -> None:
        network, scope = helper.validate_target("192.168.1.9/24")
        self.assertEqual(str(network), "192.168.1.0/24")
        self.assertEqual(scope, "private")

        network, scope = helper.validate_target("fe80::1/64")
        self.assertEqual(str(network), "fe80::/64")
        self.assertEqual(scope, "link-local")

        for target in ("8.8.8.0/24", "192.168.0.0/15", "10.0.0.0/7"):
            with self.subTest(target=target):
                with self.assertRaises(helper.HelperError) as raised:
                    helper.validate_target(target)
                self.assertIn("public-range", str(raised.exception))

        for target in ("10.0.0.0/8", "fd00::/63"):
            with self.subTest(target=target):
                with self.assertRaises(helper.HelperError) as raised:
                    helper.validate_target(target)
                self.assertIn("range-too-large", str(raised.exception))

    def test_helper_keeps_only_valid_neighbor_addresses(self) -> None:
        payload = [
            {
                "dst": "192.168.1.10",
                "dev": "wlan0",
                "lladdr": "aa:bb:cc:dd:ee:ff",
                "state": ["REACHABLE"],
                "password": "hunter2",
            },
            {"dst": "192.168.1.11", "state": "STALE", "banner": "secret"},
            {"dst": "192.168.1.12", "state": ["FAILED"]},
            {"dst": "192.168.1.13", "state": ["INCOMPLETE"]},
            {"dst": "8.8.8.8", "state": ["REACHABLE"]},
            {"dst": "192.168.2.5", "state": ["REACHABLE"]},
            {"dst": "not-an-address", "state": ["REACHABLE"]},
        ]
        result = helper.build_inventory("192.168.1.0/24", payload)
        self.assertEqual(result["kind"], "termux-helper")
        self.assertEqual(
            [host["address"] for host in result["hosts"]],
            ["192.168.1.10", "192.168.1.11"],
        )
        serialized = json.dumps(result)
        for forbidden in ("aa:bb:cc:dd:ee:ff", "hunter2", "secret", "8.8.8.8"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_helper_cli_reads_fixture_and_refuses_public_range(self) -> None:
        payload = [
            {"dst": "192.168.1.10", "state": ["REACHABLE"]},
            {"dst": "8.8.8.8", "state": ["REACHABLE"]},
        ]
        result = subprocess.run(
            [
                sys.executable,
                str(HELPER),
                "--target",
                "192.168.1.0/24",
            ],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(
            [host["address"] for host in data["hosts"]], ["192.168.1.10"]
        )

        refused = subprocess.run(
            [sys.executable, str(HELPER), "--target", "8.8.8.0/24"],
            input="[]",
            text=True,
            capture_output=True,
        )
        self.assertEqual(refused.returncode, 2)
        self.assertIn("public-range", refused.stderr)

    def test_helper_has_no_socket_subprocess_or_credential_capture(self) -> None:
        text = read_text(HELPER)
        forbidden = re.compile(
            r"^\s*(?:import|from)\s+"
            r"(?:subprocess|socket|ssl|http|urllib|requests|telnetlib|ftplib|paramiko)\b|"
            r"\bos\.system\s*\(|\bsubprocess\.|\bsocket\.",
            re.MULTILINE,
        )
        self.assertIsNone(forbidden.search(text), "helper contains active network or subprocess code")
        self.assertIsNone(REMOTE_RE.search(text), "helper contains a remote URL")


if __name__ == "__main__":
    unittest.main()
