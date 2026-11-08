"""Asset-path, dimension, resource, and overlay-boundary checks."""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from design.padilha_palette import load_palette  # noqa: E402
from tests.support import png_size, read_json, read_text, webp_size, xml_root  # noqa: E402
from tools.export_preview_tokens import render as render_preview_data  # noqa: E402
from tools.make_boot_keyframes import keyframe as boot_keyframe  # noqa: E402
from tools.svg_to_android_vector import convert as convert_icon  # noqa: E402

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
WALLPAPER_CASES = (
    ("padilha-dark-1440x3120.webp", 1440, 3120),
    ("padilha-light-1440x3120.webp", 1440, 3120),
    ("padilha-dark-1080x2424.webp", 1080, 2424),
    ("padilha-light-1080x2424.webp", 1080, 2424),
    ("padilha-dark-2560x1600.webp", 2560, 1600),
    ("padilha-light-2560x1600.webp", 2560, 1600),
    ("padilha-dark-1600x2560.webp", 1600, 2560),
    ("padilha-light-1600x2560.webp", 1600, 2560),
)
FORBIDDEN_MARKS = ("grapheneos", "android", "google", "pixel")
COLOUR_TO_TOKEN = {
    "padilha_background": "background",
    "padilha_surface": "surface",
    "padilha_surface_raised": "surfaceRaised",
    "padilha_scrim": "scrim",
    "padilha_text_primary": "textPrimary",
    "padilha_text_secondary": "textSecondary",
    "padilha_on_scrim": "onScrim",
    "padilha_accent": "accent",
    "padilha_accent_strong": "accentStrong",
    "padilha_on_accent": "onAccent",
    "padilha_on_accent_strong": "onAccentStrong",
    "padilha_border": "border",
    "padilha_success": "success",
    "padilha_warning": "warning",
    "padilha_danger": "danger",
}


def text_values(root: ET.Element) -> str:
    values = ["".join(root.itertext())]
    for element in root.iter():
        values.extend(str(value) for value in element.attrib.values())
    return " ".join(values).lower()


class WallpaperAssets(unittest.TestCase):
    def test_delivery_webp_paths_and_dimensions(self) -> None:
        for name, width, height in WALLPAPER_CASES:
            with self.subTest(name=name):
                path = ROOT / "assets" / "wallpapers" / name
                self.assertTrue(path.is_file(), path)
                self.assertEqual(webp_size(path), (width, height))

    def test_png_masters_exist_at_required_size(self) -> None:
        for theme in ("dark", "light"):
            path = (
                ROOT
                / "assets"
                / "wallpapers"
                / "masters"
                / f"padilha-{theme}-1440x3120.png"
            )
            self.assertTrue(path.is_file(), path)
            self.assertEqual(png_size(path), (1440, 3120))

    def test_delivery_webp_stays_under_runtime_budget(self) -> None:
        for name, _width, _height in WALLPAPER_CASES:
            path = ROOT / "assets" / "wallpapers" / name
            self.assertLessEqual(path.stat().st_size, 2_500_000, name)

    def test_wallpaper_sources_have_no_text_or_foreign_marks(self) -> None:
        for theme in ("dark", "light"):
            path = ROOT / "assets" / "wallpapers" / "source" / f"padilha-{theme}.svg"
            self.assertTrue(path.is_file(), path)
            root = xml_root(path)
            self.assertEqual(root.get("width"), "1440")
            self.assertEqual(root.get("height"), "3120")
            self.assertNotIn("<image", read_text(path))
            haystack = text_values(root)
            for mark in FORBIDDEN_MARKS:
                self.assertNotIn(mark, haystack, f"{path.name} contains {mark}")


class FontAssets(unittest.TestCase):
    def test_woff2_and_ttf_font_magics(self) -> None:
        woff2 = (
            "Inter-Regular.woff2",
            "Inter-Medium.woff2",
            "Inter-SemiBold.woff2",
            "Fraunces-Variable.woff2",
        )
        for name in woff2:
            path = ROOT / "assets" / "fonts" / name
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_bytes()[:4], b"wOF2", name)

        for name in ("inter_variable.ttf", "fraunces_variable.ttf"):
            path = ROOT / "assets" / "android-res" / "font" / name
            self.assertTrue(path.is_file(), path)
            magic = path.read_bytes()[:4]
            self.assertIn(magic, (b"\x00\x01\x00\x00", b"OTTO", b"true"), name)

    def test_ofl_licences_and_font_families(self) -> None:
        for name in ("OFL-Inter.txt", "OFL-Fraunces.txt"):
            path = ROOT / "assets" / "fonts" / name
            self.assertIn("SIL OPEN FONT LICENSE", read_text(path).upper())

        for name in ("padilha_display.xml", "padilha_ui.xml"):
            path = ROOT / "android" / "design" / "src" / "main" / "res" / "font" / name
            self.assertTrue(path.is_file(), path)
            root = xml_root(path)
            self.assertEqual(root.tag, "font-family")
            self.assertTrue(root.findall("font"))


class IconAssets(unittest.TestCase):
    def test_icons_are_24dp_2dp_round_linework(self) -> None:
        icons = sorted((ROOT / "assets" / "icons").glob("*.svg"))
        self.assertGreaterEqual(len(icons), 15)
        for path in icons:
            with self.subTest(icon=path.name):
                text = read_text(path)
                root = xml_root(path)
                self.assertEqual(root.get("width"), "24", path.name)
                self.assertEqual(root.get("height"), "24", path.name)
                self.assertEqual(root.get("viewBox"), "0 0 24 24", path.name)
                self.assertEqual(root.get("stroke-width"), "2", path.name)
                self.assertEqual(root.get("stroke-linecap"), "round", path.name)
                self.assertEqual(root.get("stroke-linejoin"), "round", path.name)
                self.assertEqual(root.get("fill"), "none", path.name)
                self.assertNotIn("<image", text)
                self.assertNotIn("<text", text)
                haystack = text_values(root)
                for mark in FORBIDDEN_MARKS:
                    self.assertNotIn(mark, haystack, f"{path.name} contains {mark}")

    def test_android_vectors_are_generated_and_current(self) -> None:
        for svg_path in sorted((ROOT / "assets" / "icons").glob("*.svg")):
            target = (
                ROOT
                / "assets"
                / "android-res"
                / "drawable"
                / f"{svg_path.stem}.xml"
            )
            self.assertTrue(target.is_file(), target)
            self.assertEqual(read_text(target), convert_icon(svg_path), svg_path.name)

    def test_adaptive_launcher_icon_and_monochrome_layer(self) -> None:
        for version in ("mipmap-anydpi-v26", "mipmap-anydpi-v33"):
            path = ROOT / "assets" / "android-res" / version / "ic_launcher.xml"
            self.assertTrue(path.is_file(), path)
            root = xml_root(path)
            self.assertEqual(root.tag, "adaptive-icon")
            self.assertIsNotNone(root.find("background"))
            self.assertIsNotNone(root.find("foreground"))
            monochrome = root.find("monochrome")
            if version.endswith("v33"):
                self.assertIsNotNone(monochrome)
            else:
                self.assertIsNone(monochrome)

        foreground = (
            ROOT / "assets" / "android-res" / "drawable" / "ic_launcher_foreground.xml"
        )
        root = xml_root(foreground)
        self.assertEqual(root.get(ANDROID_NS + "viewportWidth"), "108")
        self.assertEqual(root.get(ANDROID_NS + "viewportHeight"), "108")

    def test_preview_token_data_is_generated_and_current(self) -> None:
        path = ROOT / "preview" / "palette-data.js"
        self.assertTrue(path.is_file(), path)
        self.assertEqual(read_text(path), render_preview_data())


class AndroidResources(unittest.TestCase):
    def test_light_and_night_colours_match_tokens(self) -> None:
        themes = load_palette()["themes"]
        for theme, directory in (
            ("light", "values"),
            ("dark", "values-night"),
        ):
            path = (
                ROOT
                / "android"
                / "design"
                / "src"
                / "main"
                / "res"
                / directory
                / "colors.xml"
            )
            root = xml_root(path)
            colours = {
                element.get("name"): element.text.strip()
                for element in root.findall("color")
                if element.get("name") in COLOUR_TO_TOKEN
            }
            self.assertEqual(set(colours), set(COLOUR_TO_TOKEN))
            for resource_name, token in COLOUR_TO_TOKEN.items():
                self.assertEqual(
                    colours[resource_name].upper(),
                    themes[theme][token].upper(),
                    f"{theme} {resource_name}",
                )

    def test_overlay_colours_match_light_and_night_tokens(self) -> None:
        themes = load_palette()["themes"]
        for theme, directory in (("light", "values"), ("dark", "values-night")):
            path = (
                ROOT
                / "android"
                / "overlays"
                / "padilha-palette"
                / "res"
                / directory
                / "colors.xml"
            )
            root = xml_root(path)
            colours = {
                element.get("name"): element.text.strip()
                for element in root.findall("color")
            }
            self.assertEqual(set(colours), set(COLOUR_TO_TOKEN))
            for resource_name, token in COLOUR_TO_TOKEN.items():
                self.assertEqual(
                    colours[resource_name].upper(),
                    themes[theme][token].upper(),
                    f"overlay {theme} {resource_name}",
                )

    def test_theme_attributes_reference_colour_resources(self) -> None:
        for directory in ("values", "values-night"):
            path = (
                ROOT
                / "android"
                / "design"
                / "src"
                / "main"
                / "res"
                / directory
                / "themes.xml"
            )
            root = xml_root(path)
            style = root.find("style")
            self.assertIsNotNone(style)
            items = {item.get("name"): (item.text or "").strip() for item in style}
            for name in ("android:textColorPrimary", "android:textColorSecondary"):
                self.assertTrue(items[name].startswith("@color/padilha_"), name)
            self.assertEqual(items["padilhaBackground"], "@color/padilha_background")
            self.assertEqual(items["padilhaAccent"], "@color/padilha_accent")

    def test_overlayable_declares_only_palette_colours(self) -> None:
        path = (
            ROOT
            / "android"
            / "design"
            / "src"
            / "main"
            / "res"
            / "values"
            / "overlayable.xml"
        )
        root = xml_root(path)
        self.assertEqual(root.tag, "overlayable")
        items = root.findall("item")
        self.assertTrue(items)
        self.assertEqual({item.get("type") for item in items}, {"color"})
        names = {item.get("name") for item in items}
        self.assertEqual(names, set(COLOUR_TO_TOKEN))


class OverlaySafety(unittest.TestCase):
    def test_manifest_targets_only_a_castela_package(self) -> None:
        path = (
            ROOT
            / "android"
            / "overlays"
            / "padilha-palette"
            / "AndroidManifest.xml"
        )
        root = xml_root(path)
        overlay = root.find("overlay")
        self.assertIsNotNone(overlay)
        target = overlay.get(ANDROID_NS + "targetPackage")
        self.assertTrue(target.startswith("com.castela."), target)
        self.assertNotIn(
            target,
            {
                "android",
                "com.android.systemui",
                "com.android.settings",
                "com.android.packageinstaller",
            },
        )
        self.assertEqual(overlay.get(ANDROID_NS + "isStatic"), "false")

        application = root.find("application")
        self.assertIsNotNone(application)
        self.assertEqual(application.get(ANDROID_NS + "hasCode"), "false")
        self.assertIsNone(root.find("uses-permission"))
        self.assertIsNone(root.get(ANDROID_NS + "sharedUserId"))
        self.assertNotEqual(application.get(ANDROID_NS + "debuggable"), "true")

    def test_android_sources_have_no_privileged_or_security_components(self) -> None:
        for path in (ROOT / "android").rglob("*.xml"):
            text = read_text(path)
            self.assertNotIn("sharedUserId", text, path)
            self.assertNotIn("android:debuggable=\"true\"", text, path)
            self.assertNotIn("uses-permission", text, path)
            self.assertNotIn("android:exported=\"true\"", text, path)

    def test_no_tracked_build_or_signing_artifact(self) -> None:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        forbidden = re.compile(
            r"(^|/)(out|releases|artifacts|keys|signing|secrets|proprietary|vendor)/"
            r"|\.(img|iso|apk|aab|apks|keystore|jks|p12|pfx|pem|pk8|ota|bin|zip)$"
        )
        matches = [name for name in result.stdout.splitlines() if forbidden.search(name)]
        self.assertEqual(matches, [])

    def test_tooling_has_no_privileged_commands(self) -> None:
        pattern = re.compile(
            r"\b(sudo|pkexec|systemctl|pacman|mount|remount|setenforce|fastboot)\b"
            r"|\badb\s+root\b|\bpm\s+grant\b|\bsu\s+-c\b"
        )
        for path in [*(ROOT / "tools").glob("*.py"), *(ROOT / "preview").glob("*.py")]:
            self.assertIsNone(pattern.search(read_text(path)), path)


class BootAnimationSource(unittest.TestCase):
    def test_desc_and_keyframes_are_system_build_only(self) -> None:
        desc = read_text(ROOT / "android" / "system" / "bootanimation" / "desc.txt")
        self.assertEqual(desc.splitlines()[:2], ["1440 3120 30", "p 0 0 part0"])

        for index in range(4):
            path = (
                ROOT
                / "assets"
                / "bootanimation"
                / "source"
                / f"padilha-boot-{index:03d}.svg"
            )
            self.assertTrue(path.is_file(), path)
            self.assertEqual(read_text(path), boot_keyframe(index))

        readme = read_text(
            ROOT / "android" / "system" / "bootanimation" / "README.md"
        ).lower()
        for term in ("system-build only", "do **not**", "verified boot", "not installable"):
            self.assertIn(term, readme)

    def test_no_bootanimation_zip_is_committed(self) -> None:
        self.assertEqual(list(ROOT.rglob("bootanimation.zip")), [])


if __name__ == "__main__":
    unittest.main()
