#!/usr/bin/env python3
"""Read-only diagnostic for the Castela private mobile defaults.

The diagnostic evaluates a JSON snapshot supplied by the operator. It does not
query a device, run adb, open a socket, start a service, change a setting, or
perform any power-state action.

Normal use::

    python3 tools/private_defaults_diagnostic.py --template > snapshot.json
    # Fill in observed values, then:
    python3 tools/private_defaults_diagnostic.py --input snapshot.json
    cat snapshot.json | python3 tools/private_defaults_diagnostic.py --json

Exit codes: 0 for a compliant snapshot (warnings allowed), 1 for a failing
snapshot (including warnings under ``--strict``), and 2 for invalid input.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

PROFILE = "castela-private-mobile-v1"
MAX_AUTO_LOCK_SECONDS = 60

DENIED_BY_DEFAULT = frozenset(
    {
        "ACCESS_BACKGROUND_LOCATION",
        "ACCESS_COARSE_LOCATION",
        "ACCESS_FINE_LOCATION",
        "ANSWER_PHONE_CALLS",
        "BIND_ACCESSIBILITY_SERVICE",
        "BIND_NOTIFICATION_LISTENER_SERVICE",
        "CALL_PHONE",
        "CAMERA",
        "MANAGE_EXTERNAL_STORAGE",
        "PACKAGE_USAGE_STATS",
        "QUERY_ALL_PACKAGES",
        "READ_CALL_LOG",
        "READ_CONTACTS",
        "READ_PHONE_STATE",
        "READ_SMS",
        "RECEIVE_BOOT_COMPLETED",
        "RECEIVE_SMS",
        "RECORD_AUDIO",
        "REQUEST_IGNORE_BATTERY_OPTIMIZATIONS",
        "SEND_SMS",
        "SYSTEM_ALERT_WINDOW",
        "WRITE_CALL_LOG",
        "WRITE_CONTACTS",
    }
)

# These are explicit offensive-tooling markers, not general network utilities.
# The installed-package scan is deliberately narrow so a lawful diagnostic
# utility or an unrelated package name is not flagged as an exploit framework.
OFFENSIVE_TOOL_MARKERS = (
    "aircrack",
    "bettercap",
    "burpsuite",
    "crackmapexec",
    "dsploit",
    "exploit",
    "hashcat",
    "hydra",
    "impacket",
    "kismet",
    "metasploit",
    "msfconsole",
    "nikto",
    "nmap",
    "reaver",
    "responder",
    "routersploit",
    "sqlmap",
    "wifite",
    "zanti",
)


class SnapshotError(ValueError):
    """The supplied snapshot is not a JSON object."""


def baseline_snapshot() -> dict[str, Any]:
    """Return a fresh compliant baseline in the diagnostic schema.

    The template is a set of expected values, not a substitute for observing
    the device. Replace each value with the fact collected during setup.
    """

    return {
        "profile": PROFILE,
        "device": {
            "model": "Pixel 9a",
            "codename": "tegu",
            "grapheneos": True,
            "build_type": "user",
        },
        "security": {
            "bootloader_locked": True,
            "verified_boot": "green",
            "selinux": "enforcing",
            "app_sandbox": True,
            "hardware_keystore": True,
        },
        "telemetry": {
            "enabled": False,
            "analytics": False,
            "crash_reporting": False,
            "remote_logging": False,
            "sdk_packages": [],
        },
        "startup": {
            "boot_components": [],
            "background_services": [],
            "periodic_jobs": [],
        },
        "tooling": {
            "offensive_packages": [],
            "offensive_binaries": [],
            "installed_packages": [],
        },
        "permissions": {
            "default_deny": True,
            "granted": {},
            "special_access": [],
        },
        "usb": {
            "data_enabled": False,
            "debugging_enabled": False,
            "accessory_mode": False,
        },
        "wifi": {
            "enabled": False,
            "auto_connect_open_networks": False,
            "randomized_mac": True,
            "scan_always_available": False,
            "wifi_direct": False,
            "hotspot_enabled": False,
        },
        "bluetooth": {
            "enabled": False,
            "discoverable": False,
            "ble_scanning": False,
            "auto_connect": False,
        },
        "nfc": {"enabled": False},
        "lock_screen": {
            "secure_lock": True,
            "auto_lock_seconds": 30,
            "hide_sensitive_notifications": True,
            "quick_settings_enabled": False,
            "smart_lock": False,
            "lock_screen_widgets": False,
            "usb_debugging_allowed": False,
        },
        "sensors": {
            "camera_indicator": True,
            "microphone_indicator": True,
            "indicators_obscured": False,
            "sensor_privacy_toggle": True,
            "camera_access": "ask",
            "microphone_access": "ask",
        },
        "padilha_ux": {
            "privacy_indicators_visible": True,
            "status_not_color_only": True,
            "text_scale_200": True,
            "talkback_labels": True,
            "reduced_motion": True,
            "lock_screen_branding": "wallpaper-only",
            "security_prompts_unmodified": True,
        },
    }


def _value(snapshot: Any, path: str) -> tuple[Any, bool]:
    current: Any = snapshot
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]
    return current, True


def _render(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    return repr(value)


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.findings: list[dict[str, str]] = []

    def add(self, code: str, severity: str, path: str, message: str) -> None:
        self.findings.append(
            {
                "code": code,
                "severity": severity,
                "path": path,
                "message": message,
            }
        )

    def equal(
        self,
        snapshot: Any,
        path: str,
        code: str,
        expected: Any,
        severity: str = "fail",
    ) -> None:
        self.checks += 1
        value, present = _value(snapshot, path)
        if not present:
            self.add(
                code,
                severity,
                path,
                f"missing required value; expected {_render(expected)}",
            )
            return
        if isinstance(expected, bool):
            matches = type(value) is bool and value is expected
        elif isinstance(expected, str):
            matches = isinstance(value, str) and value == expected
        else:
            matches = value == expected
        if not matches:
            self.add(
                code,
                severity,
                path,
                f"expected {_render(expected)}, got {_render(value)}",
            )

    def one_of(
        self,
        snapshot: Any,
        path: str,
        code: str,
        allowed: set[str],
        severity: str = "fail",
        allow_missing: bool = False,
    ) -> None:
        self.checks += 1
        value, present = _value(snapshot, path)
        if not present:
            if allow_missing:
                return
            self.add(
                code,
                severity,
                path,
                f"missing required value; expected one of {sorted(allowed)}",
            )
            return
        if not isinstance(value, str) or value not in allowed:
            self.add(
                code,
                severity,
                path,
                f"expected one of {sorted(allowed)}, got {_render(value)}",
            )

    def empty_list(
        self, snapshot: Any, path: str, code: str, severity: str = "fail"
    ) -> None:
        self.checks += 1
        value, present = _value(snapshot, path)
        if not present:
            self.add(code, severity, path, "missing required list; expected []")
            return
        if not isinstance(value, list):
            self.add(code, severity, path, "expected a list, got a non-list value")
            return
        if value:
            rendered = ", ".join(str(item) for item in value[:3])
            suffix = "" if len(value) <= 3 else f" (+{len(value) - 3} more)"
            self.add(
                code,
                severity,
                path,
                f"expected no entries, found {len(value)}: {rendered}{suffix}",
            )

    def no_offensive_markers(
        self, snapshot: Any, path: str, code: str, severity: str = "fail"
    ) -> None:
        self.checks += 1
        value, present = _value(snapshot, path)
        if not present:
            self.add(code, severity, path, "missing required package list")
            return
        if not isinstance(value, list):
            self.add(code, severity, path, "expected a package list, got a non-list")
            return
        for index, package in enumerate(value):
            if not isinstance(package, str):
                continue
            lowered = package.lower()
            for marker in OFFENSIVE_TOOL_MARKERS:
                if marker in lowered:
                    self.add(
                        code,
                        severity,
                        f"{path}[{index}]",
                        f"offensive-tool marker {marker!r} in package {package!r}",
                    )
                    break
        # The check is counted once for the list, not once per package.

    def no_denied_permissions(
        self, snapshot: Any, path: str, code: str, severity: str = "fail"
    ) -> None:
        self.checks += 1
        value, present = _value(snapshot, path)
        if not present:
            self.add(code, severity, path, "missing required permission map")
            return
        if not isinstance(value, dict):
            self.add(code, severity, path, "expected a package-to-permissions map")
            return
        for package in sorted(value):
            permissions = value[package]
            if not isinstance(permissions, list):
                self.add(
                    code,
                    severity,
                    f"{path}.{package}",
                    "expected a list of granted permissions",
                )
                continue
            for permission in permissions:
                if not isinstance(permission, str):
                    continue
                name = permission.strip()
                if name.startswith("android.permission."):
                    name = name.removeprefix("android.permission.")
                if name.upper() in DENIED_BY_DEFAULT:
                    self.add(
                        code,
                        severity,
                        f"{path}.{package}",
                        f"deny-by-default permission granted: {permission}",
                    )


def evaluate(snapshot: Any) -> dict[str, Any]:
    """Evaluate a snapshot and return a deterministic report.

    Missing or malformed privacy/security fields fail closed. The function does
    not read a device, perform network I/O, or mutate its input.
    """

    if not isinstance(snapshot, dict):
        raise SnapshotError("snapshot must be a JSON object")

    audit = Audit()

    audit.equal(snapshot, "profile", "profile", PROFILE)

    audit.equal(snapshot, "device.grapheneos", "device.grapheneos", True)
    audit.equal(snapshot, "device.build_type", "device.build-type", "user")

    audit.equal(snapshot, "security.bootloader_locked", "security.bootloader", True)
    audit.one_of(
        snapshot,
        "security.verified_boot",
        "security.verified-boot",
        {"green"},
    )
    audit.one_of(
        snapshot,
        "security.selinux",
        "security.selinux",
        {"enforcing"},
    )
    audit.equal(snapshot, "security.app_sandbox", "security.app-sandbox", True)
    audit.equal(
        snapshot,
        "security.hardware_keystore",
        "security.hardware-keystore",
        True,
    )

    for field in ("enabled", "analytics", "crash_reporting", "remote_logging"):
        audit.equal(
            snapshot,
            f"telemetry.{field}",
            f"telemetry.{field.replace('_', '-')}",
            False,
        )
    audit.empty_list(
        snapshot, "telemetry.sdk_packages", "telemetry.sdk-packages"
    )

    audit.empty_list(
        snapshot, "startup.boot_components", "startup.boot-components"
    )
    audit.empty_list(
        snapshot, "startup.background_services", "startup.background-services"
    )
    audit.empty_list(
        snapshot, "startup.periodic_jobs", "startup.periodic-jobs"
    )

    audit.empty_list(
        snapshot, "tooling.offensive_packages", "tooling.offensive-packages"
    )
    audit.empty_list(
        snapshot, "tooling.offensive_binaries", "tooling.offensive-binaries"
    )
    audit.no_offensive_markers(
        snapshot,
        "tooling.installed_packages",
        "tooling.offensive-installed",
    )

    audit.equal(
        snapshot, "permissions.default_deny", "permissions.default-deny", True
    )
    audit.no_denied_permissions(
        snapshot, "permissions.granted", "permissions.denied"
    )
    audit.empty_list(
        snapshot, "permissions.special_access", "permissions.special-access"
    )

    audit.equal(snapshot, "usb.data_enabled", "usb.data", False)
    audit.equal(snapshot, "usb.debugging_enabled", "usb.debugging", False)
    audit.equal(snapshot, "usb.accessory_mode", "usb.accessory", False)

    # Wi-Fi on is a warning, not a failure: the user may need it for updates.
    # Unsafe Wi-Fi exposure still fails closed below.
    audit.equal(snapshot, "wifi.enabled", "wifi.enabled", False, severity="warn")
    audit.equal(
        snapshot,
        "wifi.auto_connect_open_networks",
        "wifi.open-auto-connect",
        False,
    )
    audit.equal(snapshot, "wifi.randomized_mac", "wifi.randomized-mac", True)
    audit.equal(
        snapshot,
        "wifi.scan_always_available",
        "wifi.scan-always-available",
        False,
    )
    audit.equal(snapshot, "wifi.wifi_direct", "wifi.wifi-direct", False)
    audit.equal(snapshot, "wifi.hotspot_enabled", "wifi.hotspot", False)

    audit.equal(snapshot, "bluetooth.enabled", "bluetooth.enabled", False)
    audit.equal(
        snapshot, "bluetooth.discoverable", "bluetooth.discoverable", False
    )
    audit.equal(
        snapshot, "bluetooth.ble_scanning", "bluetooth.ble-scanning", False
    )
    audit.equal(
        snapshot, "bluetooth.auto_connect", "bluetooth.auto-connect", False
    )

    audit.equal(snapshot, "nfc.enabled", "nfc.enabled", False)

    audit.equal(
        snapshot, "lock_screen.secure_lock", "lock-screen.secure-lock", True
    )
    audit.checks += 1
    auto_lock, present = _value(snapshot, "lock_screen.auto_lock_seconds")
    if not present:
        audit.add(
            "lock-screen.auto-lock",
            "fail",
            "lock_screen.auto_lock_seconds",
            f"missing required value; expected 0 < seconds <= {MAX_AUTO_LOCK_SECONDS}",
        )
    elif (
        type(auto_lock) is not int
        or auto_lock <= 0
        or auto_lock > MAX_AUTO_LOCK_SECONDS
    ):
        audit.add(
            "lock-screen.auto-lock",
            "fail",
            "lock_screen.auto_lock_seconds",
            f"expected an integer from 1 to {MAX_AUTO_LOCK_SECONDS}, got {_render(auto_lock)}",
        )
    audit.equal(
        snapshot,
        "lock_screen.hide_sensitive_notifications",
        "lock-screen.sensitive-notifications",
        True,
    )
    audit.equal(
        snapshot,
        "lock_screen.quick_settings_enabled",
        "lock-screen.quick-settings",
        False,
    )
    audit.equal(
        snapshot, "lock_screen.smart_lock", "lock-screen.smart-lock", False
    )
    audit.equal(
        snapshot,
        "lock_screen.lock_screen_widgets",
        "lock-screen.widgets",
        False,
    )
    audit.equal(
        snapshot,
        "lock_screen.usb_debugging_allowed",
        "lock-screen.usb-debugging",
        False,
    )

    audit.equal(
        snapshot,
        "sensors.camera_indicator",
        "sensors.camera-indicator",
        True,
    )
    audit.equal(
        snapshot,
        "sensors.microphone_indicator",
        "sensors.microphone-indicator",
        True,
    )
    audit.equal(
        snapshot,
        "sensors.indicators_obscured",
        "sensors.indicators-obscured",
        False,
    )
    audit.equal(
        snapshot,
        "sensors.sensor_privacy_toggle",
        "sensors.privacy-toggle",
        True,
    )
    audit.one_of(
        snapshot,
        "sensors.camera_access",
        "sensors.camera-access",
        {"ask", "deny"},
    )
    audit.one_of(
        snapshot,
        "sensors.microphone_access",
        "sensors.microphone-access",
        {"ask", "deny"},
    )

    audit.equal(
        snapshot,
        "padilha_ux.privacy_indicators_visible",
        "ux.privacy-indicators",
        True,
    )
    audit.equal(
        snapshot,
        "padilha_ux.status_not_color_only",
        "ux.status-not-color-only",
        True,
    )
    audit.equal(
        snapshot, "padilha_ux.text_scale_200", "ux.text-scale-200", True
    )
    audit.equal(
        snapshot, "padilha_ux.talkback_labels", "ux.talkback-labels", True
    )
    audit.equal(
        snapshot, "padilha_ux.reduced_motion", "ux.reduced-motion", True
    )
    audit.equal(
        snapshot,
        "padilha_ux.lock_screen_branding",
        "ux.lock-screen-branding",
        "wallpaper-only",
    )
    audit.equal(
        snapshot,
        "padilha_ux.security_prompts_unmodified",
        "ux.security-prompts",
        True,
    )

    failures = sum(1 for item in audit.findings if item["severity"] == "fail")
    warnings = sum(1 for item in audit.findings if item["severity"] == "warn")
    return {
        "profile": PROFILE,
        "ok": failures == 0,
        "status": "pass" if failures == 0 else "fail",
        "checks": audit.checks,
        "failures": failures,
        "warnings": warnings,
        "findings": audit.findings,
    }


def format_text(report: dict[str, Any], strict: bool = False) -> str:
    lines = [
        "Castela private mobile defaults diagnostic",
        f"profile: {report['profile']}",
    ]
    for finding in report["findings"]:
        lines.append(
            f"{finding['severity'].upper()} [{finding['code']}] "
            f"{finding['path']}: {finding['message']}"
        )
    if not report["findings"]:
        lines.append("No findings.")
    result = "PASS" if report["ok"] else "FAIL"
    if strict and report["warnings"]:
        result = "FAIL"
    lines.append(
        f"result: {result} ({report['failures']} failure(s), "
        f"{report['warnings']} warning(s), {report['checks']} checks)"
    )
    if strict and report["warnings"]:
        lines.append("strict mode: warnings are treated as failures")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a read-only JSON snapshot of private mobile defaults. "
            "No device access, network access, service control, or power-state test."
        )
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--input",
        type=pathlib.Path,
        help="read the JSON snapshot from this file instead of stdin",
    )
    source.add_argument(
        "--template",
        action="store_true",
        help="print a compliant snapshot schema to fill in and exit",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit a machine-readable report"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures for the exit status",
    )
    args = parser.parse_args(argv)

    if args.template:
        json.dump(baseline_snapshot(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    try:
        if args.input is None:
            if sys.stdin.isatty():
                print(
                    "private-defaults-diagnostic: provide --input, pipe JSON, "
                    "or use --template",
                    file=sys.stderr,
                )
                return 2
            text = sys.stdin.read()
        else:
            text = args.input.read_text(encoding="utf-8")
        snapshot = json.loads(text) if text.strip() else {}
        report = evaluate(snapshot)
    except (OSError, json.JSONDecodeError, SnapshotError) as error:
        print(f"private-defaults-diagnostic: {error}", file=sys.stderr)
        return 2

    exit_failure = report["failures"] > 0 or (
        args.strict and report["warnings"] > 0
    )
    if args.json:
        output = dict(report)
        output["strict"] = args.strict
        output["ok"] = not exit_failure
        output["status"] = "pass" if not exit_failure else "fail"
        json.dump(output, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(format_text(report, strict=args.strict))
    return 1 if exit_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
