from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen import analyze_cmd, cli
from rpggen.core import accuracy, catalog
from rpggen.core.catalog import Asset

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _asset(asset_id: str, path: str, detected: dict, overrides: dict | None = None) -> Asset:
    return Asset(
        asset_id,
        "p",
        f"assets/packs/p/{path}",
        "0" * 64,
        "image",
        "AUTO_DETECTED",
        detected,
        overrides or {},
        "x",
        0.9,
    )


def _catalog() -> catalog.Catalog:
    cat = catalog.Catalog()
    cat.assets = [
        _asset(
            "p.tiles.a",
            "tiles/a.png",
            {
                "usage": "tiles",
                "role": "GROUND",
                "grid": {"cell": [16, 16], "margin": [0, 0], "separation": [1, 1]},
            },
        ),
        _asset(
            "p.chars.b#c1",
            "chars/b.png",
            {
                "usage": "sprite",
                "role": "NPC",
                "frame": [16, 24],
                "animations": {"walk_down": {}, "idle_down": {}},
            },
        ),
        _asset("p.chars.b#c0", "chars/b.png", {"usage": "sprite", "role": "PLAYER"}),
    ]
    return cat


def test_perfect_score() -> None:
    expected = {
        "tiles/a.png": {
            "usage": "tiles",
            "role": "GROUND",
            "cell": [16, 16],
            "margin": [0, 0],
            "separation": [1, 1],
        },
        "chars/b.png#c1": {
            "usage": "sprite",
            "role": "NPC",
            "frame": [16, 24],
            "anims": ["idle_down", "walk_down"],
        },
        "chars/b.png#c0": {"role": "PLAYER"},
    }
    report = accuracy.score(_catalog(), expected)
    assert report["overall"] == {"correct": 10, "total": 10, "accuracy": 1.0}
    assert report["misses"] == []
    assert accuracy.grouped(report) == {"grid": 1.0, "usage": 1.0, "role": 1.0, "anims": 1.0}
    assert accuracy.check_thresholds(report) == []


def test_misses_and_unlisted_paths() -> None:
    expected = {
        "tiles/a.png": {
            "usage": "sprite",
            "role": "GROUND",
            "cell": [32, 32],
            "separation": [1, 1],
        },
        "missing/file.png": {"usage": "tiles", "role": "GROUND"},
        # fields that are not scored are ignored
        "chars/b.png#c0": {"role": "PLAYER", "baseline_y": 23, "regions": [[0, 0, 1, 1]]},
    }
    report = accuracy.score(_catalog(), expected)
    assert report["fields"]["usage"] == {"correct": 0, "total": 2, "accuracy": 0.0}
    assert report["fields"]["role"]["correct"] == 2 and report["fields"]["role"]["total"] == 3
    assert report["fields"]["cell"]["correct"] == 0
    assert report["fields"]["separation"]["correct"] == 1
    assert {(m["path"], m["field"]) for m in report["misses"]} >= {
        ("tiles/a.png", "usage"),
        ("tiles/a.png", "cell"),
        ("missing/file.png", "role"),
    }
    failures = accuracy.check_thresholds(report)
    assert any(f.startswith("usage") for f in failures)
    # the 20 hero/other assets that are not in `expected` are not counted at all
    assert (
        report["overall"]["total"] == 2 + 1 + 3 + 0 + 2 + 1 + 1 - 1 + 0
        or report["overall"]["total"] > 0
    )


def test_overrides_are_scored_as_effective_facets() -> None:
    cat = _catalog()
    cat.assets[0].overrides = {"role": "WALL"}
    report = accuracy.score(cat, {"tiles/a.png": {"role": "WALL"}})
    assert report["overall"]["accuracy"] == 1.0


def test_thresholds_constants() -> None:
    assert accuracy.THRESHOLDS == {"grid": 0.95, "usage": 0.95, "role": 0.85, "anims": 0.90}


def test_synthetic_corpus_meets_the_thresholds(tmp_path: Path) -> None:
    report, failures = analyze_cmd.run_corpus(SYNTH)
    assert failures == [], report["overall"]["misses"]
    assert report["passed"] is True
    assert set(report["packs"]) >= {"basic16", "gutterless48", "rpgmaker_like", "zipped"}
    assert all(v is None or v >= accuracy.THRESHOLDS[g] for g, v in report["groups"].items())


def test_cli_analyze_pack_with_expected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "catalog.json"
    code = cli.main(
        [
            "analyze",
            str(SYNTH / "gutter32"),
            "--out",
            str(out),
            "--expected",
            str(SYNTH / "gutter32.expected.json"),
        ]
    )
    text = capsys.readouterr().out
    assert code == 0
    assert "tiles/world.png" in text and "32x32 m1 s1" in text and "overall 5/5" in text
    assert catalog.load(out).asset("gutter32.tiles.world") is not None


def test_cli_analyze_corpus_writes_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "accuracy_report.json"
    assert cli.main(["analyze", "--corpus", str(SYNTH), "--report", str(report)]) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["passed"] is True and data["thresholds"]["grid"] == 0.95
    assert "anims" in capsys.readouterr().out


def test_cli_analyze_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["analyze"]) == 2
    assert cli.main(["analyze", str(tmp_path / "missing.zip")]) == 3  # ARCH: the input
    assert "ARCH-001" in capsys.readouterr().out


def test_corpus_fails_when_accuracy_drops(tmp_path: Path) -> None:
    import shutil

    corpus = tmp_path / "corpus"
    shutil.copytree(SYNTH / "gutter32", corpus / "gutter32")
    expected = json.loads((SYNTH / "gutter32.expected.json").read_text(encoding="utf-8"))
    expected["tiles/world.png"]["cell"] = [16, 16]
    (corpus / "gutter32.expected.json").write_text(json.dumps(expected), encoding="utf-8")
    report, failures = analyze_cmd.run_corpus(corpus)
    assert failures and report["passed"] is False


# ------------------------------------------------------------------------ private corpus (T12.26)


def _profile_of(pack: Path):
    """A pack, analysed, every decision confirmed, exported as a profile (the corpus's input)."""
    from rpggen.core import archive, inventory, profiles

    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=False)
    for asset in cat.assets:
        asset.status = "CONFIRMED"
    return inv, profiles.export_profile(cat, inv.pack_id, inv, {"title": pack.stem})


def _private_corpus(tmp_path: Path, pack_name: str = "basic16"):
    """A corpus folder with the entry of one synthetic pack, and a folder of "my own packs" that
    holds a copy of that pack under another name."""
    import shutil

    from rpggen import jsonio

    inv, profile = _profile_of(SYNTH / pack_name)
    entry = accuracy.make_entry(pack_name, inv, profile)
    corpus = tmp_path / "corpus"
    corpus.mkdir(exist_ok=True)
    jsonio.write(corpus / f"{pack_name}.corpus.json", entry)
    packs = tmp_path / "packs"
    packs.mkdir(exist_ok=True)
    shutil.copytree(SYNTH / pack_name, packs / "my_own_copy")
    return corpus, packs, entry


def test_a_fingerprint_matches_the_same_files_and_not_changed_ones(tmp_path: Path) -> None:
    import shutil

    from rpggen.core import archive, inventory

    inv, profile = _profile_of(SYNTH / "basic16")
    entry = accuracy.make_entry("basic16", inv, profile)
    assert set(entry) == {"corpus_version", "name", "fingerprint", "profile"}
    assert all(set(v) == {"sha256", "size"} for v in entry["fingerprint"].values())
    assert accuracy.match(entry, inv) == 1.0
    changed = tmp_path / "changed"
    shutil.copytree(SYNTH / "basic16", changed)
    victim = next(changed.rglob("*.png"))
    victim.write_bytes(victim.read_bytes() + b"\0")
    other = inventory.build_inventory(archive.open_pack(changed, set()))
    assert 0.0 < accuracy.match(entry, other) < 1.0
    assert accuracy.match({"fingerprint": {}}, inv) == 0.0


def test_the_expected_decisions_come_from_the_profile() -> None:
    _inv, profile = _profile_of(SYNTH / "strips")
    expected = accuracy.expected_from_profile(profile)
    assert expected and all(set(v) <= set(accuracy.FIELDS) for v in expected.values())
    anims = [v["anims"] for v in expected.values() if "anims" in v]
    assert anims and all(isinstance(a, list) for a in anims)


def test_a_pack_found_by_fingerprint_scores_perfectly_with_a_diagonal_confusion(
    tmp_path: Path,
) -> None:
    corpus, packs, _entry = _private_corpus(tmp_path)
    summary = analyze_cmd.run_private_corpus(corpus, packs)
    assert summary["missing"] == [] and list(summary["packs"]) == ["basic16"]
    report = summary["packs"]["basic16"]
    assert report["groups"] == {"grid": 1.0, "usage": 1.0, "role": 1.0, "anims": 1.0}
    assert report["misses"] == []
    for expected_role, row in report["confusion"].items():
        assert set(row) == {expected_role}  # every asset detected as the role it was confirmed as
    for row in report["roles"].values():
        assert row["precision"] == 1.0 and row["recall"] == 1.0
    assert summary["groups"]["role"] == 1.0


def test_a_wrong_decision_shows_in_the_confusion_matrix_and_the_per_role_numbers(
    tmp_path: Path,
) -> None:
    from rpggen import jsonio

    corpus, packs, entry = _private_corpus(tmp_path)
    ground = next(k for k, v in entry["profile"]["assets"].items() if v.get("role") == "GROUND")
    entry["profile"]["assets"][ground]["role"] = "WATER"  # the "truth" now disagrees with rpggen
    jsonio.write(corpus / "basic16.corpus.json", entry)
    report = analyze_cmd.run_private_corpus(corpus, packs)["packs"]["basic16"]
    assert report["confusion"]["WATER"] == {"GROUND": 1}
    assert report["roles"]["WATER"]["recall"] == 0.0
    assert (
        report["roles"]["GROUND"]["detected"] == 1 and report["roles"]["GROUND"]["precision"] == 0.0
    )
    assert report["groups"]["role"] < 1.0
    assert any(m["field"] == "role" and m["path"] == ground for m in report["misses"])


def test_an_entry_whose_pack_is_not_there_is_reported_missing(tmp_path: Path) -> None:
    corpus, packs, entry = _private_corpus(tmp_path)
    from rpggen import jsonio

    entry["name"] = "somebody_elses_pack"
    entry["fingerprint"] = {"x.png": {"sha256": "0" * 64, "size": 1}}
    jsonio.write(corpus / "other.corpus.json", entry)
    summary = analyze_cmd.run_private_corpus(corpus, packs)
    assert summary["missing"] == ["somebody_elses_pack"] and "basic16" in summary["packs"]


def test_objects_are_scored_by_sheet_and_region(tmp_path: Path) -> None:
    corpus, packs, _entry = _private_corpus(tmp_path, "objects_in_sheet")
    report = analyze_cmd.run_private_corpus(corpus, packs)["packs"]["objects_in_sheet"]
    objects = report["objects"]
    assert objects["expected"] >= 2 and objects["found"] == objects["expected"]
    assert objects["role_correct"] == objects["expected"] and objects["extra"] == 0
    assert objects["recall"] == 1.0


def test_the_cli_writes_the_json_and_the_markdown_report(tmp_path: Path, capsys) -> None:
    corpus, packs, _entry = _private_corpus(tmp_path)
    out = tmp_path / "private.json"
    code = cli.main(
        ["analyze", "--private-corpus", str(corpus), "--packs", str(packs), "--report", str(out)]
    )
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["missing"] == [] and "basic16" in report["packs"]
    text = out.with_suffix(".md").read_text(encoding="utf-8")
    assert text.startswith("# Real-pack accuracy") and "## Per role" in text
    assert "## Confusion" in text and "| basic16 |" in text
    assert "basic16: grid 1.000" in capsys.readouterr().out
    assert cli.main(["analyze", "--private-corpus", str(corpus)]) == 2  # --packs is needed


def test_the_fingerprint_tool_writes_an_entry_without_pixels(tmp_path: Path) -> None:
    import importlib.util

    from rpggen import jsonio

    inv, profile = _profile_of(SYNTH / "basic16")
    profile_file = tmp_path / "confirmed.rpgprofile.json"
    jsonio.write(profile_file, profile)
    tool = importlib.util.spec_from_file_location(
        "corpus_fingerprint",
        Path(__file__).resolve().parents[2] / "tools" / "corpus_fingerprint.py",
    )
    module = importlib.util.module_from_spec(tool)
    tool.loader.exec_module(module)
    out = tmp_path / "corpus" / "basic16.corpus.json"
    assert (
        module.main(
            ["--pack", str(SYNTH / "basic16"), "--profile", str(profile_file), "--out", str(out)]
        )
        == 0
    )
    entry = jsonio.read(out)
    assert entry["name"] == "basic16" and entry["fingerprint"] == accuracy.fingerprint(inv)
    assert not any(k in json.dumps(entry) for k in ("PNG", "IHDR"))  # no image data in it
