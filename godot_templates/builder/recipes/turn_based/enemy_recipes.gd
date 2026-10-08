extends RefCounted
## Turn-based enemies: one definition (game/data/enemies/<slug>.tres, a user_seed file) and one
## overworld scene (generated/scenes/enemies/<slug>.tscn) per ENEMY asset. Without an ENEMY asset
## the player's sprite stands in (ASSET-025), tinted red.

const RECIPE_VERSION := 1

const Paths := preload("../../lib/paths.gd")
const SceneUtil := preload("../../lib/scene_util.gd")
const ActorBuild := preload("../../lib/actor_build.gd")
const SeedUtil := preload("../../lib/seed_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")

const DEFINITIONS_DIR := "res://game/data/enemies/"
const SCENES_DIR := "res://generated/scenes/enemies/"
const ENEMY_SCRIPT := "res://addons/rpg_runtime/archetypes/turn_based/overworld_enemy.gd"
const ENEMY_DEF := "res://addons/rpg_runtime/data/enemy_definition.gd"
const STATS := "res://addons/rpg_runtime/data/stats.gd"
const LOOT := "res://addons/rpg_runtime/data/loot_table.gd"
const FALLBACK_SLUG := "enemy_fallback"
const FALLBACK_TINT := Color(1.0, 0.6, 0.6)
const NAME_NOISE := ["idle", "walk", "run", "sheet", "strip", "sprite", "sprites", "spritesheet", "anim", "animation"]

static func definition_path(slug: String) -> String:
	return DEFINITIONS_DIR + slug + ".tres"

static func scene_path(slug: String) -> String:
	return SCENES_DIR + slug + ".tscn"

## Stats of the enemy with this index: hp 12+4i, attack 4+i, defense 1+i/2, xp 5+2i, gold 3+i.
static func scaled(index: int) -> Dictionary:
	return {
		"hp": 12 + 4 * index, "attack": 4 + index, "defense": 1 + floori(index / 2.0),
		"xp": 5 + 2 * index, "gold": 3 + index,
	}

## "slime_idle" -> "Slime": the usual animation / sheet words at the end of a file name are dropped.
static func display_name(slug: String) -> String:
	var words := slug.split("_", false)
	while words.size() > 1 and NAME_NOISE.has(words[words.size() - 1]):
		words.remove_at(words.size() - 1)
	return " ".join(words).capitalize()

## Short readable file names: the last part of the asset id, the whole id when two would clash.
static func slugs_for(ids: Array) -> Array[String]:
	var counts := {}
	var shorts: Array[String] = []
	for id: Variant in ids:
		var s := JsonUtil.to_str(id)
		var short := s.substr(s.rfind(".") + 1).replace("#", "_")
		shorts.append(short)
		counts[short] = JsonUtil.to_int(counts.get(short, 0)) + 1
	var out: Array[String] = []
	for i in ids.size():
		out.append(shorts[i] if JsonUtil.to_int(counts[shorts[i]]) == 1 else JsonUtil.to_str(ids[i]).replace(".", "__").replace("#", "__"))
	return out

func _usable(ctx: BuildContext, a: Dictionary) -> bool:
	var eff: Dictionary = ctx.catalog.effective(a)
	var animations: Dictionary = eff.get("animations", {})
	return eff.get("usage", "") == "sprite" and not animations.is_empty() and not (a.get("status", "") in ["UNUSED", "MISSING"])

## [{asset, slug, index, fallback}] sorted by asset id; the fallback entry when there is no enemy asset.
func entries(ctx: BuildContext) -> Array[Dictionary]:
	var assets: Array[Dictionary] = []
	for a in ctx.catalog.assets_by_role("ENEMY"):
		if _usable(ctx, a):
			assets.append(a)
	var out: Array[Dictionary] = []
	if not assets.is_empty():
		var ids: Array = []
		for a in assets:
			ids.append(a["id"])
		var slugs := slugs_for(ids)
		for i in assets.size():
			out.append({"asset": assets[i], "slug": slugs[i], "index": i, "fallback": false})
		return out
	for a in ctx.catalog.assets_by_role("PLAYER"):
		if _usable(ctx, a):
			out.append({"asset": a, "slug": FALLBACK_SLUG, "index": 0, "fallback": true})
			break
	return out

func _tile(ctx: BuildContext) -> int:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return JsonUtil.to_int(def["tile_size"][0]) if not def.is_empty() else JsonUtil.to_int(ctx.config.get("base_tile_size", 16))

## The scene of the enemy the starter map places: the starter.enemy asset, else the first enemy.
func starter_scene(ctx: BuildContext) -> String:
	var wanted := JsonUtil.to_str(ctx.section("starter").get("enemy", ""))
	var list := entries(ctx)
	for e in list:
		var asset: Dictionary = e["asset"]
		var slug: String = e["slug"]
		if wanted != "" and asset["id"] == wanted and ResourceLoader.exists(scene_path(slug)):
			return scene_path(slug)
	for e in list:
		var slug: String = e["slug"]
		if ResourceLoader.exists(scene_path(slug)):
			return scene_path(slug)
	return ""

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	var list := entries(ctx)
	for e in list:
		var slug: String = e["slug"]
		out.append(scene_path(slug))
	for e in list:
		var slug: String = e["slug"]
		if not FileAccess.file_exists(definition_path(slug)):
			out.append(definition_path(slug))
	return out

func input_hash(ctx: BuildContext) -> String:
	var parts: Array = []
	for e in entries(ctx):
		var a: Dictionary = e["asset"]
		parts.append({"id": a["id"], "slug": e["slug"], "fallback": e["fallback"], "sha256": a.get("sha256", ""), "eff": ctx.catalog.effective(a)})
	return ctx.stable_hash({"v": RECIPE_VERSION, "enemies": parts, "tile": _tile(ctx)})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var list := entries(ctx)
	if list.is_empty():
		issues.append(ctx.make_issue("BUILD-002", {"recipe": "enemy_recipes", "reason": "no ENEMY or PLAYER sprite asset to build an enemy from"}))
		return issues
	if list[0]["fallback"]:
		issues.append(ctx.make_issue("ASSET-025", {}))
	var tile := _tile(ctx)
	for e in list:
		var a: Dictionary = e["asset"]
		var slug: String = e["slug"]
		var frames_path: String = Paths.SPRITE_FRAMES_DIR + "%s.tres" % a["id"]
		var frames := load(frames_path) as SpriteFrames
		if frames == null:
			issues.append(ctx.make_issue("VAL-002", {"file": frames_path}, frames_path))
			continue
		if not FileAccess.file_exists(definition_path(slug)):
			_save_definition(ctx, e, frames, issues)
		var def := load(definition_path(slug)) as Resource
		if def == null:
			issues.append(ctx.make_issue("VAL-002", {"file": definition_path(slug)}, definition_path(slug)))
			continue
		var fo := ActorBuild.frame_and_origin(ctx.catalog.effective(a))
		var node := _build_scene(frames, fo, tile, def, JsonUtil.to_bool(e["fallback"]))
		var err := SceneUtil.save_scene(node, scene_path(slug))
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": scene_path(slug), "err": err}, scene_path(slug)))
	return issues

func _save_definition(ctx: BuildContext, e: Dictionary, frames: SpriteFrames, issues: Array) -> void:
	var s := scaled(JsonUtil.to_int(e["index"]))
	var stats := SeedUtil.make(STATS)
	stats.set("max_hp", s["hp"])
	stats.set("hp", s["hp"])
	stats.set("attack", s["attack"])
	stats.set("defense", s["defense"])
	var loot := SeedUtil.make(LOOT)
	loot.set("entries", SeedUtil.dict_array([{"item_id": "potion", "chance": 0.3, "min": 1, "max": 1}]))
	var def := SeedUtil.make(ENEMY_DEF)
	def.set("id", JsonUtil.to_name(e["slug"]))
	def.set("display_name", "Enemy" if e["fallback"] else display_name(JsonUtil.to_str(e["slug"])))
	def.set("sprite_frames", frames)
	def.set("base_stats", stats)
	def.set("xp_reward", s["xp"])
	def.set("gold_reward", s["gold"])
	def.set("loot", loot)
	def.set("behavior", {"turn_based": {"attack": 1.0, "defend": 0.0}})
	var slug: String = e["slug"]
	var path := definition_path(slug)
	var err := SeedUtil.save(def, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## The overworld enemy: an actor with the enemy script, on the enemies layer, a Contact area for
## the player and an RpgPersistent child. (Inherited scenes cannot be saved headless, so it is
## built by the same function as every other actor.)
func _build_scene(frames: SpriteFrames, fo: Dictionary, tile: int, def: Resource, fallback: bool) -> Node:
	var frame: Vector2i = fo["frame"]
	var origin: Vector2i = fo["origin"]
	var root := ActorBuild.build("base", "Enemy", frames, frame, origin, tile)
	SceneUtil.attach_script(root, ENEMY_SCRIPT)
	root.collision_layer = 0
	root.set_collision_layer_value(3, true)  # enemies
	root.collision_mask = 0
	root.set_collision_mask_value(1, true)  # world
	root.set("definition", def)
	root.set("tile_size", float(tile))
	if fallback:
		(root.get_node("Visual") as CanvasItem).modulate = FALLBACK_TINT
	var contact := Area2D.new()
	contact.name = "Contact"
	contact.collision_layer = 0
	contact.set_collision_layer_value(6, true)  # triggers
	contact.collision_mask = 0
	contact.set_collision_mask_value(2, true)  # player
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = Vector2(maxf(tile * 1.5, frame.x), tile * 1.25)
	shape.shape = rect
	shape.position = Vector2(0, -tile * 0.4)
	contact.add_child(shape)
	root.add_child(contact)
	ActorBuild.add_persistent(root)
	return root
