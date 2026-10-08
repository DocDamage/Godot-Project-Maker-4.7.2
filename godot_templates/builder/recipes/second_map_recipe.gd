extends RefCounted
## Seeds game/maps/field_1.tscn once (user_seed ownership): a second outdoor map behind the east
## exit of the starter map (T11.23). It exists only for a starter map that has that exit (the
## starter map records it in rpggen/demo_entities.json), so a project made before M11 never gets
## new content forced into its map. Behind features.demo.

const RECIPE_VERSION := 1

const Paths := preload("../lib/paths.gd")
const JsonUtil := preload("../lib/json_util.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const MapUtil := preload("../lib/map_util.gd")
const MapBuild := preload("../lib/map_build.gd")
const ObjectEntries := preload("../lib/object_entries.gd")
const ObjectIndex := preload("../lib/object_index.gd")
const SeedUtil := preload("../lib/seed_util.gd")
const StarterMap := preload("starter_map_recipe.gd")
const BuildContext := preload("../lib/build_context.gd")

const OUT_PATH := "res://game/maps/field_1.tscn"
const TILESET_PATH := "res://generated/tilesets/overworld.tres"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const SIZE := Vector2i(32, 20)
const ENEMIES := 2
const DECORATIONS := 10
const PATCHES := 4
const CHEST_ID := "field_1_chest_001"

## True when the starter map has the east exit that leads here.
func _wanted(ctx: BuildContext) -> bool:
	if not JsonUtil.to_bool(ctx.section("features").get("demo", true)) or ctx.demo_removed:
		return false
	var data: Variant = JsonUtil.read(StarterMap.DEMO_ENTITIES_PATH)
	if not data is Dictionary:
		return false
	var table: Dictionary = data
	return str(table.get("east_exit", "")) != ""

func outputs(ctx: BuildContext) -> PackedStringArray:
	if FileAccess.file_exists(OUT_PATH) or not _wanted(ctx):
		return PackedStringArray()
	return PackedStringArray([OUT_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"wanted": _wanted(ctx),
		"overworld": ctx.catalog.tileset_def("overworld"),
		"layers": ctx.config.get("map_layers", []),
		"seed": ctx.config.get("seed", 0),
		"entries": ObjectEntries.entries(ctx),
		"chest": ObjectEntries.chest_entry(ctx).get("id", ""),
		"archetype": ctx.config.get("archetype", ""),
	})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	if FileAccess.file_exists(OUT_PATH) or not _wanted(ctx):
		return issues
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	var tile_set := load(TILESET_PATH) as TileSet
	if def.is_empty() or tile_set == null or not ResourceLoader.exists(PLAYER_SCENE):
		return issues  # the starter map reports what is missing
	var tile_px: int = JsonUtil.to_int(def["tile_size"][0])
	var rng := MapBuild.Lcg.new(MapBuild.stream_seed(JsonUtil.to_int(ctx.config.get("seed", 12345)), "field_1"))

	var root := MapUtil.new_map_root("Field1", "field_1")
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var spawns: Node2D = nodes["SpawnPoints"]
	var ground: TileMapLayer = nodes["Ground"]
	var triggers: Node2D = nodes["Triggers"]
	var gap := Vector2i(0, SIZE.y >> 1)
	var entry := Vector2i(2, gap.y)
	_paint_ground(ctx, def, tile_set, ground, rng)
	MapBuild.paint_walls(root, nodes, SIZE, MapUtil.wall_tile(ctx, def, tile_set), tile_px, [gap])
	var road := MapUtil.find_tile(ctx, def, tile_set, "ROAD")
	if nodes.has("GroundDetails"):
		var cells: Array[Vector2i] = []
		for x in range(1, 9):
			cells.append(Vector2i(x, gap.y))
		var details: TileMapLayer = nodes["GroundDetails"]
		MapBuild.paint_path(details, cells, road)

	var taken := {gap: true}
	for x in range(0, 10):
		taken[Vector2i(x, gap.y)] = true
		taken[Vector2i(x, gap.y - 1)] = true
		taken[Vector2i(x, gap.y + 1)] = true
	var entities: Node2D = nodes["Entities"]
	var placed: Array = []
	_place_decorations(ctx, root, entities, tile_px, rng, taken)
	_place_chest(ctx, root, entities, tile_px, rng, taken, issues, placed)
	_place_enemies(ctx, root, entities, tile_px, rng, taken, placed)

	MapUtil.add_marker(spawns, root, "default", MapUtil.tile_center(entry, tile_px), true, "right")
	MapUtil.add_marker(spawns, root, "west_entry", MapUtil.tile_center(entry, tile_px), true, "right")
	MapUtil.place(PLAYER_SCENE, entities, root, MapUtil.tile_center(entry, tile_px))
	MapBuild.add_exit_door(triggers, root, "field_1_west_exit", gap, tile_px, StarterMap.OUT_PATH, StringName(StarterMap.EAST_ENTRY))

	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
		return issues
	_record_demo_entities(placed, issues, ctx)
	return issues

## The second ground variant of the packs when there is one, else the first; a few patches of
## other tiles of that sheet.
func _paint_ground(ctx: BuildContext, def: Dictionary, tile_set: TileSet, ground: TileMapLayer, rng: MapBuild.Lcg) -> void:
	var base := MapBuild.nth_tile_with_role(ctx, def, tile_set, "GROUND", 1)
	if base.is_empty():
		base = MapBuild.nth_tile_with_role(ctx, def, tile_set, "GROUND", 0)
	if base.is_empty():
		return
	MapBuild.fill_ground(ground, SIZE, base)
	var others := MapUtil.other_tiles(tile_set, base, 3)
	if others.is_empty():
		return
	var patches: Array = []
	for i in PATCHES:
		var size := Vector2i(rng.range_inclusive(2, 4), rng.range_inclusive(2, 4))
		var pos := Vector2i(rng.range_inclusive(2, SIZE.x - size.x - 2), rng.range_inclusive(2, SIZE.y - size.y - 2))
		patches.append({"rect": Rect2i(pos, size), "index": i})
	MapBuild.paint_planned_patches(ground, patches, others)

## A free tile inside the walls (random, never on `taken`); it is added to `taken`. Vector2i.ZERO
## when the map is full.
func _free_tile(rng: MapBuild.Lcg, taken: Dictionary) -> Vector2i:
	for attempt in 60:
		var tile := Vector2i(rng.range_inclusive(2, SIZE.x - 3), rng.range_inclusive(2, SIZE.y - 3))
		if not taken.has(tile):
			taken[tile] = true
			return tile
	return Vector2i.ZERO

func _place_decorations(ctx: BuildContext, root: Node2D, entities: Node2D, tile_px: int, rng: MapBuild.Lcg, taken: Dictionary) -> void:
	var decor: Array[Dictionary] = []
	for e in ObjectEntries.entries(ctx):
		var decor_id: String = e["id"]
		if e["role"] == "DECORATION" and ResourceLoader.exists(ObjectIndex.scene_path(decor_id)):
			decor.append(e)
	if decor.is_empty():
		return
	for i in DECORATIONS:
		var tile := _free_tile(rng, taken)
		if tile == Vector2i.ZERO:
			return
		var e: Dictionary = decor[i % decor.size()]
		var pos := Vector2(tile) * tile_px + Vector2(tile_px / 2.0, tile_px - 1)
		var scene_id: String = e["id"]
		MapUtil.place(ObjectIndex.scene_path(scene_id), entities, root, pos, "Decor%d" % (i + 1))

func _place_chest(ctx: BuildContext, root: Node2D, entities: Node2D, tile_px: int, rng: MapBuild.Lcg, taken: Dictionary, issues: Array, placed: Array) -> void:
	var entry := ObjectEntries.chest_entry(ctx)
	if entry.is_empty():
		return
	var tile := _free_tile(rng, taken)
	if tile == Vector2i.ZERO:
		return
	var chest_scene_id: String = entry["id"]
	var chest := MapUtil.place(ObjectIndex.scene_path(chest_scene_id), entities, root, MapUtil.tile_center(tile, tile_px), "Chest1")
	if chest == null:
		return
	chest.set("entity_id", CHEST_ID)
	chest.set("loot", SeedUtil.dict_array([{"item_id": "potion", "qty": 2}]))
	chest.set("gold", 35)
	placed.append(CHEST_ID)

func _place_enemies(ctx: BuildContext, root: Node2D, entities: Node2D, tile_px: int, rng: MapBuild.Lcg, taken: Dictionary, placed: Array) -> void:
	var recipe := StarterMap.new()
	for i in ENEMIES:
		var scene := recipe._enemy_scene(ctx, i)
		if scene == "":
			scene = recipe._enemy_scene(ctx)
		if scene == "":
			return
		var tile := Vector2i.ZERO
		for attempt in 60:  # away from the entry
			tile = _free_tile(rng, taken)
			if tile.x >= 12 or tile == Vector2i.ZERO:
				break
		if tile == Vector2i.ZERO:
			return
		var enemy := MapUtil.place(scene, entities, root, MapUtil.tile_center(tile, tile_px), "Enemy%d" % (i + 1))
		if enemy != null:
			var id := "field_1_enemy_%03d" % (i + 1)
			enemy.set("entity_id", id)
			enemy.set("facing", "down")
			placed.append(id)

## Lists the field's demo entities beside the starter map's, for "Remove demo content".
func _record_demo_entities(placed: Array, issues: Array, ctx: BuildContext) -> void:
	var data: Variant = JsonUtil.read(StarterMap.DEMO_ENTITIES_PATH)
	if not data is Dictionary:
		return
	var table: Dictionary = data
	var extra: Dictionary = table.get("extra_maps", {})
	extra[OUT_PATH] = placed
	table["extra_maps"] = extra
	var err := JsonUtil.write(StarterMap.DEMO_ENTITIES_PATH, table)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": StarterMap.DEMO_ENTITIES_PATH, "err": err}, StarterMap.DEMO_ENTITIES_PATH))
