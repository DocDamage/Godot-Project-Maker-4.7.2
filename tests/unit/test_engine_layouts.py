"""T16.21: a pack that ships one art laid out for several engines is read from one of them."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, catalog, classifier, explain, inventory

ENGINES = ["Godot", "RPG_Maker_MV_MZ", "RPG_Maker_VX_VXace", "RPG_Maker_XP", "Unity"]


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


_PICTURES = 0


def _png(path: Path, size: tuple[int, int]) -> None:
    global _PICTURES
    _PICTURES += 1  # every picture in a colour of its own: none is a copy of another
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (_PICTURES * 29 % 256, 120, _PICTURES * 53 % 256, 255)).save(path)


def _multi_engine(tmp: Path) -> Path:
    pack = tmp / "ranch"
    _png(pack / "assets" / "animals" / "cow_idle_32x32.png", (32, 32))
    _png(pack / "assets" / "autotiles" / "02_grass" / "01_grass_01.png", (16, 96))
    for layout, size in (("2x2", (64, 64)), ("3x3", (192, 64))):
        _png(pack / "engines" / "Godot" / "autotiles" / layout / "02_grass" / "grass_01.png", size)
    for engine in ENGINES[1:4]:
        _png(pack / "engines" / engine / "autotiles" / "A2" / "A2_01.png", (768, 576))
        _png(pack / "engines" / engine / "animals" / "cow_01.png", (96, 128))
    _png(pack / "engines" / "Unity" / "autotiles" / "grass.png", (16, 80))
    return pack


def _catalog(pack: Path) -> catalog.Catalog:
    opened = archive.open_pack(pack, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    return cat


def test_the_godot_files_are_used_once_and_the_four_other_copies_are_marked(tmp_path: Path) -> None:
    cat = _catalog(_multi_engine(tmp_path))
    assert "engines:5:Godot" in cat.packs[0].warnings
    by_path = {a.path.split("/", 3)[-1]: a for a in cat.assets}
    used = sorted(p for p, a in by_path.items() if a.status != "UNUSED")
    assert used == [
        "assets/animals/cow_idle_32x32.png",
        "engines/Godot/autotiles/3x3/02_grass/grass_01.png",
    ]
    other = [a for p, a in by_path.items() if p.startswith("engines/") and "/Godot/" not in p]
    assert len(other) == 7 and {a.status for a in other} == {"UNUSED"}
    assert all("for another engine" in explain.why(a) for a in other)
    for path in ("engines/Godot/autotiles/2x2/02_grass/grass_01.png",
                 "assets/autotiles/02_grass/01_grass_01.png"):  # fmt: skip
        assert by_path[path].status == "UNUSED" and "47-tile sheet" in explain.why(by_path[path])
    # in the catalog, not left out: a role chosen in the audit brings one back
    xp = by_path["engines/RPG_Maker_XP/animals/cow_01.png"]
    xp.overrides["role"] = "NPC"
    assert catalog.recompute_status(xp) == "CONFIRMED"


@pytest.mark.parametrize(
    ("folders", "kept"),
    [
        (ENGINES, "Godot"),
        (["Unity", "RPG_Maker_XP", "RPG_Maker_MV_MZ"], "RPG_Maker_MV_MZ"),
        (["Unity", "RPG_Maker_XP", "RPG_Maker_VX_VXace"], "RPG_Maker_VX_VXace"),
        (["Unity", "GameMaker", "Construct"], "Construct"),
        (["unity", "GODOT"], "GODOT"),
    ],
)
def test_which_engine_is_read(folders: list[str], kept: str) -> None:
    plan = classifier.engine_plan([f"engines/{f}/tiles/a.png" for f in folders])
    assert plan is not None and plan.kept == kept and len(plan.engines) == len(folders)
    assert plan.warning == f"engines:{len(folders)}:{kept}"
    assert not plan.godot_autotiles and not plan.both_layouts


def test_a_pack_for_one_engine_or_none_has_no_plan() -> None:
    assert classifier.engine_plan(["engines/Godot/tiles/a.png", "assets/b.png"]) is None
    assert classifier.engine_plan(["tiles/a.png", "engines.png", "engines/readme.png"]) is None
    assert classifier.engine_plan([]) is None
    # the folder an archive wraps everything in is not looked at
    wrapped = [f"Ranch v3/engines/{f}/a/b.png" for f in ("Godot", "Unity")]
    plan = classifier.engine_plan(wrapped, "Ranch v3")
    assert plan is not None and plan.kept == "Godot"
    assert (
        classifier.not_this_engine(wrapped[1], plan, "Ranch v3") == classifier.UNUSED_OTHER_ENGINE
    )
    assert classifier.not_this_engine(wrapped[0], plan, "Ranch v3") is None


def test_without_godot_nothing_is_said_about_layouts_or_templates() -> None:
    paths = [
        "engines/Unity/autotiles/grass.png",
        "engines/RPG_Maker_XP/autotiles/2x2/grass.png",
        "assets/autotiles/grass.png",
    ]
    plan = classifier.engine_plan(paths)
    assert plan is not None and plan.kept == "RPG_Maker_XP"
    assert [classifier.not_this_engine(p, plan) for p in paths] == [
        classifier.UNUSED_OTHER_ENGINE,
        None,
        None,
    ]


def test_godot_with_one_layout_keeps_it() -> None:
    paths = ["engines/Godot/autotiles/2x2/grass.png", "engines/Unity/autotiles/grass.png"]
    plan = classifier.engine_plan(paths)
    assert plan is not None and plan.godot_autotiles and not plan.both_layouts
    assert classifier.not_this_engine(paths[0], plan) is None
