extends RefCounted
## Builds the node tree of the actor scenes (base, player, npc and the per-character scenes).
##
## Inherited scenes cannot be saved from a headless script (probe: tests/probes/probe_inherited.gd,
## docs/godot_api_verified.md), so every actor scene is built by this one function; player and npc
## differ from the base only by the parts added here. Users who want their own variant create an
## inherited scene from the generated one in the editor.

const SceneUtil := preload("scene_util.gd")
const JsonUtil := preload("json_util.gd")

const ACTOR_SCRIPT := "res://addons/rpg_runtime/actors/actor.gd"
const NPC_SCRIPT := "res://addons/rpg_runtime/actors/npc.gd"
const MOVEMENT_SCRIPT := "res://addons/rpg_runtime/actors/components/movement.gd"
const STATS_SCRIPT := "res://addons/rpg_runtime/actors/components/stats_component.gd"
const INTERACTION_SCRIPT := "res://addons/rpg_runtime/actors/components/interaction.gd"
const PLAYER_INPUT_SCRIPT := "res://addons/rpg_runtime/actors/player_input.gd"
const PERSISTENT_SCRIPT := "res://addons/rpg_runtime/world/persistent.gd"

const DEFAULT_FRAME := Vector2i(16, 24)

## The feet of an actor `width` pixels wide, where its sheet says how wide they are (the facet
## `feet`, T17.29: a character drawn in frames much wider than it walks through no door with feet
## of 0.6 of its frame). An actor whose sheet says nothing keeps the feet `build` gave it.
static func set_feet(root: Node, eff: Dictionary) -> void:
	if not eff.has("feet"):
		return
	var feet := root.get_node_or_null("Feet") as CollisionShape2D
	if feet == null:
		return
	var shape := feet.shape as RectangleShape2D
	if shape != null:
		shape.size = Vector2(maxf(4.0, JsonUtil.to_float(eff["feet"])), shape.size.y)

## How opaque a pack's shadow is drawn (Gridwright's READMEs: "at about 35% opacity").
const SHADOW_ALPHA := 0.35

## The shadow a pack draws under a character or a thing (the facet `shadow`, 2026-10-26): a
## Sprite2D `Shadow` under the picture. A thing's shadow is drawn with the thing's anchor (its
## picture may be larger: an altar's falls beyond it), so it lies at the thing's `picture_offset`
## when one is given (`aligned`); a character's (an oval for under the feet) is centred on them.
## Nothing is added when the facet is not there or its file is missing.
static func add_shadow(root: Node, eff: Dictionary, picture_offset: Vector2 = Vector2.ZERO, aligned: bool = false) -> void:
	var path := JsonUtil.to_str(eff.get("shadow", ""))
	if path == "" or root.get_node_or_null("Shadow") != null:
		return
	var res_path := path if path.begins_with("res://") else "res://" + path
	var texture := load(res_path) as Texture2D if ResourceLoader.exists(res_path) else null
	if texture == null:
		return
	var shadow := Sprite2D.new()
	shadow.name = "Shadow"
	shadow.texture = texture
	shadow.modulate = Color(1, 1, 1, SHADOW_ALPHA)
	if aligned:
		shadow.centered = false
		shadow.offset = picture_offset
	root.add_child(shadow)
	root.move_child(shadow, 0)  # drawn first: under the picture

## kind: "base", "player" or "npc". `frames` may be null (base and npc templates). `frame` is the
## frame size and `origin` the feet pixel inside it.
static func build(kind: String, root_name: String, frames: SpriteFrames, frame: Vector2i, origin: Vector2i, tile: int) -> CharacterBody2D:
	var root := CharacterBody2D.new()
	root.name = root_name
	root.motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	SceneUtil.attach_script(root, NPC_SCRIPT if kind == "npc" else ACTOR_SCRIPT)
	root.collision_layer = 0  # clear the engine default (layer 1)
	root.collision_mask = 0
	match kind:
		"player":
			root.set_collision_layer_value(2, true)  # player
			for layer: int in [1, 3, 4]:  # world, enemies, npcs
				root.set_collision_mask_value(layer, true)
			root.add_to_group("player", true)
		"npc":
			root.set_collision_layer_value(4, true)  # npcs
			root.set_collision_mask_value(1, true)  # world
		_:
			root.set_collision_mask_value(1, true)

	var visual := AnimatedSprite2D.new()
	visual.name = "Visual"
	visual.centered = false
	visual.offset = -Vector2(origin)  # node origin = feet
	if frames != null:
		visual.sprite_frames = frames
		if frames.has_animation("idle_down"):
			visual.animation = "idle_down"
	root.add_child(visual)

	var feet := CollisionShape2D.new()
	feet.name = "Feet"
	var shape := RectangleShape2D.new()
	shape.size = Vector2(maxf(4.0, frame.x * 0.6), 6.0)
	feet.shape = shape
	feet.position = Vector2(0, -3)
	root.add_child(feet)

	var components := Node.new()
	components.name = "Components"
	root.add_child(components)
	var movement := Node.new()
	movement.name = "Movement"
	SceneUtil.attach_script(movement, MOVEMENT_SCRIPT)
	components.add_child(movement)
	var stats := Node.new()
	stats.name = "Stats"
	SceneUtil.attach_script(stats, STATS_SCRIPT)
	components.add_child(stats)

	if kind == "player":
		var input := Node.new()
		input.name = "PlayerInput"
		SceneUtil.attach_script(input, PLAYER_INPUT_SCRIPT)
		components.add_child(input)
		var interaction := Area2D.new()
		interaction.name = "Interaction"
		SceneUtil.attach_script(interaction, INTERACTION_SCRIPT)
		interaction.set("tile_size", float(tile))
		interaction.collision_layer = 0
		interaction.collision_mask = 0
		interaction.set_collision_mask_value(4, true)  # npcs
		interaction.set_collision_mask_value(5, true)  # interactables
		interaction.monitorable = true  # static bodies (chests, signs) are only found by monitorable areas
		var ishape := CollisionShape2D.new()
		ishape.name = "Shape"
		var irect := RectangleShape2D.new()
		irect.size = Vector2(tile * 0.75, tile * 0.75)
		ishape.shape = irect
		interaction.add_child(ishape)
		interaction.position = Vector2(0, tile * 0.6)
		root.add_child(interaction)
		var cam := Camera2D.new()
		cam.name = "Camera"
		cam.enabled = true
		root.add_child(cam)
	return root

## Frame size and origin of a sprite asset from its effective facets.
static func frame_and_origin(eff: Dictionary) -> Dictionary:
	var f: Array = eff.get("frame", [DEFAULT_FRAME.x, DEFAULT_FRAME.y])
	var frame := Vector2i(JsonUtil.to_int(f[0]), JsonUtil.to_int(f[1]))
	var o: Array = eff.get("origin", [frame.x / 2, frame.y - 1])
	return {"frame": frame, "origin": Vector2i(JsonUtil.to_int(o[0]), JsonUtil.to_int(o[1]))}

## Adds an RpgPersistent child (owner is set by the scene saver).
static func add_persistent(parent: Node) -> Node:
	var p := Node.new()
	p.name = "Persistent"
	SceneUtil.attach_script(p, PERSISTENT_SCRIPT)
	parent.add_child(p)
	return p
