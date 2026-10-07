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
