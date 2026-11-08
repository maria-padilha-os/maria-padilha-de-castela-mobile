#!/usr/bin/env python3
"""Generate the Padilha boot-animation source keyframes.

The generated files are design sources for a future system-image build. They are
not a flashable ``bootanimation.zip`` and are never installed by the stock-device
preview. The release pipeline expands these keyframes to a 30 fps sequence.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "bootanimation" / "source"
KEYFRAMES = 4


def keyframe(index: int) -> str:
    progress = (index + 1) / KEYFRAMES
    radius = 120 + 220 * progress
    ring_opacity = 0.10 + 0.42 * progress
    dot_opacity = 0.20 + 0.65 * progress
    label = f"{index:03d}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="3120" viewBox="0 0 1440 3120" role="img" aria-label="Padilha boot-animation source keyframe {label}">
  <title>Padilha boot source {label}</title>
  <desc>System-build source only. No text, logos, flashing, or audio.</desc>
  <defs>
    <linearGradient id="night" x1="0" y1="0" x2="0.8" y2="1">
      <stop offset="0" stop-color="#0B0710"/>
      <stop offset="0.55" stop-color="#1A1020"/>
      <stop offset="1" stop-color="#120C17"/>
    </linearGradient>
    <radialGradient id="candle" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#E6B85C" stop-opacity="{dot_opacity:.3f}"/>
      <stop offset="0.55" stop-color="#E58AA0" stop-opacity="{dot_opacity * 0.35:.3f}"/>
      <stop offset="1" stop-color="#120C17" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1440" height="3120" fill="url(#night)"/>
  <circle cx="720" cy="1560" r="520" fill="url(#candle)"/>
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="720" cy="1560" r="{radius:.1f}" stroke="#E6B85C" stroke-opacity="{ring_opacity:.3f}" stroke-width="3"/>
    <circle cx="720" cy="1560" r="{radius * 0.72:.1f}" stroke="#E58AA0" stroke-opacity="{ring_opacity * 0.8:.3f}" stroke-width="2" stroke-dasharray="2 14"/>
    <circle cx="720" cy="1560" r="{radius * 0.46:.1f}" stroke="#E6B85C" stroke-opacity="{ring_opacity * 1.1:.3f}" stroke-width="2"/>
    <path d="M720,{1560 - radius * 0.72:.1f} C{720 + radius * 0.22:.1f},1500 {720 + radius * 0.22:.1f},1620 720,{1560 + radius * 0.72:.1f} C{720 - radius * 0.22:.1f},1620 {720 - radius * 0.22:.1f},1500 720,{1560 - radius * 0.72:.1f} Z"
      stroke="#E6B85C" stroke-opacity="{ring_opacity * 0.9:.3f}" stroke-width="2.5"/>
    <path d="M720,{1560 - radius * 0.72:.1f} C{720 + radius * 0.22:.1f},1500 {720 + radius * 0.22:.1f},1620 720,{1560 + radius * 0.72:.1f} C{720 - radius * 0.22:.1f},1620 {720 - radius * 0.22:.1f},1500 720,{1560 - radius * 0.72:.1f} Z"
      stroke="#E6B85C" stroke-opacity="{ring_opacity * 0.9:.3f}" stroke-width="2.5" transform="rotate(90 720 1560)"/>
    <circle cx="720" cy="1560" r="{8 + 10 * progress:.1f}" fill="#E6B85C" fill-opacity="{dot_opacity:.3f}" stroke="none"/>
  </g>
</svg>
'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    stale = False
    if not args.check:
        args.output.mkdir(parents=True, exist_ok=True)
    for index in range(KEYFRAMES):
        target = args.output / f"padilha-boot-{index:03d}.svg"
        expected = keyframe(index)
        if args.check:
            actual = target.read_text(encoding="utf-8") if target.is_file() else ""
            if actual != expected:
                print(f"FAIL stale boot keyframe: {target.relative_to(ROOT)}")
                stale = True
            else:
                print(f"ok {target.relative_to(ROOT)}")
        else:
            target.write_text(expected, encoding="utf-8")
            print(f"wrote {target.relative_to(ROOT)}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
