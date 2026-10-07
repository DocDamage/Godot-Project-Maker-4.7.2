class_name RpgActor
extends CharacterBody2D
## Base of the player, NPCs and (later) enemies. Behaviour lives in components under the
## "Components" child (Movement, Stats, ...).

signal facing_changed(f: String)

@export var definition: RpgActorDefinition
@export var facing: String = "down":
	set = _set_facing_property
var input_enabled := true

var _components: Dictionary = {}
var _driver := RpgAnimationDriver.new()

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

## Forwards to the Movement component.
func move_dir(dir: Vector2) -> void:
	var movement := component("Movement")
	if movement != null:
		movement.set("desired", dir)
	if dir != Vector2.ZERO:
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
	if velocity.length() > 1.0:
		_driver.play("walk", facing)
	else:
		_play_idle()

func _play_idle() -> void:
	_driver.play("idle", facing)
