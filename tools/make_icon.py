"""Draw packaging/rpggen.ico (a tile-and-sword mark) deterministically with Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "packaging" / "rpggen.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw(size: int) -> Image.Image:
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 248, 248), radius=40, fill=(32, 41, 64, 255))
    cell = 56
    for gx in range(3):
        for gy in range(3):
            shade = 70 + ((gx + gy) % 2) * 25
            x, y = 36 + gx * (cell + 8), 36 + gy * (cell + 8)
            d.rectangle((x, y, x + cell, y + cell), fill=(40, shade + 60, shade, 255))
    d.polygon([(150, 60), (176, 60), (176, 150), (163, 172), (150, 150)], fill=(230, 232, 240, 255))
    d.rectangle((136, 150, 190, 162), fill=(214, 168, 70, 255))
    d.rectangle((158, 162, 168, 204), fill=(140, 90, 50, 255))
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base = draw(256)
    base.save(OUT, format="ICO", sizes=[(n, n) for n in SIZES])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
