extends RefCounted
## Seeds game/maps/starter_map.tscn once (user_seed ownership: never rewritten afterwards).

const RECIPE_VERSION := 4

const Paths := preload("../lib/paths.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const MapUtil := preload("../lib/map_util.gd")
const ObjectEntries := preload("../lib/object_entries.gd")
const ObjectIndex := preload("../lib/object_index.gd")
const SeedUtil := preload("../lib/seed_util.gd")
const ActorRecipes := preload("actor_recipes.gd")

const OUT_PATH := "res://game/maps/starter_map.tscn"
const INTERIOR_PATH := "res://game/maps/interior_1.tscn"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const GREETING_PATH := "res://game/data/dialogue/npc_greeting.tres"
const NPC_ID := "starter_map_npc_001"
const CHEST_ID := "starter_map_chest_001"
const ENEMY_ID := "starter_map_enemy_001"
## Archetype -> recipe that knows its enemies (builder/recipes/<this>); the archetypes without one place none.
const ENEMY_RECIPES := {"turn_based": "turn_based/enemy_recipes.gd"}
const TILESET_PATH := "res://generated/tilesets/overworld.tres"
const MAP_SIZE := Vector2i(40, 24)
const HOUSE_TILE := Vector2i(8, 6)
const SPAWN_TILE := Vector2i(12, 12)
const DECOR_TILES := [Vector2i(20, 4), Vector2i(24, 5), Vector2i(30, 8), Vector2i(33, 14),
	Vector2i(6, 17), Vector2i(14, 19), Vector2i(26, 18), Vector2i(35, 20)]
const RESERVED_SPOTS := {"npc_spot": Vector2i(16, 12), "enemy_spot": Vector2i(28, 12), "chest_spot": Vector2i(18, 8)}
const PATCHES := 6

## Only listed while the file does not exist yet, so an existing (possibly edited) map is kept.
func outputs(_ctx) -> PackedStringArray:
	if FileAccess.file_exists(OUT_PATH):
		return PackedStringArray()
	return PackedStringArray([OUT_PATH])

func input_hash(ctx) -> String:
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"overworld": ctx.catalog.tileset_def("overworld"),
		"layers": ctx.config.get("map_layers", []),
		"seed": ctx.config.get("seed", 0),
		"starter": ctx.config.get("starter", {}),
		"entries": ObjectEntries.entries(ctx),
		"npc": _npc_scene(ctx),
		"chest": ObjectEntries.chest_entry(ctx).get("id", ""),
		"enemy": _enemy_scene(ctx),
	})

func build(ctx) -> Array:
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
	var tile_px: int = int(def["tile_size"][0])

	var root := MapUtil.new_map_root("StarterMap", "starter_map")
	var nodes := MapUtil.build_layers(root, ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS), tile_set)
	var entities: Node2D = nodes["Entities"]
	var building := ObjectEntries.starter_building(ctx)

	_paint_ground(ctx, def, tile_set, nodes["Ground"], building, tile_px)
	_paint_walls(ctx, def, tile_set, root, nodes, tile_px)
	if not building.is_empty():
		_place_building(building, root, entities, tile_px)
	_place_decorations(ctx, root, entities, tile_px)
	_place_npc(ctx, root, entities, tile_px, issues)
	_place_chest(ctx, root, entities, tile_px, issues)
	_place_enemy(ctx, root, entities, tile_px)

	MapUtil.add_marker(nodes["SpawnPoints"], root, "default", MapUtil.tile_center(SPAWN_TILE, tile_px), true)
	for spot in RESERVED_SPOTS.keys():
		MapUtil.add_marker(nodes["SpawnPoints"], root, spot, MapUtil.tile_center(RESERVED_SPOTS[spot], tile_px))
	MapUtil.place(PLAYER_SCENE, entities, root, MapUtil.tile_center(SPAWN_TILE, tile_px))
	if not building.is_empty() and nodes.has("GroundDetails"):
		_paint_path(ctx, def, tile_set, nodes["GroundDetails"], building, tile_px)

	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues

func _ground_tile(ctx, def: Dictionary, tile_set: TileSet) -> Dictionary:
	var wanted := String(ctx.config.get("starter", {}).get("ground", ""))
	if wanted != "":
		var tile := MapUtil.tile_of_asset(ctx, def, tile_set, wanted)
		if not tile.is_empty():
			return tile
	return MapUtil.find_tile(ctx, def, tile_set, "GROUND")

## The house area (in tiles) that patches of other ground stay away from.
func _house_area(building: Dictionary, tile_px: int) -> Rect2i:
	if building.is_empty():
		return Rect2i()
	var region: Array = building["region"]
	var size := Vector2i(ceili(float(region[2]) / tile_px), ceili(float(region[3]) / tile_px))
	return Rect2i(HOUSE_TILE - Vector2i(2, 2), size + Vector2i(4, 4))

func _paint_ground(ctx, def: Dictionary, tile_set: TileSet, ground: TileMapLayer, building: Dictionary, tile_px: int) -> void:
	var base := _ground_tile(ctx, def, tile_set)
	if base.is_empty():
		return
	MapUtil.fill(ground, Rect2i(Vector2i.ZERO, MAP_SIZE), base)
	var others := MapUtil.other_tiles(tile_set, base, 3)
	if others.is_empty():
		return
	var rng := RandomNumberGenerator.new()
	rng.seed = int(ctx.config.get("seed", 12345))
	var house := _house_area(building, tile_px)
	for i in PATCHES:
		var size := Vector2i(rng.randi_range(2, 4), rng.randi_range(2, 4))
		var rect := Rect2i()
		for attempt in 20:
			var pos := Vector2i(rng.randi_range(2, MAP_SIZE.x - size.x - 2), rng.randi_range(2, MAP_SIZE.y - size.y - 2))
			rect = Rect2i(pos, size)
			if not rect.intersects(house):
				break
			rect = Rect2i()
		if rect.size != Vector2i.ZERO:
			MapUtil.fill(ground, rect, others[i % others.size()])

func _paint_walls(ctx, def: Dictionary, tile_set: TileSet, root: Node2D, nodes: Dictionary, tile_px: int) -> void:
	var wall := MapUtil.wall_tile(ctx, def, tile_set)
	var rect := Rect2i(Vector2i.ZERO, MAP_SIZE)
	if not wall.is_empty() and nodes.has("Walls"):
		MapUtil.border(nodes["Walls"], rect, wall)
	else:
		if not wall.is_empty():
			MapUtil.border(nodes["Ground"], rect, wall)  # looks like a wall; the rectangles block
		MapUtil.border_collision(root, MAP_SIZE, tile_px)

func _place_building(building: Dictionary, root: Node2D, entities: Node2D, tile_px: int) -> void:
	var origin := Vector2(float(building["origin"][0]), float(building["origin"][1]))
	var path: String = ObjectIndex.scene_path(building["id"])
	var inst := MapUtil.place(path, entities, root, Vector2(HOUSE_TILE) * tile_px + origin)
	if inst == null:
		return
	# Properties of nodes inside an instanced scene are saved only when it is editable.
	root.set_editable_instance(inst, true)
	var entrance := inst.get_node_or_null("Entrance")
	if entrance != null:
		entrance.set("target_map", INTERIOR_PATH)
		entrance.set("target_spawn", &"default")

func _place_decorations(ctx, root: Node2D, entities: Node2D, tile_px: int) -> void:
	var decor: Array = []
	for e in ObjectEntries.entries(ctx):
		if e["role"] == "DECORATION" and ResourceLoader.exists(ObjectIndex.scene_path(e["id"])):
			decor.append(e)
	if decor.is_empty():
		return
	for i in DECOR_TILES.size():
		var e: Dictionary = decor[i % decor.size()]
		# The feet sit at the bottom-center of the tile.
		var pos := Vector2(DECOR_TILES[i]) * tile_px + Vector2(tile_px / 2.0, tile_px - 1)
		MapUtil.place(ObjectIndex.scene_path(e["id"]), entities, root, pos, "Decor%d" % (i + 1))

## A path of ROAD tiles from the spawn to the house door on the GroundDetails layer.
func _paint_path(ctx, def: Dictionary, tile_set: TileSet, layer: TileMapLayer, building: Dictionary, tile_px: int) -> void:
	var road := MapUtil.find_tile(ctx, def, tile_set, "ROAD")
	if road.is_empty():
		return
	var door_px := Vector2(float(building["region"][2]) / 2.0, float(building["region"][3]) - 1.0)
	if building["door"].size() == 2:
		door_px = Vector2(float(building["door"][0]), float(building["door"][1]))
	var door_tile := HOUSE_TILE + Vector2i(int(door_px.x) / tile_px, int(door_px.y) / tile_px + 1)
	var step := 1 if door_tile.x >= SPAWN_TILE.x else -1
	for x in range(SPAWN_TILE.x, door_tile.x + step, step):
		layer.set_cell(Vector2i(x, SPAWN_TILE.y), road["source_id"], road["coords"], 0)
	for y in range(door_tile.y, SPAWN_TILE.y + 1):
		layer.set_cell(Vector2i(door_tile.x, y), road["source_id"], road["coords"], 0)

## The NPC scene of the demo: the starter NPC asset, else any NPC character, else the fallback
## built from the player's sprite. "" when none exists.
func _npc_scene(ctx) -> String:
	var wanted := String(ctx.config.get("starter", {}).get("npc", ""))
	if wanted != "":
		var path := ActorRecipes.character_scene_path(wanted)
		if ResourceLoader.exists(path):
			return path
	for a in ctx.catalog.assets_by_role("NPC"):
		var path := ActorRecipes.character_scene_path(a["id"])
		if ResourceLoader.exists(path):
			return path
	if ResourceLoader.exists(ActorRecipes.FALLBACK_NPC_PATH):
		return ActorRecipes.FALLBACK_NPC_PATH
	return ""

func _place_npc(ctx, root: Node2D, entities: Node2D, tile_px: int, issues: Array) -> void:
	var scene := _npc_scene(ctx)
	if scene == "":
		return
	if scene == ActorRecipes.FALLBACK_NPC_PATH:
		issues.append(ctx.make_issue("ASSET-022", {}))
	var npc := MapUtil.place(scene, entities, root, MapUtil.tile_center(RESERVED_SPOTS["npc_spot"], tile_px), "Npc1")
	if npc == null:
		return
	npc.set("entity_id", NPC_ID)
	npc.set("facing", "down")
	if ResourceLoader.exists(GREETING_PATH):
		npc.set("dialogue", load(GREETING_PATH))

func _place_chest(ctx, root: Node2D, entities: Node2D, tile_px: int, issues: Array) -> void:
	var entry := ObjectEntries.chest_entry(ctx)
	if entry.is_empty():
		return
	if entry.get("fallback", false):
		issues.append(ctx.make_issue("ASSET-023", {"asset": entry["id"]}))
	var path: String = ObjectIndex.scene_path(entry["id"])
	var chest := MapUtil.place(path, entities, root, MapUtil.tile_center(RESERVED_SPOTS["chest_spot"], tile_px), "Chest1")
	if chest == null:
		return
	chest.set("entity_id", CHEST_ID)
	chest.set("loot", SeedUtil.dict_array([{"item_id": "potion", "qty": 1}]))
	chest.set("gold", 20)

## The scene of the starter enemy, from the archetype's enemy recipe. "" when the archetype has none.
func _enemy_scene(ctx) -> String:
	var rel: String = ENEMY_RECIPES.get(String(ctx.config.get("archetype", "")), "")
	if rel == "":
		return ""
	var script := load(get_script().resource_path.get_base_dir().path_join(rel)) as GDScript
	return String(script.new().starter_scene(ctx)) if script != null else ""

func _place_enemy(ctx, root: Node2D, entities: Node2D, tile_px: int) -> void:
	var scene := _enemy_scene(ctx)
	if scene == "":
		return
	var enemy := MapUtil.place(scene, entities, root, MapUtil.tile_center(RESERVED_SPOTS["enemy_spot"], tile_px), "Enemy1")
	if enemy != null:
		enemy.set("entity_id", ENEMY_ID)
		enemy.set("facing", "down")
