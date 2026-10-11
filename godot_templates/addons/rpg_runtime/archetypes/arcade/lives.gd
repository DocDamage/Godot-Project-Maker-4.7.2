class_name RpgArcadeLives
extends Node
## The lives of an arcade run: one is lost with every death, one is gained every `extra_every`
## points, and the game is over when none is left.

signal changed(count: int)
signal extra_life
signal game_over

const MAX_LIVES := 9

@export var start_lives: int = 3
## An extra life at every multiple of this score; 0 gives none.
@export var extra_every: int = 20000

var count := 3
## How many extra lives the score has paid for already.
var _awarded := 0

func _ready() -> void:
	count = start_lives

## A new run, or a continue: the starting lives. `points` is the score the run goes on with, so a
## continue does not hand out again what that score has already paid for.
func reset(points: int = 0) -> void:
	count = start_lives
	_awarded = _steps(points)
	changed.emit(count)

## Called by a load.
func restore(saved: int, points: int) -> void:
	count = clampi(saved, 0, MAX_LIVES)
	_awarded = _steps(points)
	changed.emit(count)

func _steps(points: int) -> int:
	if extra_every <= 0:
		return 0
	@warning_ignore("integer_division")
	return points / extra_every

## One more life (a power-up), up to MAX_LIVES. True when it was given.
func gain() -> bool:
	if count >= MAX_LIVES:
		return false
	count += 1
	changed.emit(count)
	extra_life.emit()
	return true

## A life is lost. True when it was the last one (game_over is emitted).
func lose() -> bool:
	if count <= 0:
		return true
	count -= 1
	changed.emit(count)
	if count == 0:
		game_over.emit()
		return true
	return false

## The score changed: an extra life for every step of `extra_every` it has passed.
func on_score(points: int) -> void:
	while _steps(points) > _awarded:
		_awarded += 1
		if count < MAX_LIVES:
			count += 1
			changed.emit(count)
			extra_life.emit()
