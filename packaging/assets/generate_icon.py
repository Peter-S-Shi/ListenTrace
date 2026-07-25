"""Generates a simple placeholder application icon for the Phase A packaging
spike (see ROADMAP.md's "Post-M10 -- Release Engineering and v1.0 Delivery").

This is deliberately a generic, no-design-effort placeholder -- a rounded
square with a five-bar waveform glyph -- so the packaging pipeline (PyInstaller
spec, Windows version resource, Inno Setup installer) can be built and
validated end-to-end before a real icon is designed. Swapping in a real icon
later requires no pipeline changes: regenerate or replace
`listentrace.ico` in this directory and rebuild.

Run with the project's `packaging` extra installed:
    python packaging/assets/generate_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

_BACKGROUND = (0x1F, 0x6F, 0x78, 255)  # a calm teal, arbitrary placeholder color
_BAR_COLOR = (0xFF, 0xFF, 0xFF, 255)
_BASE_SIZE = 256
_ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def _draw_waveform(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    corner_radius = round(size * 0.22)
    draw.rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=corner_radius, fill=_BACKGROUND)

    # Five vertical bars of alternating height, evenly spaced -- a generic
    # "audio waveform" glyph, not a specific brand mark.
    bar_heights = [0.35, 0.6, 0.85, 0.6, 0.35]
    bar_count = len(bar_heights)
    margin = size * 0.18
    usable_width = size - 2 * margin
    gap = usable_width * 0.12
    bar_width = (usable_width - gap * (bar_count - 1)) / bar_count
    center_y = size / 2

    for i, height_fraction in enumerate(bar_heights):
        bar_height = size * 0.5 * height_fraction
        x0 = margin + i * (bar_width + gap)
        x1 = x0 + bar_width
        y0 = center_y - bar_height / 2
        y1 = center_y + bar_height / 2
        radius = bar_width / 2
        draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=radius, fill=_BAR_COLOR)

    return image


def main() -> None:
    base = _draw_waveform(_BASE_SIZE)
    output_path = Path(__file__).parent / "listentrace.ico"
    base.save(output_path, format="ICO", sizes=[(s, s) for s in _ICO_SIZES])
    print(f"Wrote {output_path} ({', '.join(str(s) for s in _ICO_SIZES)} px)")


if __name__ == "__main__":
    main()
