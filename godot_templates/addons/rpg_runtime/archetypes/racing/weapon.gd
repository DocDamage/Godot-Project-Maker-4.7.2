class_name RpgRaceWeapon
extends Node2D
## What a car fires in a race. A **missile** flies the way the car pointed and makes the first
## other car it meets spin; a **bomb** is dropped behind the car and waits for a car to drive
## over it. A shield takes either. The race moves them (`advance`) and gives them the cars.

const MISSILE := "missile"
const BOMB := "bomb"
## Tiles a second, and how long each lasts.
const MISSILE_TILES := 26.0
const MISSILE_S := 1.6
const BOMB_S := 12.0
## A bomb does not go off under the car that dropped it: it is armed a moment later.
const BOMB_ARM_S := 0.5

var kind := MISSILE
var tile := 16.0
var velocity := Vector2.ZERO
var life_s := 0.0
var age_s := 0.0
## The car that fired it (its instance id): a missile never hits it.
var owner_id := 0
var done := false

## A weapon of `kind` fired by `car` (a Node2D with `heading`), not yet in the scene.
static func fired(by: Node2D, which: String, tile_px: float) -> RpgRaceWeapon:
	var made := RpgRaceWeapon.new()
	made.kind = which
	made.tile = tile_px
	made.owner_id = by.get_instance_id()
	var way := Vector2.from_angle(RpgUtil.to_float(by.get(&"heading")))
	if which == BOMB:
		made.position = by.position - way * tile_px * 1.2
		made.life_s = BOMB_S
	else:
		made.position = by.position + way * tile_px * 1.2
		made.velocity = way * MISSILE_TILES * tile_px
		made.life_s = MISSILE_S
		made.rotation = way.angle()
	made.z_index = 4
	return made

func radius() -> float:
	return tile * (0.9 if kind == BOMB else 0.7)

## One step: it moves, and the first car in reach is hit. `cars` are Node2Ds with `hit()`.
func advance(delta: float, cars: Array) -> void:
	if done:
		return
	age_s += delta
	position += velocity * delta
	if age_s >= life_s:
		done = true
		return
	if kind == BOMB and age_s < BOMB_ARM_S:
		return
	for entry: Variant in cars:
		if not (entry is Node2D) or not is_instance_valid(entry):
			continue
		var car: Node2D = entry
		if kind == MISSILE and car.get_instance_id() == owner_id:
			continue
		if car.position.distance_to(position) <= radius():
			car.call(&"hit")
			done = true
			return

func _draw() -> void:
	if kind == BOMB:
		draw_circle(Vector2.ZERO, tile * 0.3, Color(0.1, 0.1, 0.12))
		draw_circle(Vector2.ZERO, tile * 0.12, Color(0.9, 0.3, 0.2))
	else:
		draw_rect(Rect2(-tile * 0.4, -tile * 0.12, tile * 0.8, tile * 0.24), Color(0.95, 0.85, 0.3))
