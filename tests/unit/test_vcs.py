from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rpggen.core import vcs

pytestmark = pytest.mark.skipif(not vcs.git_available(), reason="git is not installed")


def _isolate_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No global or system git configuration, so no identity is configured."""
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for name in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
    ):
        monkeypatch.delenv(name, raising=False)


def _git(folder: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=folder, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_init_and_commit_uses_the_fallback_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_git(tmp_path, monkeypatch)
    project = tmp_path / "game"
    project.mkdir()
    (project / "a.txt").write_text("hello\n", encoding="utf-8")
    assert vcs.init_and_commit(project, "first generation") is True
    assert (
        _git(project, "log", "-1", "--format=%an <%ae>|%s")
        == "rpggen <rpggen@localhost>|first generation"
    )
    assert vcs.is_clean(project)


def test_a_configured_identity_is_not_overridden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_git(tmp_path, monkeypatch)
    config = tmp_path / "empty.gitconfig"
    config.write_text("[user]\n\tname = Dana\n\temail = dana@example.com\n", encoding="utf-8")
    project = tmp_path / "game"
    project.mkdir()
    (project / "a.txt").write_text("hello\n", encoding="utf-8")
    assert vcs.init_and_commit(project, "m") is True
    assert _git(project, "log", "-1", "--format=%an") == "Dana"


def test_a_second_commit_only_records_changes_and_nothing_to_commit_is_fine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_git(tmp_path, monkeypatch)
    project = tmp_path / "game"
    project.mkdir()
    (project / "a.txt").write_text("1\n", encoding="utf-8")
    assert vcs.init_and_commit(project, "one")
    assert vcs.init_and_commit(project, "nothing changed")
    assert _git(project, "rev-list", "--count", "HEAD") == "1"
    (project / "a.txt").write_text("2\n", encoding="utf-8")
    assert vcs.init_and_commit(project, "two")
    assert _git(project, "rev-list", "--count", "HEAD") == "2"


def test_nothing_is_pushed_and_no_remote_is_added(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_git(tmp_path, monkeypatch)
    project = tmp_path / "game"
    project.mkdir()
    (project / "a.txt").write_text("1\n", encoding="utf-8")
    vcs.init_and_commit(project, "one")
    assert _git(project, "remote") == ""


def test_without_git_the_function_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vcs, "git_available", lambda: False)
    assert vcs.init_and_commit(tmp_path, "m") is False


# ------------------------------------------------------------------------ only what rpggen wrote (T12.12)


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository of the user's, with one commit of their own."""
    _isolate_git(tmp_path, monkeypatch)
    config = tmp_path / "empty.gitconfig"
    config.write_text("[user]\n\tname = Dana\n\temail = dana@example.com\n", encoding="utf-8")
    project = tmp_path / "game"
    project.mkdir()
    (project / "mine.txt").write_text("mine 1\n", encoding="utf-8")
    (project / "generated.txt").write_text("gen 1\n", encoding="utf-8")
    assert vcs.commit(project, "the user's first commit").committed
    return project


def test_an_existing_repository_gets_only_the_files_rpggen_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _repo(tmp_path, monkeypatch)
    (project / "mine.txt").write_text("mine 2 (not committed yet)\n", encoding="utf-8")  # unstaged
    (project / "notes.txt").write_text("a new file of the user\n", encoding="utf-8")  # untracked
    (project / "staged.txt").write_text("staged by the user\n", encoding="utf-8")
    _git(project, "add", "staged.txt")
    (project / "generated.txt").write_text("gen 2\n", encoding="utf-8")
    (project / "rpggen").mkdir()
    (project / "rpggen" / "report.json").write_text("{}\n", encoding="utf-8")
    files = ["generated.txt", "rpggen/report.json"]
    assert vcs.foreign_changes(project, files)  # the user has work of their own in there
    result = vcs.commit(project, "rpggen: regenerate project", files)
    assert result.ok and result.committed
    assert _git(project, "log", "-1", "--format=%s") == "rpggen: regenerate project"
    assert sorted(_git(project, "show", "--name-only", "--format=", "HEAD").split()) == [
        "generated.txt",
        "rpggen/report.json",
    ]
    status = _git(project, "status", "--porcelain")
    assert "mine.txt" in status and "notes.txt" in status and "staged.txt" in status
    assert "A  staged.txt" in status  # still staged, never committed by rpggen


def test_a_deleted_generated_file_is_committed_as_a_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _repo(tmp_path, monkeypatch)
    (project / "generated.txt").unlink()
    result = vcs.commit(
        project, "rpggen: regenerate project", ["generated.txt", "never_existed.txt"]
    )
    assert result.ok and result.committed
    assert _git(project, "show", "--name-status", "--format=", "HEAD") == "D\tgenerated.txt"


def test_nothing_of_ours_changed_means_no_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _repo(tmp_path, monkeypatch)
    (project / "mine.txt").write_text("mine 2\n", encoding="utf-8")
    before = _git(project, "rev-list", "--count", "HEAD")
    result = vcs.commit(project, "rpggen: regenerate project", ["generated.txt"])
    assert result.ok and not result.committed
    assert _git(project, "rev-list", "--count", "HEAD") == before


def test_a_repository_rpggen_creates_gets_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolate_git(tmp_path, monkeypatch)
    project = tmp_path / "fresh"
    project.mkdir()
    (project / "a.txt").write_text("a\n", encoding="utf-8")
    (project / "b.txt").write_text("b\n", encoding="utf-8")
    result = vcs.commit(project, "rpggen: generate project", ["a.txt"])  # files are ignored here
    assert result.committed
    assert sorted(_git(project, "show", "--name-only", "--format=", "HEAD").split()) == [
        "a.txt",
        "b.txt",
    ]


def test_a_failing_hook_is_reported_not_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _repo(tmp_path, monkeypatch)
    hook = project / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'lint says no' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    (project / "generated.txt").write_text("gen 2\n", encoding="utf-8")
    result = vcs.commit(project, "rpggen: regenerate project", ["generated.txt"])
    assert not result.ok and not result.committed
    assert "lint says no" in result.reason


def test_without_a_repository_there_are_no_foreign_changes(tmp_path: Path) -> None:
    assert vcs.foreign_changes(tmp_path, ["a.txt"]) is False
