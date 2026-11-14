"""Private mobile defaults, setup checklist, and diagnostic tests."""

from __future__ import annotations

import copy
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.support import read_text  # noqa: E402
from tools import private_defaults_diagnostic as diagnostic  # noqa: E402

SCRIPT = ROOT / "tools" / "private_defaults_diagnostic.py"
DOC = ROOT / "docs" / "private-mobile-defaults.md"
CHECKLIST = ROOT / "docs" / "setup-checklist.md"
REMOTE_RE = re.compile(r"https?://", re.IGNORECASE)
FORBIDDEN_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+"
    r"(?:subprocess|socket|ssl|http|urllib|requests|paramiko)\b",
    re.MULTILINE,
)
FORBIDDEN_COMMAND_RE = re.compile(
    r"\b(?:reboot|suspend|poweroff|shutdown|systemctl|pkexec|sudo|pacman|mount)\b",
    re.IGNORECASE,
)


def snapshot() -> dict:
    return copy.deepcopy(diagnostic.baseline_snapshot())


def codes(report: dict) -> set[str]:
    return {finding["code"] for finding in report["findings"]}


def findings_for(report: dict, code: str) -> list[dict]:
    return [item for item in report["findings"] if item["code"] == code]


class BaselineTests(unittest.TestCase):
    def test_compliant_baseline_passes(self) -> None:
        report = diagnostic.evaluate(snapshot())
        self.assertIs(report["ok"], True)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["failures"], 0)
        self.assertEqual(report["warnings"], 0)
        self.assertEqual(report["findings"], [])
        self.assertGreater(report["checks"], 40)
        self.assertEqual(report["profile"], diagnostic.PROFILE)

    def test_baseline_is_a_fresh_object(self) -> None:
        first = diagnostic.baseline_snapshot()
        second = diagnostic.baseline_snapshot()
        self.assertIsNot(first, second)
        first["telemetry"]["enabled"] = True
        self.assertIs(second["telemetry"]["enabled"], False)

    def test_missing_sections_fail_closed(self) -> None:
        report = diagnostic.evaluate({})
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in (
            "profile",
            "device.grapheneos",
            "device.build-type",
            "security.bootloader",
            "security.verified-boot",
            "security.selinux",
            "security.app-sandbox",
            "security.hardware-keystore",
            "telemetry.enabled",
            "startup.boot-components",
            "tooling.offensive-packages",
            "permissions.default-deny",
            "usb.data",
            "wifi.open-auto-connect",
            "bluetooth.enabled",
            "lock-screen.secure-lock",
            "sensors.camera-indicator",
            "ux.privacy-indicators",
        ):
            with self.subTest(code=code):
                self.assertIn(code, found)

    def test_non_object_snapshot_is_rejected(self) -> None:
        for value in ([], "snapshot", 42, None):
            with self.subTest(value=value):
                with self.assertRaises(diagnostic.SnapshotError):
                    diagnostic.evaluate(value)


class SecurityInvariantTests(unittest.TestCase):
    def test_verified_boot_selinux_and_sandbox_failures_are_reported(self) -> None:
        data = snapshot()
        data["device"]["grapheneos"] = False
        data["device"]["build_type"] = "userdebug"
        data["security"]["bootloader_locked"] = False
        data["security"]["verified_boot"] = "yellow"
        data["security"]["selinux"] = "permissive"
        data["security"]["app_sandbox"] = False
        data["security"]["hardware_keystore"] = False
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in (
            "device.grapheneos",
            "device.build-type",
            "security.bootloader",
            "security.verified-boot",
            "security.selinux",
            "security.app-sandbox",
            "security.hardware-keystore",
        ):
            with self.subTest(code=code):
                self.assertIn(code, found)

    def test_wrong_field_types_do_not_pass_as_expected_values(self) -> None:
        data = snapshot()
        data["security"]["bootloader_locked"] = 1
        data["security"]["app_sandbox"] = "true"
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        self.assertIn("security.bootloader", codes(report))
        self.assertIn("security.app-sandbox", codes(report))


class TelemetryStartupAndToolingTests(unittest.TestCase):
    def test_telemetry_sdk_and_remote_logging_fail(self) -> None:
        data = snapshot()
        data["telemetry"].update(
            {
                "enabled": True,
                "analytics": True,
                "crash_reporting": True,
                "remote_logging": True,
                "sdk_packages": ["com.example.telemetry"],
            }
        )
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in (
            "telemetry.enabled",
            "telemetry.analytics",
            "telemetry.crash-reporting",
            "telemetry.remote-logging",
            "telemetry.sdk-packages",
        ):
            with self.subTest(code=code):
                self.assertIn(code, found)

    def test_boot_background_and_periodic_work_fail(self) -> None:
        data = snapshot()
        data["startup"] = {
            "boot_components": ["com.castela.launcher/.BootReceiver"],
            "background_services": ["com.castela.security/.SyncService"],
            "periodic_jobs": ["com.castela.security/.PollWorker"],
        }
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in (
            "startup.boot-components",
            "startup.background-services",
            "startup.periodic-jobs",
        ):
            with self.subTest(code=code):
                self.assertIn(code, found)

    def test_explicit_and_installed_offensive_tooling_fails(self) -> None:
        data = snapshot()
        data["tooling"] = {
            "offensive_packages": ["com.example.nmap"],
            "offensive_binaries": ["msfconsole"],
            "installed_packages": [
                "com.castela.launcher",
                "com.example.metasploit",
                "com.example.password-cracker",
            ],
        }
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in (
            "tooling.offensive-packages",
            "tooling.offensive-binaries",
            "tooling.offensive-installed",
        ):
            with self.subTest(code=code):
                self.assertIn(code, found)
        installed = findings_for(report, "tooling.offensive-installed")
        paths = " ".join(item["path"] for item in installed)
        self.assertIn("[1]", paths)
        self.assertNotIn("[0]", paths)

    def test_benign_installed_packages_do_not_fail(self) -> None:
        data = snapshot()
        data["tooling"]["installed_packages"] = [
            "com.castela.launcher",
            "com.castela.security",
            "com.android.settings",
            "org.example.network-inventory",
        ]
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], True)
        self.assertNotIn("tooling.offensive-installed", codes(report))


class PermissionTests(unittest.TestCase):
    def test_deny_by_default_and_denied_permissions_fail(self) -> None:
        data = snapshot()
        data["permissions"]["default_deny"] = False
        data["permissions"]["granted"] = {
            "com.castela.security": [
                "android.permission.QUERY_ALL_PACKAGES",
                "ACCESS_BACKGROUND_LOCATION",
                "android.permission.INTERNET",
            ]
        }
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        self.assertIn("permissions.default-deny", codes(report))
        denied = findings_for(report, "permissions.denied")
        self.assertEqual(len(denied), 2)
        messages = " ".join(item["message"] for item in denied)
        self.assertIn("QUERY_ALL_PACKAGES", messages)
        self.assertIn("ACCESS_BACKGROUND_LOCATION", messages)
        self.assertNotIn("INTERNET", messages)

    def test_special_access_fails(self) -> None:
        data = snapshot()
        data["permissions"]["special_access"] = [
            "accessibility",
            "notification-listener",
        ]
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        self.assertIn("permissions.special-access", codes(report))

    def test_normal_permissions_are_allowed(self) -> None:
        data = snapshot()
        data["permissions"]["granted"] = {
            "com.castela.security": [
                "android.permission.INTERNET",
                "android.permission.POST_NOTIFICATIONS",
                "android.permission.FOREGROUND_SERVICE",
                "android.permission.ACCESS_NETWORK_STATE",
            ]
        }
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], True)
        self.assertNotIn("permissions.denied", codes(report))


class ExposureTests(unittest.TestCase):
    def test_usb_exposure_fails(self) -> None:
        data = snapshot()
        data["usb"] = {
            "data_enabled": True,
            "debugging_enabled": True,
            "accessory_mode": True,
        }
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in ("usb.data", "usb.debugging", "usb.accessory"):
            with self.subTest(code=code):
                self.assertIn(code, found)

    def test_unsafe_wifi_exposure_fails_but_wifi_on_is_a_warning(self) -> None:
        data = snapshot()
        data["wifi"].update(
            {
                "enabled": True,
                "auto_connect_open_networks": True,
                "randomized_mac": False,
                "scan_always_available": True,
                "wifi_direct": True,
                "hotspot_enabled": True,
            }
        )
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in (
            "wifi.open-auto-connect",
            "wifi.randomized-mac",
            "wifi.scan-always-available",
            "wifi.wifi-direct",
            "wifi.hotspot",
        ):
            with self.subTest(code=code):
                self.assertIn(code, found)
        enabled = findings_for(report, "wifi.enabled")
        self.assertEqual(len(enabled), 1)
        self.assertEqual(enabled[0]["severity"], "warn")
        self.assertGreater(report["warnings"], 0)

    def test_wifi_on_alone_only_warns(self) -> None:
        data = snapshot()
        data["wifi"]["enabled"] = True
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], True)
        self.assertEqual(report["failures"], 0)
        self.assertEqual(report["warnings"], 1)
        self.assertEqual(report["findings"][0]["code"], "wifi.enabled")

    def test_bluetooth_and_nfc_exposure_fails(self) -> None:
        data = snapshot()
        data["bluetooth"] = {
            "enabled": True,
            "discoverable": True,
            "ble_scanning": True,
            "auto_connect": True,
        }
        data["nfc"]["enabled"] = True
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in (
            "bluetooth.enabled",
            "bluetooth.discoverable",
            "bluetooth.ble-scanning",
            "bluetooth.auto-connect",
            "nfc.enabled",
        ):
            with self.subTest(code=code):
                self.assertIn(code, found)


class LockScreenSensorAndUxTests(unittest.TestCase):
    def test_unsafe_lock_screen_fails(self) -> None:
        data = snapshot()
        data["lock_screen"] = {
            "secure_lock": False,
            "auto_lock_seconds": 0,
            "hide_sensitive_notifications": False,
            "quick_settings_enabled": True,
            "smart_lock": True,
            "lock_screen_widgets": True,
            "usb_debugging_allowed": True,
        }
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in (
            "lock-screen.secure-lock",
            "lock-screen.auto-lock",
            "lock-screen.sensitive-notifications",
            "lock-screen.quick-settings",
            "lock-screen.smart-lock",
            "lock-screen.widgets",
            "lock-screen.usb-debugging",
        ):
            with self.subTest(code=code):
                self.assertIn(code, found)

    def test_auto_lock_boundaries_and_types(self) -> None:
        cases = [
            (1, True),
            (30, True),
            (60, True),
            (61, False),
            (0, False),
            (-1, False),
            (True, False),
            ("30", False),
            (None, False),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                data = snapshot()
                data["lock_screen"]["auto_lock_seconds"] = value
                report = diagnostic.evaluate(data)
                self.assertEqual("lock-screen.auto-lock" not in codes(report), expected)

    def test_sensor_indicator_regressions_fail(self) -> None:
        data = snapshot()
        data["sensors"] = {
            "camera_indicator": False,
            "microphone_indicator": False,
            "indicators_obscured": True,
            "sensor_privacy_toggle": False,
            "camera_access": "allow",
            "microphone_access": "always",
        }
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in (
            "sensors.camera-indicator",
            "sensors.microphone-indicator",
            "sensors.indicators-obscured",
            "sensors.privacy-toggle",
            "sensors.camera-access",
            "sensors.microphone-access",
        ):
            with self.subTest(code=code):
                self.assertIn(code, found)

    def test_sensor_access_ask_or_deny_passes(self) -> None:
        for access in ("ask", "deny"):
            with self.subTest(access=access):
                data = snapshot()
                data["sensors"]["camera_access"] = access
                data["sensors"]["microphone_access"] = access
                report = diagnostic.evaluate(data)
                self.assertIs(report["ok"], True)

    def test_padilha_ux_review_regressions_fail(self) -> None:
        data = snapshot()
        data["padilha_ux"] = {
            "privacy_indicators_visible": False,
            "status_not_color_only": False,
            "text_scale_200": False,
            "talkback_labels": False,
            "reduced_motion": False,
            "lock_screen_branding": "system-themed",
            "security_prompts_unmodified": False,
        }
        report = diagnostic.evaluate(data)
        self.assertIs(report["ok"], False)
        found = codes(report)
        for code in (
            "ux.privacy-indicators",
            "ux.status-not-color-only",
            "ux.text-scale-200",
            "ux.talkback-labels",
            "ux.reduced-motion",
            "ux.lock-screen-branding",
            "ux.security-prompts",
        ):
            with self.subTest(code=code):
                self.assertIn(code, found)


class DiagnosticCliTests(unittest.TestCase):
    def run_cli(
        self, *args: str, input_text: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            input=input_text,
        )

    def test_template_is_valid_and_compliant(self) -> None:
        result = self.run_cli("--template")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data, diagnostic.baseline_snapshot())
        check = self.run_cli(input_text=result.stdout)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("result: PASS", check.stdout)

    def test_compliant_snapshot_exits_zero_in_text_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "snapshot.json"
            path.write_text(json.dumps(snapshot()), encoding="utf-8")
            text = self.run_cli("--input", str(path))
            machine = self.run_cli("--input", str(path), "--json")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("result: PASS", text.stdout)
        self.assertEqual(machine.returncode, 0, machine.stderr)
        report = json.loads(machine.stdout)
        self.assertIs(report["ok"], True)
        self.assertEqual(report["status"], "pass")
        self.assertIs(report["strict"], False)
        self.assertEqual(report["findings"], [])

    def test_failing_snapshot_exits_one_and_names_the_finding(self) -> None:
        data = snapshot()
        data["telemetry"]["enabled"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "snapshot.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli("--input", str(path))
            machine = self.run_cli("--input", str(path), "--json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL [telemetry.enabled]", result.stdout)
        self.assertEqual(machine.returncode, 1)
        report = json.loads(machine.stdout)
        self.assertIs(report["ok"], False)
        self.assertEqual(report["status"], "fail")

    def test_strict_turns_wifi_warning_into_failure(self) -> None:
        data = snapshot()
        data["wifi"]["enabled"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "snapshot.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            normal = self.run_cli("--input", str(path))
            strict = self.run_cli("--input", str(path), "--strict")
            machine = self.run_cli("--input", str(path), "--strict", "--json")
        self.assertEqual(normal.returncode, 0, normal.stderr)
        self.assertIn("WARN [wifi.enabled]", normal.stdout)
        self.assertEqual(strict.returncode, 1)
        self.assertIn("strict mode", strict.stdout)
        self.assertEqual(machine.returncode, 1)
        report = json.loads(machine.stdout)
        self.assertIs(report["ok"], False)
        self.assertEqual(report["warnings"], 1)

    def test_malformed_and_non_object_json_exit_two(self) -> None:
        malformed = self.run_cli(input_text="{not json")
        non_object = self.run_cli(input_text="[]")
        empty = self.run_cli(input_text="")
        self.assertEqual(malformed.returncode, 2)
        self.assertIn("private-defaults-diagnostic", malformed.stderr)
        self.assertEqual(non_object.returncode, 2)
        self.assertIn("snapshot must be a JSON object", non_object.stderr)
        self.assertEqual(empty.returncode, 1)
        self.assertIn("result: FAIL", empty.stdout)

    def test_missing_input_file_exits_two(self) -> None:
        result = self.run_cli("--input", str(ROOT / "does-not-exist.json"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("private-defaults-diagnostic", result.stderr)


class DiagnosticSourceSafety(unittest.TestCase):
    def test_script_has_no_device_network_subprocess_or_power_commands(self) -> None:
        text = read_text(SCRIPT)
        self.assertIsNone(
            FORBIDDEN_IMPORT_RE.search(text),
            "diagnostic imports device, network, or subprocess code",
        )
        self.assertIsNone(
            REMOTE_RE.search(text), "diagnostic contains a remote URL"
        )
        self.assertIsNone(
            FORBIDDEN_COMMAND_RE.search(text),
            "diagnostic contains a privileged or power-state command",
        )
        for term in ("sys.stdin", "pathlib.Path", "json.loads"):
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_script_does_not_execute_adb_or_write_files(self) -> None:
        text = read_text(SCRIPT)
        for term in (
            "subprocess.",
            "os.system",
            "os.popen",
            "adb ",
            "adb shell",
            "write_text(",
            "write_bytes(",
        ):
            with self.subTest(term=term):
                self.assertNotIn(term, text)


class DocumentationTests(unittest.TestCase):
    def test_private_defaults_document_has_required_boundaries(self) -> None:
        text = read_text(DOC)
        for term in (
            "Private mobile defaults",
            "no telemetry",
            "no unnecessary background services",
            "no default offensive tooling",
            "GrapheneOS security features that must remain untouched",
            "verified boot",
            "SELinux",
            "app sandbox",
            "USB",
            "Wi-Fi",
            "Bluetooth",
            "lock screen",
            "sensor indicators",
            "Padilha UX",
            "setup checklist",
            "diagnostic script",
            "No automatic suspend or reboot tests",
            "Do not weaken verified boot, SELinux, or app sandboxing",
        ):
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_setup_checklist_covers_operator_steps_and_refuses_privilege(self) -> None:
        text = read_text(CHECKLIST)
        for term in (
            "Private mobile setup checklist",
            "verified boot",
            "SELinux",
            "app sandbox",
            "no telemetry",
            "USB",
            "Wi-Fi",
            "Bluetooth",
            "lock screen",
            "sensor",
            "no default offensive tooling",
            "diagnostic",
            "suspend",
            "reboot",
            "stop and report",
            "privileged command",
        ):
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_docs_do_not_instruct_disabling_security_features(self) -> None:
        combined = read_text(DOC) + "\n" + read_text(CHECKLIST)
        for term in (
            "SELinux permissive mode",
            "bootloader unlock",
            "system-partition write",
        ):
            with self.subTest(term=term):
                self.assertIn(term, combined)
        # The documents may mention these only as forbidden actions.
        for sentence in combined.splitlines():
            if "setenforce 0" in sentence or "fastboot oem unlock" in sentence:
                self.assertTrue(
                    any(
                        token in sentence.lower()
                        for token in ("not ", "do **not**", "no ")
                    ),
                    sentence,
                )


if __name__ == "__main__":
    unittest.main()
