"""Move rpggen to another Godot version in one step.

Usage:
    python tools/bump_godot.py 4.8.1        rewrite the version everywhere it is configured
    python tools/bump_godot.py --check      verify that nothing disagrees (CI runs this as a test)

Rewrites ``rpggen/godot_target.py`` (the single source: the app's gate, the Download Godot
button, the default of tools/fetch_godot.py), ``GODOT_VERSION`` in the CI and release workflows,
and the version in ``docs/spec/03_ERROR_CODES.md`` (then regenerates the error tables). It cannot
verify that the new Godot still behaves the same; the checklist it prints is the part for a
person.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "rpggen" / "godot_target.py"
WORKFLOWS = [
    REPO / ".github" / "workflows" / "ci.yml",
    REPO / ".github" / "workflows" / "release.yml",
]
ERROR_SPEC = REPO / "docs" / "spec" / "03_ERROR_CODES.md"
_VERSION_LINE = re.compile(r'^VERSION = "(\d+\.\d+\.\d+)"', re.M)
_ENV_LINE = re.compile(r'^(\s*GODOT_VERSION:\s*)"([^"]+)"', re.M)

CHECKLIST = """\
Still to do by hand (the tool cannot know whether Godot changed behaviour):
  1. Re-run the API probes in godot_templates/tests/probes with the new Godot and update
     docs/godot_api_verified.md (date and any difference).
  2. Run the whole suite with it:  RPGGEN_GODOT=<console exe> python -m pytest -q -m integration
     and the GDScript tests (godot_templates/tests/run_tests.gd).
  3. Regenerate goldens only if a diff is explained:  python -m rpggen.dev update-goldens
  4. Search the docs for the old version (README.md, docs/user_guide.md, docs/release.md,
     docs/coverage.md) and update the wording.
  5. Redo the manual rows of docs/spec/M11_pre_release.md T11.29 that touch the editor.
  6. If the new Godot's series differs (e.g. 4.7 -> 4.8), check godot_templates/project.godot
     and the 'config/features' line, and bump the runtime/app version if generated output changed.
"""


def current_version() -> str:
    match = _VERSION_LINE.search(TARGET.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"cannot find VERSION in {TARGET}")
    return match.group(1)


def check() -> list[str]:
    """Descriptions of every place that disagrees with ``godot_target.VERSION``."""
    version = current_version()
    problems: list[str] = []
    for path in WORKFLOWS:
        for match in _ENV_LINE.finditer(path.read_text(encoding="utf-8")):
            if match.group(2) != version:
                problems.append(f"{path.relative_to(REPO)}: GODOT_VERSION {match.group(2)}")
    spec = ERROR_SPEC.read_text(encoding="utf-8")
    if version not in spec:
        problems.append(f"{ERROR_SPEC.relative_to(REPO)} does not name {version}")
    return problems


def _rewrite(path: Path, fn) -> None:  # type: ignore[no-untyped-def]
    raw = path.read_bytes().decode("utf-8")
    new = fn(raw)
    if new != raw:
        path.write_bytes(new.encode("utf-8"))


def rewrite_spec(text: str, old: str, new: str) -> str:
    """Replace the full version, and the series ("4.7", "4.7.x") when it changes too."""
    text = text.replace(old, new)
    old_series = ".".join(old.split(".")[:2])
    new_series = ".".join(new.split(".")[:2])
    if old_series != new_series:
        text = re.sub(rf"(?<![\d.]){re.escape(old_series)}(?!\.?\d)", new_series, text)
    return text


def bump(new: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", new):
        raise SystemExit(f"not a version like 4.8.1: {new}")
    old = current_version()
    _rewrite(TARGET, lambda s: _VERSION_LINE.sub(f'VERSION = "{new}"', s))
    for path in WORKFLOWS:
        _rewrite(path, lambda s: _ENV_LINE.sub(lambda m: f'{m.group(1)}"{new}"', s))
    _rewrite(ERROR_SPEC, lambda s: rewrite_spec(s, old, new))
    subprocess.run([sys.executable, str(REPO / "tools" / "gen_error_codes.py")], check=True)
    print(f"Godot {old} -> {new}\n")
    print(CHECKLIST)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("version", nargs="?", help="the new Godot version, e.g. 4.8.1")
    parser.add_argument("--check", action="store_true", help="only verify consistency")
    args = parser.parse_args(argv)
    if args.check or not args.version:
        problems = check()
        for line in problems:
            print("mismatch:", line)
        if not problems:
            print(f"Godot {current_version()}: consistent")
        return 1 if problems else 0
    bump(args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
