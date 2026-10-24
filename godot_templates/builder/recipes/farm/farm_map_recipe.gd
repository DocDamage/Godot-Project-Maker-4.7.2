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
## (forage_recipe.add_places). The doors to the maps added to the farm (T17.23) are not nodes of
## this map: it instances `generated/scenes/farm/trails.tscn` as `Trails`, under what stands on
## it, and added_maps_recipe.gd writes that scene on every build. So a map that is added later
## gets its door on the farm, and its spawn, without this map being written again. A farm whose
## plan has no `trails` (one planned before T17.23) has no such node.
##
## **Squares or diamonds** (T17.14). The plan is a grid of cells whatever the view, and every
## cell becomes a place, a shape or a tile through the seam of the map recipes
## (builder/lib/map_geo.gd): for a farm seen from above it is the arithmetic of squares this
## recipe always had, and its maps are byte for byte what they were. An isometric farm is
## painted with the project's tile set of diamonds, and what stands on it stands on the middle
## of its diamond and blocks that diamond: an isometric picture of the packs (by the same words,
## one that stands on one cell; a building whose `stands_on` fits the plan's footprint with its
## door before the plan's door cell), else a stand-in drawn as boxes on the diamond (RpgFarmIso):
## a house with a roof and a door on its south side, a fence whose rails run to the fence cells
## beside it, a gate of two posts, a tree, a bush, a rock, flowers, a branch, a stump, grass and
## a well. The door of a drawn building is a band along its south side, as the door of an
## isometric building of the packs is. The rooms are painted with the same tile set.

const RECIPE_VERSION := 6
## The version of what the recipe does for an isometric project only (T17.14): it is in the hash
## of such a project and of no other.
const ISO_VERSION := 2

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
const MapGeo := preload("../../lib/map_geo.gd")
const PlainGround := preload("../../lib/plain_ground.gd")
const IsoTileset := preload("../../lib/iso_tileset.gd")
const IsoHouse := preload("../../lib/iso_house.gd")
const FarmBuild := preload("farm_build.gd")
const FieldRecipe := preload("field_recipe.gd")
const RoomRecipe := preload("room_recipe.gd")
const HomeRecipe := preload("home_recipe.gd")
const HudRecipe := preload("hud_recipe.gd")
const ForageRecipe := preload("forage_recipe.gd")
const EventsRecipe := preload("events_recipe.gd")

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
## The second bed of a bed for two (T17.26: the room's plan says `sleepers: 2`).
const BED_TWO := "Bed2"
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
const MOST_TREE_CELLS := Vector2i(6, 8)

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

## The drawn stand-in of a thing on a diamond: boxes [u0, v0, u1, v1, lift, height, colour], the
## base of each in the cell's own coordinates (0 to 1 east and south, RpgFarmIso), its underside
## `lift` and its height in tiles (one step on the diamonds), drawn in this order.
const DRAWN_ISO := {
	"branch": [[0.2, 0.42, 0.85, 0.56, 0.0, 0.12, WOOD], [0.5, 0.26, 0.6, 0.42, 0.0, 0.1, WOOD]],
	"stump": [[0.3, 0.3, 0.7, 0.7, 0.0, 0.32, WOOD], [0.36, 0.36, 0.64, 0.64, 0.32, 0.03, WOOD_LIGHT]],
	"grass": [[0.22, 0.22, 0.78, 0.78, 0.0, 0.06, GRASS], [0.3, 0.42, 0.42, 0.54, 0.06, 0.26, GRASS], [0.56, 0.5, 0.68, 0.62, 0.06, 0.2, GRASS]],
	"tree": [[0.42, 0.42, 0.58, 0.58, 0.0, 0.7, WOOD], [0.14, 0.14, 0.86, 0.86, 0.6, 0.85, LEAF], [0.3, 0.3, 0.7, 0.7, 1.45, 0.4, LEAF]],
	"bush": [[0.2, 0.2, 0.8, 0.8, 0.0, 0.42, LEAF_DARK], [0.36, 0.36, 0.64, 0.64, 0.42, 0.18, LEAF_DARK]],
	"rock": [[0.2, 0.26, 0.8, 0.76, 0.0, 0.32, STONE], [0.3, 0.36, 0.6, 0.66, 0.32, 0.14, STONE_LIGHT]],
	"flowers": [[0.24, 0.24, 0.76, 0.76, 0.0, 0.05, GRASS], [0.3, 0.36, 0.42, 0.48, 0.05, 0.18, PETAL], [0.56, 0.54, 0.68, 0.66, 0.05, 0.26, PETAL]],
	"well": [[0.14, 0.14, 0.86, 0.86, 0.0, 0.42, STONE], [0.26, 0.26, 0.74, 0.74, 0.42, 0.02, WATER], [0.14, 0.44, 0.24, 0.56, 0.42, 0.6, WOOD], [0.76, 0.44, 0.86, 0.56, 0.42, 0.6, WOOD], [0.08, 0.34, 0.92, 0.66, 1.02, 0.12, ROOF]],
}
## A post of a fence, and its two rails towards a side of the cell (n, e, s, w), as DRAWN_ISO
## has boxes. The rails to the north and the west are drawn before the post, the others after.
const FENCE_POST := [0.42, 0.42, 0.58, 0.58, 0.0, 0.75, WOOD]
const FENCE_RAILS := {
	"n": [0.46, 0.0, 0.54, 0.5],
	"w": [0.0, 0.46, 0.5, 0.54],
	"s": [0.46, 0.5, 0.54, 1.0],
	"e": [0.5, 0.46, 1.0, 0.54],
}
const FENCE_RAIL_LIFTS: Array[float] = [0.2, 0.48]
const FENCE_RAIL_HEIGHT := 0.1
## How high the walls and the roof of a drawn building are on diamonds, in tiles.
const ISO_WALL := 1.5
const ISO_ROOF := 0.4

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

## Paints the plot of a field with the terrain `plot` (FarmBuild.plot_terrain, T17.31): as one
## area, edged where it meets the ground round it; for a terrain that joins at its sides only
## (beds of soil one cell wide, *Tiny Farm*'s) every column of the plot as a bed of its own.
static func paint_plot(layer: TileMapLayer, cells: Array[Vector2i], plot: Dictionary, map_seed: int) -> void:
	var set_index := JsonUtil.to_int(plot["set"])
	var terrain := JsonUtil.to_int(plot["terrain"])
	if JsonUtil.to_str(plot.get("shape", "any")) != "path":
		RpgTerrain.paint_area(layer, cells, set_index, terrain, map_seed)
		return
	var by_x := {}
	for cell in cells:
		if not by_x.has(cell.x):
			by_x[cell.x] = []
		var column: Array = by_x[cell.x]
		column.append(cell)
	var xs := by_x.keys()
	xs.sort()
	for x: Variant in xs:
		var column: Array = by_x[x]
		column.sort_custom(func(a: Vector2i, b: Vector2i) -> bool: return a.y < b.y)
		var run: Array[Vector2i] = []
		for cell: Vector2i in column:
			if not run.is_empty() and cell.y != run[run.size() - 1].y + 1:
				RpgTerrain.paint_path(layer, run, set_index, terrain, map_seed)
				run = []
			run.append(cell)
		if not run.is_empty():
			RpgTerrain.paint_path(layer, run, set_index, terrain, map_seed)

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
		if MapGeo.is_iso_entry(entry):
			# drawn for the isometric view: it may be as high as it likes and stands on one cell
			if region.size() != 4 or MapGeo.entry_cells(entry) != Vector2i.ONE:
				continue
		elif region.size() != 4 or JsonUtil.to_int(region[2]) > most.x * tile_px or JsonUtil.to_int(region[3]) > most.y * tile_px:
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
## one tagged `coop` or `barn`. {} when none fits: the building is drawn. For an isometric farm
## (`iso`, T17.14) only a building drawn for that view counts, and it fits when it stands on the
## plan's footprint with its door before the plan's door cell (`iso_building_offset`).
static func building_entry(entries: Array[Dictionary], kind: String, cells: Vector2i, door_column: int, tile_px: int, chosen: String = "", iso: bool = false) -> Dictionary:
	var ranked: Array[Dictionary] = []
	var others: Array[Dictionary] = []
	for entry in entries:
		if JsonUtil.to_str(entry.get("role", "")) != "BUILDING" or IsoHouse.is_kit(entry):
			continue  # a house of pieces is put together on the plan's own footprint (kit_building)
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
		if iso or MapGeo.is_iso_entry(entry):
			if iso and MapGeo.is_iso_entry(entry) and iso_building_offset(entry, cells, door_column).x >= 0:
				return entry
			continue
		var info := InteriorRecipe.building_info(entry, tile_px)
		var size := Vector2i(JsonUtil.to_int(info["size"][0]), JsonUtil.to_int(info["size"][1]))
		if size == cells and JsonUtil.to_int(info["door"][0]) == door_column:
			return entry
	return {}

## Where an isometric building of the packs stands on a footprint of `cells` of the plan whose
## door is before the column `door_column`: the cells from the footprint's first cell to the
## building's own first cell, or (-1, -1) when it does not fit. It stands on the last rows of
## the footprint with its own door (before the middle of its south side, MapGeo.building_info)
## in the plan's column. A building that is smaller than the footprint (the plan gives none
## less than two cells each way) leaves the rest of it as ground.
static func iso_building_offset(entry: Dictionary, cells: Vector2i, door_column: int) -> Vector2i:
	var own := MapGeo.entry_cells(entry)
	@warning_ignore("integer_division")
	var across := door_column - (own.x - 1) / 2
	if own.x > cells.x or own.y > cells.y or across < 0 or across + own.x > cells.x:
		return Vector2i(-1, -1)
	return Vector2i(across, cells.y - own.y)

# ---------------------------------------------------------------- the recipe

## Only the maps that do not exist yet: one that exists (and may have been edited) is kept.
func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for path in map_paths(plan()):
		if not FileAccess.file_exists(path):
			out.append(path)
	return out

func input_hash(ctx: BuildContext) -> String:
	var hashed := {
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
		"room": RoomRecipe.RECIPE_VERSION,
		"forage": ForageRecipe.spots(),
		"plain": PlainGround.stored(),
	}
	if MapGeo.is_isometric(ctx):  # only an isometric project's hash has the keys (T17.14)
		hashed["iso"] = MapGeo.new(ctx).def
		hashed["iso_v"] = ISO_VERSION
		hashed.merge(MapGeo.edge_hash(ctx))  # T17.22: only with walls along a side
	if not FarmBuild.events().is_empty():  # only a farm with festivals has the key (T17.25)
		hashed["calendar"] = EventsRecipe.RECIPE_VERSION
	hashed.merge(MapGeo.TerrainPaint.hash_part(ctx))  # T17.31: only with terrains
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var farm := plan()
	if farm.is_empty():
		print("[rpggen] INFO farm_map: the project has no plan of its farm (rpggen/world_plan.json, farm.map)")
		return issues
	if not FileAccess.file_exists(FARM_PATH):
		_build_farm(ctx, farm, issues)
	else:
		var kept := MapGeo.TerrainPaint.kept_map(ctx, FARM_PATH, input_hash(ctx))  # T17.31
		if not kept.is_empty():
			issues.append(kept)
	for building in buildings_of(farm):
		if not FileAccess.file_exists(room_path(building)):
			_build_room(ctx, building, issues)
	return issues

# ---------------------------------------------------------------- the farm

func _ground_tile(ctx: BuildContext, geo: MapGeo) -> Dictionary:
	# the plain tile of the ground sheet where rpggen found one (farm.ground), not its first
	var plain := PlainGround.tile(geo)
	if not plain.is_empty():
		return plain
	var wanted := JsonUtil.to_str(ctx.section("starter_map").get("ground", ""))
	if wanted == "":
		wanted = JsonUtil.to_str(ctx.section("starter").get("ground", ""))
	if wanted != "":
		var tile := geo.tile_of_asset(wanted)
		if not tile.is_empty():
			return tile
	return geo.find_tile("GROUND")

## Where a thing of a cell stands: with the middle of its lower edge on the lower edge of a
## square (HomeRecipe.foot_of), on the middle of a diamond.
static func _spot(cell: Vector2i, geo: MapGeo) -> Vector2:
	if geo.isometric:
		return geo.center(cell)
	return HomeRecipe.foot_of(cell, geo.tile_px)

func _build_farm(ctx: BuildContext, farm: Dictionary, issues: Array) -> void:
	var root := farm_root(ctx, farm, issues)
	if root == null:
		return
	var err := SceneUtil.save_scene(root, FARM_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": FARM_PATH, "err": err}, FARM_PATH))

## The farm of a plan (`farm.map`) as the nodes of its map, not yet saved; null, with an issue,
## when the project lacks what it is built from.
func farm_root(ctx: BuildContext, farm: Dictionary, issues: Array) -> Node2D:
	# the seam between the plan's cells and the map's px (T17.14): squares, or diamonds
	var geo := MapGeo.new(ctx)
	if geo.def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, FARM_PATH))
		return null
	var tile_set := geo.load_tile_set()
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": geo.tileset_path()}, geo.tileset_path()))
		return null
	if not ResourceLoader.exists(PLAYER_SCENE):
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		return null
	var tile_px := geo.tile_px
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
	# the ground varies where its tile is the middle of a terrain with plain variants (T17.31)
	geo.fill_ground(ground, Rect2i(Vector2i.ZERO, size), geo.ground_of(_ground_tile(ctx, geo)), MAP_ID)
	var details := geo.road_layer(nodes)  # GroundDetails; the ground itself on diamonds
	if details != null:
		var ways := cells_of(farm.get("paths"))
		if not geo.isometric:
			ways = wide_paths(farm, size)  # T17.33: a path two cells wide where there is room
		geo.paint_joined(details, ways, "ROAD", geo.find_tile("ROAD"))
	var water := JsonUtil.to_dict(farm.get("water", {}))
	var water_cells := cells_of(water.get("cells"))
	var pond := JsonUtil.to_str(water.get("kind", "")) == "pond"
	var water_tile: Dictionary = geo.find_tile("WATER") if pond else {}
	# a pond of a terrain of water has its shore (T17.31), whatever sheet the water is in
	var water_terrain := pond and not geo.terrain_for("WATER").is_empty()
	if not water_tile.is_empty() or water_terrain:
		geo.paint_joined(ground, water_cells, "WATER", water_tile)
		if water_tile.is_empty():
			water_tile = {"terrain": true}  # the map paints its water: the Soil layer marks it
	var way_out := JsonUtil.to_dict(farm.get("exit", {}))
	var gap := cell_of(way_out.get("cell"))
	var skip: Array[Vector2i] = []
	if not way_out.is_empty():
		skip.append(gap)
	geo.paint_walls(root, nodes, size, skip, true)  # a farm is fenced where the packs have a fence
	for note in geo.take_notes():
		print("[rpggen] INFO farm_map: ", note)

	# the field: what can be tilled and where the can is filled are written into the tiles
	var soil := FieldRecipe.add_field(root, nodes)
	if soil == null:
		issues.append(ctx.make_issue("VAL-002", {"file": FarmBuild.SOIL_TILESET}, FarmBuild.SOIL_TILESET))
		root.free()
		return null
	# the plot: earth of a terrain of the ground, edged where it meets the grass, when the tile
	# set has one (T17.31), the Soil layer marking it with a tile that shows nothing; else the
	# drawn ground that can be tilled
	var tillable := cells_of(farm.get("tillable"))
	var plot := FarmBuild.plot_terrain(ctx)
	if not plot.is_empty() and not tillable.is_empty():
		paint_plot(ground, tillable, plot, geo.seed_for(MAP_ID + "_plot"))
	for cell in tillable:
		soil.set_cell(cell, FieldRecipe.SOURCE_ID, FieldRecipe.PLOT_TILE if plot.is_empty() else FieldRecipe.PLOT_MARK)
	# a pond without a water tile of the packs is drawn; the others show through
	var water_mark := FieldRecipe.WATER_TILE if pond and water_tile.is_empty() else FieldRecipe.WATER_MARK
	for cell in water_cells:
		soil.set_cell(cell, FieldRecipe.SOURCE_ID, water_mark)

	var entries := ObjectEntries.entries(ctx)
	var markers := Node2D.new()
	SceneUtil.add(root, markers, root, "Markers")
	var chosen := JsonUtil.to_str(ctx.section("starter").get("building", ""))
	for building in buildings_of(farm):
		_add_building(building, root, nodes, geo, entries, chosen)
		_add_yard(building, root, entities, geo, entries)
	_add_water(water, water_cells, root, entities, markers, geo, entries)
	_add_bin(ctx, farm, root, entities, markers, geo)
	_add_sign(ctx, farm, root, entities, geo)
	add_things(farm, root, entities, geo, entries)
	ForageRecipe.add_places(root, geo)
	_add_trails(farm, root, nodes)

	if not way_out.is_empty():
		MapUtil.add_marker(spawns, root, FROM_VILLAGE, geo.center(cell_of(way_out.get("spawn"))), true, JsonUtil.to_str(way_out.get("facing", "down")))
		geo.add_exit_door(triggers, root, EXIT_NAME, gap, VILLAGE_PATH, StringName(FROM_FARM))
	var door := cell_of(JsonUtil.to_dict(farm.get("house", {})).get("door"))
	MapUtil.add_marker(markers, root, "HouseDoor", geo.center(door))
	MapUtil.add_marker(spawns, root, "default", geo.center(door), true)
	MapUtil.place(PLAYER_SCENE, entities, root, geo.center(door))
	return root

## The cells the paths of the plan are painted on (T17.33): each path cell and, beside it, the
## cell that makes the way two cells wide (below a path that runs across, right of one that runs
## up and down) where that cell is open grass: not the plot, the water, a building, a tree, a
## thing of the plan or the edge. A path of one cell looked like a line drawn on the grass. The
## plan's own cells stay what is walked and checked; the second cell is only painted.
static func wide_paths(farm: Dictionary, size: Vector2i) -> Array[Vector2i]:
	var ways := cells_of(farm.get("paths"))
	var on := {}
	for cell in ways:
		on[cell] = true
	var taken := {}
	for key: String in ["tillable", "trees"]:
		for cell in cells_of(farm.get(key)):
			taken[cell] = true
	for cell in cells_of(JsonUtil.to_dict(farm.get("water", {})).get("cells")):
		taken[cell] = true
	for key: String in ["debris", "scenery"]:
		for raw: Variant in JsonUtil.to_array(farm.get(key, [])):
			taken[cell_of(JsonUtil.to_dict(raw).get("cell"))] = true
	for building in buildings_of(farm):
		var rect := rect_of(building.get("rect"))
		for y in range(rect.position.y - 1, rect.end.y + 1):
			for x in range(rect.position.x - 1, rect.end.x + 1):
				taken[Vector2i(x, y)] = true
	var out: Array[Vector2i] = ways.duplicate()
	for cell in ways:
		var across: bool = on.has(cell + Vector2i.LEFT) or on.has(cell + Vector2i.RIGHT)
		var beside := cell + (Vector2i.DOWN if across else Vector2i.RIGHT)
		if on.has(beside) or taken.has(beside) or out.has(beside):
			continue
		if beside.x < 1 or beside.y < 1 or beside.x >= size.x - 1 or beside.y >= size.y - 1:
			continue
		out.append(beside)
	return out

## A building of the plan on its footprint, with the door into its room and the spawn in front
## of it where the farmer comes out again.
func _add_building(building: Dictionary, root: Node2D, nodes: Dictionary, geo: MapGeo, entries: Array[Dictionary], chosen: String) -> void:
	var tile_px := geo.tile_px
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
	var entry := building_entry(entries, kind, rect.size, column, tile_px, chosen, geo.isometric)
	var scene := ObjectIndex.scene_path(JsonUtil.to_str(entry["id"])) if not entry.is_empty() else ""
	var placed: Node2D = null
	if scene != "" and ResourceLoader.exists(scene):
		# an isometric building may be smaller than the plan's footprint: it stands at its door
		var first := rect.position + iso_building_offset(entry, rect.size, column) if geo.isometric else rect.position
		placed = MapUtil.place(scene, entities, root, geo.building_position(entry, first), node_name)
		if placed != null and geo.isometric:
			_block_rest(root, node_name, uncovered_cells(rect, Rect2i(first, MapGeo.entry_cells(entry))), geo)
	if placed != null:
		# properties of nodes inside an instanced scene are saved only when it is editable
		root.set_editable_instance(placed, true)
		entrance = placed.get_node_or_null("Entrance")
		exit_spawn = placed.get_node_or_null("ExitSpawn")
	elif geo.isometric:
		# a house of the packs' pieces where they have them (T17.22), else one that is drawn
		var box := kit_building(geo, entries, rect, column)
		if box == null:
			box = drawn_iso_building(kind, rect.size, column, geo.footprint, tile_px)
		box.position = geo.center(rect.end - Vector2i.ONE)
		SceneUtil.add(entities, box, root, node_name)
	else:
		var drawn := drawn_building(kind, rect.size, column, tile_px)
		drawn.position = Vector2((rect.position.x + rect.size.x * 0.5) * tile_px, rect.end.y * tile_px)
		SceneUtil.add(entities, drawn, root, node_name)
	if entrance == null and geo.isometric:
		# a thin band along the south side of the building, before the plan's door cell: walking
		# against it anywhere near its middle enters (object_scenes_recipe._add_iso_door)
		var half := Vector2(geo.footprint) / 2.0
		var edge := (geo.center(door + Vector2i.UP) + geo.center(door)) / 2.0
		var band := add_door(triggers, root, node_name + "Door", edge + Vector2(-half.x, half.y).normalized() * 2.0, Vector2(tile_px * 0.6, 6.0))
		(band.get_node("Shape") as CollisionShape2D).rotation = half.angle()
		entrance = band
	if entrance == null:
		# the door lies on the lower edge of the building and reaches a little into the cell
		# before it, as the door of a building of the packs does
		entrance = add_door(triggers, root, node_name + "Door", Vector2((door.x + 0.5) * tile_px, door.y * tile_px + 3.0), Vector2(tile_px * 0.75, tile_px * 0.5))
	entrance.set("target_map", room_path(building))
	entrance.set("target_spawn", &"default")
	if exit_spawn != null:
		exit_spawn.set("spawn_id", StringName(spawn_id))
	elif geo.isometric:
		MapUtil.add_marker(spawns, root, spawn_id, geo.center(door), true)
	else:
		MapUtil.add_marker(spawns, root, spawn_id, Vector2((door.x + 0.5) * tile_px, (door.y + 1) * tile_px - 1.0), true)

## The cells of a footprint of the plan (`rect`) that a building standing on `own` leaves
## open, row by row.
static func uncovered_cells(rect: Rect2i, own: Rect2i) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y in range(rect.position.y, rect.end.y):
		for x in range(rect.position.x, rect.end.x):
			if not own.has_point(Vector2i(x, y)):
				out.append(Vector2i(x, y))
	return out

## Blocks `cells` (T17.18): the cells of a planned footprint that a smaller building of the packs
## does not stand on. The planner gives no building less than two cells each way and counts
## the whole footprint as blocked (its paths, its forage places, the check that everything can
## be reached), so a house drawn on one diamond left three cells one could walk on that the
## plan knew nothing of. They stay ground to look at and are solid, a diamond each, in a body
## of their own (`<Building>Ground`) so that nothing of the building's scene is changed.
func _block_rest(root: Node2D, node_name: String, cells: Array[Vector2i], geo: MapGeo) -> void:
	if cells.is_empty():
		return
	var body := StaticBody2D.new()
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)  # world
	SceneUtil.add(root, body, root, node_name + "Ground")
	var diamond := geo.cell_shape()
	for cell in cells:
		var shape := CollisionShape2D.new()
		shape.name = "Cell_%d_%d" % [cell.x, cell.y]
		shape.shape = diamond
		shape.position = geo.center(cell)
		body.add_child(shape)
		shape.owner = root

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

## A building nobody drew, on diamonds (T17.14): walls, a roof and a door on its south side,
## solid over its whole footprint. Its origin is the middle of the cell of its footprint nearest
## the camera, and it is drawn in two halves that sort apart, as an isometric building of the
## packs is: who stands north or west of it is drawn behind it, who stands south or east of it
## in front.
static func drawn_iso_building(kind: String, cells: Vector2i, door_column: int, footprint: Vector2i, tile_px: int) -> StaticBody2D:
	var body := StaticBody2D.new()
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)  # world
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var outline := ConvexPolygonShape2D.new()
	var u0 := 1.0 - cells.x
	var v0 := 1.0 - cells.y
	outline.points = RpgFarmIso.outline(u0, v0, 1.0, 1.0, footprint)
	shape.shape = outline
	body.add_child(shape)
	var wall_colour: Color = WALLS.get(kind, WALLS["house"])
	var wall := tile_px * ISO_WALL
	var parts := RpgFarmIso.halves(body, cells, footprint)
	RpgFarmIso.add_box(parts, "Wall", u0 + 0.08, v0 + 0.08, 0.92, 0.92, 0.0, wall, wall_colour, footprint)
	# the door, on the wall that looks south, before the plan's door cell
	var left := RpgFarmIso.point(u0 + door_column + 0.25, 0.92, footprint)
	var right := RpgFarmIso.point(u0 + door_column + 0.75, 0.92, footprint)
	var lintel := Vector2(0.0, -minf(tile_px * 0.9, wall * 0.7))
	RpgFarmIso.add_face(parts, "Door", PackedVector2Array([left + lintel, right + lintel, right, left]), DOOR)
	RpgFarmIso.add_box(parts, "Roof", u0 - 0.04, v0 - 0.04, 1.04, 1.04, wall, tile_px * ISO_ROOF, ROOF, footprint)
	return body

## A building put together from the packs' pieces on the plan's footprint `rect`, its door
## before the column `door_column` (T17.22, IsoHouse): walls along its sides, the wall with a
## door, windows by where it stands, a roof a cell. Solid over its footprint, its origin the
## middle of the cell nearest the camera, in the two halves an isometric building sorts by.
## Null when the packs have no kit (`entries` has no house of pieces).
static func kit_building(geo: MapGeo, entries: Array[Dictionary], rect: Rect2i, door_column: int) -> StaticBody2D:
	var pieces := {}
	for entry in entries:
		if IsoHouse.is_kit(entry):
			pieces = JsonUtil.to_dict(entry.get("kit", {}))
	if pieces.is_empty() or geo.iso == null:
		return null
	var body := StaticBody2D.new()
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)  # world
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var outline := ConvexPolygonShape2D.new()
	outline.points = RpgFarmIso.outline(1.0 - rect.size.x, 1.0 - rect.size.y, 1.0, 1.0, geo.footprint)
	shape.shape = outline
	body.add_child(shape)
	body.set_meta(&"kit", pieces.duplicate())
	var parts := IsoHouse.parts(geo.iso, pieces, rect.size, door_column, rect.position.x * 131 + rect.position.y)
	IsoHouse.assemble(body, parts, rect.size, geo.footprint)
	return body

## The sides of a cell of a yard's fence on which the yard lies (n, e, s, w): where a segment of
## fence stands. A cell at a corner of the fence has none: the segments beside it meet there.
static func yard_sides(cell: Vector2i, yard: Rect2i) -> Array[String]:
	var out: Array[String] = []
	for side in RpgIso.SIDES:
		var by: Vector2i = RpgIso.STEPS[side]
		if yard.has_point(cell + by):
			out.append(side)
	return out

## A piece of a yard's fence from the packs' fence segments (T17.22): a solid diamond with the
## segment of `fence_set` that stands along each of `sides` (`Sprite`, `Sprite2`), the middle of
## the cell at the origin. Without a side it is the diamond alone.
static func make_edge_fence(iso: IsoTileset, fence_set: String, sides: Array[String], footprint: Vector2i) -> Node2D:
	var body := StaticBody2D.new()
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)  # world
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	shape.shape = RpgFarmIso.diamond_shape(footprint, 1.0)
	body.add_child(shape)
	SceneUtil.attach_script(body, WORLD_OBJECT)
	body.set("blocks_movement", true)
	var count := 0
	for side in sides:
		var piece := iso.edge_piece(fence_set, side)
		if piece.is_empty():
			continue
		var asset_id := JsonUtil.to_str(piece["asset_id"])
		var picture := iso.picture_of(asset_id)
		var region := JsonUtil.to_array(picture.get("region", []))
		if region.size() != 4:
			continue
		var texture := TextureUtil.region_texture(JsonUtil.to_str(picture["texture"]), Rect2i(JsonUtil.to_int(region[0]), JsonUtil.to_int(region[1]), JsonUtil.to_int(region[2]), JsonUtil.to_int(region[3])))
		if texture == null:
			continue
		count += 1
		var sprite := Sprite2D.new()
		sprite.name = "Sprite" if count == 1 else "Sprite%d" % count
		sprite.texture = texture
		IsoTileset.stand(sprite, iso.facets(asset_id), Vector2.ZERO)
		sprite.set_meta(&"asset_id", asset_id)
		sprite.set_meta(&"side", side)
		body.add_child(sprite)
	return body

## The yard of an animal house: a piece of fence on every cell of the plan's fence, the gate
## (which is walked through), and the node the animals' recipe finds it by.
func _add_yard(building: Dictionary, root: Node2D, entities: Node2D, geo: MapGeo, entries: Array[Dictionary]) -> void:
	var tile_px := geo.tile_px
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
	# the corner of the yard's first cell, or on diamonds the middle of that cell
	node.position = geo.center(rect.position) if geo.isometric else Vector2(rect.position) * tile_px
	node.set_meta(&"kind", kind)
	node.set_meta(&"yard", rect)
	node.set_meta(&"gate", cell_of(yard.get("gate")))
	node.set_meta(&"stalls", JsonUtil.to_array(room.get("stalls", [])).size())
	node.set_meta(&"house_map", room_path(building))
	SceneUtil.add(holder, node, root, kind.capitalize())
	var pictures := thing_entries(entries, "fence", tile_px)
	var index := 0
	var fence := cells_of(yard.get("fence"))
	var gate_cell := cell_of(yard.get("gate"))
	# on diamonds a piece of fence joins the pieces beside it, and the gate
	var joined := fence.duplicate()
	joined.append(gate_cell)
	# the packs' fence segments, where they have a fence that stands along a side (T17.22)
	var fence_set := ""
	if geo.isometric and not geo.iso.wall_sets(true).is_empty():
		fence_set = geo.iso.border_set(true)
	for cell in fence:
		var piece: Node2D = null
		if fence_set != "":
			piece = make_edge_fence(geo.iso, fence_set, yard_sides(cell, rect), geo.footprint)
		elif geo.isometric:
			piece = make_iso_thing("fence", _entry_at(pictures, index), geo.footprint, tile_px, true, sides_of(cell, joined))
		else:
			piece = make_thing("fence", thing_texture(pictures, index), tile_px, true)
		piece.position = _spot(cell, geo)
		SceneUtil.add(entities, piece, root, "Fence_%s_%d_%d" % [kind, cell.x, cell.y])
		index += 1
	var gate: Node2D = null
	if geo.isometric:
		gate = make_iso_thing("gate", {}, geo.footprint, tile_px, false, sides_of(gate_cell, fence))
	else:
		gate = make_thing("gate", null, tile_px, false)
	gate.position = _spot(gate_cell, geo)
	SceneUtil.add(entities, gate, root, "Gate_%s" % kind)

## The sides of `cell` (n, e, s, w) on which a cell of `others` lies.
static func sides_of(cell: Vector2i, others: Array[Vector2i]) -> Array[String]:
	var out: Array[String] = []
	for side in RpgIso.SIDES:
		var by: Vector2i = RpgIso.STEPS[side]
		if others.has(cell + by):
			out.append(side)
	return out

## The `index`-th entry of the packs' pictures of a kind, in turn; {} when they have none.
static func _entry_at(found: Array[Dictionary], index: int) -> Dictionary:
	return found[index % found.size()] if not found.is_empty() else {}

## The water: one body over its cells that is solid and fills the can with `interact` (the
## tiles under it fill it with `use`), a picture when it is a well, and the place to stand.
func _add_water(water: Dictionary, cells: Array[Vector2i], root: Node2D, entities: Node2D, markers: Node2D, geo: MapGeo, entries: Array[Dictionary]) -> void:
	if cells.is_empty():
		return
	var tile_px := geo.tile_px
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
	body.position = _spot(water_beside(fill, cells), geo)
	var diamond := geo.cell_shape() if geo.isometric else null  # one shape for every cell
	for cell in cells:
		var shape := CollisionShape2D.new()
		shape.name = "Cell_%d_%d" % [cell.x, cell.y]
		if geo.isometric:
			shape.shape = diamond
		else:
			var rect := RectangleShape2D.new()
			rect.size = Vector2(tile_px, tile_px)
			shape.shape = rect
		shape.position = geo.center(cell) - body.position
		body.add_child(shape)
	if kind == "well" and geo.isometric:
		body.add_child(iso_picture("well", _entry_at(thing_entries(entries, "well", tile_px), 0), geo.footprint, tile_px))
	elif kind == "well":
		body.add_child(picture("well", thing_texture(thing_entries(entries, "well", tile_px), 0), tile_px))
	SceneUtil.add(entities, body, root, "Water")
	MapUtil.add_marker(markers, root, "WaterFill", geo.center(fill))

func _add_bin(ctx: BuildContext, farm: Dictionary, root: Node2D, entities: Node2D, markers: Node2D, geo: MapGeo) -> void:
	var bin_plan := JsonUtil.to_dict(farm.get("bin", {}))
	if bin_plan.is_empty():
		return
	var at := _spot(cell_of(bin_plan.get("cell")), geo)
	if MapUtil.place(HomeRecipe.BIN_SCENE, entities, root, at) == null:
		var bin := HomeRecipe.build_bin(ctx)
		bin.position = at
		SceneUtil.add(entities, bin, root, HomeRecipe.BIN_NAME)
	MapUtil.add_marker(markers, root, "BinFront", geo.center(cell_of(bin_plan.get("front"))))

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
func _add_sign(ctx: BuildContext, farm: Dictionary, root: Node2D, entities: Node2D, geo: MapGeo) -> void:
	var cell := sign_cell(farm)
	if cell.x < 0:
		print("[rpggen] INFO farm_map: no room for the weather's sign by the door of the house")
		return
	var sign := HudRecipe.build_sign(ctx)
	sign.position = _spot(cell, geo)
	SceneUtil.add(entities, sign, root, String(sign.name))

## The farm's side of the doors to its added maps (T17.23): the scene added_maps_recipe.gd
## writes on every build, instanced once, under what stands on the map (its marks lie flat on
## the ground). Nothing for a plan without trails.
func _add_trails(farm: Dictionary, root: Node2D, nodes: Dictionary) -> void:
	if not farm.has("trails"):
		return
	var ysorted: Node = nodes["YSorted"]
	var trails := MapUtil.place(FarmBuild.TRAILS_SCENE, root, root, Vector2.ZERO, FarmBuild.TRAILS_NODE)
	if trails == null:
		print("[rpggen] INFO farm_map: the scene of the trails is missing (%s): the farm has no doors to added maps" % FarmBuild.TRAILS_SCENE)
		return
	root.move_child(trails, ysorted.get_index())

## What lies and stands about on a map of the farm: the things to clear (each remembered once it
## is cleared, under an id that begins with `prefix`: the farm's, or the id of an added map,
## T17.23), the trees and the scenery. `farm` is the plan of the map: its `debris`, `trees` and
## `scenery`.
func add_things(farm: Dictionary, root: Node2D, entities: Node2D, geo: MapGeo, entries: Array[Dictionary], prefix: String = "farm") -> void:
	var tile_px := geo.tile_px
	# a px above the lower edge of a square, so that a thing sorts with what stands there
	var lift := Vector2.ZERO if geo.isometric else Vector2(0.0, 1.0)
	var pictures := {}
	for kind: String in WORDS.keys():
		pictures[kind] = thing_entries(entries, kind, tile_px)
	var counts := {}
	for raw: Variant in JsonUtil.to_array(farm.get("debris", [])):
		var thing := JsonUtil.to_dict(raw)
		var kind := JsonUtil.to_str(thing.get("kind", ""))
		var cell := cell_of(thing.get("cell"))
		var node := _thing(kind, pictures, counts, geo)
		node.set_meta(CLEAR_META, kind)
		node.set("entity_id", "%s_debris_%d_%d" % [prefix, cell.x, cell.y])
		var persistent := Node.new()
		persistent.name = "Persistent"
		SceneUtil.attach_script(persistent, PERSISTENT)
		node.add_child(persistent)
		node.position = _spot(cell, geo) - lift
		SceneUtil.add(entities, node, root, "Debris_%d_%d" % [cell.x, cell.y])
	var covered := _covered(farm)
	var tree_pictures: Array[Dictionary] = []
	if pictures.has("tree"):
		tree_pictures = pictures["tree"]
	for cell in cells_of(farm.get("trees")):
		if not geo.isometric and _crown_covers(cell, tree_pictures, JsonUtil.to_int(counts.get("tree", 0)), tile_px, covered):
			counts["tree"] = JsonUtil.to_int(counts.get("tree", 0)) + 1
			continue  # T17.33: its crown would stand over the plot, the pond or a roof
		var tree := _thing("tree", pictures, counts, geo)
		tree.position = _spot(cell, geo) - lift
		SceneUtil.add(entities, tree, root, "Tree%d" % JsonUtil.to_int(counts["tree"]))
	for raw: Variant in JsonUtil.to_array(farm.get("scenery", [])):
		var thing := JsonUtil.to_dict(raw)
		var kind := JsonUtil.to_str(thing.get("kind", ""))
		var node := _thing(kind, pictures, counts, geo)
		node.position = _spot(cell_of(thing.get("cell")), geo) - lift
		SceneUtil.add(entities, node, root, "%s%d" % [kind.capitalize(), JsonUtil.to_int(counts[kind])])

## The cells of a farm plan a tree's crown must not stand over: the plot, the water and the
## buildings.
static func _covered(farm: Dictionary) -> Dictionary:
	var out := {}
	for cell in cells_of(farm.get("tillable")):
		out[cell] = true
	for cell in cells_of(JsonUtil.to_dict(farm.get("water", {})).get("cells")):
		out[cell] = true
	for building in buildings_of(farm):
		var rect := rect_of(building.get("rect"))
		for y in range(rect.position.y, rect.end.y):
			for x in range(rect.position.x, rect.end.x):
				out[Vector2i(x, y)] = true
	return out

## True when the `index`-th tree picture of `found`, standing on `cell`, reaches over a cell of
## `covered` (its picture is taller and wider than its cell). A drawn tree is one cell.
static func _crown_covers(cell: Vector2i, found: Array[Dictionary], index: int, tile_px: int, covered: Dictionary) -> bool:
	if found.is_empty() or tile_px <= 0:
		return false
	var region: Array = found[index % found.size()].get("region", [])
	if region.size() != 4:
		return false
	var high := ceili(JsonUtil.to_float(region[3]) / tile_px)
	var half := floori(JsonUtil.to_float(region[2]) / tile_px / 2.0)
	for dy in range(0, high):
		for dx in range(-half, half + 1):
			if covered.has(cell + Vector2i(dx, -dy)):
				return true
	return false

## The next thing of a kind, with the picture of the packs that is its turn (`counts` counts).
func _thing(kind: String, pictures: Dictionary, counts: Dictionary, geo: MapGeo) -> Node2D:
	var index := JsonUtil.to_int(counts.get(kind, 0))
	counts[kind] = index + 1
	var found: Array[Dictionary] = []
	if pictures.has(kind):
		found = pictures[kind]
	if geo.isometric:
		return make_iso_thing(kind, _entry_at(found, index), geo.footprint, geo.tile_px, BLOCKING.has(kind))
	return make_thing(kind, thing_texture(found, index), geo.tile_px, BLOCKING.has(kind))

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

# ---------------------------------------------------------------- things on diamonds (T17.14)

## A thing of one cell of an isometric farm, the middle of its diamond at the origin: a solid
## body when it `blocks` (a fence closes its diamond, anything else the middle of it), else a
## node that is walked over. Its picture is the packs' (`entry`, an object entry), else drawn.
## `sides` are the sides on which a fence joins the next piece, or a gate has its posts.
static func make_iso_thing(kind: String, entry: Dictionary, footprint: Vector2i, tile_px: int, blocks: bool, sides: Array[String] = []) -> Node2D:
	var node: Node2D = null
	if blocks:
		var body := StaticBody2D.new()
		body.collision_layer = 0
		body.collision_mask = 0
		body.set_collision_layer_value(1, true)  # world
		var shape := CollisionShape2D.new()
		shape.name = "Shape"
		shape.shape = RpgFarmIso.diamond_shape(footprint, 1.0 if kind == "fence" else 0.7)
		body.add_child(shape)
		node = body
	else:
		node = Node2D.new()
	SceneUtil.attach_script(node, WORLD_OBJECT)
	node.set("blocks_movement", blocks)
	node.add_child(iso_picture(kind, entry, footprint, tile_px, sides))
	return node

## The picture of a thing on a diamond, the middle of the diamond at the origin: the packs' own
## (one drawn for the isometric view by its `origin`, any other standing on the middle with its
## lower edge), else the boxes of its kind.
static func iso_picture(kind: String, entry: Dictionary, footprint: Vector2i, tile_px: int, sides: Array[String] = []) -> Node2D:
	if not entry.is_empty():
		var region: Array = entry["region"]
		var texture := TextureUtil.region_texture(JsonUtil.to_str(entry["texture_path"]), Rect2i(JsonUtil.to_int(region[0]), JsonUtil.to_int(region[1]), JsonUtil.to_int(region[2]), JsonUtil.to_int(region[3])))
		var sprite := Sprite2D.new()
		sprite.name = "Sprite"
		sprite.texture = texture
		sprite.centered = false
		if MapGeo.is_iso_entry(entry):
			sprite.offset = -Vector2(JsonUtil.to_float(entry["origin"][0]), JsonUtil.to_float(entry["origin"][1]))
		else:
			sprite.position = Vector2(-texture.get_width() * 0.5, -texture.get_height())
		return sprite
	var drawn := Node2D.new()
	drawn.name = "Sprite"
	var boxes: Array = []
	match kind:
		"fence":
			boxes = _fence_boxes(sides)
		"gate":
			boxes = _gate_boxes(sides)
		_:
			boxes = DRAWN_ISO.get(kind, DRAWN_ISO["rock"])
	for i in boxes.size():
		var box: Array = boxes[i]
		var colour: Color = box[6]
		drawn.add_child(RpgFarmIso.box("Part%d" % (i + 1), JsonUtil.to_float(box[0]), JsonUtil.to_float(box[1]), JsonUtil.to_float(box[2]), JsonUtil.to_float(box[3]), JsonUtil.to_float(box[4]) * tile_px, JsonUtil.to_float(box[5]) * tile_px, colour, footprint))
	return drawn

## The boxes of a piece of fence: its post, and two rails to every side it joins on. What lies
## behind the post (the rails to the north and the west) comes first.
static func _fence_boxes(sides: Array[String]) -> Array:
	var out: Array = []
	for behind: bool in [true, false]:
		for side: String in ["n", "w"] if behind else ["s", "e"]:
			if not sides.has(side):
				continue
			var rail: Array = FENCE_RAILS[side]
			for lift in FENCE_RAIL_LIFTS:
				out.append([rail[0], rail[1], rail[2], rail[3], lift, FENCE_RAIL_HEIGHT, WOOD_LIGHT])
		if behind:
			out.append(FENCE_POST)
	return out

## The boxes of a gate: a post towards every side the fence goes on (both ends of the cell
## along the fence), the one behind first. A gate with no fence beside it has one on each side
## east and west.
static func _gate_boxes(sides: Array[String]) -> Array:
	var posts := {"n": [0.42, 0.0, 0.58, 0.14], "w": [0.0, 0.42, 0.14, 0.58], "s": [0.42, 0.86, 0.58, 1.0], "e": [0.86, 0.42, 1.0, 0.58]}
	var wanted: Array[String] = ["w", "e"]
	if not sides.is_empty():
		wanted = sides
	var out: Array = []
	for side: String in ["n", "w", "s", "e"]:
		if wanted.has(side):
			var post: Array = posts[side]
			out.append([post[0], post[1], post[2], post[3], 0.0, 0.9, WOOD])
	return out

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
	var root := room_root(ctx, building, issues)
	if root == null:
		return
	var err := SceneUtil.save_scene(root, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## The room of a building of a plan as the nodes of its map, not yet saved; null, with an issue,
## when the project lacks what it is built from.
func room_root(ctx: BuildContext, building: Dictionary, issues: Array) -> Node2D:
	var path := room_path(building)
	var id := room_id(building)
	var room := JsonUtil.to_dict(building.get("interior", {}))
	var def := _room_tileset(ctx)
	# an isometric farm's rooms are painted with its tile set of diamonds (the packs that were
	# listed have no floor of their own), every other farm's with the interior tile set
	var geo := MapGeo.new(ctx, JsonUtil.to_str(def.get("name", "")))
	if geo.def.is_empty() or room.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, path))
		return null
	var tile_path := geo.tileset_path()
	var tile_set := geo.load_tile_set()
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": tile_path}, tile_path))
		return null
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
	# A room reads as indoors (T17.18). Its floor and its walls are the interior tiles of the
	# packs when the project has an interior tile set with them (as the houses of a village
	# choose theirs, interior_recipe.gd); what that leaves is drawn: boards and plaster
	# (room_recipe.gd), a tile set of the rooms alone that no season changes. Never the ground
	# and the wall of the maps outside, which floored a room with grass and walled it with a
	# hedge. (Should the drawn tile set be missing, the room is painted as it was.)
	var rect := Rect2i(Vector2i.ZERO, size)
	var indoors := not geo.isometric and JsonUtil.to_str(def.get("name", "")) == "interior"
	var floor_tile := geo.find_tile("GROUND") if indoors else {}
	var wall := geo.wall_tile() if indoors else {}
	if not floor_tile.is_empty():
		MapUtil.fill(ground, rect, floor_tile)
	elif not RoomRecipe.use_floor(ground, rect):
		MapUtil.fill(ground, rect, geo.find_tile("GROUND"))
	if geo.isometric:
		geo.paint_walls(root, nodes, size, [way_out])
	elif not wall.is_empty() and nodes.has("Walls"):
		var walls: TileMapLayer = nodes["Walls"]
		MapUtil.border(walls, rect, wall, [way_out])
	else:
		var drawn_walls: TileMapLayer = nodes.get("Walls")
		RoomRecipe.use_wall(drawn_walls, rect, [way_out])
		geo.border_collision(root, size, [way_out])
	MapUtil.add_marker(spawns, root, "default", geo.center(arrive), true, "up")
	geo.add_exit_door(triggers, root, "Exit", way_out, FARM_PATH, StringName(door_spawn(JsonUtil.to_str(building.get("id", "")))))
	var player_cell := arrive
	var markers := Node2D.new()
	SceneUtil.add(root, markers, root, "Markers")
	var bed_plan := JsonUtil.to_dict(room.get("bed", {}))
	if not bed_plan.is_empty():
		player_cell = _add_bed(ctx, room, bed_plan, root, nodes, geo)
		# the calendar on the wall of the farmhouse (T17.25): only in a farm with festivals
		EventsRecipe.add_wall_calendar(root, entities, size, cell_of(bed_plan.get("cell")), geo)
	if JsonUtil.to_array(room.get("trough")).size() == 2:
		MapUtil.add_marker(markers, root, "Trough", geo.center(cell_of(room.get("trough"))))
	var stalls := cells_of(room.get("stalls"))
	for i in stalls.size():
		MapUtil.add_marker(markers, root, "Stall%d" % (i + 1), geo.center(stalls[i]))
	if MapUtil.place(PLAYER_SCENE, entities, root, geo.center(player_cell)) == null:
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		root.free()
		return null
	return root

## The bed at its cells (its head at the plan's cell) and the spawn `start` beside it, where a
## new game begins and the farmer wakes. Returns the cell of that spawn.
func _add_bed(ctx: BuildContext, room: Dictionary, bed_plan: Dictionary, root: Node2D, nodes: Dictionary, geo: MapGeo) -> Vector2i:
	var tile_px := geo.tile_px
	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var bed := SceneUtil.instance(HomeRecipe.BED_SCENE) as Node2D
	if bed == null:
		bed = HomeRecipe.build_bed(ctx)
	var footprint: Vector2i = bed.get("footprint")
	var head := cell_of(bed_plan.get("cell"))
	# a bed for two (T17.26: the plan's `sleepers`): a second bed east of the first, both
	# waking the farmer on the same cell
	var two := JsonUtil.to_int(bed_plan.get("sleepers", 1), 1) >= 2
	var lying := Vector2i(footprint.x * (2 if two else 1), footprint.y)
	var start := start_cell(cell_of(room.get("start")), head, lying, cell_of(room.get("size")))
	var facing := JsonUtil.to_str(JsonUtil.to_dict(plan().get("start", {})).get("facing", "down"))
	var beds: Array[Node2D] = [bed]
	if two:
		var second := SceneUtil.instance(HomeRecipe.BED_SCENE) as Node2D
		if second == null:
			second = HomeRecipe.build_bed(ctx)
		second.name = BED_TWO
		beds.append(second)
	for i in beds.size():
		var one := beds[i]
		var at := head + Vector2i(footprint.x * i, 0)
		# its foot is the lowest row of its cells, and the middle of their width; on diamonds
		# the middle of the one of its cells nearest the camera
		if geo.isometric:
			one.position = geo.center(at + footprint - Vector2i.ONE)
		else:
			one.position = Vector2(at.x * tile_px + footprint.x * tile_px * 0.5, (at.y + footprint.y) * tile_px)
		one.set("wake_offset", geo.center(start) - one.position)
		one.set("wake_facing", facing)
		entities.add_child(one)
		one.owner = root
	MapUtil.add_marker(spawns, root, START_SPAWN, geo.center(start), true, facing)
	return start
