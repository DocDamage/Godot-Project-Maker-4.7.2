"""Validate every profile of the registry and regenerate index.json.

Usage: python scripts/build_index.py [--check]

Run by .github/workflows/validate.yml. With --check the index is not written; the exit code is 1
when the committed index.json is out of date. The only third-party dependency is jsonschema.
Profiles are data: this script never executes anything from them.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "scripts" / "profile.schema.json"
SUFFIX = ".rpgprofile.json"
REQUIRED_LICENSE = "CC0-1.0"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_]{0,99}$")


def problems(path: Path, validator: Draft202012Validator) -> tuple[dict | None, list[str]]:
    """The parsed profile (None when unreadable) and every reason it must be rejected."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, [f"not valid JSON: {exc}"]
    errors = [
        f"schema: {e.message} at /{'/'.join(map(str, e.absolute_path))}"
        for e in validator.iter_errors(data)
    ]
    name = path.name[: -len(SUFFIX)]
    if not isinstance(data, dict):
        return None, errors or ["not an object"]
    if data.get("profile_id") != name:
        errors.append(f"profile_id {data.get('profile_id')!r} must equal the file name {name!r}")
    if not SAFE_ID.match(name):
        errors.append("the file name must be lowercase letters, digits and underscores")
    if data.get("license") != REQUIRED_LICENSE:
        errors.append(f"license must be {REQUIRED_LICENSE}")
    return data, errors


def build(root: Path = ROOT) -> tuple[list[dict], dict[str, list[str]]]:
    validator = Draft202012Validator(
        json.loads((root / "scripts" / "profile.schema.json").read_text("utf-8"))
    )
    index: list[dict] = []
    failed: dict[str, list[str]] = {}
    for path in sorted((root / "profiles").glob(f"*{SUFFIX}")):
        data, errors = problems(path, validator)
        if errors or data is None:
            failed[path.name] = errors
            continue
        index.append(
            {
                "profile_id": data["profile_id"],
                "title": data["title"],
                "fingerprint_hashes": sorted(set(data["fingerprint"]["required_files"].values())),
                "author": data.get("author", ""),
                "license": data["license"],
            }
        )
    return index, failed


def main(argv: list[str]) -> int:
    check = "--check" in argv
    index, failed = build()
    for name, errors in failed.items():
        for error in errors:
            print(f"{name}: {error}")
    if failed:
        return 1
    text = json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    target = ROOT / "index.json"
    if check:
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            print("index.json is out of date; run python scripts/build_index.py")
            return 1
        return 0
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"index.json: {len(index)} profile(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
