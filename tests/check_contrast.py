#!/usr/bin/env python3
"""Validate the Padilha design tokens and their WCAG contrast pairs."""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKENS_PATH = ROOT / "docs" / "branding" / "tokens.json"
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def srgb_channel(value: int) -> float:
    channel = value / 255.0
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    color = hex_color.lstrip("#")
    red, green, blue = (int(color[index : index + 2], 16) for index in (0, 2, 4))
    return (
        0.2126 * srgb_channel(red)
        + 0.7152 * srgb_channel(green)
        + 0.0722 * srgb_channel(blue)
    )


def contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (luminance(foreground), luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def main() -> int:
    if not TOKENS_PATH.is_file():
        print(f"FAIL missing {TOKENS_PATH.relative_to(ROOT)}")
        return 1

    try:
        data = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"FAIL invalid JSON in {TOKENS_PATH.relative_to(ROOT)}: {error}")
        return 1

    themes = data.get("themes")
    pairs = data.get("contrastPairs")
    if not isinstance(themes, dict) or not isinstance(pairs, list) or not pairs:
        print("FAIL tokens.json must contain themes and a non-empty contrastPairs list")
        return 1

    errors: list[str] = []

    for theme_name, theme in themes.items():
        if not isinstance(theme, dict):
            errors.append(f"theme {theme_name!r} is not an object")
            continue
        for token_name, value in theme.items():
            if not isinstance(value, str) or not HEX_RE.match(value):
                errors.append(
                    f"theme {theme_name!r} token {token_name!r} is not a #RRGGBB colour: {value!r}"
                )

    for index, pair in enumerate(pairs, start=1):
        if not isinstance(pair, dict):
            errors.append(f"contrast pair #{index} is not an object")
            continue

        name = pair.get("name", f"pair #{index}")
        theme_name = pair.get("theme")
        foreground_name = pair.get("foreground")
        background_name = pair.get("background")
        minimum = pair.get("min")

        if not isinstance(minimum, (int, float)):
            errors.append(f"{name}: min must be a number")
            continue

        theme = themes.get(theme_name)
        if not isinstance(theme, dict):
            errors.append(f"{name}: unknown theme {theme_name!r}")
            continue

        try:
            foreground = theme[foreground_name]
            background = theme[background_name]
        except KeyError as error:
            errors.append(f"{name}: unknown token {error}")
            continue

        ratio = contrast(foreground, background)
        status = "ok" if ratio + 1e-9 >= minimum else "FAIL"
        print(
            f"{status} {name}: {ratio:.2f}:1 "
            f"({foreground} on {background}, minimum {minimum}:1)"
        )
        if ratio + 1e-9 < minimum:
            errors.append(f"{name}: {ratio:.2f}:1 is below {minimum}:1")

    if errors:
        print("\nContrast validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"\nok {len(pairs)} contrast pairs and {len(themes)} themes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
