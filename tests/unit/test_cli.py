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


def test_the_hint_and_the_suggested_resolution_follow_the_tile_size() -> None:
    from rpggen.core import options

    assert options.tiles_hint((640, 360), 48) == "≈ 13.3 × 7.5 tiles on screen"
    assert options.tiles_hint((640, 360), 16) == "≈ 40 × 22.5 tiles on screen"
    presets = options.RESOLUTION_PRESETS
    assert options.suggested_preset(presets, 16) == (320, 180)  # 20 tiles across
    assert options.suggested_preset(presets, 24) == (480, 270)
    assert options.suggested_preset(presets, 48) == (640, 360)  # the closest there is
