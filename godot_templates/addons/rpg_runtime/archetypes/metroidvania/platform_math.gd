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

## One step of a pendulum: `angle` (rad, from straight down, to the right is positive) and
## `omega` (rad/s) of a body on a rope of `length` px under `gravity_px`. Half of the step's pull
## before the move and half after, as a jump is stepped. Returns Vector2(angle, omega).
static func swing_step(angle: float, omega: float, length: float, gravity_px: float, delta: float) -> Vector2:
	if length <= 0.0:
		return Vector2(angle, 0.0)
	var pull := gravity_px / length
	omega -= pull * sin(angle) * delta * 0.5
	angle += omega * delta
	omega -= pull * sin(angle) * delta * 0.5
	return Vector2(angle, omega)

## The time of one whole swing (there and back) let go at rest at `amplitude` rad: the small
## swing's 2π√(L/g), longer for a wide one (over the arithmetic-geometric mean of 1 and
## cos(amplitude / 2)). rpggen works out the same number (stage_plan.swing_period).
static func swing_period(length: float, gravity_px: float, amplitude: float) -> float:
	if length <= 0.0 or gravity_px <= 0.0:
		return 0.0
	var a := 1.0
	var b := cos(amplitude * 0.5)
	for i in 24:
		var mean := (a + b) * 0.5
		b = sqrt(a * b)
		a = mean
	return TAU * sqrt(length / gravity_px) / a

## The time of one whole swing stepped at `delta` the way the grapple steps it.
static func simulate_swing(length: float, gravity_px: float, amplitude: float, delta: float) -> float:
	var state := Vector2(amplitude, 0.0)
	var time := 0.0
	var crossings: Array[float] = []
	while time < 60.0 and crossings.size() < 3:
		var before := state.x
		state = swing_step(state.x, state.y, length, gravity_px, delta)
		if before != 0.0 and signf(before) != signf(state.x):
			crossings.append(time + delta * absf(before) / absf(before - state.x))
		time += delta
	return crossings[2] - crossings[0] if crossings.size() == 3 else 0.0

## How fast (px/s, along its path) a body on a rope of `length` px swings through the lowest
## point when it was let go at rest at `amplitude` rad.
static func swing_speed(length: float, gravity_px: float, amplitude: float) -> float:
	return sqrt(maxf(0.0, 2.0 * gravity_px * length * (1.0 - cos(amplitude))))
