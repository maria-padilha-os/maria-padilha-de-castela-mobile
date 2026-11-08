#!/usr/bin/env python3
"""Convert the small Padilha SVG icon set to Android vector drawables.

Only the SVG subset used by ``assets/icons`` is supported: ``path``, ``circle``,
``rect``, and ``line``.  The conversion is deterministic so tests can compare a
freshly generated vector with the committed one.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVG_NS = "http://www.w3.org/2000/svg"
ANDROID_NS = "http://schemas.android.com/apk/res/android"
ICON_COLOR = "@color/padilha_icon"
TRANSPARENT = "@android:color/transparent"


def _attr(element: ET.Element, name: str, default: str | None = None) -> str | None:
    return element.get(name, default)


def _circle_path(cx: float, cy: float, radius: float) -> str:
    return (
        f"M{cx - radius:g},{cy:g} "
        f"a{radius:g},{radius:g} 0 1,0 {2 * radius:g},0 "
        f"a{radius:g},{radius:g} 0 1,0 {-2 * radius:g},0 Z"
    )


def _rect_path(x: float, y: float, width: float, height: float, rx: float, ry: float) -> str:
    if rx <= 0 or ry <= 0:
        return f"M{x:g},{y:g} h{width:g} v{height:g} h{-width:g} Z"
    return (
        f"M{x + rx:g},{y:g} "
        f"h{width - 2 * rx:g} "
        f"a{rx:g},{ry:g} 0 0,1 {rx:g},{ry:g} "
        f"v{height - 2 * ry:g} "
        f"a{rx:g},{ry:g} 0 0,1 {-rx:g},{ry:g} "
        f"h{-(width - 2 * rx):g} "
        f"a{rx:g},{ry:g} 0 0,1 {-rx:g},{-ry:g} "
        f"v{-(height - 2 * ry):g} "
        f"a{rx:g},{ry:g} 0 0,1 {rx:g},{-ry:g} Z"
    )


def _paint(value: str | None, default: str) -> str:
    if value is None:
        return default
    if value == "currentColor":
        return ICON_COLOR
    if value == "none":
        return TRANSPARENT
    if value.startswith("#"):
        return value.upper()
    return value


def _path(
    path_data: str,
    fill: str,
    stroke: str,
    stroke_width: str,
    *,
    stroke_linecap: str = "round",
    stroke_linejoin: str = "round",
) -> str:
    fill_attr = TRANSPARENT if fill == TRANSPARENT else fill
    stroke_attr = TRANSPARENT if stroke == TRANSPARENT else stroke
    return (
        "    <path\n"
        f'        android:fillColor="{fill_attr}"\n'
        f'        android:pathData="{path_data}"\n'
        f'        android:strokeColor="{stroke_attr}"\n'
        f'        android:strokeLineCap="{stroke_linecap}"\n'
        f'        android:strokeLineJoin="{stroke_linejoin}"\n'
        f'        android:strokeWidth="{stroke_width}" />'
    )


def convert(svg_path: pathlib.Path) -> str:
    root = ET.parse(svg_path).getroot()
    viewbox = root.get("viewBox", "0 0 24 24").split()
    width = viewbox[2]
    height = viewbox[3]
    parent_fill = _paint(root.get("fill"), TRANSPARENT)
    parent_stroke = _paint(root.get("stroke"), ICON_COLOR)
    parent_width = root.get("stroke-width", "2")
    parent_cap = root.get("stroke-linecap", "round")
    parent_join = root.get("stroke-linejoin", "round")

    paths: list[str] = []
    for element in root:
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"title", "desc", "defs"}:
            continue
        fill = _paint(element.get("fill"), parent_fill)
        stroke = _paint(element.get("stroke"), parent_stroke)
        stroke_width = element.get("stroke-width", parent_width)
        cap = element.get("stroke-linecap", parent_cap)
        join = element.get("stroke-linejoin", parent_join)

        if tag == "path":
            path_data = element.get("d")
            if path_data:
                paths.append(_path(path_data, fill, stroke, stroke_width, stroke_linecap=cap, stroke_linejoin=join))
        elif tag == "circle":
            cx = float(element.get("cx", "0"))
            cy = float(element.get("cy", "0"))
            radius = float(element.get("r", "0"))
            paths.append(
                _path(
                    _circle_path(cx, cy, radius),
                    fill,
                    stroke,
                    stroke_width,
                    stroke_linecap=cap,
                    stroke_linejoin=join,
                )
            )
        elif tag == "rect":
            x = float(element.get("x", "0"))
            y = float(element.get("y", "0"))
            rect_width = float(element.get("width", "0"))
            rect_height = float(element.get("height", "0"))
            rx = float(element.get("rx", element.get("ry", "0")))
            ry = float(element.get("ry", rx))
            paths.append(
                _path(
                    _rect_path(x, y, rect_width, rect_height, rx, ry),
                    fill,
                    stroke,
                    stroke_width,
                    stroke_linecap=cap,
                    stroke_linejoin=join,
                )
            )
        elif tag == "line":
            x1 = element.get("x1", "0")
            y1 = element.get("y1", "0")
            x2 = element.get("x2", "0")
            y2 = element.get("y2", "0")
            paths.append(
                _path(
                    f"M{x1},{y1} L{x2},{y2}",
                    fill,
                    stroke,
                    stroke_width,
                    stroke_linecap=cap,
                    stroke_linejoin=join,
                )
            )

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f"<!-- Generated from assets/icons/{svg_path.name} by tools/svg_to_android_vector.py. -->\n"
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        f'    android:width="{width}dp"\n'
        f'    android:height="{height}dp"\n'
        f'    android:viewportWidth="{width}"\n'
        f'    android:viewportHeight="{height}">\n'
        + "\n".join(paths)
        + "\n</vector>\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=ROOT / "assets" / "android-res" / "drawable",
    )
    parser.add_argument("--check", action="store_true", help="fail if output is stale")
    args = parser.parse_args(argv)

    stale = False
    for svg_path in sorted((ROOT / "assets" / "icons").glob("*.svg")):
        expected = convert(svg_path)
        target = args.output / f"{svg_path.stem}.xml"
        if args.check:
            actual = target.read_text(encoding="utf-8") if target.is_file() else ""
            if actual != expected:
                print(f"FAIL stale Android vector: {target.relative_to(ROOT)}")
                stale = True
            else:
                print(f"ok {target.relative_to(ROOT)}")
        else:
            target.write_text(expected, encoding="utf-8")
            print(f"wrote {target.relative_to(ROOT)}")

    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
