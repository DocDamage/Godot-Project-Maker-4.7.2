extends RefCounted
## Actor scenes under res://generated/scenes/actors/: actor_base, player, npc and one concrete
## scene per character asset (players and NPCs). Replaces the M1 player recipe.

const RECIPE_VERSION := 3

const Paths := preload("../lib/paths.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const ActorBuild := preload("../lib/actor_build.gd")

const ACTORS_DIR := "res://generated/scenes/actors/"
const BASE_PATH := ACTORS_DIR + "actor_base.tscn"
const PLAYER_PATH := ACTORS_DIR + "player.tscn"
const NPC_PATH := ACTORS_DIR + "npc.tscn"
const CHARACTERS_DIR := ACTORS_DIR + "characters/"
const FALLBACK_NPC_PATH := CHARACTERS_DIR + "npc_fallback.tscn"
## Archetype -> helper that adds the archetype's parts to the player (builder/recipes/<this>); the
## archetypes without one leave the player as it is.
const PLAYER_AUGMENTERS := {"arpg": "arpg/arpg_build.gd"}
## Character asset id -> scene path, for the editor's asset library (T8.02).
const INDEX_PATH := "res://rpggen/character_index.json"

static func character_scene_path(asset_id: String) -> String:
	return CHARACTERS_DIR + asset_id.replace(".", "__").replace("#", "__") + ".tscn"

## Assets with an actor role (PLAYER first), as {asset, kind} entries sorted by id.
func _characters(ctx) -> Array:
	var out: Array = []
	for role in ["PLAYER", "NPC"]:
		for a in ctx.catalog.assets_by_role(role):
			var eff: Dictionary = ctx.catalog.effective(a)
			if eff.get("usage", "") != "sprite" or eff.get("animations", {}).is_empty():
				continue
			if a.get("status", "") in ["UNUSED", "MISSING"]:
				continue
			out.append({"asset": a, "kind": "player" if role == "PLAYER" else "npc", "path": character_scene_path(a["id"])})
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

func _player_asset(ctx) -> Dictionary:
	for c in _characters(ctx):
		if c["kind"] == "player":
			return c["asset"]
	return {}

func _tile(ctx) -> int:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return int(def["tile_size"][0]) if not def.is_empty() else int(ctx.config.get("base_tile_size", 16))

func outputs(ctx) -> PackedStringArray:
	var out := PackedStringArray([BASE_PATH, PLAYER_PATH, NPC_PATH, INDEX_PATH])
	for c in _characters(ctx):
		out.append(c["path"])
	return out

func input_hash(ctx) -> String:
	var parts: Array = []
	for c in _characters(ctx):
		var a: Dictionary = c["asset"]
		parts.append({"id": a["id"], "kind": c["kind"], "path": c["path"], "sha256": a.get("sha256", ""), "eff": ctx.catalog.effective(a)})
	return ctx.stable_hash({"v": RECIPE_VERSION, "chars": parts, "tile": _tile(ctx), "archetype": ctx.config.get("archetype", "")})

func build(ctx) -> Array:
	var issues: Array = []
	var tile := _tile(ctx)
	_save(ctx, ActorBuild.build("base", "ActorBase", null, ActorBuild.DEFAULT_FRAME, Vector2i(8, 23), tile), BASE_PATH, issues)
	_save(ctx, ActorBuild.build("npc", "Npc", null, ActorBuild.DEFAULT_FRAME, Vector2i(8, 23), tile), NPC_PATH, issues)
	var player_asset := _player_asset(ctx)
	if player_asset.is_empty():
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
		var root_name := "Player" if c["kind"] == "player" else "Npc"
		var node := ActorBuild.build(c["kind"], root_name, frames, fo["frame"], fo["origin"], tile)
		if c["kind"] == "player":
			_augment_player(ctx, node, fo, tile)
		_save(ctx, node, c["path"], issues)
		if c["path"] != FALLBACK_NPC_PATH:
			index[a["id"]] = c["path"]
		if c["kind"] == "player" and a["id"] == player_asset["id"]:
			var main := ActorBuild.build("player", "Player", frames, fo["frame"], fo["origin"], tile)
			_augment_player(ctx, main, fo, tile)
			_save(ctx, main, PLAYER_PATH, issues)
	var write_err := JsonUtil.write(INDEX_PATH, index)
	if write_err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": INDEX_PATH, "err": write_err}, INDEX_PATH))
	return issues

## Adds the archetype's combat parts to a player actor (the arpg player gets its hurtbox, hitbox,
## health and combat state machine).
func _augment_player(ctx, node: Node, fo: Dictionary, tile: int) -> void:
	var rel: String = PLAYER_AUGMENTERS.get(String(ctx.config.get("archetype", "")), "")
	if rel == "":
		return
	var script := load(get_script().resource_path.get_base_dir().path_join(rel)) as GDScript
	if script != null:
		script.call("augment_player", node, fo["frame"], fo["origin"], tile)

func _save(ctx, node: Node, path: String, issues: Array) -> void:
	var err := SceneUtil.save_scene(node, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
