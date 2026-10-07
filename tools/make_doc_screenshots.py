"""Render the screenshots used by docs/user_guide.md (T10.06).

    python tools/make_doc_screenshots.py [--out docs/images] [--godot PATH]

The wizard is driven offscreen on the bundled sample pack and every page is grabbed with
``QWidget.grab()``, so the images are regenerated instead of drawn by hand. With ``--godot`` (or
RPGGEN_GODOT) the generate and results pages are included as well. The pictures depend on the
fonts of the machine that renders them; regenerate them when the GUI changes.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

if sys.platform != "win32":
    # Windows renders real fonts with its own platform plugin (windows pop up briefly); the
    # offscreen plugin has no font database there. Elsewhere install a font (fonts-dejavu).
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

PAGES = ("project", "archetype", "audit", "mapping", "options")


def _pump(app, seconds: float = 0.3) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def render(out: Path, godot: Path | None = None) -> list[Path]:
    """Write one PNG per wizard page (plus the crash dialog) and return the paths."""
    from PySide6.QtWidgets import QApplication

    from rpggen.core import godot as godot_mod
    from rpggen.gui import app as gui_app
    from rpggen.gui import state as state_mod
    from rpggen.gui.pages.generate_page import GeneratePage
    from rpggen.gui.pages.project_page import ProjectPage
    from rpggen.gui.wizard import OPTIONS_INDEX, MainWindow, default_pages

    out.mkdir(parents=True, exist_ok=True)
    qapp = gui_app.create_app([])
    assert isinstance(qapp, QApplication)
    written: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="rpggen_shots_") as tmp:
        tmp_path = Path(tmp)
        os.environ["RPGGEN_CACHE_DIR"] = str(tmp_path / "cache")
        (tmp_path / "Documents").mkdir()
        ProjectPage.documents_dir = lambda self: tmp_path / "Documents"  # type: ignore[method-assign]
        if godot is not None:
            godot_mod.auto_find_godot = lambda: [godot]  # type: ignore[assignment]
        window = MainWindow(state_mod.WizardState(), default_pages())
        window.resize(1100, 720)
        window.show()
        _pump(qapp)

        def grab(name: str) -> None:
            _pump(qapp)
            path = out / f"{name}.png"
            window.grab().save(str(path))
            written.append(path)

        grab("wizard_project")
        page0 = window.pages[0]
        assert isinstance(page0, ProjectPage)
        page0.sample_button.click()  # fills the inputs and presses Next to the options page
        _pump(qapp, 1.0)
        for index, name in enumerate(PAGES):
            if index == 0:
                continue
            window.show_page(index)
            if name == "audit":
                window.current_page.grid.chips["chipAll"].click()  # the sample pack needs no review
                model = window.current_page.grid.view.model()
                rows = [model.index(r, 0) for r in range(model.rowCount())]
                pick = next((i for i in rows if "town" in str(i.data())), rows[0])
                window.current_page.grid.view.setCurrentIndex(pick)
            _pump(qapp, 1.5 if name == "audit" else 0.3)  # thumbnails load in the background
            grab(f"wizard_{name}")
        if godot is not None:
            window.show_page(OPTIONS_INDEX)
            window.next_button.click()
            generate = window.current_page
            assert isinstance(generate, GeneratePage)
            deadline = time.time() + 600
            while generate.running and time.time() < deadline:
                _pump(qapp, 0.2)
            grab("wizard_generate")
            window.next_button.click()
            grab("wizard_results")
        dialog = gui_app.CrashDialog("Traceback (most recent call last):\nValueError: example")
        dialog.show()
        _pump(qapp)
        crash = out / "crash_dialog.png"
        dialog.grab().save(str(crash))
        written.append(crash)
        dialog.close()
        window.close()
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=REPO / "docs" / "images")
    parser.add_argument("--godot", type=Path, default=None)
    args = parser.parse_args(argv)
    exe = args.godot or (
        Path(os.environ["RPGGEN_GODOT"]) if os.environ.get("RPGGEN_GODOT") else None
    )
    for path in render(args.out, exe):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
