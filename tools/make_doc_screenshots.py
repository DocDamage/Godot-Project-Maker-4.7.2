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

# The conflict resolver's picture: a generated script the user edited, and a newer version of it.
CONFLICT_FILE = "addons/rpg_runtime/world/sign.gd"
CONFLICT_MINE = (
    (
        "@export var dialogue: RpgDialogueResource\n",
        "@export var dialogue: RpgDialogueResource\n"
        "@export var read_once := false  # my change: a sign that is read only once\n",
    ),
)
CONFLICT_NEW = (
    (
        '\t\tpush_error("[RPG-DLG] no dialogue box to show the sign")\n',
        '\t\tpush_warning("[RPG-DLG] no dialogue box to show the sign")\n',
    ),
)


def _edited(text: str, edits: tuple[tuple[str, str], ...]) -> str:
    for old, new in edits:
        assert old in text, old
        text = text.replace(old, new)
    return text


def conflict_project(root: Path) -> Path:
    """A project folder with one conflict: the last generated file (in a backup, as the ledger
    records it), the user's edit of it, and the new version beside it as ``.rpggen-new``."""
    from rpggen import paths
    from rpggen.core import conflicts, ledger, promote

    base = (REPO / "godot_templates" / CONFLICT_FILE).read_text(encoding="utf-8")
    mine = paths.from_posix_rel(CONFLICT_FILE, root)
    backup = paths.from_posix_rel(CONFLICT_FILE, root / promote.BACKUPS_NAME / "20260101-120000")
    for path, text in (
        (backup, base),
        (mine, _edited(base, CONFLICT_MINE)),
        (mine.with_name(mine.name + conflicts.NEW_SUFFIX), _edited(base, CONFLICT_NEW)),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    book = ledger.Ledger()
    book.files[CONFLICT_FILE] = ledger.LedgerEntry(
        ledger.hash_bytes(base.encode("utf-8"), CONFLICT_FILE), "runtime", "generated"
    )
    ledger_path = paths.from_posix_rel(paths.LEDGER, root)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    book.save(ledger_path)
    return root


def promotion_summary():  # type: ignore[no-untyped-def]
    """A regeneration after a pack update and one edited script, for the preview's picture."""
    from rpggen.core.promote import PromotionSummary

    return PromotionSummary(
        write=[
            "generated/tilesets/rpggen_sample_pack.tres",
            "generated/sprite_frames/hero.tres",
            "generated/sprite_frames/slime.tres",
            "generated/objects/tree_oak.tscn",
            "generated/minimaps/starter_map.tres",
            "addons/rpg_runtime/CHANGELOG.md",
            "rpggen/asset_catalog.json",
        ],
        conflicts=[CONFLICT_FILE],
        delete=["generated/objects/barrel_old.tscn"],
        skipped_deleted=["game/data/dialogue/demo_elder.tres"],
        backup=".rpggen_backups/20260101-120000",
    )


def _pump(app, seconds: float = 0.3) -> None:
    from PySide6.QtCore import QCoreApplication, QEvent

    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        # no event loop runs here, so a widget a page replaced (deleteLater) would stay painted
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.01)


def render(out: Path, godot: Path | None = None) -> list[Path]:
    """Write one PNG per wizard page (plus the crash dialog) and return the paths."""
    from PySide6.QtWidgets import QApplication

    from rpggen.core import godot as godot_mod
    from rpggen.gui import app as gui_app
    from rpggen.gui import state as state_mod
    from rpggen.gui import theme
    from rpggen.gui.dialogs.about_dialog import AboutDialog
    from rpggen.gui.dialogs.conflict_dialog import ConflictDialog
    from rpggen.gui.dialogs.promotion_dialog import PromotionDialog
    from rpggen.gui.dialogs.storage_dialog import StorageDialog
    from rpggen.gui.pages.generate_page import GeneratePage
    from rpggen.gui.pages.project_page import ProjectPage
    from rpggen.gui.wizard import OPTIONS_INDEX, MainWindow, default_pages

    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="rpggen_shots_") as tmp:
        tmp_path = Path(tmp)
        # before the application starts: the pictures must not depend on this machine's settings
        # (theme, language, splitter positions)
        os.environ["RPGGEN_CACHE_DIR"] = str(tmp_path / "cache")
        qapp = gui_app.create_app([])
        assert isinstance(qapp, QApplication)
        # a fresh settings folder would start the Audit page's first-run tour over the picture
        from rpggen.core import app_settings

        app_settings.update(tours_seen=["audit"])
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

        window.show_welcome_view()
        _pump(qapp, 1.0)  # the Godot check runs in the background
        grab("welcome")
        window.leave_welcome()
        window.show_page(0)
        grab("wizard_project")
        page0 = window.pages[0]
        assert isinstance(page0, ProjectPage)
        page0.sample_button.click()  # fills the inputs and presses Next to the options page
        deadline = time.time() + 120
        while window.state.catalog is None and time.time() < deadline:
            _pump(qapp, 0.2)  # the pack is analyzed in the background
        _pump(qapp, 1.0)
        window.show_page(0)  # the sample pack's card, with its format and licence
        _pump(qapp)
        cards = out / "pack_cards.png"
        page0.pack_list.grab().save(str(cards))
        written.append(cards)
        for index, name in enumerate(PAGES):
            if index == 0:
                continue
            window.show_page(index)
            if name == "audit":
                window.current_page.grid.chips["chipAll"].click()  # the sample pack needs no review
                model = window.current_page.grid.view.model()
                rows = [model.index(r, 0) for r in range(model.rowCount())]
                pick = next((i for i in rows if str(i.data()) == "town.png"), rows[0])
                window.current_page.grid.view.setCurrentIndex(pick)
            _pump(qapp, 1.5 if name == "audit" else 0.3)  # thumbnails load in the background
            grab(f"wizard_{name}")
            if name == "audit":  # the light theme, on the page that uses the most colour
                theme.apply_theme("light", remember=False)
                grab("wizard_audit_light")
                theme.apply_theme("dark", remember=False)
            if name == "options":
                _pump(qapp, 1.0)  # the starter map preview renders in the background
                picture = out / "map_preview.png"
                window.current_page.preview.grab().save(str(picture))
                written.append(picture)
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

        def grab_dialog(widget, name: str, seconds: float = 0.3) -> None:  # type: ignore[no-untyped-def]
            widget.show()
            _pump(qapp, seconds)
            path = out / f"{name}.png"
            widget.grab().save(str(path))
            written.append(path)
            widget.close()

        grab_dialog(AboutDialog(window), "about_dialog")
        grab_dialog(PromotionDialog(promotion_summary(), window), "regeneration_preview")
        resolver = ConflictDialog(conflict_project(tmp_path / "conflict_demo"), None, window)
        grab_dialog(resolver, "conflict_resolver")
        grab_dialog(StorageDialog(window), "storage_dialog", 1.5)  # the sizes are measured
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
