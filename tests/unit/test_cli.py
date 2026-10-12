from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen import cli
from rpggen.core import catalog, orchestrator, staging

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


# ------------------------------------------------------------------------ unknown arguments


def test_an_unknown_flag_exits_with_2_and_says_so(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(
            [
                "generate",
                "--pack",
                "X",
                "--target",
                "Y",
                "--placeholdr",
                "PLAYER",
                "--godott",
                "Z",
            ]
        )
    assert raised.value.code == 2
    err = capsys.readouterr().err
    assert "unrecognized arguments" in err and "--placeholdr" in err and "--godott" in err


def test_an_abbreviated_flag_is_an_error_not_a_guess(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["generate", "--pack", "X", "--targ", "Y"])
    assert raised.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_every_command_rejects_unknown_arguments(capsys) -> None:
    for command in (["version"], ["restore", "--target", "t"], ["diagnose", "--target", "t"]):
        with pytest.raises(SystemExit) as raised:
            cli.main([*command, "--nonsense"])
        assert raised.value.code == 2, command


def test_a_mistyped_command_does_not_open_the_wizard(monkeypatch, capsys) -> None:
    from rpggen.gui import app

    monkeypatch.setattr(app, "run_gui", lambda *a, **k: pytest.fail("the wizard was opened"))
    with pytest.raises(SystemExit) as raised:
        cli.main(["genrate", "--target", "X"])
    assert raised.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_gui_forwards_unknown_arguments_to_qt(monkeypatch) -> None:
    from rpggen.gui import app

    seen: list[tuple[list[str], Path | None]] = []
    monkeypatch.setattr(
        app, "run_gui", lambda argv=None, target=None: seen.append((argv, target)) or 0
    )
    assert cli.main(["gui", "-platform", "offscreen", "--target", "T"]) == 0
    assert seen[-1][0][1:] == ["-platform", "offscreen"] and seen[-1][1] == Path("T")
    assert cli.main(["-platform", "offscreen", "-style", "Fusion"]) == 0  # no command: the wizard
    assert seen[-1][0][1:] == ["-platform", "offscreen", "-style", "Fusion"]
    assert cli.main([]) == 0 and seen[-1][0][1:] == []


def test_version_still_works(capsys) -> None:
    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.startswith("rpggen ")


# ------------------------------------------------------------------------ the tile size


def _capture_run(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    def fake_run(cfg_path, target, exe, cb=None, **kwargs):
        calls.append(
            {
                "cfg": json.loads(Path(cfg_path).read_text(encoding="utf-8")),
                "target": target,
                **kwargs,
            }
        )
        return orchestrator.RunResult(True, Path(target), [], None, None)

    monkeypatch.setattr(orchestrator, "run", fake_run)
    monkeypatch.setenv("RPGGEN_GODOT", "godot")
    return calls


def test_pack_runs_derive_the_tile_size_unless_it_is_given(monkeypatch, tmp_path: Path) -> None:
    calls = _capture_run(monkeypatch)
    pack = str(SYNTH / "rpgmaker_like")
    assert cli.main(["generate", "--pack", pack, "--target", str(tmp_path / "a")]) == 0
    assert calls[-1]["derive_tile_size"] is True
    assert (
        cli.main(["generate", "--pack", pack, "--target", str(tmp_path / "b"), "--tile-size", "24"])
        == 0
    )
    assert calls[-1]["derive_tile_size"] is False and calls[-1]["cfg"]["base_tile_size"] == 24
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps(calls[-1]["cfg"]), encoding="utf-8")
    assert cli.main(["generate", "--config", str(cfg), "--target", str(tmp_path / "c")]) == 0
    assert calls[-1]["derive_tile_size"] is False


def test_the_tile_size_flag_is_checked(capsys) -> None:
    for bad in ("7", "257", "x"):
        with pytest.raises(SystemExit) as raised:
            cli.main(["generate", "--pack", "P", "--target", "T", "--tile-size", bad])
        assert raised.value.code == 2, bad


@pytest.mark.parametrize(
    ("pack", "size"),
    [("basic16", 16), ("gutter32", 32), ("gutterless48", 48), ("rpgmaker_like", 48)],
)
def test_the_dominant_tile_size_of_the_synthetic_packs(pack: str, size: int) -> None:
    from rpggen.core import archive, inventory

    opened = archive.open_pack(SYNTH / pack, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    assert catalog.dominant_tile_size(cat) == size


def test_no_tile_set_means_no_size() -> None:
    assert catalog.dominant_tile_size(catalog.Catalog.from_json(_empty_catalog())) is None


def _empty_catalog() -> dict:
    from rpggen.core import archive, inventory

    opened = archive.open_pack(SYNTH / "strips", set())
    cat, _i, _g = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    data = cat.to_json()
    data["tilesets"] = []
    return data


def test_the_catalog_phase_records_the_derived_size_and_sizes_placeholders(
    tmp_path: Path,
) -> None:
    from PIL import Image

    cfg = orchestrator.default_config_for_pack(SYNTH / "mixed", "Mixed")  # no player in this pack
    assert cfg.base_tile_size == 16
    state = orchestrator._State(None, tmp_path / "out", Path("godot"), orchestrator.Callbacks())
    state.cfg = cfg
    state.derive_tile_size = True
    state.placeholders = ["PLAYER"]
    orchestrator.phase_stage(state)
    orchestrator.phase_install(state)
    orchestrator.phase_catalog(state)
    assert state.cfg.base_tile_size == 32  # the overworld set of the pack
    written = json.loads(
        (state.staging.staging / "rpggen" / "generator_config.json").read_text(encoding="utf-8")
    )
    assert written["base_tile_size"] == 32
    placeholder = state.staging.staging / "generated" / "debug_placeholders" / "player.png"
    assert Image.open(placeholder).size == (4 * 32, 4 * 48)  # 4 x 4 frames of 32 x 48
    staging.discard(state.staging)


# ------------------------------------------------------------------------ a bundle of packs

BUNDLE = SYNTH / "bundle.zip"


def test_pack_folder_takes_those_folders_of_a_bundle(monkeypatch, tmp_path: Path) -> None:
    calls = _capture_run(monkeypatch)
    code = cli.main(
        [
            "generate",
            "--pack",
            str(BUNDLE),
            "--pack-folder",
            "Pirate Cove Tileset",
            "--pack-folder",
            "medieval fantasy town tileset",  # the case of a letter does not matter
            "--target",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0
    packs = calls[-1]["cfg"]["packs"]
    assert [(p["pack_id"], p["folders"]) for p in packs] == [
        ("pirate_cove_tileset", ["Pirate Cove Tileset"]),
        ("medieval_fantasy_town_tileset", ["Medieval Fantasy Town Tileset"]),
    ]
    assert {p["source"] for p in packs} == {str(BUNDLE.resolve())}
    assert {p["kind"] for p in packs} == {"zip"}


def test_a_bundle_without_pack_folder_stops_with_the_list_of_its_folders(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    calls = _capture_run(monkeypatch)
    code = cli.main(["generate", "--pack", str(BUNDLE), "--target", str(tmp_path / "o"), "--json"])
    assert code == 2 and calls == []
    captured = capsys.readouterr()
    error = json.loads(captured.out)["error"]
    assert "bundle of 12 packs" in error and "--pack-folder" in error
    assert "  Pirate Cove Tileset" in error.splitlines()
    assert "  WW1 Trench & Bunker Pixel Art Tileset Pack" in error.splitlines()
    assert "--pack-folder" in captured.err  # the human lines say it too


def test_an_unknown_pack_folder_names_the_nearest(monkeypatch, tmp_path: Path, capsys) -> None:
    calls = _capture_run(monkeypatch)
    args = ["generate", "--target", str(tmp_path / "o"), "--json"]
    code = cli.main([*args, "--pack", str(BUNDLE), "--pack-folder", "Pirate Cave Tilest"])
    assert code != 0 and calls == []
    issue = json.loads(capsys.readouterr().out)["issues"][0]
    assert issue["code"] == "ARCH-001"
    assert 'no pack folder "Pirate Cave Tilest"' in issue["message"]
    assert 'the nearest is "Pirate Cove Tileset"' in issue["message"]
    # a pack that is not a bundle has no pack folders
    code = cli.main([*args, "--pack", str(SYNTH / "basic16"), "--pack-folder", "tiles"])
    assert code != 0 and calls == []
    issue = json.loads(capsys.readouterr().out)["issues"][0]
    assert issue["code"] == "ARCH-001" and "not a bundle of packs" in issue["message"]
    # and the option goes with --pack
    assert cli.main([*args, "--config", "c.json", "--pack-folder", "x"]) == 2
    capsys.readouterr()


def _config_with(tmp_path: Path, pack: dict) -> Path:
    cfg = orchestrator.default_config_for_pack(SYNTH / "basic16", "Folders").to_json()
    cfg["packs"] = [pack]
    path = tmp_path / "generator_config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


def test_the_config_takes_folders_and_only_for_a_bundle(tmp_path: Path) -> None:
    from rpggen.core import archive
    from rpggen.core import config as config_mod
    from rpggen.errors import RpgGenError

    entry = {"pack_id": "packs", "source": str(BUNDLE), "source_sha256": "0" * 64, "kind": "zip"}
    two = ["Pirate Cove Tileset", "Cyberpunk City Tileset"]
    loaded = config_mod.load(_config_with(tmp_path, {**entry, "folders": two}))
    # one entry for each folder, named by it; saved once, it reads the same ever after
    assert [(p.pack_id, p.folders) for p in loaded.packs] == [
        ("pirate_cove_tileset", (two[0],)),
        ("cyberpunk_city_tileset", (two[1],)),
    ]
    config_mod.save(loaded, tmp_path / "again.json")
    assert config_mod.load(tmp_path / "again.json").packs == loaded.packs
    one = config_mod.load(_config_with(tmp_path, {**entry, "folders": two[:1]}))
    assert [(p.pack_id, p.folder) for p in one.packs] == [("packs", two[0])]  # its id is kept
    opened = archive.open_pack(Path(one.packs[0].source), set(), folder=one.packs[0].folder)
    assert sorted(p.name for p in opened.root.glob("*.png")) == ["1.png", "3.png"]
    assert (opened.root / "LICENSE.txt").is_file()  # the bundle's licence is the pack's
    # the schema: a list of names, never an empty one, never on a rar
    for bad in ({"folders": []}, {"folders": [""]}, {"folders": two[:1], "kind": "rar"}):
        with pytest.raises(RpgGenError):
            config_mod.load(_config_with(tmp_path, {**entry, **bad}))
    # a pack that is not a bundle is refused where it is opened
    plain = {**entry, "source": str(SYNTH / "basic16"), "kind": "folder", "folders": ["tiles"]}
    refused = config_mod.load(_config_with(tmp_path, plain)).packs[0]
    with pytest.raises(RpgGenError, match="not a bundle of packs"):
        archive.open_pack(Path(refused.source), set(), folder=refused.folder)


def test_a_dry_run_reads_only_the_folders_named(tmp_path: Path, capsys) -> None:
    code = cli.main(
        [
            "generate",
            "--pack",
            str(BUNDLE),
            "--pack-folder",
            "Medieval Fantasy Town Tileset",
            "--target",
            str(tmp_path / "out"),
            "--dry-run",
            "--json",
        ]
    )
    document = json.loads(capsys.readouterr().out)
    assert document["summary"]["packs"] == ["medieval_fantasy_town_tileset"]
    # tiles alone make no game (no player), but the pack itself was read without a complaint
    assert code != 0 and document["failed_phase"] != "preflight"
    assert not [i for i in document["issues"] if i["code"].startswith("ARCH-")]
    from rpggen import paths

    unpacked = list((paths.cache_dir() / "extracted").rglob("*.png"))
    assert sorted(p.name for p in unpacked) == ["1.png", "2.png", "3.png", "5.png", "6.png"]


def test_the_hint_and_the_suggested_resolution_follow_the_tile_size() -> None:
    from rpggen.core import options

    assert options.tiles_hint((640, 360), 48) == "≈ 13.3 × 7.5 tiles on screen"
    assert options.tiles_hint((640, 360), 16) == "≈ 40 × 22.5 tiles on screen"
    presets = options.RESOLUTION_PRESETS
    assert options.suggested_preset(presets, 16) == (320, 180)  # 20 tiles across
    assert options.suggested_preset(presets, 24) == (480, 270)
    assert options.suggested_preset(presets, 48) == (640, 360)  # the closest there is
