extends RefCounted
## Seeds game/maps/starter_map.tscn once (user_seed ownership: never rewritten afterwards).
##
## The layout comes from MapBuild.plan (builder/lib/map_build.gd) and the `starter_map` options of
## the config: size, buildings, NPCs, enemies, chests, decorations, ground patches and the ground
## set. With the default options the plan is the map of every project made before M11.

const RECIPE_VERSION := 7

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

const OUT_PATH := "res://game/maps/starter_map.tscn"
## The entities of the demo placed in the starter map (T8.08 removes exactly these).
const DEMO_ENTITIES_PATH := "res://rpggen/demo_entities.json"
const INTERIOR_PATH := "res://game/maps/interior_1.tscn"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const GREETING_PATH := "res://game/data/dialogue/npc_greeting.tres"
const NPC_ID := "starter_map_npc_001"
const CHEST_ID := "starter_map_chest_001"
const ENEMY_ID := "starter_map_enemy_001"
const ENEMY2_ID := "starter_map_enemy_002"
## Archetype -> recipe that knows its enemies (builder/recipes/<this>); the archetypes without one place none.
const ENEMY_RECIPES := {"turn_based": "turn_based/enemy_recipes.gd", "arpg": "arpg/enemy_recipes.gd"}
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
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"overworld": ctx.catalog.tileset_def("overworld"),
		"layers": ctx.config.get("map_layers", []),
		"seed": ctx.config.get("seed", 0),
		"starter": ctx.config.get("starter", {}),
		"starter_map": ctx.config.get("starter_map", {}),
		"music": JsonUtil.to_str(ctx.section("sounds").get("music_map", "")),
		"entries": ObjectEntries.entries(ctx),
		"npc": _npc_scene(ctx),
		"chest": ObjectEntries.chest_entry(ctx).get("id", ""),
		"enemy": _enemy_scene(ctx),
		"demo_removed": ctx.demo_removed,
		"demo": ctx.section("features").get("demo", true),
	})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	if FileAccess.file_exists(OUT_PATH):
		return issues
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, OUT_PATH))
		return issues
	var tile_set := load(TILESET_PATH) as TileSet
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": TILESET_PATH}, TILESET_PATH))
		return issues
	if not ResourceLoader.exists(PLAYER_SCENE):
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		return issues
	var tile_px: int = JsonUtil.to_int(def["tile_size"][0])

	var building := ObjectEntries.starter_building(ctx)
	var layout := MapBuild.plan(
		ctx.section("starter_map"), JsonUtil.to_int(ctx.config.get("seed", 12345)),
		_building_info(building, tile_px), JsonUtil.to_str(ctx.config.get("archetype", "turn_based")))
	var notes: Array = layout["warnings"]
	for note: Variant in notes:
		print("[rpggen] INFO starter_map: ", note)
	var size: Vector2i = layout["size"]
	var east_exit := east_exit_wanted(ctx)

	var root := MapUtil.new_map_root("StarterMap", "starter_map")
	root.set("music_asset_id", JsonUtil.to_str(ctx.section("sounds").get("music_map", "")))
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var ground: TileMapLayer = nodes["Ground"]
	_paint_ground(ctx, def, tile_set, ground, building, tile_px, layout)
	var exit_gap: Vector2i = layout["exit_gap"]
	var skip: Array[Vector2i] = []
	if east_exit:
		skip.append(exit_gap)
	MapBuild.paint_walls(root, nodes, size, MapUtil.wall_tile(ctx, def, tile_set), tile_px, skip)
	var building_tiles: Array[Vector2i] = layout["buildings"]
	if not building.is_empty():
		var index := 0
		for tile in building_tiles:
			_place_building(building, root, entities, tile_px, tile, index)
			index += 1
	var decoration_tiles: Array[Vector2i] = layout["decorations"]
	_place_decorations(ctx, root, entities, tile_px, decoration_tiles)
	var npc_tiles: Array[Vector2i] = layout["npcs"]
	var chest_tiles: Array[Vector2i] = layout["chests"]
	var enemy_tiles: Array[Vector2i] = layout["enemies"]
	var placed: Array = []  # ids of the demo entities, for "Remove demo content"
	if not ctx.demo_removed:
		_place_npcs(ctx, root, entities, tile_px, npc_tiles, issues, placed)
		_place_chests(ctx, root, entities, tile_px, chest_tiles, issues, placed)
		_place_enemies(ctx, root, entities, tile_px, enemy_tiles, placed)

	var spawn: Vector2i = layout["spawn"]
	MapUtil.add_marker(spawns, root, "default", MapUtil.tile_center(spawn, tile_px), true)
	var spots := {"npc_spot": npc_tiles, "enemy_spot": enemy_tiles, "chest_spot": chest_tiles}
	for spot: String in spots.keys():
		var spot_tiles: Array[Vector2i] = spots[spot]
		if not spot_tiles.is_empty():
			MapUtil.add_marker(spawns, root, spot, MapUtil.tile_center(spot_tiles[0], tile_px))
	MapUtil.place(PLAYER_SCENE, entities, root, MapUtil.tile_center(spawn, tile_px))
	var road := MapUtil.find_tile(ctx, def, tile_set, "ROAD")
	if not building.is_empty() and nodes.has("GroundDetails"):
		var details: TileMapLayer = nodes["GroundDetails"]
		var path_tiles: Array[Vector2i] = layout["path"]
		MapBuild.paint_path(details, path_tiles, road)
	if east_exit:
		var exit_tiles: Array[Vector2i] = layout["exit_path"]
		if nodes.has("GroundDetails"):
			var exit_details: TileMapLayer = nodes["GroundDetails"]
			MapBuild.paint_path(exit_details, exit_tiles, road)
		var last: Vector2i = exit_tiles[exit_tiles.size() - 1]
		MapUtil.add_marker(spawns, root, EAST_ENTRY, MapUtil.tile_center(last, tile_px), true, "left")
		var triggers: Node2D = nodes["Triggers"]
		MapBuild.add_exit_door(triggers, root, EAST_EXIT_NAME, exit_gap, tile_px, FIELD_PATH, &"west_entry")

	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	_write_demo_entities(placed, issues, ctx, east_exit)
	return issues

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

func _ground_tile(ctx: BuildContext, def: Dictionary, tile_set: TileSet) -> Dictionary:
	var wanted := JsonUtil.to_str(ctx.section("starter_map").get("ground", ""))
	if wanted == "":
		wanted = JsonUtil.to_str(ctx.section("starter").get("ground", ""))
	if wanted != "":
		var tile := MapUtil.tile_of_asset(ctx, def, tile_set, wanted)
		if not tile.is_empty():
			return tile
	return MapUtil.find_tile(ctx, def, tile_set, "GROUND")

## The house area (in tiles) that patches of other ground stay away from (the default map only).
func _house_area(building: Dictionary, tile_px: int) -> Rect2i:
	if building.is_empty():
		return Rect2i()
	var region: Array = building["region"]
	var size := Vector2i(ceili(JsonUtil.to_float(region[2]) / tile_px), ceili(JsonUtil.to_float(region[3]) / tile_px))
	return Rect2i(MapBuild.DEFAULT_HOUSE - Vector2i(2, 2), size + Vector2i(4, 4))

func _paint_ground(ctx: BuildContext, def: Dictionary, tile_set: TileSet, ground: TileMapLayer, building: Dictionary, tile_px: int, layout: Dictionary) -> void:
	var base := _ground_tile(ctx, def, tile_set)
	if base.is_empty():
		return
	var size: Vector2i = layout["size"]
	MapBuild.fill_ground(ground, size, base)
	var others := MapUtil.other_tiles(tile_set, base, 3)
	if others.is_empty():
		return
	if layout["legacy_patches"]:
		MapBuild.paint_legacy_patches(ground, size, others, JsonUtil.to_int(ctx.config.get("seed", 12345)), JsonUtil.to_int(layout["patch_count"]), _house_area(building, tile_px))
	else:
		var patches: Array[Dictionary] = layout["patches"]
		MapBuild.paint_planned_patches(ground, patches, others)

func _place_building(building: Dictionary, root: Node2D, entities: Node2D, tile_px: int, tile: Vector2i, index: int) -> void:
	var origin := Vector2(JsonUtil.to_float(building["origin"][0]), JsonUtil.to_float(building["origin"][1]))
	var building_id: String = building["id"]
	var path: String = ObjectIndex.scene_path(building_id)
	var node_name := ""
	if index > 0:
		node_name = JsonUtil.to_str(building["name"]).validate_node_name() + str(index + 1)
	var inst := MapUtil.place(path, entities, root, Vector2(tile) * tile_px + origin, node_name)
	if inst == null:
		return
	# Properties of nodes inside an instanced scene are saved only when it is editable.
	root.set_editable_instance(inst, true)
	var entrance := inst.get_node_or_null("Entrance")
	if entrance != null:
		entrance.set("target_map", INTERIOR_PATH)
		entrance.set("target_spawn", &"default")

func _place_decorations(ctx: BuildContext, root: Node2D, entities: Node2D, tile_px: int, tiles: Array[Vector2i]) -> void:
	var decor: Array[Dictionary] = []
	for e in ObjectEntries.entries(ctx):
		var decor_id: String = e["id"]
		if e["role"] == "DECORATION" and ResourceLoader.exists(ObjectIndex.scene_path(decor_id)):
			decor.append(e)
	if decor.is_empty():
		return
	for i in tiles.size():
		var e: Dictionary = decor[i % decor.size()]
		# The feet sit at the bottom-center of the tile.
		var pos := Vector2(tiles[i]) * tile_px + Vector2(tile_px / 2.0, tile_px - 1)
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

func _place_npcs(ctx: BuildContext, root: Node2D, entities: Node2D, tile_px: int, tiles: Array[Vector2i], issues: Array, placed: Array) -> void:
	var scene := _npc_scene(ctx)
	if scene == "":
		return
	if scene == ActorRecipes.FALLBACK_NPC_PATH:
		issues.append(ctx.make_issue("ASSET-022", {}))
	for i in tiles.size():
		var npc := MapUtil.place(scene, entities, root, MapUtil.tile_center(tiles[i], tile_px), "Npc%d" % (i + 1))
		if npc == null:
			continue
		var id := "starter_map_npc_%03d" % (i + 1)
		npc.set("entity_id", id)
		npc.set("facing", "down")
		if ResourceLoader.exists(GREETING_PATH):
			npc.set("dialogue", load(GREETING_PATH))
		placed.append(id)

func _place_chests(ctx: BuildContext, root: Node2D, entities: Node2D, tile_px: int, tiles: Array[Vector2i], issues: Array, placed: Array) -> void:
	var entry := ObjectEntries.chest_entry(ctx)
	if entry.is_empty():
		return
	if entry.get("fallback", false):
		issues.append(ctx.make_issue("ASSET-023", {"asset": entry["id"]}))
	var entry_id: String = entry["id"]
	var path: String = ObjectIndex.scene_path(entry_id)
	for i in tiles.size():
		var chest := MapUtil.place(path, entities, root, MapUtil.tile_center(tiles[i], tile_px), "Chest%d" % (i + 1))
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

func _place_enemies(ctx: BuildContext, root: Node2D, entities: Node2D, tile_px: int, tiles: Array[Vector2i], placed: Array) -> void:
	for i in tiles.size():
		var scene := _enemy_scene(ctx, i)
		if scene == "":
			scene = _enemy_scene(ctx)  # an archetype with one kind of enemy places it again
		if scene == "":
			return
		var enemy := MapUtil.place(scene, entities, root, MapUtil.tile_center(tiles[i], tile_px), "Enemy%d" % (i + 1))
		if enemy != null:
			var id := "starter_map_enemy_%03d" % (i + 1)
			enemy.set("entity_id", id)
			enemy.set("facing", "down")
			placed.append(id)
