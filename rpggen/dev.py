"""Developer commands: ``python -m rpggen.dev godot-test`` and ``make-fixtures``."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rpggen.core import godot

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
            if line.startswith(("PASS ", "FAIL ", "tests:")):
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
    return 0


LAYOUT_ARCHETYPES = ("turn_based", "arpg")
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

    sample = paths.sample_pack_root()
    state = WizardState(project_name="Layout check", pack_sources=[sample], archetype=archetype)
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    ref = config.PackRef("sample_pack", str(sample), "0" * 64, "folder")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rpggen.dev")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("godot-test", help="run the template project's GDScript tests")
    sub.add_parser("make-fixtures", help="regenerate test_packs/synthetic")
    sub.add_parser("update-goldens", help="rewrite tests/golden/*.catalog.json")
    shots = sub.add_parser("layout-shots", help="picture every wizard page, theme and size")
    shots.add_argument("--out", type=Path, default=None, help="folder for the PNG files")
    args = parser.parse_args(argv)
    if args.command == "godot-test":
        return godot_test()
    if args.command == "update-goldens":
        return update_goldens()
    if args.command == "layout-shots":
        return layout_shots(args.out)
    return make_fixtures()


if __name__ == "__main__":
    raise SystemExit(main())
