"""The wizard's translations (T12.56).

The texts of the wizard go through ``tr()``. ``tools/update_translations.py`` extracts them with
``pyside6-lupdate`` into ``rpggen/gui/i18n/rpggen_<lang>.ts`` (what translators edit) and compiles
those with ``pyside6-lrelease`` into ``rpggen_<lang>.qm`` (built, not committed; the release
build runs it). At start-up ``install`` loads the ``.qm`` of the language chosen in the settings,
or of the first of the system's UI languages that has one, plus Qt's own ``qtbase`` translation
for the standard dialogs. A text without a translation stays English; so do the error messages,
which are documented by code.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator

log = logging.getLogger(__name__)

I18N_DIR = Path(__file__).resolve().parent / "i18n"
PREFIX = "rpggen_"
SYSTEM = ""  # the setting that follows the operating system

_installed: list[QTranslator] = []


def available(folder: Path = I18N_DIR) -> list[str]:
    """The languages that have a compiled translation, sorted ("fr", "pt_BR")."""
    if not folder.is_dir():
        return []
    return sorted(p.stem[len(PREFIX) :] for p in folder.glob(f"{PREFIX}*.qm"))


def choose(setting: str, ui_languages: list[str], languages: list[str]) -> str | None:
    """The language to load: the setting when it has a translation, else the first system UI
    language that has one ("pt-BR" matches "pt_BR", then "pt"); None means English."""
    wanted = [setting] if setting else [lang.replace("-", "_") for lang in ui_languages]
    for lang in wanted:
        for candidate in (lang, lang.split("_")[0]):
            if candidate in languages:
                return candidate
    return None


def display_name(language: str) -> str:
    """The language's own name ("français"), for the menu."""
    name = QLocale(language).nativeLanguageName()
    return name or language


def install(setting: str = SYSTEM, folder: Path = I18N_DIR) -> str | None:
    """Replace the wizard's translators with those of ``setting`` (or the system's language).
    Returns the language loaded, or None for English. Call before the widgets are made: texts
    are set once, when a widget is created."""
    app = QCoreApplication.instance()
    if app is None:
        return None
    for old in _installed:
        app.removeTranslator(old)
    _installed.clear()
    language = choose(setting, QLocale.system().uiLanguages(), available(folder))
    if language is None:
        return None
    ours = QTranslator(app)
    if not ours.load(str(folder / f"{PREFIX}{language}.qm")):
        log.warning("could not load the %s translation of the wizard", language)
        return None
    app.installTranslator(ours)
    _installed.append(ours)
    qt = QTranslator(app)  # the buttons of Qt's own dialogs (OK, Cancel, Yes, No)
    if qt.load(f"qtbase_{language}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(qt)
        _installed.append(qt)
    log.info("wizard language: %s", language)
    return language
