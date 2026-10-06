from __future__ import annotations

from rpggen import ids


def test_slug_examples() -> None:
    assert ids.slug("Hero 01") == "hero_01"
    assert ids.slug("Hero 01.png") == "hero_01_png"
    assert ids.slug("Árbol-Grande") == "arbol_grande"
    assert ids.slug("123") == "n123"
    assert ids.slug("***") == "x"
    assert ids.slug("") == "x"
    assert ids.slug("__a__") == "a"


def test_asset_id() -> None:
    assert (
        ids.asset_id("forest_pack", "Tilesets/Grass Tiles.png")
        == "forest_pack.tilesets.grass_tiles"
    )
    assert ids.asset_id("p", "a.b/c.d.png") == "p.a_b.c_d"
    assert ids.asset_id("p", "tiles/terrain.png") == "p.tiles.terrain"


def test_disambiguate() -> None:
    assert ids.disambiguate(["a", "a", "b", "a"]) == ["a", "a__2", "b", "a__3"]
    assert ids.disambiguate([]) == []


def test_pack_id_from_name() -> None:
    assert ids.pack_id_from_name("Forest Pack.zip", set()) == "forest_pack"
    assert ids.pack_id_from_name("Forest Pack.zip", {"forest_pack"}) == "forest_pack_2"
    assert ids.pack_id_from_name("Forest Pack.zip", {"forest_pack", "forest_pack_2"}) == (
        "forest_pack_3"
    )
    assert len(ids.pack_id_from_name("x" * 100 + ".zip", set())) == 40
