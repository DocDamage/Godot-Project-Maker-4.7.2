"""T12.56: the wizard's translations (QTranslator, the language setting, the pilot file)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from rpggen.core import app_settings
from rpggen.gui import translations

REPO = Path(__file__).resolve().parents[2]

TEST_TS = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="xx">
<context>
    <name>MainWindow</name>
    <message>
        <source>Project</source>
        <translation>Projekto</translation>
    </message>
</context>
</TS>
"""


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "update_translations", REPO / "tools" / "update_translations.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def english_again():
    yield
    translations.install("en")  # no translation for "en": the translators are removed


def _compiled(folder: Path, lang: str, ts_text: str) -> Path:
    (folder / f"rpggen_{lang}.ts").write_text(ts_text, encoding="utf-8")
    (qm,) = _tool().release(folder)
    return qm


def test_choose_follows_the_setting_then_the_system() -> None:
    langs = ["de", "fr", "pt_BR"]
    assert translations.choose("fr", ["de-DE"], langs) == "fr"  # the setting wins
    assert translations.choose("", ["it-IT", "pt-BR"], langs) == "pt_BR"  # the system's order
    assert translations.choose("", ["fr-CA"], langs) == "fr"  # a region falls back to its language
    assert translations.choose("", ["it-IT"], langs) is None  # nothing: English
    assert translations.choose("en", ["fr-FR"], langs) is None  # English chosen on purpose


def test_the_wizard_loads_a_qm_and_a_page_title_changes(
    qtbot, tmp_path: Path, english_again
) -> None:
    from rpggen.gui.wizard import MainWindow

    _compiled(tmp_path, "xx", TEST_TS)
    assert translations.available(tmp_path) == ["xx"]
    assert translations.install("xx", tmp_path) == "xx"
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.sidebar.item(0).text() == "1. Projekto"
    assert window.sidebar.item(1).text() == "2. Archetype"  # not translated: English
    translations.install("en")
    english = MainWindow()
    qtbot.addWidget(english)
    assert english.sidebar.item(0).text() == "1. Project"


def test_a_missing_or_broken_translation_leaves_english(tmp_path: Path, english_again) -> None:
    assert translations.install("xx", tmp_path) is None  # no .qm at all
    (tmp_path / "rpggen_xx.qm").write_bytes(b"not a qm file")
    assert translations.install("xx", tmp_path) is None


def test_the_french_pilot_compiles_and_names_the_steps(
    qtbot, tmp_path: Path, english_again
) -> None:
    from rpggen.gui.wizard import MainWindow

    source = REPO / "rpggen" / "gui" / "i18n" / "rpggen_fr.ts"
    _compiled(tmp_path, "fr", source.read_text(encoding="utf-8"))
    assert translations.install("fr", tmp_path) == "fr"
    window = MainWindow()
    qtbot.addWidget(window)
    names = [window.sidebar.item(i).text() for i in range(window.sidebar.count())]
    assert names[0] == "1. Projet" and names[5] == "6. Générer"


def test_the_language_setting_is_saved_and_checked(tmp_path: Path) -> None:
    data = app_settings.AppSettings(language="fr").to_json()
    assert data["language"] == "fr"
    assert app_settings.from_json(data).language == "fr"
    assert app_settings.from_json({"language": "../evil"}).language == ""  # not a language code
    assert app_settings.from_json({"language": 3}).language == ""


def test_the_language_menu_saves_the_choice_and_says_when_it_applies(qtbot, monkeypatch) -> None:
    from rpggen.gui.wizard import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    told: list[bool] = []
    window.tell_language_restart = lambda: told.append(True)  # type: ignore[method-assign]
    saved: dict[str, object] = {}
    monkeypatch.setattr(app_settings, "update", lambda **changes: saved.update(changes))
    assert "" in window.language_actions and "en" in window.language_actions
    window.language_actions["en"].trigger()
    assert saved == {"language": "en"} and told == [True]
    assert window.language_actions["en"].isChecked()
