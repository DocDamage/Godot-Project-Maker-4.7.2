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


def _areas_picture(box, out: Path, qapp) -> Path:  # type: ignore[no-untyped-def]
    """The Areas table with a small world and its preview (T13.20). The table is switched off
    again afterwards, so the project the script generates is the usual one."""
    from PySide6.QtCore import QRect

    box.areas.enable_box.setChecked(True)
    for name, biome in (("Woods", "forest"), ("Old mine", "cave"), ("Bay", "shore")):
        box.areas.set_value(box.areas.add_row(name), "biome", biome)
    box.world.choose("woods")
    _pump(qapp, 0.5)
    top = box.areas.y()
    path = out / "areas_table.png"
    box.grab(QRect(0, top, box.width(), box.height() - top)).save(str(path))
    box.areas.enable_box.setChecked(False)
    _pump(qapp, 0.2)
    return path


def _samples_picture(welcome, out: Path, qapp) -> Path | None:  # type: ignore[no-untyped-def]
    """The welcome view's *Try the sample* card with its menu of two samples open under it
    (T14.09). A menu is a window of its own, so the two are drawn into one picture."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor, QPainter, QPixmap

    menu = welcome.sample_menu
    if menu is None:  # the metroidvania is switched off: there is one sample and no menu
        return None
    card = welcome.sample_card.grab()
    menu.popup(welcome.sample_card.mapToGlobal(QPoint(0, welcome.sample_card.height())))
    _pump(qapp)
    listed = menu.grab()
    menu.close()
    _pump(qapp)
    ratio = card.devicePixelRatio()
    width = max(card.width(), listed.width())
    picture = QPixmap(width, card.height() + listed.height())
    picture.setDevicePixelRatio(ratio)
    picture.fill(QColor(0, 0, 0, 0))
    painter = QPainter(picture)
    painter.drawPixmap(0, 0, card)
    painter.drawPixmap(0, int(card.height() / ratio), listed)
    painter.end()
    path = out / "welcome_samples.png"
    picture.save(str(path))
    return path


def _world_picture(out: Path, qapp) -> Path:  # type: ignore[no-untyped-def]
    """The Options page's *Starter world* box of a metroidvania with its side-view preview
    (T14.10): the default world of six rooms."""
    from rpggen.core import config
    from rpggen.gui import state as state_mod
    from rpggen.gui.pages.options_page import OptionsPage

    ref = config.PackRef("sample_pack_side", "sample_pack_side", "0" * 64, "folder")
    cfg = config.default_for("Sample Cave", [ref], archetype="metroidvania")
    page = OptionsPage()
    page.resize(760, 900)
    page.show()
    page.enter(state_mod.WizardState(config=cfg, archetype="metroidvania"))
    _pump(qapp, 0.5)
    page._show_world()  # once more at the shown width: the picture fits the box
    _pump(qapp)
    path = out / "world_preview.png"
    page.world_box.grab().save(str(path))
    page.close()
    return path


KIND_PICTURES = {  # kind: (the sample of the kind, the picture of its options)
    "shmup": ("sample_pack_shmup", "options_shmup"),
    "run_and_gun": ("sample_pack_gun", "options_run_and_gun"),
    "racing": ("sample_pack_race", "options_racing"),
}


def _kind_pictures(out: Path, qapp) -> list[Path]:  # type: ignore[no-untyped-def]
    """The Options page's box of each arcade kind with the picture of its plan (T16.16): the
    wave chart, the stage strip and the tracks, each of the kind's default options."""
    from rpggen.core import config
    from rpggen.gui import state as state_mod
    from rpggen.gui.pages.options_page import OptionsPage

    written: list[Path] = []
    for kind, (pack, name) in KIND_PICTURES.items():
        ref = config.PackRef(pack, pack, "0" * 64, "folder")
        cfg = config.default_for("Sample", [ref], archetype=kind)
        page = OptionsPage()
        page.resize(760, 900)
        page.show()
        page.enter(state_mod.WizardState(config=cfg, archetype=kind))
        _pump(qapp, 0.5)
        page._show_world()  # once more at the shown width: the picture fits the box
        _pump(qapp)
        path = out / f"{name}.png"
        page.arcade_boxes[kind].grab().save(str(path))
        page.close()
        written.append(path)
    return written


# kind: (the sample's key, the step of its smoke sequence that is on the picture, frames into
# it, the picture)
GAME_PICTURES = {
    "shmup": ("shmup", "wave_is_fought", 45, "game_shmup"),
    "run_and_gun": ("gun", "weapon_is_picked_up", 60, "game_run_and_gun"),
    "racing": ("race", "race_is_driven_to_the_finish", 420, "game_racing"),
}


def _game_pictures(godot: Path, work: Path, out: Path) -> list[Path]:
    """One picture of each arcade kind's game (T16.19): the sample of the kind is generated and
    its smoke sequence plays it in a window, with tools/doc_shots/game_shot.gd taking the
    picture. None for a kind whose game Godot could not show (a machine without a display)."""
    import shutil
    import subprocess

    from rpggen.core import archive, catalog, config, inventory, mapping, orchestrator, profiles
    from rpggen.core import godot as godot_mod
    from rpggen.gui.models import project_model

    written: list[Path] = []
    for kind, (key, step, frames, name) in GAME_PICTURES.items():
        sample = project_model.sample(key)
        pack = REPO / sample.folder
        profiles.install_profile(pack / sample.profile)
        opened = archive.open_pack(pack, set(), pack_id=sample.folder)
        cat, _issues, _generated = catalog.assemble(
            [(opened, inventory.build_inventory(opened))], None, []
        )
        cfg = config.default_for(
            sample.name, [config.pack_ref_from_source(pack, sample.folder)], archetype=kind
        )
        cfg.starter = mapping.default_starter(cat, kind)
        cfg.validation = {**cfg.validation, "smoke_test": False, "export_check": False}
        target = work / f"game_{kind}"
        result = orchestrator.run_in_memory(cfg, None, target, godot)
        if not result.ok:
            continue
        shot = REPO / "tools" / "doc_shots" / "game_shot.gd"
        shutil.copyfile(shot, target / "rpggen/doc_shot.gd")
        path = (out / f"{name}.png").resolve()  # Godot is given the whole path
        path.unlink(missing_ok=True)
        cmd = [
            str(godot_mod.find_console_exe(godot)), "--path", str(target), "--",
            "--rpg-smoke", "--rpg-smoke-steps=res://rpggen/doc_shot.gd",
            f"--rpg-doc-steps={orchestrator.smoke_steps_for(kind)}",
            f"--rpg-doc-step={step}", f"--rpg-doc-frames={frames}", f"--rpg-doc-out={path}",
        ]  # fmt: skip
        try:
            subprocess.run(cmd, capture_output=True, timeout=600, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if path.is_file() and path.stat().st_size > 500:
            written.append(path)
    return written


def _variant_dialog(window):  # type: ignore[no-untyped-def]
    """Audit → Make variant… for the sample pack's slime, turned to another colour (T13.18)."""
    from rpggen.gui.dialogs.variant_dialog import VariantDialog
    from rpggen.gui.pages.audit_page import make_resolver

    catalog = window.state.catalog
    slime = next(a for a in catalog.assets if a.path.endswith("slime_idle.png"))
    dialog = VariantDialog(catalog, slime, Path(make_resolver(window.state)(slime)), window)
    dialog.hue_dial.setValue(120)
    dialog.name_edit.setText("Fire slime")
    dialog.stat_spins["hp"].setValue(2.0)
    dialog.stat_spins["gold"].setValue(3.0)
    return dialog


FAILED_LOG = "godot_build.log"
FAILED_CAUSE = (
    "Failed loading resource: res://assets/packs/sample_pack/tilesets/town.png. "
    "Make sure resources have been imported by opening the project in the editor at least once."
)


def failed_result(root: Path, target: Path | None):  # type: ignore[no-untyped-def]
    """A run that failed while Godot built the project, for the Results page's picture (T15.21):
    the problem with what Godot said, the log of the step and the folder that was kept."""
    from rpggen.core import orchestrator
    from rpggen.errors import Issue, Severity

    failed = root / ".rpggen_failed" / "20260101-120000"
    logs = failed / "rpggen" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    lines = [
        "Godot Engine v4.7.2.stable.official - https://godotengine.org",
        "[rpggen] INFO running tileset_recipe",
        "[rpggen] INFO tileset rpggen_sample_pack: 3 sources",
        f"ERROR: {FAILED_CAUSE}",
        "   at: _load (core/io/resource_loader.cpp:343)",
        "[rpggen] ERROR BUILD-002 recipe tileset_recipe failed",
        "[rpggen] INFO build finished ok=false",
    ]
    (logs / FAILED_LOG).write_text("\n".join(lines) + "\n", encoding="utf-8")
    issue = Issue(
        "BUILD-002",
        Severity.ERROR,
        "Recipe tileset_recipe failed.",
        "Open the log; if the file it names is one of your assets, check it in the audit.",
    )
    issue.detail.update(
        cause=FAILED_CAUSE,
        log=FAILED_LOG,
        file="res://assets/packs/sample_pack/tilesets/town.png",
    )
    return orchestrator.RunResult(
        False, target or root / "game", [issue], None, failed, failed_phase="build"
    )


def _quests_picture(godot: Path, project: Path | None, out: Path) -> Path | None:
    """The dock's Quests tab of the generated project (T13.19), drawn by Godot itself. Godot has
    to open a window for it; None when it cannot (a machine without a display)."""
    import subprocess

    from rpggen.core import godot as godot_mod

    if project is None or not (Path(project) / "project.godot").is_file():
        return None
    path = out / "quests_tab.png"
    path.unlink(missing_ok=True)
    script = REPO / "tools" / "doc_shots" / "quests_tab.gd"
    cmd = [str(godot_mod.find_console_exe(godot)), "--path", str(project), "--script", str(script)]
    try:
        subprocess.run([*cmd, "--", str(path)], capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return path if path.is_file() and path.stat().st_size > 500 else None


def render(
    out: Path,
    godot: Path | None = None,
    size: tuple[int, int] = (1100, 720),
    font: str | None = None,
) -> list[Path]:
    """Write one PNG per wizard page (plus the crash dialog) and return the paths. ``size`` is
    the window's and ``font`` a family for every text (the machine's own when None)."""
    from PySide6.QtGui import QFont
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
        if font:
            qapp.setFont(QFont(font, 9))
        # a fresh settings folder would start the Audit page's first-run tour over the picture
        from rpggen.core import app_settings

        app_settings.update(tours_seen=["audit"])
        (tmp_path / "Documents").mkdir()
        ProjectPage.documents_dir = lambda self: tmp_path / "Documents"  # type: ignore[method-assign]
        if godot is not None:
            godot_mod.auto_find_godot = lambda: [godot]  # type: ignore[assignment]
        window = MainWindow(state_mod.WizardState(), default_pages())
        window.resize(*size)
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
        samples = _samples_picture(window.welcome, out, qapp)
        if samples is not None:
            written.append(samples)
        window.leave_welcome()
        window.show_page(0)
        grab("wizard_project")
        page0 = window.pages[0]
        assert isinstance(page0, ProjectPage)
        page0.sample_actions["top"].trigger()  # fills the inputs and presses Next to the options
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
                window.current_page.toggle_review_mode()  # one asset at a time (T13.01)
                _pump(qapp, 0.8)
                grab("review_mode")
                window.current_page.toggle_review_mode()
            if name == "options":
                _pump(qapp, 1.0)  # the starter map preview renders in the background
                picture = out / "map_preview.png"
                window.current_page.preview.grab().save(str(picture))
                written.append(picture)
                written.append(_areas_picture(window.current_page.starter_box, out, qapp))
                written.append(_world_picture(out, qapp))
                written.extend(_kind_pictures(out, qapp))
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
            quests = _quests_picture(godot, window.state.target, out)
            if quests is not None:  # Godot needs a window for it: not on a machine without one
                written.append(quests)
            written.extend(_game_pictures(godot, tmp_path, out))

        # the Results page after a failed run: the cause, the end of the log and the buttons
        finished = window.state.run_result
        window.state.run_result = failed_result(tmp_path / "failed_demo", window.state.target)
        window.show_page(len(window.pages) - 1)
        grab("results_failed")
        window.state.run_result = finished

        def grab_dialog(widget, name: str, seconds: float = 0.3) -> None:  # type: ignore[no-untyped-def]
            widget.show()
            _pump(qapp, seconds)
            path = out / f"{name}.png"
            widget.grab().save(str(path))
            written.append(path)
            widget.close()

        grab_dialog(AboutDialog(window), "about_dialog")
        grab_dialog(_variant_dialog(window), "variant_dialog")
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
    parser.add_argument("--size", default="1100x720", help="the window, as WIDTHxHEIGHT")
    parser.add_argument("--font", default=None, help="a font family for every text")
    args = parser.parse_args(argv)
    width, _, height = args.size.partition("x")
    exe = args.godot or (
        Path(os.environ["RPGGEN_GODOT"]) if os.environ.get("RPGGEN_GODOT") else None
    )
    for path in render(args.out, exe, (int(width), int(height)), args.font):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
