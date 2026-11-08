#!/usr/bin/env python3
"""Resolve the Padilha palette, including safe dynamic-colour fallbacks.

This module is the executable contract behind the Android resources, the
browser preview, and the contrast tests.  It deliberately has no third-party
dependencies so it can run in CI and on a developer laptop without the Android
SDK.

Resolution order
----------------
1. A dynamic (Material You style) accent supplied by the platform, but only if
   it passes every text-on-surface contrast check against the active Padilha
   theme.
2. The selected Padilha light or dark theme from ``tokens.json``.
3. A built-in copy of the Padilha palette, used when the token file is missing,
   unreadable, or contains an invalid colour.

The built-in fallback is intentionally the same safe palette as ``tokens.json``;
``tests/test_palette_fallback.py`` keeps the two copies in sync.
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKENS_PATH = ROOT / "docs" / "branding" / "tokens.json"

THEME_NAMES = ("light", "dark")
REQUIRED_TOKENS = (
    "background",
    "surface",
    "surfaceRaised",
    "scrim",
    "textPrimary",
    "textSecondary",
    "onScrim",
    "accent",
    "accentStrong",
    "onAccent",
    "onAccentStrong",
    "border",
    "success",
    "warning",
    "danger",
)

FALLBACK_THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "background": "#120C17",
        "surface": "#1D1424",
        "surfaceRaised": "#2A1D33",
        "scrim": "#120C17",
        "textPrimary": "#F6EDE3",
        "textSecondary": "#CDBFCB",
        "onScrim": "#F6EDE3",
        "accent": "#E58AA0",
        "accentStrong": "#E6B85C",
        "onAccent": "#241A28",
        "onAccentStrong": "#241A28",
        "border": "#8C7594",
        "success": "#7CC49A",
        "warning": "#E8B45A",
        "danger": "#F08A8A",
    },
    "light": {
        "background": "#FBF5EC",
        "surface": "#F3E8DA",
        "surfaceRaised": "#FFFFFF",
        "scrim": "#FBF5EC",
        "textPrimary": "#241A28",
        "textSecondary": "#5A4A57",
        "onScrim": "#241A28",
        "accent": "#7A2340",
        "accentStrong": "#7A5A1E",
        "onAccent": "#FFFFFF",
        "onAccentStrong": "#FFFFFF",
        "border": "#7A6355",
        "success": "#2F6B4A",
        "warning": "#7A4E00",
        "danger": "#9B1C1C",
    },
}

# The pair list mirrors tokens.json.  It is used only when the token file is
# unavailable, so a broken checkout still gets a meaningful validation result.
CONTRAST_PAIRS: tuple[tuple[str, str, str, float], ...] = (
    ("body text on background", "textPrimary", "background", 4.5),
    ("body text on surface", "textPrimary", "surface", 4.5),
    ("body text on raised surface", "textPrimary", "surfaceRaised", 4.5),
    ("secondary text on background", "textSecondary", "background", 4.5),
    ("secondary text on surface", "textSecondary", "surface", 4.5),
    ("text on scrim", "onScrim", "scrim", 4.5),
    ("accent on background", "accent", "background", 4.5),
    ("accent on surface", "accent", "surface", 4.5),
    ("strong accent on background", "accentStrong", "background", 4.5),
    ("text on accent", "onAccent", "accent", 4.5),
    ("text on strong accent", "onAccentStrong", "accentStrong", 4.5),
    ("success on background", "success", "background", 4.5),
    ("warning on background", "warning", "background", 4.5),
    ("danger on background", "danger", "background", 4.5),
    ("border on background", "border", "background", 3.0),
    ("border on surface", "border", "surface", 3.0),
)

# A dynamic accent may only replace these two tokens.  Semantic colours, text,
# borders, and surfaces stay under Padilha control.
DYNAMIC_ACCENT_TOKENS = ("accent", "onAccent")
DYNAMIC_ACCENT_PAIRS: tuple[tuple[str, str, float], ...] = (
    ("accent", "background", 4.5),
    ("accent", "surface", 4.5),
    ("accent", "surfaceRaised", 4.5),
    ("onAccent", "accent", 4.5),
)

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class PaletteError(ValueError):
    """Raised when a theme name or palette value cannot be resolved."""


def _is_hex(value: Any) -> bool:
    return isinstance(value, str) and bool(HEX_RE.match(value))


def normalize_hex(value: str) -> str:
    """Return an uppercase ``#RRGGBB`` value or raise ``PaletteError``."""
    if not _is_hex(value):
        raise PaletteError(f"not a #RRGGBB colour: {value!r}")
    return value.upper()


def srgb_channel(value: int) -> float:
    channel = value / 255.0
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    color = normalize_hex(hex_color).lstrip("#")
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


def best_text_on(background: str) -> str:
    """Pick black or white for a dynamic accent, whichever has more contrast."""
    dark = contrast("#000000", background)
    light = contrast("#FFFFFF", background)
    return "#000000" if dark >= light else "#FFFFFF"


def _read_contrast_pairs(data: dict[str, Any]) -> list[tuple[str, str, str, float]]:
    raw_pairs = data.get("contrastPairs")
    if not isinstance(raw_pairs, list) or not raw_pairs:
        return list(CONTRAST_PAIRS)

    pairs: list[tuple[str, str, str, float]] = []
    for index, pair in enumerate(raw_pairs, start=1):
        if not isinstance(pair, dict):
            return list(CONTRAST_PAIRS)
        name = pair.get("name", f"pair #{index}")
        theme = pair.get("theme")
        foreground = pair.get("foreground")
        background = pair.get("background")
        minimum = pair.get("min")
        if (
            not isinstance(name, str)
            or theme not in THEME_NAMES
            or not isinstance(foreground, str)
            or not isinstance(background, str)
            or not isinstance(minimum, (int, float))
        ):
            return list(CONTRAST_PAIRS)
        pairs.append((name, foreground, background, float(minimum)))
    return pairs


def load_palette(path: pathlib.Path | str | None = None) -> dict[str, Any]:
    """Load and normalise a palette, falling back per-token when necessary.

    A missing, unreadable, or malformed token file never disables the design
    system: every theme and token is filled from the built-in Padilha palette.
    """
    token_path = pathlib.Path(path) if path is not None else TOKENS_PATH
    source = "tokens"
    warnings: list[str] = []
    data: dict[str, Any] = {}

    try:
        loaded = json.loads(token_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
        else:
            warnings.append("token file root is not an object")
    except FileNotFoundError:
        warnings.append(f"token file not found: {token_path}")
        source = "builtin-fallback"
    except OSError as error:
        warnings.append(f"token file unreadable: {error}")
        source = "builtin-fallback"
    except json.JSONDecodeError as error:
        warnings.append(f"token file is invalid JSON: {error}")
        source = "builtin-fallback"

    raw_themes = data.get("themes") if isinstance(data.get("themes"), dict) else {}
    themes: dict[str, dict[str, str]] = {}
    for theme_name in THEME_NAMES:
        fallback = copy.deepcopy(FALLBACK_THEMES[theme_name])
        raw_theme = raw_themes.get(theme_name)
        if not isinstance(raw_theme, dict):
            if source == "tokens":
                warnings.append(f"theme {theme_name!r} is missing; using fallback")
                source = "partial-fallback"
            themes[theme_name] = fallback
            continue

        for token_name in REQUIRED_TOKENS:
            raw_value = raw_theme.get(token_name)
            if _is_hex(raw_value):
                fallback[token_name] = normalize_hex(raw_value)
            else:
                warnings.append(
                    f"theme {theme_name!r} token {token_name!r} is missing or invalid; "
                    "using fallback"
                )
                source = "partial-fallback"
        themes[theme_name] = fallback

    return {
        "themes": themes,
        "contrastPairs": _read_contrast_pairs(data),
        "source": source,
        "warnings": warnings,
    }


def validate_theme(
    theme: dict[str, str],
    pairs: list[tuple[str, str, str, float]] | tuple[tuple[str, str, str, float], ...]
    | None = None,
) -> list[str]:
    """Return human-readable contrast failures for a resolved theme."""
    errors: list[str] = []
    for token_name in REQUIRED_TOKENS:
        if not _is_hex(theme.get(token_name)):
            errors.append(f"token {token_name!r} is missing or invalid")
    if errors:
        return errors

    for name, foreground, background, minimum in pairs or CONTRAST_PAIRS:
        if foreground not in theme or background not in theme:
            errors.append(f"{name}: unknown token")
            continue
        ratio = contrast(theme[foreground], theme[background])
        if ratio + 1e-9 < minimum:
            errors.append(f"{name}: {ratio:.2f}:1 is below {minimum}:1")
    return errors


def resolve_theme(
    theme_name: str = "light",
    dynamic_accent: str | None = None,
    palette: dict[str, Any] | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Resolve one theme and report whether a dynamic accent was accepted.

    ``dynamic_accent`` is only used when it passes text contrast against the
    background, surface, and raised surface and an automatically selected
    ``onAccent`` passes contrast against it.  Otherwise the canonical Padilha
    accent is returned, with the reason recorded in ``meta``.
    """
    if theme_name not in THEME_NAMES:
        raise PaletteError(f"unknown theme {theme_name!r}")

    data = palette if palette is not None else load_palette()
    theme = copy.deepcopy(data["themes"][theme_name])
    meta: dict[str, Any] = {
        "theme": theme_name,
        "source": data.get("source", "tokens"),
        "dynamic": False,
        "fallback": data.get("source") != "tokens",
        "reason": None,
    }

    if dynamic_accent is None:
        return theme, meta

    if not _is_hex(dynamic_accent):
        meta["reason"] = "dynamic accent is not a #RRGGBB colour"
        return theme, meta

    candidate = copy.deepcopy(theme)
    candidate["accent"] = normalize_hex(dynamic_accent)
    candidate["onAccent"] = best_text_on(candidate["accent"])

    failures: list[str] = []
    for foreground, background, minimum in DYNAMIC_ACCENT_PAIRS:
        ratio = contrast(candidate[foreground], candidate[background])
        if ratio + 1e-9 < minimum:
            failures.append(
                f"{foreground} on {background} is {ratio:.2f}:1 (minimum {minimum}:1)"
            )

    if failures:
        meta["reason"] = "dynamic accent rejected: " + "; ".join(failures)
        return theme, meta

    meta["dynamic"] = True
    meta["reason"] = "dynamic accent accepted after contrast checks"
    return candidate, meta


def css_variables(theme: dict[str, str]) -> dict[str, str]:
    """Map theme tokens to CSS custom-property names."""

    def kebab(name: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()

    return {f"--color-{kebab(name)}": value for name, value in theme.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", choices=THEME_NAMES, default="light")
    parser.add_argument("--dynamic-accent", metavar="#RRGGBB")
    parser.add_argument("--tokens", type=pathlib.Path)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    palette = load_palette(args.tokens)
    theme, meta = resolve_theme(args.theme, args.dynamic_accent, palette)
    errors = validate_theme(theme, palette["contrastPairs"])

    if args.json:
        print(
            json.dumps(
                {"theme": theme, "meta": meta, "errors": errors},
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"theme: {args.theme} ({meta['source']})")
        for name, value in theme.items():
            print(f"  {name}: {value}")
        if meta["reason"]:
            print(f"dynamic: {meta['reason']}")
        for error in errors:
            print(f"FAIL {error}")
        if not errors:
            print(f"ok {len(palette['contrastPairs'])} contrast pairs")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
