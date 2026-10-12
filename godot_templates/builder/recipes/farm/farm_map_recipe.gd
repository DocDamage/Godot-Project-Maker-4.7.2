extends RefCounted
## The farm's own maps (T17.06), built from the stored plan (`rpggen/world_plan.json`, the
## section `farm.map`, planned by rpggen/core/farm_plan.py). Each is seeded once (user_seed
## ownership): a map that exists is never built again, and the plan it was built from is kept.
##
## * game/maps/farm.tscn, the farm: the layers of a top-down map, the `Soil` layer and the
##   `Field` (field_recipe.add_field) with the plan's `tillable` cells written as the tile that
##   says so, and on it what the plan names: the farmhouse and the animal houses (a building of
##   the packs when one has the plan's footprint, else a drawn one), each with its door; the
##   yards with their fences and gates; the water (the packs' water tile for a pond, a well as
##   an object), which fills the can; the shipping bin; what the axe and the sickle clear;
##   trees and scenery; the way out to the village.
## * game/maps/<id>.tscn for every building of the plan (`farm_house`, `farm_coop`,
##   `farm_barn`): the room of the plan, with the bed (the farmhouse; a new game starts beside
##   it, at the spawn `start`) or the trough and the stalls as markers (an animal house).
##
## The interior recipe of the top-down kinds is not used for these rooms: it makes one room
## for every house of the starter map, all of one size, and cannot take a planned one.
##
## **What other recipes find here** (T17.07 builds on it): on the farm, `Yards/<Kind>` (a
## Node2D at the yard's first cell with the metadata `kind`, `yard` (Rect2i, cells), `gate`
## (Vector2i), `stalls` (int) and `house_map` (the scene of the room)), `Markers/WaterFill`,
## `Markers/BinFront` and `Markers/HouseDoor`, and the weather's sign `WeatherSign` (T17.11); in a room, `Markers/Trough` and
## `Markers/Stall1` ... `Markers/Stall<n>`. The places where things to forage lie (T17.10) are
## the markers `Forage/Spot1` ... of the farm, at the cells `farm.forage.spots` of the plan
## (forage_recipe.add_places).

const RECIPE_VERSION := 2

const Paths := preload("../../lib/paths.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const SceneUtil := preload("../../lib/scene_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const MapBuild := preload("../../lib/map_build.gd")
const TextureUtil := preload("../../lib/texture_util.gd")
const ObjectEntries := preload("../../lib/object_entries.gd")
const ObjectIndex := preload("../../lib/object_index.gd")
const BuildContext := preload("../../lib/build_context.gd")
const InteriorRecipe := preload("../interior_recipe.gd")
const FarmBuild := preload("farm_build.gd")
const FieldRecipe := preload("field_recipe.gd")
const HomeRecipe := preload("home_recipe.gd")
const HudRecipe := preload("hud_recipe.gd")
const ForageRecipe := preload("forage_recipe.gd")

const MAPS_DIR := "res://game/maps/"
const MAP_ID := "farm"
const FARM_PATH := MAPS_DIR + "farm.tscn"
const VILLAGE_PATH := MAPS_DIR + "starter_map.tscn"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const TILESET_PATH := "res://generated/tilesets/overworld.tres"
const WORLD_OBJECT := "res://addons/rpg_runtime/world/world_object.gd"
const PERSISTENT := "res://addons/rpg_runtime/world/persistent.gd"

## The door pair between the farm and the village: the farm's way out is the door `to_village`
## and leads to the village's spawn `from_farm`; the village's door `to_farm`
## (people_recipes.gd) leads to the farm's spawn `from_village`.
const EXIT_NAME := "to_village"
const FROM_VILLAGE := "from_village"
const FROM_FARM := "from_farm"
## Where a new game starts, in the farmhouse.
const START_SPAWN := "start"
## What a tool clears says what it is with this metadata (RpgField.CLEAR_META).
const CLEAR_META := &"farm_clear"
## What of the plan the farmer cannot walk through (farm_plan.BLOCKING, and a tree).
const BLOCKING: Array[String] = ["branch", "stump", "bush", "rock", "tree"]

## The words a picture of the packs (a DECORATION object) is known by, by what it is.
const WORDS := {
	"tree": ["tree", "trees", "pine", "oak"],
	"bush": ["bush", "bushes", "shrub"],
	"rock": ["rock", "rocks", "stone", "boulder"],
	"flowers": ["flower", "flowers"],
	"branch": ["branch", "branches", "twig", "log"],
	"stump": ["stump"],
	"grass": ["grass", "weed", "weeds"],
	"fence": ["fence"],
	"well": ["well"],
}
## The most cells a picture of the packs may be wide and high to stand for a thing of one cell.
const MOST_CELLS := Vector2i(2, 2)
const MOST_TREE_CELLS := Vector2i(4, 6)

const WOOD := Color(0.5, 0.33, 0.18)
const WOOD_LIGHT := Color(0.72, 0.56, 0.36)
const LEAF := Color(0.22, 0.5, 0.2)
const LEAF_DARK := Color(0.16, 0.38, 0.17)
const GRASS := Color(0.45, 0.7, 0.3)
const STONE := Color(0.55, 0.56, 0.6)
const STONE_LIGHT := Color(0.74, 0.75, 0.78)
const PETAL := Color(0.92, 0.5, 0.65)
const WATER := Color(0.27, 0.5, 0.78)
const ROOF := Color(0.62, 0.24, 0.2)
const DOOR := Color(0.25, 0.16, 0.1)
const WALLS := {"house": Color(0.85, 0.78, 0.62), "coop": Color(0.8, 0.66, 0.42), "barn": Color(0.66, 0.3, 0.24)}
## The drawn stand-in of a thing: boxes [wide, high, x of the middle, lift of the foot, colour]
## in cells, the foot of the thing at the origin.
const DRAWN := {
	"branch": [[0.8, 0.18, 0.0, 0.1, WOOD], [0.25, 0.14, 0.2, 0.28, WOOD]],
	"stump": [[0.5, 0.4, 0.0, 0.0, WOOD], [0.5, 0.1, 0.0, 0.4, WOOD_LIGHT]],
	"grass": [[0.6, 0.3, 0.0, 0.0, GRASS], [0.2, 0.25, -0.15, 0.3, GRASS], [0.15, 0.2, 0.2, 0.3, GRASS]],
	"tree": [[0.25, 0.6, 0.0, 0.0, WOOD], [1.2, 0.9, 0.0, 0.5, LEAF], [0.8, 0.35, 0.0, 1.4, LEAF]],
	"bush": [[0.8, 0.5, 0.0, 0.0, LEAF_DARK], [0.5, 0.2, 0.0, 0.5, LEAF_DARK]],
	"rock": [[0.7, 0.4, 0.0, 0.0, STONE], [0.4, 0.15, -0.05, 0.4, STONE_LIGHT]],
	"flowers": [[0.5, 0.12, 0.0, 0.0, GRASS], [0.15, 0.15, -0.15, 0.12, PETAL], [0.15, 0.15, 0.15, 0.2, PETAL]],
	"fence": [[0.18, 0.8, 0.0, 0.0, WOOD], [1.0, 0.14, 0.0, 0.5, WOOD_LIGHT], [1.0, 0.14, 0.0, 0.22, WOOD_LIGHT]],
	"gate": [[0.16, 0.9, -0.42, 0.0, WOOD], [0.16, 0.9, 0.42, 0.0, WOOD]],
	"well": [[0.9, 0.5, 0.0, 0.0, STONE], [0.6, 0.18, 0.0, 0.5, WATER], [0.9, 0.1, 0.0, 0.68, STONE_LIGHT]],
}

# ---------------------------------------------------------------- the plan

## The farm's map of the stored plan (`farm.map`), or {}.
static func plan() -> Dictionary:
	return JsonUtil.to_dict(FarmBuild.plan().get("map", {}))

## [x, y] of a plan as a cell.
static func cell_of(value: Variant) -> Vector2i:
	var pair := JsonUtil.to_array(value)
	return Vector2i(JsonUtil.to_int(pair[0]), JsonUtil.to_int(pair[1])) if pair.size() == 2 else Vector2i.ZERO

## [x, y, w, h] of a plan as a rectangle of cells.
static func rect_of(value: Variant) -> Rect2i:
	var four := JsonUtil.to_array(value)
	if four.size() != 4:
		return Rect2i()
	return Rect2i(JsonUtil.to_int(four[0]), JsonUtil.to_int(four[1]), JsonUtil.to_int(four[2]), JsonUtil.to_int(four[3]))

## A list of [x, y] of a plan as cells.
static func cells_of(value: Variant) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for raw: Variant in JsonUtil.to_array(value):
		out.append(cell_of(raw))
	return out

## The buildings of a plan: the house, then the animal houses.
static func buildings_of(farm: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var house := JsonUtil.to_dict(farm.get("house", {}))
	if not house.is_empty():
		out.append(house)
	for raw: Variant in JsonUtil.to_array(farm.get("animal_houses", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

## The id of the room of a building (`farm_house`): the id of its map.
static func room_id(building: Dictionary) -> String:
	var room := JsonUtil.to_dict(building.get("interior", {}))
	return JsonUtil.to_str(room.get("id", building.get("id", "")))

static func room_path(building: Dictionary) -> String:
	return MAPS_DIR + room_id(building) + ".tscn"

## The spawn in front of the door of a building, on the farm.
static func door_spawn(building_id: String) -> String:
	return building_id + "_door"

## The maps a plan asks for: the farm, then the room of every building.
static func map_paths(farm: Dictionary) -> Array[String]:
	var out: Array[String] = []
	if farm.is_empty():
		return out
	out.append(FARM_PATH)
	for building in buildings_of(farm):
		out.append(room_path(building))
	return out

## Where a new game of this plan starts: {map: the scene, spawn: the id}; {} without a plan.
static func start_of(farm: Dictionary) -> Dictionary:
	var start := JsonUtil.to_dict(farm.get("start", {}))
	if start.is_empty():
		return {}
	return {"map": MAPS_DIR + JsonUtil.to_str(start.get("map", "")) + ".tscn", "spawn": START_SPAWN}

## The cell the farmer starts on and wakes in: the plan's, or, when the bed of the packs is
## wider than the plan's and lies on it, the first cell east of the bed.
static func start_cell(planned: Vector2i, head: Vector2i, footprint: Vector2i, room: Vector2i) -> Vector2i:
	var bed := Rect2i(head, footprint)
	if not bed.has_point(planned):
		return planned
	return Vector2i(mini(bed.end.x, room.x - 2), clampi(planned.y, head.y, bed.end.y - 1))

## The water cell the can is filled at from `fill`: the one beside it (north first), else the
## nearest.
static func water_beside(fill: Vector2i, water: Array[Vector2i]) -> Vector2i:
	for step: Vector2i in [Vector2i.UP, Vector2i.LEFT, Vector2i.RIGHT, Vector2i.DOWN]:
		if water.has(fill + step):
			return fill + step
	var best := fill
	var best_distance := -1
	for cell in water:
		var distance := absi(cell.x - fill.x) + absi(cell.y - fill.y)
		if best_distance < 0 or distance < best_distance:
			best = cell
			best_distance = distance
	return best

# ---------------------------------------------------------------- the packs

## The words of a name: "Oak-Tree_02" -> oak, tree, 02.
static func name_words(text: String) -> PackedStringArray:
	return text.to_lower().replace("-", "_").replace(" ", "_").replace(".", "_").split("_", false)

## The DECORATION objects of the packs that are a `kind` (a tree, a rock, ...): one of the
## kind's words is in their name or among their tags, and they are not larger than the thing.
static func thing_entries(entries: Array[Dictionary], kind: String, tile_px: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var words: Array = WORDS.get(kind, [])
	var most := MOST_TREE_CELLS if kind == "tree" else MOST_CELLS
	for entry in entries:
		if JsonUtil.to_str(entry.get("role", "")) != "DECORATION":
			continue
		var region: Array = entry.get("region", [])
		if region.size() != 4 or JsonUtil.to_int(region[2]) > most.x * tile_px or JsonUtil.to_int(region[3]) > most.y * tile_px:
			continue
		var named := name_words(JsonUtil.to_str(entry.get("name", "")))
		var tags: Array = entry.get("tags", [])
		for word: String in words:
			if named.has(word) or tags.has(word):
				out.append(entry)
				break
	return out

## The picture of the `index`-th thing of a kind: the packs' objects of the kind in turn, or
## null when they have none.
static func thing_texture(found: Array[Dictionary], index: int) -> Texture2D:
	if found.is_empty():
		return null
	var entry: Dictionary = found[index % found.size()]
	var region: Array = entry["region"]
	return TextureUtil.region_texture(JsonUtil.to_str(entry["texture_path"]), Rect2i(JsonUtil.to_int(region[0]), JsonUtil.to_int(region[1]), JsonUtil.to_int(region[2]), JsonUtil.to_int(region[3])))

## The building of the packs that stands for a building of the plan: a BUILDING object whose
## footprint (`cells`) and door column are the plan's. For the house the chosen starter
## building first, then any that is no coop and no barn, then the rest; for an animal house
## one tagged `coop` or `barn`. {} when none fits: the building is drawn.
static func building_entry(entries: Array[Dictionary], kind: String, cells: Vector2i, door_column: int, tile_px: int, chosen: String = "") -> Dictionary:
	var ranked: Array[Dictionary] = []
	var others: Array[Dictionary] = []
	for entry in entries:
		if JsonUtil.to_str(entry.get("role", "")) != "BUILDING":
			continue
		var tags: Array = entry.get("tags", [])
		var animal := tags.has("coop") or tags.has("barn")
		if kind != "house":
			if tags.has(kind):
				ranked.append(entry)
		elif JsonUtil.to_str(entry.get("id", "")) == chosen:
			ranked.push_front(entry)
		elif animal:
			others.append(entry)
		else:
			ranked.append(entry)
	ranked.append_array(others)
	for entry in ranked:
		var info := InteriorRecipe.building_info(entry, tile_px)
		var size := Vector2i(JsonUtil.to_int(info["size"][0]), JsonUtil.to_int(info["size"][1]))
		if size == cells and JsonUtil.to_int(info["door"][0]) == door_column:
			return entry
	return {}

# ---------------------------------------------------------------- the recipe

## Only the maps that do not exist yet: one that exists (and may have been edited) is kept.
func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for path in map_paths(plan()):
		if not FileAccess.file_exists(path):
			out.append(path)
	return out

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"map": plan(),
		"overworld": ctx.catalog.tileset_def("overworld"),
		"interior": ctx.catalog.tileset_def("interior"),
		"layers": ctx.config.get("map_layers", []),
		"starter": ctx.config.get("starter", {}),
		"ground": JsonUtil.to_str(ctx.section("starter_map").get("ground", "")),
		"music": JsonUtil.to_str(ctx.section("sounds").get("music_map", "")),
		"entries": ObjectEntries.entries(ctx),
		"bin": FarmBuild.bin_asset(ctx).get("id", ""),
		"bed": FarmBuild.bed_asset(ctx).get("id", ""),
		"sign": HudRecipe.sign_asset(ctx).get("id", ""),
		"field": FieldRecipe.RECIPE_VERSION,
		"forage": ForageRecipe.spots(),
	})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var farm := plan()
	if farm.is_empty():
		print("[rpggen] INFO farm_map: the project has no plan of its farm (rpggen/world_plan.json, farm.map)")
		return issues
	if not FileAccess.file_exists(FARM_PATH):
		_build_farm(ctx, farm, issues)
	for building in buildings_of(farm):
		if not FileAccess.file_exists(room_path(building)):
			_build_room(ctx, building, issues)
	return issues

# ---------------------------------------------------------------- the farm

func _ground_tile(ctx: BuildContext, def: Dictionary, tile_set: TileSet) -> Dictionary:
	var wanted := JsonUtil.to_str(ctx.section("starter_map").get("ground", ""))
	if wanted == "":
		wanted = JsonUtil.to_str(ctx.section("starter").get("ground", ""))
	if wanted != "":
		var tile := MapUtil.tile_of_asset(ctx, def, tile_set, wanted)
		if not tile.is_empty():
			return tile
	return MapUtil.find_tile(ctx, def, tile_set, "GROUND")

func _build_farm(ctx: BuildContext, farm: Dictionary, issues: Array) -> void:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, FARM_PATH))
		return
	var tile_set := load(TILESET_PATH) as TileSet
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": TILESET_PATH}, TILESET_PATH))
		return
	if not ResourceLoader.exists(PLAYER_SCENE):
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		return
	var tile_px: int = JsonUtil.to_int(def["tile_size"][0])
	var size := cell_of(farm.get("size"))
	var root := MapUtil.new_map_root("Farm", MAP_ID)
	root.set("music_asset_id", JsonUtil.to_str(ctx.section("sounds").get("music_map", "")))
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var ground: TileMapLayer = nodes["Ground"]
	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var triggers: Node2D = nodes["Triggers"]

	# the ground, the paths on it, the water of a pond, and the edge with its one gap
	MapBuild.fill_ground(ground, size, _ground_tile(ctx, def, tile_set))
	if nodes.has("GroundDetails"):
		var details: TileMapLayer = nodes["GroundDetails"]
		MapBuild.paint_path(details, cells_of(farm.get("paths")), MapUtil.find_tile(ctx, def, tile_set, "ROAD"))
	var water := JsonUtil.to_dict(farm.get("water", {}))
	var water_cells := cells_of(water.get("cells"))
	var pond := JsonUtil.to_str(water.get("kind", "")) == "pond"
	var water_tile: Dictionary = MapUtil.find_tile(ctx, def, tile_set, "WATER") if pond else {}
	if not water_tile.is_empty():
		for cell in water_cells:
			MapUtil.put(ground, cell, water_tile)
	var way_out := JsonUtil.to_dict(farm.get("exit", {}))
	var gap := cell_of(way_out.get("cell"))
	var skip: Array[Vector2i] = []
	if not way_out.is_empty():
		skip.append(gap)
	MapBuild.paint_walls(root, nodes, size, MapUtil.wall_tile(ctx, def, tile_set), tile_px, skip)

	# the field: what can be tilled and where the can is filled are written into the tiles
	var soil := FieldRecipe.add_field(root, nodes)
	if soil == null:
		issues.append(ctx.make_issue("VAL-002", {"file": FarmBuild.SOIL_TILESET}, FarmBuild.SOIL_TILESET))
		root.free()
		return
	for cell in cells_of(farm.get("tillable")):
		soil.set_cell(cell, FieldRecipe.SOURCE_ID, FieldRecipe.PLOT_TILE)
	# a pond without a water tile of the packs is drawn; the others show through
	var water_mark := FieldRecipe.WATER_TILE if pond and water_tile.is_empty() else FieldRecipe.WATER_MARK
	for cell in water_cells:
		soil.set_cell(cell, FieldRecipe.SOURCE_ID, water_mark)

	var entries := ObjectEntries.entries(ctx)
	var markers := Node2D.new()
	SceneUtil.add(root, markers, root, "Markers")
	var chosen := JsonUtil.to_str(ctx.section("starter").get("building", ""))
	for building in buildings_of(farm):
		_add_building(building, root, nodes, tile_px, entries, chosen)
		_add_yard(building, root, entities, tile_px, entries)
	_add_water(water, water_cells, root, entities, markers, tile_px, entries)
	_add_bin(ctx, farm, root, entities, markers, tile_px)
	_add_sign(ctx, farm, root, entities, tile_px)
	_add_things(farm, root, entities, tile_px, entries)
	ForageRecipe.add_places(root, tile_px)

	if not way_out.is_empty():
		MapUtil.add_marker(spawns, root, FROM_VILLAGE, MapUtil.tile_center(cell_of(way_out.get("spawn")), tile_px), true, JsonUtil.to_str(way_out.get("facing", "down")))
		MapBuild.add_exit_door(triggers, root, EXIT_NAME, gap, tile_px, VILLAGE_PATH, StringName(FROM_FARM))
	var door := cell_of(JsonUtil.to_dict(farm.get("house", {})).get("door"))
	MapUtil.add_marker(markers, root, "HouseDoor", MapUtil.tile_center(door, tile_px))
	MapUtil.add_marker(spawns, root, "default", MapUtil.tile_center(door, tile_px), true)
	MapUtil.place(PLAYER_SCENE, entities, root, MapUtil.tile_center(door, tile_px))
	var err := SceneUtil.save_scene(root, FARM_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": FARM_PATH, "err": err}, FARM_PATH))

## A building of the plan on its footprint, with the door into its room and the spawn in front
## of it where the farmer comes out again.
func _add_building(building: Dictionary, root: Node2D, nodes: Dictionary, tile_px: int, entries: Array[Dictionary], chosen: String) -> void:
	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var triggers: Node2D = nodes["Triggers"]
	var rect := rect_of(building.get("rect"))
	var door := cell_of(building.get("door"))
	var kind := JsonUtil.to_str(building.get("kind", "house"))
	var node_name := kind.capitalize()
	var spawn_id := door_spawn(JsonUtil.to_str(building.get("id", "")))
	var column := door.x - rect.position.x
	var entrance: Node = null
	var exit_spawn: Node = null
	var entry := building_entry(entries, kind, rect.size, column, tile_px, chosen)
	var scene := ObjectIndex.scene_path(JsonUtil.to_str(entry["id"])) if not entry.is_empty() else ""
	var placed: Node2D = null
	if scene != "" and ResourceLoader.exists(scene):
		var origin := Vector2(JsonUtil.to_float(entry["origin"][0]), JsonUtil.to_float(entry["origin"][1]))
		placed = MapUtil.place(scene, entities, root, Vector2(rect.position) * tile_px + origin, node_name)
	if placed != null:
		# properties of nodes inside an instanced scene are saved only when it is editable
		root.set_editable_instance(placed, true)
		entrance = placed.get_node_or_null("Entrance")
		exit_spawn = placed.get_node_or_null("ExitSpawn")
	else:
		var drawn := drawn_building(kind, rect.size, column, tile_px)
		drawn.position = Vector2((rect.position.x + rect.size.x * 0.5) * tile_px, rect.end.y * tile_px)
		SceneUtil.add(entities, drawn, root, node_name)
	if entrance == null:
		# the door lies on the lower edge of the building and reaches a little into the cell
		# before it, as the door of a building of the packs does
		entrance = add_door(triggers, root, node_name + "Door", Vector2((door.x + 0.5) * tile_px, door.y * tile_px + 3.0), Vector2(tile_px * 0.75, tile_px * 0.5))
	entrance.set("target_map", room_path(building))
	entrance.set("target_spawn", &"default")
	if exit_spawn != null:
		exit_spawn.set("spawn_id", StringName(spawn_id))
	else:
		MapUtil.add_marker(spawns, root, spawn_id, Vector2((door.x + 0.5) * tile_px, (door.y + 1) * tile_px - 1.0), true)

## A door (RpgDoor) of `size` px at `at`: walked into, it sends the player to another map.
static func add_door(parent: Node, root: Node, node_name: String, at: Vector2, size: Vector2) -> Area2D:
	var door := Area2D.new()
	SceneUtil.attach_script(door, MapUtil.DOOR_SCRIPT)
	door.collision_layer = 0
	door.collision_mask = 0
	door.set_collision_layer_value(6, true)  # triggers
	door.set_collision_mask_value(2, true)  # player
	door.position = at
	SceneUtil.add(parent, door, root, node_name)
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = size
	shape.shape = rect
	door.add_child(shape)
	return door

## A building nobody drew: walls, a roof and a door, solid over its whole footprint. Its origin
## is the middle of its lower edge.
static func drawn_building(kind: String, cells: Vector2i, door_column: int, tile_px: int) -> StaticBody2D:
	var size := Vector2(cells) * tile_px
	var body := StaticBody2D.new()
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)  # world
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = size
	shape.shape = rect
	shape.position = Vector2(0.0, -size.y * 0.5)
	body.add_child(shape)
	var wall_colour: Color = WALLS.get(kind, WALLS["house"])
	body.add_child(FarmBuild.stand_in("Wall", Vector2(size.x, size.y * 0.55), wall_colour))
	var roof := FarmBuild.stand_in("Roof", Vector2(size.x, size.y * 0.45), ROOF)
	roof.position = Vector2(0.0, -size.y * 0.55)
	body.add_child(roof)
	var door := FarmBuild.stand_in("Door", Vector2(tile_px * 0.75, minf(tile_px, size.y * 0.5)), DOOR)
	door.position = Vector2((door_column + 0.5) * tile_px - size.x * 0.5, 0.0)
	body.add_child(door)
	return body

## The yard of an animal house: a piece of fence on every cell of the plan's fence, the gate
## (which is walked through), and the node the animals' recipe finds it by.
func _add_yard(building: Dictionary, root: Node2D, entities: Node2D, tile_px: int, entries: Array[Dictionary]) -> void:
	var yard := JsonUtil.to_dict(building.get("yard", {}))
	if yard.is_empty():
		return
	var kind := JsonUtil.to_str(building.get("kind", ""))
	var holder := root.get_node_or_null("Yards")
	if holder == null:
		holder = SceneUtil.add(root, Node2D.new(), root, "Yards")
	var rect := rect_of(yard.get("rect"))
	var room := JsonUtil.to_dict(building.get("interior", {}))
	var node := Node2D.new()
	node.position = Vector2(rect.position) * tile_px
	node.set_meta(&"kind", kind)
	node.set_meta(&"yard", rect)
	node.set_meta(&"gate", cell_of(yard.get("gate")))
	node.set_meta(&"stalls", JsonUtil.to_array(room.get("stalls", [])).size())
	node.set_meta(&"house_map", room_path(building))
	SceneUtil.add(holder, node, root, kind.capitalize())
	var pictures := thing_entries(entries, "fence", tile_px)
	var index := 0
	for cell in cells_of(yard.get("fence")):
		var piece := make_thing("fence", thing_texture(pictures, index), tile_px, true)
		piece.position = HomeRecipe.foot_of(cell, tile_px)
		SceneUtil.add(entities, piece, root, "Fence_%s_%d_%d" % [kind, cell.x, cell.y])
		index += 1
	var gate := make_thing("gate", null, tile_px, false)
	gate.position = HomeRecipe.foot_of(cell_of(yard.get("gate")), tile_px)
	SceneUtil.add(entities, gate, root, "Gate_%s" % kind)

## The water: one body over its cells that is solid and fills the can with `interact` (the
## tiles under it fill it with `use`), a picture when it is a well, and the place to stand.
func _add_water(water: Dictionary, cells: Array[Vector2i], root: Node2D, entities: Node2D, markers: Node2D, tile_px: int, entries: Array[Dictionary]) -> void:
	if cells.is_empty():
		return
	var kind := JsonUtil.to_str(water.get("kind", "pond"))
	var fill := cells[cells.size() - 1] + Vector2i.DOWN
	if JsonUtil.to_array(water.get("fill")).size() == 2:
		fill = cell_of(water.get("fill"))
	var body := StaticBody2D.new()
	SceneUtil.attach_script(body, FarmBuild.WATER_SOURCE)
	body.set("kind", kind)
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)  # world
	body.set_collision_layer_value(5, true)  # interactables
	# its origin is the foot of the cell the can is filled at: the key hint stands over it
	body.position = HomeRecipe.foot_of(water_beside(fill, cells), tile_px)
	for cell in cells:
		var shape := CollisionShape2D.new()
		shape.name = "Cell_%d_%d" % [cell.x, cell.y]
		var rect := RectangleShape2D.new()
		rect.size = Vector2(tile_px, tile_px)
		shape.shape = rect
		shape.position = MapUtil.tile_center(cell, tile_px) - body.position
		body.add_child(shape)
	if kind == "well":
		body.add_child(picture("well", thing_texture(thing_entries(entries, "well", tile_px), 0), tile_px))
	SceneUtil.add(entities, body, root, "Water")
	MapUtil.add_marker(markers, root, "WaterFill", MapUtil.tile_center(fill, tile_px))

func _add_bin(ctx: BuildContext, farm: Dictionary, root: Node2D, entities: Node2D, markers: Node2D, tile_px: int) -> void:
	var bin_plan := JsonUtil.to_dict(farm.get("bin", {}))
	if bin_plan.is_empty():
		return
	var at := HomeRecipe.foot_of(cell_of(bin_plan.get("cell")), tile_px)
	if MapUtil.place(HomeRecipe.BIN_SCENE, entities, root, at) == null:
		var bin := HomeRecipe.build_bin(ctx)
		bin.position = at
		SceneUtil.add(entities, bin, root, HomeRecipe.BIN_NAME)
	MapUtil.add_marker(markers, root, "BinFront", MapUtil.tile_center(cell_of(bin_plan.get("front")), tile_px))

## The cell of the sign that tells tomorrow's weather: beside the cell before the door of the
## house (east first), where no path runs and the bin does not stand. (-1, -1) when both
## sides are taken.
static func sign_cell(farm: Dictionary) -> Vector2i:
	var door := cell_of(JsonUtil.to_dict(farm.get("house", {})).get("door"))
	var taken := cells_of(farm.get("paths"))
	var bin_plan := JsonUtil.to_dict(farm.get("bin", {}))
	taken.append(cell_of(bin_plan.get("cell")))
	taken.append(cell_of(bin_plan.get("front")))
	for step: Vector2i in [Vector2i.RIGHT, Vector2i.LEFT]:
		if not taken.has(door + step):
			return door + step
	return Vector2i(-1, -1)

## The weather's sign (T17.11, hud_recipe.build_sign: the generated scene is made after this
## map), by the door of the house.
func _add_sign(ctx: BuildContext, farm: Dictionary, root: Node2D, entities: Node2D, tile_px: int) -> void:
	var cell := sign_cell(farm)
	if cell.x < 0:
		print("[rpggen] INFO farm_map: no room for the weather's sign by the door of the house")
		return
	var sign := HudRecipe.build_sign(ctx)
	sign.position = HomeRecipe.foot_of(cell, tile_px)
	SceneUtil.add(entities, sign, root, String(sign.name))

## What lies and stands about: the things to clear (each remembered once it is cleared), the
## trees and the scenery.
func _add_things(farm: Dictionary, root: Node2D, entities: Node2D, tile_px: int, entries: Array[Dictionary]) -> void:
	var pictures := {}
	for kind: String in WORDS.keys():
		pictures[kind] = thing_entries(entries, kind, tile_px)
	var counts := {}
	for raw: Variant in JsonUtil.to_array(farm.get("debris", [])):
		var thing := JsonUtil.to_dict(raw)
		var kind := JsonUtil.to_str(thing.get("kind", ""))
		var cell := cell_of(thing.get("cell"))
		var node := _thing(kind, pictures, counts, tile_px)
		node.set_meta(CLEAR_META, kind)
		node.set("entity_id", "farm_debris_%d_%d" % [cell.x, cell.y])
		var persistent := Node.new()
		persistent.name = "Persistent"
		SceneUtil.attach_script(persistent, PERSISTENT)
		node.add_child(persistent)
		node.position = HomeRecipe.foot_of(cell, tile_px) - Vector2(0.0, 1.0)
		SceneUtil.add(entities, node, root, "Debris_%d_%d" % [cell.x, cell.y])
	for cell in cells_of(farm.get("trees")):
		var tree := _thing("tree", pictures, counts, tile_px)
		tree.position = HomeRecipe.foot_of(cell, tile_px) - Vector2(0.0, 1.0)
		SceneUtil.add(entities, tree, root, "Tree%d" % JsonUtil.to_int(counts["tree"]))
	for raw: Variant in JsonUtil.to_array(farm.get("scenery", [])):
		var thing := JsonUtil.to_dict(raw)
		var kind := JsonUtil.to_str(thing.get("kind", ""))
		var node := _thing(kind, pictures, counts, tile_px)
		node.position = HomeRecipe.foot_of(cell_of(thing.get("cell")), tile_px) - Vector2(0.0, 1.0)
		SceneUtil.add(entities, node, root, "%s%d" % [kind.capitalize(), JsonUtil.to_int(counts[kind])])

## The next thing of a kind, with the picture of the packs that is its turn (`counts` counts).
func _thing(kind: String, pictures: Dictionary, counts: Dictionary, tile_px: int) -> Node2D:
	var index := JsonUtil.to_int(counts.get(kind, 0))
	counts[kind] = index + 1
	var found: Array[Dictionary] = []
	if pictures.has(kind):
		found = pictures[kind]
	return make_thing(kind, thing_texture(found, index), tile_px, BLOCKING.has(kind))

## A thing of one cell, its foot at the origin: a solid body when it `blocks` (a fence fills its
## cell, anything else stands in the middle of it), else a node that is walked over. Its
## picture is `texture`, else drawn.
static func make_thing(kind: String, texture: Texture2D, tile_px: int, blocks: bool) -> Node2D:
	var node: Node2D = null
	if blocks:
		var body := StaticBody2D.new()
		body.collision_layer = 0
		body.collision_mask = 0
		body.set_collision_layer_value(1, true)  # world
		var shape := CollisionShape2D.new()
		shape.name = "Shape"
		var rect := RectangleShape2D.new()
		rect.size = Vector2(tile_px, tile_px) * (1.0 if kind == "fence" else 0.7)
		shape.shape = rect
		shape.position = Vector2(0.0, -tile_px * 0.5)
		body.add_child(shape)
		node = body
	else:
		node = Node2D.new()
	SceneUtil.attach_script(node, WORLD_OBJECT)
	node.set("blocks_movement", blocks)
	node.add_child(picture(kind, texture, tile_px))
	return node

## The picture of a thing with the middle of its lower edge on the origin: the texture, or the
## drawn boxes of its kind.
static func picture(kind: String, texture: Texture2D, tile_px: int) -> Node2D:
	if texture != null:
		var sprite := Sprite2D.new()
		sprite.name = "Sprite"
		sprite.texture = texture
		sprite.centered = false
		sprite.position = Vector2(-texture.get_width() * 0.5, -texture.get_height())
		return sprite
	var drawn := Node2D.new()
	drawn.name = "Sprite"
	var boxes: Array = DRAWN.get(kind, DRAWN["rock"])
	for i in boxes.size():
		var box: Array = boxes[i]
		var colour: Color = box[4]
		var part := FarmBuild.stand_in("Part%d" % (i + 1), Vector2(JsonUtil.to_float(box[0]), JsonUtil.to_float(box[1])) * tile_px, colour)
		part.position = Vector2(JsonUtil.to_float(box[2]), -JsonUtil.to_float(box[3])) * tile_px
		drawn.add_child(part)
	return drawn

# ---------------------------------------------------------------- the rooms

func _room_tileset(ctx: BuildContext) -> Dictionary:
	var interior: Dictionary = ctx.catalog.tileset_def("interior")
	if not interior.is_empty() and ResourceLoader.exists(Paths.TILESETS_DIR + "interior.tres"):
		return interior
	return ctx.catalog.tileset_def("overworld")

## The room of a building: the floor, the walls with the way out in the bottom one, and what
## the plan puts into it.
func _build_room(ctx: BuildContext, building: Dictionary, issues: Array) -> void:
	var path := room_path(building)
	var id := room_id(building)
	var room := JsonUtil.to_dict(building.get("interior", {}))
	var def := _room_tileset(ctx)
	if def.is_empty() or room.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, path))
		return
	var tile_path: String = Paths.TILESETS_DIR + "%s.tres" % def["name"]
	var tile_set := load(tile_path) as TileSet
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": tile_path}, tile_path))
		return
	var tile_px: int = JsonUtil.to_int(def["tile_size"][0])
	var size := cell_of(room.get("size"))
	var way_out := cell_of(room.get("door"))
	var arrive := cell_of(room.get("arrive"))
	var root := MapUtil.new_map_root(id.capitalize().replace(" ", ""), id)
	root.set("is_interior", true)  # a dimmer ambient, and the day's light does not reach it
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var ground: TileMapLayer = nodes["Ground"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var triggers: Node2D = nodes["Triggers"]
	var entities: Node2D = nodes["Entities"]
	MapUtil.fill(ground, Rect2i(Vector2i.ZERO, size), MapUtil.find_tile(ctx, def, tile_set, "GROUND"))
	var wall := MapUtil.wall_tile(ctx, def, tile_set)
	if not wall.is_empty() and nodes.has("Walls"):
		var walls: TileMapLayer = nodes["Walls"]
		MapUtil.border(walls, Rect2i(Vector2i.ZERO, size), wall, [way_out])
	else:
		MapUtil.border_collision(root, size, tile_px, [way_out])
	MapUtil.add_marker(spawns, root, "default", MapUtil.tile_center(arrive, tile_px), true, "up")
	MapBuild.add_exit_door(triggers, root, "Exit", way_out, tile_px, FARM_PATH, StringName(door_spawn(JsonUtil.to_str(building.get("id", "")))))
	var player_cell := arrive
	var markers := Node2D.new()
	SceneUtil.add(root, markers, root, "Markers")
	var bed_plan := JsonUtil.to_dict(room.get("bed", {}))
	if not bed_plan.is_empty():
		player_cell = _add_bed(ctx, room, bed_plan, root, nodes, tile_px)
	if JsonUtil.to_array(room.get("trough")).size() == 2:
		MapUtil.add_marker(markers, root, "Trough", MapUtil.tile_center(cell_of(room.get("trough")), tile_px))
	var stalls := cells_of(room.get("stalls"))
	for i in stalls.size():
		MapUtil.add_marker(markers, root, "Stall%d" % (i + 1), MapUtil.tile_center(stalls[i], tile_px))
	if MapUtil.place(PLAYER_SCENE, entities, root, MapUtil.tile_center(player_cell, tile_px)) == null:
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		root.free()
		return
	var err := SceneUtil.save_scene(root, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## The bed at its cells (its head at the plan's cell) and the spawn `start` beside it, where a
## new game begins and the farmer wakes. Returns the cell of that spawn.
func _add_bed(ctx: BuildContext, room: Dictionary, bed_plan: Dictionary, root: Node2D, nodes: Dictionary, tile_px: int) -> Vector2i:
	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var bed := SceneUtil.instance(HomeRecipe.BED_SCENE) as Node2D
	if bed == null:
		bed = HomeRecipe.build_bed(ctx)
	var footprint: Vector2i = bed.get("footprint")
	var head := cell_of(bed_plan.get("cell"))
	var start := start_cell(cell_of(room.get("start")), head, footprint, cell_of(room.get("size")))
	var facing := JsonUtil.to_str(JsonUtil.to_dict(plan().get("start", {})).get("facing", "down"))
	# its foot is the lowest row of its cells, and the middle of their width
	bed.position = Vector2(head.x * tile_px + footprint.x * tile_px * 0.5, (head.y + footprint.y) * tile_px)
	bed.set("wake_offset", MapUtil.tile_center(start, tile_px) - bed.position)
	bed.set("wake_facing", facing)
	entities.add_child(bed)
	bed.owner = root
	MapUtil.add_marker(spawns, root, START_SPAWN, MapUtil.tile_center(start, tile_px), true, facing)
	return start
