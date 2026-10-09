class_name RpgPlatformMath
extends RefCounted
## Pure formulas of the side-view movement. A jump is described by how high it goes and how long
## it takes to get there; gravity and the take-off speed follow from those two.

## Lengths are written for 16 px tiles and scaled by tile_size / 16.
const BASE_TILE := 16.0
## A jump released early keeps this much of its upward speed.
const JUMP_CUT := 0.5
## Sliding down a wall: this much of the fastest fall.
const WALL_SLIDE_FACTOR := 0.3
const LADDER_SPEED := 70.0
## Seconds a drop through a one-way platform ignores it.
const DROP_THROUGH_S := 0.2
## Touching a hazard.
const HAZARD_DAMAGE := 1
const HAZARD_INVULN_S := 0.6
const HAZARD_RETURN_S := 0.3
## A cell is safe ground after standing on it this long.
const SAFE_GROUND_S := 0.25

## 2h / t²: the gravity that brings a jump of height `height` to its peak after `time_to_peak`.
static func gravity(height: float, time_to_peak: float) -> float:
	return 2.0 * height / (time_to_peak * time_to_peak) if time_to_peak > 0.0 else 0.0

## 2h / t: the upward speed at take-off.
static func jump_speed(height: float, time_to_peak: float) -> float:
	return 2.0 * height / time_to_peak if time_to_peak > 0.0 else 0.0

## How high a body rises that leaves the ground at `speed` under `gravity_px`.
static func apex(speed: float, gravity_px: float) -> float:
	return speed * speed / (2.0 * gravity_px) if gravity_px > 0.0 else 0.0

## The vertical speed after one step of `delta` under `gravity_px`, never faster than `max_fall`.
## The actor adds half of the step before it moves and half after, so a jump follows its parabola
## whatever the frame rate.
static func fall_step(speed: float, gravity_px: float, delta: float, max_fall: float) -> float:
	return minf(speed + gravity_px * delta, max_fall)

## The peak (px above the start) of a jump stepped at `delta` the way the actor steps it. With
## `release_at` >= 0 the jump button is let go after that many seconds and the rise is cut.
static func simulate_jump(height: float, time_to_peak: float, delta: float, release_at: float = -1.0, fall_mul: float = 1.0, max_fall: float = 100000.0) -> float:
	var g := gravity(height, time_to_peak)
	var speed := -jump_speed(height, time_to_peak)
	var y := 0.0
	var peak := 0.0
	var time := 0.0
	var cut := false
	while time < 10.0:
		if release_at >= 0.0 and not cut and time >= release_at and speed < 0.0:
			speed *= JUMP_CUT
			cut = true
		var pull := g * (fall_mul if speed > 0.0 else 1.0)
		speed = fall_step(speed, pull, delta * 0.5, max_fall)
		y += speed * delta
		speed = fall_step(speed, pull, delta * 0.5, max_fall)
		peak = maxf(peak, -y)
		time += delta
		if y >= 0.0 and speed > 0.0:
			break
	return peak

## How far a dash carries: `speed` for `seconds`.
static func dash_distance(speed: float, seconds: float) -> float:
	return speed * seconds

## The cell of `tile` px that holds a point.
static func cell_of(point: Vector2, tile: float) -> Vector2i:
	return Vector2i(floori(point.x / tile), floori(point.y / tile)) if tile > 0.0 else Vector2i.ZERO
