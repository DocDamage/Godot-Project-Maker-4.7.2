class_name RpgShmupBomb
extends Node
## The ship's bombs: a count, and a blast that takes every enemy bullet off the screen and hurts
## everything on it.

signal used(bullets_cleared: int, targets_hit: int)
signal changed(count: int)

const MAX_BOMBS := 9

@export var start_count: int = 3
@export var damage: int = 20
## The sound slot of the blast.
@export var sound: StringName = &"sfx_bomb"

var count := 3

func _ready() -> void:
	count = start_count

## A new life: the starting bombs again.
func refill() -> void:
	count = start_count
	changed.emit(count)

## One more (a power-up), up to MAX_BOMBS. True when it was taken.
func add() -> bool:
	if count >= MAX_BOMBS:
		return false
	count += 1
	changed.emit(count)
	return true

## The blast. Every enemy bullet of `pool` is gone, and every target inside `view` (in the
## coordinates of the pool; an empty one means everywhere) takes `damage`. False without a bomb.
func use(pool: RpgShmupBulletPool, view: Rect2 = Rect2()) -> bool:
	if count <= 0:
		return false
	count -= 1
	changed.emit(count)
	var cleared := pool.clear(RpgShmupBulletPool.Team.ENEMY) if pool != null else 0
	var hit := 0
	if pool != null and pool.is_inside_tree():
		for node in pool.get_tree().get_nodes_in_group(RpgShmupBulletPool.TARGET_GROUP):
			if not (node is Node2D) or not node.has_method(&"take_hit"):
				continue
			var target := node as Node2D
			if view.size != Vector2.ZERO and not view.has_point(pool.to_local(target.global_position)):
				continue
			target.call(&"take_hit", damage)
			hit += 1
	var router := RpgUtil.router()
	if router != null and router.audio != null:
		router.audio.call(&"play", sound)
	used.emit(cleared, hit)
	return true
