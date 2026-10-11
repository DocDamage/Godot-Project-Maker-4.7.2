class_name RpgRacingMode
extends RpgArcadeMode
## The combat mode of a racing game: the arcade run (RpgArcadeMode) with a car. A track is a
## stage; it is over when its race says so (`stage.finish()`).

## The player's car on the track that is driven, or null.
var car: RpgCar = null

func bind_stage(next: RpgArcadeStage) -> void:
	car = _find_car(next)
	super.bind_stage(next)

func _find_car(inside: Node) -> RpgCar:
	for node in inside.find_children("*", "CharacterBody2D", true, false):
		if node is RpgCar and (node as RpgCar).is_player:
			return node as RpgCar
	return null
