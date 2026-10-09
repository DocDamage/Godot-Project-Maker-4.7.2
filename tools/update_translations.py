"""Extract and compile the wizard's translations (T12.56).

    python tools/update_translations.py extract [--lang fr]   # update the .ts files
    python tools/update_translations.py release               # build the .qm files

``extract`` runs ``pyside6-lupdate`` over the wizard's Python files and writes
``rpggen/gui/i18n/rpggen_<lang>.ts`` for every language that has one (``--lang`` starts a new
one). Line numbers are left out so that a moved line does not change the file. ``release`` runs
``pyside6-lrelease`` on each ``.ts`` and writes the ``.qm`` next to it; the release build calls
it, and ``.qm`` files are not committed. See CONTRIBUTING.md, "Translating the wizard".
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUI = REPO / "rpggen" / "gui"
I18N = GUI / "i18n"
PREFIX = "rpggen_"


def tool(name: str) -> str:
    """``pyside6-<name>`` next to this Python, on PATH, or the binary inside the PySide6 package."""
    scripts = Path(sys.executable).parent
    for candidate in (scripts / f"pyside6-{name}.exe", scripts / f"pyside6-{name}"):
        if candidate.is_file():
            return str(candidate)
    found = shutil.which(f"pyside6-{name}")
    if found:
        return found
    import PySide6

    package = Path(PySide6.__file__).parent
    for candidate in (package / f"{name}.exe", package / name, package / "Qt" / "libexec" / name):
        if candidate.is_file():
            return str(candidate)
    raise SystemExit(f"pyside6-{name} was not found (it comes with PySide6)")


def sources() -> list[str]:
    return sorted(str(p.relative_to(REPO)) for p in GUI.rglob("*.py"))


def ts_files() -> list[Path]:
    return sorted(I18N.glob(f"{PREFIX}*.ts"))


def extract(new_lang: str | None = None) -> list[Path]:
    I18N.mkdir(exist_ok=True)
    targets = ts_files()
    if new_lang:
        new = I18N / f"{PREFIX}{new_lang}.ts"
        if new not in targets:
            targets.append(new)
    if not targets:
        raise SystemExit("no translation yet: start one with --lang <code>, e.g. --lang fr")
    for ts in targets:
        command = [tool("lupdate"), "-no-obsolete", "-locations", "none", *sources()]
        command += ["-ts", str(ts.relative_to(REPO))]
        subprocess.run(command, cwd=REPO, check=True)
    return targets


def release(folder: Path = I18N) -> list[Path]:
    """Compile every .ts of ``folder``; returns the .qm files."""
    out: list[Path] = []
    for ts in sorted(folder.glob(f"{PREFIX}*.ts")):
        qm = ts.with_suffix(".qm")
        subprocess.run([tool("lrelease"), str(ts), "-qm", str(qm)], check=True)
        out.append(qm)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    ext = sub.add_parser("extract", help="update the .ts files from the source")
    ext.add_argument("--lang", help="start a translation for this language code (fr, pt_BR)")
    sub.add_parser("release", help="compile the .ts files to .qm")
    args = parser.parse_args(argv)
    if args.command == "extract":
        for ts in extract(args.lang):
            print("updated", ts.relative_to(REPO))
    else:
        for qm in release():
            print("built", qm.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
