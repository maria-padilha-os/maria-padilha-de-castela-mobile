"""Shared helpers for the Padilha design-system tests."""

from __future__ import annotations

import json
import pathlib
import struct
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def xml_root(path: pathlib.Path) -> ET.Element:
    return ET.parse(path).getroot()


def png_size(path: pathlib.Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"{path} is not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def webp_size(path: pathlib.Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise AssertionError(f"{path} is not a WebP")
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8 ":
        if data[23:26] != b"\x9d\x01\x2a":
            raise AssertionError(f"{path} has an unexpected VP8 frame header")
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    raise AssertionError(f"{path} uses an unsupported WebP chunk {chunk!r}")


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")
