extends RefCounted
## Action-RPG enemies: one definition (game/data/enemies/<slug>.tres, a user_seed file) and one scene
## (generated/scenes/enemies/<slug>.tscn) per ENEMY asset. Without an ENEMY asset the player's
## sprite stands in (ASSET-025), tinted red. The scene holds the combat parts of arpg_build.gd and
## the enemy_ai.gd state machine; the numbers live in the definition's `behavior`.

const RECIPE_VERSION := 2

const Paths := preload("../../lib/paths.gd")
const SceneUtil := preload("../../lib/scene_util.gd")
const ActorBuild := preload("../../lib/actor_build.gd")
const SeedUtil := preload("../../lib/seed_util.gd")
const ArpgBuild := preload("arpg_build.gd")
const Navigation := preload("navigation_recipe.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")

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
	"kind": "melee",
	"vision_px": 96, "lose_px": 160, "attack_range_px": 18, "attack_cooldown_s": 1.2,
	"windup_s": 0.35, "active_s": 0.15, "move_speed": 45, "chase_speed": 60,
	"wander_radius_px": 32, "wander_pause_s": [1.0, 2.5], "knockback_resist": 0.0,
	"nav_mode": "direct",
	"shoot_range_px": 80, "keep_away_px": 40, "projectile_speed": 120, "projectile_range_px": 160,
	"shoot_windup_s": 0.45, "shoot_cooldown_s": 1.6,
	"charge_range_px": 72, "charge_speed": 180, "charge_windup_s": 0.5, "charge_s": 0.45,
	"charge_recover_s": 0.6, "charge_cooldown_s": 1.5,
}
const PIXEL_KEYS: Array[String] = ["vision_px", "lose_px", "attack_range_px", "move_speed", "chase_speed", "wander_radius_px", "shoot_range_px", "keep_away_px", "projectile_speed", "projectile_range_px", "charge_range_px", "charge_speed"]
## How an enemy fights, from words in its asset's name (anything else fights in melee).
const KIND_WORDS := {
	"shooter": ["archer", "mage", "wizard", "witch", "caster", "shaman", "sorcerer", "gunner"],
	"turret": ["turret", "cannon", "totem", "tower", "eye", "plant"],
	"charger": ["boar", "bull", "rhino", "charger", "ram", "beetle"],
}
## Kinds of the extra definitions made from the first enemy for the demo field: <slug>_<kind>.tres.
const DEMO_VARIANTS: Array[String] = ["charger", "shooter"]

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
static func behavior_for(tile: int, nav_mode: String, kind: String = "melee") -> Dictionary:
	var out: Dictionary = BEHAVIOR.duplicate(true)
	for key in PIXEL_KEYS:
		out[key] = JsonUtil.to_int(round(JsonUtil.to_float(out[key]) * JsonUtil.to_float(tile) / 16.0))
	out["nav_mode"] = nav_mode
	out["kind"] = kind
	return out

## The kind an enemy named `slug` fights as: a word of KIND_WORDS in its name, else melee.
static func kind_for(slug: String) -> String:
	var words := slug.to_lower().replace("-", "_").split("_", false)
	for kind: String in KIND_WORDS:
		var kind_words: Array = KIND_WORDS[kind]
		for word in words:
			if kind_words.has(word):
				return kind
	return "melee"

## The demo variant of an enemy: <slug>_<kind>.tres.
static func variant_path(slug: String, kind: String) -> String:
	return definition_path("%s_%s" % [slug, kind])

## `stats` ({hp, attack, defense, xp, gold}) with a recolour variant's multipliers applied (its
## `stats`: hp, attack, xp, gold; each result at least 1). Without a variant, `stats` as it is.
static func recoloured_stats(stats: Dictionary, recolour: Dictionary) -> Dictionary:
	var factors := JsonUtil.to_dict(recolour.get("stats", {}))
	if factors.is_empty():
		return stats
	var out := stats.duplicate()
	for key: String in ["hp", "attack", "xp", "gold"]:
		if factors.has(key):
			out[key] = maxi(1, roundi(JsonUtil.to_float(stats[key]) * JsonUtil.to_float(factors[key])))
	return out

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
## Recolour variants (T13.18) come after the packs' own enemies, so those keep their index and
## slug; a variant's entry also has `recolour` (its definition in the catalog) and the index of
## its source, whose stats it starts from. The demo maps never place a variant by themselves.
func entries(ctx: BuildContext) -> Array[Dictionary]:
	var assets: Array[Dictionary] = []
	var recoloured: Array[Dictionary] = []
	for a in ctx.catalog.assets_by_role("ENEMY"):
		if not _usable(ctx, a):
			continue
		if ctx.catalog.recolour(JsonUtil.to_str(a["id"])).is_empty():
			assets.append(a)
		else:
			recoloured.append(a)
	if assets.is_empty():  # only variants are left: they are the enemies
		assets = recoloured
		recoloured = []
	var out: Array[Dictionary] = []
	if not assets.is_empty():
		var ids: Array = []
		for a in assets:
			ids.append(a["id"])
		var slugs := slugs_for(ids)
		for i in assets.size():
			out.append({"asset": assets[i], "slug": slugs[i], "index": i, "fallback": false})
		var taken := {}
		for e in out:
			taken[e["slug"]] = true
		for a in recoloured:
			var id := JsonUtil.to_str(a["id"])
			var recolour: Dictionary = ctx.catalog.recolour(id)
			var slug := id.substr(id.rfind(".") + 1).replace("#", "_")
			if taken.has(slug):
				slug = id.replace(".", "__").replace("#", "__")
			taken[slug] = true
			var index := out.size()
			for e in out:
				var base: Dictionary = e["asset"]
				if base["id"] == recolour.get("source", ""):
					index = JsonUtil.to_int(e["index"])
			out.append({"asset": a, "slug": slug, "index": index, "fallback": false, "recolour": recolour})
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

## The scene of the `index`-th enemy the starter map places: index 0 is the starter.enemy asset (else
## the first enemy), the next ones the following enemies (the same one again when there is only
## one). "" when no enemy scene exists.
func starter_scene_at(ctx: BuildContext, index: int) -> String:
	var list: Array[Dictionary] = []
	var wanted := JsonUtil.to_str(ctx.section("starter").get("enemy", ""))
	for e in entries(ctx):
		var slug: String = e["slug"]
		var entry_asset: Dictionary = e["asset"]
		if e.has("recolour") and entry_asset["id"] != wanted:
			continue  # a recolour variant is placed only when it is the chosen starter enemy
		if ResourceLoader.exists(scene_path(slug)):
			list.append(e)
	if list.is_empty():
		return ""
	var first := 0
	for i in list.size():
		var asset: Dictionary = list[i]["asset"]
		if wanted != "" and asset["id"] == wanted:
			first = i
	var chosen_slug: String = list[(first + index) % list.size()]["slug"]
	return scene_path(chosen_slug)

func starter_scene(ctx: BuildContext) -> String:
	return starter_scene_at(ctx, 0)

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
	var first := _demo_slug(ctx)
	if first != "":
		for kind in DEMO_VARIANTS:
			if not FileAccess.file_exists(variant_path(first, kind)):
				out.append(variant_path(first, kind))
	return out

## The slug of the starter enemy when the demo is on (its variants are made), else "". Chosen from
## the catalog alone, never from which scenes exist yet, so that the input hash is the same before
## and after the first build.
func _demo_slug(ctx: BuildContext) -> String:
	var list := entries(ctx)
	if not JsonUtil.to_bool(ctx.section("features").get("demo", true)) or ctx.demo_removed or list.is_empty():
		return ""
	var wanted := JsonUtil.to_str(ctx.section("starter").get("enemy", ""))
	for e in list:
		var asset: Dictionary = e["asset"]
		if wanted != "" and asset["id"] == wanted:
			return JsonUtil.to_str(e["slug"])
	return JsonUtil.to_str(list[0]["slug"])

func input_hash(ctx: BuildContext) -> String:
	var parts: Array = []
	for e in entries(ctx):
		var a: Dictionary = e["asset"]
		var part := {"id": a["id"], "slug": e["slug"], "fallback": e["fallback"], "sha256": a.get("sha256", ""), "eff": ctx.catalog.effective(a)}
		if e.has("recolour"):
			part["recolour"] = e["recolour"]
		parts.append(part)
	return ctx.stable_hash({"v": RECIPE_VERSION, "enemies": parts, "tile": _tile(ctx), "nav": Navigation.nav_mode(ctx), "demo": _demo_slug(ctx)})

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
			_save_definition(ctx, e, frames, tile, issues)
		var def := load(definition_path(slug)) as Resource
		if def == null:
			issues.append(ctx.make_issue("VAL-002", {"file": definition_path(slug)}, definition_path(slug)))
			continue
		var fo := ActorBuild.frame_and_origin(ctx.catalog.effective(a))
		var node := _build_scene(frames, fo, tile, def, JsonUtil.to_bool(e["fallback"]), Navigation.enabled(ctx))
		var err := SceneUtil.save_scene(node, scene_path(slug))
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": scene_path(slug), "err": err}, scene_path(slug)))
	var first := _demo_slug(ctx)
	if first != "":
		_save_variants(ctx, first, tile, issues)
	return issues

func _save_definition(ctx: BuildContext, e: Dictionary, frames: SpriteFrames, tile: int, issues: Array) -> void:
	var recolour := JsonUtil.to_dict(e.get("recolour", {}))
	var s := recoloured_stats(scaled(JsonUtil.to_int(e["index"])), recolour)
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
	var recolour_name := JsonUtil.to_str(recolour.get("name", ""))
	if recolour_name != "":
		def.set("display_name", recolour_name)
	def.set("sprite_frames", frames)
	def.set("base_stats", stats)
	def.set("xp_reward", s["xp"])
	def.set("gold_reward", s["gold"])
	def.set("loot", loot)
	var slug: String = e["slug"]
	def.set("behavior", behavior_for(tile, Navigation.nav_mode(ctx), kind_for(slug)))
	var path := definition_path(slug)
	var err := SeedUtil.save(def, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## The demo field's charger and shooter: copies of the first enemy's definition that fight that way
## (written once, beside it; a project without the demo gets none).
func _save_variants(ctx: BuildContext, slug: String, tile: int, issues: Array) -> void:
	var base := load(definition_path(slug)) as Resource
	if base == null:
		return
	for kind in DEMO_VARIANTS:
		var path := variant_path(slug, kind)
		if FileAccess.file_exists(path):
			continue
		var variant := base.duplicate(true)
		variant.set("id", StringName("%s_%s" % [slug, kind]))
		variant.set("display_name", "%s (%s)" % [JsonUtil.to_str(base.get("display_name")), kind])
		variant.set("behavior", behavior_for(tile, Navigation.nav_mode(ctx), kind))
		var err := SeedUtil.save(variant, path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## The enemy actor: base actor + enemy_ai.gd + the combat parts. (Inherited scenes cannot be saved
## headless, so it is built by the same function as every other actor.)
func _build_scene(frames: SpriteFrames, fo: Dictionary, tile: int, def: Resource, fallback: bool, agent: bool) -> Node:
	var frame: Vector2i = fo["frame"]
	var origin: Vector2i = fo["origin"]
	var root := ActorBuild.build("base", "Enemy", frames, frame, origin, tile)
	SceneUtil.attach_script(root, ArpgBuild.ENEMY_AI)
	root.set("definition", def)
	root.set("tile_size", float(tile))
	if fallback:
		(root.get_node("Visual") as CanvasItem).modulate = FALLBACK_TINT
	ArpgBuild.augment_enemy(root, frame, tile, agent)
	ActorBuild.add_persistent(root)
	return root
