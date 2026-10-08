from __future__ import annotations

import json
import zipfile
from pathlib import Path

from rpggen import cli
from rpggen.core import diagnostics

HOME = Path("C:/Users/alice")


def _project(root: Path) -> Path:
    meta = root / "rpggen"
    (meta / "logs").mkdir(parents=True)
    (meta / "results").mkdir()
    (root / "assets" / "packs" / "p").mkdir(parents=True)
    (root / "assets/packs/p/hero.png").write_bytes(b"\x89PNG not really")
    (meta / "generator_config.json").write_text('{"project_name": "T"}', encoding="utf-8")
    (meta / "ownership_ledger.json").write_text("{}", encoding="utf-8")
    (meta / "build_state.json").write_text("{}", encoding="utf-8")
    (meta / "asset_catalog.json").write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "id": "p/hero",
                        "path": "assets/packs/p/hero.png",
                        "sha256": "ab",
                        "detected": {"size": [32, 48]},
                        "overrides": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (meta / "results" / "build_results.json").write_text(
        '{"path": "C:\\Users\\alice\\x"}', encoding="utf-8"
    )
    (meta / "logs" / "build.log").write_text(
        r"opening C:\Users\alice\proj and C:/Users/alice/other by alice" + "\n", encoding="utf-8"
    )
    return root


def test_bundle_contents_have_no_art_and_are_redacted(tmp_path: Path) -> None:
    project = _project(tmp_path / "proj")
    out = diagnostics.make_bundle(project, tmp_path / "b.zip", None, home=HOME, user="alice")
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert not [n for n in names if Path(n).suffix.lower() in diagnostics.FORBIDDEN_SUFFIXES]
        for expected in (
            "README.txt", "system.json", "config.json", "asset_catalog.json",
            "ownership_ledger.json", "build_state.json", "results/build_results.json",
            "logs/build.log", "assets_manifest.json",
        ):  # fmt: skip
            assert expected in names
        log = zf.read("logs/build.log").decode()
        assert "alice" not in log and "<home>" in log and "<user>" in log
        assert "alice" not in zf.read("results/build_results.json").decode()
        manifest = json.loads(zf.read("assets_manifest.json"))
        assert manifest == [
            {"id": "p/hero", "path": "assets/packs/p/hero.png", "sha256": "ab",
             "w": 32, "h": 48, "size": 15}
        ]  # fmt: skip
        system = json.loads(zf.read("system.json"))
        assert {"os", "python", "rpggen", "godot_version", "godot_path", "locale"} <= set(system)
        assert b"no art" in zf.read("README.txt").lower()


def test_log_is_capped_to_its_tail(tmp_path: Path) -> None:
    project = _project(tmp_path / "proj")
    big = project / "rpggen/logs/big.log"
    line = b"x" * 99 + b"\n"
    big.write_bytes(line * (diagnostics.LOG_TAIL_BYTES // 100 + 5000))
    out = diagnostics.make_bundle(project, tmp_path / "b.zip", None, home=HOME, user="alice")
    with zipfile.ZipFile(out) as zf:
        data = zf.read("logs/big.log")
    assert len(data) <= diagnostics.LOG_TAIL_BYTES
    assert data.startswith(b"x" * 99 + b"\n")  # cut at a line boundary


def test_failed_run_folder_and_cli(tmp_path: Path, capsys) -> None:
    failed = _project(tmp_path / ".rpggen_failed" / "20260101-000000")
    out = tmp_path / "out.zip"
    assert cli.main(["diagnose", "--target", str(failed), "--out", str(out)]) == 0
    assert out.is_file()
    assert "diagnostic bundle written" in capsys.readouterr().out
    assert cli.main(["diagnose", "--target", str(tmp_path / "missing")]) == 2


def test_short_user_names_are_not_redacted_everywhere() -> None:
    redact = diagnostics.redactor(Path("C:/Users/a"), "a")
    assert redact("a banana") == "a banana"


# ------------------------------------------------------------------------ one log, rotated, run ids (T12.24)


def _reset_logging():
    import logging

    for handler in list(logging.getLogger().handlers):
        if getattr(handler, "_rpggen", False):
            logging.getLogger().removeHandler(handler)
            handler.close()


def test_the_command_line_and_the_wizard_log_to_the_same_folder(tmp_path, monkeypatch) -> None:
    from rpggen import logging_setup, paths
    from rpggen.gui.dialogs import diagnostic_export

    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "_rpggen"))
    assert diagnostic_export.app_log_dir() == paths.log_dir()
    seen: list[Path] = []
    monkeypatch.setattr(logging_setup, "configure", lambda folder, verbose: seen.append(folder))
    monkeypatch.setenv("RPGGEN_GODOT", "godot")
    from rpggen.core import orchestrator

    monkeypatch.setattr(
        orchestrator,
        "run",
        lambda *a, **k: orchestrator.RunResult(True, Path(a[1]), [], None, None),
    )
    assert cli.main(["generate", "--pack", str(tmp_path), "--target", str(tmp_path / "t")]) == 0
    assert seen == [paths.log_dir()]  # the folder the GUI's run_gui configures as well


def test_the_log_rotates_at_two_megabytes_and_keeps_five_older_files(tmp_path) -> None:
    import logging

    from rpggen import logging_setup

    _reset_logging()
    try:
        logging_setup.MAX_BYTES = 4000
        logging_setup.configure(tmp_path / "logs", False)
        log = logging.getLogger("rpggen.test")
        for i in range(400):
            log.info("a line of the log that is long enough to fill the file %d", i)
        logging.shutdown()
        names = sorted(p.name for p in (tmp_path / "logs").iterdir())
        assert names == [
            "rpggen.log",
            "rpggen.log.1",
            "rpggen.log.2",
            "rpggen.log.3",
            "rpggen.log.4",
            "rpggen.log.5",
        ]
        assert logging_setup.BACKUPS == 5
        assert [p.name for p in logging_setup.log_files(tmp_path / "logs")][-1] == "rpggen.log"
    finally:
        logging_setup.MAX_BYTES = 2 * 1024 * 1024
        _reset_logging()


def test_records_carry_the_run_id_of_the_run_they_were_made_in(tmp_path) -> None:
    import logging

    from rpggen import logging_setup

    _reset_logging()
    try:
        logging_setup.configure(tmp_path / "logs", False)
        log = logging.getLogger("rpggen.test")
        log.info("before any run")
        with logging_setup.run_context("3f9a1c2e"):
            log.info("inside the run")
            try:
                _ = 1 / 0
            except ZeroDivisionError:
                log.exception("a failure with a traceback")
        log.info("after the run")
        for handler in logging.getLogger().handlers:
            handler.flush()
        text = (tmp_path / "logs" / "rpggen.log").read_text(encoding="utf-8")
        assert "[-] rpggen.test: before any run" in text
        assert "[3f9a1c2e] rpggen.test: inside the run" in text
        assert "[-] rpggen.test: after the run" in text
        lines = logging_setup.read_run_lines(tmp_path / "logs", "3f9a1c2e")
        assert any("inside the run" in line for line in lines)
        assert any("ZeroDivisionError" in line for line in lines)  # the traceback came along
        assert not any("before any run" in line or "after the run" in line for line in lines)
        assert len(logging_setup.new_run_id()) == 8
    finally:
        _reset_logging()


def test_a_bundle_holds_only_the_lines_of_its_own_run(tmp_path) -> None:
    import logging

    from rpggen import logging_setup

    _reset_logging()
    try:
        app_logs = tmp_path / "applogs"
        logging_setup.configure(app_logs, False)
        log = logging.getLogger("rpggen.test")
        with logging_setup.run_context("aaaaaaaa"):
            log.info("the other run, alice")
        with logging_setup.run_context("bbbbbbbb"):
            log.info("my run, said by alice")
        for handler in logging.getLogger().handlers:
            handler.flush()
        project = _project(tmp_path / "proj")
        (project / "rpggen" / "generation_report.json").write_text(
            '{"run_id": "bbbbbbbb", "ok": true}', encoding="utf-8"
        )
        out = diagnostics.make_bundle(
            project, tmp_path / "b.zip", None, home=HOME, user="alice", app_log_dir=app_logs
        )
        with zipfile.ZipFile(out) as zf:
            app = zf.read("logs/rpggen_app.log").decode()
            assert "my run" in app and "the other run" not in app
            assert "alice" not in app  # redacted like the other logs
        # a project with no run id (older, or a crash outside a generation) gets the end of the log
        (project / "rpggen" / "generation_report.json").write_text('{"ok": true}', encoding="utf-8")
        out = diagnostics.make_bundle(
            project, tmp_path / "c.zip", None, home=HOME, user="alice", app_log_dir=app_logs
        )
        with zipfile.ZipFile(out) as zf:
            assert "the other run" in zf.read("logs/rpggen_app.log").decode()
    finally:
        _reset_logging()


def test_the_report_and_the_result_carry_the_run_id(tmp_path, monkeypatch) -> None:
    from rpggen.core import orchestrator

    state = orchestrator._State(None, tmp_path, Path("godot"), orchestrator.Callbacks())
    assert len(state.run_id) == 8
    assert orchestrator._report_data(state, True)["run_id"] == state.run_id
