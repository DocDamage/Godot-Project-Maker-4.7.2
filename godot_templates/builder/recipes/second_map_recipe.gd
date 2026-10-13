extends RefCounted
## Seeds game/maps/field_1.tscn once (user_seed ownership): a second outdoor map behind the east
## exit of the starter map (T11.23). It exists only for a starter map that has that exit (the
## starter map records it in rpggen/demo_entities.json), so a project made before M11 never gets
## new content forced into its map. Behind features.demo. A turn-based project also gets a random
## encounter zone over the east half of the field and its table game/data/encounters/field_1.tres
## (T12.53), both written once.
##
## With a world plan (rpggen/world_plan.json, from `starter_map.areas`, T13.20) this is the **area
## recipe** instead: every area of the plan other than the village gets game/maps/<id>.tscn, once,
## as the plan says cell by cell (ground by biome, walls with a gap per door, the doors and where a
## player arrives, chests, enemies, decorations, water on a shore, the gate of a locked door).
## An area whose map exists is never rebuilt, whatever the plan says now.

const RECIPE_VERSION := 3
## The version of what the recipe does for an isometric project only (T17.14): in the hash of
## such a project and of no other.
const ISO_VERSION := 1

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
const WorldPlan := preload("../lib/world_plan.gd")
const MapGeo := preload("../lib/map_geo.gd")

const OUT_PATH := "res://game/maps/field_1.tscn"
const TILESET_PATH := "res://generated/tilesets/overworld.tres"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const SIZE := Vector2i(32, 20)
const ENEMIES := 2
const DECORATIONS := 10
const PATCHES := 4
const CHEST_ID := "field_1_chest_001"
const TABLE_PATH := "res://game/data/encounters/field_1.tres"
const ZONE_SCRIPT := "res://addons/rpg_runtime/world/encounter_zone.gd"
const TABLE_SCRIPT := "res://addons/rpg_runtime/data/encounter_table.gd"
## The zone starts this many tiles from the west wall, past the entry and its road.
const ZONE_FROM_X := 12
const STEPS_PER_ENCOUNTER := 20.0
## Action RPG: the field's first enemy charges, the second shoots (the definitions the arpg enemy
## recipe makes from the starter enemy: <slug>_<kind>.tres).
const ARPG_FIELD_KINDS: Array[String] = ["charger", "shooter"]
const ENEMY_DEFS_DIR := "res://game/data/enemies/"

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
	var plan := WorldPlan.read()
	if WorldPlan.has_areas(plan):
		return _area_outputs(plan)
	if FileAccess.file_exists(OUT_PATH) or not _wanted(ctx):
		return PackedStringArray()
	var out := PackedStringArray([OUT_PATH])
	if _encounters_wanted(ctx) and not FileAccess.file_exists(TABLE_PATH):
		out.append(TABLE_PATH)
	return out

## Random encounters are a turn-based feature.
func _encounters_wanted(ctx: BuildContext) -> bool:
	return JsonUtil.to_str(ctx.config.get("archetype", "")) == "turn_based"

func input_hash(ctx: BuildContext) -> String:
	var hashed := {
		"v": RECIPE_VERSION,
		"wanted": _wanted(ctx),
		"world": WorldPlan.areas(WorldPlan.read()),
		"overworld": ctx.catalog.tileset_def("overworld"),
		"layers": ctx.config.get("map_layers", []),
		"seed": ctx.config.get("seed", 0),
		"entries": ObjectEntries.entries(ctx),
		"chest": ObjectEntries.chest_entry(ctx).get("id", ""),
		"archetype": ctx.config.get("archetype", ""),
	}
	if MapGeo.is_isometric(ctx):  # only an isometric project's hash has the keys (T17.14)
		hashed["iso"] = MapGeo.new(ctx).def
		hashed["iso_v"] = ISO_VERSION
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var world := WorldPlan.read()
	if WorldPlan.has_areas(world):
		_build_areas(ctx, world, issues)
		return issues
	if FileAccess.file_exists(OUT_PATH) or not _wanted(ctx):
		return issues
	var geo := MapGeo.new(ctx)  # squares, or diamonds (T17.14)
	var tile_set := geo.load_tile_set()
	if geo.def.is_empty() or tile_set == null or not ResourceLoader.exists(PLAYER_SCENE):
		return issues  # the starter map reports what is missing
	var rng := MapBuild.Lcg.new(MapBuild.stream_seed(JsonUtil.to_int(ctx.config.get("seed", 12345)), "field_1"))

	var root := MapUtil.new_map_root("Field1", "field_1")
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var spawns: Node2D = nodes["SpawnPoints"]
	var ground: TileMapLayer = nodes["Ground"]
	var triggers: Node2D = nodes["Triggers"]
	var gap := Vector2i(0, SIZE.y >> 1)
	var entry := Vector2i(2, gap.y)
	_paint_ground(geo, ground, rng)
	geo.paint_walls(root, nodes, SIZE, [gap])
	var road := geo.find_tile("ROAD")
	if nodes.has("GroundDetails"):
		var cells: Array[Vector2i] = []
		for x in range(1, 9):
			cells.append(Vector2i(x, gap.y))
		var details: TileMapLayer = nodes["GroundDetails"]
		geo.paint_joined(details, cells, "ROAD", road)
	for note in geo.take_notes():
		print("[rpggen] INFO field_1: ", note)

	var taken := {gap: true}
	for x in range(0, 10):
		taken[Vector2i(x, gap.y)] = true
		taken[Vector2i(x, gap.y - 1)] = true
		taken[Vector2i(x, gap.y + 1)] = true
	var entities: Node2D = nodes["Entities"]
	var placed: Array = []
	_place_decorations(ctx, root, entities, geo, rng, taken)
	_place_chest(ctx, root, entities, geo, rng, taken, issues, placed)
	var enemy_slugs := _place_enemies(ctx, root, entities, geo, rng, taken, placed)
	if _encounters_wanted(ctx):
		_add_encounter_zone(root, triggers, geo, enemy_slugs, issues, ctx)

	MapUtil.add_marker(spawns, root, "default", geo.center(entry), true, "right")
	MapUtil.add_marker(spawns, root, "west_entry", geo.center(entry), true, "right")
	MapUtil.place(PLAYER_SCENE, entities, root, geo.center(entry))
	geo.add_exit_door(triggers, root, "field_1_west_exit", gap, StarterMap.OUT_PATH, StringName(StarterMap.EAST_ENTRY))

	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
		return issues
	_record_demo_entities(placed, issues, ctx)
	return issues

## The second ground variant of the packs when there is one, else the first; a few patches of
## other tiles of that sheet.
func _paint_ground(geo: MapGeo, ground: TileMapLayer, rng: MapBuild.Lcg) -> void:
	var base := geo.nth_tile_with_role("GROUND", 1)
	if base.is_empty():
		base = geo.nth_tile_with_role("GROUND", 0)
	if base.is_empty():
		return
	MapBuild.fill_ground(ground, SIZE, base)
	var others := geo.other_tiles(base, 3)
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

func _place_decorations(ctx: BuildContext, root: Node2D, entities: Node2D, geo: MapGeo, rng: MapBuild.Lcg, taken: Dictionary) -> void:
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
		var pos := geo.foot(tile)
		var scene_id: String = e["id"]
		MapUtil.place(ObjectIndex.scene_path(scene_id), entities, root, pos, "Decor%d" % (i + 1))

func _place_chest(ctx: BuildContext, root: Node2D, entities: Node2D, geo: MapGeo, rng: MapBuild.Lcg, taken: Dictionary, issues: Array, placed: Array) -> void:
	var entry := ObjectEntries.chest_entry(ctx)
	if entry.is_empty():
		return
	var tile := _free_tile(rng, taken)
	if tile == Vector2i.ZERO:
		return
	var chest_scene_id: String = entry["id"]
	var chest := MapUtil.place(ObjectIndex.scene_path(chest_scene_id), entities, root, geo.center(tile), "Chest1")
	if chest == null:
		return
	chest.set("entity_id", CHEST_ID)
	chest.set("loot", SeedUtil.dict_array([{"item_id": "potion", "qty": 2}]))
	chest.set("gold", 35)
	placed.append(CHEST_ID)

## Places the field's enemies; returns the slugs of their scenes (= their definition ids).
func _place_enemies(ctx: BuildContext, root: Node2D, entities: Node2D, geo: MapGeo, rng: MapBuild.Lcg, taken: Dictionary, placed: Array) -> Array[String]:
	var recipe := StarterMap.new()
	var slugs: Array[String] = []
	for i in ENEMIES:
		var scene := recipe._enemy_scene(ctx, i)
		if scene == "":
			scene = recipe._enemy_scene(ctx)
		if scene == "":
			return slugs
		if not slugs.has(scene.get_file().get_basename()):
			slugs.append(scene.get_file().get_basename())
		var tile := Vector2i.ZERO
		for attempt in 60:  # away from the entry
			tile = _free_tile(rng, taken)
			if tile.x >= 12 or tile == Vector2i.ZERO:
				break
		if tile == Vector2i.ZERO:
			return slugs
		var enemy := MapUtil.place(scene, entities, root, geo.center(tile), "Enemy%d" % (i + 1))
		if enemy != null:
			var id := "field_1_enemy_%03d" % (i + 1)
			enemy.set("entity_id", id)
			enemy.set("facing", "down")
			placed.append(id)
			_use_arpg_variant(ctx, enemy, recipe._enemy_scene(ctx), i)
	return slugs

## In an action RPG the field's enemies fight as a charger and a shooter when those definitions exist.
func _use_arpg_variant(ctx: BuildContext, enemy: Node, first_scene: String, index: int) -> void:
	if JsonUtil.to_str(ctx.config.get("archetype", "")) != "arpg" or index >= ARPG_FIELD_KINDS.size():
		return
	var path := ENEMY_DEFS_DIR + "%s_%s.tres" % [first_scene.get_file().get_basename(), ARPG_FIELD_KINDS[index]]
	if ResourceLoader.exists(path):
		enemy.set("definition", load(path))

## A random-encounter zone over the east half of the field (inside the walls) with the table
## game/data/encounters/field_1.tres: each enemy alone (weights 3 and 2) and the first one twice.
func _add_encounter_zone(root: Node2D, triggers: Node2D, geo: MapGeo, slugs: Array[String], issues: Array, ctx: BuildContext) -> void:
	if slugs.is_empty():
		return
	if not FileAccess.file_exists(TABLE_PATH):
		var table := SeedUtil.make(TABLE_SCRIPT)
		table.set("id", &"field_1")
		var groups: Array = [{"enemies": [slugs[0]], "weight": 3}]
		if slugs.size() > 1:
			groups.append({"enemies": [slugs[1]], "weight": 2})
		groups.append({"enemies": [slugs[0], slugs[0]], "weight": 1})
		table.set("groups", SeedUtil.dict_array(groups))
		var err := SeedUtil.save(table, TABLE_PATH)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": TABLE_PATH, "err": err}, TABLE_PATH))
			return
	var zone := Area2D.new()
	zone.name = "EncounterZone"
	SceneUtil.attach_script(zone, ZONE_SCRIPT)
	zone.set("table", load(TABLE_PATH))
	zone.set("steps_per_encounter", STEPS_PER_ENCOUNTER)
	var shape := CollisionPolygon2D.new()
	shape.name = "Shape"
	shape.polygon = geo.cells_outline(Rect2i(ZONE_FROM_X, 1, SIZE.x - 1 - ZONE_FROM_X, SIZE.y - 2))
	zone.add_child(shape)
	triggers.add_child(zone)
	zone.owner = root
	shape.owner = root

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

# ---------------------------------------------------------------- the areas of a world (T13.20)

const KEY_ITEM_DIR := "res://game/data/items/"
const ITEM_DEF := "res://addons/rpg_runtime/data/item_definition.gd"
const KEY_CATEGORY := 5  # RpgItemDefinition.Category.KEY

## The maps (and the key item) that do not exist yet.
func _area_outputs(plan: Dictionary) -> PackedStringArray:
	var out := PackedStringArray()
	for area in WorldPlan.areas(plan):
		if area["id"] != WorldPlan.VILLAGE_ID and not FileAccess.file_exists(WorldPlan.map_path(area)):
			out.append(WorldPlan.map_path(area))
	var key := _key_item(plan)
	if key != "" and not FileAccess.file_exists(KEY_ITEM_DIR + key + ".tres"):
		out.append(KEY_ITEM_DIR + key + ".tres")
	return out

static func _key_item(plan: Dictionary) -> String:
	return JsonUtil.to_str(JsonUtil.to_dict(plan.get("key", {})).get("item", ""))

func _build_areas(ctx: BuildContext, plan: Dictionary, issues: Array) -> void:
	var geo := MapGeo.new(ctx)  # squares, or diamonds (T17.14)
	var tile_set := geo.load_tile_set()
	if geo.def.is_empty() or tile_set == null or not ResourceLoader.exists(PLAYER_SCENE):
		return  # the starter map reports what is missing
	var key := _key_item(plan)
	if key != "" and not FileAccess.file_exists(KEY_ITEM_DIR + key + ".tres"):
		_save_key_item(ctx, plan, key, issues)
	for area in WorldPlan.areas(plan):
		var path := WorldPlan.map_path(area)
		if area["id"] == WorldPlan.VILLAGE_ID or FileAccess.file_exists(path):
			continue
		var root := _build_area(ctx, area, geo, tile_set)
		for note in geo.take_notes():
			print("[rpggen] INFO %s: " % JsonUtil.to_str(area["id"]), note)
		var err := SceneUtil.save_scene(root, path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## The key that opens the locked area: a KEY item named after it, written once.
func _save_key_item(ctx: BuildContext, plan: Dictionary, key: String, issues: Array) -> void:
	var opened := WorldPlan.area(plan, JsonUtil.to_str(JsonUtil.to_dict(plan.get("key", {})).get("opens", "")))
	var item := SeedUtil.make(ITEM_DEF)
	item.set("id", StringName(key))
	item.set("display_name", "%s key" % JsonUtil.to_str(opened.get("name", "Gate")))
	item.set("description", "Opens the way to %s." % JsonUtil.to_str(opened.get("name", "the next area")))
	item.set("category", KEY_CATEGORY)
	item.set("max_stack", 1)
	item.set("value", 0)
	var path := KEY_ITEM_DIR + key + ".tres"
	var err := SeedUtil.save(item, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## "old_mine" -> "OldMine" (the root node's name).
static func _root_name(area_id: String) -> String:
	return area_id.to_pascal_case()

func _build_area(ctx: BuildContext, area: Dictionary, geo: MapGeo, tile_set: TileSet) -> Node2D:
	var area_id := JsonUtil.to_str(area["id"])
	var size := WorldPlan.cell(area["size"])
	var rng := MapBuild.Lcg.new(MapBuild.stream_seed(JsonUtil.to_int(ctx.config.get("seed", 12345)), area_id))
	var root := MapUtil.new_map_root(_root_name(area_id), area_id)
	root.set("music_asset_id", JsonUtil.to_str(ctx.section("sounds").get("music_map", "")))
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var ground: TileMapLayer = nodes["Ground"]
	_paint_area_ground(area, geo, ground, size, rng)
	var doors := WorldPlan.list_of(area, "doors")
	var gaps: Array[Vector2i] = []
	for door in doors:
		gaps.append(WorldPlan.cell(door["cell"]))
	geo.paint_walls(root, nodes, size, gaps)
	_place_area_decorations(ctx, area, root, entities, geo)
	_place_area_chests(ctx, area, root, entities, geo)
	_place_area_enemies(ctx, area, root, entities, geo)
	var arrive := Vector2i(size.x >> 1, size.y >> 1)
	var facing := "down"
	if not doors.is_empty():
		arrive = WorldPlan.cell(doors[0]["spawn"])
		facing = JsonUtil.to_str(doors[0].get("facing", "down"))
	MapUtil.add_marker(spawns, root, "default", geo.center(arrive), true, facing)
	MapUtil.place(PLAYER_SCENE, entities, root, geo.center(arrive))
	for door in doors:
		var door_cell := WorldPlan.cell(door["cell"])
		WorldPlan.add_door(door, door_cell, WorldPlan.cell(door["spawn"]), root, nodes, geo)
		var gate := WorldPlan.gate_of(area, JsonUtil.to_str(door.get("id", "")))
		if not gate.is_empty():
			WorldPlan.add_gate(gate, door_cell, root, entities, geo)
	return root

## The ground of an area: the plan's ground asset when the tile set has it, else the second ground
## variant for a field and the first one for the rest; a few patches of other tiles; and the water
## of a shore.
func _paint_area_ground(area: Dictionary, geo: MapGeo, ground: TileMapLayer, size: Vector2i, rng: MapBuild.Lcg) -> void:
	var base := {}
	var wanted := JsonUtil.to_str(area.get("ground", ""))
	if wanted != "":
		base = geo.tile_of_asset(wanted)
	if base.is_empty() and JsonUtil.to_str(area.get("biome", "")) == "field":
		base = geo.nth_tile_with_role("GROUND", 1)
	if base.is_empty():
		base = geo.nth_tile_with_role("GROUND", 0)
	if base.is_empty():
		return
	MapBuild.fill_ground(ground, size, base)
	var others := geo.other_tiles(base, 3)
	if not others.is_empty():
		var patches: Array = []
		for i in PATCHES:
			var patch := Vector2i(rng.range_inclusive(2, 4), rng.range_inclusive(2, 4))
			var pos := Vector2i(rng.range_inclusive(2, size.x - patch.x - 2), rng.range_inclusive(2, size.y - patch.y - 2))
			patches.append({"rect": Rect2i(pos, patch), "index": i})
		MapBuild.paint_planned_patches(ground, patches, others)
	var water := JsonUtil.to_array(area.get("water", []))
	var water_tile := geo.find_tile("WATER")
	if water.size() == 4 and not water_tile.is_empty():
		geo.fill_joined(ground, Rect2i(JsonUtil.to_int(water[0]), JsonUtil.to_int(water[1]), JsonUtil.to_int(water[2]), JsonUtil.to_int(water[3])), "WATER", water_tile)

## The decoration objects an area uses: those whose name has one of the biome's words (trees in a
## forest), else every decoration.
func _area_decor(ctx: BuildContext, area: Dictionary) -> Array[Dictionary]:
	var all: Array[Dictionary] = []
	var fitting: Array[Dictionary] = []
	var words := JsonUtil.to_array(area.get("decor_words", []))
	for e in ObjectEntries.entries(ctx):
		var decor_id: String = e["id"]
		if e["role"] != "DECORATION" or not ResourceLoader.exists(ObjectIndex.scene_path(decor_id)):
			continue
		all.append(e)
		var label := (JsonUtil.to_str(e.get("name", "")) + " " + decor_id).to_lower()
		for word: Variant in words:
			if label.contains(JsonUtil.to_str(word)):
				fitting.append(e)
				break
	return fitting if not fitting.is_empty() else all

func _place_area_decorations(ctx: BuildContext, area: Dictionary, root: Node2D, entities: Node2D, geo: MapGeo) -> void:
	var decor := _area_decor(ctx, area)
	if decor.is_empty():
		return
	var cells := JsonUtil.to_array(area.get("decorations", []))
	for i in cells.size():
		var tile := WorldPlan.cell(cells[i])
		var e: Dictionary = decor[i % decor.size()]
		var scene_id: String = e["id"]
		var pos := geo.foot(tile)
		MapUtil.place(ObjectIndex.scene_path(scene_id), entities, root, pos, "Decor%d" % (i + 1))

func _place_area_chests(ctx: BuildContext, area: Dictionary, root: Node2D, entities: Node2D, geo: MapGeo) -> void:
	var entry := ObjectEntries.chest_entry(ctx)
	if entry.is_empty():
		return
	var chest_scene_id: String = entry["id"]
	var chests := WorldPlan.list_of(area, "chests")
	for i in chests.size():
		var tile := WorldPlan.cell(chests[i]["cell"])
		var chest := MapUtil.place(ObjectIndex.scene_path(chest_scene_id), entities, root, geo.center(tile), "Chest%d" % (i + 1))
		if chest == null:
			continue
		chest.set("entity_id", JsonUtil.to_str(chests[i]["id"]))
		chest.set("loot", SeedUtil.dict_array(JsonUtil.to_array(chests[i].get("items", []))))
		chest.set("gold", JsonUtil.to_int(chests[i].get("gold", 0)))

func _place_area_enemies(ctx: BuildContext, area: Dictionary, root: Node2D, entities: Node2D, geo: MapGeo) -> void:
	var recipe := StarterMap.new()
	var enemies := WorldPlan.list_of(area, "enemies")
	for i in enemies.size():
		var scene := recipe._enemy_scene(ctx, i)
		if scene == "":
			scene = recipe._enemy_scene(ctx)
		if scene == "":
			return
		var tile := WorldPlan.cell(enemies[i]["cell"])
		var enemy := MapUtil.place(scene, entities, root, geo.center(tile), "Enemy%d" % (i + 1))
		if enemy != null:
			enemy.set("entity_id", JsonUtil.to_str(enemies[i]["id"]))
			enemy.set("facing", "down")
