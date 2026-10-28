extends RefCounted
## T18.19: the people of a race: the drivers beside their cars until the lights, their names
## and faces on the screens, the marshal, the spectators along the straights, and the podium.

const Fixtures := preload("../lib/fixtures.gd")
const CarRecipe := preload("res://builder/recipes/racing/car_recipe.gd")

const TILE := 16
const LOOP := {
	"laps": 2,
	"start": {"position": [60.0, 0.0], "heading": 0.0, "line": [100.0, 0.0]},
	"checkpoints": [{"id": "c01", "position": [300.0, 0.0], "heading": 0.0, "width": 100.0}],
	"waypoints": [{"position": [200.0, 0.0], "speed": 12.0}],
	# a wall along the top (a straight: 20 cells long, one wide), a block that is no straight
	"barriers": [[0, -3, 20, 1], [5, 5, 3, 3]],
}
const FRAMES_PATH := "user://test_race_people_frames.tres"

func _data_file(file_name: String, data: Dictionary) -> String:
	var path := "user://" + file_name
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data))
	f.close()
	return path

## A person's frames: a 6x10 picture standing.
func _frames() -> String:
	var picture := Image.create(6, 10, false, Image.FORMAT_RGBA8)
	picture.fill(Color.ORANGE)
	var frames := SpriteFrames.new()
	frames.add_animation(&"idle_down")
	frames.add_frame(&"idle_down", ImageTexture.create_from_image(picture))
	ResourceSaver.save(frames, FRAMES_PATH)
	return FRAMES_PATH

func _drivers(frames: String) -> Dictionary:
	return {
		"drivers": [
			{"id": "player", "name": "", "frames": frames, "portrait": {}, "colour": [1.0, 0.85, 0.3]},
			{"id": "rival_1", "name": "Greta", "frames": "", "portrait": {}, "colour": [0.45, 0.6, 1.0]},
			{"id": "rival_2", "name": "Otto", "frames": frames, "portrait": {}, "colour": [0.5, 0.95, 0.5]},
		],
		"people": [frames],
	}

class Field:
	var root: Node2D
	var race: RpgRace
	var people: RpgRacePeople
	var cars: Array[RpgCar] = []

	func run(steps: int) -> void:
		for i in steps:
			race.advance(1.0 / 60.0)
			people._process(1.0 / 60.0)

	func drop() -> void:
		RpgRacePeople.data_path = RpgRacePeople.DATA_PATH
		root.get_parent().remove_child(root)
		root.free()

func _field(data_path: String) -> Field:
	await Fixtures.tree().process_frame
	RpgRacePeople.data_path = data_path
	var field := Field.new()
	field.root = Node2D.new()
	for i in 3:
		var car := CarRecipe.build_car(null, Vector2i(24, 24), 1, TILE, i == 0) as RpgCar
		car.name = "Player" if i == 0 else "Rival%d" % i
		car.input_node_enabled = false
		car.position = Vector2(60, 24.0 * i)
		car.heading = 0.0
		field.root.add_child(car)
		car.set_physics_process(false)
		field.cars.append(car)
	field.race = RpgRace.new()
	field.race.name = "Race"
	field.race.auto_advance = false
	field.race.countdown_s = 3.0
	field.root.add_child(field.race)
	Fixtures.tree().root.add_child(field.root)
	field.race.setup(LOOP, field.cars)
	field.race.begin()
	field.people = RpgRacePeople.new()
	field.root.add_child(field.people)
	field.people.setup(field.race, LOOP)
	return field

func test_the_drivers_stand_at_their_cars_until_the_lights(t) -> void:
	var field := await _field(_data_file("test_race_people_a.json", _drivers(_frames())))
	var people := field.people
	t.eq(people.drivers.size(), 3, "a driver for every car")
	t.ok(people.drivers_standing(), "they stand before the start")
	for i in 3:
		var person := people.drivers[i]
		t.near(person.position.distance_to(field.cars[i].position), TILE * 0.9, 0.5, "beside its car")
	t.ok(people.drivers[0] is AnimatedSprite2D, "the player's driver is the pack's person")
	t.ok(not (people.drivers[1] is AnimatedSprite2D), "a driver without a person is drawn")
	t.eq((people.drivers[1].get_child(0) as Polygon2D).color, Color(0.45, 0.6, 1.0), "in the colour of its car")
	t.eq(people.find_children("*", "CollisionObject2D", true, false).size(), 0, "nobody blocks the track")
	field.run(30)
	t.ok(people.drivers_standing(), "three: still out")
	field.run(60)
	t.ok(people.drivers.all(func(p: Node2D) -> bool: return not p.visible), "the lights begin: they get in")
	field.drop()

func test_the_drivers_have_names_and_faces(t) -> void:
	var field := await _field(_data_file("test_race_people_b.json", _drivers(_frames())))
	t.eq(RpgChampionship.driver_name("rival_1"), "Greta")
	t.eq(RpgChampionship.driver_name("rival_2"), "Otto")
	t.eq(RpgChampionship.driver_name("player"), RpgRacingStrings.t("RACE_DRIVER_YOU"), "the player is the player")
	t.ok(RpgRacePeople.portrait_of("player") != null, "a face from the first standing frame")
	t.eq(RpgRacePeople.portrait_of("rival_1"), null, "none without a person")
	var screen := RpgRaceResults.new()
	Fixtures.tree().root.add_child(screen)
	var rows: Array[Dictionary] = [
		{"driver": "rival_2", "place": 1, "finished": true, "time_s": 60.0, "points": 10, "total": 10},
		{"driver": "player", "place": 2, "finished": true, "time_s": 61.0, "points": 6, "total": 6, "player": true},
	]
	screen.show_results("Track", rows, [], rows)
	var lines := screen.grid_texts("Race")
	t.eq([lines[0][1], lines[1][1]], ["Otto", RpgRacingStrings.t("RACE_DRIVER_YOU")], "the standings name them")
	t.ok(screen.find_child("Portrait", true, false) is TextureRect, "with the faces beside")
	screen.free()
	field.drop()

func test_a_rivals_driving_differs_a_little_by_its_driver(t) -> void:
	var field := await _field(_data_file("test_race_people_c.json", _drivers("")))
	var greta := RpgRacePeople.skill_of(0.7, "rival_1")
	t.ok(absf(greta - 0.7) <= RpgRacePeople.SKILL_SPREAD + 0.0001, "a little")
	t.eq(RpgRacePeople.skill_of(0.7, "rival_1"), greta, "the same driver drives the same way")
	t.eq(RpgRacePeople.skill_of(0.7, "player"), 0.7, "no name: as before")
	field.drop()

func test_the_marshal_waves_and_the_spectators_cheer(t) -> void:
	var field := await _field(_data_file("test_race_people_d.json", _drivers(_frames())))
	var people := field.people
	t.ok(people.marshal != null, "a marshal")
	t.near(absf(people.marshal.position.y), 50.0 + TILE, 0.5, "beside the start line")
	var spots := RpgRacePeople.spectator_spots(LOOP, TILE)
	t.eq(spots.size(), 4, "along the straight, none on the block")
	t.eq(people.spectators.size(), 4)
	t.ok(spots.all(func(p: Vector2) -> bool: return is_equal_approx(p.y, -2.5 * TILE)), "on the wall")
	var heights := {}
	for i in 40:
		field.run(1)
		heights[people.spectators[0].position.y] = true
	t.eq(heights.size(), 2, "a bob of two steps")
	field.run(200)  # past the countdown: the start
	var waved := {}
	for i in 30:
		field.run(1)
		waved[people.marshal.position.y] = true
	t.eq(waved.size(), 2, "the marshal waves the start")
	field.drop()

func test_the_podium_has_the_first_three(t) -> void:
	var field := await _field(_data_file("test_race_people_e.json", _drivers(_frames())))
	var top: Array[String] = ["rival_2", "player", "rival_1"]
	var podium := field.people.show_podium(top)
	t.eq(podium.size(), 3)
	t.eq(podium.map(func(p: Node2D) -> String: return RpgUtil.to_str(p.get_meta(&"driver"))), ["rival_2", "player", "rival_1"])
	t.ok(podium[0].position.y < podium[1].position.y and podium[1].position.y < podium[2].position.y, "the first highest")
	field.drop()

func test_a_race_without_the_option_has_no_people(t) -> void:
	var field := await _field("user://test_race_people_none.json")
	t.eq(field.people.get_child_count(), 0)
	t.eq(RpgChampionship.driver_name("rival_1"), RpgRacingStrings.t("RACE_DRIVER_RIVAL", [1]), "named as before")
	field.drop()
