#!/usr/bin/env python3
"""Explicit Termux/native helper for the Castela local-network inventory.

This helper reads JSON from stdin (or ``--input``) and emits only host,
address, and empty service-hint fields. It does not scan, ping, open sockets,
probe ports, run subprocesses, or capture credentials. The normal invocation is
an explicit, user-started read of the non-privileged neighbor cache:

    ip -j neigh | python3 tools/network_inventory_helper.py --target 192.168.1.0/24

The app-side provider must validate this output again before display. Public,
documentation, shared, reserved, multicast, and unspecified ranges are refused.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import pathlib
import sys
from typing import Any

IPV4_PRIVATE = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)
IPV4_LINK_LOCAL = ipaddress.ip_network("169.254.0.0/16")
IPV4_LOOPBACK = ipaddress.ip_network("127.0.0.0/8")
IPV6_PRIVATE = ipaddress.ip_network("fc00::/7")
IPV6_LINK_LOCAL = ipaddress.ip_network("fe80::/10")
IPV6_LOOPBACK = ipaddress.ip_network("::1/128")

MAX_IPV4_HOSTS = 1024
MAX_IPV6_HOST_BITS = 64


class HelperError(ValueError):
    """A safe, user-facing helper failure."""


def _scope_for_network(
    network: ipaddress.IPv4Network | ipaddress.IPv6Network,
) -> str | None:
    if network.version == 4:
        for private in IPV4_PRIVATE:
            if network.subnet_of(private):
                return "private"
        if network.subnet_of(IPV4_LINK_LOCAL):
            return "link-local"
        if network.subnet_of(IPV4_LOOPBACK):
            return "loopback"
        return None

    if network.subnet_of(IPV6_PRIVATE):
        return "private"
    if network.subnet_of(IPV6_LINK_LOCAL):
        return "link-local"
    if network.subnet_of(IPV6_LOOPBACK):
        return "loopback"
    return None


def _allowed_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    if address.version == 4:
        return (
            any(address in network for network in IPV4_PRIVATE)
            or address in IPV4_LINK_LOCAL
            or address in IPV4_LOOPBACK
        )
    return (
        address in IPV6_PRIVATE
        or address in IPV6_LINK_LOCAL
        or address in IPV6_LOOPBACK
    )


def validate_target(
    text: str,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, str]:
    """Return a validated private/link-local network and its scope."""

    if not isinstance(text, str) or not text.strip():
        raise HelperError(
            "invalid-target: enter a private or link-local CIDR range."
        )
    if "%" in text:
        raise HelperError("invalid-target: CIDR targets cannot include a zone id.")

    try:
        network = ipaddress.ip_network(text.strip(), strict=False)
    except ValueError as error:
        raise HelperError(f"invalid-target: {error}") from error

    scope = _scope_for_network(network)
    if scope is None:
        raise HelperError(
            "public-range: only private, link-local, and loopback ranges are allowed."
        )
    if network.version == 4 and network.num_addresses > MAX_IPV4_HOSTS:
        raise HelperError(
            f"range-too-large: IPv4 inventory is limited to {MAX_IPV4_HOSTS} addresses."
        )
    if network.version == 6 and network.prefixlen < 128 - MAX_IPV6_HOST_BITS:
        raise HelperError(
            "range-too-large: IPv6 inventory is limited to /64 or narrower."
        )
    return network, scope


def parse_neighbors(payload: Any) -> list[str]:
    """Extract neighbor addresses without keeping MACs, credentials, or banners."""

    if isinstance(payload, dict):
        for key in ("neighbors", "neigh", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            raise HelperError(
                "invalid-input: expected a neighbor array or an object with a neighbors array."
            )
    if not isinstance(payload, list):
        raise HelperError("invalid-input: expected a JSON neighbor array.")

    addresses: list[str] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        address = entry.get("dst") or entry.get("destination") or entry.get("address")
        if not isinstance(address, str) or not address.strip():
            continue

        state = entry.get("state")
        if isinstance(state, list):
            state_text = " ".join(str(value) for value in state).upper()
        else:
            state_text = str(state or "").upper()
        if "FAILED" in state_text or "INCOMPLETE" in state_text:
            continue

        addresses.append(address.strip())
    return addresses


def build_inventory(target_text: str, payload: Any) -> dict[str, Any]:
    """Build a minimal inventory result from explicit neighbor-cache data."""

    network, scope = validate_target(target_text)
    hosts: list[dict[str, Any]] = []
    seen: set[str] = set()

    for text in parse_neighbors(payload):
        try:
            address = ipaddress.ip_address(text)
        except ValueError:
            continue
        if address.version != network.version:
            continue
        if address not in network or not _allowed_address(address):
            continue

        canonical = str(address)
        if canonical in seen:
            continue
        seen.add(canonical)
        hosts.append(
            {
                "host": "Unknown host",
                "address": canonical,
                "services": [],
            }
        )

    hosts.sort(key=lambda host: ipaddress.ip_address(host["address"]))
    return {
        "kind": "termux-helper",
        "provider": "ip-neigh",
        "target": str(network),
        "scope": scope,
        "hosts": hosts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a private/link-local target and convert explicit "
            "ip-neigh JSON into a minimal Castela inventory."
        )
    )
    parser.add_argument("--target", required=True, help="private or link-local CIDR")
    parser.add_argument(
        "--input",
        type=pathlib.Path,
        help="read neighbor JSON from this file instead of stdin",
    )
    parser.add_argument("--pretty", action="store_true", help="indent JSON output")
    args = parser.parse_args(argv)

    try:
        if args.input is None:
            text = sys.stdin.read()
        else:
            text = args.input.read_text(encoding="utf-8")
        payload = json.loads(text) if text.strip() else []
        result = build_inventory(args.target, payload)
    except (HelperError, json.JSONDecodeError, OSError) as error:
        print(f"network-inventory-helper: {error}", file=sys.stderr)
        return 2

    json.dump(result, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
