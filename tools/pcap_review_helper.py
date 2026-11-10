#!/usr/bin/env python3
"""Explicit non-root helper for offline Castela pcap/pcapng review.

This helper reads bytes from a user-selected file or stdin and emits a summary
of packet metadata only. It does not capture live traffic, open sockets, run
subprocesses, need root, or upload anything. Payload contents are counted but
never printed.

The normal invocation is an explicit, user-started review:

    python3 tools/pcap_review_helper.py --input capture.pcap
    cat capture.pcapng | python3 tools/pcap_review_helper.py --pretty

Classic pcap (microsecond and nanosecond, both byte orders) and pcapng are
supported. The app-side contract validates and re-summarizes the same file, so
a helper cannot inject payload text into the display.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import pathlib
import struct
import sys
from typing import Any

PCAP_REVIEW_ID = "com.castela.pcap-review"
MAX_PACKETS = 100_000
MAX_CONVERSATIONS = 20
MAX_ENDPOINTS = 20
MAX_PORTS = 20

SENSITIVE_PAYLOAD_WARNING = (
    "This capture includes packet payloads. Payloads can contain passwords, "
    "tokens, cookies, private messages, and third-party personal data. Keep "
    "the file local, do not upload it, and delete it when finished."
)
CAPTURE_METADATA_WARNING = (
    "Packet captures reveal who communicated with whom even when payloads are "
    "not shown. Treat this file as sensitive personal data."
)
PLAINTEXT_PORTS = {
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
}
VLAN_TYPES = {0x8100, 0x88A8, 0x9100}


class HelperError(ValueError):
    """A safe, user-facing helper failure."""


def _u16(data: bytes, offset: int, little: bool = False) -> int:
    return int.from_bytes(data[offset : offset + 2], "little" if little else "big")


def _u32(data: bytes, offset: int, little: bool = False) -> int:
    return int.from_bytes(data[offset : offset + 4], "little" if little else "big")


class Aggregator:
    def __init__(self) -> None:
        self.protocols = {
            "tcp": 0,
            "udp": 0,
            "icmp": 0,
            "ipv4": 0,
            "ipv6": 0,
            "arp": 0,
            "other": 0,
        }
        self.endpoints: dict[str, dict[str, Any]] = {}
        self.conversations: dict[str, dict[str, Any]] = {}
        self.ports: dict[str, dict[str, Any]] = {}
        self.plaintext_ports: dict[str, int] = {}
        self.unsupported_link_types: set[int] = set()
        self.payload_bytes = 0
        self.payload_packets = 0

    def endpoint(self, address: str, size: int) -> None:
        current = self.endpoints.get(address)
        if current is None:
            self.endpoints[address] = {"address": address, "packets": 1, "bytes": size}
        else:
            current["packets"] += 1
            current["bytes"] += size

    def conversation(
        self,
        protocol: str,
        source: str,
        destination: str,
        source_port: int | None,
        destination_port: int | None,
        size: int,
    ) -> None:
        left = f"{source}:{'' if source_port is None else source_port}"
        right = f"{destination}:{'' if destination_port is None else destination_port}"
        ordered = sorted((left, right))
        key = f"{protocol}|{ordered[0]}|{ordered[1]}"
        current = self.conversations.get(key)
        if current is None:
            self.conversations[key] = {
                "protocol": protocol,
                "source": source,
                "sourcePort": source_port,
                "destination": destination,
                "destinationPort": destination_port,
                "packets": 1,
                "bytes": size,
            }
        else:
            current["packets"] += 1
            current["bytes"] += size

    def port(self, protocol: str, port: int) -> None:
        key = f"{protocol}:{port}"
        current = self.ports.get(key)
        if current is None:
            self.ports[key] = {"protocol": protocol, "port": port, "packets": 1}
        else:
            current["packets"] += 1
        label = PLAINTEXT_PORTS.get(port)
        if label:
            self.plaintext_ports[label] = self.plaintext_ports.get(label, 0) + 1

    def payload(self, size: int) -> None:
        if size > 0:
            self.payload_bytes += size
            self.payload_packets += 1

    def _transport(self, data: bytes, network: dict[str, Any], size: int) -> None:
        offset = network["transportOffset"]
        available = max(0, len(data) - offset)
        protocol = network["protocol"]

        if protocol == 6:
            self.protocols["tcp"] += 1
            if available < 20:
                return
            source_port = _u16(data, offset)
            destination_port = _u16(data, offset + 2)
            header_length = (data[offset + 12] >> 4) * 4
            if header_length < 20:
                return
            self.conversation(
                "tcp",
                network["source"],
                network["destination"],
                source_port,
                destination_port,
                size,
            )
            self.port("tcp", source_port)
            self.port("tcp", destination_port)
            payload = max(
                0,
                min(
                    network["payloadLength"] - header_length,
                    len(data) - (offset + header_length),
                ),
            )
            self.payload(payload)
            return

        if protocol == 17:
            self.protocols["udp"] += 1
            if available < 8:
                return
            source_port = _u16(data, offset)
            destination_port = _u16(data, offset + 2)
            self.conversation(
                "udp",
                network["source"],
                network["destination"],
                source_port,
                destination_port,
                size,
            )
            self.port("udp", source_port)
            self.port("udp", destination_port)
            udp_length = _u16(data, offset + 4)
            declared = udp_length - 8 if udp_length >= 8 else 0
            self.payload(max(0, min(declared, len(data) - (offset + 8))))
            return

        if protocol in (1, 58):
            self.protocols["icmp"] += 1
            self.payload(max(0, network["payloadLength"] - 4))
            return

        self.protocols["other"] += 1
        self.payload(network["payloadLength"])

    def _ipv4(self, data: bytes, offset: int, size: int) -> bool:
        if len(data) < offset + 20:
            return False
        header_length = (data[offset] & 0x0F) * 4
        if data[offset] >> 4 != 4 or header_length < 20:
            return False
        if len(data) < offset + header_length:
            return False

        self.protocols["ipv4"] += 1
        total_length = _u16(data, offset + 2)
        protocol = data[offset + 9]
        source = str(ipaddress.IPv4Address(data[offset + 12 : offset + 16]))
        destination = str(ipaddress.IPv4Address(data[offset + 16 : offset + 20]))
        self.endpoint(source, size)
        self.endpoint(destination, size)

        available = max(0, len(data) - (offset + header_length))
        declared = total_length - header_length if total_length >= header_length else available
        self._transport(
            data,
            {
                "protocol": protocol,
                "source": source,
                "destination": destination,
                "transportOffset": offset + header_length,
                "payloadLength": min(declared, available),
            },
            size,
        )
        return True

    def _ipv6(self, data: bytes, offset: int, size: int) -> bool:
        if len(data) < offset + 40 or data[offset] >> 4 != 6:
            return False

        self.protocols["ipv6"] += 1
        source = str(ipaddress.IPv6Address(data[offset + 8 : offset + 24]))
        destination = str(ipaddress.IPv6Address(data[offset + 24 : offset + 40]))
        self.endpoint(source, size)
        self.endpoint(destination, size)

        declared_length = _u16(data, offset + 4)
        next_header = data[offset + 6]
        cursor = offset + 40
        remaining = declared_length
        extensions = {0, 43, 44, 51, 60}

        for _guard in range(8):
            if next_header not in extensions:
                break
            if len(data) < cursor + 2:
                return True
            if next_header == 44:
                if len(data) < cursor + 8:
                    return True
                next_header = data[cursor]
                cursor += 8
                remaining = max(0, remaining - 8)
                continue
            extension_length = (
                (data[cursor + 1] + 2) * 4
                if next_header == 51
                else (data[cursor + 1] + 1) * 4
            )
            if extension_length < 8 or len(data) < cursor + extension_length:
                return True
            next_header = data[cursor]
            cursor += extension_length
            remaining = max(0, remaining - extension_length)

        if next_header in extensions:
            self.protocols["other"] += 1
            return True

        available = max(0, len(data) - cursor)
        self._transport(
            data,
            {
                "protocol": next_header,
                "source": source,
                "destination": destination,
                "transportOffset": cursor,
                "payloadLength": min(remaining, available),
            },
            size,
        )
        return True

    def process(self, link_type: int, data: bytes, size: int) -> None:
        offset = 0
        ether_type: int | None = None

        if link_type == 1:
            if len(data) < 14:
                self.protocols["other"] += 1
                return
            ether_type = _u16(data, 12)
            offset = 14
            for _guard in range(2):
                if ether_type not in VLAN_TYPES:
                    break
                if len(data) < offset + 4:
                    self.protocols["other"] += 1
                    return
                ether_type = _u16(data, offset + 2)
                offset += 4
        elif link_type == 113:
            if len(data) < 16:
                self.protocols["other"] += 1
                return
            ether_type = _u16(data, 14)
            offset = 16
        elif link_type == 276:
            if len(data) < 20:
                self.protocols["other"] += 1
                return
            ether_type = _u16(data, 0)
            offset = 20
        elif link_type in (0, 108):
            if len(data) < 4:
                self.protocols["other"] += 1
                return
            version = data[0] >> 4
            offset = 0 if version in (4, 6) else 4
        elif link_type not in (101, 228, 229):
            self.protocols["other"] += 1
            self.unsupported_link_types.add(link_type)
            return

        if ether_type == 0x0800:
            if not self._ipv4(data, offset, size):
                self.protocols["other"] += 1
            return
        if ether_type == 0x86DD:
            if not self._ipv6(data, offset, size):
                self.protocols["other"] += 1
            return
        if ether_type == 0x0806:
            self.protocols["arp"] += 1
            return

        version = data[offset] >> 4 if len(data) > offset else 0
        if version == 4:
            if not self._ipv4(data, offset, size):
                self.protocols["other"] += 1
            return
        if version == 6:
            if not self._ipv6(data, offset, size):
                self.protocols["other"] += 1
            return
        self.protocols["other"] += 1


def _top(values: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return values[:limit]


def _build_summary(
    *,
    fmt: dict[str, Any],
    packet_count: int,
    captured_bytes: int,
    original_bytes: int,
    truncated_packets: int,
    first_timestamp: float | None,
    last_timestamp: float | None,
    aggregator: Aggregator,
    parse_errors: int,
    max_packets: int,
    reached_limit: bool,
) -> dict[str, Any]:
    endpoints = sorted(
        aggregator.endpoints.values(),
        key=lambda item: (
            -item["packets"],
            -item["bytes"],
            item["address"],
        ),
    )
    conversations = sorted(
        aggregator.conversations.values(),
        key=lambda item: (
            -item["packets"],
            -item["bytes"],
            item["source"],
            item["sourcePort"] or 0,
            item["destination"],
            item["destinationPort"] or 0,
        ),
    )
    ports = sorted(
        aggregator.ports.values(),
        key=lambda item: (-item["packets"], item["port"], item["protocol"]),
    )

    plaintext_services = sorted(aggregator.plaintext_ports)
    warnings = [
        {"code": "capture-metadata-sensitive", "message": CAPTURE_METADATA_WARNING}
    ]
    if aggregator.payload_packets > 0:
        warnings.append({"code": "sensitive-payload", "message": SENSITIVE_PAYLOAD_WARNING})
    if plaintext_services:
        warnings.append(
            {
                "code": "plaintext-service",
                "message": (
                    "Plaintext or weakly protected service ports were observed "
                    f"({', '.join(plaintext_services)}). These protocols can "
                    "expose credentials and content in payloads."
                ),
            }
        )
    if packet_count == 0:
        warnings.append(
            {
                "code": "empty-capture",
                "message": "The capture contains no packets. Check that the file is complete.",
            }
        )
    if truncated_packets > 0:
        warnings.append(
            {
                "code": "truncated-packets",
                "message": (
                    f"{truncated_packets} packet"
                    f"{'' if truncated_packets == 1 else 's'} were truncated by "
                    "the capture length. The summary only covers captured bytes."
                ),
            }
        )
    if aggregator.unsupported_link_types:
        warnings.append(
            {
                "code": "unsupported-link-type",
                "message": (
                    "Unsupported link-layer type"
                    f"{'' if len(aggregator.unsupported_link_types) == 1 else 's'}: "
                    f"{', '.join(str(value) for value in sorted(aggregator.unsupported_link_types))}. "
                    "Those packets are counted but not decoded."
                ),
            }
        )
    if parse_errors > 0:
        warnings.append(
            {
                "code": "parse-errors",
                "message": (
                    f"{parse_errors} malformed packet record"
                    f"{'' if parse_errors == 1 else 's'} were skipped safely."
                ),
            }
        )
    if reached_limit:
        warnings.append(
            {
                "code": "packet-limit",
                "message": (
                    f"Review stopped at the local limit of {max_packets} packets. "
                    "The summary covers only the first records."
                ),
            }
        )

    duration = (
        max(0.0, last_timestamp - first_timestamp)
        if first_timestamp is not None and last_timestamp is not None
        else None
    )
    risk = (
        "high"
        if aggregator.payload_packets > 0
        else "medium"
        if plaintext_services
        else "low"
    )
    return {
        "ok": True,
        "id": PCAP_REVIEW_ID,
        "kind": "pcap-review-helper",
        "format": fmt,
        "packetCount": packet_count,
        "capturedBytes": captured_bytes,
        "originalBytes": original_bytes,
        "truncatedPackets": truncated_packets,
        "firstTimestamp": first_timestamp,
        "lastTimestamp": last_timestamp,
        "durationSeconds": duration,
        "protocols": dict(aggregator.protocols),
        "endpoints": _top(endpoints, MAX_ENDPOINTS),
        "conversations": _top(conversations, MAX_CONVERSATIONS),
        "ports": _top(ports, MAX_PORTS),
        "payload": {
            "packets": aggregator.payload_packets,
            "bytes": aggregator.payload_bytes,
        },
        "sensitive": {
            "hasPayload": aggregator.payload_packets > 0,
            "plaintextServices": plaintext_services,
            "risk": risk,
            "warning": (
                SENSITIVE_PAYLOAD_WARNING
                if aggregator.payload_packets > 0
                else CAPTURE_METADATA_WARNING
            ),
        },
        "warnings": warnings,
        "parseErrors": parse_errors,
        "limits": {"maxPackets": max_packets, "reached": reached_limit},
    }


def _parse_classic(data: bytes, max_packets: int) -> dict[str, Any]:
    if len(data) < 24:
        raise HelperError("invalid-pcap: the file is shorter than its global header.")

    magic = data[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
        endian = "<"
        little = True
        resolution = "microsecond" if magic[0] == 0xD4 else "nanosecond"
    elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
        endian = ">"
        little = False
        resolution = "microsecond" if magic[2] == 0xC3 else "nanosecond"
    else:
        raise HelperError("unsupported-format: the pcap magic number is not supported.")

    version_major, version_minor = struct.unpack_from(endian + "HH", data, 4)
    link_type = struct.unpack_from(endian + "I", data, 20)[0] & 0xFFFF
    denominator = 1e9 if resolution == "nanosecond" else 1e6

    aggregator = Aggregator()
    offset = 24
    packet_count = 0
    captured_bytes = 0
    original_bytes = 0
    truncated_packets = 0
    parse_errors = 0
    first_timestamp: float | None = None
    last_timestamp: float | None = None
    reached_limit = False

    while offset + 16 <= len(data):
        if packet_count >= max_packets:
            reached_limit = True
            break
        seconds, fraction, captured_length, original_length = struct.unpack_from(
            endian + "IIII", data, offset
        )
        if captured_length > len(data) - (offset + 16):
            parse_errors += 1
            break
        start = offset + 16
        packet = data[start : start + captured_length]
        aggregator.process(link_type, packet, captured_length)
        packet_count += 1
        captured_bytes += captured_length
        original_bytes += original_length
        if captured_length < original_length:
            truncated_packets += 1
        timestamp = seconds + fraction / denominator
        first_timestamp = (
            timestamp if first_timestamp is None else min(first_timestamp, timestamp)
        )
        last_timestamp = (
            timestamp if last_timestamp is None else max(last_timestamp, timestamp)
        )
        offset = start + captured_length

    if offset < len(data) and not reached_limit:
        parse_errors += 1

    return _build_summary(
        fmt={
            "name": "pcap",
            "version": f"{version_major}.{version_minor}",
            "byteOrder": "little" if little else "big",
            "timestampResolution": resolution,
            "linkType": link_type,
        },
        packet_count=packet_count,
        captured_bytes=captured_bytes,
        original_bytes=original_bytes,
        truncated_packets=truncated_packets,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
        aggregator=aggregator,
        parse_errors=parse_errors,
        max_packets=max_packets,
        reached_limit=reached_limit,
    )


def _parse_options(data: bytes, start: int, end: int, little: bool) -> tuple[int, int]:
    offset = start
    resolution = 6
    timestamp_offset = 0
    while offset + 4 <= end:
        code = _u16(data, offset, little)
        length = _u16(data, offset + 2, little)
        offset += 4
        if code == 0:
            break
        if offset + length > end:
            break
        if code == 9 and length >= 1:
            resolution = data[offset]
        elif code == 14 and length >= 8:
            raw = int.from_bytes(data[offset : offset + 8], "little" if little else "big")
            if raw & (1 << 63):
                raw -= 1 << 64
            timestamp_offset = raw
        offset += length + ((4 - (length % 4)) % 4)
    return resolution, timestamp_offset


def _resolution_denominator(value: int) -> float:
    if value & 0x80:
        return float(2 ** (value & 0x7F))
    return float(10**value)


def _parse_pcapng(data: bytes, max_packets: int) -> dict[str, Any]:
    if len(data) < 28:
        raise HelperError("invalid-pcapng: the file is shorter than its section header.")

    aggregator = Aggregator()
    offset = 0
    little = True
    endian_known = False
    version_major = 1
    version_minor = 0
    sections = 0
    interfaces: list[dict[str, Any]] = []
    packet_count = 0
    captured_bytes = 0
    original_bytes = 0
    truncated_packets = 0
    parse_errors = 0
    first_timestamp: float | None = None
    last_timestamp: float | None = None
    reached_limit = False

    while offset + 12 <= len(data):
        is_section_header = data[offset : offset + 4] == b"\x0a\x0d\x0d\x0a"
        if is_section_header:
            bom = data[offset + 8 : offset + 12]
            if bom == b"\x1a\x2b\x3c\x4d":
                little = False
            elif bom == b"\x4d\x3c\x2b\x1a":
                little = True
            else:
                raise HelperError(
                    "invalid-pcapng: a section header has an unknown byte-order magic."
                )
            endian_known = True
        elif not endian_known:
            raise HelperError(
                "invalid-pcapng: the stream does not start with a section header block."
            )

        block_type = _u32(data, offset, little)
        block_length = _u32(data, offset + 4, little)
        if (
            block_length < 12
            or block_length % 4 != 0
            or offset + block_length > len(data)
        ):
            parse_errors += 1
            break
        if _u32(data, offset + block_length - 4, little) != block_length:
            parse_errors += 1
            break

        body_start = offset + 8
        body_end = offset + block_length - 4

        if block_type == 0x0A0D0D0A:
            sections += 1
            interfaces = []
            version_major = _u16(data, offset + 12, little)
            version_minor = _u16(data, offset + 14, little)
        elif block_type == 0x00000001:
            if body_end - body_start < 8:
                parse_errors += 1
            else:
                link_type = _u16(data, offset + 8, little)
                resolution, timestamp_offset = _parse_options(
                    data, offset + 16, body_end, little
                )
                interfaces.append(
                    {
                        "linkType": link_type,
                        "timestampResolution": resolution,
                        "timestampOffset": timestamp_offset,
                    }
                )
        elif block_type in (0x00000006, 0x00000002):
            if packet_count >= max_packets:
                reached_limit = True
                break
            enhanced = block_type == 0x00000006
            interface_id = (
                _u32(data, offset + 8, little)
                if enhanced
                else _u16(data, offset + 8, little)
            )
            timestamp_high = _u32(data, offset + 12, little)
            timestamp_low = _u32(data, offset + 16, little)
            captured_length = _u32(data, offset + 20, little)
            original_length = _u32(data, offset + 24, little)
            data_start = offset + 28
            iface = (
                interfaces[interface_id]
                if 0 <= interface_id < len(interfaces)
                else None
            )
            if (
                iface is None
                or data_start + captured_length > body_end
                or captured_length > len(data)
            ):
                parse_errors += 1
                offset += block_length
                continue
            packet = data[data_start : data_start + captured_length]
            aggregator.process(iface["linkType"], packet, captured_length)
            packet_count += 1
            captured_bytes += captured_length
            original_bytes += original_length
            if captured_length < original_length:
                truncated_packets += 1
            ticks = (timestamp_high << 32) | timestamp_low
            timestamp = (
                ticks / _resolution_denominator(iface["timestampResolution"])
                + iface["timestampOffset"]
            )
            first_timestamp = (
                timestamp if first_timestamp is None else min(first_timestamp, timestamp)
            )
            last_timestamp = (
                timestamp if last_timestamp is None else max(last_timestamp, timestamp)
            )
        elif block_type == 0x00000003:
            if packet_count >= max_packets:
                reached_limit = True
                break
            original_length = _u32(data, offset + 8, little)
            captured_length = min(original_length, body_end - (offset + 12))
            iface = interfaces[0] if interfaces else None
            if iface is None or offset + 12 + captured_length > body_end:
                parse_errors += 1
                offset += block_length
                continue
            packet = data[offset + 12 : offset + 12 + captured_length]
            aggregator.process(iface["linkType"], packet, captured_length)
            packet_count += 1
            captured_bytes += captured_length
            original_bytes += original_length
            if captured_length < original_length:
                truncated_packets += 1

        offset += block_length

    if offset < len(data) and not reached_limit:
        parse_errors += 1

    link_type = interfaces[0]["linkType"] if interfaces else None
    return _build_summary(
        fmt={
            "name": "pcapng",
            "version": f"{version_major}.{version_minor}",
            "byteOrder": "little" if little else "big",
            "timestampResolution": "per-interface",
            "linkType": link_type,
            "sections": sections,
            "interfaces": len(interfaces),
        },
        packet_count=packet_count,
        captured_bytes=captured_bytes,
        original_bytes=original_bytes,
        truncated_packets=truncated_packets,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
        aggregator=aggregator,
        parse_errors=parse_errors,
        max_packets=max_packets,
        reached_limit=reached_limit,
    )


def summarize(data: bytes, max_packets: int = MAX_PACKETS) -> dict[str, Any]:
    """Summarize user-supplied pcap/pcapng bytes without keeping payload text."""

    if not isinstance(data, (bytes, bytearray)):
        raise HelperError("invalid-input: pass capture bytes.")
    if not data:
        raise HelperError("empty-input: the selected capture file is empty.")
    limit = max_packets if isinstance(max_packets, int) and max_packets > 0 else MAX_PACKETS
    limit = min(limit, MAX_PACKETS)
    if data[:4] == b"\x0a\x0d\x0d\x0a":
        return _parse_pcapng(bytes(data), limit)
    return _parse_classic(bytes(data), limit)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize a user-selected pcap/pcapng file offline. No live capture, "
            "no root, no network, and no upload."
        )
    )
    parser.add_argument(
        "--input",
        type=pathlib.Path,
        help="read the capture from this file instead of stdin",
    )
    parser.add_argument(
        "--max-packets",
        type=int,
        default=MAX_PACKETS,
        help=f"stop after this many packets (default: {MAX_PACKETS})",
    )
    parser.add_argument("--pretty", action="store_true", help="indent JSON output")
    args = parser.parse_args(argv)

    try:
        data = args.input.read_bytes() if args.input else sys.stdin.buffer.read()
        result = summarize(data, max_packets=args.max_packets)
    except (HelperError, OSError) as error:
        print(f"pcap-review-helper: {error}", file=sys.stderr)
        return 2

    json.dump(result, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
