from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import catalog, profiles
from rpggen.gui import workers
from rpggen.gui.dialogs.profile_dialogs import ExportProfileDialog
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _state(pack: str = "basic16") -> WizardState:
    from rpggen.core.orchestrator import Callbacks

    state = WizardState(pack_sources=[SYNTH / pack], target=None)
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    return state


def _page(qtbot, state: WizardState) -> AuditPage:
    page = AuditPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page


def _sync_analysis(page: AuditPage) -> None:
    from rpggen.core.orchestrator import Callbacks

    def run(state: WizardState) -> bool:
        workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
        return True

    page.run_analysis = run  # type: ignore[method-assign]


def test_export_dialog_defaults_and_validation(qtbot) -> None:
    dialog = ExportProfileDialog(["a", "b"], "Pack A")
    qtbot.addWidget(dialog)
    assert dialog.meta() == {"title": "Pack A", "author": "", "license": "CC0-1.0"}
    assert dialog.ok_button.isEnabled()
    dialog.title_edit.setText("  ")
    assert not dialog.ok_button.isEnabled()
    dialog.author_edit.setText("me")
    dialog.license_edit.setText("")
    assert dialog.meta()["license"] == "CC0-1.0" and dialog.meta()["author"] == "me"


def test_menu_has_export_and_import(qtbot) -> None:
    page = _page(qtbot, _state())
    assert page.export_action.text().startswith("Export pack profile")
    assert page.import_action.text().startswith("Import profile")


def test_export_then_import_into_a_fresh_session(qtbot, tmp_path: Path) -> None:
    state = _state()
    page = _page(qtbot, state)
    hero = next(a.id for a in state.catalog.assets if a.id.endswith("hero"))
    page.session.set_override(hero, "role", "NPC")

    def accept(dialog) -> bool:
        if isinstance(dialog, ExportProfileDialog):
            dialog.title_edit.setText("My Basic")
            dialog.author_edit.setText("tester")
        return True

    page.run_dialog = accept  # type: ignore[method-assign]
    out = tmp_path / "my.rpgprofile.json"
    page.choose_save_path = lambda name: out if name.startswith("my_basic") else None  # type: ignore[method-assign]
    assert page.export_profile() == out
    data = profiles.load_profile(out)
    assert data["title"] == "My Basic" and data["author"] == "tester"
    assert data["license"] == "CC0-1.0"

    # a fresh state knows nothing; importing the file brings the decision back
    fresh = _state()
    fresh_page = _page(qtbot, fresh)
    assert catalog.effective(fresh.catalog.asset(hero))["role"] != "NPC"
    fresh_page.choose_open_path = lambda: out  # type: ignore[method-assign]
    _sync_analysis(fresh_page)
    assert fresh_page.import_profile()
    assert catalog.effective(fresh.catalog.asset(hero))["role"] == "NPC"
    assert fresh_page.session.catalog is fresh.catalog


def test_import_keeps_the_users_existing_edits(qtbot, tmp_path: Path) -> None:
    state = _state()
    page = _page(qtbot, state)
    hero = next(a.id for a in state.catalog.assets if a.id.endswith("hero"))
    page.session.set_override(hero, "role", "NPC")
    page.run_dialog = lambda dialog: True  # type: ignore[method-assign]
    out = tmp_path / "p.rpgprofile.json"
    page.choose_save_path = lambda name: out  # type: ignore[method-assign]
    page.export_profile()

    other = _state()
    other_page = _page(qtbot, other)
    terrain = next(a.id for a in other.catalog.assets if a.id.endswith("terrain"))
    other_page.session.set_override(terrain, "role", "WALL")
    other_page.choose_open_path = lambda: out  # type: ignore[method-assign]
    _sync_analysis(other_page)
    assert other_page.import_profile()
    assert catalog.effective(other.catalog.asset(terrain))["role"] == "WALL"  # own edit kept
    assert catalog.effective(other.catalog.asset(hero))["role"] == "NPC"  # profile applied


def test_importing_a_bad_file_reports_and_changes_nothing(qtbot, tmp_path: Path) -> None:
    state = _state()
    page = _page(qtbot, state)
    bad = tmp_path / "bad.rpgprofile.json"
    bad.write_text('{"profile_version": 1}', encoding="utf-8")
    messages: list[str] = []
    page.show_error = lambda title, message: messages.append(title)  # type: ignore[method-assign]
    page.choose_open_path = lambda: bad  # type: ignore[method-assign]
    before = state.catalog
    assert not page.import_profile()
    assert messages and state.catalog is before
    assert profiles.installed() == []


def test_cancelled_dialogs_do_nothing(qtbot, tmp_path: Path) -> None:
    page = _page(qtbot, _state())
    page.run_dialog = lambda dialog: False  # type: ignore[method-assign]
    assert page.export_profile() is None
    page.run_dialog = lambda dialog: True  # type: ignore[method-assign]
    page.choose_save_path = lambda name: None  # type: ignore[method-assign]
    assert page.export_profile() is None
    page.choose_open_path = lambda: None  # type: ignore[method-assign]
    assert not page.import_profile()
