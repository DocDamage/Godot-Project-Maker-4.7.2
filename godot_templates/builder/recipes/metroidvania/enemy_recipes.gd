extends RefCounted
## The enemies of a metroidvania (T14.07): one definition (game/data/enemies/<slug>.tres, written
## once) and one scene (generated/scenes/enemies/<slug>.tscn) per ENEMY asset, and the guardian
## (generated/scenes/enemies/guardian.tscn) from the BOSS asset, else from the strongest enemy.
## Without an ENEMY asset the player's sprite stands in, tinted red (ASSET-025).
##
## What an enemy does comes from its asset's tags and name: `fly`, `bat`, `bird`, `ghost` fly;
## `shoot`, `turret`, `archer`, `mage` shoot; anything else patrols its platform. The kind is
## written into the definition's `behavior` ("kind"), where it can be changed.

const RECIPE_VERSION := 1

const Paths := preload("../../lib/paths.gd")
const SceneUtil := preload("../../lib/scene_util.gd")
const SeedUtil := preload("../../lib/seed_util.gd")
const ActorBuild := preload("../../lib/actor_build.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const MvBuild := preload("metroidvania_build.gd")

const DEFINITIONS_DIR := "res://game/data/enemies/"
const SCENES_DIR := "res://generated/scenes/enemies/"
const ENEMY_DEF := "res://addons/rpg_runtime/data/enemy_definition.gd"
const STATS := "res://addons/rpg_runtime/data/stats.gd"
const LOOT := "res://addons/rpg_runtime/data/loot_table.gd"
const SCRIPTS := {
	"patrol": MvBuild.DIR + "enemies/patrol.gd",
	"flyer": MvBuild.DIR + "enemies/flyer.gd",
	"shooter": MvBuild.DIR + "enemies/shooter.gd",
	"guardian": MvBuild.DIR + "enemies/guardian.gd",
}
const KIND_WORDS := {
	"flyer": ["fly", "flyer", "flying", "bat", "bird", "ghost", "wasp", "bee"],
	"shooter": ["shoot", "shooter", "turret", "archer", "mage", "wizard", "cannon"],
}
const FALLBACK_SLUG := "enemy_fallback"
const GUARDIAN_SLUG := "guardian"
const FALLBACK_TINT := Color(1.0, 0.6, 0.6)
const NAME_NOISE := ["idle", "walk", "run", "fly", "attack", "sheet", "strip", "sprite", "sprites"]
## The guardian's health at 16 px tiles (T14.07), and what it is worth.
const GUARDIAN_HP := 20
const GUARDIAN_ATTACK := 3
const GUARDIAN_XP := 30
const GUARDIAN_GOLD := 40
## Walking speeds in px/s at 16 px tiles.
const SPEEDS := {"patrol": 40.0, "flyer": 55.0, "shooter": 0.0, "guardian": 60.0}

static func definition_path(slug: String) -> String:
	return DEFINITIONS_DIR + slug + ".tres"

static func scene_path(slug: String) -> String:
	return SCENES_DIR + slug + ".tscn"

## Stats of the enemy with this index: hp 3+i, attack 2+i/2, xp 4+2i, gold 2+i. A side-view enemy
## is weaker than a top-down one: the player has a handful of hit points and a short blade.
static func scaled(index: int) -> Dictionary:
	return {"hp": 3 + index, "attack": 2 + floori(index / 2.0), "defense": 0, "xp": 4 + 2 * index, "gold": 2 + index}

## patrol, flyer or shooter, from the asset's tags and the words of its name.
static func kind_for(slug: String, tags: Array = []) -> String:
	var words: Array = slug.to_lower().replace("-", "_").split("_", false)
	for tag: Variant in tags:
		words.append(JsonUtil.to_str(tag).to_lower())
	for kind: String in KIND_WORDS:
		var kind_words: Array = KIND_WORDS[kind]
		for word: Variant in words:
			if kind_words.has(word):
				return kind
	return "patrol"

static func display_name(slug: String) -> String:
	var words := slug.split("_", false)
	while words.size() > 1 and NAME_NOISE.has(words[words.size() - 1]):
		words.remove_at(words.size() - 1)
	return " ".join(words).capitalize()

func _usable(ctx: BuildContext, a: Dictionary) -> bool:
	var eff: Dictionary = ctx.catalog.effective(a)
	var animations: Dictionary = eff.get("animations", {})
	return eff.get("usage", "") == "sprite" and not animations.is_empty() and not (a.get("status", "") in ["UNUSED", "MISSING"])

static func _short(id: String) -> String:
	return id.substr(id.rfind(".") + 1).replace("#", "_")

## The enemies: [{asset, slug, index, kind, fallback}] by asset id; the fallback entry (the
## player's sprite) when the packs have no enemy.
func entries(ctx: BuildContext) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var seen := {}
	for a in ctx.catalog.assets_by_role("ENEMY"):
		if not _usable(ctx, a):
			continue
		var id := JsonUtil.to_str(a["id"])
		var slug := _short(id)
		if seen.has(slug):
			slug = id.replace(".", "__").replace("#", "__")
		seen[slug] = true
		var tags := JsonUtil.to_array(ctx.catalog.effective(a).get("tags", []))
		out.append({"asset": a, "slug": slug, "index": out.size(), "kind": kind_for(slug, tags), "fallback": false})
	# an assets-only project has the packs' enemies only (T17.33)
	if out.is_empty() and JsonUtil.to_str(ctx.config.get("archetype", "")) != "assets":
		for a in ctx.catalog.assets_by_role("PLAYER"):
			if _usable(ctx, a):
				out.append({"asset": a, "slug": FALLBACK_SLUG, "index": 0, "kind": "patrol", "fallback": true})
				break
	return out

## The guardian's entry: the BOSS asset, else the last (strongest) enemy; {} when there is none.
func guardian_entry(ctx: BuildContext) -> Dictionary:
	var wanted := JsonUtil.to_str(ctx.section("starter").get("boss", ""))
	var first: Dictionary = {}
	for a in ctx.catalog.assets_by_role("BOSS"):
		if not _usable(ctx, a):
			continue
		if first.is_empty() or JsonUtil.to_str(a["id"]) == wanted:
			first = a
	if not first.is_empty():
		return {"asset": first, "slug": GUARDIAN_SLUG, "index": 0, "kind": "guardian", "fallback": false, "scale": 1.0}
	if JsonUtil.to_str(ctx.config.get("archetype", "")) == "assets":
		return {}  # no enemy drawn larger to stand for a boss in an assets-only project (T17.33)
	var all := entries(ctx)
	if all.is_empty():
		return {}
	var last: Dictionary = all[all.size() - 1]
	# an ordinary enemy as the guardian is drawn half as large again, so it reads as the boss
	return {"asset": last["asset"], "slug": GUARDIAN_SLUG, "index": 0, "kind": "guardian", "fallback": last["fallback"], "scale": 1.5}

## The scene of the enemy placed `index`-th in the rooms ("" without one): the kinds take turns.
func scene_for(ctx: BuildContext, index: int) -> String:
	var all := entries(ctx)
	if all.is_empty():
		return ""
	var entry: Dictionary = all[index % all.size()]
	return scene_path(JsonUtil.to_str(entry["slug"]))

func guardian_scene(ctx: BuildContext) -> String:
	return scene_path(GUARDIAN_SLUG) if not guardian_entry(ctx).is_empty() else ""

func _all(ctx: BuildContext) -> Array[Dictionary]:
	var all := entries(ctx)
	var guardian := guardian_entry(ctx)
	if not guardian.is_empty():
		all.append(guardian)
	return all

func _tile(ctx: BuildContext) -> int:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return JsonUtil.to_int(def["tile_size"][0]) if not def.is_empty() else JsonUtil.to_int(ctx.config.get("base_tile_size", 16))

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for e in _all(ctx):
		var slug: String = e["slug"]
		if not FileAccess.file_exists(definition_path(slug)):
			out.append(definition_path(slug))
		out.append(scene_path(slug))
	return out

func input_hash(ctx: BuildContext) -> String:
	var parts: Array = []
	for e in _all(ctx):
		var a: Dictionary = e["asset"]
		parts.append({"slug": e["slug"], "id": a["id"], "sha256": a.get("sha256", ""), "eff": ctx.catalog.effective(a), "kind": e["kind"], "fallback": e["fallback"], "scale": e.get("scale", 1.0)})
	return ctx.stable_hash({"v": RECIPE_VERSION, "enemies": parts, "tile": _tile(ctx)})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := _tile(ctx)
	for e in _all(ctx):
		var slug: String = e["slug"]
		var asset: Dictionary = e["asset"]
		if JsonUtil.to_bool(e["fallback"]) and slug == FALLBACK_SLUG:
			issues.append(ctx.make_issue("ASSET-025", {}))
		var frames_path: String = Paths.SPRITE_FRAMES_DIR + "%s.tres" % asset["id"]
		var frames := load(frames_path) as SpriteFrames
		if frames == null:
			issues.append(ctx.make_issue("VAL-002", {"file": frames_path}, frames_path))
			continue
		if not FileAccess.file_exists(definition_path(slug)):
			var err := SeedUtil.save(definition(e, frames, tile), definition_path(slug))
			if err != OK:
				issues.append(ctx.make_issue("BUILD-004", {"file": definition_path(slug), "err": err}, definition_path(slug)))
		var fo := ActorBuild.frame_and_origin(ctx.catalog.effective(asset))
		var frame: Vector2i = fo["frame"]
		var origin: Vector2i = fo["origin"]
		var node := build_enemy(e, frames, frame, origin, tile, load(definition_path(slug)) as Resource)
		var save_err := SceneUtil.save_scene(node, scene_path(slug))
		if save_err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": scene_path(slug), "err": save_err}, scene_path(slug)))
	return issues

## A new definition: stats by the enemy's index (the guardian's own), a potion now and then.
static func definition(entry: Dictionary, frames: SpriteFrames, tile: int) -> Resource:
	var def := SeedUtil.make(ENEMY_DEF)
	var slug := JsonUtil.to_str(entry["slug"])
	var kind := JsonUtil.to_str(entry["kind"])
	def.set("id", StringName(slug))
	def.set("display_name", "Guardian" if kind == "guardian" else display_name(_short(JsonUtil.to_str(JsonUtil.to_dict(entry["asset"])["id"]))))
	def.set("sprite_frames", frames)
	var numbers := scaled(JsonUtil.to_int(entry["index"]))
	if kind == "guardian":
		numbers = {"hp": roundi(GUARDIAN_HP * tile / 16.0), "attack": GUARDIAN_ATTACK, "defense": 0, "xp": GUARDIAN_XP, "gold": GUARDIAN_GOLD}
	var stats := SeedUtil.make(STATS)
	stats.set("max_hp", numbers["hp"])
	stats.set("hp", numbers["hp"])
	stats.set("attack", numbers["attack"])
	stats.set("defense", numbers["defense"])
	stats.set("extra", {"crit_chance": 0.0})
	def.set("base_stats", stats)
	def.set("xp_reward", numbers["xp"])
	def.set("gold_reward", numbers["gold"])
	var loot := SeedUtil.make(LOOT)
	loot.set("entries", SeedUtil.dict_array([{"item_id": "potion", "chance": 1.0 if kind == "guardian" else 0.25, "min": 1, "max": 1}]))
	def.set("loot", loot)
	def.set("behavior", {"kind": kind})
	return def

## The scene of an enemy: the side-view body with its kind's script, health, hurtbox and a hitbox
## around the body that hurts on contact; RpgPersistent keeps a defeated one out of its room.
static func build_enemy(entry: Dictionary, frames: SpriteFrames, frame: Vector2i, origin: Vector2i, tile: int, def: Resource) -> CharacterBody2D:
	var kind := JsonUtil.to_str(entry["kind"])
	if def != null:
		var behavior: Variant = def.get("behavior")
		if behavior is Dictionary:
			var table: Dictionary = behavior
			var chosen := JsonUtil.to_str(table.get("kind", kind))
			if SCRIPTS.has(chosen) and kind != "guardian":
				kind = chosen  # the definition's kind wins: it is the user's to change
	var script_path: String = SCRIPTS.get(kind, SCRIPTS["patrol"])
	var root := MvBuild.body("Guardian" if kind == "guardian" else "Enemy", script_path, frames, frame, origin, tile)
	MvBuild.set_layers(root, [3], [1, MvBuild.ONE_WAY_LAYER])  # enemies; world and one-way platforms
	root.set("definition", def)
	root.set("run_speed", SPEEDS.get(kind, 40.0))
	var size := JsonUtil.to_float(entry.get("scale", 1.0))
	if size != 1.0:
		var visual := root.get_node("Visual") as AnimatedSprite2D
		visual.scale = Vector2(size, size)
		visual.position = Vector2.ZERO
		var body_shape := root.get_node("Body") as CollisionShape2D
		var rect := body_shape.shape as RectangleShape2D
		rect.size *= size
		body_shape.position = Vector2(0.0, -rect.size.y * 0.5)
	if JsonUtil.to_bool(entry.get("fallback", false)):
		(root.get_node("Visual") as AnimatedSprite2D).modulate = FALLBACK_TINT
	MvBuild.add_health(root)
	var scaled_frame := Vector2i(roundi(frame.x * size), roundi(frame.y * size))
	MvBuild.add_hurtbox(root, "enemy", 10, MvBuild.ENEMY_INVULN_S, scaled_frame, tile)
	var body := MvBuild.body_size(scaled_frame, tile)
	var hitbox := MvBuild.add_hitbox(root, "enemy", 8, 9, scaled_frame, tile, body * 1.1, 0.0)
	hitbox.set("knockback_strength", 120.0)
	ActorBuild.add_persistent(root)
	return root
