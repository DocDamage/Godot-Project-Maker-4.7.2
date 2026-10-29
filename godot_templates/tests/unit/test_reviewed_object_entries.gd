extends RefCounted
## Reviewed static tools and modular stamps remain placeable with their chosen collision.

const Entries := preload("res://builder/lib/object_entries.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")

func test_assets_dock_includes_tools_weapons_and_static_terrain_stamps(t) -> void:
	var ctx := BuildContext.new("")
	ctx.config = {"archetype": "assets"}
	var assets: Array = []
	for role: String in ["TOOL", "WEAPON", "GROUND", "WATER", "WALL", "ROAD", "CLIFF"]:
		assets.append({"id": "pack." + role, "path": "icon.svg", "status": "CONFIRMED",
			"detected": {"role": role, "usage": "object", "size": [32, 48], "frame": [32, 48],
				"origin": [12, 44], "collision": {"profile": "NONE"}, "animations": {}}})
	ctx.catalog = CatalogReader.new({"assets": assets})
	var entries := Entries.entries(ctx)
	t.eq(entries.size(), assets.size())
	for e: Dictionary in entries:
		t.eq(e["origin"], [12, 44])
		t.eq(e["collision"], {"profile": "NONE"}, "explicit NONE must prevent automatic blocking")
		t.eq(e["region"], [0, 0, 32, 48])

func test_assets_only_never_turns_an_inventory_icon_into_a_demo_chest(t) -> void:
	var ctx := BuildContext.new("")
	ctx.config = {"archetype": "assets"}
	ctx.catalog = CatalogReader.new({"assets": [{"id": "pack.apple", "path": "icon.svg", "status": "CONFIRMED",
		"detected": {"role": "ITEM", "usage": "object", "size": [32, 32], "frame": [32, 32],
			"origin": [16, 31], "collision": {"profile": "NONE"}, "animations": {}}}]})
	t.eq(Entries.chest_entry(ctx), {})
	ctx.config = {"archetype": "turn_based"}
	# A named thing is placeable outside the assets archetype; keep the existing game fallback.
	ctx.catalog = CatalogReader.new({"assets": [{"id": "pack.apple", "path": "icon.svg", "status": "CONFIRMED",
		"detected": {"role": "ITEM", "usage": "sprite", "size": [32, 32], "frame": [32, 32]}}]})
	t.eq(Entries.chest_entry(ctx).get("id", ""), "pack.apple")
