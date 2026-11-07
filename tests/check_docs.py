#!/usr/bin/env python3
"""Check the ADR deliverables, required disclaimers, and local Markdown links."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

REQUIRED_TERMS = {
    "README.md": [
        "not official GrapheneOS",
        "private",
        "Pixel 9a",
        "docs/adr/0001-",
    ],
    "docs/adr/0001-grapheneos-base-device-support-and-padilha-branding.md": [
        "**Status:** Accepted",
        "Option B",
        "Pixel 9a (`tegu`)",
        "April 2032",
        "MIT",
        "Apache-2.0",
        "GPL-2.0",
        "90746220",
        "WCAG 2.2",
        "boot animation",
        "VpnService",
        "No ROM build",
        "private",
    ],
    "docs/legal/grapheneos-aosp-attribution.md": [
        "90746220",
        "Apache-2.0",
        "GPL-2.0",
        "vendor",
        "unofficial build",
        "Android brand",
        "GrapheneOS name and logo are trademarks",
    ],
    "docs/branding/padilha-look-and-feel.md": [
        "boot animation",
        "Fraunces",
        "Inter",
        "4.5:1",
        "3:1",
        "tokens.json",
        "Wallpaper",
        "WCAG 2.2",
    ],
}

LINK_RE = re.compile(r"\]\(([^)#]+)(?:#[^)]*)?\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#", "<")


def relative(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    errors: list[str] = []

    for name, terms in REQUIRED_TERMS.items():
        path = ROOT / name
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty required document: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        for term in terms:
            if term not in text:
                errors.append(f"{name}: missing required text {term!r}")

    markdown_files = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    for path in markdown_files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        # Ignore fenced code and inline code when looking for links.
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"`[^`]*`", "", text)
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith(SKIP_PREFIXES):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"{relative(path)}: broken local link {target!r}")

    if errors:
        print("Documentation checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"ok {len(REQUIRED_TERMS)} required documents, "
        f"{len(markdown_files)} Markdown files, and local links"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
