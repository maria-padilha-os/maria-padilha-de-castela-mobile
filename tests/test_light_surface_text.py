"""Guard against hardcoded light text on light surfaces."""

from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from design.padilha_palette import (  # noqa: E402
    FALLBACK_THEMES,
    contrast,
    luminance,
    resolve_theme,
    validate_theme,
)
from tests.support import read_text, xml_root  # noqa: E402

HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")
TEXT_COLOUR_RE = re.compile(r"(?m)^\s*color\s*:\s*([^;]+);")
CUSTOM_PROP_RE = re.compile(r"(--color-[a-z-]+)\s*:\s*(#[0-9A-Fa-f]{6})")


class PreviewCssTextColours(unittest.TestCase):
    def setUp(self) -> None:
        self.css = read_text(ROOT / "preview" / "styles.css")

    def test_every_text_colour_is_a_token(self) -> None:
        declarations = TEXT_COLOUR_RE.findall(self.css)
        self.assertTrue(declarations)
        for value in declarations:
            with self.subTest(value=value):
                self.assertTrue(
                    value.strip().startswith("var(--color-")
                    or value.strip() in {"currentColor", "inherit", "transparent"},
                    f"literal text colour would not follow the theme: {value}",
                )

    def test_light_theme_text_variables_are_dark(self) -> None:
        values = re.findall(r"--color-text-primary\s*:\s*(#[0-9A-Fa-f]{6})", self.css)
        backgrounds = re.findall(
            r"--color-background\s*:\s*(#[0-9A-Fa-f]{6})", self.css
        )
        self.assertGreaterEqual(len(values), 2)
        self.assertGreaterEqual(len(backgrounds), 2)

        # The first occurrence is the dark default, the second is the light
        # prefers-color-scheme block.
        light_text, light_background = values[1], backgrounds[1]
        self.assertLess(luminance(light_text), luminance(light_background))
        self.assertGreaterEqual(contrast(light_text, light_background), 4.5)
        self.assertLess(luminance(light_text), 0.2, "light theme text must be dark")

    def test_no_inline_literal_colour_in_markup(self) -> None:
        html = read_text(ROOT / "preview" / "index.html")
        self.assertNotIn("<font", html.lower())
        for style in re.findall(r'style\s*=\s*"([^"]*)"', html):
            self.assertNotIn("color", style.lower(), style)
            self.assertIsNone(HEX_RE.search(style), style)

    def test_app_script_never_sets_a_literal_text_colour(self) -> None:
        script = read_text(ROOT / "preview" / "app.js")
        self.assertNotRegex(script, r"\.style\.color\b")
        self.assertNotRegex(script, r"setProperty\(\s*[\"']color[\"']")
        self.assertNotRegex(script, r"style\s*=\s*[\"'][^\"']*color")

    def test_launcher_labels_use_a_scrim_not_the_wallpaper(self) -> None:
        css = read_text(ROOT / "preview" / "styles.css")
        match = re.search(r"\.app-label\s*\{(.*?)\}", css, re.DOTALL)
        self.assertIsNotNone(match)
        block = match.group(1)
        self.assertIn("background: var(--color-scrim)", block)
        self.assertIn("color: var(--color-on-scrim)", block)

    def test_android_text_colours_are_resource_references(self) -> None:
        for path in (ROOT / "android").rglob("*.xml"):
            text = read_text(path)
            for value in re.findall(r'android:textColor="([^"]+)"', text):
                with self.subTest(path=path, value=value):
                    self.assertTrue(
                        value.startswith("@color/")
                        or value.startswith("?attr/")
                        or value.startswith("?padilha"),
                        value,
                    )


class ThemeContrast(unittest.TestCase):
    def test_both_themes_pass_every_contrast_pair(self) -> None:
        for theme_name in ("light", "dark"):
            theme, meta = resolve_theme(theme_name)
            self.assertFalse(meta["fallback"])
            self.assertEqual(validate_theme(theme), [], theme_name)

    def test_light_surfaces_only_have_dark_body_and_secondary_text(self) -> None:
        theme = FALLBACK_THEMES["light"]
        for foreground in ("textPrimary", "textSecondary"):
            for background in ("background", "surface", "surfaceRaised"):
                with self.subTest(foreground=foreground, background=background):
                    self.assertLess(
                        luminance(theme[foreground]),
                        luminance(theme[background]),
                    )
                    self.assertLess(luminance(theme[foreground]), 0.2)
                    self.assertGreaterEqual(
                        contrast(theme[foreground], theme[background]),
                        4.5,
                    )

    def test_accent_text_pairs_are_readable_in_both_themes(self) -> None:
        for theme_name in ("light", "dark"):
            theme = FALLBACK_THEMES[theme_name]
            with self.subTest(theme=theme_name, pair="onAccent"):
                self.assertGreaterEqual(
                    contrast(theme["onAccent"], theme["accent"]),
                    4.5,
                )
            with self.subTest(theme=theme_name, pair="onAccentStrong"):
                self.assertGreaterEqual(
                    contrast(theme["onAccentStrong"], theme["accentStrong"]),
                    4.5,
                )

    def test_preview_light_variables_match_tokens(self) -> None:
        css = read_text(ROOT / "preview" / "styles.css")
        custom = CUSTOM_PROP_RE.findall(css)
        # Later declarations in the light media query override the dark default.
        resolved: dict[str, str] = {}
        for name, value in custom:
            resolved[name] = value.upper()
        expected = {
            "--color-background": FALLBACK_THEMES["light"]["background"],
            "--color-surface": FALLBACK_THEMES["light"]["surface"],
            "--color-surface-raised": FALLBACK_THEMES["light"]["surfaceRaised"],
            "--color-scrim": FALLBACK_THEMES["light"]["scrim"],
            "--color-text-primary": FALLBACK_THEMES["light"]["textPrimary"],
            "--color-text-secondary": FALLBACK_THEMES["light"]["textSecondary"],
            "--color-on-scrim": FALLBACK_THEMES["light"]["onScrim"],
        }
        for name, value in expected.items():
            self.assertEqual(resolved[name], value, name)


if __name__ == "__main__":
    unittest.main()
