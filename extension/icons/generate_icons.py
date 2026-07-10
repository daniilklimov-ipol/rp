#!/usr/bin/env python3
"""Regenerate the extension's toolbar icons (16/48/128px PNG).

Draws a red-to-green gradient ring (same hue math as content.js's
colorForPercent) around a play triangle, so the icon echoes what the
extension actually paints on thumbnails. Run with:

    python3 generate_icons.py

Requires Pillow (`pip install Pillow`); not a runtime dependency of the
extension itself, just a dev tool for regenerating the PNGs.
"""

from __future__ import annotations

import colorsys
import math
from pathlib import Path

from PIL import Image, ImageDraw

SIZES = (16, 48, 128)
OUT_DIR = Path(__file__).parent


def hue_color(fraction: float) -> tuple[int, int, int]:
    """fraction in [0,1] -> RGB, red (0) to green (1), matching content.js."""
    hue_deg = fraction * 120.0
    r, g, b = colorsys.hls_to_rgb(hue_deg / 360.0, 0.45, 0.72)
    return int(r * 255), int(g * 255), int(b * 255)


def render(size: int) -> Image.Image:
    scale = 4  # supersample for smoother edges, then downsize
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    ring_width = max(2, s // 8)
    margin = ring_width // 2 + scale
    bbox = (margin, margin, s - margin, s - margin)

    steps = 360
    for i in range(steps):
        start = i * 360 / steps - 90
        end = start + 360 / steps + 1
        color = hue_color(i / steps)
        draw.arc(bbox, start=start, end=end, fill=color, width=ring_width)

    # Dark center disc.
    inset = margin + ring_width
    draw.ellipse((inset, inset, s - inset, s - inset), fill=(24, 24, 27, 255))

    # White play triangle, centered.
    cx, cy = s / 2, s / 2
    tri_r = (s - 2 * inset) * 0.28
    points = [
        (cx - tri_r * 0.6, cy - tri_r),
        (cx - tri_r * 0.6, cy + tri_r),
        (cx + tri_r * 1.1, cy),
    ]
    draw.polygon(points, fill=(255, 255, 255, 255))

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    for size in SIZES:
        out_path = OUT_DIR / f"icon{size}.png"
        render(size).save(out_path)
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
