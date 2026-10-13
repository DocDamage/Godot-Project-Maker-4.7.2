extends RefCounted
## T17.14, the farm in the isometric view: the soil's tile set of diamonds, the farm and its
## rooms built from a plan through the seam of the map recipes, the tile ahead for the four
## facings and both settings of `iso_controls`, tools that change exactly the faced cell, the can
## filled at the water ahead, crops that stand on the middle of their cell and sort with the
## farmer, what blocks its diamonds (the bed, the bin, a fence), an animal that keeps to the
## cells of its yard, and the boxes the stand-ins are drawn with.

const Fixtures := preload("../lib/fixtures.gd")
const TilesetRecipe := preload("res://builder/recipes/tileset_recipe.gd")
const FarmMap := preload("res://builder/recipes/farm/farm_map_recipe.gd")
const FieldRecipe := preload("res://builder/recipes/farm/field_recipe.gd")
const HomeRecipe := preload("res://builder/recipes/farm/home_recipe.gd")
const CropRecipes := preload("res://builder/recipes/farm/crop_recipes.gd")
const HudRecipe := preload("res://builder/recipes/farm/hud_recipe.gd")
const FarmBuild := preload("res://builder/recipes/farm/farm_build.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const ObjectEntries := preload("res://builder/lib/object_entries.gd")
const MapGeo := preload("res://builder/lib/map_geo.gd")
const MapUtil := preload("res://builder/lib/map_util.gd")
const ActorBuild := preload("res://builder/lib/actor_build.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

const FIXTURE := "res://tests/fixtures/iso_tiles/catalog.json"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const FILES: Array[String] = [
	"res://generated/tilesets/iso.tres", "res://rpggen/tileset_apply_state.json",
	"res://generated/tilesets/farm_soil.tres", PLAYER_SCENE,
]
const FOOT := Vector2i(60, 34)
const UNIT := 34  # a step from a diamond of 60 x 34 to the next is 34.48 px
const WATER_TILE := "iso_tiles.png.isotile_002_"
const CROPS := [
	{"id": "corn", "name": "Corn", "seed": "seed_corn", "produce": "crop_corn", "seasons": ["spring", "summer"], "days": 3, "stages": 4, "regrow": 0, "seed_price": 15, "price": 30, "energy": 14},
]
const ITEMS: Array[StringName] = [&"hoe", &"watering_can", &"sickle", &"farm_axe", &"seed_corn", &"crop_corn"]
## A small farm: the house in the north with the bin east of it, a pond of four cells, a plot of
## twelve, a coop with its yard, and one thing of each kind.
const PLOT := Rect2i(3, 7, 4, 3)
const COOP := {"id": "farm_coop", "kind": "coop", "rect": [12, 7, 3, 2], "door": [13, 9],
	"interior": {"id": "farm_coop", "size": [8, 6], "door": [2, 5], "arrive": [2, 4], "trough": [1, 1], "stalls": [[3, 1], [4, 1]]},
	"yard": {"rect": [12, 10, 3, 2], "fence": [[11, 9], [11, 10], [11, 11], [11, 12], [12, 12], [14, 12], [15, 12], [15, 11], [15, 10], [15, 9]], "gate": [13, 12], "side": "S"}}
const HOUSE := {"id": "farm_house", "kind": "house", "rect": [6, 2, 2, 2], "door": [6, 4],
	"interior": {"id": "farm_house", "size": [8, 7], "door": [3, 6], "arrive": [3, 5], "bed": {"cell": [1, 1], "size": [1, 2]}, "start": [2, 2]}}

var _made: Array[Node] = []

func _plan() -> Dictionary:
	var tillable: Array = []
	for y in range(PLOT.position.y, PLOT.end.y):
		for x in range(PLOT.position.x, PLOT.end.x):
			tillable.append([x, y])
	return {
		"size": [18, 15], "house": HOUSE, "animal_houses": [COOP],
		"bin": {"cell": [8, 3], "front": [8, 4]},
		"paths": [[6, 4], [6, 5], [6, 6]],
		"water": {"kind": "pond", "cells": [[10, 2], [11, 2], [10, 3], [11, 3]], "fill": [10, 4]},
		"tillable": tillable,
		"debris": [{"cell": [4, 8], "kind": "stump"}, {"cell": [5, 9], "kind": "grass"}],
		"trees": [[1, 1], [2, 1]],
		"scenery": [{"cell": [9, 9], "kind": "rock"}, {"cell": [9, 11], "kind": "flowers"}],
		"start": {"map": "farm_house", "cell": [2, 2], "facing": "down"},
		"exit": {"edge": "W", "cell": [0, 6], "spawn": [1, 6], "facing": "right", "to": "starter_map"},
	}

## The catalog of the fixture with a tile that is water (the synthetic pack names none).
func _catalog() -> Dictionary:
	var cat := JsonUtil.to_dict(JsonUtil.read(FIXTURE)).duplicate(true)
	for raw: Variant in JsonUtil.to_array(cat["assets"]):
		var asset: Dictionary = raw
		if str(asset["id"]).begins_with(WATER_TILE):
			asset["overrides"] = {"role": "WATER"}
	return cat

func _context(projection: String = "isometric") -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"projection": projection, "archetype": "farm", "seed": 7, "map_layers": MapUtil.DEFAULT_LAYERS.duplicate()}
	if projection != "isometric":
		ctx.config.erase("projection")
	ctx.catalog = CatalogReader.new(_catalog(), projection)
	return ctx

func _cleanup() -> void:
	for node in _made:
		if is_instance_valid(node):
			node.free()
	_made.clear()
	for path in FILES:
		if FileAccess.file_exists(path):
			DirAccess.remove_absolute(path)
	Fixtures.uninstall_state()
	ProjectSettings.set_setting(RpgIso.CONTROLS_SETTING, null)

func _frames(n: int) -> void:
	for i in n:
		await Fixtures.tree().physics_frame

## The tile sets and the farmer's scene an isometric farm is built from.
func _prepare(t) -> BuildContext:
	_cleanup()
	var ctx := _context()
	t.eq(TilesetRecipe.new().build(ctx), [])
	t.eq(FieldRecipe.new().build(ctx), [])
	var player := ActorBuild.build("player", "Player", null, Vector2i(24, 36), Vector2i(12, 35), UNIT)
	FarmBuild.augment_player(player, Vector2i(24, 36), Vector2i(12, 35), UNIT)
	t.eq(SceneUtil.save_scene(player, PLAYER_SCENE), OK)
	return ctx

## The farm of `_plan` built by the recipe, with a game around it: {root, field, soil, farmer,
## mode, state, geo}. In the scene tree when `in_tree`.
func _farm(t, in_tree: bool = false) -> Dictionary:
	var ctx := _prepare(t)
	var issues: Array = []
	var root := FarmMap.new().farm_root(ctx, _plan(), issues)
	t.eq(issues, [])
	_made.append(root)
	var registry := {}
	for id in ITEMS:
		registry[id] = Fixtures.item(id)
	var state := Fixtures.install_state(registry) as RpgGameState
	state.inventory.registry = state.items
	for id: StringName in [&"hoe", &"watering_can", &"sickle", &"farm_axe"]:
		state.inventory.add(id, 1)
	state.inventory.add(&"seed_corn", 5)
	var crops := RpgCropData.new()
	crops.add_list(CROPS)
	var mode := RpgFarmMode.new()
	mode.crops = crops
	mode.ensure_parts()
	_made.append(mode)
	var field := root.get_node("Field") as RpgField
	field.crops = crops
	var farmer := root.get_node("YSorted/Entities/Player") as RpgFarmer
	farmer.mode = mode
	farmer.field = field
	farmer.get_node("Components/PlayerInput").free()  # the test moves it
	if in_tree:
		Fixtures.tree().root.add_child(root)
	else:
		field.setup()
	return {"root": root, "field": field, "soil": root.get_node("Soil"), "farmer": farmer, "mode": mode, "state": state, "geo": MapGeo.new(ctx)}

func _use(farmer: RpgFarmer) -> bool:
	var done := farmer.use_held()
	farmer._end_use()
	return done

static func _inside(shape_node: CollisionShape2D, at: Vector2) -> bool:
	var body := shape_node.get_parent() as Node2D
	var points := (shape_node.shape as ConvexPolygonShape2D).points
	return Geometry2D.is_point_in_polygon(at - body.position - shape_node.position, points)

# ---------------------------------------------------------------- the soil

func test_the_soil_of_an_isometric_farm_is_a_tile_set_of_diamonds(t) -> void:
	var ctx := _prepare(t)
	t.eq(FarmBuild.tile(ctx), UNIT, "a tile of an isometric farm is one step on its diamonds")
	var tiles := load(FarmBuild.SOIL_TILESET) as TileSet
	t.ok(RpgIso.is_iso(tiles), "Godot's isometric shape")
	t.eq(tiles.tile_layout, TileSet.TILE_LAYOUT_DIAMOND_DOWN)
	t.eq(tiles.tile_size, FOOT, "the diamond of the project's ground")
	t.ok(tiles.get_custom_data_layer_by_name("tillable") >= 0 and tiles.get_custom_data_layer_by_name("water") >= 0)
	t.eq(tiles.get_source_count(), 1, "square soil of a pack or of the kit cannot lie on a diamond")
	var source := tiles.get_source(FieldRecipe.SOURCE_ID) as TileSetAtlasSource
	t.eq(source.texture_region_size, FOOT)
	t.eq(source.get_tile_data(FieldRecipe.PLOT_TILE, 0).get_custom_data("tillable"), true)
	t.eq(source.get_tile_data(FieldRecipe.TILLED_TILE, 0).get_custom_data("tillable"), false)
	for coords: Vector2i in [FieldRecipe.WATER_TILE, FieldRecipe.WATER_MARK]:
		t.eq(source.get_tile_data(coords, 0).get_custom_data("water"), true)
	# the five tiles are diamonds: the middle is drawn, the corners of the cell are not
	var image := FarmBuild.iso_soil_texture(FOOT).get_image()
	t.eq(image.get_size(), Vector2i(FOOT.x * 5, FOOT.y))
	var seen := {}
	for index in 4:
		var middle := image.get_pixel(FOOT.x * index + FOOT.x / 2, FOOT.y / 2)
		t.eq(middle.a, 1.0, "tile %d is drawn" % index)
		seen[middle.to_html()] = true
		for corner: Vector2i in [Vector2i(1, 1), Vector2i(FOOT.x - 2, 1), Vector2i(1, FOOT.y - 2), Vector2i(FOOT.x - 2, FOOT.y - 2)]:
			t.eq(image.get_pixel(FOOT.x * index + corner.x, corner.y).a, 0.0, "outside the diamond of tile %d" % index)
		t.eq(image.get_pixel(FOOT.x * index + 4, FOOT.y / 2).a, 1.0, "its left corner")
		t.eq(image.get_pixel(FOOT.x * index + FOOT.x / 2, 2).a, 1.0, "its top corner")
	t.eq(seen.size(), 4, "ground, tilled soil, watered soil and water are four colours")
	t.eq(image.get_pixel(FOOT.x * 4 + FOOT.x / 2, FOOT.y / 2).a, 0.0, "the mark of a cell that fills the can shows nothing")
	t.eq(FarmBuild.iso_soil_texture(FOOT).get_image().get_data(), image.get_data(), "the same every time")
	# seen from above the recipe is what it was: squares of the tile
	var flat := _context("top_down")
	t.ok(not MapGeo.is_isometric(flat))
	# a pack's own isometric soil (a flat tile tagged so) is the tilled tile, with its origin
	t.eq(FarmBuild.iso_soil_asset(ctx, "soil"), "", "the fixture names none")
	var cat := _catalog()
	for raw: Variant in JsonUtil.to_array(cat["assets"]):
		var asset: Dictionary = raw
		if str(asset["id"]).begins_with("iso_tiles.png.isotile_004_"):
			asset["overrides"] = {"tags": ["soil", "turn:%s" % str(asset["id"]).right(1)]}
		elif str(asset["id"]).begins_with("iso_tiles.png.isotile_019_"):
			asset["overrides"] = {"tags": ["soil"]}  # a block that rises is no soil
	var own := _context()
	own.catalog = CatalogReader.new(cat, "isometric")
	t.eq(FarmBuild.iso_soil_asset(own, "soil"), "iso_tiles.png.isotile_004_0", "the first turn of the flat tile")
	t.eq(FarmBuild.iso_soil_asset(own, "watered"), "")
	t.ok(FieldRecipe.new().input_hash(own) != FieldRecipe.new().input_hash(ctx))
	t.eq(FieldRecipe.new().build(own), [])
	var with_soil := ResourceLoader.load(FarmBuild.SOIL_TILESET, "TileSet", ResourceLoader.CACHE_MODE_IGNORE) as TileSet
	t.ok(with_soil.has_source(FieldRecipe.TILLED_SOURCE) and not with_soil.has_source(FieldRecipe.WATERED_SOURCE))
	var tilled := with_soil.get_source(FieldRecipe.TILLED_SOURCE) as TileSetAtlasSource
	var iso_set := load("res://generated/tilesets/iso.tres") as TileSet
	var place := MapGeo.new(own).iso.tile_for("iso_tiles.png.isotile_004_0")
	var there := iso_set.get_source(int(place["source"])) as TileSetAtlasSource
	t.eq(tilled.get_tiles_count(), 1)
	t.eq(tilled.get_tile_id(0), place["coords"], "the same cell of the same atlas")
	t.eq(tilled.texture, there.texture)
	t.eq(tilled.texture_region_size, there.texture_region_size)
	t.eq(tilled.get_tile_data(tilled.get_tile_id(0), 0).texture_origin, there.get_tile_data(place["coords"], 0).texture_origin, "on its diamond as it is on the ground")
	_cleanup()

# ---------------------------------------------------------------- the map

func test_the_farm_is_built_on_diamonds_from_its_plan(t) -> void:
	var farm := _farm(t)
	var root: Node2D = farm["root"]
	var field: RpgField = farm["field"]
	var soil: TileMapLayer = farm["soil"]
	var geo: MapGeo = farm["geo"]
	var plan := _plan()
	var ground := root.get_node("Ground") as TileMapLayer
	t.ok(RpgIso.is_iso(ground.tile_set) and RpgIso.is_iso(soil.tile_set), "the ground and the soil are diamonds")
	t.eq(ground.get_used_cells().size(), 18 * 15, "every cell of the plan")
	for cell: Vector2i in [Vector2i(0, 0), Vector2i(5, 8), Vector2i(17, 14)]:
		t.eq(soil.map_to_local(cell), ground.map_to_local(cell), "the Soil layer lies on the grid of the ground")
		t.eq(field.cell_center(cell), geo.center(cell))
		t.eq(field.cell_at(geo.center(cell)), cell)
	t.eq(field.footprint(), FOOT)
	t.eq(field.tile_px, UNIT, "what the field calls a tile is one step")
	# what can be tilled is what the plan lists, and nothing else
	var plot: Array = []
	for cell in soil.get_used_cells():
		if field.state_of(cell) == RpgField.GROUND:
			plot.append([cell.x, cell.y])
	plot.sort()
	var planned: Array = plan["tillable"]
	planned.sort()
	t.eq(plot, planned, "the field's cells are the plan's tillable cells")
	t.eq(field.state_of(Vector2i(2, 8)), "", "the ground beside the plot is not tilled")
	# the pond: the pack's water on the ground, and its cells fill the can
	for raw: Variant in JsonUtil.to_array(plan["water"]["cells"]):
		var cell := FarmMap.cell_of(raw)
		t.ok(field.is_water(cell), "%s is water" % cell)
		t.ok(str(ground.get_cell_tile_data(cell).get_custom_data("asset_id")).begins_with(WATER_TILE))
	t.ok(not field.is_water(Vector2i(10, 4)))
	var water := root.get_node("YSorted/Entities/Water") as StaticBody2D
	t.eq(water.get("kind"), "pond")
	t.eq(water.position, geo.center(Vector2i(10, 3)), "its origin is the middle of the cell the can is filled at")
	t.eq(water.get_child_count(), 4, "a diamond a cell")
	var first := water.get_node("Cell_10_2") as CollisionShape2D
	t.ok(first.shape is ConvexPolygonShape2D and first.shape == (water.get_node("Cell_11_3") as CollisionShape2D).shape, "one shape for all")
	t.ok(_inside(first, geo.center(Vector2i(10, 2))) and not _inside(first, geo.center(Vector2i(10, 4))))
	# everything stands on the middle of its cell
	t.eq((root.get_node("Markers/WaterFill") as Node2D).position, geo.center(Vector2i(10, 4)))
	t.eq((root.get_node("Markers/BinFront") as Node2D).position, geo.center(Vector2i(8, 4)))
	t.eq((root.get_node("Markers/HouseDoor") as Node2D).position, geo.center(Vector2i(6, 4)))
	t.eq((root.get_node("SpawnPoints/from_village") as Node2D).position, geo.center(Vector2i(1, 6)))
	t.eq((root.get_node("SpawnPoints/farm_house_door") as Node2D).position, geo.center(Vector2i(6, 4)), "who comes out of the house stands on the door cell")
	t.eq((root.get_node("YSorted/Entities/Player") as Node2D).position, geo.center(Vector2i(6, 4)))
	t.eq((root.get_node("YSorted/Entities/ShippingBin") as Node2D).position, geo.center(Vector2i(8, 3)))
	t.eq((root.get_node("YSorted/Entities/WeatherSign") as Node2D).position, geo.center(Vector2i(7, 4)), "the sign east of the door")
	t.eq((root.get_node("YSorted/Entities/Tree1") as Node2D).position, geo.center(Vector2i(1, 1)))
	t.eq((root.get_node("YSorted/Entities/Rock1") as Node2D).position, geo.center(Vector2i(9, 9)))
	var stump := root.get_node("YSorted/Entities/Debris_4_8") as Node2D
	t.eq(stump.position, geo.center(Vector2i(4, 8)))
	t.eq(stump.get_meta(RpgField.CLEAR_META), "stump")
	t.eq(field.clearable_at(Vector2i(4, 8), ["stump"] as Array[String]), stump, "the field finds it in its cell")
	t.ok(not field.can_till(Vector2i(4, 8)), "ground under a stump is not tilled")
	# the way out: a diamond on the gap of the edge
	var way_out := root.get_node("Triggers/to_village") as Area2D
	t.eq(way_out.position, geo.center(Vector2i(0, 6)))
	t.ok((way_out.get_node("Shape") as CollisionShape2D).shape is ConvexPolygonShape2D)
	var props := root.get_node("YSorted/Props") as TileMapLayer
	t.ok(props.get_cell_source_id(Vector2i(17, 5)) != -1, "the near edge is the pack's wall, on the layer that sorts with the actors")
	# the far edge lies in the place of the ground (T17.18), with an unseen diamond a cell
	t.eq(props.get_cell_source_id(Vector2i(0, 5)), -1)
	t.ok(ground.get_cell_tile_data(Vector2i(0, 5)).get_collision_polygons_count(0) > 0, "the far edge is the pack's wall, on the ground's layer")
	t.eq(props.get_cell_source_id(Vector2i(0, 6)), -1, "the gap is open")
	t.ok(ground.get_cell_tile_data(Vector2i(0, 6)).get_collision_polygons_count(0) == 0, "and its ground stays ground")
	var unseen := root.get_node_or_null("BorderCollision") as StaticBody2D
	t.ok(unseen != null and unseen.get_node_or_null("Wall_0_5") != null and unseen.get_node_or_null("Wall_0_6") == null and unseen.get_node_or_null("Wall_17_5") == null, "the far walls block by unseen diamonds, the near ones by their tiles")
	# the house: the pack's own is drawn on one cell and has no scene here, so it is drawn as a
	# box over the plan's footprint, in two halves, with the door as a band on its south side
	var house := root.get_node("YSorted/Entities/House") as StaticBody2D
	t.eq(house.position, geo.center(Vector2i(7, 3)), "on the cell of its footprint nearest the camera")
	t.ok(house.y_sort_enabled and house.get_node_or_null("Left") != null and house.get_node_or_null("Right") != null)
	t.eq((house.get_node("Left") as Node2D).position.y, (1 - 2) * FOOT.y / 2.0, "the left half sorts by the left corner")
	var walls := house.get_node("Shape") as CollisionShape2D
	for cell: Vector2i in [Vector2i(6, 2), Vector2i(7, 2), Vector2i(6, 3), Vector2i(7, 3)]:
		t.ok(_inside(walls, geo.center(cell)), "it blocks %s" % cell)
	for cell: Vector2i in [Vector2i(6, 4), Vector2i(8, 3), Vector2i(5, 2), Vector2i(6, 1)]:
		t.ok(not _inside(walls, geo.center(cell)), "and not %s" % cell)
	var door := root.get_node("Triggers/HouseDoor") as Area2D
	var side := (geo.center(Vector2i(6, 3)) + geo.center(Vector2i(6, 4))) / 2.0
	t.ok(door.position.distance_to(side) < 2.5, "the door lies on the south side, before the door cell")
	t.eq(RpgIso.screen_to_cell(door.position, FOOT), Vector2i(6, 4), "just outside the house")
	t.near((door.get_node("Shape") as CollisionShape2D).rotation, Vector2(30, 17).angle(), 0.0001, "along the side")
	t.eq(door.get("target_map"), "res://game/maps/farm_house.tscn")
	# the yard: its cells, a fence that closes its diamonds, a gate that is walked through
	var yard := root.get_node("Yards/Coop") as Node2D
	t.eq(yard.get_meta(&"yard"), Rect2i(12, 10, 3, 2))
	t.eq(yard.position, geo.center(Vector2i(12, 10)))
	var fence := root.get_node("YSorted/Entities/Fence_coop_11_10") as StaticBody2D
	t.eq(fence.position, geo.center(Vector2i(11, 10)))
	t.eq(((fence.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points, RpgFarmIso.diamond(FOOT), "a fence closes its diamond")
	t.eq(fence.get_node("Sprite").get_child_count(), 5, "a post, and two rails to each of the two pieces beside it")
	var corner := root.get_node("YSorted/Entities/Fence_coop_11_12") as StaticBody2D
	t.eq(FarmMap.sides_of(Vector2i(11, 12), FarmMap.cells_of(COOP["yard"]["fence"])), ["n", "e"] as Array[String])
	t.eq(corner.get_node("Sprite").get_child_count(), 5)
	var gate := root.get_node("YSorted/Entities/Gate_coop") as Node2D
	t.ok(not gate is StaticBody2D, "the gate does not block")
	t.eq(gate.position, geo.center(Vector2i(13, 12)))
	t.eq(gate.get_node("Sprite").get_child_count(), 2, "a post towards the fence on either side")
	var coop := root.get_node("YSorted/Entities/Coop") as StaticBody2D
	t.eq(coop.position, geo.center(Vector2i(14, 8)))
	_cleanup()

func test_a_building_of_the_packs_stands_at_the_plans_door(t) -> void:
	var ctx := _prepare(t)
	var entries := ObjectEntries.entries(ctx)
	var house := FarmMap.building_entry(entries, "house", Vector2i(2, 2), 0, UNIT, "", true)
	t.eq(house.get("id"), "iso_tiles.png.house_01_0", "the pack's house on one cell fits a footprint of two by two")
	t.eq(FarmMap.iso_building_offset(house, Vector2i(2, 2), 0), Vector2i(0, 1), "in the last row, over the door")
	t.eq(FarmMap.iso_building_offset(house, Vector2i(3, 2), 2), Vector2i(2, 1))
	var wide := house.duplicate(true)
	wide["stands_on"] = [3, 2]
	t.eq(FarmMap.iso_building_offset(wide, Vector2i(3, 2), 1), Vector2i(0, 0), "one that is the footprint")
	t.eq(FarmMap.iso_building_offset(wide, Vector2i(3, 2), 2), Vector2i(-1, -1), "its door is not before the plan's cell")
	t.eq(FarmMap.iso_building_offset(wide, Vector2i(2, 2), 0), Vector2i(-1, -1), "too large")
	# what a smaller building leaves of the plan's footprint is blocked (T17.18): the plan
	# counts the whole footprint as a building
	var rest := FarmMap.uncovered_cells(Rect2i(6, 2, 2, 2), Rect2i(Vector2i(6, 2) + FarmMap.iso_building_offset(house, Vector2i(2, 2), 0), MapGeo.entry_cells(house)))
	t.eq(rest, [Vector2i(6, 2), Vector2i(7, 2), Vector2i(7, 3)] as Array[Vector2i], "three of the four cells of a house on one diamond")
	t.eq(FarmMap.uncovered_cells(Rect2i(6, 2, 3, 2), Rect2i(6, 2, 3, 2)), [] as Array[Vector2i], "none of a building that is the footprint")
	t.eq(FarmMap.building_entry(entries, "coop", Vector2i(3, 2), 1, UNIT, "", true), {}, "a house is no coop: drawn")
	t.eq(FarmMap.building_entry(entries, "house", Vector2i(2, 2), 0, UNIT), {}, "seen from above nothing drawn for the other view is taken")
	var trees := FarmMap.thing_entries(entries, "tree", UNIT)
	t.eq(trees.size(), 1, "the pack's tree stands on one cell, however high it is")
	var picture := FarmMap.iso_picture("tree", trees[0], FOOT, UNIT) as Sprite2D
	t.eq(picture.offset, Vector2(-30, -39), "the middle of its diamond on the origin")
	picture.free()
	_cleanup()

# ---------------------------------------------------------------- the farmer

func test_the_tile_ahead_on_diamonds(t) -> void:
	var farm := _farm(t, true)
	var root: Node2D = farm["root"]
	var farmer: RpgFarmer = farm["farmer"]
	var field: RpgField = farm["field"]
	var here := Vector2i(4, 5)
	await _frames(2)
	farmer.global_position = field.cell_center(here)
	t.eq(farmer.cell(), here)
	t.eq(farmer.diamond(), FOOT)
	# a facing alone: up n, right e, down s, left w
	farmer._look = Vector2.ZERO
	for case: Array in [["up", "n"], ["right", "e"], ["down", "s"], ["left", "w"]]:
		farmer.facing = case[0]
		var by: Vector2i = RpgIso.STEPS[case[1]]
		t.eq(farmer.tile_ahead(), here + by, "facing %s" % [case[0]])
		t.eq(farmer.tile_ahead(), farmer.cell_ahead(), "what any actor is asked")
	# turned to a neighbour: that neighbour, whatever the farmer did before
	for side in RpgIso.SIDES:
		var by: Vector2i = RpgIso.STEPS[side]
		farmer._look = Vector2(3, 9)
		t.ok(farmer.face_cell(here + by))
		t.eq(farmer.tile_ahead(), here + by, "turned %s" % side)
	t.ok(not farmer.face_cell(here + Vector2i(1, 1)), "a cell across a corner is no neighbour")
	t.ok(not farmer.face_cell(here))
	# walking, with the pad on the screen and on the grid: the neighbour it walked towards
	for controls: String in [RpgIso.CONTROLS_SCREEN, RpgIso.CONTROLS_GRID]:
		ProjectSettings.set_setting(RpgIso.CONTROLS_SETTING, controls)
		for input: Vector2 in [Vector2.UP, Vector2.RIGHT, Vector2.DOWN, Vector2.LEFT, Vector2(1, -1), Vector2(-1, 1)]:
			farmer.global_position = field.cell_center(here)
			for i in 5:
				farmer.move_dir(RpgIso.move_vector(root, input.normalized()))
				await Fixtures.tree().physics_frame
			farmer.move_dir(Vector2.ZERO)
			await _frames(2)
			var side := RpgIso.side_of(RpgIso.move_vector(root, input.normalized()))
			var by: Vector2i = RpgIso.STEPS[side]
			t.eq(farmer.cell(), here, "five frames stay in the cell")
			t.eq(farmer.tile_ahead(), here + by, "%s with %s controls faces %s" % [input, controls, side])
			var frame := farmer.get_node("TileFrame") as Line2D
			t.ok(frame.global_position.distance_to(field.cell_center(here + by)) < 0.01, "the frame lies on that cell")
			t.eq(frame.points, RpgFarmIso.diamond(FOOT), "and is its diamond")
	t.eq(RpgIso.pad_side(Vector2.UP, RpgIso.CONTROLS_GRID), "n")
	_cleanup()
	await _frames(2)

func test_a_tool_changes_exactly_the_faced_cell(t) -> void:
	var farm := _farm(t)
	var farmer: RpgFarmer = farm["farmer"]
	var mode: RpgFarmMode = farm["mode"]
	var state: RpgGameState = farm["state"]
	var field: RpgField = farm["field"]
	var soil: TileMapLayer = farm["soil"]
	var root: Node2D = farm["root"]
	var here := Vector2i(5, 7)  # a cell of the plot with a free cell of the plot on three sides
	farmer.position = field.cell_center(here)
	t.ok(mode.hotbar.hold_item(&"hoe"))
	var tilled: Array[Vector2i] = []
	for side: String in ["e", "s", "w"]:
		var by: Vector2i = RpgIso.STEPS[side]
		t.ok(farmer.face_cell(here + by))
		t.ok(_use(farmer), "the hoe tills the cell to the %s" % side)
		tilled.append(here + by)
		var worked: Array[Vector2i] = []
		worked.assign(field.cells.keys())
		t.eq(worked, tilled, "that cell and no other")
		t.eq(soil.get_cell_atlas_coords(here + by), field.tilled_tile, "painted on the Soil layer")
	t.ok(farmer.face_cell(here + Vector2i(0, -1)))
	t.ok(not _use(farmer), "the cell to the north is not of the plot")
	t.eq(field.cells.size(), 3)
	t.eq(field.state_of(here), RpgField.GROUND, "the cell under its feet is left alone")
	# the can waters the faced cell, a seed is planted in it
	mode.hotbar.hold_item(&"watering_can")
	farmer.face_cell(here + Vector2i(1, 0))
	t.ok(_use(farmer))
	t.ok(field.is_watered(here + Vector2i(1, 0)) and not field.is_watered(here + Vector2i(0, 1)) and not field.is_watered(here + Vector2i(-1, 0)))
	t.eq(soil.get_cell_atlas_coords(here + Vector2i(1, 0)), field.watered_tile)
	mode.hotbar.hold_item(&"seed_corn")
	farmer.face_cell(here + Vector2i(0, 1))
	t.ok(_use(farmer), "a seed goes into the faced cell")
	t.eq(field.crop_at(here + Vector2i(0, 1)), "corn")
	t.eq([field.crop_at(here + Vector2i(1, 0)), field.crop_at(here + Vector2i(-1, 0))], ["", ""])
	t.eq(state.inventory.count(&"seed_corn"), 4)
	# the axe clears what stands in the faced cell: the stump of the plan
	var stump := root.get_node("YSorted/Entities/Debris_4_8") as Node2D
	farmer.position = field.cell_center(Vector2i(4, 7))
	mode.hotbar.hold_item(&"farm_axe")
	t.ok(farmer.face_cell(Vector2i(3, 7)))
	t.ok(not _use(farmer), "nothing to clear to the west")
	t.ok(farmer.face_cell(Vector2i(4, 8)))
	t.ok(_use(farmer), "the stump to the south is cleared")
	t.ok(stump.is_queued_for_deletion())
	_cleanup()

func test_the_can_fills_at_the_water_ahead(t) -> void:
	var farm := _farm(t)
	var farmer: RpgFarmer = farm["farmer"]
	var mode: RpgFarmMode = farm["mode"]
	var field: RpgField = farm["field"]
	mode.hotbar.hold_item(&"watering_can")
	farmer.position = field.cell_center(Vector2i(10, 4))  # the plan's place to fill it at
	RpgFarmWateringCan.set_charges(0)
	var before := mode.energy.value
	t.ok(farmer.face_cell(Vector2i(11, 4)))
	t.ok(not _use(farmer), "the cell to the east is ground")
	t.ok(farmer.face_cell(Vector2i(10, 3)))
	t.ok(field.is_water(farmer.tile_ahead()), "the cell to the north is the pond")
	t.ok(_use(farmer), "filled at the water ahead")
	t.eq(RpgFarmWateringCan.charges(), RpgFarmWateringCan.SIZE)
	t.eq(mode.energy.value, before, "filling costs nothing")
	t.ok(not _use(farmer), "a full can is not filled")
	# the rod is cast at the same cell: the water is the tile's, on any layer of the map
	var rod := RpgFarmRod.new()
	t.ok(not rod.can_use(field, farmer.tile_ahead()), "a rod without the game's fishing casts nothing")
	_cleanup()

func test_a_crop_stands_on_its_cell_and_sorts_with_the_farmer(t) -> void:
	var farm := _farm(t)
	var farmer: RpgFarmer = farm["farmer"]
	var field: RpgField = farm["field"]
	var cell := Vector2i(5, 8)
	t.ok(field.till(cell) and field.plant(cell, "corn"))
	var crop := field.crop_node(cell)
	t.ok(crop != null)
	t.eq(crop.get_parent(), farmer.get_parent(), "among the entities the farmer Y-sorts with")
	t.eq(crop.position, field.cell_center(cell), "on the middle of its diamond")
	t.eq(field.foot_of(cell), field.cell_center(cell))
	t.ok((crop.get_parent() as Node2D).y_sort_enabled)
	# who stands north or west of it is drawn before it (behind), who stands south or east after
	for side: String in ["n", "w"]:
		var by: Vector2i = RpgIso.STEPS[side]
		t.ok(field.cell_center(cell + by).y < crop.position.y, "a farmer to the %s is behind the crop" % side)
	for side: String in ["s", "e"]:
		var by: Vector2i = RpgIso.STEPS[side]
		t.ok(field.cell_center(cell + by).y > crop.position.y, "a farmer to the %s is in front of it" % side)
	# the scene of a crop: what `interact` finds is most of its diamond, around its foot
	var ctx := _context()
	var scene := CropRecipes.new()._scene(ctx, CROPS[0], {}, UNIT, FOOT)
	var shape := scene.get_node("Shape") as CollisionShape2D
	t.eq(shape.position, Vector2.ZERO)
	t.eq((shape.shape as ConvexPolygonShape2D).points, RpgFarmIso.diamond(FOOT, 0.8))
	scene.free()
	var flat := CropRecipes.new()._scene(ctx, CROPS[0], {}, 16)
	t.ok((flat.get_node("Shape") as CollisionShape2D).shape is RectangleShape2D, "seen from above it is the square it was")
	t.eq((flat.get_node("Shape") as CollisionShape2D).position, Vector2(0, -8))
	flat.free()
	_cleanup()

# ---------------------------------------------------------------- what blocks

func test_the_bed_the_bin_and_a_fence_block_their_diamonds(t) -> void:
	var farm := _farm(t, true)
	var root: Node2D = farm["root"]
	var farmer: RpgFarmer = farm["farmer"]
	var geo: MapGeo = farm["geo"]
	var ctx := _context()
	await _frames(2)
	# the bin: a crate on the middle of its cell
	var bin := root.get_node("YSorted/Entities/ShippingBin") as RpgShippingBin
	t.ok(bin != null, "the bin is the game's")
	t.ok(bin.get_collision_layer_value(1) and bin.get_collision_layer_value(5), "it blocks and is found by interact")
	var bin_shape := bin.get_node("Shape") as CollisionShape2D
	t.eq((bin_shape.shape as ConvexPolygonShape2D).points, RpgFarmIso.diamond(FOOT))
	t.ok(_inside(bin_shape, geo.center(Vector2i(8, 3))) and not _inside(bin_shape, geo.center(Vector2i(8, 4))))
	t.ok(bin.get_node_or_null("Sprite/Crate") != null and bin.get_node_or_null("Sprite/Lid") != null, "drawn as a crate with a lid")
	# walking at it from the cell before it: the farmer stays out of its cell
	farmer.global_position = geo.center(Vector2i(8, 4))
	await _frames(2)
	var entered := false
	for i in 60:
		farmer.move_dir(RpgIso.step("n", FOOT).normalized())
		await Fixtures.tree().physics_frame
		entered = entered or farmer.map_cell() == Vector2i(8, 3)
	farmer.move_dir(Vector2.ZERO)
	t.ok(not entered, "the bin blocks its diamond (the farmer slides along its side)")
	# a fence: the farmer walks at it from inside the yard and stays inside
	farmer.global_position = geo.center(Vector2i(12, 11))
	await _frames(2)
	var left := false
	for i in 90:
		farmer.move_dir(RpgIso.step("w", FOOT).normalized())
		await Fixtures.tree().physics_frame
		left = left or not Rect2i(12, 10, 3, 2).has_point(farmer.map_cell())
	farmer.move_dir(Vector2.ZERO)
	t.ok(not left, "a fence blocks its diamond: who walks at it stays in the yard")
	# ... and walks out through the gate
	farmer.global_position = geo.center(Vector2i(13, 11))
	await _frames(2)
	for i in 60:
		farmer.move_dir(RpgIso.step("s", FOOT).normalized())
		await Fixtures.tree().physics_frame
	farmer.move_dir(Vector2.ZERO)
	t.ok(farmer.map_cell().y >= 12, "the gate is walked through")
	# the bed, in the room of the house: two cells, its foot nearest the camera
	var issues: Array = []
	var room := FarmMap.new().room_root(ctx, HOUSE, issues)
	t.eq(issues, [])
	_made.append(room)
	t.ok(RpgIso.is_iso((room.get_node("Ground") as TileMapLayer).tile_set), "the room is painted with the same diamonds")
	var bed := room.get_node("YSorted/Entities/Bed") as RpgBed
	t.eq(bed.footprint, Vector2i(1, 2))
	t.eq(bed.position, geo.center(Vector2i(1, 2)), "its origin is the middle of the cell of its foot")
	var bed_shape := bed.get_node("Shape") as CollisionShape2D
	for cell: Vector2i in [Vector2i(1, 1), Vector2i(1, 2)]:
		t.ok(_inside(bed_shape, geo.center(cell)), "the bed blocks %s" % cell)
	for cell: Vector2i in [Vector2i(2, 2), Vector2i(1, 3), Vector2i(2, 1)]:
		t.ok(not _inside(bed_shape, geo.center(cell)), "and not %s" % cell)
	t.eq(bed.position + bed.wake_offset, geo.center(Vector2i(2, 2)), "the farmer wakes on the plan's cell beside it")
	t.eq((room.get_node("SpawnPoints/start") as Node2D).position, geo.center(Vector2i(2, 2)))
	t.eq((room.get_node("YSorted/Entities/Player") as Node2D).position, geo.center(Vector2i(2, 2)))
	t.ok(bed.y_sort_enabled and bed.get_node("Left").get_child_count() > 0 and bed.get_node("Right").get_child_count() > 0, "drawn in two halves that sort apart")
	t.eq((room.get_node("Triggers/Exit") as Area2D).position, geo.center(Vector2i(3, 6)))
	# the room of the coop: the markers the animals' house finds its things by
	var coop_room := FarmMap.new().room_root(ctx, COOP, issues)
	_made.append(coop_room)
	t.eq((coop_room.get_node("Markers/Trough") as Node2D).position, geo.center(Vector2i(1, 1)))
	t.eq((coop_room.get_node("Markers/Stall2") as Node2D).position, geo.center(Vector2i(4, 1)))
	var trough := RpgFarmTrough.make("coop", UNIT, FOOT)
	t.eq(((trough.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points, RpgFarmIso.diamond(FOOT), "a trough blocks its diamond")
	t.ok(trough.get_node_or_null("Feed") != null and not (trough.get_node("Feed") as CanvasItem).visible)
	trough.free()
	# the sign of the weather blocks the middle of its cell
	var sign := HudRecipe.build_sign(ctx)
	t.eq(((sign.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points, RpgFarmIso.diamond(FOOT, 0.5))
	sign.free()
	_cleanup()
	await _frames(2)

func test_an_animal_keeps_to_the_cells_of_its_yard(t) -> void:
	var layer := TileMapLayer.new()
	var tiles := TileSet.new()
	tiles.tile_shape = TileSet.TILE_SHAPE_ISOMETRIC
	tiles.tile_layout = TileSet.TILE_LAYOUT_DIAMOND_DOWN
	tiles.tile_size = FOOT
	layer.tile_set = tiles
	var yard := Rect2i(12, 10, 3, 2)
	t.eq(RpgFarmIso.world_of(layer, Vector2(12.5, 10.5)), RpgIso.cell_to_screen(Vector2i(12, 10), FOOT), "the middle of a cell")
	t.ok(RpgFarmIso.grid_of(layer, RpgIso.cell_to_screen(Vector2i(13, 11), FOOT)).distance_to(Vector2(13.5, 11.5)) < 0.0001)
	var hen := RpgFarmAnimal.new()
	hen.position = RpgIso.cell_to_screen(Vector2i(13, 10), FOOT)
	hen.roam_cells(layer, yard)
	t.ok(hen.is_roaming())
	t.eq(hen.roaming_cells(), Rect2(12.25, 10.25, 2.5, 1.5), "a quarter of a cell from the fence")
	# pushed out of the yard it is put back on its edge; inside it is left where it is
	hen.position = RpgIso.cell_to_screen(Vector2i(20, 3), FOOT)
	hen.wander(0.0)
	var at := RpgFarmIso.grid_of(layer, hen.position)
	t.ok(at.distance_to(Vector2(14.75, 10.25)) < 0.001, "kept in: %s" % at)
	var inside := RpgIso.cell_to_screen(Vector2i(13, 11), FOOT)
	hen.position = inside
	hen.wander(0.0)
	t.eq(hen.position, inside)
	# where it walks to next is a place of the yard
	for i in 40:
		hen._timer = 0.0
		hen._walking = false
		hen.wander(0.1)
		var goal := RpgFarmIso.grid_of(layer, hen._goal)
		t.ok(hen.roaming_cells().grow(0.001).has_point(goal), "a goal in the yard: %s" % goal)
	# seen from above nothing changed: a rectangle of the world
	hen.roam(Rect2(10, 10, 40, 30))
	t.eq(hen.roaming_cells(), Rect2())
	t.eq(hen.roaming_ground(), Rect2(10, 10, 40, 30))
	hen.free()
	layer.free()

# ---------------------------------------------------------------- the boxes

func test_boxes_on_a_diamond(t) -> void:
	t.eq(RpgFarmIso.point(0.5, 0.5, FOOT), Vector2.ZERO, "the middle of the cell")
	t.eq(RpgFarmIso.point(0, 0, FOOT), Vector2(0, -17), "its top corner")
	t.eq(RpgFarmIso.point(1, 0, FOOT), Vector2(30, 0))
	t.eq(RpgFarmIso.point(1, 1, FOOT), Vector2(0, 17), "the corner nearest the camera")
	t.eq(RpgFarmIso.point(0, 1, FOOT), Vector2(-30, 0))
	t.eq(RpgFarmIso.point(0.5, 1.5, FOOT), RpgIso.step("s", FOOT), "the middle of the cell to the south")
	t.eq(RpgFarmIso.diamond(FOOT), PackedVector2Array([Vector2(0, -17), Vector2(30, 0), Vector2(0, 17), Vector2(-30, 0)]))
	t.eq(RpgFarmIso.diamond_shape(FOOT, 0.5).points, PackedVector2Array([Vector2(0, -8.5), Vector2(15, 0), Vector2(0, 8.5), Vector2(-15, 0)]))
	var faces := RpgFarmIso.box_faces(0, 0, 1, 1, 2.0, 10.0, FOOT)
	t.eq(faces["top"], PackedVector2Array([Vector2(0, -29), Vector2(30, -12), Vector2(0, 5), Vector2(-30, -12)]), "the diamond, lifted")
	t.eq(faces["left"], PackedVector2Array([Vector2(-30, -12), Vector2(0, 5), Vector2(0, 15), Vector2(-30, -2)]), "the face that looks south")
	t.eq(faces["right"], PackedVector2Array([Vector2(0, 5), Vector2(30, -12), Vector2(30, -2), Vector2(0, 15)]), "the face that looks east")
	var box := RpgFarmIso.box("Crate", 0.2, 0.2, 0.8, 0.8, 0.0, 12.0, Color.RED, FOOT)
	t.eq([box.get_child(0).name, box.get_child(1).name, box.get_child(2).name], [&"Left", &"Right", &"Top"], "the top is drawn last")
	t.ok((box.get_node("Right") as Polygon2D).color.v < (box.get_node("Left") as Polygon2D).color.v, "the east face is in shade")
	box.free()
	# a polygon cut at a line: what a thing of several cells needs to sort in two halves
	var square := PackedVector2Array([Vector2(-10, -5), Vector2(20, -5), Vector2(20, 5), Vector2(-10, 5)])
	t.eq(RpgFarmIso.clip_x(square, 0.0, true), PackedVector2Array([Vector2(-10, -5), Vector2(0, -5), Vector2(0, 5), Vector2(-10, 5)]))
	t.eq(RpgFarmIso.clip_x(square, 0.0, false), PackedVector2Array([Vector2(0, -5), Vector2(20, -5), Vector2(20, 5), Vector2(0, 5)]))
	t.eq(RpgFarmIso.clip_x(square, -30.0, true).size(), 0, "nothing on that side")
	var root := Node2D.new()
	var parts := RpgFarmIso.halves(root, Vector2i(3, 2), FOOT)
	var keys := RpgIso.sort_keys(Rect2i(0, 0, 3, 2), FOOT)
	var origin := RpgIso.cell_to_screen(Vector2i(2, 1), FOOT)
	t.ok(root.y_sort_enabled)
	t.near(origin.y + (parts["left"] as Node2D).position.y, keys[1], 0.0001, "the left half sorts by the left corner")
	t.near(origin.y + (parts["right"] as Node2D).position.y, keys[2], 0.0001, "the right half by the right corner")
	RpgFarmIso.add_box(parts, "Wall", -2.0, -1.0, 1.0, 1.0, 0.0, 20.0, Color.WHITE, FOOT)
	var left := parts["left"] as Node2D
	var right := parts["right"] as Node2D
	t.ok(left.get_node_or_null("WallLeft") != null and left.get_node_or_null("WallRight") == null, "the south face is all in the left half")
	t.ok(right.get_node_or_null("WallRight") != null and right.get_node_or_null("WallLeft") == null, "the east face in the right one")
	t.ok(left.get_node_or_null("WallTop") != null and right.get_node_or_null("WallTop") != null, "the top is cut in two")
	for at in (left.get_node("WallTop") as Polygon2D).polygon:
		t.ok(at.x <= 0.0001, "left of the corner nearest the camera")
	root.free()
