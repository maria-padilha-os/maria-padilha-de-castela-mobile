"""Palette resolution, dynamic-accent rejection, and missing-token fallback."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from design.padilha_palette import (  # noqa: E402
    FALLBACK_THEMES,
    THEME_NAMES,
    contrast,
    css_variables,
    load_palette,
    resolve_theme,
    validate_theme,
)
from tests.support import read_text  # noqa: E402
from tools.export_preview_tokens import render as render_preview_data  # noqa: E402


class MissingPaletteFallback(unittest.TestCase):
    def test_builtin_fallback_matches_tokens(self) -> None:
        themes = load_palette()["themes"]
        self.assertEqual(themes, FALLBACK_THEMES)

    def test_missing_file_uses_full_safe_fallback(self) -> None:
        palette = load_palette(pathlib.Path("/nonexistent/padilha/tokens.json"))
        self.assertEqual(palette["source"], "builtin-fallback")
        self.assertTrue(palette["warnings"])
        for theme_name in THEME_NAMES:
            self.assertEqual(validate_theme(palette["themes"][theme_name]), [])

    def test_invalid_json_uses_full_safe_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "tokens.json"
            path.write_text("{ this is not json", encoding="utf-8")
            palette = load_palette(path)
        self.assertEqual(palette["source"], "builtin-fallback")
        self.assertEqual(palette["themes"], FALLBACK_THEMES)

    def test_partial_or_invalid_token_uses_per_token_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "tokens.json"
            path.write_text(
                json.dumps(
                    {
                        "themes": {
                            "light": {
                                "background": "not-a-colour",
                                "surface": "#F3E8DA",
                            },
                            "dark": {},
                        },
                        "contrastPairs": [],
                    }
                ),
                encoding="utf-8",
            )
            palette = load_palette(path)

        self.assertEqual(palette["source"], "partial-fallback")
        self.assertEqual(
            palette["themes"]["light"]["background"],
            FALLBACK_THEMES["light"]["background"],
        )
        self.assertEqual(
            palette["themes"]["light"]["surface"],
            FALLBACK_THEMES["light"]["surface"],
        )
        self.assertEqual(palette["themes"]["dark"], FALLBACK_THEMES["dark"])
        for theme_name in THEME_NAMES:
            self.assertEqual(validate_theme(palette["themes"][theme_name]), [])

    def test_missing_theme_uses_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "tokens.json"
            path.write_text(
                json.dumps({"themes": {"dark": FALLBACK_THEMES["dark"]}}),
                encoding="utf-8",
            )
            palette = load_palette(path)
        self.assertEqual(palette["themes"]["light"], FALLBACK_THEMES["light"])
        self.assertEqual(palette["source"], "partial-fallback")


class DynamicAccent(unittest.TestCase):
    def test_canonical_accents_are_accepted(self) -> None:
        for theme_name in THEME_NAMES:
            canonical = FALLBACK_THEMES[theme_name]["accent"]
            theme, meta = resolve_theme(theme_name, canonical)
            self.assertTrue(meta["dynamic"], meta)
            self.assertEqual(theme["accent"], canonical)
            self.assertEqual(validate_theme(theme), [])

    def test_failing_accent_is_rejected_and_canonical_kept(self) -> None:
        for theme_name in THEME_NAMES:
            canonical = FALLBACK_THEMES[theme_name]["accent"]
            theme, meta = resolve_theme(theme_name, "#777777")
            self.assertFalse(meta["dynamic"], theme_name)
            self.assertIn("dynamic accent rejected", meta["reason"])
            self.assertEqual(theme["accent"], canonical)
            self.assertEqual(validate_theme(theme), [])

    def test_non_hex_accent_is_rejected(self) -> None:
        theme, meta = resolve_theme("light", "rose")
        self.assertFalse(meta["dynamic"])
        self.assertIn("not a #RRGGBB colour", meta["reason"])
        self.assertEqual(theme["accent"], FALLBACK_THEMES["light"]["accent"])

    def test_no_dynamic_accent_keeps_fixed_palette(self) -> None:
        theme, meta = resolve_theme("dark")
        self.assertFalse(meta["dynamic"])
        self.assertIsNone(meta["reason"])
        self.assertEqual(theme, FALLBACK_THEMES["dark"])

    def test_css_variable_names_are_kebab_case(self) -> None:
        variables = css_variables(FALLBACK_THEMES["light"])
        self.assertEqual(variables["--color-text-primary"], "#241A28")
        self.assertEqual(variables["--color-surface-raised"], "#FFFFFF")
        self.assertEqual(variables["--color-on-accent"], "#FFFFFF")


class PreviewData(unittest.TestCase):
    def test_preview_data_is_generated_from_tokens(self) -> None:
        self.assertEqual(
            read_text(ROOT / "preview" / "palette-data.js"),
            render_preview_data(),
        )

    def test_preview_js_has_missing_palette_fallback_path(self) -> None:
        palette_js = read_text(ROOT / "preview" / "palette.js")
        for term in ("fallbackThemes", "missing-palette", "themeWithFallback"):
            self.assertIn(term, palette_js)

    def test_preview_fallback_themes_pass_contrast(self) -> None:
        preview = json.loads(
            read_text(ROOT / "preview" / "palette-data.js")
            .split("window.PADILHA_DATA = ", 1)[1]
            .rstrip(";\n")
        )
        for theme_name in THEME_NAMES:
            theme = preview["fallbackThemes"][theme_name]
            for pair in preview["contrastPairs"]:
                ratio = contrast(theme[pair["foreground"]], theme[pair["background"]])
                self.assertGreaterEqual(
                    ratio + 1e-9,
                    pair["min"],
                    f"{theme_name}: {pair['name']}",
                )


if __name__ == "__main__":
    unittest.main()
