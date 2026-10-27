extends RefCounted
## Actor scenes under res://generated/scenes/actors/: actor_base, player, npc and one concrete
## scene per character asset (players and NPCs). Replaces the M1 player recipe.

const RECIPE_VERSION := 3

const Paths := preload("../lib/paths.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const ActorBuild := preload("../lib/actor_build.gd")
const BuildContext := preload("../lib/build_context.gd")
const MapGeo := preload("../lib/map_geo.gd")
const SideTileset := preload("../lib/side_tileset.gd")

const ACTORS_DIR := "res://generated/scenes/actors/"
const BASE_PATH := ACTORS_DIR + "actor_base.tscn"
const PLAYER_PATH := ACTORS_DIR + "player.tscn"
const NPC_PATH := ACTORS_DIR + "npc.tscn"
const CHARACTERS_DIR := ACTORS_DIR + "characters/"
const FALLBACK_NPC_PATH := CHARACTERS_DIR + "npc_fallback.tscn"
## Archetype -> helper that adds the archetype's parts to the player (builder/recipes/<this>); the
## archetypes without one leave the player as it is.
const PLAYER_AUGMENTERS := {"arpg": "arpg/arpg_build.gd", "farm": "farm/farm_build.gd"}
## Archetype -> helper that builds the whole actor instead of ActorBuild (builder/recipes/<this>):
## a side-view character is another kind of body (T14.03). Its static `build_actor(kind, root_name,
## frames, frame, origin, tile)` returns the scene's root.
const ACTOR_BUILDERS := {"metroidvania": "metroidvania/player_recipe.gd"}
## Character asset id -> scene path, for the editor's asset library (T8.02).
const INDEX_PATH := "res://rpggen/character_index.json"

static func character_scene_path(asset_id: String) -> String:
	return CHARACTERS_DIR + asset_id.replace(".", "__").replace("#", "__") + ".tscn"

## Assets with an actor role (PLAYER first), as {asset, kind} entries sorted by id. An
## assets-only project (T17.33) has its animals among them, as people who walk about: the dock
## places them.
func _characters(ctx: BuildContext) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var roles: Array[String] = ["PLAYER", "NPC"]
	if _assets_only(ctx):
		roles.append("ANIMAL")
	for role: String in roles:
		for a in ctx.catalog.assets_by_role(role):
			var eff: Dictionary = ctx.catalog.effective(a)
			var animations: Dictionary = eff.get("animations", {})
			if eff.get("usage", "") != "sprite" or animations.is_empty():
				continue
			if a.get("status", "") in ["UNUSED", "MISSING"]:
				continue
			var asset_id: String = a["id"]
			out.append({"asset": a, "kind": "player" if role == "PLAYER" else "npc", "path": character_scene_path(asset_id)})
	# Without an NPC asset the player's sprite also serves as the NPC (tagged as a fallback).
	var has_npc := false
	var player_entry: Dictionary = {}
	for c in out:
		if c["kind"] == "npc":
			has_npc = true
		elif player_entry.is_empty():
			player_entry = c
	if not has_npc and not player_entry.is_empty():
		out.append({"asset": player_entry["asset"], "kind": "npc", "path": FALLBACK_NPC_PATH})
	return out

static func _assets_only(ctx: BuildContext) -> bool:
	return JsonUtil.to_str(ctx.config.get("archetype", "")) == SideTileset.ASSETS_KIND

func _player_asset(ctx: BuildContext) -> Dictionary:
	for c in _characters(ctx):
		if c["kind"] == "player":
			return c["asset"]
	return {}

func _tile(ctx: BuildContext) -> int:
	return MapGeo.tile_unit(ctx)

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([BASE_PATH, PLAYER_PATH, NPC_PATH, INDEX_PATH])
	for c in _characters(ctx):
		var char_path: String = c["path"]
		out.append(char_path)
	return out

func input_hash(ctx: BuildContext) -> String:
	var parts: Array = []
	for c in _characters(ctx):
		var a: Dictionary = c["asset"]
		parts.append({"id": a["id"], "kind": c["kind"], "path": c["path"], "sha256": a.get("sha256", ""), "eff": ctx.catalog.effective(a)})
	var hashed := {"v": RECIPE_VERSION, "chars": parts, "tile": _tile(ctx), "archetype": ctx.config.get("archetype", "")}
	if _assets_only(ctx):
		hashed["view"] = ctx.config.get("view", "")  # the side-view body or the top-down one
	if MapGeo.camera_zoom(ctx) != 1.0:  # only an isometric project of large diamonds has the key
		hashed["zoom"] = MapGeo.camera_zoom(ctx)
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := _tile(ctx)
	_save(ctx, _build_actor(ctx, "base", "ActorBase", null, ActorBuild.DEFAULT_FRAME, Vector2i(8, 23), tile), BASE_PATH, issues)
	_save(ctx, _build_actor(ctx, "npc", "Npc", null, ActorBuild.DEFAULT_FRAME, Vector2i(8, 23), tile), NPC_PATH, issues)
	var player_asset := _player_asset(ctx)
	if player_asset.is_empty() and not _assets_only(ctx):
		issues.append(ctx.make_issue("BUILD-002", {"recipe": "actor_recipes", "reason": "no asset with role PLAYER in the catalog"}))
		return issues
	var index := {}
	for c in _characters(ctx):
		var a: Dictionary = c["asset"]
		var frames_path: String = Paths.SPRITE_FRAMES_DIR + "%s.tres" % a["id"]
		var frames := load(frames_path) as SpriteFrames
		if frames == null:
			issues.append(ctx.make_issue("VAL-002", {"file": frames_path}, frames_path))
			continue
		var fo := ActorBuild.frame_and_origin(ctx.catalog.effective(a))
		var kind: String = c["kind"]
		var char_path: String = c["path"]
		var frame: Vector2i = fo["frame"]
		var origin: Vector2i = fo["origin"]
		var root_name := "Player" if kind == "player" else "Npc"
		var node := _build_actor(ctx, kind, root_name, frames, frame, origin, tile)
		ActorBuild.set_feet(node, ctx.catalog.effective(a))
		ActorBuild.add_shadow(node, ctx.catalog.effective(a))
		if kind == "player":
			_augment_player(ctx, node, fo, tile)
		_save(ctx, node, char_path, issues)
		if char_path != FALLBACK_NPC_PATH:
			index[a["id"]] = char_path
		if kind == "player" and a["id"] == player_asset.get("id", ""):
			var main := _build_actor(ctx, "player", "Player", frames, frame, origin, tile)
			ActorBuild.set_feet(main, ctx.catalog.effective(a))
			ActorBuild.add_shadow(main, ctx.catalog.effective(a))
			_augment_player(ctx, main, fo, tile)
			_save(ctx, main, PLAYER_PATH, issues)
	var write_err := JsonUtil.write(INDEX_PATH, index)
	if write_err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": INDEX_PATH, "err": write_err}, INDEX_PATH))
	return issues

## The actor's node tree: the archetype's own builder when it has one, else the top-down actor.
func _build_actor(ctx: BuildContext, kind: String, root_name: String, frames: SpriteFrames, frame: Vector2i, origin: Vector2i, tile: int) -> CharacterBody2D:
	var rel: String = ACTOR_BUILDERS.get(JsonUtil.to_str(ctx.config.get("archetype", "")), "")
	if _assets_only(ctx) and SideTileset.side_view(ctx.config):
		rel = ACTOR_BUILDERS["metroidvania"]  # seen from the side: the side-view body (T17.33)
	if rel != "":
		var here: Script = get_script()
		var script := load(here.resource_path.get_base_dir().path_join(rel)) as GDScript
		if script != null:
			var built: Variant = script.call("build_actor", kind, root_name, frames, frame, origin, tile)
			if built is CharacterBody2D:
				var body: CharacterBody2D = built
				return body
	return ActorBuild.build(kind, root_name, frames, frame, origin, tile)

## Adds the archetype's combat parts to a player actor (the arpg player gets its hurtbox, hitbox,
## health and combat state machine).
func _augment_player(ctx: BuildContext, node: Node, fo: Dictionary, tile: int) -> void:
	var rel: String = PLAYER_AUGMENTERS.get(JsonUtil.to_str(ctx.config.get("archetype", "")), "")
	if rel == "":
		return
	var here: Script = get_script()
	var script := load(here.resource_path.get_base_dir().path_join(rel)) as GDScript
	if script != null:
		script.call("augment_player", node, fo["frame"], fo["origin"], tile)

func _save(ctx: BuildContext, node: Node, path: String, issues: Array) -> void:
	# the camera of an isometric game of large diamonds is drawn back (T17.14)
	var camera := node.get_node_or_null("Camera") as Camera2D
	var zoom := MapGeo.camera_zoom(ctx)
	if camera != null and zoom != 1.0:
		camera.zoom = Vector2(zoom, zoom)
	var err := SceneUtil.save_scene(node, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
