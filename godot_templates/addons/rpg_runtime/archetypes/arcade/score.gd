class_name RpgArcadeScore
extends Node
## The score of an arcade run: points for kills and pickups, and a multiplier that grows with
## kills in a row and is back at 1 when the player is hit.

signal changed(points: int, multiplier: int)

const MAX_MULTIPLIER := 8

## This many kills without being hit raise the multiplier by one.
@export var kills_per_step: int = 5

var points := 0
var multiplier := 1
## Kills since the last hit.
var streak := 0

## A new run: nothing scored.
func reset() -> void:
	points = 0
	reset_multiplier()

## Back to x1 (a hit, a continue). The points stay.
func reset_multiplier() -> void:
	streak = 0
	multiplier = 1
	changed.emit(points, multiplier)

## Called by a load: the points of the saved run, at x1.
func restore(saved_points: int) -> void:
	points = maxi(0, saved_points)
	reset_multiplier()

## A kill worth `value`: counted with the multiplier, and it feeds the streak. Returns the points
## gained.
func add_kill(value: int) -> int:
	var gained := maxi(0, value) * multiplier
	points += gained
	streak += 1
	if kills_per_step > 0 and streak % kills_per_step == 0:
		multiplier = mini(MAX_MULTIPLIER, multiplier + 1)
	changed.emit(points, multiplier)
	return gained

## A pickup worth `value`: counted with the multiplier, without feeding the streak.
func add_pickup(value: int) -> int:
	var gained := maxi(0, value) * multiplier
	points += gained
	changed.emit(points, multiplier)
	return gained

## A bonus (the tally of a cleared stage): as it is.
func add_bonus(value: int) -> void:
	points += maxi(0, value)
	changed.emit(points, multiplier)

## The player was hit: the streak is gone.
func hit() -> void:
	reset_multiplier()
