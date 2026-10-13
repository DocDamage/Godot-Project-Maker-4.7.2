"""The Project page's decisions without Qt (T12.25)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from rpggen.core import config as config_mod
from rpggen.core import godot, pack_sniff
from rpggen.errors import Issue, Severity
from rpggen.gui.models import project_model as pm
from rpggen.gui.models.forms import FieldStatus
from rpggen.gui.state import WizardState


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _inputs(tmp_path: Path, **changes) -> pm.Inputs:
    values = {
        "sources": [tmp_path / "pack"],
        "target": tmp_path / "out",
        "godot": tmp_path / "godot.exe",
        "name": "My Game",
    }
    values.update(changes)
    return pm.Inputs(**values)


def _checked(model: pm.ProjectModel, inputs: pm.Inputs, check: pm.InputCheck) -> None:
    assert model.finish_check(model.begin_check(), inputs.key(), check)


def test_the_models_import_nothing_from_qt() -> None:
    code = (
        "import sys, rpggen.gui.models.project_model, rpggen.gui.models.options_model; "
        "sys.exit(any(m.startswith('PySide6') for m in sys.modules))"
    )
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


def test_prefill_name_size_and_sample_folder(tmp_path) -> None:
    assert pm.prefill_name(Path("cool_tiles-v2")) == "Cool Tiles V2"
    assert pm.prefill_name(Path('<>:"')) == "My Game"
    assert pm.format_size(512) == "512 B"
    assert pm.format_size(2048) == "2.0 KB"
    assert pm.format_size(None) == ""
    (tmp_path / "rpggen-sample-1").mkdir()
    assert pm.sample_target(tmp_path) == tmp_path / "rpggen-sample-2"


def test_new_sources_skip_plain_files_and_known_packs(tmp_path) -> None:
    folder = tmp_path / "Pack"
    folder.mkdir()
    archive = tmp_path / "more.zip"
    archive.write_bytes(b"x")
    text = tmp_path / "notes.txt"
    text.write_text("x")
    model = pm.ProjectModel()
    assert model.new_sources([], [text]) == []
    assert not model.touched["packs"]
    found = model.new_sources([tmp_path / "pack"], [folder, archive, archive])
    assert found == [archive]  # "Pack" is listed already (paths compare without case)
    assert model.touched["packs"]


def test_suggestions_stop_once_the_user_typed(tmp_path) -> None:
    model = pm.ProjectModel()
    docs = tmp_path / "Documents"
    name, folder = model.suggestions([Path("forest_pack")], "", "", docs)
    assert name == "Forest Pack"
    assert folder == str(docs / "rpggen" / "Forest Pack")
    # a second pack does not replace the suggestion the user kept
    assert model.suggestions([Path("other")], name, folder, docs) == (
        "Other",
        str(docs / "rpggen" / "Other"),
    )
    model.name_typed()
    model.target_typed()
    assert model.suggestions([Path("third")], "Mine", "C:/mine", docs) == (None, None)
    assert model.suggestions([], "", "", docs) == (None, None)


def test_field_lines_start_as_hints_and_turn_red_once_touched(tmp_path) -> None:
    model = pm.ProjectModel()
    empty = pm.Inputs([], None, None, "")
    for status in (
        model.packs_status(empty),
        model.target_status(empty),
        model.godot_status(empty),
        model.name_status(""),
    ):
        assert status.state == "hint"
    model.touch_all()
    assert model.packs_status(empty).state == "error"
    assert model.target_status(empty) == FieldStatus("Choose an output folder.", "error")
    assert model.godot_status(empty).text == "Select a Godot 4.7.x executable."
    assert model.name_status("") == FieldStatus("The name needs 1 to 64 characters.", "error")
    assert model.name_status("x" * 65).state == "error"
    assert model.name_status("Fine") == FieldStatus("Name is fine.", "ok")


def test_lines_wait_for_the_check_of_the_current_inputs(tmp_path) -> None:
    model = pm.ProjectModel()
    inputs = _inputs(tmp_path)
    assert model.godot_status(inputs) == FieldStatus("Checking…")
    assert model.target_status(inputs) == FieldStatus("Checking…")
    _checked(model, inputs, pm.InputCheck(godot_version="4.7.2.stable"))
    assert model.godot_status(inputs) == FieldStatus("Godot 4.7.2.stable", "ok")
    assert model.packs_status(inputs) == FieldStatus("1 pack(s) ready.", "ok")
    # another folder: the check of the old inputs no longer counts
    assert model.target_status(_inputs(tmp_path, target=tmp_path / "x")).text == "Checking…"


def test_a_superseded_check_is_ignored(tmp_path) -> None:
    model = pm.ProjectModel()
    inputs = _inputs(tmp_path)
    old = model.begin_check()
    model.begin_check()
    assert not model.finish_check(old, inputs.key(), pm.InputCheck())
    assert model.current_check(inputs) is None


def test_validate_names_every_missing_field_then_waits_for_the_check(tmp_path) -> None:
    model = pm.ProjectModel()
    messages = [i.message for i in model.validate(pm.Inputs([], None, None, ""))]
    assert messages == [
        "Add at least one asset pack.",
        "Choose an output folder.",
        "Select a Godot 4.7.x executable.",
        "The name needs 1 to 64 characters.",
    ]
    inputs = _inputs(tmp_path)
    assert [i.message for i in model.validate(inputs)] == ["Checking your choices…"]
    bad = Issue("ENV-002", Severity.ERROR, "Godot 4.2 is not supported.", "")
    warn = Issue("PRE-001", Severity.WARNING, "Low disk space.", "")
    _checked(model, inputs, pm.InputCheck(godot=[bad], target=[warn]))
    assert model.validate(inputs) == [bad]
    assert model.offers_download(inputs)
    assert model.godot_status(inputs).state == "error"
    assert model.target_status(inputs) == FieldStatus("Low disk space.", "warning")


def test_pack_cards_show_format_and_licence_or_the_archive_problem(tmp_path) -> None:
    model = pm.ProjectModel()
    path = str(tmp_path / "pack")
    assert model.card_for(path, None)["detail"] == path
    sniffed = pack_sniff.PackSniff(format="rpgmaker", tile_size=48, has_license=False)
    check = pm.InputCheck(
        pack_info={path: ("folder", 12, 2048)}, pack_sniff={path: sniffed}, pack_issues={}
    )
    card = model.card_for(path, check)
    assert card["detail"] == "folder · 12 files · 2.0 KB"
    assert card["chips"] == [("RPG Maker · 48 px", "format"), ("No licence file", "warn")]
    assert model.row_text(path, check) == (f"{path}   ·   folder · 12 files · 2.0 KB", path)
    broken = Issue("ARCH-003", Severity.ERROR, "The archive is damaged.", "Download it again.")
    check.pack_issues[path] = [broken]
    assert model.card_for(path, check)["error"] == "The archive is damaged."
    text, tooltip = model.row_text(path, check)
    assert text.startswith("⚠ ") and tooltip == "The archive is damaged. Download it again."


def test_check_inputs_reports_the_godot_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(godot, "detect_version", lambda p: (4, 7, 2, "stable"))
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "a.png").write_bytes(b"x")
    found = pm.check_inputs(tmp_path / "godot.exe", None, [pack])
    assert found.godot_version == "4.7.2.stable"
    assert str(pack) in found.pack_info and str(pack) in found.pack_sniff


def test_godot_choices(tmp_path, monkeypatch) -> None:
    found = tmp_path / "found.exe"
    saved = tmp_path / "saved.exe"
    saved.write_text("x")
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [found])
    assert pm.godot_choices(tmp_path / "state.exe", "") == (
        [str(tmp_path / "state.exe"), str(found)],
        str(tmp_path / "state.exe"),
    )
    assert pm.godot_choices(None, str(saved)) == ([str(saved), str(found)], str(saved))
    assert pm.godot_choices(None, "") == ([str(found)], None)
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [])
    assert pm.godot_choices(None, "") == ([], "")


def test_store_keeps_only_updates_of_listed_packs(tmp_path) -> None:
    model = pm.ProjectModel()
    diff = SimpleNamespace(changed_paths=lambda: ["a.png"], renamed=["b.png"])
    model.record_update(tmp_path / "new.zip", "forest", diff)  # type: ignore[arg-type]
    state = WizardState()
    model.store(state, _inputs(tmp_path, sources=[tmp_path / "new.zip"]))
    assert state.pack_updates == {str(tmp_path / "new.zip"): "forest"}
    assert state.changed_paths == {"assets/packs/forest/a.png", "assets/packs/forest/b.png"}
    model.store(state, _inputs(tmp_path))
    assert state.pack_updates == {} and state.changed_paths == set()


def test_config_with_packs_keeps_ids_and_the_updated_pack_id(tmp_path) -> None:
    kept = config_mod.PackRef("forest", str(tmp_path / "forest"), "aa", "folder")
    old = config_mod.PackRef("town", str(tmp_path / "town.zip"), "bb", "zip")
    state = WizardState(config=config_mod.default_for("T", [kept, old]))
    (tmp_path / "town-v2.zip").write_bytes(b"zip")
    (tmp_path / "caves").mkdir()
    state.pack_sources = [tmp_path / "forest", tmp_path / "town-v2.zip", tmp_path / "caves"]
    state.pack_updates = {str(tmp_path / "town-v2.zip"): "town"}
    state.opened_packs = [  # type: ignore[list-item]
        SimpleNamespace(source_sha256="aa"),
        SimpleNamespace(source_sha256="cc"),
        SimpleNamespace(source_sha256="dd"),
    ]
    refs = pm.config_with_packs(state).packs
    assert [(r.pack_id, r.source_sha256) for r in refs] == [
        ("forest", "aa"),
        ("town", "cc"),
        ("caves", "dd"),
    ]


def test_analysed_hash_prefers_the_opened_pack(tmp_path) -> None:
    state = WizardState()
    state.opened_packs = [SimpleNamespace(source_sha256="")]  # type: ignore[list-item]
    state.inventories = [SimpleNamespace(source_sha256="inv")]  # type: ignore[list-item]
    assert pm.analysed_hash(state, 0) == "inv"
    assert pm.analysed_hash(state, 1) is None


def test_needs_analysis(tmp_path) -> None:
    state = WizardState()
    assert pm.needs_analysis(state, ("a",), None)
    state.catalog = object()  # type: ignore[assignment]
    state.analyzed_key = ("a",)
    assert not pm.needs_analysis(state, ("a",), None)
    assert pm.needs_analysis(state, ("a",), object())  # a resumed draft is analysed again


def test_a_sample_does_not_take_the_folder_of_another_samples_saved_work(
    tmp_path, monkeypatch
) -> None:
    """T17.17 saw it: every sample went to the first free folder, a sample that was tried and
    not generated left a draft for it, and the next sample was asked *Resume previous
    session?* for the first one's work."""
    from rpggen import paths
    from rpggen.gui import state as state_mod

    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "data")
    docs = tmp_path / "Documents"
    docs.mkdir()
    farm, iso = tmp_path / "sample_pack_farm", tmp_path / "sample_pack_iso"
    first = pm.sample_target(docs, [farm])
    assert first == docs / "rpggen-sample-1"
    state = state_mod.WizardState()
    state.target, state.pack_sources, state.project_name = first, [farm], "Green acre"
    state_mod.save_draft(state)
    assert pm.sample_target(docs, [iso]) == docs / "rpggen-sample-2", "another sample's work"
    assert pm.sample_target(docs, [farm]) == first, "its own work is offered again"
    assert pm.sample_target(docs) == first, "asked without a sample, it is the first free folder"
