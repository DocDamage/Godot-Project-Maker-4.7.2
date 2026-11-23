class_name RpgActor
extends CharacterBody2D
## Base of the player, NPCs and (later) enemies. Behaviour lives in components under the
## "Components" child (Movement, Stats, ...).

signal facing_changed(f: String)

@export var definition: RpgActorDefinition
@export var facing: String = "down":
	set = _set_facing_property
var input_enabled := true
## Set by an archetype's combat code (attack, dodge, hurt): the input does not move the actor and
## `facing_locked` keeps move_dir from turning it.
var move_locked := false
var facing_locked := false
## While true the actor does not pick walk/idle animations itself (a combat state is playing one).
var animation_locked := false
## Set by a running sequence that walks this actor by moving its position: the walk animation
## plays although the body has no velocity.
var scripted_walk := false

var _components: Dictionary = {}
var _driver := RpgAnimationDriver.new()
## The last direction of travel: a sprite with diagonal animations shows them along it.
var _look := Vector2.ZERO
## The levels of the map the actor is on (T18.20), found once; null on a map without heights.
var _levels: RpgLevels = null
var _levels_known := false
var _tile_hazards := RpgTileHazards.new()

func _ready() -> void:
	_cache_components()
	_driver.sprite = get_node_or_null("Visual") as AnimatedSprite2D
	_play_idle()

func _cache_components() -> void:
	_components.clear()
	var holder := get_node_or_null("Components")
	if holder != null:
		for child in holder.get_children():
			_components[String(child.name)] = child

## Component name -> node, cached in _ready from the "Components" child.
func components() -> Dictionary:
	if _components.is_empty():
		_cache_components()
	return _components

func component(component_name: String) -> Node:
	return components().get(component_name)

## The last direction of travel on the screen (zero for an actor that has not moved).
func look() -> Vector2:
	return _look

## The map this actor is on: its nearest RpgMapRoot ancestor, else the router's current map.
func map_node() -> Node:
	var node := get_parent()
	while node != null:
		if node is RpgMapRoot:
			return node
		node = node.get_parent()
	var router := RpgUtil.router()
	return router.current_map if router != null else null

## The cell this actor stands on and the one in front of it (T17.14): asked of the map, so the
## answer holds on squares and on diamonds. On an isometric map the cell ahead is the neighbour
## the actor last walked towards, else the one its facing names (up n, right e, down s, left w).
func map_cell() -> Vector2i:
	return RpgIso.cell_at(map_node(), RpgUtil.world_position(self))

func cell_ahead() -> Vector2i:
	return RpgIso.cell_ahead(map_node(), RpgUtil.world_position(self), facing, _look)

## Forwards to the Movement component.
func move_dir(dir: Vector2) -> void:
	var movement := component("Movement")
	if movement != null:
		movement.set("desired", dir)
	if dir != Vector2.ZERO and not facing_locked:
		set_facing(RpgAnimationDriver.dir_to_facing(dir))

func set_facing(f: String) -> void:
	if f == facing:
		return
	facing = f

func _set_facing_property(f: String) -> void:
	if f == facing:
		return
	facing = f
	facing_changed.emit(f)

func _physics_process(_delta: float) -> void:
	if is_in_group("player"):
		_tile_hazards.tick(_delta)
		var hazard := _tile_hazards.on_map(map_node(), RpgUtil.world_position(self))
		var stats := component("Stats") as RpgStatsComponent
		if stats != null and _tile_hazards.consume(hazard):
			stats.take_damage(RpgUtil.to_int(hazard["damage"]))
	_keep_level()
	if animation_locked:
		return
	if velocity.length() > 1.0 or scripted_walk:
		if velocity.length() > 1.0:
			_look = velocity
		_driver.play("walk", facing, _look)
	else:
		_play_idle()

## On a map with height layers (T18.20): the level under the actor, its picture drawn that
## high, and the wall of its level in its mask (RpgLevels.follow). Nothing on any other map.
func _keep_level() -> void:
	if not _levels_known or (_levels != null and not is_instance_valid(_levels)):
		_levels_known = true
		_levels = RpgLevels.near(self) if is_inside_tree() else null
	if _levels != null:
		_levels.follow(self, get_node_or_null("Visual") as Node2D)

## Plays "<base>_<facing>" and holds it (a sequence's `animate`) until release_animation().
## False when the actor has no such animation.
func hold_animation(base: String) -> bool:
	if not _driver.has_animation(base, facing):
		return false
	_driver.play_exact(base, facing)
	animation_locked = true
	return true

## hold_animation() in the facing the actor has, else in the first direction the sheet has it
## (a pack that drew a tool's use looking down only, T18.10). False when it has none.
func hold_animation_any(base: String) -> bool:
	if hold_animation(base):
		return true
	for other: String in ["down", "right", "left", "up"]:
		if _driver.has_animation(base, other):
			_driver.play_exact(base, other)
			animation_locked = true
			return true
	return false

## Back to the walk / idle animations.
func release_animation() -> void:
	animation_locked = false
	_play_idle()

func _play_idle() -> void:
	_driver.play("idle", facing, _look)
