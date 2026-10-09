"""World repair (T13.24), the Python side: which maps the tool may write (the hash rule), the
backup and *Restore previous*, the report, the config key and the command line. Godot is replaced
by a stand-in that does what the tool's result says."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rpggen import cli, jsonio, paths, schema
from rpggen.core import config, ledger, promote, report, world_plan, world_repair
from rpggen.errors import RpgGenError

AREAS = [
    {"name": "Village", "biome": "village"},
    {"name": "Meadow", "biome": "field"},
    {"name": "Woods", "biome": "forest"},
]
MAPS = ("starter_map", "meadow", "woods")


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> Path:
    """A project with a three-area world whose maps rpggen built (their hashes are recorded)."""
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    root = tmp_path / "game"
    (root / "game" / "maps").mkdir(parents=True)
    (root / "generated" / "builder" / "tools").mkdir(parents=True)
    (root / "generated" / "builder" / "tools" / "world_repair.gd").write_text("# tool\n", "utf-8")
    (root / "addons" / "rpg_project_tools" / "tools").mkdir(parents=True)
    (root / "addons" / "rpg_project_tools" / "tools" / "world_repair.gd").write_text("#\n", "utf-8")
    files = {}
    for name in MAPS:
        path = root / "game" / "maps" / f"{name}.tscn"
        path.write_text(f"[gd_scene]\n; {name}\n", encoding="utf-8", newline="\n")
        files[f"game/maps/{name}.tscn"] = ledger.LedgerEntry(
            ledger.file_hash(path), "starter_map_recipe", "user_seed"
        )
    plan = world_plan.plan(AREAS, 7)
    world_plan.record_hashes(root, plan)
    world_plan.save(root, plan)
    ledger.Ledger(files=files).save(root / paths.LEDGER)
    monkeypatch.setattr(promote, "editor_open", lambda target: False)
    return root


def _line(map_name: str, what: str, kind: str = "spawn") -> dict[str, str]:
    return {
        "kind": kind,
        "map": f"game/maps/{map_name}.tscn",
        "node": "SpawnPoints/x",
        "what": what,
    }


class FakeTool:
    """What Godot would do: the planned lines, those on maps outside ``only`` skipped, and (not
    in a dry run) a line appended to every map a repair names."""

    def __init__(self, lines: list[dict[str, str]], unfixable: list[dict[str, str]] | None = None):
        self.lines = lines
        self.unfixable = unfixable or []
        self.calls: list[tuple[list[str] | None, bool]] = []

    def __call__(self, target: Path, exe: Path, only: list[str] | None, dry_run: bool) -> dict:
        self.calls.append((only, dry_run))
        repairs = [line for line in self.lines if only is None or line["map"] in only]
        skipped = [line for line in self.lines if line not in repairs]
        if not dry_run:
            for line in repairs:
                with open(Path(target) / line["map"], "a", encoding="utf-8", newline="\n") as fh:
                    fh.write(f"; repaired: {line['what']}\n")
            jsonio.write(
                Path(target) / world_repair.RESULT_FILE,
                {"repairs": repairs, "skipped": skipped, "unfixable": self.unfixable},
            )
        return {"repairs": repairs, "skipped": skipped, "unfixable": self.unfixable}


def _text(project: Path, name: str) -> str:
    return (project / "game" / "maps" / f"{name}.tscn").read_text(encoding="utf-8")


# ------------------------------------------------------------------------ the hash rule


def test_only_the_maps_nobody_changed_are_rpggens(project: Path) -> None:
    assert world_repair.unedited_maps(project) == [f"game/maps/{n}.tscn" for n in sorted(MAPS)]
    (project / "game/maps/woods.tscn").write_text("[gd_scene]\n; mine now\n", encoding="utf-8")
    assert world_repair.unedited_maps(project) == [
        "game/maps/meadow.tscn",
        "game/maps/starter_map.tscn",
    ]
    (project / world_plan.PLAN_FILE).unlink()
    assert world_repair.unedited_maps(project) == [], "without a plan no map is rpggen's to mend"


def test_auto_mends_generated_maps_and_only_offers_for_an_edited_one(
    project: Path, monkeypatch
) -> None:
    (project / "game/maps/woods.tscn").write_text("[gd_scene]\n; mine now\n", encoding="utf-8")
    tool = FakeTool(
        [_line("meadow", "added the spawn point from_woods"), _line("woods", "added a door back")]
    )
    monkeypatch.setattr(world_repair, "_run_tool", tool)
    before_woods = _text(project, "woods")
    result = world_repair.auto(project, Path("godot"))
    assert [line["map"] for line in result.repairs] == ["game/maps/meadow.tscn"]
    assert [line["map"] for line in result.offered] == ["game/maps/woods.tscn"]
    assert "repaired: added the spawn point from_woods" in _text(project, "meadow")
    assert _text(project, "woods") == before_woods, "a map its owner changed is never touched"
    # the tool was asked twice (what would be done, then doing it), both limited to the same maps
    allowed = ["game/maps/meadow.tscn", "game/maps/starter_map.tscn"]
    assert tool.calls == [(allowed, True), (allowed, False)]
    # the mended map is still rpggen's: its new hash is in the plan and in the ledger
    plan = world_plan.load(project)
    digest = ledger.file_hash(project / "game/maps/meadow.tscn")
    assert plan["maps"]["meadow"]["map_hash"] == digest
    assert promote.load_ledger(project).files["game/maps/meadow.tscn"].sha256 == digest
    assert "game/maps/meadow.tscn" in world_repair.unedited_maps(project)
    assert world_repair.summary(result) == (
        "world repair: made 1 repair, 1 offered for maps you changed"
    )


def test_a_project_without_a_world_plan_is_left_alone(project: Path, monkeypatch) -> None:
    (project / world_plan.PLAN_FILE).unlink()
    tool = FakeTool([_line("meadow", "x")])
    monkeypatch.setattr(world_repair, "_run_tool", tool)
    result = world_repair.auto(project, Path("godot"))
    assert not result.ran and tool.calls == [], "a 1.0 project: Godot is not even started"
    assert world_repair.summary(result) == "world repair: nothing to look at"
    assert world_repair.report_lines(result) == []


def test_asking_mends_every_map(project: Path, monkeypatch) -> None:
    (project / "game/maps/woods.tscn").write_text("[gd_scene]\n; mine now\n", encoding="utf-8")
    tool = FakeTool([_line("woods", "added a door back", "door")])
    monkeypatch.setattr(world_repair, "_run_tool", tool)
    result = world_repair.run(project, Path("godot"))
    assert [line["map"] for line in result.repairs] == ["game/maps/woods.tscn"]
    assert "repaired: added a door back" in _text(project, "woods")
    assert tool.calls == [(None, True), (None, False)]
    # an edited map stays the user's: neither the plan nor the ledger is told a new hash
    plan = world_plan.load(project)
    assert plan["maps"]["woods"]["map_hash"] != ledger.file_hash(project / "game/maps/woods.tscn")
    recorded = promote.load_ledger(project).files["game/maps/woods.tscn"].sha256
    assert recorded == plan["maps"]["woods"]["map_hash"], "the ledger still has what rpggen wrote"
    assert "game/maps/woods.tscn" not in world_repair.unedited_maps(project)


# ------------------------------------------------------------------------ dry run, backup, restore


def test_a_dry_run_writes_nothing(project: Path, monkeypatch) -> None:
    tool = FakeTool([_line("meadow", "added the spawn point from_woods")])
    monkeypatch.setattr(world_repair, "_run_tool", tool)
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    result = world_repair.run(project, Path("godot"), dry_run=True)
    assert result.dry_run and len(result.repairs) == 1 and result.backup is None
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == before
    assert tool.calls == [(None, True)]
    assert not (project / ".rpggen_backups").exists()
    assert world_repair.summary(result) == "world repair: would make 1 repair"


def test_nothing_to_do_makes_no_backup(project: Path, monkeypatch) -> None:
    tool = FakeTool(
        [], [{"kind": "unfixable", "map": "game/maps/woods.tscn", "node": "", "what": "w"}]
    )
    monkeypatch.setattr(world_repair, "_run_tool", tool)
    result = world_repair.run(project, Path("godot"))
    assert result.repairs == [] and len(result.unfixable) == 1 and result.backup is None
    assert tool.calls == [(None, True)], "the tool is not run a second time"
    assert not (project / ".rpggen_backups").exists()


def test_the_maps_are_backed_up_and_restore_previous_undoes_the_repair(
    project: Path, monkeypatch
) -> None:
    tool = FakeTool([_line("meadow", "added the spawn point from_woods")])
    monkeypatch.setattr(world_repair, "_run_tool", tool)
    before = _text(project, "meadow")
    plan_before = world_plan.load(project)
    ledger_before = (project / paths.LEDGER).read_text(encoding="utf-8")
    result = world_repair.auto(project, Path("godot"))
    assert result.backup is not None and result.backup.parent.name == ".rpggen_backups"
    assert (result.backup / "game/maps/meadow.tscn").read_text(encoding="utf-8") == before
    assert (result.backup / world_plan.PLAN_FILE).is_file()
    assert (result.backup / paths.LEDGER).is_file()
    assert not (result.backup / "game/maps/woods.tscn").exists(), "only what the repair changes"
    assert _text(project, "meadow") != before
    # Restore previous: the map, the plan and the ledger are as they were
    promote.restore(project)
    assert _text(project, "meadow") == before
    assert world_plan.load(project) == plan_before
    assert (project / paths.LEDGER).read_text(encoding="utf-8") == ledger_before
    assert "game/maps/meadow.tscn" in world_repair.unedited_maps(project)


def test_nothing_runs_while_the_editor_has_the_project_open(project: Path, monkeypatch) -> None:
    tool = FakeTool([_line("meadow", "x")])
    monkeypatch.setattr(world_repair, "_run_tool", tool)
    monkeypatch.setattr(promote, "editor_open", lambda target: True)
    with pytest.raises(RpgGenError) as caught:
        world_repair.run(project, Path("godot"))
    assert caught.value.code == "REGEN-005" and tool.calls == []
    assert world_repair.run(project, Path("godot"), dry_run=True).repairs, "looking is allowed"
    assert world_repair.run(project, Path("godot"), force_while_open=True).repairs


def test_a_project_without_the_tool_has_nothing_to_run(project: Path, monkeypatch) -> None:
    tool = FakeTool([_line("meadow", "x")])
    monkeypatch.setattr(world_repair, "_run_tool", tool)
    (project / "addons/rpg_project_tools/tools/world_repair.gd").unlink()
    assert not world_repair.available(project)
    assert not world_repair.run(project, Path("godot")).ran and tool.calls == []


def test_the_tools_result_line_is_parsed() -> None:
    data = {"repairs": [_line("meadow", "x")], "skipped": [], "unfixable": []}
    out = f"Godot Engine v4.7.2\nnoise\n{world_repair.MARK}{json.dumps(data)}\n"
    assert world_repair._parse(out) == data
    assert world_repair._parse("no result here") is None
    assert world_repair._parse(world_repair.MARK + "{broken") is None
    assert world_repair._lines({"repairs": [{"kind": "door", "what": 3}, "junk"]}, "repairs") == [
        {"kind": "door", "map": "", "node": "", "what": "3"}
    ]
    assert world_repair.needed(["VAL-013", "VAL-028"]) and not world_repair.needed(["VAL-016"])


# ------------------------------------------------------------------------ the report


def test_the_report_has_a_world_repairs_section(project: Path, monkeypatch) -> None:
    (project / "game/maps/woods.tscn").write_text("[gd_scene]\n; mine now\n", encoding="utf-8")
    tool = FakeTool(
        [_line("meadow", "added the spawn point from_woods"), _line("woods", "added a door back")],
        [{"kind": "unfixable", "map": "game/maps/woods.tscn", "node": "", "what": "no free floor"}],
    )
    monkeypatch.setattr(world_repair, "_run_tool", tool)
    result = world_repair.auto(project, Path("godot"))
    lines = world_repair.report_lines(result)
    assert lines[:3] == ["", "## World repairs", ""]
    assert "- game/maps/meadow.tscn: added the spawn point from_woods." in lines
    assert any(".rpggen_backups/" in line and "Restore previous" in line for line in lines)
    assert any(
        line.startswith("- Not done (game/maps/woods.tscn was changed by you)") for line in lines
    )
    assert "- Cannot be mended: no free floor." in lines
    text = report.build_markdown(None, None, [], True, project=project, world_repair=result)
    assert "## World repairs" in text and text.index("## World repairs") > text.index("## World")
    assert "## World repairs" not in report.build_markdown(None, None, [], True, project=project)
    assert world_repair.report_lines(None) == []
    assert world_repair.report_lines(world_repair.RepairResult()) == []


# ------------------------------------------------------------------------ the config and the command line


def test_repair_world_is_on_by_default_and_only_stored_when_off() -> None:
    cfg = config.default_for("W", [config.PackRef("p", "x", "0" * 64, "folder")])
    assert cfg.repair_world is True and "repair_world" not in cfg.to_json()
    cfg.repair_world = False
    data = cfg.to_json()
    assert data["repair_world"] is False
    schema.validate("config", data)
    assert config.GeneratorConfig.from_json(data).repair_world is False
    del data["repair_world"]
    assert config.GeneratorConfig.from_json(data).repair_world is True


def test_the_command_line_repairs_or_only_says_what_it_would_do(
    project: Path, monkeypatch, capsys
) -> None:
    tool = FakeTool([_line("meadow", "added the spawn point from_woods")])
    monkeypatch.setattr(world_repair, "_run_tool", tool)
    monkeypatch.setenv("RPGGEN_GODOT", str(project / "godot.exe"))
    before = _text(project, "meadow")
    code = cli.main(["repair-world", "--target", str(project), "--dry-run", "--json"])
    document: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert code == 0 and document["command"] == "repair-world" and document["dry_run"] is True
    assert document["repairs"] == [_line("meadow", "added the spawn point from_woods")]
    assert document["backup"] is None and _text(project, "meadow") == before
    schema.validate("cli", document)
    code = cli.main(["repair-world", "--target", str(project), "--json"])
    document = json.loads(capsys.readouterr().out)
    assert code == 0 and document["dry_run"] is False and document["backup"]
    assert _text(project, "meadow") != before
    schema.validate("cli", document)
    # the editor has the project open: an error document, nothing written
    monkeypatch.setattr(promote, "editor_open", lambda target: True)
    code = cli.main(["repair-world", "--target", str(project), "--json"])
    document = json.loads(capsys.readouterr().out)
    assert code != 0 and document["issues"][0]["code"] == "REGEN-005"
    assert document["repairs"] == []
    schema.validate("cli", document)


def test_generate_has_the_no_repair_world_flag() -> None:
    parser = cli._build_parser()
    args = parser.parse_args(["generate", "--pack", "p", "--target", "t"])
    assert args.no_repair_world is False
    args = parser.parse_args(["generate", "--pack", "p", "--target", "t", "--no-repair-world"])
    assert args.no_repair_world is True
