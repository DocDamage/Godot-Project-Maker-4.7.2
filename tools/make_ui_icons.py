"""Writes the wizard's icon set, ``rpggen/gui/icons/*.svg`` (T15.04).

The icons are drawn here, for rpggen, in the manner of the common outline sets: a 24 px view
box, a 2 px stroke with round caps and joins, and ``currentColor`` as the only colour, so that
``rpggen.gui.icons`` can draw each one in any token. They are plain files in the repository;
this tool only exists so that a change to one of them is a change to one line.

    python tools/make_ui_icons.py            # rewrite the folder
    python tools/make_ui_icons.py --check    # exit 1 when the folder differs from this file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "rpggen" / "gui" / "icons"

HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
)
RING = '<circle cx="12" cy="12" r="9"/>'


def p(d: str) -> str:
    return f'<path d="{d}"/>'


def c(cx: float, cy: float, r: float, filled: bool = False) -> str:
    fill = ' fill="currentColor" stroke="none"' if filled else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}"{fill}/>'


def r(x: float, y: float, w: float, h: float, rx: float = 0) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"/>'


ICONS: dict[str, str] = {
    "folder": p("M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"),
    "folder-open": p("M3 18V7a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v2") + p("M3 19l2.6-8H22l-2.6 8z"),
    "file-archive": p("M6 3h8l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z")
    + p("M14 3v4h4")
    + p("M10 9v1M10 12v1M10 15v1"),
    "plus": p("M12 5v14M5 12h14"),
    "minus": p("M6 12h12"),
    "x": p("M6 6l12 12M18 6L6 18"),
    "trash": p("M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5"),
    "check": p("M5 12.5l4.5 4.5L19 7.5"),
    "check-circle": RING + p("M8 12.5l3 3 5-6"),
    "alert-triangle": p("M12 4L2.5 20h19z") + p("M12 10v4") + p("M12 17v.01"),
    "x-circle": RING + p("M9 9l6 6M15 9l-6 6"),
    "info": RING + p("M12 11v5M12 8v.01"),
    "circle": RING,
    "circle-dot": RING + c(12, 12, 2.5, filled=True),
    "dot": c(12, 12, 5, filled=True),
    "search": c(10.5, 10.5, 6.5) + p("M15.5 15.5L20 20"),
    "filter": p("M4 5h16l-6 7v6l-4 2v-8z"),
    "layout-grid": r(4, 4, 7, 7, 1) + r(13, 4, 7, 7, 1) + r(4, 13, 7, 7, 1) + r(13, 13, 7, 7, 1),
    "list": p("M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"),
    "play": p("M7 4.5v15l12-7.5z"),
    "pause": p("M8 5v14M16 5v14"),
    "square": r(5, 5, 14, 14, 2),
    "eye": p("M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z") + c(12, 12, 3),
    "external-link": p("M14 4h6v6M20 4l-9 9")
    + p("M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"),
    "download": p("M12 4v11M7 11l5 5 5-5M4 20h16"),
    "refresh-cw": p("M20 11a8 8 0 0 0-14.3-4.3L4 9")
    + p("M4 4v5h5")
    + p("M4 13a8 8 0 0 0 14.3 4.3L20 15")
    + p("M20 20v-5h-5"),
    "settings": c(12, 12, 3)
    + c(12, 12, 6.5)
    + p("M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1")
    + p("M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"),
    "sliders": p("M4 7h10M18 7h2M4 17h2M10 17h10") + c(16, 7, 2) + c(8, 17, 2),
    "chevron-down": p("M6 9l6 6 6-6"),
    "chevron-up": p("M6 15l6-6 6 6"),
    "chevron-right": p("M9 6l6 6-6 6"),
    "chevron-left": p("M15 6l-6 6 6 6"),
    "undo": p("M9 14L4 9l5-5") + p("M4 9h10a6 6 0 0 1 0 12h-3"),
    "redo": p("M15 14l5-5-5-5") + p("M20 9H10a6 6 0 0 0 0 12h3"),
    "map": p("M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z") + p("M9 4v14M15 6v14"),
    "image": r(3, 4, 18, 16, 2) + c(8.5, 9.5, 1.5) + p("M21 16l-5-5L5 20"),
    "music": p("M9 18V5l11-2v13") + c(6.5, 18, 2.5) + c(17.5, 16, 2.5),
    "volume-2": p("M4 9v6h4l5 4V5L8 9z")
    + p("M16.5 8.5a5 5 0 0 1 0 7")
    + p("M19 6a8.5 8.5 0 0 1 0 12"),
    "box": p("M12 3l8 4.5v9L12 21l-8-4.5v-9z") + p("M4 7.5l8 4.5 8-4.5M12 12v9"),
    "gamepad-2": r(2, 7, 20, 10, 5) + p("M7 10.5v3M5.5 12h3") + p("M15.5 11h.01M18 13h.01"),
    "user": c(12, 8, 4) + p("M4 21a8 8 0 0 1 16 0"),
    "users": c(9, 8, 3.5)
    + p("M2 21a7 7 0 0 1 14 0")
    + p("M16 4.6a3.5 3.5 0 0 1 0 6.8")
    + p("M18 14.5a7 7 0 0 1 4 6.5"),
    "swords": p("M5 3l11 11M19 3L8 14") + p("M13 17l4-4M7 13l4 4") + p("M16 18l3 3M8 18l-3 3"),
    "book-open": p("M12 7v13")
    + p("M3 5h6a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H3z")
    + p("M21 5h-6a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h7z"),
    "help-circle": RING + p("M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7") + p("M12 17v.01"),
    "copy": r(8, 8, 12, 12, 2) + p("M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"),
    "loader": p("M12 3a9 9 0 1 0 9 9"),
}

# The application's own mark (About, T15.19): the tile-and-sword of tools/make_icon.py, in
# fixed colours. It is the one file of the folder that is not drawn in ``currentColor``.
APP_MARK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
    '<rect x="8" y="8" width="240" height="240" rx="40" fill="#202940"/>'
    + "".join(
        f'<rect x="{36 + gx * 64}" y="{36 + gy * 64}" width="56" height="56" '
        f'fill="rgb(40,{130 + ((gx + gy) % 2) * 25},{70 + ((gx + gy) % 2) * 25})"/>'
        for gx in range(3)
        for gy in range(3)
    )
    + '<polygon points="150,60 176,60 176,150 163,172 150,150" fill="#e6e8f0"/>'
    '<rect x="136" y="150" width="54" height="12" fill="#d6a846"/>'
    '<rect x="158" y="162" width="10" height="42" fill="#8c5a32"/>'
    "</svg>\n"
)
FIXED_COLOUR = {"app": APP_MARK}


def text_of(name: str) -> str:
    return HEAD + ICONS[name] + "</svg>\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    on_disk = {f.stem: f.read_text(encoding="utf-8") for f in OUT.glob("*.svg")}
    wanted = {name: text_of(name) for name in ICONS} | FIXED_COLOUR
    if args.check:
        if on_disk != wanted:
            print("rpggen/gui/icons differs from tools/make_ui_icons.py", file=sys.stderr)
            return 1
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in set(on_disk) - set(wanted):
        (OUT / f"{stale}.svg").unlink()
    for name, text in wanted.items():
        (OUT / f"{name}.svg").write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(wanted)} icons to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
