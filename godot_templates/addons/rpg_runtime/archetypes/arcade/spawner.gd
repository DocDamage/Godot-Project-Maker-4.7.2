class_name RpgArcadeSpawner
extends Node
## Puts the enemies of one wave into a stage when its trigger comes: the scroller has come far
## enough, the stage has run long enough, or an earlier wave is cleared. It knows when the wave
## is cleared (every enemy is gone from the stage, killed or flown away).
##
## An enemy is any Node2D. When it has a signal `defeated` the spawner hears of the kill and
## reports its points (the property `points` of the enemy, else those of the wave).

signal triggered
signal spawned(enemy: Node2D)
signal enemy_defeated(points: int)
signal cleared

enum State { WAITING, SPAWNING, ACTIVE, CLEARED }

var wave: RpgArcadeWave = RpgArcadeWave.new()
var state: int = State.WAITING

var _factory: Callable = Callable()
var _parent: Node = null
var _middle := Vector2.ZERO
var _offsets := PackedVector2Array()
var _made := 0
var _alive := 0
var _since := 0.0

func is_waiting() -> bool:
	return state == State.WAITING

func is_cleared() -> bool:
	return state == State.CLEARED

## How many enemies of the wave are in the stage now.
func alive() -> int:
	return _alive

## True when the trigger of the wave has come. `cleared_ids` holds the ids of the cleared waves.
func should_trigger(progress: float, time_s: float, cleared_ids: Dictionary) -> bool:
	if state != State.WAITING:
		return false
	match wave.trigger:
		"progress":
			return progress >= wave.at
		"time":
			return time_s >= wave.at
		"after":
			return cleared_ids.has(wave.after)
	return true

## Starts the wave: its enemies are made by `factory` (wave -> Node2D), added to `parent` and
## placed around `middle`. With an interval the first one comes now and the others in advance().
func trigger(middle: Vector2, factory: Callable, parent: Node) -> void:
	if state != State.WAITING:
		return
	state = State.SPAWNING
	_factory = factory
	_parent = parent
	_middle = middle
	_offsets = RpgArcadeWave.offsets(wave.formation, wave.count, wave.gap)
	_since = 0.0
	triggered.emit()
	_spawn_one()
	if wave.interval <= 0.0:
		while state == State.SPAWNING:
			_spawn_one()

## One step: the enemies that are still to come, one every `interval` seconds.
func advance(delta: float) -> void:
	if state != State.SPAWNING or wave.interval <= 0.0:
		return
	_since += delta
	while state == State.SPAWNING and _since >= wave.interval:
		_since -= wave.interval
		_spawn_one()

func _spawn_one() -> void:
	var index := _made
	_made += 1
	var made: Variant = _factory.call(wave) if _factory.is_valid() else null
	var enemy: Node2D = null
	if made is Node2D:
		enemy = made
	if enemy != null and _parent != null:
		_alive += 1
		enemy.position = _middle + _offsets[index]
		enemy.tree_exited.connect(_on_gone)
		if enemy.has_signal(&"defeated"):
			enemy.connect(&"defeated", _on_defeated.bind(enemy))
		_parent.add_child(enemy)
		spawned.emit(enemy)
	if _made >= wave.count:
		state = State.ACTIVE
		_check_cleared()

func _on_defeated(enemy: Node2D) -> void:
	var own: Variant = enemy.get(&"points") if is_instance_valid(enemy) else null
	enemy_defeated.emit(RpgUtil.to_int(own, wave.points) if own != null else wave.points)

func _on_gone() -> void:
	_alive = maxi(0, _alive - 1)
	_check_cleared()

func _check_cleared() -> void:
	if state == State.ACTIVE and _alive == 0:
		state = State.CLEARED
		cleared.emit()
