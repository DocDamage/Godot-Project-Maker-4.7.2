class_name RpgRacingMode
extends RpgArcadeMode
## The combat mode of a racing game: the arcade run (RpgArcadeMode) with a car and a race. A
## track is a stage; when it is entered its race is set up with the cars of the track and
## counted down, and when the player has driven its laps the place it came in is worth points
## and the track is over. The parts the player has won (`speed`, `tyres`, `acceleration`,
## three levels each) stay for the run and are kept in its save.

## The points of a place, the first first.
const PLACE_POINTS: Array[int] = [3000, 1800, 1000, 500, 250, 100]

## The player's car on the track that is driven, or null.
var car: RpgCar = null
## The race of that track, or null (a track without one).
var race: RpgRace = null
## The place the player came in at in the race that has just ended (0: none yet).
var last_place := 0

func bind_stage(next: RpgArcadeStage) -> void:
	car = _find_car(next)
	race = next.get_node_or_null("Race") as RpgRace
	last_place = 0
	super.bind_stage(next)
	_fit_parts()
	if race == null:
		return
	var all: Array[RpgCar] = []
	for node in next.find_children("*", "CharacterBody2D", true, false):
		if node is RpgCar:
			all.append(node as RpgCar)
	race.setup(stages().current(), all)
	if not race.finished.is_connected(_on_race_finished):
		race.finished.connect(_on_race_finished)
		race.part_taken.connect(_on_part_taken)
	race.begin()

## The race that is run now: null between two tracks, when the one of the last is gone.
func current_race() -> RpgRace:
	return race if race != null and is_instance_valid(race) else null

func _find_car(inside: Node) -> RpgCar:
	for node in inside.find_children("*", "CharacterBody2D", true, false):
		if node is RpgCar and (node as RpgCar).is_player:
			return node as RpgCar
	return null

## The level of a part (0 to 3). The parts are kept as text in the run's `weapon`, which the
## arcade run saves: "speed=1;tyres=0;acceleration=2".
func part_level(part: String) -> int:
	for entry in weapon.split(";", false):
		var pair := entry.split("=")
		if pair.size() == 2 and pair[0] == part:
			return clampi(pair[1].to_int(), 0, RpgCarPhysics.PART_LEVELS)
	return 0

## One more level of a part, up to three. True when it was added.
func add_part(part: String) -> bool:
	if not RpgRacePickup.PARTS.has(part) or part_level(part) >= RpgCarPhysics.PART_LEVELS:
		return false
	var levels := PackedStringArray()
	for other in RpgRacePickup.PARTS:
		levels.append("%s=%d" % [other, part_level(other) + (1 if other == part else 0)])
	weapon = ";".join(levels)
	_fit_parts()
	_store_run()
	return true

## Gives the player's car what its parts make of it.
func _fit_parts() -> void:
	if car == null or not is_instance_valid(car):
		return
	car.top_mul = RpgCarPhysics.part_factor("speed", part_level("speed"))
	car.accel_mul = RpgCarPhysics.part_factor("acceleration", part_level("acceleration"))
	car.grip_mul = RpgCarPhysics.part_factor("tyres", part_level("tyres"))

func _on_part_taken(kind: String) -> void:
	if add_part(kind):
		pickup(500)

func _on_race_finished(standings: Array) -> void:
	for raw: Variant in standings:
		var entry: Dictionary = raw
		if RpgUtil.to_bool(entry.get("player", false)):
			last_place = RpgUtil.to_int(entry.get("place", 0))
	if last_place >= 1:
		pickup(PLACE_POINTS[mini(last_place, PLACE_POINTS.size()) - 1])
	if stage != null and is_instance_valid(stage):
		stage.finish()
