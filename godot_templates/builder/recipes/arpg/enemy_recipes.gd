extends RefCounted
## Action-RPG enemies: one definition (game/data/enemies/<slug>.tres, a user_seed file) and one scene
## (generated/scenes/enemies/<slug>.tscn) per ENEMY asset. Without an ENEMY asset the player's
## sprite stands in (ASSET-025), tinted red. The scene holds the combat parts of arpg_build.gd and
## the enemy_ai.gd state machine; the numbers live in the definition's `behavior`.

const RECIPE_VERSION := 1

const Paths := preload("../../lib/paths.gd")
const SceneUtil := preload("../../lib/scene_util.gd")
const ActorBuild := preload("../../lib/actor_build.gd")
const SeedUtil := preload("../../lib/seed_util.gd")
const ArpgBuild := preload("arpg_build.gd")
const Navigation := preload("navigation_recipe.gd")

const DEFINITIONS_DIR := "res://game/data/enemies/"
const SCENES_DIR := "res://generated/scenes/enemies/"
const ENEMY_DEF := "res://addons/rpg_runtime/data/enemy_definition.gd"
const STATS := "res://addons/rpg_runtime/data/stats.gd"
const LOOT := "res://addons/rpg_runtime/data/loot_table.gd"
const FALLBACK_SLUG := "enemy_fallback"
const FALLBACK_TINT := Color(1.0, 0.6, 0.6)
const NAME_NOISE := ["idle", "walk", "run", "sheet", "strip", "sprite", "sprites", "spritesheet", "anim", "animation"]

## Defaults of the behavior keys for 16 px tiles; pixel values scale with the tile size.
const BEHAVIOR := {
	"vision_px": 96, "lose_px": 160, "attack_range_px": 18, "attack_cooldown_s": 1.2,
	"windup_s": 0.35, "active_s": 0.15, "move_speed": 45, "chase_speed": 60,
	"wander_radius_px": 32, "wander_pause_s": [1.0, 2.5], "knockback_resist": 0.0,
	"nav_mode": "direct",
}
const PIXEL_KEYS := ["vision_px", "lose_px", "attack_range_px", "move_speed", "chase_speed", "wander_radius_px"]

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

## The behavior dictionary written into a new definition.
static func behavior_for(tile: int, nav_mode: String) -> Dictionary:
	var out: Dictionary = BEHAVIOR.duplicate(true)
	for key in PIXEL_KEYS:
		out[key] = int(round(float(out[key]) * float(tile) / 16.0))
	out["nav_mode"] = nav_mode
	return out

## "slime_idle" -> "Slime": the usual animation / sheet words at the end of a file name are dropped.
static func display_name(slug: String) -> String:
	var words := slug.split("_", false)
	while words.size() > 1 and NAME_NOISE.has(words[words.size() - 1]):
		words.remove_at(words.size() - 1)
	return " ".join(words).capitalize()

## Short readable file names: the last part of the asset id, the whole id when two would clash.
static func slugs_for(ids: Array) -> Array:
	var counts := {}
	var shorts: Array = []
	for id in ids:
		var s := String(id)
		var short := s.substr(s.rfind(".") + 1).replace("#", "_")
		shorts.append(short)
		counts[short] = int(counts.get(short, 0)) + 1
	var out: Array = []
	for i in ids.size():
		out.append(shorts[i] if int(counts[shorts[i]]) == 1 else String(ids[i]).replace(".", "__").replace("#", "__"))
	return out

func _usable(ctx, a: Dictionary) -> bool:
	var eff: Dictionary = ctx.catalog.effective(a)
	return eff.get("usage", "") == "sprite" and not eff.get("animations", {}).is_empty() and not (a.get("status", "") in ["UNUSED", "MISSING"])

## [{asset, slug, index, fallback}] sorted by asset id; the fallback entry when there is no enemy asset.
func entries(ctx) -> Array:
	var assets: Array = []
	for a in ctx.catalog.assets_by_role("ENEMY"):
		if _usable(ctx, a):
			assets.append(a)
	var out: Array = []
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

func _tile(ctx) -> int:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return int(def["tile_size"][0]) if not def.is_empty() else int(ctx.config.get("base_tile_size", 16))

## The scene of the `index`-th enemy the starter map places: index 0 is the starter.enemy asset (else
## the first enemy), the next ones the following enemies (the same one again when there is only
## one). "" when no enemy scene exists.
func starter_scene_at(ctx, index: int) -> String:
	var list: Array = []
	for e in entries(ctx):
		if ResourceLoader.exists(scene_path(e["slug"])):
			list.append(e)
	if list.is_empty():
		return ""
	var wanted := String(ctx.config.get("starter", {}).get("enemy", ""))
	var first := 0
	for i in list.size():
		if wanted != "" and list[i]["asset"]["id"] == wanted:
			first = i
	return scene_path(list[(first + index) % list.size()]["slug"])

func starter_scene(ctx) -> String:
	return starter_scene_at(ctx, 0)

func outputs(ctx) -> PackedStringArray:
	var out := PackedStringArray()
	for e in entries(ctx):
		out.append(scene_path(e["slug"]))
	for e in entries(ctx):
		if not FileAccess.file_exists(definition_path(e["slug"])):
			out.append(definition_path(e["slug"]))
	return out

func input_hash(ctx) -> String:
	var parts: Array = []
	for e in entries(ctx):
		var a: Dictionary = e["asset"]
		parts.append({"id": a["id"], "slug": e["slug"], "fallback": e["fallback"], "sha256": a.get("sha256", ""), "eff": ctx.catalog.effective(a)})
	return ctx.stable_hash({"v": RECIPE_VERSION, "enemies": parts, "tile": _tile(ctx), "nav": Navigation.nav_mode(ctx)})

func build(ctx) -> Array:
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
			_save_definition(ctx, e, frames, tile, issues)
		var def := load(definition_path(slug)) as Resource
		if def == null:
			issues.append(ctx.make_issue("VAL-002", {"file": definition_path(slug)}, definition_path(slug)))
			continue
		var fo := ActorBuild.frame_and_origin(ctx.catalog.effective(a))
		var node := _build_scene(frames, fo, tile, def, bool(e["fallback"]), Navigation.enabled(ctx))
		var err := SceneUtil.save_scene(node, scene_path(slug))
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": scene_path(slug), "err": err}, scene_path(slug)))
	return issues

func _save_definition(ctx, e: Dictionary, frames: SpriteFrames, tile: int, issues: Array) -> void:
	var s := scaled(int(e["index"]))
	var stats := SeedUtil.make(STATS)
	stats.set("max_hp", s["hp"])
	stats.set("hp", s["hp"])
	stats.set("attack", s["attack"])
	stats.set("defense", s["defense"])
	var loot := SeedUtil.make(LOOT)
	loot.set("entries", SeedUtil.dict_array([{"item_id": "potion", "chance": 0.3, "min": 1, "max": 1}]))
	var def := SeedUtil.make(ENEMY_DEF)
	def.set("id", StringName(e["slug"]))
	def.set("display_name", "Enemy" if e["fallback"] else display_name(String(e["slug"])))
	def.set("sprite_frames", frames)
	def.set("base_stats", stats)
	def.set("xp_reward", s["xp"])
	def.set("gold_reward", s["gold"])
	def.set("loot", loot)
	def.set("behavior", behavior_for(tile, Navigation.nav_mode(ctx)))
	var path := definition_path(e["slug"])
	var err := SeedUtil.save(def, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## The enemy actor: base actor + enemy_ai.gd + the combat parts. (Inherited scenes cannot be saved
## headless, so it is built by the same function as every other actor.)
func _build_scene(frames: SpriteFrames, fo: Dictionary, tile: int, def: Resource, fallback: bool, agent: bool) -> Node:
	var frame: Vector2i = fo["frame"]
	var root := ActorBuild.build("base", "Enemy", frames, frame, fo["origin"], tile)
	SceneUtil.attach_script(root, ArpgBuild.ENEMY_AI)
	root.set("definition", def)
	root.set("tile_size", float(tile))
	if fallback:
		(root.get_node("Visual") as CanvasItem).modulate = FALLBACK_TINT
	ArpgBuild.augment_enemy(root, frame, tile, agent)
	ActorBuild.add_persistent(root)
	return root
