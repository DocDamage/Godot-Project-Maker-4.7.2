"""M16: an LPC character is put together from a body and the layers drawn over it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from rpggen import schema
from rpggen.core import archive, catalog, explain, inventory, lpc_compose
from rpggen.core.adapters import lpc
from rpggen.errors import IssueList

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
BODY = (200, 150, 120, 255)
HAIR = (160, 60, 20, 255)
SHIRT = (40, 90, 200, 255)
BACK = (90, 90, 90, 255)
SIZES = {"walk": (9, 4), "slash": (6, 4), "hurt": (6, 1), "idle": (2, 4)}


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _strip(action: str, color: tuple[int, int, int, int], box: tuple[int, int, int, int]) -> Image.Image:  # fmt: skip
    """Every cell of an animation with one rectangle of ``color`` at ``box`` inside it."""
    count, rows = SIZES[action]
    img = Image.new("RGBA", (count * 64, rows * 64), (0, 0, 0, 0))
    for row in range(rows):
        for col in range(count):
            x, y = col * 64, row * 64
            img.paste(Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), color), (x + box[0], y + box[1]))  # fmt: skip
    return img


def _part(pack: Path, folder: str, color, box, actions=("walk", "slash", "hurt")) -> None:  # noqa: ANN001
    for action in actions:
        path = pack / "spritesheets" / folder / f"{action}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        _strip(action, color, box).save(path)


def _small_pack(tmp: Path, hair: int = 1) -> Path:
    """A body, a shirt over its middle, hair on top, and the back of a cape behind it."""
    pack = tmp / "hero_parts"
    _part(pack, "body/bodies/male", BODY, (24, 20, 40, 60), ("walk", "slash", "hurt", "idle"))
    _part(pack, "torso/shirt/male", SHIRT, (22, 30, 42, 46))
    _part(pack, "cape/behind/male", BACK, (16, 24, 48, 56))
    for n in range(hair):
        _part(pack, f"hair/style_{n + 1}/adult", HAIR, (24, 12, 40, 26))
    return pack


def _assemble(pack: Path, previous: catalog.Catalog | None = None):
    opened = archive.open_pack(pack, set())
    cat, issues, generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], previous, [], use_cache=False
    )
    return cat, issues, generated, {opened.pack_id: Path(opened.root)}


def _character(cat: catalog.Catalog) -> catalog.Asset:
    (found,) = [a for a in cat.assets if lpc_compose.is_character(a)]
    return found


def test_a_pack_that_leaves_no_choice_gets_its_character_by_itself(tmp_path: Path) -> None:
    cat, issues, generated, _roots = _assemble(_small_pack(tmp_path))
    schema.validate("catalog", cat.to_json())
    assert not [i for i in issues if i.code == "ASSET-033"]
    (definition,) = cat.characters
    assert definition["auto"] is True and definition["name"] == "Male"
    assert definition["body"].endswith("body.bodies.male.walk") and len(definition["layers"]) == 3
    hero = _character(cat)
    assert hero.id == definition["id"] == "hero_parts.lpc_character.male"
    assert hero.path == "generated/lpc_characters/hero_parts__lpc_character__male.png"
    assert hero.status == "CONFIRMED" and hero.detected_by == "lpc_compose"
    eff = catalog.effective(hero)
    assert eff["role"] == "NPC" and eff["tags"] == ["lpc_character"] and eff["frame"] == [64, 64]
    assert eff["derived_from"] == definition["body"]
    assert {"walk_down", "idle_up", "attack_left", "hurt", "death"} <= set(eff["animations"])
    assert "source" not in eff["animations"]["walk_down"], "one sheet, as a pack ships it whole"
    # the bare body is in the character and not a character of its own any more
    body = cat.asset(definition["body"])
    assert body.status == "UNUSED" and "is put together with its layers" in explain.why(body)
    assert Path(generated[hero.path]).is_file()


def test_the_layers_lie_over_the_body_in_the_order_of_their_parts(tmp_path: Path) -> None:
    cat, _issues, generated, _roots = _assemble(_small_pack(tmp_path))
    sheet = Image.open(generated[_character(cat).path]).convert("RGBA")
    walk = lpc.BY_NAME["walk"].row * 64
    assert sheet.size == (832, 26 * 64), "down to the body's last animation: its idle"

    def at(x: int, y: int, col: int = 3, row: int = 2) -> tuple[int, ...]:
        return sheet.getpixel((col * 64 + x, walk + row * 64 + y))

    assert at(32, 55) == BODY  # the legs: nothing over them
    assert at(32, 40) == SHIRT  # the shirt over the body
    assert at(32, 16) == HAIR  # the hair over all
    assert at(18, 40) == BACK  # the cape's back shows beside the body ...
    assert at(26, 50) == BODY  # ... and is under it
    assert at(4, 4)[3] == 0
    # a layer that has no picture for an animation is not drawn in it: the idle is bare
    idle = lpc.BY_NAME["idle"].row * 64
    assert sheet.getpixel((32, idle + 40)) == BODY and sheet.getpixel((32, idle + 16))[3] == 0
    hurt = lpc.BY_NAME["hurt"].row * 64
    assert sheet.getpixel((32, hurt + 16)) == HAIR


def test_a_part_with_two_candidates_is_left_for_somebody_to_choose(tmp_path: Path) -> None:
    cat, _issues, _generated, _roots = _assemble(_small_pack(tmp_path, hair=2))
    (definition,) = cat.characters
    assert len(definition["layers"]) == 2, "the shirt and the cape; no hair"
    body = cat.asset(definition["body"])
    parts = lpc_compose.layers_for(cat, body)
    assert sorted(parts) == ["cape_behind", "hair", "torso"] and len(parts["hair"]) == 2
    # nothing but a body: no character at all
    bare = tmp_path / "bare"
    _part(bare / "x", "body/bodies/female", BODY, (24, 20, 40, 60))
    alone, _i, _g, _r = _assemble(bare / "x")
    assert alone.characters == [] and not [a for a in alone.assets if lpc_compose.is_character(a)]
    assert next(a for a in alone.assets if lpc_compose.is_body(a)).status != "UNUSED"


def test_a_layer_drawn_for_another_build_does_not_fit(tmp_path: Path) -> None:
    pack = _small_pack(tmp_path)
    _part(pack, "torso/dress/female", SHIRT, (20, 28, 44, 58))
    cat, _issues, _generated, _roots = _assemble(pack)
    body = cat.asset(cat.characters[0]["body"])
    assert len(lpc_compose.layers_for(cat, body)["torso"]) == 1, "the dress is for another body"
    assert lpc_compose.build_of(body) == "male"


def test_a_chosen_character_is_kept_and_rendered_again(tmp_path: Path) -> None:
    pack = _small_pack(tmp_path, hair=2)
    cat, _issues, _generated, roots = _assemble(pack)
    body = next(a for a in cat.assets if lpc_compose.is_body(a))
    hair = lpc_compose.layers_for(cat, body)["hair"][1]
    mine = {
        "id": "hero_parts.lpc_character.rogue",
        "name": "Rogue",
        "body": body.id,
        "layers": [hair.id],
    }
    lpc_compose.apply(cat, [mine], roots, IssueList(), cat)
    assert [d["id"] for d in cat.characters] == [mine["id"]], "the automatic one gave way"
    rogue = _character(cat)
    rogue.overrides["role"] = "PLAYER"
    again, issues, generated, _roots = _assemble(pack, catalog.Catalog.from_json(cat.to_json()))
    assert not [i for i in issues if i.code in ("ASSET-033", "CAT-004")]
    assert again.characters == [mine]
    kept = _character(again)
    assert (
        kept.id == mine["id"]
        and kept.sha256 == rogue.sha256
        and kept.overrides == {"role": "PLAYER"}
    )
    sheet = Image.open(generated[kept.path]).convert("RGBA")
    walk = lpc.BY_NAME["walk"].row * 64
    assert sheet.getpixel((32, walk + 16)) == HAIR and sheet.getpixel((32, walk + 40)) == BODY


def test_a_removed_character_stays_away_and_its_body_is_free(tmp_path: Path) -> None:
    pack = _small_pack(tmp_path)
    cat, _issues, _generated, roots = _assemble(pack)
    auto = cat.characters[0]
    lpc_compose.apply(cat, [{**auto, "auto": False, "removed": True}], roots, IssueList(), cat)
    assert not [a for a in cat.assets if lpc_compose.is_character(a)]
    assert cat.characters[0]["removed"] is True
    assert lpc_compose.definition_of(cat, auto["id"]) is None
    body = cat.asset(auto["body"])
    assert body.status != "UNUSED" and catalog.effective(body)["role"] != "NONE"
    schema.validate("catalog", cat.to_json())
    again, _i, _g, _r = _assemble(pack, catalog.Catalog.from_json(cat.to_json()))
    assert not [a for a in again.assets if lpc_compose.is_character(a)], "not put together again"


def test_a_part_that_left_the_pack_is_a_warning_not_a_crash(tmp_path: Path) -> None:
    pack = _small_pack(tmp_path)
    cat, _issues, _generated, roots = _assemble(pack)
    made = {**cat.characters[0], "auto": False}
    lost = {**made, "layers": [*made["layers"], "hero_parts.hat.gone"]}
    issues = IssueList()
    lpc_compose.apply(cat, [lost], roots, issues, cat)
    (warning,) = issues
    assert warning.code == "ASSET-033" and "hat.gone" in warning.message
    assert _character(cat) is not None, "drawn without the layer that is gone"
    nobody = {**made, "id": "hero_parts.lpc_character.ghost", "body": "hero_parts.no.body"}
    issues = IssueList()
    lpc_compose.apply(cat, [nobody], roots, issues, cat)
    assert [i.code for i in issues] == ["ASSET-033"] and "its body" in issues[0].message
    assert not [a for a in cat.assets if lpc_compose.is_character(a)]
    assert cat.characters == [lpc_compose.normalized(nobody)], "the definition stays"
    for broken in ({"id": "x"}, {"id": "x", "body": "b", "name": " "}):
        with pytest.raises(lpc_compose.CharacterError):
            lpc_compose.normalized(broken)


def test_a_universal_sheet_can_be_a_layer_of_the_same_rows(tmp_path: Path) -> None:
    """The rows of a whole sheet are taken as the pictures of its animations."""
    pack = _small_pack(tmp_path)
    cat, _issues, _generated, roots = _assemble(pack)
    body = next(a for a in cat.assets if lpc_compose.is_body(a))
    strips = lpc_compose._strips(body, roots)
    assert sorted(strips) == ["hurt", "idle", "slash", "walk"]
    assert strips["walk"].size == (576, 256) and strips["hurt"].size == (384, 64)
    whole = _character(cat)
    files = {whole.pack_id: lpc_compose.cached_file(whole.sha256).parent}
    assert lpc_compose._file(whole.path, files) is None, "a generated sheet is no pack file"


def test_the_synthetic_collection_pack_has_its_character() -> None:
    cat, issues, generated, _roots = _assemble(SYNTH / "lpc_parts")
    assert not [i for i in issues if i.code == "ASSET-033"]
    (definition,) = cat.characters
    assert definition["body"] == "lpc_parts.spritesheets.body.bodies.male.walk"
    assert definition["layers"] == ["lpc_parts.spritesheets.hair.afro.adult.walk"], (
        "one hair; the shirt comes in two colours and is left to choose"
    )
    hero = _character(cat)
    assert catalog.effective(hero)["size"] == [832, 42 * 64], "the body runs: rows 38 to 41"
    golden = json.loads(
        (SYNTH.parents[1] / "tests/golden/lpc_parts.catalog.json").read_text("utf-8")
    )
    assert golden["characters"] == cat.characters
    assert Path(generated[hero.path]).is_file()
