extends RefCounted
## Seeds game/maps/starter_map.tscn once (user_seed ownership: never rewritten afterwards).
##
## The layout comes from MapBuild.plan (builder/lib/map_build.gd) and the `starter_map` options of
## the config: size, buildings, NPCs, enemies, chests, decorations, ground patches and the ground
## set. With the default options the plan is the map of every project made before M11.
## When the config picks an imported Tiled or LDtk map as the starter map (`imported_maps.starter`,
## T12.49) the planner is skipped and that map is built instead (imported_maps_recipe.gd).

const RECIPE_VERSION := 8
## The version of what the recipe does for an isometric project only (T17.14): it is in the hash
## of such a project and of no other, so a change of the isometric painting rebuilds nothing of
## a project seen from above.
const ISO_VERSION := 1

const Paths := preload("../lib/paths.gd")
const JsonUtil := preload("../lib/json_util.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const MapUtil := preload("../lib/map_util.gd")
const MapBuild := preload("../lib/map_build.gd")
const ObjectEntries := preload("../lib/object_entries.gd")
const ObjectIndex := preload("../lib/object_index.gd")
const SeedUtil := preload("../lib/seed_util.gd")
const ActorRecipes := preload("actor_recipes.gd")
const BuildContext := preload("../lib/build_context.gd")
const ImportedMaps := preload("imported_maps_recipe.gd")
const WorldPlan := preload("../lib/world_plan.gd")
const MapGeo := preload("../lib/map_geo.gd")

const OUT_PATH := "res://game/maps/starter_map.tscn"
## The entities of the demo placed in the starter map (T8.08 removes exactly these).
const DEMO_ENTITIES_PATH := "res://rpggen/demo_entities.json"
const INTERIOR_PATH := "res://game/maps/interior_1.tscn"  # the first house's
const InteriorRecipe := preload("interior_recipe.gd")
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const GREETING_PATH := "res://game/data/dialogue/npc_greeting.tres"
const NPC_ID := "starter_map_npc_001"
const CHEST_ID := "starter_map_chest_001"
const ENEMY_ID := "starter_map_enemy_001"
const ENEMY2_ID := "starter_map_enemy_002"
## Archetype -> recipe that knows its enemies (builder/recipes/<this>); the archetypes without one place none.
const ENEMY_RECIPES := {"turn_based": "turn_based/enemy_recipes.gd", "arpg": "arpg/enemy_recipes.gd"}
## Archetype -> recipe that adds its own parts to the map before it is saved (builder/recipes/<this>),
## with a static `prepare(layout, house, skip)` (asked before the walls are painted: `gaps`, cells
## of the wall to leave open, and `npcs`, how many of the planner's NPCs are placed), a static
## `augment_map(ctx, root, nodes, layout, house, kept_free, prepared)` and a static `map_hash()`.
## The village of a farm gets its door to the farm (T17.06) and its people (T17.09); the other
## archetypes have none and their map is what it was.
const MAP_AUGMENTERS := {"farm": "farm/people_recipes.gd"}
const TILESET_PATH := "res://generated/tilesets/overworld.tres"
## The second outdoor map and the way to it (T11.23): a gap in the east wall of the starter map.
const FIELD_PATH := "res://game/maps/field_1.tscn"
const EAST_EXIT_NAME := "starter_map_east_exit"
## The spawn point of the starter map where the player arrives from the field.
const EAST_ENTRY := "east_entry"

## Only listed while the file does not exist yet, so an existing (possibly edited) map is kept.
func outputs(_ctx: BuildContext) -> PackedStringArray:
	if FileAccess.file_exists(OUT_PATH):
		return PackedStringArray()
	return PackedStringArray([OUT_PATH, DEMO_ENTITIES_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash(_iso_hash(ctx).merged({
		"v": RECIPE_VERSION,
		"overworld": ctx.catalog.tileset_def("overworld"),
		"layers": ctx.config.get("map_layers", []),
		"seed": ctx.config.get("seed", 0),
		"starter": ctx.config.get("starter", {}),
		"starter_map": ctx.config.get("starter_map", {}),
		"imported": ImportedMaps.starter_map(ctx),
		"music": JsonUtil.to_str(ctx.section("sounds").get("music_map", "")),
		"entries": ObjectEntries.entries(ctx),
		"npc": _npc_scene(ctx),
		"chest": ObjectEntries.chest_entry(ctx).get("id", ""),
		"enemy": _enemy_scene(ctx),
		"demo_removed": ctx.demo_removed,
		"demo": ctx.section("features").get("demo", true),
		"world": WorldPlan.area(WorldPlan.read(), WorldPlan.VILLAGE_ID),
	}).merged(_augmenter_hash(ctx)))

## What an isometric project's map is made from beside the rest (T17.14): its tile set of
## diamonds. Nothing for a project seen from above, whose hash is what it was.
static func _iso_hash(ctx: BuildContext) -> Dictionary:
	if not MapGeo.is_isometric(ctx):
		return {}
	return {"iso": MapGeo.new(ctx).def, "iso_v": ISO_VERSION}

## The archetype's map augmenter (MAP_AUGMENTERS), or null.
func _augmenter(ctx: BuildContext) -> GDScript:
	var rel: String = MAP_AUGMENTERS.get(JsonUtil.to_str(ctx.config.get("archetype", "")), "")
	if rel == "":
		return null
	var here: Script = get_script()
	return load(here.resource_path.get_base_dir().path_join(rel)) as GDScript

## What the augmenter adds to the hash: nothing for an archetype without one.
func _augmenter_hash(ctx: BuildContext) -> Dictionary:
	var augmenter := _augmenter(ctx)
	return {"augmenter": augmenter.call("map_hash")} if augmenter != null else {}

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	if FileAccess.file_exists(OUT_PATH):
		return issues
	var imported := ImportedMaps.starter_map(ctx)
	if not imported.is_empty():
		issues.append_array(ImportedMaps.build_map(ctx, imported, OUT_PATH, "StarterMap", "starter_map"))
		var no_entities: Array = []
		_write_demo_entities(no_entities, issues, ctx, false)  # an imported map has no demo content
		return issues
	# the seam between the plan's cells and the map's px (T17.14): squares, or diamonds
	var geo := MapGeo.new(ctx)
	if geo.def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, OUT_PATH))
		return issues
	var tile_set := geo.load_tile_set()
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": geo.tileset_path()}, geo.tileset_path()))
		return issues
	if not ResourceLoader.exists(PLAYER_SCENE):
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		return issues

	var building := ObjectEntries.starter_building(ctx)
	var house := geo.building_info(building)
	var house_cells := Vector2i.ZERO
	if not house.is_empty():
		house_cells = Vector2i(JsonUtil.to_int(house["size"][0]), JsonUtil.to_int(house["size"][1]))
	var layout := MapBuild.plan(
		ctx.section("starter_map"), JsonUtil.to_int(ctx.config.get("seed", 12345)),
		house, JsonUtil.to_str(ctx.config.get("archetype", "turn_based")))
	var notes: Array = layout["warnings"]
	for note: Variant in notes:
		print("[rpggen] INFO starter_map: ", note)
	var size: Vector2i = layout["size"]
	# a world of areas (T13.20): the village's doors come from the stored plan, and the demo's
	# east exit to field_1 is not made
	var village := WorldPlan.area(WorldPlan.read(), WorldPlan.VILLAGE_ID)
	var world_doors := _world_doors(village, layout, house)
	var east_exit := east_exit_wanted(ctx) and village.is_empty()

	var root := MapUtil.new_map_root("StarterMap", "starter_map")
	root.set("music_asset_id", JsonUtil.to_str(ctx.section("sounds").get("music_map", "")))
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var ground: TileMapLayer = nodes["Ground"]
	_paint_ground(ctx, geo, ground, building, layout)
	var exit_gap: Vector2i = layout["exit_gap"]
	var skip: Array[Vector2i] = []
	if east_exit:
		skip.append(exit_gap)
	for world_door in world_doors:
		var gap_cell: Vector2i = world_door["cell"]
		skip.append(gap_cell)
	var augmenter := _augmenter(ctx)
	var prepared := {}
	if augmenter != null:
		prepared = JsonUtil.to_dict(augmenter.call("prepare", layout, house_cells, skip))
		var gaps: Array = prepared.get("gaps", [])
		for gap: Vector2i in gaps:
			skip.append(gap)
	geo.paint_walls(root, nodes, size, skip)
	var building_tiles: Array[Vector2i] = layout["buildings"]
	if not building.is_empty():
		var index := 0
		for tile in building_tiles:
			_place_building(building, root, entities, geo, tile, index)
			index += 1
	var decoration_tiles: Array[Vector2i] = layout["decorations"]
	_place_decorations(ctx, root, entities, geo, decoration_tiles)
	var npc_tiles: Array[Vector2i] = layout["npcs"]
	if prepared.has("npcs"):  # the archetype places people of its own where the others would stand
		npc_tiles = npc_tiles.slice(0, JsonUtil.to_int(prepared["npcs"]))
	var chest_tiles: Array[Vector2i] = layout["chests"]
	var enemy_tiles: Array[Vector2i] = layout["enemies"]
	var placed: Array = []  # ids of the demo entities, for "Remove demo content"
	if not ctx.demo_removed:
		_place_npcs(ctx, root, entities, geo, npc_tiles, issues, placed)
		_place_chests(ctx, root, entities, geo, chest_tiles, issues, placed)
		_place_enemies(ctx, root, entities, geo, enemy_tiles, placed)

	var spawn: Vector2i = layout["spawn"]
	MapUtil.add_marker(spawns, root, "default", geo.center(spawn), true)
	var spots := {"npc_spot": npc_tiles, "enemy_spot": enemy_tiles, "chest_spot": chest_tiles}
	for spot: String in spots.keys():
		var spot_tiles: Array[Vector2i] = spots[spot]
		if not spot_tiles.is_empty():
			MapUtil.add_marker(spawns, root, spot, geo.center(spot_tiles[0]))
	MapUtil.place(PLAYER_SCENE, entities, root, geo.center(spawn))
	# the roads of the map, in the order they were always painted: to the doors of the houses,
	# to the east exit, to the door of a world of areas that takes the exit's place
	var road := geo.find_tile("ROAD")
	var roads: Array = []
	if not building.is_empty() and nodes.has("GroundDetails"):
		var path_tiles: Array[Vector2i] = layout["path"]
		roads.append(path_tiles)
	if east_exit:
		var exit_tiles: Array[Vector2i] = layout["exit_path"]
		if nodes.has("GroundDetails"):
			roads.append(exit_tiles)
		var last: Vector2i = exit_tiles[exit_tiles.size() - 1]
		MapUtil.add_marker(spawns, root, EAST_ENTRY, geo.center(last), true, "left")
		var triggers: Node2D = nodes["Triggers"]
		geo.add_exit_door(triggers, root, EAST_EXIT_NAME, exit_gap, FIELD_PATH, &"west_entry")
	for world_door in world_doors:
		var door: Dictionary = world_door["door"]
		var door_cell: Vector2i = world_door["cell"]
		var arrive: Vector2i = world_door["spawn"]
		if world_door["road"] and nodes.has("GroundDetails"):
			var road_tiles: Array[Vector2i] = layout["exit_path"]
			roads.append(road_tiles)
		WorldPlan.add_door(door, door_cell, arrive, root, nodes, geo)
		var gate := WorldPlan.gate_of(village, JsonUtil.to_str(door.get("id", "")))
		if not gate.is_empty():
			WorldPlan.add_gate(gate, door_cell, root, entities, geo)
	if nodes.has("GroundDetails"):
		var details: TileMapLayer = nodes["GroundDetails"]
		geo.paint_runs(details, roads, "ROAD", road)
	for note in geo.take_notes():
		print("[rpggen] INFO starter_map: ", note)

	if augmenter != null:
		var kept_free: Array[Vector2i] = skip.duplicate()
		for world_door in world_doors:
			var door_spawn: Vector2i = world_door["spawn"]
			kept_free.append(door_spawn)
		augmenter.call("augment_map", ctx, root, nodes, layout, house_cells, kept_free, prepared)

	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	_write_demo_entities(placed, issues, ctx, east_exit)
	return issues

## The village's doors of the world plan as [{door, cell, spawn, road}]. The east door uses the
## planner's own exit (the gap its road leads to); every other door takes the plan's cell, moved
## along the wall until the floor in front of it is free of what the planner placed.
func _world_doors(village: Dictionary, layout: Dictionary, building_info: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if village.is_empty():
		return out
	var size: Vector2i = layout["size"]
	var blocked := {}
	var houses: Array[Vector2i] = layout["buildings"]
	var house_size := Vector2i(1, 1)
	if not building_info.is_empty():
		house_size = Vector2i(JsonUtil.to_int(building_info["size"][0]), JsonUtil.to_int(building_info["size"][1]))
	for house in houses:
		for dx in range(-1, house_size.x + 1):
			for dy in range(-1, house_size.y + 2):
				blocked[house + Vector2i(dx, dy)] = true
	for key: String in ["decorations", "npcs", "chests", "enemies"]:
		var tiles: Array[Vector2i] = layout[key]
		for tile in tiles:
			blocked[tile] = true
	var east_used := false
	for door in WorldPlan.list_of(village, "doors"):
		var edge := JsonUtil.to_str(door.get("edge", ""))
		if edge == "E" and not east_used:
			east_used = true
			var exit_tiles: Array[Vector2i] = layout["exit_path"]
			var gap: Vector2i = layout["exit_gap"]
			out.append({"door": door, "cell": gap, "spawn": exit_tiles[exit_tiles.size() - 1], "road": true})
			continue
		var wanted := WorldPlan.cell(door.get("cell"))
		match edge:  # the plan was made for the planned size; the map may differ
			"E":
				wanted.x = size.x - 1
			"S":
				wanted.y = size.y - 1
		wanted = Vector2i(clampi(wanted.x, 0, size.x - 1), clampi(wanted.y, 0, size.y - 1))
		var cell := WorldPlan.free_edge_cell(wanted, edge, size, blocked)
		blocked[WorldPlan.inside(edge, cell)] = true
		out.append({"door": door, "cell": cell, "spawn": WorldPlan.inside(edge, cell), "road": false})
	return out

## The size of the starter building in cells; (0, 0) without one.
static func _house_cells(building: Dictionary, tile_px: int) -> Vector2i:
	var info := _building_info(building, tile_px)
	if info.is_empty():
		return Vector2i.ZERO
	return Vector2i(JsonUtil.to_int(info["size"][0]), JsonUtil.to_int(info["size"][1]))

## The east exit and the field behind it belong to the demo: they exist when the demo is on.
static func east_exit_wanted(ctx: BuildContext) -> bool:
	return JsonUtil.to_bool(ctx.section("features").get("demo", true)) and not ctx.demo_removed

## {size: [w, h] tiles, door: [dx, dy] tiles from the top-left corner, one row below the base}
## of the starter building for MapBuild.plan; {} when there is none.
static func _building_info(building: Dictionary, tile_px: int) -> Dictionary:
	if building.is_empty():
		return {}
	var region: Array = building["region"]
	var door_px := Vector2(JsonUtil.to_float(region[2]) / 2.0, JsonUtil.to_float(region[3]) - 1.0)
	var door_info: Array = building["door"]
	if door_info.size() == 2:
		door_px = Vector2(JsonUtil.to_float(door_info[0]), JsonUtil.to_float(door_info[1]))
	return {
		"size": [ceili(JsonUtil.to_float(region[2]) / tile_px), ceili(JsonUtil.to_float(region[3]) / tile_px)],
		"door": [floori(float(int(door_px.x)) / tile_px), floori(float(int(door_px.y)) / tile_px) + 1],
	}

## Ids of the demo entities the map holds, for the dock's "Remove demo content" (T8.08).
func _write_demo_entities(placed: Array, issues: Array, ctx: BuildContext, east_exit: bool) -> void:
	var data := {"demo_entities_version": 1, "map": OUT_PATH, "entities": placed}
	if east_exit:
		data["east_exit"] = EAST_EXIT_NAME  # the field map is built (once) only for a map that has this
		data["extra_maps"] = {}
	var err := JsonUtil.write(DEMO_ENTITIES_PATH, data)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": DEMO_ENTITIES_PATH, "err": err}, DEMO_ENTITIES_PATH))

func _ground_tile(ctx: BuildContext, geo: MapGeo) -> Dictionary:
	var wanted := JsonUtil.to_str(ctx.section("starter_map").get("ground", ""))
	if wanted == "":
		wanted = JsonUtil.to_str(ctx.section("starter").get("ground", ""))
	if wanted != "":
		var tile := geo.tile_of_asset(wanted)
		if not tile.is_empty():
			return tile
	return geo.find_tile("GROUND")

## The house area (in tiles) that patches of other ground stay away from (the default map only).
func _house_area(building: Dictionary, geo: MapGeo) -> Rect2i:
	if building.is_empty():
		return Rect2i()
	var info := geo.building_info(building)
	var size := Vector2i(JsonUtil.to_int(info["size"][0]), JsonUtil.to_int(info["size"][1]))
	return Rect2i(MapBuild.DEFAULT_HOUSE - Vector2i(2, 2), size + Vector2i(4, 4))

## The ground of the map: one tile everywhere and a few patches of others, by the seed. Seen
## from above the others are tiles of the same sheet; an isometric pack's are its other flat
## ground tiles.
func _paint_ground(ctx: BuildContext, geo: MapGeo, ground: TileMapLayer, building: Dictionary, layout: Dictionary) -> void:
	var base := _ground_tile(ctx, geo)
	if base.is_empty():
		return
	var size: Vector2i = layout["size"]
	MapBuild.fill_ground(ground, size, base)
	var others := geo.other_tiles(base, 3)
	if others.is_empty():
		return
	if layout["legacy_patches"]:
		MapBuild.paint_legacy_patches(ground, size, others, JsonUtil.to_int(ctx.config.get("seed", 12345)), JsonUtil.to_int(layout["patch_count"]), _house_area(building, geo))
	else:
		var patches: Array[Dictionary] = layout["patches"]
		MapBuild.paint_planned_patches(ground, patches, others)

func _place_building(building: Dictionary, root: Node2D, entities: Node2D, geo: MapGeo, tile: Vector2i, index: int) -> void:
	var building_id: String = building["id"]
	var path: String = ObjectIndex.scene_path(building_id)
	var node_name := ""
	if index > 0:
		node_name = JsonUtil.to_str(building["name"]).validate_node_name() + str(index + 1)
	var inst := MapUtil.place(path, entities, root, geo.building_position(building, tile), node_name)
	if inst == null:
		return
	# Properties of nodes inside an instanced scene are saved only when it is editable.
	root.set_editable_instance(inst, true)
	# each house has an interior of its own, and its own spawn to come back to (T13.12)
	var entrance := inst.get_node_or_null("Entrance")
	if entrance != null:
		entrance.set("target_map", InteriorRecipe.interior_path(index + 1))
		entrance.set("target_spawn", &"default")
	var exit_spawn := inst.get_node_or_null("ExitSpawn")
	if exit_spawn != null and index > 0:
		exit_spawn.set("spawn_id", InteriorRecipe.exit_spawn_for(building_id, index + 1))

func _place_decorations(ctx: BuildContext, root: Node2D, entities: Node2D, geo: MapGeo, tiles: Array[Vector2i]) -> void:
	var decor: Array[Dictionary] = []
	for e in ObjectEntries.entries(ctx):
		var decor_id: String = e["id"]
		if e["role"] == "DECORATION" and ResourceLoader.exists(ObjectIndex.scene_path(decor_id)):
			decor.append(e)
	if decor.is_empty():
		return
	for i in tiles.size():
		var e: Dictionary = decor[i % decor.size()]
		# The feet sit at the bottom-center of the tile (the middle of a diamond).
		var pos := geo.foot(tiles[i])
		var scene_id: String = e["id"]
		MapUtil.place(ObjectIndex.scene_path(scene_id), entities, root, pos, "Decor%d" % (i + 1))

## The NPC scene of the demo: the starter NPC asset, else any NPC character, else the fallback
## built from the player's sprite. "" when none exists.
func _npc_scene(ctx: BuildContext) -> String:
	var wanted := JsonUtil.to_str(ctx.section("starter").get("npc", ""))
	if wanted != "":
		var path := ActorRecipes.character_scene_path(wanted)
		if ResourceLoader.exists(path):
			return path
	for a in ctx.catalog.assets_by_role("NPC"):
		var npc_id: String = a["id"]
		var path := ActorRecipes.character_scene_path(npc_id)
		if ResourceLoader.exists(path):
			return path
	if ResourceLoader.exists(ActorRecipes.FALLBACK_NPC_PATH):
		return ActorRecipes.FALLBACK_NPC_PATH
	return ""

func _place_npcs(ctx: BuildContext, root: Node2D, entities: Node2D, geo: MapGeo, tiles: Array[Vector2i], issues: Array, placed: Array) -> void:
	var scene := _npc_scene(ctx)
	if scene == "":
		return
	if scene == ActorRecipes.FALLBACK_NPC_PATH:
		issues.append(ctx.make_issue("ASSET-022", {}))
	for i in tiles.size():
		var npc := MapUtil.place(scene, entities, root, geo.center(tiles[i]), "Npc%d" % (i + 1))
		if npc == null:
			continue
		var id := "starter_map_npc_%03d" % (i + 1)
		npc.set("entity_id", id)
		npc.set("facing", "down")
		if ResourceLoader.exists(GREETING_PATH):
			npc.set("dialogue", load(GREETING_PATH))
		placed.append(id)

func _place_chests(ctx: BuildContext, root: Node2D, entities: Node2D, geo: MapGeo, tiles: Array[Vector2i], issues: Array, placed: Array) -> void:
	var entry := ObjectEntries.chest_entry(ctx)
	if entry.is_empty():
		return
	if entry.get("fallback", false):
		issues.append(ctx.make_issue("ASSET-023", {"asset": entry["id"]}))
	var entry_id: String = entry["id"]
	var path: String = ObjectIndex.scene_path(entry_id)
	for i in tiles.size():
		var chest := MapUtil.place(path, entities, root, geo.center(tiles[i]), "Chest%d" % (i + 1))
		if chest == null:
			continue
		var id := "starter_map_chest_%03d" % (i + 1)
		chest.set("entity_id", id)
		chest.set("loot", SeedUtil.dict_array([{"item_id": "potion", "qty": 1}]))
		chest.set("gold", 20 + 10 * i)
		placed.append(id)

## The scene of the starter enemy, from the archetype's enemy recipe. "" when the archetype has none.
func _enemy_scene(ctx: BuildContext, index: int = 0) -> String:
	var rel: String = ENEMY_RECIPES.get(JsonUtil.to_str(ctx.config.get("archetype", "")), "")
	if rel == "":
		return ""
	var here: Script = get_script()
	var script := load(here.resource_path.get_base_dir().path_join(rel)) as GDScript
	if script == null:
		return ""
	var recipe: RefCounted = script.new()
	if index > 0:
		return JsonUtil.to_str(recipe.call("starter_scene_at", ctx, index)) if recipe.has_method("starter_scene_at") else ""
	return JsonUtil.to_str(recipe.call("starter_scene", ctx))

func _place_enemies(ctx: BuildContext, root: Node2D, entities: Node2D, geo: MapGeo, tiles: Array[Vector2i], placed: Array) -> void:
	for i in tiles.size():
		var scene := _enemy_scene(ctx, i)
		if scene == "":
			scene = _enemy_scene(ctx)  # an archetype with one kind of enemy places it again
		if scene == "":
			return
		var enemy := MapUtil.place(scene, entities, root, geo.center(tiles[i]), "Enemy%d" % (i + 1))
		if enemy != null:
			var id := "starter_map_enemy_%03d" % (i + 1)
			enemy.set("entity_id", id)
			enemy.set("facing", "down")
			placed.append(id)
