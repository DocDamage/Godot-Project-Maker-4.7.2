"""Developer commands: ``python -m rpggen.dev godot-test`` and ``make-fixtures``."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rpggen.core import godot

if TYPE_CHECKING:
    from PySide6.QtGui import QImage

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = REPO_ROOT / "godot_templates"


def resolve_godot(exe: Path | None = None) -> Path:
    """The Godot executable from the argument, $RPGGEN_GODOT, or auto-discovery."""
    if exe is not None:
        return exe
    env = os.environ.get("RPGGEN_GODOT")
    if env:
        return Path(env)
    found = godot.auto_find_godot()
    if not found:
        raise SystemExit("Godot not found: set RPGGEN_GODOT to the Godot 4.7.2 console executable")
    return found[0]


def godot_test(exe: Path | None = None) -> int:
    """Run the template project's GDScript tests headless; returns the process exit code."""
    exe = godot.find_console_exe(resolve_godot(exe))
    with tempfile.TemporaryDirectory(prefix="rpggen_godot_test_") as tmp:
        project = Path(tmp) / "godot_templates"
        shutil.copytree(TEMPLATES, project, ignore=shutil.ignore_patterns(".godot", "results.json"))
        log_dir = Path(tmp) / "logs"
        imp = godot.import_project(exe, project, log_dir)
        if imp.returncode != 0 or imp.timed_out:
            print(imp.stdout)
            print(imp.stderr, file=sys.stderr)
            return 1
        run = godot.run_godot(
            exe,
            project,
            ["--script", "res://tests/run_tests.gd"],
            timeout_s=godot.BUILD_TIMEOUT_S,
            log_name="unit_tests",
            log_dir=log_dir,
        )
        for line in run.stdout.splitlines():
            if line.startswith(("PASS ", "FAIL ", "tests:", "godot:")):
                print(line)
        if run.returncode != 0:
            print(run.stderr, file=sys.stderr)
        return 1 if run.timed_out else run.returncode


def make_fixtures() -> int:
    tool = REPO_ROOT / "tools" / "make_synthetic_packs.py"
    out = REPO_ROOT / "test_packs" / "synthetic"
    return subprocess.run([sys.executable, str(tool), "--out", str(out)], check=False).returncode


def synthetic_packs() -> list[Path]:
    root = REPO_ROOT / "test_packs" / "synthetic"
    return sorted(p for p in root.iterdir() if p.is_dir() or p.suffix == ".zip")


SIDE_SAMPLE = "sample_pack_side"


def update_goldens() -> int:
    """Rewrite tests/golden/<pack>.catalog.json from the current assemble() output."""
    from rpggen import jsonio
    from rpggen.core import archive, catalog, inventory

    golden = REPO_ROOT / "tests" / "golden"
    golden.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rpggen_goldens_") as tmp:
        os.environ["RPGGEN_CACHE_DIR"] = tmp
        for pack_path in synthetic_packs():
            opened = archive.open_pack(pack_path, set())
            inv = inventory.build_inventory(opened)
            cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=False)
            target = golden / f"{pack_path.stem}.catalog.json"
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(jsonio.dumps(cat.to_json()))
            print(f"wrote {pack_path.stem}.catalog.json")
        # the side-view sample pack has its own golden (T14.09); the top-down one never had
        side = REPO_ROOT / SIDE_SAMPLE
        opened = archive.open_pack(side, set(), pack_id=SIDE_SAMPLE)
        inv = inventory.build_inventory(opened)
        cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=False)
        with open(
            golden / f"{SIDE_SAMPLE}.catalog.json", "w", encoding="utf-8", newline="\n"
        ) as fh:
            fh.write(jsonio.dumps(cat.to_json()))
        print(f"wrote {SIDE_SAMPLE}.catalog.json")
    return 0


LAYOUT_ARCHETYPES = ("turn_based", "arpg", "metroidvania")
LAYOUT_THEMES = ("dark", "light")


_FONT_FILES = (
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
)


def ensure_real_font() -> str | None:
    """Make the application use a real font and return its family (None when the machine has
    none). Qt's offscreen platform on Windows has no font database, so every glyph is a box about
    twice as wide as a letter and layouts measured there are not those a user sees."""
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return None
    families = QFontDatabase.families()
    if not families:
        for candidate in _FONT_FILES:
            if Path(candidate).is_file():
                font_id = QFontDatabase.addApplicationFont(candidate)
                families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
                if families:
                    break
    if not families:
        return None
    family = next(
        (f for f in ("Segoe UI", "DejaVu Sans", "Arial", "Helvetica") if f in families), families[0]
    )
    app.setFont(QFont(family, 9))
    return family


def layout_sizes() -> dict[str, tuple[int, int]]:
    """The two window sizes the layout test and ``layout-shots`` use."""
    from rpggen.gui import wizard

    return {"minimum": wizard.MIN_WINDOW, "default": wizard.DEFAULT_WINDOW}


def layout_state(archetype: str, scratch: Path):  # noqa: ANN201 - WizardState, imported lazily
    """A wizard state analysed from the sample pack (no Godot needed), with a finished run in
    ``scratch`` so that the Generate and Results pages show their finished views."""
    from rpggen import paths
    from rpggen.core import config, orchestrator, report
    from rpggen.core.orchestrator import Callbacks
    from rpggen.gui import workers
    from rpggen.gui.state import WizardState

    # a metroidvania is laid out with the pack it is made for: the side-view sample
    side = archetype == "metroidvania"
    sample = paths.sample_pack_side_root() if side else paths.sample_pack_root()
    state = WizardState(project_name="Layout check", pack_sources=[sample], archetype=archetype)
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    ref = config.PackRef(sample.name, str(sample), "0" * 64, "folder")
    state.config = config.default_for("Layout check", [ref], archetype=archetype)
    state.target = scratch / "layout_project"
    state.godot_exe = scratch / "godot.exe"
    (state.target / "generated").mkdir(parents=True, exist_ok=True)
    (state.target / "generated" / "a.tscn").write_text("", encoding="utf-8")
    (state.target / report.REPORT_MD).write_text("# Generation Report\n", encoding="utf-8")
    state.run_result = orchestrator.RunResult(
        True, state.target, [], None, None, catalog=state.catalog, cfg=state.config
    )
    return state


def show_each_page(window, on_page) -> None:  # noqa: ANN001 - MainWindow, imported lazily
    """Show every wizard page of ``window`` (and the welcome view) and call
    ``on_page(name, widget)`` once the page has been laid out."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    assert app is not None

    def settle() -> None:  # a scroll area lays its content out over a few turns
        for _ in range(3):
            app.processEvents()

    for index, page in enumerate(window.pages):
        window.show_page(index)
        settle()
        on_page(f"{index + 1}_{page.title.lower()}", window)
    window.show_welcome_view()
    settle()
    on_page("0_welcome", window)


def layout_shots(out: Path | None = None) -> int:
    """Write a PNG of every page, in both themes, both archetypes and both window sizes."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from rpggen.gui import app as gui_app
    from rpggen.gui import theme
    from rpggen.gui.wizard import MainWindow, default_pages

    out = out or Path(tempfile.mkdtemp(prefix="rpggen_layout_shots_"))
    out.mkdir(parents=True, exist_ok=True)
    os.environ["RPGGEN_CACHE_DIR"] = str(out / "cache")
    gui_app.create_app()
    ensure_real_font()
    count = 0
    for archetype in LAYOUT_ARCHETYPES:
        state = layout_state(archetype, out)
        for theme_name in LAYOUT_THEMES:
            theme.apply_theme(theme_name, remember=False)
            for size_name, (width, height) in layout_sizes().items():
                window = MainWindow(state, default_pages())
                window.resize(width, height)
                window.show()

                def shoot(name: str, win, prefix: str = f"{archetype}_{theme_name}_{size_name}"):
                    win.grab().save(str(out / f"{prefix}_{name}.png"))

                show_each_page(window, shoot)
                count += 1 + len(window.pages)
                window.close()
    print(f"wrote {count} pictures to {out}")
    return 0


# ---------------------------------------------------------------------- visual goldens (T15.23)

UI_GOLDENS = REPO_ROOT / "tests" / "gui" / "goldens"
UI_GOLDENS_MADE_WITH = "made_with.json"  # the font the goldens were rendered with
UI_GOLDEN_ARCHETYPE = "turn_based"
MEAN_LIMIT = 0.015  # the mean absolute difference over the whole picture
BLOCK_LIMIT = 0.20  # and over any one block of BLOCK x BLOCK pixels
BLOCK = 32
# Widgets that show this machine's own paths: painted over in a golden picture.
UI_GOLDEN_MASKED: tuple[str, ...] = ()


def _pump(seconds: float) -> None:
    """Run the application's events for a while: thumbnails and previews load in workers."""
    import time

    from PySide6.QtCore import QCoreApplication, QEvent

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.01)


def _golden_picture(window: Any) -> QImage:
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QWidget

    from rpggen.gui import theme

    picture = window.grab().toImage().convertToFormat(QImage.Format.Format_RGB888)
    painter = QPainter(picture)
    for name in UI_GOLDEN_MASKED:
        for widget in window.findChildren(QWidget, name):
            if widget.isVisible():
                corner = widget.mapTo(window, QPoint(0, 0))
                painter.fillRect(QRect(corner, widget.size()), theme.token("border"))
    painter.end()
    return picture


def ui_golden_pictures(scratch: Path) -> Iterator[tuple[str, QImage]]:
    """The welcome view and the seven pages in both themes and both window sizes, as
    ``(name, picture)``. Nothing in a picture depends on the machine but its font: the welcome
    view is a first start without a Godot, the Project page has no folder and no Godot yet, the
    later pages show the sample pack and a finished run, and nothing is animated. The
    application needs a real font (``ensure_real_font``) and its settings in a folder of their
    own (``RPGGEN_CACHE_DIR``)."""
    from rpggen.core import app_settings
    from rpggen.gui import theme
    from rpggen.gui.wizard import MainWindow, default_pages

    found = godot.auto_find_godot
    godot.auto_find_godot = lambda *_args: []  # type: ignore[assignment]  # none is found
    motion = app_settings.get().reduce_motion
    app_settings.update(reduce_motion="on", tours_seen=["audit"])
    theme.apply_motion()
    try:
        state = layout_state(UI_GOLDEN_ARCHETYPE, scratch)
        for theme_name in LAYOUT_THEMES:
            theme.apply_theme(theme_name, remember=False)
            for size_name, (width, height) in layout_sizes().items():
                target, exe = state.target, state.godot_exe
                state.target = state.godot_exe = None
                window = MainWindow(state, default_pages())
                window.resize(width, height)
                window.show()
                prefix = f"{theme_name}_{size_name}"
                app_settings.update(recent_projects=[])  # the Generate page before this one
                window.show_welcome_view()
                window.welcome._godot_generation += 1  # the answer of the search is not shown
                window.welcome.show_godot(None)
                _pump(0.3)
                yield f"{prefix}_0_welcome", _golden_picture(window)
                window.leave_welcome()
                for index, page in enumerate(window.pages):
                    window.show_page(index)
                    if index == 1:  # the Project page was left: the folder of the run comes back
                        state.target, state.godot_exe = target, exe
                    _pump(1.5 if page.title in ("Audit", "Options") else 0.3)
                    yield f"{prefix}_{index + 1}_{page.title.lower()}", _golden_picture(window)
                window.close()
                state.target, state.godot_exe = target, exe
                _pump(0.05)
    finally:
        godot.auto_find_godot = found
        app_settings.update(reduce_motion=motion)
        theme.apply_motion()
        theme.apply_theme("dark", remember=False)


def compare_pictures(shown: QImage, golden: QImage) -> tuple[float, float, QImage]:
    """How far ``shown`` is from ``golden``: the mean absolute difference over the picture, the
    largest mean difference of one 32 x 32 block (both 0 to 1), and a picture of the difference
    (the golden in grey, red where the two differ). Pictures of two sizes differ wholly."""
    import numpy as np
    from PySide6.QtGui import QImage

    def pixels(image: QImage) -> Any:
        image = image.convertToFormat(QImage.Format.Format_RGB888)
        raw = np.frombuffer(image.constBits(), dtype=np.uint8)
        rows = raw.reshape(image.height(), image.bytesPerLine())[:, : image.width() * 3]
        return rows.reshape(image.height(), image.width(), 3).astype(np.float32) / 255.0

    if shown.size() != golden.size():
        return 1.0, 1.0, shown.copy()
    old = pixels(golden)
    diff = np.abs(pixels(shown) - old).mean(axis=2)
    height, width = diff.shape
    rows = np.add.reduceat(diff, np.arange(0, height, BLOCK), axis=0)
    sums = np.add.reduceat(rows, np.arange(0, width, BLOCK), axis=1)
    # a block at the right or bottom edge is smaller: its mean is over what it has
    areas = np.outer(
        np.diff(np.append(np.arange(0, height, BLOCK), height)),
        np.diff(np.append(np.arange(0, width, BLOCK), width)),
    )
    grey = old.mean(axis=2, keepdims=True) * 0.5 + 0.25
    marked = np.clip(np.sqrt(diff)[..., None] * 2.0, 0.0, 1.0)
    out = grey * (1.0 - marked) + np.array([1.0, 0.1, 0.1], dtype=np.float32) * marked
    data = np.ascontiguousarray((out * 255.0).astype(np.uint8))
    picture = QImage(data.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()
    return float(diff.mean()), float((sums / areas).max()), picture


def ui_goldens_font() -> str | None:
    """The font family the goldens in the repository were rendered with (None: there are none)."""
    import json

    path = UI_GOLDENS / UI_GOLDENS_MADE_WITH
    if not path.is_file():
        return None
    return str(json.loads(path.read_text(encoding="utf-8")).get("font") or "") or None


def update_ui_goldens() -> int:
    """Rewrite tests/gui/goldens/*.png (and the note of the font they were made with)."""
    import json

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # as the GUI tests render
    from rpggen.gui import app as gui_app

    with tempfile.TemporaryDirectory(prefix="rpggen_ui_goldens_") as tmp:
        os.environ["RPGGEN_CACHE_DIR"] = str(Path(tmp) / "cache")
        gui_app.create_app()
        family = ensure_real_font()
        if family is None:
            print("no real font on this machine: the goldens were not written")
            return 1
        UI_GOLDENS.mkdir(parents=True, exist_ok=True)
        for old in UI_GOLDENS.glob("*.png"):
            old.unlink()
        shutil.rmtree(UI_GOLDENS / "_failed", ignore_errors=True)
        count = 0
        for name, picture in ui_golden_pictures(Path(tmp)):
            picture.save(str(UI_GOLDENS / f"{name}.png"))
            count += 1
        note = {"font": family, "platform": sys.platform}
        (UI_GOLDENS / UI_GOLDENS_MADE_WITH).write_text(
            json.dumps(note, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    print(f"wrote {count} goldens to {UI_GOLDENS} (font: {family})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rpggen.dev")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("godot-test", help="run the template project's GDScript tests")
    sub.add_parser("make-fixtures", help="regenerate test_packs/synthetic")
    sub.add_parser("update-goldens", help="rewrite tests/golden/*.catalog.json")
    sub.add_parser("update-ui-goldens", help="rewrite tests/gui/goldens/*.png")
    shots = sub.add_parser("layout-shots", help="picture every wizard page, theme and size")
    shots.add_argument("--out", type=Path, default=None, help="folder for the PNG files")
    args = parser.parse_args(argv)
    if args.command == "godot-test":
        return godot_test()
    if args.command == "update-goldens":
        return update_goldens()
    if args.command == "update-ui-goldens":
        return update_ui_goldens()
    if args.command == "layout-shots":
        return layout_shots(args.out)
    return make_fixtures()


if __name__ == "__main__":
    raise SystemExit(main())
