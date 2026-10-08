"""T12.58: the resolver of .rpggen-new conflicts."""

from __future__ import annotations

import itertools
import subprocess
from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import conflicts, ledger, promote, vcs
from rpggen.core.conflicts import Action
from rpggen.core.ledger import Ledger
from rpggen.core.staging import Staging
from rpggen.errors import RpgGenError

FILE = "generated/scenes/sign.tscn"
V1 = "[gd_scene]\nline a\nline b\nline c\n"
_runs = itertools.count()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _first_generation(target: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        _write(target, rel, text)
    ledger.scan(target).save(target / paths.LEDGER)


def _regenerate(target: Path, files: dict[str, str]) -> promote.PromotionResult:
    stg = target.parent / f"staging{next(_runs)}"
    for rel, text in files.items():
        _write(stg, rel, text)
    return promote.promote(Staging(target, stg, "regenerate"))


def _codes(result: promote.PromotionResult) -> list[str]:
    return [i.code for i in result.issues]


@pytest.fixture
def target(tmp_path: Path) -> Path:
    t = tmp_path / "game"
    _first_generation(t, {FILE: V1})
    return t


def _conflict(target: Path, mine: str, new: str) -> None:
    """The user edits FILE, then a regeneration produces ``new``: a conflict."""
    _write(target, FILE, mine)
    result = _regenerate(target, {FILE: new})
    assert _codes(result) == ["REGEN-001"]
    assert conflicts.list_conflicts(target) == [FILE]


# --------------------------------------------------------------------------- the spec's tests


def test_after_take_new_the_next_regeneration_overwrites_freely(target: Path) -> None:
    _conflict(target, "mine\n", "v2\n")
    done = conflicts.resolve(target, FILE, Action.TAKE_NEW)
    assert (target / FILE).read_text(encoding="utf-8") == "v2\n"
    assert conflicts.list_conflicts(target) == []
    assert (done.backup / FILE).read_text(encoding="utf-8") == "mine\n"  # backed up first
    result = _regenerate(target, {FILE: "v3\n"})
    assert _codes(result) == [] and result.plan.write == [FILE]
    assert (target / FILE).read_text(encoding="utf-8") == "v3\n"


def test_keep_mine_suppresses_the_conflict_until_the_generated_content_changes(
    target: Path,
) -> None:
    _conflict(target, "mine\n", "v2\n")
    conflicts.resolve(target, FILE, Action.KEEP_MINE)
    assert (target / FILE).read_text(encoding="utf-8") == "mine\n"
    assert not (target / (FILE + ".rpggen-new")).exists()
    entry = Ledger.load(target / paths.LEDGER).files[FILE]
    assert entry.declined_sha256 == ledger.hash_bytes(b"v2\n", FILE)
    again = _regenerate(target, {FILE: "v2\n"})  # the same generated content: no conflict
    assert _codes(again) == [] and FILE not in again.plan.write
    assert conflicts.list_conflicts(target) == []
    assert (target / FILE).read_text(encoding="utf-8") == "mine\n"
    changed = _regenerate(target, {FILE: "v3\n"})  # new generated content: asked again
    assert _codes(changed) == ["REGEN-001"]
    assert (target / (FILE + ".rpggen-new")).read_text(encoding="utf-8") == "v3\n"


def test_a_merge_without_a_base_produces_markers(target: Path) -> None:
    _conflict(target, "[gd_scene]\nmine\n", "[gd_scene]\nnew\n")
    done = conflicts.resolve(target, FILE, Action.MERGE)
    text = (target / FILE).read_text(encoding="utf-8")
    assert text == ("[gd_scene]\n<<<<<<< yours\nmine\n=======\nnew\n>>>>>>> rpggen\n")
    assert done.conflicts == 1 and done.check_in_godot  # a .tscn: validate it in Godot
    # merged: the new version is the base now, and the same content is not offered again
    assert _codes(_regenerate(target, {FILE: "[gd_scene]\nnew\n"})) == []


# --------------------------------------------------------------------------- the base


def test_the_base_comes_from_a_backup_after_a_resolution(target: Path) -> None:
    _conflict(target, V1.replace("line a", "line A"), V1.replace("line c", "line C"))
    conflicts.resolve(target, FILE, Action.TAKE_NEW)  # the backup now holds the new version
    v2 = V1.replace("line c", "line C")
    _conflict(target, v2.replace("line a", "MY a"), v2.replace("line C", "NEW C"))
    found = conflicts.versions(target, FILE)
    assert found.base == v2.encode()
    done = conflicts.resolve(target, FILE, Action.MERGE)
    assert done.conflicts == 0  # lines apart: a clean three-way merge
    assert (target / FILE).read_text(encoding="utf-8") == "[gd_scene]\nMY a\nline b\nNEW C\n"


@pytest.mark.skipif(not vcs.git_available(), reason="git is not installed")
def test_the_base_comes_from_git_on_a_first_conflict(target: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=target,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "generation 1")
    _conflict(target, V1.replace("line a", "MY a"), V1.replace("line c", "NEW c"))
    assert conflicts.versions(target, FILE).base == V1.encode()
    assert conflicts.resolve(target, FILE, Action.MERGE).conflicts == 0
    assert (target / FILE).read_text(encoding="utf-8") == "[gd_scene]\nMY a\nline b\nNEW c\n"


def test_without_a_base_there_are_two_versions(target: Path) -> None:
    _conflict(target, "mine\n", "v2\n")
    found = conflicts.versions(target, FILE)
    assert found.base is None and found.mine == b"mine\n" and found.new == b"v2\n"


# --------------------------------------------------------------------------- the merge itself


def _lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def test_merge3_takes_each_sides_changes_and_marks_overlaps() -> None:
    base = _lines("a\nb\nc\nd\n")
    merged, n = conflicts.merge3(base, _lines("A\nb\nc\nd\n"), _lines("a\nb\nc\nD\n"))
    assert "".join(merged) == "A\nb\nc\nD\n" and n == 0
    merged, n = conflicts.merge3(base, _lines("a\nX\nc\nd\n"), _lines("a\nY\nc\nd\n"))
    assert n == 1
    assert "".join(merged) == (
        "a\n<<<<<<< yours\nX\n||||||| last generated\nb\n=======\nY\n>>>>>>> rpggen\nc\nd\n"
    )
    merged, n = conflicts.merge3(base, _lines("a\nZ\nc\nd\n"), _lines("a\nZ\nc\nd\n"))
    assert "".join(merged) == "a\nZ\nc\nd\n" and n == 0  # the same change once
    merged, n = conflicts.merge3(base, _lines("a\nb\nc\nd\ne\n"), _lines("a\nc\nd\n"))
    assert "".join(merged) == "a\nc\nd\ne\n" and n == 0  # an insertion and a deletion


def test_a_merge_keeps_the_users_line_endings_and_closes_the_last_line() -> None:
    merged, n = conflicts.merge_text(b"a\nb\nc\n", b"A\r\nb\r\nc\r\n", b"a\nb\nc\nd\n")
    assert merged == b"A\r\nb\r\nc\r\nd\r\n" and n == 0
    # changes on neighbouring lines overlap, as in diff3 and git
    assert conflicts.merge_text(b"a\nb\n", b"a\nB\n", b"a\nb\nc\n")[1] == 1
    merged, n = conflicts.merge_text(None, b"x", b"y")
    assert merged == b"<<<<<<< yours\nx\n=======\ny\n>>>>>>> rpggen\n" and n == 1


# --------------------------------------------------------------------------- safety


def test_resolving_a_file_without_a_new_version_is_regen_009(target: Path) -> None:
    with pytest.raises(RpgGenError) as raised:
        conflicts.resolve(target, FILE, Action.TAKE_NEW)
    assert raised.value.code == "REGEN-009"


def test_binary_files_cannot_be_merged(tmp_path: Path) -> None:
    t = tmp_path / "game"
    rel = "generated/art/tile.png"
    _first_generation(t, {rel: "PNG1"})
    _write(t, rel, "PNG-mine")
    _regenerate(t, {rel: "PNG2"})
    with pytest.raises(RpgGenError) as raised:
        conflicts.resolve(t, rel, Action.MERGE)
    assert raised.value.code == "REGEN-010"
    assert conflicts.list_conflicts(t) == [rel]  # nothing changed
    conflicts.resolve(t, rel, "take_new")
    assert (t / rel).read_text(encoding="utf-8") == "PNG2"


def test_restore_previous_undoes_a_resolution(target: Path) -> None:
    _conflict(target, "mine\n", "v2\n")
    conflicts.resolve(target, FILE, Action.TAKE_NEW)
    promote.restore(target)
    assert (target / FILE).read_text(encoding="utf-8") == "mine\n"
    assert conflicts.list_conflicts(target) == [FILE]
    entry = Ledger.load(target / paths.LEDGER).files[FILE]
    assert entry.sha256 == ledger.hash_bytes(V1.encode(), FILE)


def test_backups_and_staging_folders_are_not_listed(target: Path) -> None:
    _conflict(target, "mine\n", "v2\n")
    conflicts.resolve(target, FILE, Action.KEEP_MINE)  # its backup holds a .rpggen-new
    assert any(p.name.endswith(".rpggen-new") for p in (target / ".rpggen_backups").rglob("*"))
    assert conflicts.list_conflicts(target) == []


def test_the_ledger_round_trips_the_declined_hash() -> None:
    entry = ledger.LedgerEntry("a" * 64, "r", "generated", "b" * 64)
    data = Ledger({"x.gd": entry}).to_json()
    assert data["files"]["x.gd"]["declined_sha256"] == "b" * 64
    assert Ledger.from_json(data).files["x.gd"] == entry
    plain = Ledger({"x.gd": ledger.LedgerEntry("a" * 64, "r", "generated")}).to_json()
    assert "declined_sha256" not in plain["files"]["x.gd"]  # optional, omitted when unset


# --------------------------------------------------------------------------- CLI


def test_cli_lists_and_resolves(target: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import json

    from rpggen import cli

    _conflict(target, "mine\n", "v2\n")
    assert cli.main(["conflicts", "--target", str(target), "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["command"] == "conflicts" and listed["files"] == [FILE]
    code = cli.main(["conflicts", "--target", str(target), "--keep-mine", FILE + ".rpggen-new"])
    assert code == 0 and "kept yours" in capsys.readouterr().out
    assert conflicts.list_conflicts(target) == []
    code = cli.main(["conflicts", "--target", str(target), "--take-new", FILE, "--json"])
    doc = json.loads(capsys.readouterr().out)
    assert code != 0 and doc["issues"][0]["code"] == "REGEN-009"  # nothing left to resolve


def test_cli_usage_errors(target: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from rpggen import cli

    assert cli.main(["conflicts", "--target", str(target), FILE]) == 2  # no action
    assert cli.main(["conflicts", "--target", str(target), "--merge"]) == 2  # no file
    with pytest.raises(SystemExit):
        cli.main(["conflicts", "--target", str(target), "--merge", "--take-new", FILE])
    capsys.readouterr()
