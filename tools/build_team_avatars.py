# coding=utf-8
"""Render the UI's curated 64x64 SVG marks as BotHider-safe PNG avatars.

This is a release-asset builder, not a runtime dependency.  The shipped app
only reads the resulting small PNG files, so end users do not need Pillow.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cs2career" / "web" / "static" / "crests"
TARGET = ROOT / "cs2career" / "web" / "static" / "team_avatars"
MAX_BYTES = 16 * 1024


def font(size: int):
    candidates = (
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    )
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default(size=size)


def render(path: Path, target: Path) -> None:
    root = ET.parse(path).getroot()
    rect = next(node for node in root if node.tag.endswith("rect"))
    text = next(node for node in root if node.tag.endswith("text"))
    size = int(float(text.attrib.get("font-size", "18")))
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 63, 63), radius=12, fill=rect.attrib["fill"])
    draw.text(
        (32, 31),
        "".join(text.itertext()).strip(),
        font=font(size),
        fill=text.attrib["fill"],
        anchor="mm",
        stroke_width=0,
    )
    image.save(target, "PNG", optimize=True, compress_level=9)


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for source in sorted(SOURCE.glob("*.svg")):
        render(source, TARGET / f"{source.stem}.png")

    default = Image.new("RGBA", (64, 64), "#535b66")
    draw = ImageDraw.Draw(default)
    draw.rounded_rectangle((0, 0, 63, 63), radius=12, fill="#535b66")
    draw.text((32, 31), "BOT", font=font(16), fill="#ffffff", anchor="mm")
    default.save(TARGET / "default.png", "PNG", optimize=True, compress_level=9)

    files = sorted(TARGET.glob("*.png"))
    oversized = [f.name for f in files if f.stat().st_size > MAX_BYTES]
    if len(files) != len(list(SOURCE.glob("*.svg"))) + 1 or oversized:
        raise SystemExit(f"avatar build failed: count={len(files)} oversized={oversized}")
    print(f"built {len(files)} safe avatars; largest={max(f.stat().st_size for f in files)} bytes")


if __name__ == "__main__":
    main()
