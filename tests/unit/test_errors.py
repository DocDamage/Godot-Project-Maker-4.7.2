from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from rpggen import errors, jsonio, schema
from rpggen.errors import CODES, IssueList, RpgGenError, Severity

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs" / "spec" / "03_ERROR_CODES.md"


def test_every_spec_code_present() -> None:
    codes = re.findall(r"^\| ([A-Z]+-\d{3}) \|", SPEC.read_text(encoding="utf-8"), re.M)
    assert len(codes) > 70
    assert sorted(codes) == sorted(CODES)


def test_severities_parsed() -> None:
    assert CODES["ENV-001"].severity == "error"
    assert CODES["ENV-003"].severity == "warning"
    assert CODES["ENV-010"].severity == "info"


def test_unknown_code_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        RpgGenError("NOPE-001", "x")
    with pytest.raises(KeyError):
        IssueList().add("NOPE-001", "x")


def test_missing_detail_key_keeps_placeholder() -> None:
    err = RpgGenError("ENV-001")
    assert err.issue.message == "Godot executable not found at {path}."
    err = RpgGenError("ENV-001", path="C:/g.exe")
    assert err.issue.message == "Godot executable not found at C:/g.exe."


def test_file_is_available_to_template() -> None:
    err = RpgGenError("VAL-001", file="game/x.gd")
    assert "game/x.gd" in err.issue.message
    assert err.issue.file == "game/x.gd"


def test_error_issue_fields() -> None:
    err = RpgGenError("CAT-002", "custom text", file="a.json", reason="r")
    assert err.issue.code == "CAT-002"
    assert err.issue.severity is Severity.ERROR
    assert err.issue.message == "custom text"
    assert err.issue.fix == CODES["CAT-002"].fix
    assert err.issue.detail == {"reason": "r"}
    assert "CAT-002" in str(err)


def test_issue_list_sorting_and_errors() -> None:
    issues = IssueList()
    issues.add("ENV-010")
    issues.add("ENV-003", found="4.7.1")
    assert not issues.has_errors()
    issues.add("BUILD-001", code=1)
    issues.add("ARCH-001", file="b", path="p", reason="r")
    issues.add("ARCH-001", file="a", path="p", reason="r")
    assert issues.has_errors()
    out = issues.to_json()
    assert [i["code"] for i in out] == ["ARCH-001", "ARCH-001", "BUILD-001", "ENV-003", "ENV-010"]
    assert [i.get("file") for i in out[:2]] == ["a", "b"]
    assert all(set(i) >= {"code", "severity", "message", "fix"} for i in out)


def test_generator_is_deterministic(tmp_path: Path) -> None:
    targets = [
        REPO / "rpggen" / "errors_table.py",
        REPO / "godot_templates" / "builder" / "lib" / "error_codes.gd",
        REPO / "docs" / "errors.md",
    ]
    before = [t.read_bytes() for t in targets]
    for _ in range(2):
        subprocess.run([sys.executable, str(REPO / "tools" / "gen_error_codes.py")], check=True)
    assert [t.read_bytes() for t in targets] == before


def test_generated_header() -> None:
    first = (REPO / "rpggen" / "errors_table.py").read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("# GENERATED — do not edit")


def test_jsonio_and_schema_raise_coded_errors(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(RpgGenError) as ei:
        jsonio.read(bad)
    assert ei.value.code == "CAT-001"
    with pytest.raises(RpgGenError) as ei:
        schema.validate("results", {})
    assert ei.value.code == "CAT-002"


def test_module_exports() -> None:
    assert errors.CodeInfo is not None
