"""Security-panel registration, lab-mode, and capability-contract tests."""

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

SECURITY_DIR = ROOT / "preview" / "security"
MODULE = SECURITY_DIR / "security-panel.js"
MODULE_URL = MODULE.as_uri()
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
        script = f"""import * as panel from {json.dumps(MODULE_URL)};
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


class PanelRegistration(NodeContractTestCase):
    def test_security_panel_registers_its_four_tabs_and_safety_flags(self) -> None:
        registered = self.run_js(
            """
  const registry = panel.createPanelRegistry();
  const definition = panel.registerSecurityPanel(registry);
  return {
    id: definition.id,
    name: definition.name,
    registered: registry.get(panel.PANEL_ID)?.id ?? null,
    size: registry.size,
    tabIds: definition.tabs.map((tab) => tab.id),
    tabLabels: definition.tabs.map((tab) => tab.label),
    requiredTabIds: panel.REQUIRED_TAB_IDS,
    requiresLabMode: definition.requiresLabMode,
    autoRun: definition.autoRun,
    backgroundScanning: definition.backgroundScanning,
    hiddenService: definition.hiddenService,
    privileged: definition.privileged,
  };
"""
        )
        self.assertEqual(registered["id"], "com.castela.security")
        self.assertEqual(registered["registered"], "com.castela.security")
        self.assertEqual(registered["size"], 1)
        self.assertEqual(
            registered["tabIds"],
            ["network", "capture", "permissions", "integrity"],
        )
        self.assertEqual(registered["tabIds"], registered["requiredTabIds"])
        self.assertEqual(
            registered["tabLabels"],
            [
                "Network inventory",
                "Capture review",
                "Permission audit",
                "Device integrity",
            ],
        )
        self.assertIs(registered["requiresLabMode"], True)
        self.assertIs(registered["autoRun"], False)
        self.assertIs(registered["backgroundScanning"], False)
        self.assertIs(registered["hiddenService"], False)
        self.assertIs(registered["privileged"], False)

    def test_duplicate_registration_is_rejected(self) -> None:
        result = self.run_js(
            """
  const registry = panel.createPanelRegistry();
  panel.registerSecurityPanel(registry);
  try {
    panel.registerSecurityPanel(registry);
    return { threw: false };
  } catch (error) {
    return { threw: true, code: error.code };
  }
"""
        )
        self.assertIs(result["threw"], True)
        self.assertEqual(result["code"], "duplicate-panel")

    def test_incomplete_tab_set_cannot_register_as_security_panel(self) -> None:
        result = self.run_js(
            """
  const registry = panel.createPanelRegistry();
  const definition = panel.securityPanelDefinition();
  const incomplete = { ...definition, tabs: definition.tabs.slice(0, 3) };
  try {
    panel.registerSecurityPanel(registry, incomplete);
    return { threw: false };
  } catch (error) {
    return { threw: true, code: error.code };
  }
"""
        )
        self.assertIs(result["threw"], True)
        self.assertEqual(result["code"], "missing-required-tabs")

    def test_panel_claiming_automatic_or_privileged_work_is_rejected(self) -> None:
        result = self.run_js(
            """
  const invalid = {
    ...panel.securityPanelDefinition(),
    id: "com.castela.unsafe",
    autoRun: true,
    backgroundScanning: true,
    hiddenService: true,
    privileged: true,
  };
  const validation = panel.validatePanel(invalid);
  const registry = panel.createPanelRegistry();
  let code = null;
  try {
    registry.register(invalid);
  } catch (error) {
    code = error.code;
  }
  return { ok: validation.ok, errors: validation.errors, code };
"""
        )
        self.assertIs(result["ok"], False)
        self.assertEqual(result["code"], "invalid-panel")
        errors = " ".join(result["errors"])
        for term in (
            "automatic execution",
            "background scanning",
            "hidden services",
            "privileged panels",
        ):
            self.assertIn(term, errors)


class AuthorizationGating(NodeContractTestCase):
    def test_lab_mode_requires_acknowledgement_and_never_auto_runs(self) -> None:
        result = self.run_js(
            """
  let calls = 0;
  const probe = {
    networkInventory: () => ({ available: true, tool: "test-inventory" }),
    captureReview: () => true,
    permissionAudit: () => false,
    deviceIntegrity: () => ({ available: true }),
  };
  const actions = {
    network: (context) => {
      calls += 1;
      return { hosts: ["127.0.0.1"], context };
    },
  };
  const session = panel.createSecurityPanel({
    probe,
    actions,
    now: () => "2026-11-08T00:00:00Z",
  });

  const before = session.run("network");
  const callsAfterCreate = calls;
  const refused = session.authorize({ acknowledged: false });
  const authorized = session.authorize({ acknowledged: true });
  const callsAfterAuthorize = calls;
  const afterAuthorize = session.run("network");
  const callsAfterRun = calls;
  const stopped = session.stopAndClear();
  const resultsAfterStop = Object.keys(stopped.state.results);
  const afterStop = session.run("network");

  return {
    beforeCode: before.code,
    callsAfterCreate,
    refusedCode: refused.code,
    refusedLabMode: refused.state.labMode,
    authorizedCode: authorized.code,
    authorizedLabMode: authorized.state.labMode,
    sessionId: authorized.state.session.id,
    callsAfterAuthorize,
    afterAuthorizeCode: afterAuthorize.code,
    callsAfterRun,
    actionContext: afterAuthorize.data.context,
    stoppedCode: stopped.code,
    stoppedCleared: stopped.cleared,
    stoppedLabMode: stopped.state.labMode,
    stoppedSession: stopped.state.session,
    resultsAfterStop,
    afterStopCode: afterStop.code,
    lastStoppedAt: stopped.state.lastStoppedAt,
  };
"""
        )
        self.assertEqual(result["beforeCode"], "not-authorized")
        self.assertEqual(result["callsAfterCreate"], 0, "panel ran on construction")
        self.assertEqual(result["refusedCode"], "acknowledgement-required")
        self.assertEqual(result["refusedLabMode"], "locked")
        self.assertEqual(result["authorizedCode"], "authorized")
        self.assertEqual(result["authorizedLabMode"], "authorized")
        self.assertTrue(result["sessionId"])
        self.assertEqual(result["callsAfterAuthorize"], 0, "authorization auto-ran a tab")
        self.assertEqual(result["afterAuthorizeCode"], "complete")
        self.assertEqual(result["callsAfterRun"], 1)
        self.assertTrue(result["actionContext"]["authorized"])
        self.assertEqual(
            result["actionContext"]["session"], result["sessionId"]
        )
        self.assertEqual(result["stoppedCode"], "stopped")
        self.assertIs(result["stoppedCleared"], True)
        self.assertEqual(result["stoppedLabMode"], "locked")
        self.assertIsNone(result["stoppedSession"])
        self.assertEqual(result["resultsAfterStop"], [])
        self.assertEqual(result["afterStopCode"], "not-authorized")
        self.assertEqual(result["lastStoppedAt"], "2026-11-08T00:00:00Z")

    def test_tab_selection_is_bounded(self) -> None:
        result = self.run_js(
            """
  const session = panel.createSecurityPanel({ probe: {} });
  const valid = session.selectTab("integrity");
  const invalid = session.selectTab("general-settings");
  return {
    validCode: valid.code,
    active: valid.state.activeTab,
    invalidCode: invalid.code,
    activeAfterInvalid: invalid.state.activeTab,
  };
"""
        )
        self.assertEqual(result["validCode"], "selected")
        self.assertEqual(result["active"], "integrity")
        self.assertEqual(result["invalidCode"], "unknown-tab")
        self.assertEqual(result["activeAfterInvalid"], "integrity")


class MissingCapabilities(NodeContractTestCase):
    def test_empty_probe_renders_graceful_unavailable_states(self) -> None:
        result = self.run_js(
            """
  const capabilities = panel.detectCapabilities({});
  const session = panel.createSecurityPanel({ capabilities });
  const authorized = session.authorize({ acknowledged: true });
  const runs = Object.fromEntries(
    panel.PANEL_TABS.map((tab) => [tab.id, session.run(tab.id).code]),
  );
  return {
    authorized: authorized.code,
    capabilities: Object.fromEntries(
      Object.entries(capabilities).map(([id, capability]) => [
        id,
        {
          available: capability.available,
          status: capability.status,
          hasReason: typeof capability.reason === "string" && capability.reason.length > 0,
          tool: capability.tool,
        },
      ]),
    ),
    runs,
  };
"""
        )
        self.assertEqual(result["authorized"], "authorized")
        for tab_id in ("network", "capture", "permissions", "integrity"):
            with self.subTest(tab=tab_id):
                capability = result["capabilities"][tab_id]
                self.assertIs(capability["available"], False)
                self.assertEqual(capability["status"], "unavailable")
                self.assertIs(capability["hasReason"], True)
                self.assertIsNone(capability["tool"])
                self.assertEqual(result["runs"][tab_id], "capability-unavailable")

    def test_throwing_and_privileged_probes_fail_closed(self) -> None:
        result = self.run_js(
            """
  const capabilities = panel.detectCapabilities({
    networkInventory: () => {
      throw new Error("probe exploded");
    },
    captureReview: () => false,
    permissionAudit: () => ({ available: true, privileged: true }),
    deviceIntegrity: () => ({ available: true, tool: "local-verifier" }),
  });
  return Object.fromEntries(
    Object.entries(capabilities).map(([id, capability]) => [
      id,
      {
        available: capability.available,
        reason: capability.reason,
        rejected: capability.rejected ?? null,
        tool: capability.tool,
      },
    ]),
  );
"""
        )
        self.assertIs(result["network"]["available"], False)
        self.assertEqual(result["network"]["rejected"], "probe-failed")
        self.assertIn("probe exploded", result["network"]["reason"])
        self.assertIs(result["capture"]["available"], False)
        self.assertTrue(result["capture"]["reason"])
        self.assertIs(result["permissions"]["available"], False)
        self.assertEqual(result["permissions"]["rejected"], "privileged-provider")
        self.assertIn("privileged", result["permissions"]["reason"].lower())
        self.assertIs(result["integrity"]["available"], True)
        self.assertEqual(result["integrity"]["tool"], "local-verifier")

    def test_available_capability_without_action_fails_safely(self) -> None:
        result = self.run_js(
            """
  const session = panel.createSecurityPanel({
    probe: { networkInventory: () => ({ available: true, tool: "inventory" }) },
  });
  session.authorize({ acknowledged: true });
  return session.run("network");
"""
        )
        self.assertIs(result["ok"], False)
        self.assertEqual(result["code"], "no-action")
        self.assertIn("No local action", result["message"])


class SecurityPanelSourceSafety(unittest.TestCase):
    def test_page_has_warning_lab_mode_tabs_and_stop_clear(self) -> None:
        html = read_text(SECURITY_DIR / "index.html")
        for value in (
            "Authorized use only",
            "Authorize lab mode",
            "Stop and clear",
            "Lab mode is locked",
            "Network inventory",
            "Capture review",
            "Permission audit",
            "Device integrity",
            "Not official GrapheneOS",
            "no telemetry",
        ):
            with self.subTest(value=value):
                self.assertIn(value, html)
        for tab_id in ("network", "capture", "permissions", "integrity"):
            with self.subTest(tab=tab_id):
                self.assertIn(f'data-tab="{tab_id}"', html)
                self.assertIn(f'data-tab-panel="{tab_id}"', html)

    def test_front_end_has_no_timers_workers_network_or_storage(self) -> None:
        forbidden = re.compile(
            r"\bsetTimeout\s*\(|\bsetInterval\s*\(|"
            r"\brequestAnimationFrame\s*\(|\bfetch\s*\(|XMLHttpRequest|"
            r"\bWebSocket\b|\bsendBeacon\s*\(|serviceWorker|"
            r"new\s+Worker\s*\(|localStorage|sessionStorage|indexedDB|"
            r"\bnavigator\.",
        )
        for name in ("security-panel.js", "security.js"):
            text = read_text(SECURITY_DIR / name)
            with self.subTest(name=name):
                self.assertIsNone(forbidden.search(text), f"{name} contains forbidden work")
                self.assertIsNone(REMOTE_RE.search(text), f"{name} contains a remote URL")

    def test_pure_contract_has_no_dom_or_browser_globals(self) -> None:
        text = read_text(SECURITY_DIR / "security-panel.js")
        for term in ("document.", "window.", "globalThis", "localStorage"):
            with self.subTest(term=term):
                self.assertNotIn(term, text)

    def test_all_page_references_are_local_and_exist(self) -> None:
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

        for script_name in ("security.js", "security-panel.js"):
            script = read_text(SECURITY_DIR / script_name)
            for reference in JS_IMPORT_RE.findall(script):
                if reference.startswith("."):
                    with self.subTest(js_reference=reference):
                        self.assertTrue(local_reference(reference).exists())

        for name in ("security.css", "security.js", "security-panel.js"):
            text = read_text(SECURITY_DIR / name)
            with self.subTest(name=name):
                self.assertIsNone(REMOTE_RE.search(text), f"{name} contains a remote URL")

    def test_css_text_colours_follow_theme_tokens(self) -> None:
        css = read_text(SECURITY_DIR / "security.css")
        declarations = re.findall(r"(?m)^\s*color\s*:\s*([^;]+);", css)
        self.assertTrue(declarations)
        for value in declarations:
            with self.subTest(value=value):
                self.assertTrue(
                    value.strip().startswith("var(--color-")
                    or value.strip() in {"currentColor", "inherit", "transparent"},
                    value,
                )

    @unittest.skipUnless(NODE, "node is not installed")
    def test_javascript_syntax(self) -> None:
        for name in ("security-panel.js", "security.js"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                target = pathlib.Path(directory) / f"{name}.mjs"
                target.write_text(read_text(SECURITY_DIR / name), encoding="utf-8")
                result = subprocess.run(
                    [NODE, "--check", str(target)],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
