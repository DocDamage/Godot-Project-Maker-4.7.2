extends RefCounted
## The farm's smoke sequence (T17.04 to T17.09). A farm's game starts in its farmhouse, not in
## the village, so the sequence is the farm's own: it takes the shared top-down steps
## (smoke_steps_m6.gd) and runs them where they belong, in the village.
##
## New Game opens the farmhouse, the farmer by the bed -> it walks out of the door onto the
## farm -> through the way out into the village -> **the shared steps**, in the village (the
## demo's villager, the chest, the house, saving, the shop, the pause menu) -> a villager is
## where its schedule says at two times of the day (the calendar is moved on) -> a talk, then
## a gift of the held item with `interact`, and the points and the People page show both ->
## back to the farm through the village's door -> the farm is the plan's: its tillable cells
## are the ones the plan lists -> the can is filled at the water with `use` and with
## `interact` -> a thing is cleared with the tool that clears it -> a cell is tilled, planted
## and watered with the real input actions (`hotbar_<n>` chooses, `use` works) -> a night
## passes and the crop is a day further -> the nights to ripeness -> the crop is picked with
## `interact` -> it is put into the shipping bin beside the house, taken back out and put in
## again -> the farmer walks into the house and sleeps in the bed (`interact`): the day ends
## once, the energy is full, the game is saved -> the morning's summary names the crop and
## what it earned, and `confirm` closes it -> the shop is closed before 9:00 and on its closed
## day, and sells the seeds of the season in its hours -> the weather and the HUD (T17.11) ->
## a thing that lies at one of the farm's forage places is picked up with `interact`, and on a
## farm with a pond the rod is cast with `use` and the fish landed with `use` held as the bar
## asks (T17.10) -> the animals (T17.07) -> the game is saved, everything a save holds of a farm
## is changed (a night passes, soil is tilled, a crop is cut, money, the bag, a friendship, the
## herd), and the game is loaded: the field is what it was cell by cell, and the date, the
## money, the bag, the herd, the friendships and the energy with it (T17.18).
##
## Before that last step, festivals and birthdays (T17.25): the calendar on the wall of the
## farmhouse is read with `interact` -> the next birthday is waited for and its gift counts
## five times -> the day before a festival the sign by the house says so -> a year is run by
## ending days, every festival on its day and on no other -> the egg hunt is played in the
## village, the people on the square and the shop closed. The last step keeps their state too.
##
## Then marriage (T17.26): the bouquet and the pendant are bought at the shop -> a person who
## can be courted is courted with the bouquet held and `interact` -> asked with the pendant ->
## the days to the wedding are ended, and on its day the one to be married stands on the square
## -> its night is ended with crops on the plot -> the next morning part of the plot is watered
## and the spouse is at home in the farmhouse. The last step keeps the marriage's state too.
##
## The nights of the growing are the calendar's `end_day()`, run in full (a day that nobody
## slept through); the night after the harvest is slept in the bed.
##
## **The map is asked, not the screen** (T17.14), so the same steps play a farm of squares and
## an isometric one, with either setting of `iso_controls`: a walk through a door walks to the
## door (SmokeMap.walk_toward; on squares that holds the one key the step used to hold), the
## farmer is turned to the cell it works on (RpgFarmer.face_cell; on squares that is the facing
## the step used to set), it stands where its interaction reaches what it talks to
## (RpgIso.reach_dir; straight below it on squares), and "inside the yard" is asked of the
## yard's cells.

## What a failed step of this sequence is reported as (docs/spec/03_ERROR_CODES.md).
const CODE := "SMOKE-013"

const JsonUtil := preload("../lib/json_util.gd")
const SmokeMap := preload("smoke_map.gd")
## The addon's smoke runner: it knows the folder this run saves into (a run's own).
const SmokeRunner := preload("res://addons/rpg_runtime/debug/smoke_runner.gd")

const HOUSE := "FarmHouse"
const FARM := "Farm"
const VILLAGE := "StarterMap"
const PLAN_PATH := "res://rpggen/world_plan.json"
## The hours a villager is looked for at: by day, and in the evening.
const HOURS: Array[int] = [11, 21]

var _shared := preload("smoke_steps_m6.gd").new()
var _box := {}  # values remembered between steps

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	_shared.start_map = HOUSE
	var shared: Array[Dictionary] = _shared.steps()
	var list: Array[Dictionary] = [shared[0]]  # title_new_game
	list.append_array([
		_step("wake_in_the_house", _wake_in_the_house, 20.0),
		_step("walk_out_of_the_house", _walk_out_of_the_house, 30.0),
		_step("go_to_the_village", _go_to_the_village, 30.0),
	])
	list.append_array(shared.slice(1))  # the shared top-down steps, in the village
	list.append_array([
		_step("villager_by_the_clock", _villager_by_the_clock, 60.0),
		_step("give_a_gift", _give_a_gift, 60.0),
		_step("back_to_the_farm", _back_to_the_farm, 30.0),
		_step("farm_is_there", _farm_is_there, 20.0),
		_step("fill_the_can", _fill_the_can, 30.0),
		_step("clear_debris", _clear_debris, 30.0),
		_step("till_a_cell", _till_a_cell, 20.0),
		_step("plant_a_seed", _plant_a_seed, 20.0),
		_step("water_it", _water_it, 20.0),
		_step("a_night_grows_it", _a_night_grows_it, 20.0),
		_step("crop_ripens", _crop_ripens, 30.0),
		_step("harvest", _harvest, 30.0),
		_step("ship_the_crop", _ship_the_crop, 30.0),
		_step("sleep_in_the_bed", _sleep_in_the_bed, 60.0),
		_step("morning_summary", _morning_summary, 30.0),
		_step("buy_seeds_at_the_shop", _buy_seeds_at_the_shop, 40.0),
		# the weather and the HUD (T17.11): they stand on their own, after everything else
		_step("rain_waters_the_field", _rain_waters_the_field, 40.0),
		_step("hud_shows_the_day", _hud_shows_the_day, 20.0),
		_step("season_turns", _season_turns, 90.0),
		# fishing and foraging (T17.10): they stand on their own too
		_step("forage_on_the_farm", _forage_on_the_farm, 40.0),
		_step("catch_a_fish", _catch_a_fish, 90.0),
		# the animals (T17.07): only in a farm with an animal house, else each passes with a note
		_step("buy_a_hen", _buy_a_hen, 60.0),
		_step("hen_in_the_coop", _hen_in_the_coop, 60.0),
		_step("feed_at_the_trough", _feed_at_the_trough, 40.0),
		_step("pet_the_hen", _pet_the_hen, 40.0),
		_step("egg_in_the_morning", _egg_in_the_morning, 60.0),
		_step("ship_the_egg", _ship_the_egg, 40.0),
		# the added maps (T17.23): only in a farm that has a forest or a beach, else each passes
		# with a note
		_step("visit_the_forest", _visit_the_forest, 120.0),
		_step("fish_at_the_beach", _fish_at_the_beach, 180.0),
		# the cave (T17.24): only in a farm that fights, else each passes with a note
		_step("buy_a_weapon", _buy_a_weapon, 120.0),
		_step("enter_the_cave", _enter_the_cave, 120.0),
		_step("defeat_an_enemy", _defeat_an_enemy, 90.0),
		_step("bring_back_what_it_left", _bring_back_what_it_left, 90.0),
		_step("defeated_and_wake_at_home", _defeated_and_wake_at_home, 120.0),
		# festivals and birthdays (T17.25): only in a farm that has them, else each passes with a
		# note. They end on the morning of the egg hunt, in spring, where the last step finds crops
		_step("read_the_calendar", _read_the_calendar, 60.0),
		_step("birthday_gift", _birthday_gift, 180.0),
		_step("festival_is_announced", _festival_is_announced, 180.0),
		_step("a_year_of_festivals", _a_year_of_festivals, 300.0),
		_step("egg_hunt", _egg_hunt, 120.0),
		# marriage (T17.26): only in a farm with somebody to court, else each passes with a note
		_step("buy_a_bouquet", _buy_a_bouquet, 120.0),
		_step("court_with_a_bouquet", _court_with_a_bouquet, 60.0),
		_step("propose_with_a_pendant", _propose_with_a_pendant, 60.0),
		_step("the_wedding", _the_wedding, 120.0),
		_step("spouse_at_home", _spouse_at_home, 60.0),
		# the last (T17.18): by now the field, the bag, the friendships and the herd hold something
		_step("save_and_load", _save_and_load, 90.0),
	])
	return list

func _step(step_name: String, fn: Callable, timeout_s: float) -> Dictionary:
	return {"name": step_name, "fn": fn, "timeout_s": timeout_s, "code": CODE}

# ---------------------------------------------------------------- helpers

func _farmer() -> RpgFarmer:
	var players := _tree().get_nodes_in_group("player")
	return players[0] as RpgFarmer if players.size() == 1 else null

func _state() -> RpgGameState:
	return RpgUtil.state()

func _frames(count: int) -> void:
	for i in count:
		await _tree().physics_frame

func _wait_for(check: Callable, frames: int) -> bool:
	for i in frames:
		if check.call():
			return true
		await _tree().physics_frame
	return check.call()

## Holds an action for a few frames (a "just pressed" is seen at least once).
func _tap(action: String) -> void:
	Input.action_press(action)
	await _frames(3)
	Input.action_release(action)
	await _frames(2)

## Chooses the slot of `item_id` with its number key. "" when it is held afterwards.
func _hold(item_id: StringName) -> String:
	var bar := RpgFarmMode.current().hotbar
	for i in RpgHotbar.SLOTS:
		if bar.item_at(i) == item_id:
			await _tap("hotbar_%d" % (i + 1))
			return "" if bar.held_item() == item_id else "hotbar_%d did not hold %s (held: %s)" % [i + 1, item_id, bar.held_item()]
	return "%s is not among the ten slots of the hotbar" % item_id

## Puts the farmer in the cell above the cell that is worked, looking down at it, and waits
## until it can act.
func _stand_at_cell() -> String:
	var farmer := _farmer()
	var field := RpgField.current()
	if farmer == null or field == null:
		return "the farmer or the field is gone"
	var cell: Vector2i = _box["cell"]
	farmer.global_position = field.cell_center(cell + Vector2i.UP)
	farmer.set_facing("down")
	farmer.face_cell(cell)  # down on squares; the neighbour to the south on diamonds
	await _frames(3)
	if not await _wait_for(func() -> bool: return not farmer.is_busy(), 120):
		return "the farmer never finished using its tool"
	if farmer.tile_ahead() != cell:
		return "the tile ahead is %s, expected %s" % [farmer.tile_ahead(), cell]
	return ""

func _crop() -> Dictionary:
	return RpgFarmMode.current().crops.crop(str(_box["crop"]))

# ---------------------------------------------------------------- steps

## The farm's map of the stored plan (`farm.map`), or {}.
func _plan() -> Dictionary:
	if not FileAccess.file_exists(PLAN_PATH):
		return {}
	var farm := JsonUtil.to_dict(JsonUtil.to_dict(JsonUtil.read(PLAN_PATH)).get("farm", {}))
	return JsonUtil.to_dict(farm.get("map", {}))

static func _cell(value: Variant) -> Vector2i:
	var pair := JsonUtil.to_array(value)
	return Vector2i(JsonUtil.to_int(pair[0]), JsonUtil.to_int(pair[1])) if pair.size() == 2 else Vector2i.ZERO

## Waits (physics frames) until the router is idle and the map `map_name` is shown.
func _wait_for_map(map_name: String, frames: int) -> bool:
	var tree := _tree()
	for i in frames:
		await tree.physics_frame
		var router := RpgUtil.router()
		var scene := tree.current_scene
		if router != null and not router.is_busy() and scene != null and scene.name == map_name:
			return true
	return false

## The spawn point `spawn_id` of the map that is shown, or null.
func _spawn(spawn_id: String) -> RpgSpawnPoint:
	var scene := _tree().current_scene
	for node in _tree().get_nodes_in_group("spawn_points"):
		var spawn := node as RpgSpawnPoint
		if spawn != null and scene != null and scene.is_ancestor_of(spawn) and String(spawn.spawn_id) == spawn_id:
			return spawn
	return null

## The door of the map that is shown that leads to the map file `file_name`, or null.
func _door_to(file_name: String) -> RpgDoor:
	var scene := _tree().current_scene
	if scene == null:
		return null
	for node in scene.find_children("*", "Area2D", true, false):
		var door := node as RpgDoor
		if door != null and door.target_map.get_file() == file_name:
			return door
	return null

## Puts the farmer at `from` and walks it to `to` (a door) until another map is shown; the map
## must then be `map_name`, and the farmer stand at its spawn `spawn_id`. "" when it does. The
## map is asked which way to hold the pad (T17.14): on squares, where `to` lies straight along
## an axis from `from`, it is the one key this step always held.
func _walk_to_map(from: Vector2, to: Vector2, map_name: String, spawn_id: String) -> String:
	var tree := _tree()
	var farmer := _farmer()
	if farmer == null:
		return "the farmer is gone"
	var before := tree.current_scene
	farmer.global_position = from
	await _frames(2)
	var router := RpgUtil.router()
	await SmokeMap.walk_toward(farmer, to, 240, func() -> bool: return tree.current_scene != before or router.is_busy())
	if not await _wait_for_map(map_name, 600):
		return "walking from %s to %s did not lead to %s" % [from, to, map_name]
	var spawn := _spawn(spawn_id)
	if spawn == null:
		return "%s has no spawn point '%s'" % [map_name, spawn_id]
	farmer = _farmer()
	if farmer == null or farmer.global_position.distance_to(spawn.global_position) > 20.0:
		return "the farmer did not arrive at '%s' of %s" % [spawn_id, map_name]
	return ""

## Walks out of the map that is shown through the gap of its edge whose door is `door_name`,
## from the spawn `spawn_id` before it, into `map_name` at its spawn `arrive`.
func _through_the_gap(door_name: String, spawn_id: String, map_name: String, arrive: String) -> String:
	var scene := _tree().current_scene
	var door := scene.find_child(door_name, true, false) as RpgDoor if scene != null else null
	var inside := _spawn(spawn_id)
	if door == null or inside == null:
		return "%s has no door '%s' with the spawn '%s' before it" % [scene.name if scene != null else "no map", door_name, spawn_id]
	if door.target_map == "" or not ResourceLoader.exists(door.target_map):
		return "the door '%s' leads to no map (%s)" % [door_name, door.target_map]
	return await _walk_to_map(inside.global_position, door.global_position, map_name, arrive)

# ---------------------------------------------------------------- the house and the way (T17.06)

func _wake_in_the_house() -> String:
	var scene := _tree().current_scene
	if scene == null or scene.name != HOUSE:
		return "a new game did not start in the farmhouse"
	if RpgFarmMode.current() == null:
		return "SceneRouter.combat is not the farm's mode"
	var calendar := RpgCalendar.current()
	if calendar == null or calendar.clock()[0] != 6:
		return "the game has no calendar, or the first morning is not at 6:00"
	var farmer := _farmer()
	if farmer == null:
		return "the player is not an RpgFarmer"
	var bed := scene.find_child("Bed", true, false) as RpgBed
	if bed == null:
		return "the farmhouse has no bed"
	if farmer.global_position.distance_to(bed.wake_position()) > 4.0:
		return "the farmer starts %.0f px from where it wakes, by the bed" % farmer.global_position.distance_to(bed.wake_position())
	var home := RpgBed.home(_state())
	if home.is_empty() or str(home.get("map", "")) != scene.scene_file_path:
		return "the bed of the house is not where the farmer wakes: %s" % home
	if RpgField.current() != null:
		return "the farmhouse has a field"
	if not (scene as RpgMapRoot).interior():
		return "the farmhouse is not an inside map"
	return ""

func _walk_out_of_the_house() -> String:
	var way_out := _door_to("farm.tscn")
	if way_out == null:
		return "the farmhouse has no door to the farm"
	# from the cell north of the way out (a tile above it on squares), down into it
	var failure: String = await _walk_to_map(way_out.global_position + SmokeMap.cells(Vector2(0.0, -1.0)), way_out.global_position, FARM, "farm_house_door")
	if failure != "":
		return failure
	if not str(_state().current_map).ends_with("farm.tscn"):
		return "the game does not know the farmer is on the farm (%s)" % _state().current_map
	return ""

func _go_to_the_village() -> String:
	var failure: String = await _through_the_gap("to_village", "from_village", VILLAGE, "from_farm")
	if failure != "":
		return failure
	if not str(_state().current_map).ends_with("starter_map.tscn"):
		return "the game does not know the farmer is in the village (%s)" % _state().current_map
	var scene := _tree().current_scene
	if RpgField.current() != null or scene.find_child("ShippingBin", true, false) != null or scene.find_child("Bed", true, false) != null:
		return "the village still has the field, the bin or the bed of the farm"
	# the shared steps begin where the game of another kind begins: in the middle of the
	# village, not before the gap the farmer came in by (the first of them walks to the right)
	var middle := _spawn("default")
	if middle == null:
		return "the village has no default spawn point"
	_farmer().global_position = middle.global_position
	await _frames(2)
	return ""

func _back_to_the_farm() -> String:
	var calendar := RpgCalendar.current()
	if calendar != null and _box.has("minute"):
		calendar.minute = JsonUtil.to_int(_box["minute"])  # the day goes on where it was
	return await _through_the_gap("to_farm", "from_farm", FARM, "from_village")

# ---------------------------------------------------------------- the people (T17.09)

func _person_node(person_id: String) -> RpgNpc:
	var scene := _tree().current_scene
	return scene.find_child("Person_%s" % person_id, true, false) as RpgNpc if scene != null else null

func _villager_by_the_clock() -> String:
	var scene := _tree().current_scene
	if scene == null or scene.name != VILLAGE:
		return "not in the village"
	var friends := RpgFriendship.current()
	var calendar := RpgCalendar.current()
	if friends == null or calendar == null:
		return "the game has no friendships"
	if friends.order.is_empty():
		return "game/data/people.json lists nobody"
	var npc: RpgNpc = null
	var id := ""
	for person_id in friends.order:
		var node := _person_node(person_id)
		if node == null:
			return "%s of people.json has no NPC in the village" % person_id
		if node.schedule() == null or not node.schedule().at_work():
			return "%s has no schedule at work" % person_id
		if RpgUtil.to_str(friends.person(person_id).get("scene", "")) != node.scene_file_path:
			return "%s is not the scene people.json names" % person_id
		if npc == null:
			npc = node
			id = person_id
	var schedule := npc.schedule()
	_box["minute"] = calendar.minute
	var seen: Array[String] = []
	for hour in HOURS:
		if hour * 60 <= calendar.minute:
			return "it is %s already: the steps before took the day" % [calendar.clock()]
		calendar.pass_minutes(hour * 60 - calendar.minute)
		var entry := schedule.entry_in_force()
		if entry.is_empty() or not schedule.here(entry):
			return "%s is not in the village at %d:00 (%s)" % [id, hour, entry]
		var at := schedule.place_position(entry)
		if not at.is_finite():
			return "the village has no place for %s" % [entry]
		var there := func() -> bool: return not schedule.walking() and not schedule.away() and npc.global_position.distance_to(at) <= 4.0
		if not await _wait_for(there, 600):
			return "%s is %.0f px from %s at %d:00" % [id, npc.global_position.distance_to(at), entry.get("place", entry.get("cell")), hour]
		seen.append(str(entry.get("place", "")))
	# in the rain everybody stays in: only a dry day has two places
	if RpgSchedule.weather() == "" and seen[0] == seen[1]:
		return "%s is at %s at %d:00 and at %d:00" % [id, seen[0], HOURS[0], HOURS[1]]
	_box["person"] = id
	return ""

func _give_a_gift() -> String:
	var friends := RpgFriendship.current()
	var id := str(_box.get("person", ""))
	var npc := _person_node(id)
	var bus := RpgUtil.events()
	if friends == null or npc == null or bus == null:
		return "the villager is gone"
	var seen := {"started": 0, "finished": 0}
	var on_started := func(_resource: Resource) -> void: seen["started"] += 1
	var on_finished := func(_resource: Resource) -> void: seen["finished"] += 1
	bus.dialogue_started.connect(on_started)
	bus.dialogue_finished.connect(on_finished)
	var failure: String = await _talk_and_give(friends, id, npc, seen)
	bus.dialogue_started.disconnect(on_started)
	bus.dialogue_finished.disconnect(on_finished)
	return failure

func _talk_and_give(friends: RpgFriendship, id: String, npc: RpgNpc, seen: Dictionary) -> String:
	var state := _state()
	# with a tool in the hand `interact` talks: the first talk of a day counts
	var failure: String = await _hold(&"hoe")
	if failure == "":
		failure = await _stand(_below(npc, 9.0), "up")
	if failure != "":
		return failure
	var before := friends.points_of(id)
	if not await _interact_until(func() -> bool: return friends.has_met(id)):
		return "`interact` with %s did not count as a talk" % id
	if friends.points_of(id) != before + RpgFriendship.TALK_POINTS:
		return "the talk gave %d points, expected %d" % [friends.points_of(id) - before, RpgFriendship.TALK_POINTS]
	if npc.dialogue == null or JsonUtil.to_int(seen["started"]) != 1:
		return "%s has nothing to say" % id
	for i in 40:
		if JsonUtil.to_int(seen["finished"]) > 0:
			break
		await _shared._press("confirm")  # an input event: the box reads those, not the state
		await _frames(2)
	if JsonUtil.to_int(seen["finished"]) != 1:
		return "the talk with %s did not end" % id
	await _frames(6)  # the farmer has its controls back two frames after the box closes
	# a gift: the held item, with the same key
	var gift := &"potion"
	if not state.inventory.has(gift):
		state.inventory.add(gift, 1)
	failure = await _hold(gift)
	if failure == "":
		failure = await _stand(_below(npc, 9.0), "up")
	if failure != "":
		return failure
	var had: int = state.inventory.count(gift)
	var points := friends.points_of(id)
	var taste := friends.taste_of(id, gift)
	var wanted := clampi(points + RpgFriendship.gift_points(taste), 0, RpgFriendship.MAX_POINTS)
	if not await _interact_until(func() -> bool: return friends.gifts_left(id) == RpgFriendship.GIFTS_PER_WEEK - 1):
		return "`interact` with %s held did not give it to %s" % [gift, id]
	await _frames(4)
	if state.inventory.count(gift) != had - 1:
		return "the gift took %d of %s out of the bag, expected 1" % [had - state.inventory.count(gift), gift]
	if friends.points_of(id) != wanted:
		return "%s has %d points after a gift it %s, expected %d" % [id, friends.points_of(id), taste, wanted]
	if JsonUtil.to_int(seen["started"]) != 1:
		return "the gift started a talk as well"
	var known: Array = friends.known.get(id, [])
	if not known.has(String(gift)):
		return "what %s thinks of %s is not known after the gift" % [id, gift]
	# the pause menu has the People page, and it lists who was met
	var controller := _controller()
	var menu := controller.open_pause() if controller != null else null
	await _frames(3)
	if menu == null:
		return "the pause menu did not open"
	var button := menu.find_child(RpgPeoplePage.BUTTON_NAME, true, false) as Button
	var page: RpgPeoplePage = null
	if button == null:
		failure = "the pause menu has no People button"
	else:
		button.pressed.emit()
		await _frames(3)
		page = menu.get_node_or_null(RpgPeoplePage.PAGE_NAME) as RpgPeoplePage
		if page == null or page.rows().size() != 1 or page.person_of(page.rows()[0]) != id:
			failure = "the People page does not list %s" % id
		elif not page.detail().contains(RpgFarmStrings.item_name(gift)) and taste != RpgFriendship.NEUTRAL:
			failure = "the People page does not say what %s thinks of %s: %s" % [id, gift, page.detail()]
	if page != null and is_instance_valid(page):
		page.close()
		await _frames(2)
	if is_instance_valid(menu):
		menu.call(&"close")
	await _frames(3)
	_tree().paused = false
	return failure

# ---------------------------------------------------------------- the farm (T17.04 to T17.06)

func _farm_is_there() -> String:
	var scene := _tree().current_scene
	if scene == null or scene.name != FARM:
		return "not on the farm"
	var mode := RpgFarmMode.current()
	if mode == null:
		return "SceneRouter.combat is not the farm's mode"
	if _farmer() == null:
		return "the player is not an RpgFarmer"
	var field := RpgField.current()
	if field == null:
		return "the farm has no Field"
	var soil := scene.get_node_or_null("Soil") as TileMapLayer
	if soil == null:
		return "the farm has no Soil layer"
	# the map was built from the stored plan: what can be tilled is what the plan lists
	var plan := _plan()
	if plan.is_empty():
		return "rpggen/world_plan.json has no map of the farm"
	var planned := {}
	for raw: Variant in JsonUtil.to_array(plan.get("tillable", [])):
		planned[_cell(raw)] = true
	var plot: Array[Vector2i] = []
	for cell in soil.get_used_cells():
		if field.state_of(cell) == RpgField.GROUND:
			plot.append(cell)
			if not planned.has(cell):
				return "%s can be tilled and is not in the plan" % cell
	if plot.size() != planned.size():
		return "%d cells can be tilled, the plan lists %d" % [plot.size(), planned.size()]
	if plot.size() < 12:
		return "the plot has %d cells that can be tilled, at least 12 are needed" % plot.size()
	plot.sort()
	# the cell that is worked: one of the upper edge of the plot with nothing lying on it; the
	# farmer stands above it, on the free ground round the plot
	var found := false
	for cell in plot:
		if not planned.has(cell + Vector2i.UP) and field.can_till(cell):
			_box["cell"] = cell
			found = true
			break
	if not found:
		return "no cell of the upper edge of the plot is free to be tilled"
	for item: StringName in [&"hoe", &"watering_can", &"sickle", &"farm_axe"]:
		if mode.tool_for(item) == null or not _state().items.has(item):
			return "the game has no %s" % item
	# a new game starts with a hoe and a can (T17.08); the sickle and the axe are bought
	for item: StringName in [&"hoe", &"watering_can"]:
		if not _state().inventory.has(item):
			return "a new game has no %s" % item
	if mode.crops.order.is_empty():
		return "game/data/crops.json has no crop"
	var first := mode.crops.order[0]
	_box["crop"] = first
	var seed := StringName(str(mode.crops.crop(first).get("seed", "")))
	if not mode.crops.grows_in(first, RpgField.season_now()):
		return "the first crop (%s) does not grow in %s" % [first, RpgField.season_now()]
	if not _state().inventory.has(seed):
		return "a new game has no seeds of the first crop (%s)" % seed
	_box["seed"] = seed
	if not ResourceLoader.exists(str(mode.crops.crop(first).get("scene", ""))):
		return "the scene of %s is missing" % first
	return ""

func _fill_the_can() -> String:
	var scene := _tree().current_scene
	var field := RpgField.current()
	var mode := RpgFarmMode.current()
	var marker := scene.get_node_or_null("Markers/WaterFill") as Node2D
	var water := scene.find_child("Water", true, false) as RpgWaterSource
	if marker == null or water == null:
		return "the farm has no water, or no place to fill the can at"
	var at := field.cell_at(marker.global_position)
	var facing := ""
	var wet := at
	for entry: Array in [[Vector2i.UP, "up"], [Vector2i.LEFT, "left"], [Vector2i.RIGHT, "right"], [Vector2i.DOWN, "down"]]:
		var step: Vector2i = entry[0]
		if facing == "" and field.is_water(at + step):
			facing = str(entry[1])
			wet = at + step
	if facing == "":
		return "no cell beside %s says it is water" % at
	var failure: String = await _stand_toward(field.cell_center(at), facing, wet)
	if failure == "":
		failure = await _hold(&"watering_can")
	if failure != "":
		return failure
	if _farmer().tile_ahead() != wet:
		return "the tile ahead is %s, the water is at %s" % [_farmer().tile_ahead(), wet]
	# `use` with the can held, at the water ahead
	RpgFarmWateringCan.set_charges(0)
	var energy := mode.energy.value
	await _tap("use")
	if not await _wait_for(func() -> bool: return RpgFarmWateringCan.charges() == RpgFarmWateringCan.SIZE, 60):
		return "`use` with the can at the water left it at %d of %d" % [RpgFarmWateringCan.charges(), RpgFarmWateringCan.SIZE]
	if mode.energy.value != energy:
		return "filling the can cost energy"
	failure = await _stand_toward(field.cell_center(at), facing, wet)
	if failure != "":
		return failure
	# and `interact` with the water
	RpgFarmWateringCan.set_charges(3)
	if not await _interact_until(func() -> bool: return RpgFarmWateringCan.charges() == RpgFarmWateringCan.SIZE):
		return "`interact` with the water left the can at %d of %d" % [RpgFarmWateringCan.charges(), RpgFarmWateringCan.SIZE]
	return ""

## The cells of the farm the farmer cannot stand on, from the plan: what is built, what stands
## in the way, the water and the plot's own things to clear.
func _blocked(plan: Dictionary) -> Dictionary:
	var out := {}
	var buildings: Array = [plan.get("house", {})]
	buildings.append_array(JsonUtil.to_array(plan.get("animal_houses", [])))
	for raw: Variant in buildings:
		var building := JsonUtil.to_dict(raw)
		var rect := JsonUtil.to_array(building.get("rect", []))
		if rect.size() == 4:
			for x in JsonUtil.to_int(rect[2]):
				for y in JsonUtil.to_int(rect[3]):
					out[Vector2i(JsonUtil.to_int(rect[0]) + x, JsonUtil.to_int(rect[1]) + y)] = true
		for cell: Variant in JsonUtil.to_array(JsonUtil.to_dict(building.get("yard", {})).get("fence", [])):
			out[_cell(cell)] = true
	out[_cell(JsonUtil.to_dict(plan.get("bin", {})).get("cell"))] = true
	for key: String in ["trees"]:
		for cell: Variant in JsonUtil.to_array(plan.get(key, [])):
			out[_cell(cell)] = true
	for cell: Variant in JsonUtil.to_array(JsonUtil.to_dict(plan.get("water", {})).get("cells", [])):
		out[_cell(cell)] = true
	for key: String in ["scenery", "debris"]:
		for raw: Variant in JsonUtil.to_array(plan.get(key, [])):
			out[_cell(JsonUtil.to_dict(raw).get("cell"))] = true
	return out

func _clear_debris() -> String:
	var scene := _tree().current_scene
	var field := RpgField.current()
	var mode := RpgFarmMode.current()
	var plan := _plan()
	var listed := JsonUtil.to_array(plan.get("debris", []))
	var holder := scene.get_node_or_null("YSorted/Entities")
	var things: Array[Node2D] = []
	for node in holder.get_children():
		if node.has_meta(RpgField.CLEAR_META):
			things.append(node as Node2D)
	if things.size() != listed.size():
		return "%d things to clear lie on the farm, the plan lists %d" % [things.size(), listed.size()]
	if things.is_empty():
		print("[rpggen] INFO clear_debris: the plan has nothing to clear, step passes")
		return ""
	# the first thing with a free cell beside it to work from
	var blocked := _blocked(plan)
	var size := _cell(plan.get("size"))
	for thing in things:
		var kind := str(thing.get_meta(RpgField.CLEAR_META))
		var cell := field.cell_at(thing.global_position)
		for entry: Array in [[Vector2i.UP, "down"], [Vector2i.LEFT, "right"], [Vector2i.RIGHT, "left"], [Vector2i.DOWN, "up"]]:
			var step: Vector2i = entry[0]
			var stand := cell + step
			if blocked.has(stand) or stand.x < 1 or stand.y < 1 or stand.x > size.x - 2 or stand.y > size.y - 2:
				continue
			return await _clear(thing, kind, cell, stand, str(entry[1]), field, mode)
	return "nothing to clear can be reached"

func _clear(thing: Node2D, kind: String, cell: Vector2i, stand: Vector2i, facing: String, field: RpgField, mode: RpgFarmMode) -> String:
	var tool_id := &"sickle" if kind == "grass" else &"farm_axe"
	var tool := mode.tool_for(tool_id)
	var kinds: Array[String] = [kind]
	if tool == null or not tool.clears.has(kind):
		return "no tool clears a %s" % kind
	if field.clearable_at(cell, kinds) != thing:
		return "the field does not find the %s at %s" % [kind, cell]
	# a new game has neither the sickle nor the axe (they are bought, and the shop's step sees
	# to that): the tool is lent for this step
	var lent := not _state().inventory.has(tool_id)
	if lent:
		_state().inventory.add(tool_id, 1)
	var failure: String = await _use_on(thing, kind, cell, stand, facing, tool_id, field, mode)
	if lent:
		_state().inventory.remove(tool_id, 1)
	return failure

func _use_on(thing: Node2D, kind: String, cell: Vector2i, stand: Vector2i, facing: String, tool_id: StringName, field: RpgField, mode: RpgFarmMode) -> String:
	var tool := mode.tool_for(tool_id)
	var kinds: Array[String] = [kind]
	var id := str(thing.get("entity_id"))
	var failure: String = await _stand_toward(field.cell_center(stand), facing, cell)
	if failure == "":
		failure = await _hold(tool_id)
	if failure != "":
		return failure
	if _farmer().tile_ahead() != cell:
		return "the tile ahead is %s, the %s lies at %s" % [_farmer().tile_ahead(), kind, cell]
	mode.energy.fill()
	var energy := mode.energy.value
	await _tap("use")
	if not await _wait_for(func() -> bool: return field.clearable_at(cell, kinds) == null, 60):
		return "`use` with %s did not clear the %s at %s" % [tool_id, kind, cell]
	if mode.energy.value != energy - tool.energy_cost:
		return "clearing cost %d energy, expected %d" % [energy - mode.energy.value, tool.energy_cost]
	if id == "" or _state().get_flag(id, "collected", false) != true:
		return "the cleared %s is not remembered ('%s')" % [kind, id]
	return ""

func _till_a_cell() -> String:
	var failure: String = await _stand_at_cell()
	if failure != "":
		return failure
	var field := RpgField.current()
	var mode := RpgFarmMode.current()
	var cell: Vector2i = _box["cell"]
	mode.energy.fill()
	failure = await _hold(&"hoe")
	if failure != "":
		return failure
	var before := mode.energy.value
	await _tap("use")
	if not await _wait_for(func() -> bool: return field.state_of(cell) == RpgField.SOIL, 60):
		return "`use` with the hoe did not till %s (it is %s)" % [cell, field.state_of(cell)]
	var cost := mode.tool_for(&"hoe").energy_cost
	if mode.energy.value != before - cost:
		return "the hoe cost %d energy, expected %d" % [before - mode.energy.value, cost]
	var soil := _tree().current_scene.get_node("Soil") as TileMapLayer
	if soil.get_cell_atlas_coords(cell) != field.tilled_tile:
		return "the Soil layer does not show tilled soil at %s" % cell
	if field.cells.size() != 1:
		return "%d cells were worked, expected 1" % field.cells.size()
	return ""

func _plant_a_seed() -> String:
	var failure: String = await _stand_at_cell()
	if failure != "":
		return failure
	var field := RpgField.current()
	var cell: Vector2i = _box["cell"]
	var seed: StringName = _box["seed"]
	failure = await _hold(seed)
	if failure != "":
		return failure
	var before := _state().inventory.count(seed)
	await _tap("use")
	if not await _wait_for(func() -> bool: return field.crop_at(cell) == str(_box["crop"]), 60):
		return "`use` with %s did not plant %s (the cell is %s)" % [seed, cell, field.state_of(cell)]
	if _state().inventory.count(seed) != before - 1:
		return "planting took %d seeds, expected 1" % (before - _state().inventory.count(seed))
	var node := field.crop_node(cell)
	if node == null or node.stage != 0 or node.ripe:
		return "the crop is not shown as a seedling"
	if node.get_parent() != _farmer().get_parent():
		return "the crop does not stand among the entities the farmer Y-sorts with"
	return ""

func _water_it() -> String:
	var failure: String = await _stand_at_cell()
	if failure != "":
		return failure
	var field := RpgField.current()
	var cell: Vector2i = _box["cell"]
	failure = await _hold(&"watering_can")
	if failure != "":
		return failure
	RpgFarmWateringCan.fill()
	await _tap("use")
	if not await _wait_for(func() -> bool: return field.is_watered(cell), 60):
		return "`use` with the can did not water %s" % cell
	if RpgFarmWateringCan.charges() != RpgFarmWateringCan.SIZE - 1:
		return "the can holds %d, expected %d" % [RpgFarmWateringCan.charges(), RpgFarmWateringCan.SIZE - 1]
	var soil := _tree().current_scene.get_node("Soil") as TileMapLayer
	if soil.get_cell_atlas_coords(cell) != field.watered_tile:
		return "the Soil layer does not show watered soil at %s" % cell
	return ""

func _a_night_grows_it() -> String:
	var field := RpgField.current()
	var calendar := RpgCalendar.current()
	var cell: Vector2i = _box["cell"]
	var today := calendar.today()
	calendar.end_day()
	await _frames(2)
	if calendar.today() != today + 1 or calendar.minute != RpgCalendar.DAY_START:
		return "the day did not end: day %d at minute %d" % [calendar.today(), calendar.minute]
	if field.grown_at(cell) != 1:
		return "the watered crop grew %d days in one night" % field.grown_at(cell)
	if field.is_watered(cell):
		return "the soil is still wet in the morning"
	var crop := _crop()
	var wanted := RpgCropData.stage_of(1, RpgUtil.to_int(crop.get("days", 1)), RpgUtil.to_int(crop.get("stages", 1)))
	var node := field.crop_node(cell)
	if node == null or node.stage != wanted:
		return "the crop shows stage %d, expected %d" % [node.stage if node != null else -1, wanted]
	# a night without water does not count
	calendar.end_day()
	await _frames(2)
	if field.grown_at(cell) != 1:
		return "an unwatered crop grew: %d days" % field.grown_at(cell)
	return ""

func _crop_ripens() -> String:
	var field := RpgField.current()
	var calendar := RpgCalendar.current()
	var cell: Vector2i = _box["cell"]
	var days := RpgUtil.to_int(_crop().get("days", 1))
	var failure: String = await _hold(&"watering_can")
	if failure != "":
		return failure
	for night in range(1, days):
		if field.state_of(cell) != RpgField.CROP:
			return "the crop is %s after %d of %d days" % [field.state_of(cell), night, days]
		failure = await _stand_at_cell()
		if failure != "":
			return failure
		await _tap("use")
		if not await _wait_for(func() -> bool: return field.is_watered(cell), 60):
			return "the can did not water the crop on day %d (it holds %d)" % [night + 1, RpgFarmWateringCan.charges()]
		calendar.end_day()
		await _frames(2)
	if field.state_of(cell) != RpgField.RIPE:
		return "the crop is %s after %d watered nights, expected ripe" % [field.state_of(cell), days]
	var node := field.crop_node(cell)
	if node == null or not node.ripe or node.stage != RpgUtil.to_int(_crop().get("stages", 1)) - 1:
		return "the ripe crop does not show its last picture"
	return ""

func _harvest() -> String:
	var failure: String = await _stand_at_cell()
	if failure != "":
		return failure
	var field := RpgField.current()
	var cell: Vector2i = _box["cell"]
	var produce := StringName(str(_crop().get("produce", "")))
	var before := _state().inventory.count(produce)
	for attempt in 3:
		await _tap("interact")
		if await _wait_for(func() -> bool: return _state().inventory.count(produce) > before, 30):
			break
	if _state().inventory.count(produce) != before + 1:
		return "`interact` on the ripe crop put %d %s into the inventory, expected 1" % [_state().inventory.count(produce) - before, produce]
	var regrow := RpgUtil.to_int(_crop().get("regrow", 0))
	var wanted := RpgField.CROP if regrow > 0 else RpgField.SOIL
	if field.state_of(cell) != wanted:
		return "after the harvest the cell is %s, expected %s" % [field.state_of(cell), wanted]
	var saved := RpgUtil.to_dict(_state().get_flag(RpgField.FLAG_ENTITY, field.resolved_id(), {}))
	if not saved.has(RpgField.cell_name(cell)):
		return "the field is not in the saved game"
	return ""

# ---------------------------------------------------------------- money (T17.08)

func _controller() -> RpgUiController:
	var router := RpgUtil.router()
	return router.get_node_or_null("UiController") as RpgUiController if router != null else null

func _open_menu() -> Node:
	var controller := _controller()
	var menu: Node = controller.get("_menu") if controller != null else null
	return menu if menu != null and is_instance_valid(menu) else null

## Puts the farmer at `at`, looking `facing`, and waits until it can act.
func _stand(at: Vector2, facing: String) -> String:
	var farmer := _farmer()
	if farmer == null:
		return "the farmer is gone"
	farmer.global_position = at
	farmer.set_facing(facing)
	await _frames(4)
	if not await _wait_for(func() -> bool: return not farmer.is_busy(), 120):
		return "the farmer never finished using its tool"
	return ""

## Puts the farmer at `at`, looking `facing`, turned to the cell `toward` beside the one it
## stands in (T17.14): on squares that is what `facing` says already; on diamonds the four
## facings are not the four neighbours, and the farmer is told which one it faces.
func _stand_toward(at: Vector2, facing: String, toward: Vector2i) -> String:
	var failure: String = await _stand(at, facing)
	if failure == "":
		_farmer().face_cell(toward)
		await _frames(2)
	return failure

## As `_stand_toward`, for a thing of the map at `thing_at`: on squares the farmer looks
## `facing`, as the step always had it; on diamonds it is turned to the cell the thing stands
## in, when that is a cell beside its own.
func _stand_before(at: Vector2, facing: String, thing_at: Vector2) -> String:
	var failure: String = await _stand(at, facing)
	var scene := _tree().current_scene
	if failure == "" and RpgIso.footprint_of(scene) != Vector2i.ZERO:
		_farmer().face_cell(RpgIso.cell_at(scene, thing_at))
		await _frames(2)
	return failure

## Where the farmer stands to reach `target` with `interact` while it looks up: `gap` px below
## it on squares, as the steps always stood; on diamonds as far from it as its interaction
## reaches, on the side a farmer that looks up reaches from (RpgIso.reach_dir: straight below
## with the pad on the screen, down and to the left with the pad on the grid).
func _below(target: Node2D, gap: float) -> Vector2:
	var scene := _tree().current_scene
	if RpgIso.footprint_of(scene) == Vector2i.ZERO:
		return target.global_position + Vector2(0.0, gap)
	var reach := floorf(RpgIso.map_unit(scene) * 0.6)
	var area := _farmer().get_node_or_null("Interaction") as RpgInteraction if _farmer() != null else null
	if area != null:
		reach = floorf(area.tile_size * 0.6)
	return target.global_position - RpgIso.reach_dir(scene, "up") * reach

## `interact` until `done` says so (the first press may come before the bodies are known).
func _interact_until(done: Callable) -> bool:
	for attempt in 3:
		await _tap("interact")
		if await _wait_for(done, 30):
			return true
	return false

func _ship_the_crop() -> String:
	var scene := _tree().current_scene
	var field := RpgField.current()
	var bin := scene.find_child("ShippingBin", true, false) as RpgShippingBin
	if bin == null:
		return "the farm has no shipping bin"
	if not ResourceLoader.exists("res://generated/scenes/farm/shipping_bin.tscn"):
		return "generated/scenes/farm/shipping_bin.tscn is missing"
	# the bin stands beside the house: the farmer works it from the cell before it
	var front := scene.get_node_or_null("Markers/BinFront") as Node2D
	if front == null:
		return "the farm does not say where to stand before the bin"
	# (the bin's origin is the lower edge of its cell on squares, the middle of it on diamonds)
	var bin_at := bin.global_position + (Vector2.ZERO if field.footprint() != Vector2i.ZERO else Vector2(0.0, -field.tile_px * 0.5))
	var bin_cell := field.cell_at(bin_at)
	var before_bin := field.cell_at(front.global_position)
	var looks := "up"
	if before_bin.x != bin_cell.x:
		looks = "left" if bin_cell.x < before_bin.x else "right"
	elif before_bin.y < bin_cell.y:
		looks = "down"
	var failure: String = await _stand_before(field.cell_center(before_bin), looks, bin_at)
	if failure != "":
		return failure
	var produce := StringName(str(_crop().get("produce", "")))
	var had := _state().inventory.count(produce)
	if had < 1:
		return "the farmer has no %s to ship" % produce
	if RpgShippingBin.price_of(produce) <= 0:
		return "%s has no price" % produce
	failure = await _hold(produce)
	if failure != "":
		return failure
	if not await _interact_until(func() -> bool: return RpgShippingBin.count(produce) == had):
		return "`interact` with the bin put %d of %d %s into it" % [RpgShippingBin.count(produce), had, produce]
	if _state().inventory.count(produce) != 0:
		return "the held stack did not leave the inventory"
	# a mistake can be undone: with a tool in the hand the stack comes back out
	failure = await _hold(&"hoe")
	if failure != "":
		return failure
	if not await _interact_until(func() -> bool: return _state().inventory.count(produce) == had):
		return "`interact` with a tool in the hand did not take the stack back out"
	if not RpgShippingBin.is_empty():
		return "the bin still holds something"
	failure = await _hold(produce)
	if failure != "":
		return failure
	if not await _interact_until(func() -> bool: return RpgShippingBin.count(produce) == had):
		return "the stack did not go into the bin again"
	_box["shipped"] = had
	_box["produce"] = produce
	return ""

func _sleep_in_the_bed() -> String:
	# the bed is in the house: in through its door
	var way_in := _door_to("farm_house.tscn")
	if way_in == null:
		return "the farm has no door into the farmhouse"
	# from before the door (straight below it on squares; on diamonds the side the house lets
	# people out, where its spawn is), into it
	var front := Vector2(0.0, 1.0)
	var out := _spawn("farm_house_door")
	if out != null and RpgIso.footprint_of(_tree().current_scene) != Vector2i.ZERO and out.global_position.distance_to(way_in.global_position) > 0.5:
		front = (out.global_position - way_in.global_position).normalized()
	var into: String = await _walk_to_map(way_in.global_position + front * RpgField.current().tile_px * 0.8, way_in.global_position, HOUSE, "default")
	if into != "":
		return into
	var scene := _tree().current_scene
	var mode := RpgFarmMode.current()
	var calendar := RpgCalendar.current()
	var save := RpgUtil.save_manager()
	var bed := scene.find_child("Bed", true, false) as RpgBed
	if bed == null:
		return "the farmhouse has no bed"
	if mode.day_end == null or RpgDayEnd.current() != mode.day_end:
		return "the mode has no end of the day"
	var home := RpgBed.home(_state())
	if home.is_empty() or str(home.get("map", "")) != scene.scene_file_path:
		return "the bed of the map is not where the farmer wakes: %s" % home
	# the farmer wakes beside the bed and looks away from it: to sleep it turns to it
	var toward := "up"
	if absf(bed.global_position.x - bed.wake_position().x) > 1.0:
		toward = "left" if bed.global_position.x < bed.wake_position().x else "right"
	var failure: String = await _stand_before(bed.wake_position(), toward, bed.global_position)
	if failure != "":
		return failure
	mode.energy.value = 30
	save.delete(RpgSaveManager.AUTOSAVE_SLOT)
	var today := calendar.today()
	var gold: int = _state().gold
	var ended: Array[int] = []
	var count := func(day: int) -> void: ended.append(day)
	calendar.day_ended.connect(count)
	var slept: bool = await _interact_until(func() -> bool: return calendar.today() > today)
	await _frames(3)
	calendar.day_ended.disconnect(count)
	if not slept:
		return "`interact` with the bed did not end the day"
	if ended.size() != 1 or calendar.today() != today + 1:
		return "sleeping ended %d days" % ended.size()
	if mode.day_end.last_night != RpgDayEnd.SLEPT:
		return "the night was '%s', expected a sleep" % mode.day_end.last_night
	if mode.energy.value != mode.energy.max_energy:
		return "the energy is %d in the morning, expected %d" % [mode.energy.value, mode.energy.max_energy]
	var produce: StringName = _box["produce"]
	var earned := RpgShippingBin.price_of(produce) * RpgUtil.to_int(_box["shipped"])
	if _state().gold != gold + earned:
		return "the night paid %d, expected %d" % [_state().gold - gold, earned]
	if not RpgShippingBin.is_empty():
		return "the bin is not empty in the morning"
	if not mode.day_end.saved or not save.has_save(RpgSaveManager.AUTOSAVE_SLOT):
		return "sleeping did not save into the autosave slot"
	if RpgUtil.to_int(save.header(RpgSaveManager.AUTOSAVE_SLOT).get("gold", -1)) != gold + earned:
		return "the save of the morning does not hold the money of the night"
	_box["earned"] = earned
	_box["gold"] = gold + earned
	return ""

func _morning_summary() -> String:
	var tree := _tree()
	var day_end := RpgFarmMode.current().day_end
	var summary := day_end.summary()
	if summary == null:
		return "the morning shows no summary"
	if not tree.paused:
		return "the game is not paused behind the summary"
	var produce: StringName = _box["produce"]
	var lines := RpgDaySummary.lines(summary.sale)
	var wanted := "%s x%d" % [RpgFarmStrings.item_name(produce), RpgUtil.to_int(_box["shipped"])]
	if lines.size() != 1 or not lines[0].begins_with(wanted) or not lines[0].contains(str(_box["earned"])):
		return "the summary lists %s, expected one line of %s for %s" % [lines, wanted, _box["earned"]]
	var total := summary.get_node_or_null("%Total") as Label
	if total == null or total.text != RpgDaySummary.total_text(summary.sale) or not total.text.contains(str(_box["earned"])):
		return "the summary does not show the total"
	await _frames(3)
	await _tap("confirm")
	if not await _wait_for(func() -> bool: return day_end.summary() == null, 60):
		return "`confirm` did not close the summary"
	await _frames(3)
	# a game that has no slot of its own yet is offered the save screen: it is closed again
	var menu := _open_menu()
	if menu != null:
		if not (menu is RpgSaveLoadMenu) or day_end.chosen_slot() != RpgSaveManager.NO_SLOT:
			return "a menu that is not the offered save screen is open after the summary"
		menu.call(&"close")
		await _frames(3)
	if tree.paused:
		return "the game is still paused after the summary"
	if _state().gold != RpgUtil.to_int(_box["gold"]):
		return "the money changed while the summary was shown"
	# the next night sells nothing and shows nothing
	RpgCalendar.current().end_day()
	await _frames(3)
	if day_end.summary() != null or tree.paused:
		return "a night in which nothing was sold shows a summary"
	return ""

## Asks for the village shop as the keeper's `open_shop:village_shop` does and waits for it.
func _ask_for_shop() -> RpgShopMenu:
	RpgUtil.emit(&"shop_requested", [&"village_shop"])
	for i in 30:
		await _tree().physics_frame
		var menu := _open_menu() as RpgShopMenu
		if menu != null:
			return menu
	return null

func _buy_seeds_at_the_shop() -> String:
	var tree := _tree()
	var mode := RpgFarmMode.current()
	var calendar := RpgCalendar.current()
	var shop := RpgShopDefinition.load_shop(&"village_shop") as RpgFarmShop
	if shop == null:
		return "game/data/shops/village_shop.tres is not the shop of a farm"
	if calendar.clock()[0] >= shop.opens:
		return "the morning is at %s, later than the shop opens" % [calendar.clock()]
	# the morning, before 9:00: closed, and it says so
	if shop.is_open() or shop.closed_reason() == "":
		return "the shop is open at %s" % [calendar.clock()]
	var early: RpgShopMenu = await _ask_for_shop()
	if early != null:
		return "the shop opened before its hours"
	# its closed day: closed at noon too
	var guard := 0
	while calendar.weekday() != shop.closed_weekday and guard < RpgCalendar.WEEK_DAYS:
		calendar.end_day()
		guard += 1
	await _frames(2)
	calendar.pass_minutes(12 * 60 - calendar.minute)
	if shop.is_open():
		return "the shop is open at noon of its closed day (weekday %d)" % calendar.weekday()
	var on_closed_day: RpgShopMenu = await _ask_for_shop()
	if on_closed_day != null:
		return "the shop opened on its closed day"
	calendar.end_day()
	await _frames(2)
	# opening time
	calendar.pass_minutes(shop.opens * 60 - calendar.minute)
	if calendar.clock() != ([shop.opens, 0] as Array[int]) or not shop.is_open():
		return "the shop is closed at %s on weekday %d" % [calendar.clock(), calendar.weekday()]
	var in_season := mode.crops.of_season(calendar.season_name())
	if in_season.is_empty():
		return "no crop grows in %s" % calendar.season_name()
	var seeds: Array[StringName] = []
	for crop_id in in_season:
		seeds.append(StringName(str(mode.crops.crop(crop_id).get("seed", ""))))
	var offered := shop.offered(_state().items)
	for seed_id in seeds:
		if not offered.has(seed_id):
			return "the shop does not offer %s in %s: %s" % [seed_id, calendar.season_name(), offered]
	for crop_id in mode.crops.order:
		var other := StringName(str(mode.crops.crop(crop_id).get("seed", "")))
		if not in_season.has(crop_id) and offered.has(other):
			return "the shop offers %s out of its season" % other
	for tool: StringName in [&"sickle", &"farm_axe"]:
		if not offered.has(tool):
			return "the shop does not sell the %s" % tool
	var menu: RpgShopMenu = await _ask_for_shop()
	if menu == null:
		return "the shop did not open in its hours"
	var failure := ""
	var wanted := seeds[0]
	var price := shop.buy_price(wanted, _state().items)
	var gold: int = _state().gold
	var had := _state().inventory.count(wanted)
	var row: Button = null
	for candidate in menu.rows():
		if menu.item_of(candidate) == wanted:
			row = candidate
	if not tree.paused:
		failure = "the game was not paused behind the shop"
	elif row == null:
		failure = "%s is not a row of the shop" % wanted
	elif price <= 0 or gold < price:
		failure = "%s costs %d and the farmer has %d" % [wanted, price, gold]
	else:
		row.pressed.emit()
		await _frames(2)
		if _state().inventory.count(wanted) != had + 1 or _state().gold != gold - price:
			failure = "buying %s left %d of them and %d money (was %d and %d)" % [wanted, _state().inventory.count(wanted), _state().gold, had, gold]
	if is_instance_valid(menu):
		menu.close()
	await _frames(2)
	if failure == "" and tree.paused:
		failure = "closing the shop did not unpause the game"
	tree.paused = false
	return failure

# ---------------------------------------------------------------- the weather and the HUD (T17.11)
#
# These three steps stand on their own: they find the field (on the map that is shown, else on
# the farm's or the starter map), work a cell of their own through the field itself, and count
# on nothing an earlier step left behind.

## The field of the map that is shown; when it has none, the map of the farm is entered first.
## null when no map of the game has a field.
func _weather_field() -> RpgField:
	if RpgField.current() != null:
		return RpgField.current()
	var router := RpgUtil.router()
	var here := _tree().current_scene.scene_file_path if _tree().current_scene != null else ""
	for path: String in ["res://game/maps/farm.tscn", "res://game/maps/starter_map.tscn"]:
		if router == null or path == here or not ResourceLoader.exists(path):
			continue
		await router.go_to(path)
		await _weather_wait(func() -> bool: return not router.is_busy(), 300)
		await _weather_frames(5)
		if RpgField.current() != null:
			return RpgField.current()
	return null

func _weather_frames(count: int) -> void:
	for i in count:
		await _tree().physics_frame

func _weather_wait(check: Callable, frames: int) -> bool:
	for i in frames:
		if check.call():
			return true
		await _tree().physics_frame
	return check.call()

## A cell of the plot that nothing was done to and nothing stands on, or null when there is none.
func _weather_free_cell(field: RpgField) -> Variant:
	var soil := field.get_node_or_null(field.soil_path) as TileMapLayer
	if soil == null:
		return null
	var cells := soil.get_used_cells()
	cells.sort()
	for cell in cells:
		if field.can_till(cell):
			return cell
	return null

## Ends the day as somebody who did not sleep, and closes a summary the morning may show.
func _weather_end_day() -> void:
	RpgCalendar.current().end_day()
	await _weather_frames(2)
	var day_end := RpgFarmMode.current().day_end
	if day_end != null and day_end.summary() != null:
		day_end.summary().close()
		await _weather_frames(2)
	_tree().paused = false

## A rainy day waters the field, and a crop grows through it without the can. The rain is
## forced through the weather's debug hook: the smoke run's own weather is fair every day.
func _rain_waters_the_field() -> String:
	var mode := RpgFarmMode.current()
	var calendar := RpgCalendar.current()
	if mode == null or calendar == null or mode.weather == null or RpgFarmWeather.current() != mode.weather:
		return "the farm's mode has no weather"
	var weather := mode.weather
	var field: RpgField = await _weather_field()
	if field == null:
		return "no map of the game has a field"
	if weather.today != RpgFarmWeather.SUN or RpgSchedule.weather() != "":
		return "the smoke run's weather is %s (the schedules: '%s'), expected a fair day" % [weather.today, RpgSchedule.weather()]
	var found: Variant = _weather_free_cell(field)
	if found == null:
		return "the plot has no free cell to till"
	var cell: Vector2i = found
	if not field.till(cell):
		return "the cell %s could not be tilled" % cell
	var in_season := mode.crops.of_season(calendar.season_name())
	var crop := in_season[0] if not in_season.is_empty() else ""
	if crop != "" and not field.plant(cell, crop):
		return "%s could not be planted in %s" % [crop, cell]
	if field.is_watered(cell):
		return "freshly tilled soil is wet on a fair day"
	weather.force_tomorrow(RpgFarmWeather.RAIN)
	if weather.forecast() != RpgFarmWeather.RAIN or not weather.forecast_text().contains(RpgFarmWeather.text(RpgFarmWeather.RAIN)):
		return "the forecast is %s, expected rain" % weather.forecast()
	await _weather_end_day()
	if weather.today != RpgFarmWeather.RAIN or not weather.is_wet():
		return "the day that was foretold as rainy is %s" % weather.today
	if RpgSchedule.weather() != RpgFarmWeather.SCHEDULE_RAIN:
		return "the schedules were told '%s' on a rainy day" % RpgSchedule.weather()
	if not field.is_watered(cell):
		return "the rain did not water the tilled cell %s" % cell
	if field.grown_at(cell) != 0:
		return "the crop grew in the dry night before the rain"
	var soil := field.get_node_or_null(field.soil_path) as TileMapLayer
	# (the source too: a pack's wet soil may be the same cell of another source as its dry soil)
	if soil != null and (soil.get_cell_atlas_coords(cell) != field.watered_tile or soil.get_cell_source_id(cell) != field.watered_source):
		return "the Soil layer does not show watered soil at %s" % cell
	var map := RpgUtil.router().current_map
	if weather.overlay_visible() != weather.shows_on(map) or weather.overlay_visible() == map.interior():
		return "the overlay of the rain is %s on a map whose interior() is %s" % ["shown" if weather.overlay_visible() else "hidden", map.interior()]
	if RpgDayNight.weather_tint == RpgDayNight.DAY:
		return "the light of a rainy day is not duller"
	# what is tilled in the rain is wet at once
	var second: Variant = _weather_free_cell(field)
	if second != null:
		var other: Vector2i = second
		if not field.till(other) or not field.is_watered(other):
			return "a cell tilled in the rain (%s) is dry" % other
	# the night of the rainy day: the crop grew without the can
	weather.force_tomorrow(RpgFarmWeather.SUN)
	await _weather_end_day()
	if crop != "" and field.grown_at(cell) != 1:
		return "the crop grew %d days through a rainy day, expected 1" % field.grown_at(cell)
	if field.is_watered(cell):
		return "the soil is still wet on the fair morning after the rain"
	if weather.today != RpgFarmWeather.SUN or RpgSchedule.weather() != "" or weather.overlay_visible():
		return "the fair day after the rain is %s (the schedules: '%s')" % [weather.today, RpgSchedule.weather()]
	if RpgDayNight.weather_tint != RpgDayNight.DAY:
		return "the light of the fair day after the rain is still dull"
	return ""

## The HUD shows the time, the date, the weather, the money and the energy.
func _hud_shows_the_day() -> String:
	var mode := RpgFarmMode.current()
	var calendar := RpgCalendar.current()
	var state := RpgUtil.state()
	if mode == null or calendar == null:
		return "the game has no farm's mode or no calendar"
	var hud := mode.get_node_or_null("Hud") as RpgFarmHud
	if hud == null:
		return "the mode has no Hud"
	if not hud.visible:
		return "the HUD is hidden on a map"
	var labels := {}
	for label_name: String in ["Clock", "Date", "Weather", "Money"]:
		var label := hud.get_node_or_null("%" + label_name) as Label
		if label == null:
			return "the HUD has no %s" % label_name
		labels[label_name] = label
	var clock: Label = labels["Clock"]
	var date: Label = labels["Date"]
	var sky: Label = labels["Weather"]
	var money: Label = labels["Money"]
	hud.refresh()
	if clock.text != RpgFarmHud.clock_text(calendar.minute):
		return "the clock shows %s at minute %d" % [clock.text, calendar.minute]
	if date.text != RpgFarmHud.date_text(calendar) or not date.text.contains(str(calendar.day)) or not date.text.contains(RpgFarmStrings.season(calendar.season_name())):
		return "the date shows '%s' on day %d of %s" % [date.text, calendar.day, calendar.season_name()]
	if sky.text != RpgFarmWeather.text(mode.weather.today):
		return "the weather shows '%s' on a day of %s" % [sky.text, mode.weather.today]
	if money.text != RpgFarmHud.money_text(state.gold) or not money.text.contains(str(state.gold)):
		return "the money shows '%s', the farmer has %d" % [money.text, state.gold]
	# they follow the game
	var gold: int = state.gold
	state.gold = gold + 7
	if not money.text.contains(str(gold + 7)):
		return "the money did not follow: '%s' with %d" % [money.text, gold + 7]
	state.gold = gold
	var before := calendar.minute
	calendar.pass_minutes(RpgFarmHud.CLOCK_STEP * 2)
	if calendar.minute != before + RpgFarmHud.CLOCK_STEP * 2 or clock.text != RpgFarmHud.clock_text(calendar.minute):
		return "the clock did not follow: %s at minute %d" % [clock.text, calendar.minute]
	var bar := hud.get_node_or_null("%EnergyBar") as ProgressBar
	mode.energy.value = 35
	if bar == null or int(bar.value) != 35:
		return "the energy bar does not show the energy"
	mode.energy.fill()
	return ""

## The days are ended until the season changes, and again until a season the crop does not grow
## in: there it withers.
func _season_turns() -> String:
	var mode := RpgFarmMode.current()
	var calendar := RpgCalendar.current()
	if mode == null or calendar == null or mode.seasons == null:
		return "the farm's mode has no calendar or no seasons"
	if not FileAccess.file_exists(RpgFarmSeasons.TABLE_PATH):
		return "%s is missing" % RpgFarmSeasons.TABLE_PATH
	var field: RpgField = await _weather_field()
	if field == null:
		return "no map of the game has a field"
	# a crop that grows now and not all the year
	var crop := ""
	for crop_id in mode.crops.of_season(calendar.season_name()):
		for season_name in RpgCalendar.SEASONS:
			if not mode.crops.grows_in(crop_id, season_name) and crop == "":
				crop = crop_id
	if crop == "":
		# a pack of two crops: both grow all the year (crop_plan.seasons_for), and nothing can
		# wither; that is the plan, not a fault of the farm (T17.29)
		return ""
	var found: Variant = _weather_free_cell(field)
	if found == null:
		return "the plot has no free cell to till"
	var cell: Vector2i = found
	if not field.till(cell) or not field.plant(cell, crop):
		return "%s could not be planted in %s" % [crop, cell]
	var turned: Array[int] = []
	var count := func(season: int) -> void: turned.append(season)
	calendar.season_changed.connect(count)
	var failure := ""
	var hud := mode.get_node_or_null("Hud")
	var date := hud.get_node_or_null("%Date") as Label if hud != null else null
	for turn in RpgCalendar.SEASONS.size():
		var season := calendar.season
		var changes := turned.size()
		for day in calendar.days_per_season:
			if calendar.season != season:
				break
			if field.state_of(cell) == RpgField.WITHERED:
				failure = "%s withered on day %d of %s, where it grows" % [crop, calendar.day, calendar.season_name()]
				break
			await _weather_end_day()
		if failure != "":
			break
		if calendar.season != (season + 1) % RpgCalendar.SEASONS.size() or calendar.day != 1 or turned.size() != changes + 1:
			failure = "after the last day of season %d the calendar shows day %d of season %d (%d changes)" % [season, calendar.day, calendar.season, turned.size() - changes]
			break
		if date != null and not date.text.contains(RpgFarmStrings.season(calendar.season_name())):
			failure = "the HUD shows '%s' in %s" % [date.text, calendar.season_name()]
			break
		if not mode.crops.grows_in(crop, calendar.season_name()):
			if field.state_of(cell) != RpgField.WITHERED:
				failure = "%s is %s in %s, expected withered" % [crop, field.state_of(cell), calendar.season_name()]
			break
	calendar.season_changed.disconnect(count)
	if failure != "":
		return failure
	if field.state_of(cell) != RpgField.WITHERED:
		return "%s never withered: it is %s in %s" % [crop, field.state_of(cell), calendar.season_name()]
	var node := field.crop_node(cell)
	if node == null:
		return "the withered crop is not shown"
	if not field.remove_crop(cell):
		return "the withered crop could not be cut away"
	return ""

# ---------------------------------------------------------------- fishing and foraging (T17.10)
#
# These two steps stand on their own: they go to the farm's map when another one is shown and
# count on nothing an earlier step left behind (the rod is lent when the bag has none).

const FORAGE_FARM := "res://game/maps/farm.tscn"

func _forage_frames(count: int) -> void:
	for i in count:
		await _tree().physics_frame

func _forage_wait(check: Callable, frames: int) -> bool:
	for i in frames:
		if check.call():
			return true
		await _tree().physics_frame
	return check.call()

## The fish and the forage of the stored plan (`farm.forage`), or {}.
func _forage_plan() -> Dictionary:
	if not FileAccess.file_exists(PLAN_PATH):
		return {}
	return JsonUtil.to_dict(JsonUtil.to_dict(JsonUtil.to_dict(JsonUtil.read(PLAN_PATH)).get("farm", {})).get("forage", {}))

## The farm's map, entered when another map is shown. null when the game has none.
func _forage_farm() -> Node:
	var router := RpgUtil.router()
	var scene := _tree().current_scene
	if scene != null and scene.scene_file_path == FORAGE_FARM:
		return scene
	if router == null or not ResourceLoader.exists(FORAGE_FARM):
		return null
	await router.go_to(FORAGE_FARM)
	await _forage_wait(func() -> bool: return not router.is_busy(), 300)
	await _forage_frames(5)
	scene = _tree().current_scene
	return scene if scene != null and scene.scene_file_path == FORAGE_FARM else null

## Puts the farmer at `at`, looking `facing`, and waits until it can act.
func _forage_stand(at: Vector2, facing: String) -> String:
	var farmer := _farmer()
	if farmer == null:
		return "the farmer is gone"
	farmer.global_position = at
	farmer.set_facing(facing)
	await _forage_frames(4)
	if not await _forage_wait(func() -> bool: return not farmer.is_busy() and not farmer.move_locked, 180):
		return "the farmer never came free"
	return ""

## The places of the farm are the plan's, and a thing that lies at one this morning is picked up
## with `interact`.
func _forage_on_the_farm() -> String:
	var mode := RpgFarmMode.current()
	if mode == null or mode.forage == null:
		return "the farm's mode has no forage"
	var scene: Node = await _forage_farm()
	var field := RpgField.current()
	if scene == null or field == null:
		return "the game has no farm map with a field"
	var forage := mode.forage
	var spots := JsonUtil.to_array(_forage_plan().get("spots", []))
	var places := forage.places_on(scene)
	if spots.is_empty():
		return "the plan has no places to forage (rpggen/world_plan.json, farm.forage.spots)"
	if scene.get_node_or_null("Forage") == null or places.size() != spots.size():
		return "the farm has %d places to forage, the plan lists %d" % [places.size(), spots.size()]
	for i in spots.size():
		if field.cell_at(places[i]) != _cell(spots[i]):
			return "Forage/Spot%d lies in %s, the plan says %s" % [i + 1, field.cell_at(places[i]), _cell(spots[i])]
	forage.refresh()
	await _forage_frames(3)
	var lying := forage.lying(places.size())
	var shown := forage.shown()
	if shown.is_empty() or shown.size() != lying.size():
		return "%d things lie on the farm this morning, %d should (%s)" % [shown.size(), lying.size(), RpgField.season_now()]
	var spot: int = shown[0]
	var thing := forage.thing_at(spot)
	var item := thing.item_id
	if item != lying[spot] or not _state().items.has(item):
		return "the thing at Spot%d is '%s', expected '%s' (an item of the game)" % [spot + 1, item, lying[spot]]
	# standing on its cell: it is walked over, and `interact` finds it under the feet
	var failure: String = await _forage_stand(places[spot], "down")
	if failure != "":
		return failure
	var before := _state().inventory.count(item)
	var picked := false
	for attempt in 3:
		await _tap("interact")
		if await _forage_wait(func() -> bool: return _state().inventory.count(item) == before + 1, 30):
			picked = true
			break
	if not picked:
		return "`interact` at Spot%d did not pick up %s" % [spot + 1, item]
	await _forage_frames(2)
	if forage.thing_at(spot) != null or forage.lying(places.size()).has(spot):
		return "%s still lies at Spot%d after it was picked up" % [item, spot + 1]
	if not forage.picked_today().has(spot):
		return "the flags do not remember that Spot%d was picked today" % (spot + 1)
	return ""

## On a farm with a pond: the rod casts with `use` at the water, a fish bites, and it is landed
## by holding `use` as the bar asks; the fish is in the bag. A farm with a well passes.
func _catch_a_fish() -> String:
	var mode := RpgFarmMode.current()
	if mode == null or mode.fishing == null or mode.forage == null:
		return "the farm's mode has no fishing"
	# a farm with a well and a beach fishes too (T17.23), at its beach: that is another step's
	var pond := JsonUtil.to_str(JsonUtil.to_dict(_plan().get("water", {})).get("kind", "")) == RpgFishing.POND
	if not JsonUtil.to_bool(_forage_plan().get("fishing", false)) or not pond:
		print("[rpggen] INFO catch_a_fish: the farm has no pond, or fishing is switched off: step passes")
		return ""
	var scene: Node = await _forage_farm()
	var field := RpgField.current()
	if scene == null or field == null:
		return "the game has no farm map with a field"
	var fishing := mode.fishing
	var rod := mode.tool_for(&"fishing_rod")
	var marker := scene.get_node_or_null("Markers/WaterFill") as Node2D
	if rod == null or marker == null or not _state().items.has(&"fishing_rod"):
		return "the game has no fishing rod, or the farm no place at its water"
	var at := field.cell_at(marker.global_position)
	var facing := ""
	var wet := at
	for entry: Array in [[Vector2i.UP, "up"], [Vector2i.LEFT, "left"], [Vector2i.RIGHT, "right"], [Vector2i.DOWN, "down"]]:
		var step: Vector2i = entry[0]
		if facing == "" and field.is_water(at + step):
			facing = str(entry[1])
			wet = at + step
	if facing == "":
		return "no cell beside %s says it is water" % at
	_box["fish_water"] = wet
	var calendar := RpgCalendar.current()
	var biting := RpgFishing.fish_of(mode.forage.fish, calendar.season_name(), RpgFishing.time_of(calendar.minute), RpgFishing.POND)
	if biting.is_empty():
		return "no fish of game/data/forage.json bites in %s at %d:00" % [calendar.season_name(), calendar.clock()[0]]
	# the rod is bought at the shop; it is lent for this step when the bag has none
	var lent := not _state().inventory.has(&"fishing_rod")
	if lent:
		_state().inventory.add(&"fishing_rod", 1)
	# in a bag of more than ten stacks the rod goes to the front, where the hotbar is
	var slots := _state().inventory.slots
	for i in slots.size():
		if i >= RpgHotbar.SLOTS and StringName(str(slots[i].get("item_id", ""))) == &"fishing_rod":
			slots.insert(0, slots.pop_at(i))
			break
	var failure: String = await _land_a_fish(field.cell_center(at), facing, at, mode, fishing, rod)
	Input.action_release("use")
	if fishing.is_busy():
		fishing.cancel()
	if lent:
		_state().inventory.remove(&"fishing_rod", 1)
	return failure

func _land_a_fish(stand: Vector2, facing: String, at: Vector2i, mode: RpgFarmMode, fishing: RpgFishing, rod: RpgFarmTool) -> String:
	var failure: String = await _forage_stand(stand, facing)
	if failure == "":
		var wet: Vector2i = _box["fish_water"]
		_farmer().face_cell(wet)  # what `facing` says on squares; the water's cell on diamonds
		await _forage_frames(2)
		failure = await _hold(&"fishing_rod")
	if failure != "":
		return failure
	if not RpgField.current().is_water(_farmer().tile_ahead()):
		return "the tile ahead of %s is no water" % at
	mode.energy.fill()
	var energy := mode.energy.value
	var minute := RpgCalendar.current().minute
	var casts := fishing.casts()
	# the cast: the real action, once
	await _tap("use")
	if not await _forage_wait(func() -> bool: return fishing.state != RpgFishing.IDLE, 60):
		return "`use` with the rod at the pond cast nothing"
	if mode.energy.value != energy - rod.energy_cost:
		return "the cast cost %d energy, expected %d" % [energy - mode.energy.value, rod.energy_cost]
	if fishing.casts() != casts + 1 or RpgCalendar.current().minute < minute + RpgFishing.CAST_MINUTES:
		return "the cast was not counted, or passed no time"
	var fish := fishing.fish_id
	var item := StringName(str(mode.forage.fish_entry(fish).get("item", "")))
	if fish == "" or not _state().items.has(item):
		return "the fish on the line ('%s') is no item of the game" % fish
	var before := _state().inventory.count(item)
	# the wait (1 to 4 s) and the bite, with the button let go
	if not await _forage_wait(func() -> bool: return fishing.state == RpgFishing.REELING or fishing.state == RpgFishing.IDLE, 600):
		return "no bite within ten seconds"
	if fishing.state != RpgFishing.REELING:
		return "the cast ended before the bar opened"
	if not _farmer().move_locked:
		return "the farmer can walk away while the line is out"
	if fishing.bar() == null or not fishing.bar().visible:
		return "the bar is not shown"
	# the bar: the real action, held while the fish is above the middle of the zone. The button
	# goes down once for as long as it is held: Input.action_press on every frame is a new press
	# on every frame, and a press is a cast as soon as the line is in
	var held := false
	for frame in 2400:
		if fishing.state != RpgFishing.REELING:
			break
		var above := fishing.mark > fishing.zone
		if above and not held:
			Input.action_press("use")
		elif held and not above:
			Input.action_release("use")
		held = above
		await _tree().physics_frame
	Input.action_release("use")
	# the button may still go down in the frame the fish is landed in, and that press casts
	# again: the second cast is ended here, and the catch is what the bag says below
	if fishing.state != RpgFishing.IDLE and fishing.casts() == casts + 2:
		fishing.cancel()
		await _forage_frames(2)
	if fishing.state != RpgFishing.IDLE:
		return "the fish was neither landed nor lost within forty seconds (the meter stands at %.2f)" % fishing.meter
	await _forage_frames(3)
	if _state().inventory.count(item) != before + 1:
		return "the bag has %d of %s after the catch, expected %d" % [_state().inventory.count(item), item, before + 1]
	if not await _forage_wait(func() -> bool: return not _farmer().move_locked, 120):
		return "the farmer stays locked after the catch"
	return ""

# ---------------------------------------------------------------- the animals (T17.07)
#
# These steps run only in a farm with an animal house (`animals`: coop, coop_and_barn) whose
# packs, or the drawn farm kit, have an animal to live in it; in any other farm each passes with
# an INFO line. They count on nothing an earlier step left behind but the game itself: they
# move the clock to the hour they need, give the farmer the money for what they buy, and go
# to the maps they work on. One animal is bought for every house that has a kind of animal.

## The animal houses of the game, or null in a farm that keeps no animals.
func _animals_herd() -> RpgAnimalHouse:
	var mode := RpgFarmMode.current()
	var herd := mode.animals if mode != null else null
	return herd if herd != null and herd.data != null and not herd.data.is_empty() else null

## The animals the first of these steps bought: `{id, kind, house}` each.
func _animals_bought() -> Array:
	return JsonUtil.to_array(_box.get("animals", []))

## True, with an INFO line, when the step has nothing to do in this farm.
func _animals_skip(step_name: String) -> bool:
	if _animals_herd() == null:
		print("[rpggen] INFO %s: the farm has no animal house, step passes" % step_name)
		return true
	if _animals_bought().is_empty() and step_name != "buy_a_hen":
		print("[rpggen] INFO %s: no animal was bought, step passes" % step_name)
		return true
	return false

func _animals_frames(count: int) -> void:
	for i in count:
		await _tree().physics_frame

## Goes to the map `path` when it is not the one that is shown, and waits until it is entered.
func _animals_go(path: String) -> String:
	var router := RpgUtil.router()
	var here := _tree().current_scene.scene_file_path if _tree().current_scene != null else ""
	if router == null or not ResourceLoader.exists(path):
		return "the map %s is missing" % path
	if here != path:
		await router.go_to(path)
		for i in 600:
			if not router.is_busy() and _tree().current_scene != null and _tree().current_scene.scene_file_path == path:
				break
			await _tree().physics_frame
	await _animals_frames(5)
	if _tree().current_scene == null or _tree().current_scene.scene_file_path != path:
		return "the map %s was not entered" % path
	return "" if _farmer() != null else "the map %s has no farmer" % path

## Holds `item_id`, putting its stack among the ten slots of the hotbar first when the bag has
## it further back. "" when it is held afterwards.
func _animals_hold(item_id: StringName) -> String:
	var slots: Array = _state().inventory.slots
	for i in slots.size():
		if JsonUtil.to_str(JsonUtil.to_dict(slots[i]).get("item_id", "")) == String(item_id) and i >= RpgHotbar.SLOTS:
			var last: Variant = slots[RpgHotbar.SLOTS - 1]
			slots[RpgHotbar.SLOTS - 1] = slots[i]
			slots[i] = last
			break
	return await _hold(item_id)

## Puts the farmer below `thing`, looking up at it, `gap` px from its origin (on diamonds:
## where its interaction reaches the thing from, `_below`).
func _animals_face(thing: Node2D, gap: float) -> String:
	return await _stand(_below(thing, gap), "up")

## The first morning hour the shop is open on a fair day: the night passes when it is too late
## in the day, and the shop's closed day is slept through.
func _animals_shop_hour(shop: RpgFarmShop) -> void:
	var calendar := RpgCalendar.current()
	if calendar.minute > shop.opens * 60:
		await _weather_end_day()
	var guard := 0
	# (its closed day of the week, and a festival's day off, T17.25)
	while shop.closed_all_day() and guard < RpgCalendar.WEEK_DAYS:
		await _weather_end_day()
		guard += 1
	calendar.pass_minutes(shop.opens * 60 - calendar.minute)
	RpgFarmMode.current().weather.force(RpgFarmWeather.SUN)
	await _animals_frames(2)

## An animal is bought at the shop for every house that has a kind: the row is paid for, the
## animal is in the herd and not in the bag, and the house has a stall less. The feed is bought
## as a thing for the bag.
func _buy_a_hen() -> String:
	if _animals_skip("buy_a_hen"):
		return ""
	var herd := _animals_herd()
	var data := herd.data
	var shop := RpgShopDefinition.load_shop(&"village_shop") as RpgFarmShop
	if shop == null:
		return "game/data/shops/village_shop.tres is not the shop of a farm"
	var wanted: Array[String] = []
	for house_id in data.house_order:
		if not ResourceLoader.exists(JsonUtil.to_str(data.house(house_id).get("map", ""))):
			return "the room of the %s (%s) is missing" % [house_id, data.house(house_id).get("map", "")]
		if data.stalls(house_id) < 1:
			return "the %s has no stall" % house_id
		var kinds := data.kinds_of(house_id)
		if kinds.is_empty():
			print("[rpggen] INFO buy_a_hen: the game has no animal for the %s" % house_id)
		else:
			wanted.append(kinds[0])
	_box["animals"] = []
	if wanted.is_empty():
		print("[rpggen] INFO buy_a_hen: the game has no animal to buy, step passes")
		return ""
	var feed := data.feed_item
	if feed == &"" or not _state().items.has(feed):
		return "the game has no feed item (%s)" % feed
	await _animals_shop_hour(shop)
	if not shop.is_open():
		return "the shop is closed at %s on weekday %d" % [RpgCalendar.current().clock(), RpgCalendar.current().weekday()]
	var offered := shop.offered(_state().items)
	if not offered.has(feed):
		return "the shop does not sell %s: %s" % [feed, offered]
	var menu: RpgShopMenu = await _ask_for_shop()
	if menu == null:
		return "the shop did not open in its hours"
	var failure := ""
	var bought: Array = []
	for kind_id in wanted:
		var ticket := StringName(JsonUtil.to_str(data.kind(kind_id).get("ticket", "")))
		var house_id := data.house_of(kind_id)
		var price := shop.buy_price(ticket, _state().items)
		_state().gold += price
		var gold: int = _state().gold
		var room := herd.room_in(house_id)
		var before := RpgAnimalHouse.herd().size()
		var row: Button = null
		for candidate in menu.rows():
			if menu.item_of(candidate) == ticket:
				row = candidate
		if row == null:
			failure = "%s is not a row of the shop (%s)" % [ticket, shop.offered(_state().items)]
			break
		if price <= 0:
			failure = "the %s has no price" % kind_id
			break
		row.pressed.emit()
		await _animals_frames(2)
		var herd_now := RpgAnimalHouse.herd()
		if herd_now.size() != before + 1 or _state().gold != gold - price or _state().inventory.count(ticket) != 0:
			failure = "buying a %s left %d animals (was %d), %d money (was %d) and %d of the row in the bag" % [kind_id, herd_now.size(), before, _state().gold, gold, _state().inventory.count(ticket)]
			break
		var made: Dictionary = herd_now[herd_now.size() - 1]
		if made["kind"] != kind_id or made["house"] != house_id or JsonUtil.to_str(made["name"]) == "" or herd.room_in(house_id) != room - 1:
			failure = "the %s that was bought is %s, and the %s has room for %d (was %d)" % [kind_id, made, house_id, herd.room_in(house_id), room]
			break
		bought.append({"id": JsonUtil.to_int(made["id"]), "kind": kind_id, "house": house_id})
	if failure == "":
		# the feed: a portion for every house, and one to spare
		var portions := bought.size() + 1
		var had := _state().inventory.count(feed)
		_state().gold += shop.buy_price(feed, _state().items) * portions
		for i in portions:
			var feed_row: Button = null
			for candidate in menu.rows():
				if menu.item_of(candidate) == feed:
					feed_row = candidate
			if feed_row == null:
				failure = "%s is not a row of the shop" % feed
				break
			feed_row.pressed.emit()
			await _animals_frames(2)
		if failure == "" and _state().inventory.count(feed) != had + portions:
			failure = "the shop sold %d of %d %s" % [_state().inventory.count(feed) - had, portions, feed]
	if is_instance_valid(menu):
		menu.close()
	await _animals_frames(2)
	_tree().paused = false
	if failure != "":
		return failure
	_box["animals"] = bought
	return ""

## By day the animal is in the yard of its house, inside the fence; rain sends it in; in the
## evening the yard is empty and it is in its stall in the room, asleep.
func _hen_in_the_coop() -> String:
	if _animals_skip("hen_in_the_coop"):
		return ""
	var herd := _animals_herd()
	var calendar := RpgCalendar.current()
	var weather := RpgFarmMode.current().weather
	weather.force(RpgFarmWeather.SUN)
	if not herd.is_outside():
		return "the animals are indoors at %s on a fair day" % [calendar.clock()]
	for raw: Variant in _animals_bought():
		var animal := JsonUtil.to_dict(raw)
		var id := JsonUtil.to_int(animal["id"])
		var house := herd.data.house(JsonUtil.to_str(animal["house"]))
		var failure: String = await _animals_go(JsonUtil.to_str(house.get("yard_map", "")))
		if failure != "":
			return failure
		var scene := _tree().current_scene
		var yard := scene.get_node_or_null("Yards/%s" % JsonUtil.to_str(animal["house"]).capitalize()) as Node2D
		if yard == null or not (yard.get_meta(&"yard", null) is Rect2i):
			return "the farm has no yard of the %s" % animal["house"]
		# the yard is its cells (T17.14): the map says which cell the animal stands in, on
		# squares and on diamonds
		var cells: Rect2i = yard.get_meta(&"yard")
		var node := herd.node_of(id)
		if node == null:
			return "the %s is not in its yard by day" % animal["kind"]
		if not node.is_roaming() or not cells.has_point(RpgIso.cell_at(scene, node.global_position)):
			return "the %s stands at %s (cell %s), outside its yard %s" % [animal["kind"], node.global_position, RpgIso.cell_at(scene, node.global_position), cells]
		if node.get_node_or_null("Visual") == null:
			return "the %s has no picture" % animal["kind"]
		await _animals_frames(30)
		node = herd.node_of(id)
		if node == null or not cells.has_point(RpgIso.cell_at(scene, node.global_position)):
			return "the %s left its yard" % animal["kind"]
		weather.force(RpgFarmWeather.RAIN)
		await _animals_frames(2)
		if herd.node_of(id) != null:
			return "the %s is out in the rain" % animal["kind"]
		weather.force(RpgFarmWeather.SUN)
		await _animals_frames(2)
		if herd.node_of(id) == null:
			return "the %s did not come out again after the rain" % animal["kind"]
	# the evening
	calendar.pass_minutes(RpgAnimalHouse.EVENING - calendar.minute)
	await _animals_frames(3)
	if not herd.is_night() or herd.is_outside():
		return "the animals are out at %s" % [calendar.clock()]
	for raw: Variant in _animals_bought():
		var animal := JsonUtil.to_dict(raw)
		var id := JsonUtil.to_int(animal["id"])
		if herd.node_of(id) != null:
			return "the %s is still in its yard in the evening" % animal["kind"]
		var house := herd.data.house(JsonUtil.to_str(animal["house"]))
		var failure: String = await _animals_go(JsonUtil.to_str(house.get("map", "")))
		if failure != "":
			return failure
		var scene := _tree().current_scene
		var node := herd.node_of(id)
		if node == null:
			return "the %s is not in the %s in the evening" % [animal["kind"], animal["house"]]
		var stall := scene.get_node_or_null("Markers/Stall%d" % (JsonUtil.to_int(RpgAnimalHouse.animal(id)["stall"]) + 1)) as Node2D
		if stall == null:
			return "the %s has no stall for it" % animal["house"]
		if node.global_position.distance_to(stall.global_position) > RpgUtil.map_tile_px(scene):
			return "the %s is at %s, not in its stall at %s" % [animal["kind"], node.global_position, stall.global_position]
		if not node.asleep or node.is_roaming():
			return "the %s is not asleep in the evening" % animal["kind"]
	return ""

## The trough of the room that is shown, or null.
func _animals_trough(herd: RpgAnimalHouse) -> RpgFarmTrough:
	for node in herd.shown():
		if node is RpgFarmTrough:
			return node as RpgFarmTrough
	return null

## `interact` at the trough with the feed held: one portion goes in and every animal of the
## house is fed; a second portion is not taken.
func _feed_at_the_trough() -> String:
	if _animals_skip("feed_at_the_trough"):
		return ""
	var herd := _animals_herd()
	var feed := herd.data.feed_item
	for raw: Variant in _animals_bought():
		var animal := JsonUtil.to_dict(raw)
		var id := JsonUtil.to_int(animal["id"])
		var house_id := JsonUtil.to_str(animal["house"])
		var failure: String = await _animals_go(JsonUtil.to_str(herd.data.house(house_id).get("map", "")))
		if failure != "":
			return failure
		var trough := _animals_trough(herd)
		if trough == null or trough.house != house_id:
			return "the %s has no trough" % house_id
		if RpgAnimalHouse.trough_full(house_id) or RpgUtil.to_bool(RpgAnimalHouse.animal(id)["fed"]):
			return "the trough of the %s is full before anything went in" % house_id
		if _state().inventory.count(feed) < 2:
			_state().inventory.add(feed, 2)
		var had := _state().inventory.count(feed)
		failure = await _animals_face(trough, RpgUtil.map_tile_px(_tree().current_scene) * 0.5)
		if failure != "":
			return failure
		# with a tool in the hand nothing goes in
		failure = await _animals_hold(&"hoe")
		if failure != "":
			return failure
		await _tap("interact")
		await _animals_frames(3)
		if RpgAnimalHouse.trough_full(house_id) or _state().inventory.count(feed) != had:
			return "`interact` with a hoe in the hand filled the trough"
		failure = await _animals_hold(feed)
		if failure != "":
			return failure
		if not await _interact_until(func() -> bool: return RpgAnimalHouse.trough_full(house_id)):
			return "`interact` with %s in the hand did not fill the trough of the %s" % [feed, house_id]
		if _state().inventory.count(feed) != had - 1:
			return "filling the trough took %d %s, expected one" % [had - _state().inventory.count(feed), feed]
		if not RpgUtil.to_bool(RpgAnimalHouse.animal(id)["fed"]):
			return "the %s is not fed although its trough is full" % animal["kind"]
		var shown := trough.get_node_or_null("Feed") as CanvasItem
		if shown == null or not shown.visible:
			return "the full trough shows no feed"
		await _tap("interact")
		await _animals_frames(3)
		if _state().inventory.count(feed) != had - 1:
			return "a full trough took another portion"
	return ""

## `interact` with the animal pets it, once a day.
func _pet_the_hen() -> String:
	if _animals_skip("pet_the_hen"):
		return ""
	var herd := _animals_herd()
	for raw: Variant in _animals_bought():
		var animal := JsonUtil.to_dict(raw)
		var id := JsonUtil.to_int(animal["id"])
		var house := herd.data.house(JsonUtil.to_str(animal["house"]))
		# wherever it is now: in its stall in the evening, in its yard by day
		var where := JsonUtil.to_str(house.get("yard_map", "")) if herd.is_outside() else JsonUtil.to_str(house.get("map", ""))
		var failure: String = await _animals_go(where)
		if failure != "":
			return failure
		var node := herd.node_of(id)
		if node == null:
			return "the %s is not on the map it should be on (%s)" % [animal["kind"], where]
		node.roam(Rect2())  # it stands still to be petted
		node.move_dir(Vector2.ZERO)
		await _animals_frames(2)
		var tile := float(RpgUtil.map_tile_px(_tree().current_scene))
		failure = await _animals_face(node, tile * 0.6)
		if failure != "":
			return failure
		failure = await _animals_hold(&"hoe")
		if failure != "":
			return failure
		var before := RpgAnimalHouse.friendship(id)
		if RpgUtil.to_bool(RpgAnimalHouse.animal(id)["petted"]):
			return "the %s was petted before anybody touched it" % animal["kind"]
		if not await _interact_until(func() -> bool: return RpgUtil.to_bool(RpgAnimalHouse.animal(id)["petted"])):
			return "`interact` with the %s did not pet it" % animal["kind"]
		if RpgAnimalHouse.friendship(id) != before + RpgAnimalHouse.PET_POINTS:
			return "petting gave %d points, expected %d" % [RpgAnimalHouse.friendship(id) - before, RpgAnimalHouse.PET_POINTS]
		await _tap("interact")
		await _animals_frames(3)
		if RpgAnimalHouse.friendship(id) != before + RpgAnimalHouse.PET_POINTS:
			return "a second petting on the same day gave points"
	return ""

## The night passes: a fed animal has its product in the morning. What lies on the floor of
## the house is picked up there; what the animal carries is taken from it with `interact`.
func _egg_in_the_morning() -> String:
	if _animals_skip("egg_in_the_morning"):
		return ""
	var herd := _animals_herd()
	var mode := RpgFarmMode.current()
	for raw: Variant in _animals_bought():
		var fed := RpgAnimalHouse.animal(JsonUtil.to_int(JsonUtil.to_dict(raw)["id"]))
		if not RpgUtil.to_bool(fed["fed"]) or fed["ready"] != "":
			return "before the night the %s is %s" % [fed["kind"], fed]
	await _weather_end_day()
	mode.weather.force(RpgFarmWeather.SUN)
	await _animals_frames(3)
	var products: Array = []
	for raw: Variant in _animals_bought():
		var animal := JsonUtil.to_dict(raw)
		var id := JsonUtil.to_int(animal["id"])
		var kind_id := JsonUtil.to_str(animal["kind"])
		var house := herd.data.house(JsonUtil.to_str(animal["house"]))
		var row := RpgAnimalHouse.animal(id)
		var product := herd.data.product(kind_id)
		if row["ready"] != String(product):
			return "the fed %s has '%s' ready in the morning, expected %s" % [kind_id, row["ready"], product]
		if RpgUtil.to_bool(row["fed"]) or RpgUtil.to_bool(row["petted"]) or RpgAnimalHouse.trough_full(JsonUtil.to_str(animal["house"])):
			return "the morning did not empty the trough of the %s: %s" % [animal["house"], row]
		if not _state().items.has(product) or RpgShippingBin.price_of(product) <= 0:
			return "%s is no item with a price" % product
		var had := _state().inventory.count(product)
		var failure := ""
		if herd.data.on_the_floor(kind_id):
			failure = await _animals_go(JsonUtil.to_str(house.get("map", "")))
			if failure != "":
				return failure
			var lying: RpgAnimalProduct = null
			for node in herd.shown():
				var found := node as RpgAnimalProduct
				if found != null and found.animal_id == id:
					lying = found
			if lying == null or lying.item_id != product:
				return "no %s lies in the %s in the morning" % [product, animal["house"]]
			if herd.node_of(id) != null:
				return "the %s is indoors on a fair morning" % kind_id
			failure = await _animals_face(lying, RpgUtil.map_tile_px(_tree().current_scene) * 0.5)
		else:
			failure = await _animals_go(JsonUtil.to_str(house.get("yard_map", "")))
			if failure != "":
				return failure
			var node := herd.node_of(id)
			if node == null:
				return "the %s is not in its yard in the morning" % kind_id
			node.roam(Rect2())  # it stands still to give what it has
			node.move_dir(Vector2.ZERO)
			await _animals_frames(2)
			failure = await _animals_face(node, RpgUtil.map_tile_px(_tree().current_scene) * 0.6)
		if failure != "":
			return failure
		failure = await _animals_hold(&"hoe")
		if failure != "":
			return failure
		if not await _interact_until(func() -> bool: return _state().inventory.count(product) == had + 1):
			return "`interact` did not take the %s of the %s" % [product, kind_id]
		if RpgAnimalHouse.animal(id)["ready"] != "":
			return "the %s still has its %s after it was taken" % [kind_id, product]
		await _animals_frames(3)
		for node in herd.shown():
			var left := node as RpgAnimalProduct
			if left != null and left.animal_id == id:
				return "the %s still lies there after it was picked up" % product
		products.append(product)
	_box["animal_products"] = products
	return ""

## What the animals gave is put into the shipping bin and paid for overnight at its price.
func _ship_the_egg() -> String:
	if _animals_skip("ship_the_egg"):
		return ""
	var products: Array = JsonUtil.to_array(_box.get("animal_products", []))
	if products.is_empty():
		return "the animals gave nothing to ship"
	var failure: String = await _animals_go("res://game/maps/farm.tscn")
	if failure != "":
		return failure
	var scene := _tree().current_scene
	var bin := scene.find_child("ShippingBin", true, false) as RpgShippingBin
	var front := scene.get_node_or_null("Markers/BinFront") as Node2D
	if bin == null or front == null:
		return "the farm has no shipping bin with a place to stand before it"
	# as the crop was shipped: from the cell before the bin, looking at it
	var tile := float(RpgUtil.map_tile_px(scene))
	# (the bin's origin is the lower edge of its cell on squares, the middle of it on diamonds)
	var bin_at := bin.global_position + (Vector2.ZERO if RpgIso.footprint_of(scene) != Vector2i.ZERO else Vector2(0.0, -tile * 0.5))
	var to_bin := bin_at - front.global_position
	var looks := "up"
	if absf(to_bin.x) > absf(to_bin.y):
		looks = "left" if to_bin.x < 0.0 else "right"
	elif to_bin.y > 0.0:
		looks = "down"
	failure = await _stand_before(front.global_position, looks, bin_at)
	if failure != "":
		return failure
	var expected := 0
	for raw: Variant in products:
		var product: StringName = raw
		var had := _state().inventory.count(product)
		var in_bin := RpgShippingBin.count(product)
		if had < 1:
			return "the farmer has no %s to ship" % product
		failure = await _animals_hold(product)
		if failure != "":
			return failure
		if not await _interact_until(func() -> bool: return RpgShippingBin.count(product) == in_bin + had):
			return "`interact` with the bin put %d of %d %s into it" % [RpgShippingBin.count(product) - in_bin, had, product]
	for row in RpgShippingBin.contents():
		expected += RpgShippingBin.price_of(StringName(JsonUtil.to_str(row["item_id"]))) * JsonUtil.to_int(row["qty"])
	var gold: int = _state().gold
	await _weather_end_day()
	if _state().gold != gold + expected or expected <= 0:
		return "the night paid %d for what the animals gave, expected %d" % [_state().gold - gold, expected]
	var sold: Array = JsonUtil.to_array(RpgFarmMode.current().day_end.last_sale.get("rows", []))
	for raw: Variant in products:
		var listed := false
		for row: Variant in sold:
			if JsonUtil.to_str(JsonUtil.to_dict(row).get("item_id", "")) == JsonUtil.to_str(raw):
				listed = true
		if not listed:
			return "the morning's summary does not list %s" % raw
	if not RpgShippingBin.is_empty():
		return "the bin is not empty in the morning"
	return ""

# ---------------------------------------------------------------- the added maps (T17.23)
#
# These two steps run only in a farm whose plan has an added map of their kind (a forest, a
# beach); in any other farm each passes with an INFO line. They stand on their own: they go to
# the farm when another map is shown, walk to the added map and back through the real doors,
# lend the tools the bag lacks, and leave the farm's map shown, as they found it.

const ADDED_FOREST := "forest"
const ADDED_BEACH := "beach"
## After this hour the day is ended first, so that neither a cast nor a walk runs into 2:00.
const ADDED_LATEST_HOUR := 18

## The added map of a kind of the stored plan (`farm.map.added`), the first; {} without one.
func _added_entry(kind: String) -> Dictionary:
	for raw: Variant in JsonUtil.to_array(_plan().get("added", [])):
		var entry := JsonUtil.to_dict(raw)
		if JsonUtil.to_str(entry.get("kind", "")) == kind:
			return entry
	return {}

## What the root of an added map is called: `farm_map_1` is `FarmMap1` (added_maps_recipe.gd).
static func _added_root(entry: Dictionary) -> String:
	return JsonUtil.to_str(entry.get("id", "")).capitalize().replace(" ", "")

## The cells of an added map the farmer cannot stand on, from its plan.
func _added_blocked(entry: Dictionary) -> Dictionary:
	var out := {}
	for cell: Variant in JsonUtil.to_array(entry.get("trees", [])):
		out[_cell(cell)] = true
	for cell: Variant in JsonUtil.to_array(entry.get("walls", [])):  # the rock of a cave (T17.24)
		out[_cell(cell)] = true
	for cell: Variant in JsonUtil.to_array(JsonUtil.to_dict(entry.get("water", {})).get("cells", [])):
		out[_cell(cell)] = true
	for key: String in ["scenery", "debris"]:
		for raw: Variant in JsonUtil.to_array(entry.get(key, [])):
			out[_cell(JsonUtil.to_dict(raw).get("cell"))] = true
	return out

## From the farm to an added map through the door of its trail, with the real actions. ""
## when the added map is shown and the farmer stands at its spawn `from_farm`.
func _added_go(entry: Dictionary) -> String:
	var calendar := RpgCalendar.current()
	if calendar != null and (calendar.clock()[0] >= ADDED_LATEST_HOUR or calendar.clock()[0] < 6):
		await _weather_end_day()
	RpgFarmMode.current().weather.force(RpgFarmWeather.SUN)
	var farm: Node = await _forage_farm()
	if farm == null:
		return "the game has no farm map"
	var id := JsonUtil.to_str(entry.get("id", ""))
	var trails := farm.get_node_or_null("Trails")
	if trails == null or trails.get_node_or_null("to_" + id) == null or trails.get_node_or_null("Mark_" + id) == null:
		return "the farm has no trail to %s (Trails/to_%s with its mark)" % [entry.get("name", id), id]
	var failure: String = await _through_the_gap("to_" + id, "from_" + id, _added_root(entry), "from_farm")
	if failure != "":
		return failure
	var scene := _tree().current_scene
	if scene.scene_file_path != "res://" + JsonUtil.to_str(entry.get("map", "")):
		return "the door of the trail led to %s" % scene.scene_file_path
	# a cave (T17.24) is underground: an interior; a forest and a beach are not
	var underground := JsonUtil.to_str(entry.get("kind", "")) == ADDED_CAVE
	if JsonUtil.to_bool(scene.get("is_interior")) != underground:
		return "%s: is it an interior? %s; it is a %s" % [scene.name, scene.get("is_interior"), entry.get("kind")]
	if RpgForage.map_kind(scene) != JsonUtil.to_str(entry.get("kind", "")):
		return "%s says it is a '%s', the plan says %s" % [scene.name, RpgForage.map_kind(scene), entry.get("kind")]
	if RpgField.current() == null or not scene.is_ancestor_of(RpgField.current()):
		return "%s has no field: no tool would work there" % scene.name
	return ""

## Back to the farm through the gap in the edge of an added map.
func _added_back(entry: Dictionary) -> String:
	return await _through_the_gap("to_farm", "from_farm", FARM, "from_" + JsonUtil.to_str(entry.get("id", "")))

## The places of the added map that is shown are its plan's, and a thing that lies at one this
## morning is picked up with `interact`. `_box["added_item"]` is what was picked.
func _added_pick(entry: Dictionary) -> String:
	var scene := _tree().current_scene
	var field := RpgField.current()
	var forage := RpgFarmMode.current().forage
	var spots := JsonUtil.to_array(entry.get("spots", []))
	var places := forage.places_on(scene)
	if spots.is_empty() or scene.get_node_or_null("Forage") == null or places.size() != spots.size():
		return "%s has %d places to forage, its plan lists %d" % [scene.name, places.size(), spots.size()]
	for i in spots.size():
		if field.cell_at(places[i]) != _cell(spots[i]):
			return "Forage/Spot%d of %s lies in %s, the plan says %s" % [i + 1, scene.name, field.cell_at(places[i]), _cell(spots[i])]
	forage.refresh()
	await _forage_frames(3)
	var lying := forage.lying(places.size())
	var shown := forage.shown()
	if shown.is_empty() or shown.size() != lying.size():
		return "%d things lie on %s this morning, %d should (%s)" % [shown.size(), scene.name, lying.size(), RpgField.season_now()]
	var spot: int = shown[0]
	var item := forage.thing_at(spot).item_id
	if item != lying[spot] or not _state().items.has(item):
		return "the thing at Spot%d of %s is '%s', expected '%s' (an item of the game)" % [spot + 1, scene.name, item, lying[spot]]
	var failure: String = await _forage_stand(places[spot], "down")
	if failure != "":
		return failure
	var before := _state().inventory.count(item)
	var picked := false
	for attempt in 3:
		await _tap("interact")
		if await _forage_wait(func() -> bool: return _state().inventory.count(item) == before + 1, 30):
			picked = true
			break
	if not picked:
		return "`interact` at Spot%d of %s did not pick up %s" % [spot + 1, scene.name, item]
	await _forage_frames(2)
	if forage.thing_at(spot) != null or not forage.picked_today().has(spot):
		return "%s still lies at Spot%d of %s, or the flags do not remember that it was picked" % [item, spot + 1, scene.name]
	_box["added_item"] = item
	return ""

## A piece of what lies about on the added map that is shown is cleared with its tool.
func _added_clear(entry: Dictionary) -> String:
	var scene := _tree().current_scene
	var field := RpgField.current()
	var holder := scene.get_node_or_null("YSorted/Entities")
	var listed := JsonUtil.to_array(entry.get("debris", []))
	var things: Array[Node2D] = []
	for node in holder.get_children():
		if node.has_meta(RpgField.CLEAR_META):
			things.append(node as Node2D)
	if things.size() != listed.size() or things.is_empty():
		return "%d things to clear lie on %s, its plan lists %d" % [things.size(), scene.name, listed.size()]
	var blocked := _added_blocked(entry)
	var size := _cell(entry.get("size"))
	for thing in things:
		var kind := str(thing.get_meta(RpgField.CLEAR_META))
		var cell := field.cell_at(thing.global_position)
		for pair: Array in [[Vector2i.UP, "down"], [Vector2i.LEFT, "right"], [Vector2i.RIGHT, "left"], [Vector2i.DOWN, "up"]]:
			var step: Vector2i = pair[0]
			var stand := cell + step
			if blocked.has(stand) or stand.x < 1 or stand.y < 1 or stand.x > size.x - 2 or stand.y > size.y - 2:
				continue
			if not str(thing.get("entity_id")).begins_with(JsonUtil.to_str(entry.get("id", "")) + "_debris_"):
				return "the %s at %s is remembered as '%s': not under the id of its map" % [kind, cell, thing.get("entity_id")]
			return await _clear(thing, kind, cell, stand, str(pair[1]), field, RpgFarmMode.current())
	return "nothing to clear on %s can be reached" % scene.name

## A farm with a forest: the farmer walks to it through the door of its trail, picks up what
## lies there, clears a piece of what lies about, and walks back to the farm.
func _visit_the_forest() -> String:
	var entry := _added_entry(ADDED_FOREST)
	if entry.is_empty():
		print("[rpggen] INFO visit_the_forest: the farm has no forest among its added maps, step passes")
		return ""
	var failure: String = await _added_go(entry)
	if failure == "":
		failure = await _added_pick(entry)
	if failure == "":
		failure = await _added_clear(entry)
	if failure == "":
		failure = await _added_back(entry)
	return failure

## A farm with a beach: the farmer walks to it, casts the rod into the sea from the place the
## plan names and lands a fish of the sea, picks up a thing of the beach, and walks back.
func _fish_at_the_beach() -> String:
	var entry := _added_entry(ADDED_BEACH)
	if entry.is_empty():
		print("[rpggen] INFO fish_at_the_beach: the farm has no beach among its added maps, step passes")
		return ""
	var mode := RpgFarmMode.current()
	var failure: String = await _added_go(entry)
	if failure != "":
		return failure
	var scene := _tree().current_scene
	var field := RpgField.current()
	var from := scene.get_node_or_null("Markers/FishFrom") as Node2D
	var into := scene.get_node_or_null("Markers/FishAt") as Node2D
	if from == null or into == null:
		return "%s has no place to fish from (Markers/FishFrom, Markers/FishAt)" % scene.name
	var at := field.cell_at(from.global_position)
	var wet := field.cell_at(into.global_position)
	var facings := {Vector2i.UP: "up", Vector2i.LEFT: "left", Vector2i.RIGHT: "right", Vector2i.DOWN: "down"}
	if not field.is_water(wet) or field.is_water(at) or not facings.has(wet - at):
		return "the place to fish from (%s) is not beside water (%s)" % [at, wet]
	if RpgFishing.water_kind(field, wet) != "sea":
		return "the water of %s is a %s, not the sea" % [scene.name, RpgFishing.water_kind(field, wet)]
	if not JsonUtil.to_bool(_forage_plan().get("fishing", false)):
		print("[rpggen] INFO fish_at_the_beach: fishing is switched off: nothing is cast")
	else:
		var calendar := RpgCalendar.current()
		var biting := RpgFishing.fish_of(mode.forage.fish, calendar.season_name(), RpgFishing.time_of(calendar.minute), "sea")
		if biting.is_empty():
			return "no fish of the sea bites in %s at %d:00" % [calendar.season_name(), calendar.clock()[0]]
		var sea_items := {}
		for fish_id in biting:
			sea_items[str(mode.forage.fish_entry(fish_id).get("item", ""))] = true
		var counted := func() -> int:
			var total := 0
			for item: String in sea_items.keys():
				total += _state().inventory.count(StringName(item))
			return total
		var before: int = counted.call()
		var lent := not _state().inventory.has(&"fishing_rod")
		if lent:
			_state().inventory.add(&"fishing_rod", 1)
		var slots := _state().inventory.slots
		for i in slots.size():
			if i >= RpgHotbar.SLOTS and StringName(str(slots[i].get("item_id", ""))) == &"fishing_rod":
				slots.insert(0, slots.pop_at(i))
				break
		_box["fish_water"] = wet
		failure = await _land_a_fish(field.cell_center(at), str(facings[wet - at]), at, mode, mode.fishing, mode.tool_for(&"fishing_rod"))
		Input.action_release("use")
		if mode.fishing.is_busy():
			mode.fishing.cancel()
		if lent:
			_state().inventory.remove(&"fishing_rod", 1)
		if failure != "":
			return failure
		var after: int = counted.call()
		if after != before + 1:
			return "the catch at the beach is no fish of the sea (%s)" % [sea_items.keys()]
	failure = await _added_pick(entry)
	if failure != "":
		return failure
	# what lies on a beach is a thing of the beach: its entry names the kind
	var item := str(_box.get("added_item", ""))
	var of_beach := false
	for thing in mode.forage.things:
		if str(thing.get("item", "")) == item and JsonUtil.to_array(thing.get("maps", [])).has(ADDED_BEACH):
			of_beach = true
	if not of_beach:
		return "what was picked up on the beach (%s) is no thing of a beach" % item
	return await _added_back(entry)

# ---------------------------------------------------------------- the cave (T17.24)
#
# These steps come after the added maps: the weapon is bought at the shop and held, the farmer
# walks into the cave (its enemies are there, the farmer has its health, the HUD shows it), an
# enemy is defeated with `use`, what it left is walked over and carried back to the farm, and
# the farmer is defeated once: the day ends and it wakes at the bed, its health full and the
# enemy back. In a farm that does not fight each passes with a note.

const ADDED_CAVE := "cave"

## The cave of the stored plan in a farm that fights; {} (and a note: the step passes) else.
func _cave_or_skip(step_name: String) -> Dictionary:
	var entry := _added_entry(ADDED_CAVE)
	if entry.is_empty() or RpgFarmFight.current() == null:
		print("[rpggen] INFO %s: the farm does not fight (no cave among its added maps), step passes" % step_name)
		return {}
	return entry

## The enemies of the cave that is shown that still stand. (Asked by their ids and their health:
## the class of the action RPG's enemy is not named here, since a farm that does not fight has
## not got it.)
func _cave_enemies() -> Array[Node2D]:
	var out: Array[Node2D] = []
	var scene := _tree().current_scene
	if scene == null:
		return out
	for node in scene.find_children("Enemy*", "", true, false):
		var health := node.get_node_or_null("Health") as RpgHealth
		var body := node as Node2D
		if body != null and RpgFarmFight.is_cave_enemy(str(node.get("entity_id"))) and health != null and not health.is_dead() and not node.is_queued_for_deletion():
			out.append(body)
	return out

## The cave is shown: walked to from the farm when another map is.
func _cave_shown(entry: Dictionary) -> String:
	var scene := _tree().current_scene
	if scene != null and scene.scene_file_path == "res://" + JsonUtil.to_str(entry.get("map", "")):
		return ""
	return await _added_go(entry)

## The HUD's health bar, or null.
func _cave_health_bar() -> ProgressBar:
	var hud := RpgFarmMode.current().get_node_or_null("Hud")
	return hud.get_node_or_null("%HealthBar") as ProgressBar if hud != null else null

## Puts the farmer on a cell beside the one `enemy` stands in, turned to it (the tile ahead,
## on squares and on diamonds), where a swing reaches it.
func _cave_beside(enemy: Node2D, entry: Dictionary) -> void:
	var farmer := _farmer()
	var field := RpgField.current()
	var at := field.cell_at(enemy.global_position)
	var blocked := _added_blocked(entry)
	var size := _cell(entry.get("size"))
	for step: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var stand := at + step
		if blocked.has(stand) or stand.x < 1 or stand.y < 1 or stand.x > size.x - 2 or stand.y > size.y - 2:
			continue
		farmer.global_position = field.cell_center(stand)
		farmer.face_cell(at)
		return

## The weapon is bought at the shop in its hours, with the real menu, and held with its number.
func _buy_a_weapon() -> String:
	var entry := _cave_or_skip("buy_a_weapon")
	if entry.is_empty():
		return ""
	var weapon := RpgFarmFight.WEAPON
	var shop := RpgShopDefinition.load_shop(&"village_shop") as RpgFarmShop
	if shop == null:
		return "game/data/shops/village_shop.tres is not the shop of a farm"
	if not _state().items.has(weapon):
		return "the game has no item %s (game/data/items/%s.tres)" % [weapon, weapon]
	await _animals_shop_hour(shop)
	if not shop.offered(_state().items).has(weapon):
		return "the shop does not offer the weapon: %s" % [shop.offered(_state().items)]
	var price := shop.buy_price(weapon, _state().items)
	if price != RpgFarmFight.WEAPON_PRICE:
		return "the weapon costs %d, the shop's row says %d" % [price, RpgFarmFight.WEAPON_PRICE]
	_state().gold = maxi(_state().gold, price + 100)  # the run may have spent its money
	var gold: int = _state().gold
	var menu: RpgShopMenu = await _ask_for_shop()
	if menu == null:
		return "the shop did not open at %s" % [RpgCalendar.current().clock()]
	var row: Button = null
	for candidate in menu.rows():
		if menu.item_of(candidate) == weapon:
			row = candidate
	var failure := ""
	if row == null:
		failure = "the weapon is not a row of the shop's menu"
	else:
		row.pressed.emit()
		await _frames(2)
		if _state().inventory.count(weapon) != 1 or _state().gold != gold - price:
			failure = "buying the weapon left %d of it and %d money (was %d)" % [_state().inventory.count(weapon), _state().gold, gold]
	if is_instance_valid(menu):
		menu.close()
	await _frames(2)
	if failure != "":
		return failure
	if shop.offered(_state().items).has(weapon):
		return "the weapon is offered again once it is in the bag"
	failure = await _animals_hold(weapon)
	if failure != "":
		return failure
	if RpgFarmMode.current().hotbar.held_item() != weapon:
		return "the weapon is not held"
	return ""

## Through the trail into the cave: an interior with its enemies where the plan puts them, the
## farmer armed, the HUD's health bar full.
func _enter_the_cave() -> String:
	var entry := _cave_or_skip("enter_the_cave")
	if entry.is_empty():
		return ""
	var failure: String = await _added_go(entry)
	if failure != "":
		return failure
	var scene := _tree().current_scene
	var field := RpgField.current()
	var enemies := _cave_enemies()
	var planned := JsonUtil.to_array(entry.get("enemies", []))
	if enemies.size() != planned.size():
		return "%d enemies stand in %s, its plan has %d" % [enemies.size(), scene.name, planned.size()]
	for i in planned.size():
		var at := _cell(JsonUtil.to_dict(planned[i]).get("cell"))
		var found := false
		for enemy in enemies:
			var near := Vector2(field.cell_at(enemy.global_position)).distance_to(Vector2(at)) <= 2.0
			if str(enemy.get("entity_id")) == "%s_enemy_%d" % [entry.get("id"), i + 1] and near:
				found = true
		if not found:
			return "no enemy %s_enemy_%d near %s" % [entry.get("id"), i + 1, at]
	var farmer := _farmer()
	for part: String in [RpgFarmFight.HEALTH_NODE, RpgFarmFight.HURTBOX_NODE, RpgFarmFight.BLADE_NODE]:
		if farmer.get_node_or_null(part) == null:
			return "the farmer has no %s in the cave" % part
	var bar := _cave_health_bar()
	var hp := RpgFarmFight.hit_points()
	if bar == null:
		return "the HUD has no health bar"
	if not bar.is_visible_in_tree() or int(bar.value) != hp[0] or int(bar.max_value) != hp[1] or hp[0] != hp[1]:
		return "the health bar shows %d of %d, the farmer has %s" % [int(bar.value), int(bar.max_value), hp]
	return ""

## An enemy of the cave is defeated with the weapon held and `use`; it leaves a thing of the
## cave. The farmer is kept from harm meanwhile (that is the last step's).
func _defeat_an_enemy() -> String:
	var entry := _cave_or_skip("defeat_an_enemy")
	if entry.is_empty():
		return ""
	var failure: String = await _cave_shown(entry)
	if failure == "":
		failure = await _animals_hold(RpgFarmFight.WEAPON)
	if failure != "":
		return failure
	var fight := RpgFarmFight.current()
	var enemies := _cave_enemies()
	if enemies.is_empty():
		return "no enemy stands in the cave"
	var enemy: Node2D = enemies[0]
	var id := str(enemy.get("entity_id"))
	var health := enemy.get_node_or_null("Health") as RpgHealth
	var start := health.hp()
	fight.last_drop = null
	var hurtbox := _farmer().get_node_or_null(RpgFarmFight.HURTBOX_NODE) as RpgHurtbox
	var swings := 0
	for attempt in 30:
		if not is_instance_valid(enemy) or not is_instance_valid(health) or health.is_dead():
			break
		hurtbox.make_invulnerable(2.0)
		_cave_beside(enemy, entry)
		await _frames(2)
		await _tap("use")
		swings += 1
		await _wait_for(func() -> bool: return not _farmer().is_busy(), 60)
	if not RpgUtil.to_bool(_state().get_flag(id, "defeated", false)):
		return "%s still stands after %d swings (it had %d hit points)" % [id, swings, start]
	if not await _wait_for(func() -> bool: return fight.last_drop != null and is_instance_valid(fight.last_drop) and fight.last_drop.is_inside_tree(), 30):
		return "%s left nothing of the cave" % id
	var item := fight.last_drop.item_id
	if not fight.cave_things().has(item):
		return "%s left %s, which is no thing of the cave" % [id, item]
	_box["cave_enemy"] = id
	_box["cave_drop"] = item
	print("[rpggen] INFO defeat_an_enemy: %s fell after %d swings and left %s" % [id, swings, item])
	return ""

## What the enemy left is walked over (into the bag), and carried back to the farm.
func _bring_back_what_it_left() -> String:
	var entry := _cave_or_skip("bring_back_what_it_left")
	if entry.is_empty():
		return ""
	var fight := RpgFarmFight.current()
	var drop := fight.last_drop
	if drop == null or not is_instance_valid(drop) or not drop.is_inside_tree():
		return "nothing that an enemy left lies in the cave"
	var item := drop.item_id
	var before := _state().inventory.count(item)
	var farmer := _farmer()
	var tile := float(RpgUtil.map_tile_px(_tree().current_scene))
	farmer.global_position = drop.global_position + Vector2(-tile, 0.0)
	await _frames(2)
	var target := drop.global_position
	await SmokeMap.walk_toward(farmer, target, 180, func() -> bool: return _state().inventory.count(item) > before)
	if _state().inventory.count(item) != before + 1:
		return "walking over %s did not put it into the bag" % item
	# and a thing of the cave that lies at one of its places is picked up with `interact`
	var failure: String = await _added_pick(entry)
	if failure != "":
		return failure
	var found := str(_box.get("added_item", ""))
	if not RpgFarmFight.current().cave_things().has(StringName(found)):
		return "what lay in the cave (%s) is no thing of a cave" % found
	var carried := _state().inventory.count(item)
	failure = await _added_back(entry)
	if failure != "":
		return failure
	if _state().inventory.count(item) != carried:
		return "%s did not come back to the farm in the bag" % item
	var price := 0
	for thing in RpgFarmMode.current().forage.things:
		if str(thing.get("item", "")) == String(item):
			price = RpgUtil.to_int(thing.get("price", 0))
	var def: RpgItemDefinition = _state().items.get(item)
	if price <= 0 or def == null or def.value != price:
		return "%s is worth %d in the table and %d as an item: it cannot be sold" % [item, price, def.value if def != null else -1]
	return ""

## In the cave again, the farmer at its last hit point beside an enemy: the enemy's blow
## defeats it, the day ends, and it wakes at the bed with its health full and the enemy that
## fell back in its place.
func _defeated_and_wake_at_home() -> String:
	var entry := _cave_or_skip("defeated_and_wake_at_home")
	if entry.is_empty():
		return ""
	var failure: String = await _cave_shown(entry)
	if failure != "":
		return failure
	var fight := RpgFarmFight.current()
	var day_end := RpgFarmMode.current().day_end
	var calendar := RpgCalendar.current()
	var today := calendar.today()
	var enemies := _cave_enemies()
	if enemies.is_empty():
		return "no enemy stands in the cave to be defeated by"
	_state().player_stats.hp = 1
	fight.health_changed.emit(1, RpgFarmFight.hit_points()[1])
	await _frames(2)
	var bar := _cave_health_bar()
	if bar == null or int(bar.value) != 1:
		return "the health bar does not show the last hit point"
	var enemy: Node2D = enemies[0]
	var struck := false
	for attempt in 3:
		if fight.down or not is_instance_valid(enemy):
			break
		_cave_beside(enemy, entry)
		if await _wait_for(func() -> bool: return fight.down, 240):
			struck = true
	if not fight.down and is_instance_valid(enemy):
		# an enemy that keeps its distance (a shooter that missed) strikes through its hitbox
		var hitbox := enemy.get_node_or_null("AttackHitbox") as RpgHitbox
		var hurtbox := _farmer().get_node_or_null(RpgFarmFight.HURTBOX_NODE) as RpgHurtbox
		if hitbox != null and hurtbox != null:
			hurtbox.invulnerable_until_ms = 0
			hurtbox.receive(hitbox.build_info(hurtbox))
	if not fight.down:
		return "the farmer at its last hit point was not defeated"
	print("[rpggen] INFO defeated_and_wake_at_home: the farmer fell to %s" % ("an enemy's blow" if struck else "the enemy's hitbox, struck by the step (no blow came in 12 s)"))
	if not await _wait_for(func() -> bool: return calendar.today() == today + 1, 300):
		return "being defeated did not end the day"
	if not await _wait_for_map(HOUSE, 600):
		return "the farmer did not wake in the farmhouse"
	await _frames(5)
	if day_end.summary() != null:
		day_end.summary().close()
		await _frames(2)
	_tree().paused = false
	if day_end.last_night != RpgDayEnd.PASSED_OUT or not day_end.knocked_out:
		return "the night was '%s' (knocked out: %s), not a defeat" % [day_end.last_night, day_end.knocked_out]
	var home := RpgBed.home(_state())
	var farmer := _farmer()
	if home.is_empty() or farmer == null:
		return "the game has no bed, or no farmer woke"
	var bed_at: Vector2 = home["position"]
	if farmer.global_position.distance_to(bed_at) > 24.0:
		return "the farmer woke at %s, the bed is at %s" % [farmer.global_position, bed_at]
	var hp := RpgFarmFight.hit_points()
	if fight.down or hp[0] != hp[1] or not farmer.input_enabled:
		return "the morning after: down %s, %s hit points, input %s" % [fight.down, hp, farmer.input_enabled]
	bar = _cave_health_bar()
	if bar == null or int(bar.value) != hp[1]:
		return "the health bar is not full in the morning"
	var fallen := str(_box.get("cave_enemy", ""))
	if fallen != "" and RpgUtil.to_bool(_state().get_flag(fallen, "defeated", false)):
		return "%s did not come back in the morning" % fallen
	return ""

# ---------------------------------------------------------------- saving and loading (T17.18)
#
# This step stands on its own too: it goes to the farm when another map is shown and works
# cells of its own through the field. It is the game's own save and load (SaveManager, into the
# folder of this smoke run), and it is the last step: nothing after it counts on the day.

## The slot of this step: the last one (the shared steps use the first and empty all three).
const SAVE_SLOT := RpgSaveManager.SLOTS

## True when two saved values are the same: dictionaries and lists piece by piece, numbers as
## numbers (a number that went through a save file may come back as a float).
static func _save_same(a: Variant, b: Variant) -> bool:
	if a is Dictionary and b is Dictionary:
		var da: Dictionary = a
		var db: Dictionary = b
		if da.size() != db.size():
			return false
		for key: Variant in da.keys():
			if not db.has(key) or not _save_same(da[key], db[key]):
				return false
		return true
	if a is Array and b is Array:
		var aa: Array = a
		var ab: Array = b
		if aa.size() != ab.size():
			return false
		for i in aa.size():
			if not _save_same(aa[i], ab[i]):
				return false
		return true
	if (a is int or a is float) and (b is int or b is float):
		return is_equal_approx(JsonUtil.to_float(a), JsonUtil.to_float(b))
	if (a is String or a is StringName) and (b is String or b is StringName):
		return str(a) == str(b)
	return typeof(a) == typeof(b) and a == b

## What a save holds of a farm, besides its field: {date, gold, bag, herd, friends, energy,
## forage}. `forage` is what was picked up, by map (the flag of RpgForage): the places of the
## added maps are among them (T17.23).
func _save_snapshot() -> Dictionary:
	var friends := RpgFriendship.current()
	var herd: Array = []
	for row in RpgAnimalHouse.herd():
		herd.append(row.duplicate(true))
	return {
		"date": RpgCalendar.current().to_dict(),
		"gold": _state().gold,
		"bag": _state().inventory.to_array(),
		"herd": herd,
		"friends": friends.to_dict() if friends != null else {},
		"energy": RpgFarmMode.current().energy.value,
		"forage": JsonUtil.to_dict(_state().get_flag(RpgForage.FLAG_ENTITY, RpgForage.PICKED_KEY, {})).duplicate(true),
		"events": _events_snapshot(),  # the festivals' state (T17.25): {} in a farm without them
		"marriage": _marriage_snapshot(),  # who is courted, engaged, married (T17.26): {} without
	}

## The field of the map that is shown against what it was, cell by cell: the saved state of
## every cell, what the field answers for it, the crop that stands on it and the tile of wet
## soil. "" when it is what it was.
func _save_field_differs(field: RpgField, before: Dictionary) -> String:
	var after := field.to_dict()
	if after.size() != before.size():
		return "the field has %d worked cells after loading, it had %d" % [after.size(), before.size()]
	var soil := field.get_node_or_null(field.soil_path) as TileMapLayer
	for key: Variant in before.keys():
		var cell := RpgField.cell_of(JsonUtil.to_str(key))
		if not after.has(key):
			return "the cell %s is no longer worked after loading" % cell
		var was := JsonUtil.to_dict(before[key])
		var now := JsonUtil.to_dict(after[key])
		for part: String in ["w", "crop", "grown", "dead", "idle"]:
			if not _save_same(was.get(part), now.get(part)):
				return "the cell %s has %s = %s after loading, it had %s" % [cell, part, now.get(part), was.get(part)]
		var crop := JsonUtil.to_str(was.get("crop", ""))
		var was_wet := JsonUtil.to_bool(was.get("w", false))
		if field.is_watered(cell) != was_wet or field.crop_at(cell) != crop or field.grown_at(cell) != JsonUtil.to_int(was.get("grown", 0)):
			return "the field answers for %s: wet %s, crop '%s', grown %d; it was %s" % [cell, field.is_watered(cell), field.crop_at(cell), field.grown_at(cell), was]
		if (field.crop_node(cell) != null) != (crop != ""):
			return "the cell %s %s after loading" % [cell, "shows no crop" if crop != "" else "shows a crop it has not"]
		if soil != null:
			var want_source := field.watered_source if was_wet else field.tilled_source
			var want_tile := field.watered_tile if was_wet else field.tilled_tile
			if soil.get_cell_source_id(cell) != want_source or soil.get_cell_atlas_coords(cell) != want_tile:
				return "the Soil layer shows the tile %s of source %d at %s after loading, expected %s of %d (%s soil)" % [soil.get_cell_atlas_coords(cell), soil.get_cell_source_id(cell), cell, want_tile, want_source, "wet" if was_wet else "dry"]
	return ""

func _save_and_load() -> String:
	var mode := RpgFarmMode.current()
	var calendar := RpgCalendar.current()
	var save := RpgUtil.save_manager()
	var router := RpgUtil.router()
	if mode == null or calendar == null or save == null or router == null or _state() == null:
		return "the game has no farm's mode, calendar, SaveManager or SceneRouter"
	var field: RpgField = await _weather_field()
	if field == null:
		return "no map of the game has a field"
	# the field gets something of every kind a save has to keep: wet soil with a crop of the
	# season on it, and dry soil with nothing
	var in_season := mode.crops.of_season(calendar.season_name())
	if in_season.is_empty():
		return "no crop grows in %s" % calendar.season_name()
	var crop := in_season[0]
	var found: Variant = _weather_free_cell(field)
	if found == null:
		return "the plot has no free cell to till"
	var wet: Vector2i = found
	if not field.till(wet) or not field.plant(wet, crop):
		return "%s could not be planted in %s" % [crop, wet]
	if not field.is_watered(wet) and not field.water(wet):
		return "the cell %s could not be watered" % wet
	found = _weather_free_cell(field)
	if found == null:
		return "the plot has no second free cell to till"
	var dry: Vector2i = found
	if not field.till(dry):
		return "the cell %s could not be tilled" % dry
	await _weather_frames(3)
	var map_path := _tree().current_scene.scene_file_path
	var cells := field.to_dict()
	_events_mark(true)  # an event added at run time, for the save to keep (T17.25)
	var kept := _save_snapshot()
	# in a farm with added maps the last thing that was picked up lay on one of them (T17.23)
	if not JsonUtil.to_array(_plan().get("added", [])).is_empty():
		var on_added := false
		for key: Variant in JsonUtil.to_dict(JsonUtil.to_dict(kept["forage"]).get("spots", {})).keys():
			on_added = on_added or str(key).begins_with("farm_map_")
		if not on_added:
			return "the flags name no place of an added map where something was picked up: %s" % [kept["forage"]]
	if not cells.has(RpgField.cell_name(wet)) or not cells.has(RpgField.cell_name(dry)) or field.crop_at(wet) != crop or not field.is_watered(wet):
		return "the field does not hold the two cells that were worked: %s" % cells
	save.set("dir", SmokeRunner.save_dir())
	save.delete(SAVE_SLOT)
	if not save.save(SAVE_SLOT):
		return "SaveManager.save(%d) returned false" % SAVE_SLOT
	var header := save.header(SAVE_SLOT)
	if JsonUtil.to_int(header.get("gold", -1)) != JsonUtil.to_int(kept["gold"]):
		return "the header of the save names %s coins, the farmer has %s" % [header.get("gold"), kept["gold"]]
	# everything is changed: the crop is cut and a third cell tilled, a night passes (the date,
	# the wet soil, the herd), and the money, the bag, the energy and a friendship
	if not field.remove_crop(wet):
		return "the crop in %s could not be cut" % wet
	found = _weather_free_cell(field)
	if found != null:
		var third: Vector2i = found
		field.till(third)
	await _weather_end_day()
	_state().gold = JsonUtil.to_int(kept["gold"]) + 321
	_state().inventory.add(StringName(JsonUtil.to_str(mode.crops.crop(crop).get("seed", ""))), 2)
	mode.energy.value = 7 if JsonUtil.to_int(kept["energy"]) != 7 else 9
	_state().set_flag(RpgForage.FLAG_ENTITY, RpgForage.PICKED_KEY, {"day": -7, "spots": {"nowhere": [0]}})
	var friends := RpgFriendship.current()
	if friends != null and not friends.order.is_empty():
		friends.add_points(friends.order[0], 40)
	var herd := RpgAnimalHouse.current()
	for row in RpgAnimalHouse.herd():
		if herd != null:
			herd.pet(JsonUtil.to_int(row["id"]))
	_events_mark(false)  # ... and it is taken away again before the load (T17.25)
	if RpgMarriage.current() != null:  # and the marriage's state changes (T17.26)
		_state().set_flag(RpgMarriage.FLAG_ENTITY, RpgMarriage.SPOUSE_KEY, "smoke_nobody")
	await _weather_frames(2)
	var changed := _save_snapshot()
	for part: String in ["date", "gold", "bag", "energy", "forage"]:
		if _save_same(changed[part], kept[part]):
			return "the %s did not change before the load: the comparison would prove nothing" % part
	if not JsonUtil.to_dict(kept["events"]).is_empty() and _save_same(changed["events"], kept["events"]):
		return "the festivals' state did not change before the load: the comparison would prove nothing"
	if not JsonUtil.to_dict(kept["marriage"]).is_empty() and _save_same(changed["marriage"], kept["marriage"]):
		return "the marriage's state did not change before the load: the comparison would prove nothing"
	if _save_same(field.to_dict(), cells):
		return "the field did not change before the load: the comparison would prove nothing"
	if not JsonUtil.to_array(kept["herd"]).is_empty() and _save_same(changed["herd"], kept["herd"]):
		return "the herd did not change before the load: the comparison would prove nothing"
	# the game's own load
	var old_field := field.get_instance_id()
	if not save.load(SAVE_SLOT):
		return "SaveManager.load(%d) returned false" % SAVE_SLOT
	var back: bool = await _weather_wait(func() -> bool: return _save_is_back(map_path, old_field), 900)
	if not back:
		return "the map %s did not come back after loading" % map_path
	await _weather_frames(5)
	_tree().paused = false
	if _farmer() == null:
		return "no farmer after loading"
	field = RpgField.current()
	var failure := _save_field_differs(field, cells)
	if failure != "":
		return failure
	var loaded := _save_snapshot()
	var date := JsonUtil.to_dict(kept["date"])
	if calendar.day != JsonUtil.to_int(date["day"]) or calendar.season != JsonUtil.to_int(date["season"]) or calendar.year != JsonUtil.to_int(date["year"]) or calendar.minute != JsonUtil.to_int(date["minute"]):
		return "the date after loading is %s, it was %s" % [calendar.to_dict(), date]
	for part: String in ["gold", "bag", "herd", "friends", "energy", "forage", "events", "marriage"]:
		if not _save_same(loaded[part], kept[part]):
			return "the %s after loading: %s, it was %s" % [part, loaded[part], kept[part]]
	save.delete(SAVE_SLOT)
	return ""

## True when the map `map_path` is shown anew (its field is not the one that was there), and the
## router is idle.
func _save_is_back(map_path: String, old_field: int) -> bool:
	var router := RpgUtil.router()
	var scene := _tree().current_scene
	var field := RpgField.current()
	return router != null and not router.is_busy() and scene != null and scene.scene_file_path == map_path and field != null and field.is_inside_tree() and field.get_instance_id() != old_field

# ---------------------------------------------------------------- festivals and birthdays (T17.25)
#
# These steps stand on their own, before the last: they go to the map they need, move the
# calendar on by ending days (`_weather_end_day`), and count on nothing an earlier step left
# behind. In a farm without festivals (`starter_map.festivals` off) each passes with a note.

const EVENTS_HOUSE := "res://game/maps/farm_house.tscn"
const EVENTS_FARM := "res://game/maps/farm.tscn"
const EVENTS_VILLAGE := "res://game/maps/starter_map.tscn"

## The events of the game, or null, with an INFO line, in a farm that has none.
func _events_or_skip(step_name: String) -> RpgFarmEvents:
	var events := RpgFarmEvents.current()
	# a farm with marriage and without festivals has the events for its wedding only (T17.26)
	if events == null or not events.with_files:
		print("[rpggen] INFO %s: the farm has no festivals, step passes" % step_name)
		return null
	return events

## The first hour of a fair day at which a festival's people stand on the square.
func _events_hour(hour: int) -> void:
	var calendar := RpgCalendar.current()
	if calendar.minute < hour * 60:
		calendar.pass_minutes(hour * 60 - calendar.minute)
	RpgFarmMode.current().weather.force(RpgFarmWeather.SUN)
	await _frames(2)

## What is wrong with the calendar page that is shown, or "".
func _events_page_problem(page: RpgCalendarPage, events: RpgFarmEvents) -> String:
	var calendar := RpgCalendar.current()
	if page == null:
		return "no calendar page is shown"
	if page.heading() != RpgCalendarPage.heading_text(calendar.season, calendar.year):
		return "the calendar is headed '%s' in %s of year %d" % [page.heading(), calendar.season_name(), calendar.year]
	if page.day_count() != calendar.days_per_season:
		return "the calendar shows %d days, a season has %d" % [page.day_count(), calendar.days_per_season]
	if not page.mark_of(calendar.day).ends_with("today"):
		return "day %d is marked '%s', not as today" % [calendar.day, page.mark_of(calendar.day)]
	for row in events.season_rows(calendar.season, calendar.year):
		if not page.listed().contains(JsonUtil.to_str(row["text"])):
			return "the calendar does not list '%s': %s" % [row["text"], page.listed()]
		var mark := page.mark_of(JsonUtil.to_int(row["day"]))
		if mark == "" or mark == "today":
			return "day %d (%s) is not marked" % [row["day"], row["text"]]
	return ""

## The calendar on the wall of the farmhouse opens the page of the season with `interact`, and
## `cancel` closes it; the pause menu has the page too (that is where a farm from before the
## card has it: its room is never built again).
func _read_the_calendar() -> String:
	var events := _events_or_skip("read_the_calendar")
	if events == null:
		return ""
	var failure := ""
	if ResourceLoader.exists(EVENTS_HOUSE):
		failure = await _animals_go(EVENTS_HOUSE)
		if failure != "":
			return failure
	var scene := _tree().current_scene
	var wall := scene.find_child("WallCalendar", true, false) as RpgWallCalendar if scene != null else null
	if wall == null:
		print("[rpggen] INFO read_the_calendar: the farmhouse has no calendar on its wall (a room from before the card): the pause menu's page is read")
	else:
		failure = await _hold(&"hoe")
		if failure == "":
			if RpgIso.footprint_of(scene) != Vector2i.ZERO:
				failure = await _forage_stand(wall.global_position, "down")  # a board on its cell
			else:
				failure = await _stand(wall.global_position + Vector2(0.0, 10.0), "up")
		if failure != "":
			return failure
		if not await _interact_until(func() -> bool: return events.is_calendar_open()):
			return "`interact` with the calendar on the wall did not open it"
		await _frames(3)
		if not _tree().paused:
			return "the game goes on behind the calendar"
		failure = _events_page_problem(events.open_calendar(), events)
		await _frames(40)  # it is looked at
		await _shared._press("cancel")
		if not await _wait_for(func() -> bool: return not events.is_calendar_open(), 60):
			return "`cancel` did not close the calendar"
		await _frames(6)
		if _tree().paused or events.is_calendar_open():
			return "the game did not go on after the calendar was closed"
		if failure != "":
			return failure
	# the pause menu's page
	var controller := _controller()
	var menu := controller.open_pause() if controller != null else null
	await _frames(3)
	if menu == null:
		return "the pause menu did not open"
	var button := menu.find_child(RpgCalendarPage.BUTTON_NAME, true, false) as Button
	var page: RpgCalendarPage = null
	if button == null:
		failure = "the pause menu has no Calendar button"
	else:
		button.pressed.emit()
		await _frames(3)
		page = menu.get_node_or_null(RpgCalendarPage.PAGE_NAME) as RpgCalendarPage
		failure = _events_page_problem(page, events)
	if page != null and is_instance_valid(page):
		page.close()
		await _frames(2)
	if is_instance_valid(menu):
		menu.call(&"close")
	await _frames(3)
	_tree().paused = false
	return failure

## The next birthday of somebody of the village is waited for by ending days. On it the person
## says so, a gift with `interact` counts as RpgFriendship.birthday_points says and is none of
## the week's two, and the People page names the day.
func _birthday_gift() -> String:
	var events := _events_or_skip("birthday_gift")
	if events == null:
		return ""
	var friends := RpgFriendship.current()
	var calendar := RpgCalendar.current()
	var state := _state()
	if friends == null or friends.order.is_empty():
		return "game/data/people.json lists nobody"
	for person_id in friends.order:
		if events.birthday_of(person_id).is_empty():
			return "%s has no birthday (game/data/people.json, generated/data/people.json)" % person_id
	# the first day from tomorrow on that is somebody's birthday and no festival
	var id := ""
	for ahead in range(1, 4 * calendar.days_per_season + 1):
		var day := events.events_of(calendar.today() + ahead)
		if not RpgFarmEvents.festival_of(day).is_empty():
			continue
		for row in day:
			if id == "" and JsonUtil.to_str(row.get("kind", "")) == RpgFarmEvents.BIRTHDAY:
				id = JsonUtil.to_str(row.get("person", ""))
		if id != "":
			for i in ahead:
				await _weather_end_day()
			break
	if id == "" or not events.is_birthday(id):
		return "no birthday within a year (%s is not today)" % id
	await _events_hour(11)
	var failure: String = await _animals_go(EVENTS_VILLAGE)
	if failure != "":
		return failure
	var npc := _person_node(id)
	if npc == null or npc.schedule() == null:
		return "%s has no NPC in the village" % id
	var schedule := npc.schedule()
	if not await _wait_for(func() -> bool: return not schedule.walking() and not schedule.away(), 600):
		return "%s is not in the village on its birthday at 11:00" % id
	# the person says so: the line of its dialogue that the atom chooses
	var said := false
	var dialogue := npc.dialogue as RpgDialogueResource
	if dialogue != null:
		for line in dialogue.lines:
			said = said or line.condition == "birthday:%s" % id
	if not said:
		print("[rpggen] INFO birthday_gift: the dialogue of %s has no line for its birthday (a file from before the card)" % id)
	if not RpgCondition.evaluate("birthday:%s" % id):
		return "the atom birthday:%s is false on the birthday of %s" % [id, id]
	# a gift the person does not dislike, so that the day shows
	var gift := &"potion"
	for taste: String in [RpgFriendship.LOVES, RpgFriendship.LIKES]:
		for raw: Variant in JsonUtil.to_array(friends.person(id).get(taste, [])):
			if gift == &"potion" and state.items.has(StringName(JsonUtil.to_str(raw))):
				gift = StringName(JsonUtil.to_str(raw))
	if not state.items.has(gift):
		return "the game has no %s to give" % gift
	if not state.inventory.has(gift):
		state.inventory.add(gift, 1)
	failure = await _animals_hold(gift)
	if failure == "":
		failure = await _stand(_below(npc, 9.0), "up")
	if failure != "":
		return failure
	var taste_now := friends.taste_of(id, gift)
	var points := friends.points_of(id)
	var left := friends.gifts_left(id)
	var had: int = state.inventory.count(gift)
	var wanted := clampi(points + RpgFriendship.birthday_points(taste_now), 0, RpgFriendship.MAX_POINTS)
	if not events.birthday_gift_open(id):
		return "%s has had the gift of its birthday already" % id
	if not await _interact_until(func() -> bool: return not events.birthday_gift_open(id)):
		return "`interact` with %s held did not give it to %s on its birthday" % [gift, id]
	await _frames(4)
	if state.inventory.count(gift) != had - 1:
		return "the gift took %d of %s out of the bag, expected 1" % [had - state.inventory.count(gift), gift]
	if friends.points_of(id) != wanted:
		return "%s has %d points after a birthday gift it %s (%d before), expected %d" % [id, friends.points_of(id), taste_now, points, wanted]
	if taste_now != RpgFriendship.DISLIKES and wanted < RpgFriendship.MAX_POINTS and friends.points_of(id) - points != RpgFriendship.gift_points(taste_now) * RpgFriendship.BIRTHDAY_FACTOR:
		return "the birthday gift gave %d points, not %d times %d" % [friends.points_of(id) - points, RpgFriendship.BIRTHDAY_FACTOR, RpgFriendship.gift_points(taste_now)]
	if friends.gifts_left(id) != left:
		return "the birthday gift used up one of the week's gifts (%d left, %d before)" % [friends.gifts_left(id), left]
	var told := events.birthday_text(id)
	if told == "" or not RpgPeoplePage.detail_text(friends, id).contains(told):
		return "the People page does not name the birthday of %s: %s" % [id, RpgPeoplePage.detail_text(friends, id)]
	_box["birthday"] = id
	return ""

## Days are ended until tomorrow is a festival: the weather's sign by the house says so (read
## with `interact`), and so does the atom the people's dialogue asks.
func _festival_is_announced() -> String:
	var events := _events_or_skip("festival_is_announced")
	if events == null:
		return ""
	var calendar := RpgCalendar.current()
	var mode := RpgFarmMode.current()
	if events.events.is_empty():
		return "game/data/events.json lists no festival"
	var guard := 0
	while events.festival_tomorrow().is_empty() and guard <= 4 * calendar.days_per_season:
		if RpgCondition.evaluate("festival_tomorrow"):
			return "the people announce a festival on %s %d, and none is tomorrow" % [calendar.season_name(), calendar.day]
		await _weather_end_day()
		guard += 1
	var coming := events.festival_tomorrow()
	if coming.is_empty():
		return "no festival within a year"
	var title := RpgFarmEvents.event_name(coming)
	var line := events.tomorrow_text()
	if line == "" or not line.contains(title):
		return "the day before the %s is announced as '%s'" % [title, line]
	if not mode.weather.forecast_text().contains(line):
		return "the forecast does not say that the %s is tomorrow: %s" % [title, mode.weather.forecast_text()]
	if not RpgCondition.evaluate("festival_tomorrow") or RpgCondition.evaluate("festival"):
		return "the people do not say that the %s is tomorrow" % title
	if events.is_festival():
		return "today is a festival already"
	# the sign by the house, read with `interact`
	var failure: String = await _animals_go(EVENTS_FARM)
	if failure != "":
		return failure
	var found := _tree().current_scene.find_child("WeatherSign", true, false) as RpgWeatherSign
	if found == null:
		print("[rpggen] INFO festival_is_announced: the farm has no weather sign, its reading is taken from the weather")
		return ""
	if not found.reading().contains(line):
		return "the sign reads '%s' on the day before the %s" % [found.reading(), title]
	var bus := RpgUtil.events()
	var toasts: Array[String] = []
	var on_toast := func(text: String) -> void: toasts.append(text)
	bus.notify.connect(on_toast)
	failure = await _hold(&"hoe")
	if failure == "":
		failure = await _stand_before(_below(found, 8.0), "up", found.global_position)
	if failure == "":
		var read := func() -> bool:
			for text in toasts:
				if text.contains(line):
					return true
			return false
		if not await _interact_until(read):
			failure = "`interact` with the sign did not say that the %s is tomorrow: %s" % [title, toasts]
	bus.notify.disconnect(on_toast)
	return failure

## What is wrong with a day of the year, or "": a festival is on the day its entry names and on
## no other, and on it the shop is closed and says why and everybody is sent to the square.
func _events_day_problem(events: RpgFarmEvents, shop: RpgFarmShop, expected: Dictionary) -> String:
	var calendar := RpgCalendar.current()
	var friends := RpgFriendship.current()
	var today := "%s %d" % [calendar.season_name(), calendar.day]
	var entry := events.festival()
	var wanted := JsonUtil.to_str(expected.get("%d:%d" % [calendar.season, calendar.day], ""))
	if JsonUtil.to_str(entry.get("id", "")) != wanted:
		return "%s: the festival is '%s', expected '%s'" % [today, entry.get("id", ""), wanted]
	if wanted == "":
		if RpgFarmShop.day_off_reason() != "" or RpgCondition.evaluate("festival"):
			return "%s is no festival, and the shop has a day off" % today
		if friends != null and not friends.order.is_empty() and not events.schedule_override(friends.order[0], 12).is_empty():
			return "%s is no festival, and the people are sent somewhere" % today
		return ""
	var title := RpgFarmEvents.event_name(entry)
	calendar.pass_minutes(12 * 60 - calendar.minute)
	if shop != null and (shop.is_open() or not shop.closed_all_day() or not shop.closed_reason().contains(title)):
		return "%s: the shop says '%s' at noon of the %s" % [today, shop.closed_reason(), title]
	if not RpgCondition.evaluate("festival") or not RpgCondition.evaluate("event:%s" % JsonUtil.to_str(entry.get("kind", ""))):
		return "%s: the people do not know of the %s" % [today, title]
	var place := JsonUtil.to_str(entry.get("place", ""))
	if friends != null:
		for id in friends.order:
			var sent := events.schedule_override(id, 12)
			if not JsonUtil.to_str(sent.get("place", "")).begins_with(place) or JsonUtil.to_str(sent.get("map", "")) != JsonUtil.to_str(entry.get("map", "")):
				return "%s: %s is sent to %s at noon of the %s, not to %s" % [today, id, sent, title, place]
	return ""

## A year is run by ending days: every festival of game/data/events.json happens on its day and
## on no other, with the shop closed and the people sent to the square. The year ends on the
## morning of the egg hunt (the step after this one plays it), when the year has one.
func _a_year_of_festivals() -> String:
	var events := _events_or_skip("a_year_of_festivals")
	if events == null:
		return ""
	var calendar := RpgCalendar.current()
	var shop := RpgShopDefinition.load_shop(&"village_shop") as RpgFarmShop
	var length := calendar.days_per_season
	var expected := {}
	var hunt := false
	for entry in events.events:
		var key := "%d:%d" % [RpgFarmEvents.season_index(entry.get("season")), RpgFarmEvents.day_in(JsonUtil.to_int(entry.get("day", 0)), length)]
		if expected.has(key):
			return "two festivals on one day: %s and %s" % [expected[key], entry.get("id")]
		expected[key] = JsonUtil.to_str(entry.get("id", ""))
		hunt = hunt or JsonUtil.to_str(entry.get("kind", "")) == RpgFarmEvents.EGG_HUNT
	if expected.is_empty():
		return "game/data/events.json lists no festival"
	var began: Array[String] = []
	var ended: Array[String] = []
	var on_began := func(entry: Dictionary) -> void: began.append(JsonUtil.to_str(entry.get("id", "")))
	var on_ended := func(entry: Dictionary) -> void: ended.append(JsonUtil.to_str(entry.get("id", "")))
	events.festival_began.connect(on_began)
	events.festival_ended.connect(on_ended)
	var seen := {}
	var failure := ""
	var days := 0
	var year := 4 * length
	while failure == "" and days < 2 * year:
		await _weather_end_day()
		days += 1
		failure = _events_day_problem(events, shop, expected)
		var entry := events.festival()
		if not entry.is_empty():
			seen[JsonUtil.to_str(entry.get("id", ""))] = true
		if days >= year and (not hunt or JsonUtil.to_str(entry.get("kind", "")) == RpgFarmEvents.EGG_HUNT):
			break
	events.festival_began.disconnect(on_began)
	events.festival_ended.disconnect(on_ended)
	if failure != "":
		return failure
	if seen.size() != expected.size():
		return "%d of the %d festivals of events.json happened in a year: %s" % [seen.size(), expected.size(), seen.keys()]
	if began.size() < expected.size() or began.size() - ended.size() > 1 or began.size() < ended.size():
		return "%d festivals began and %d ended in %d days" % [began.size(), ended.size(), days]
	if hunt and JsonUtil.to_str(events.festival().get("kind", "")) != RpgFarmEvents.EGG_HUNT:
		return "the year did not come round to the egg hunt in %d days" % days
	print("[rpggen] INFO a_year_of_festivals: %d days, %d festivals began (%s)" % [days, began.size(), ", ".join(seen.keys())])
	return ""

## The egg hunt, in the village: the shop is closed and says why, everybody stands on the
## square, an egg lies at every spot, each is found with `interact` and pays, and the last one
## pays the prize. Where the year has no egg hunt the step passes with a note.
func _egg_hunt() -> String:
	var events := _events_or_skip("egg_hunt")
	if events == null:
		return ""
	var entry := events.festival()
	if JsonUtil.to_str(entry.get("kind", "")) != RpgFarmEvents.EGG_HUNT:
		print("[rpggen] INFO egg_hunt: today is no egg hunt (game/data/events.json has none), step passes")
		return ""
	var calendar := RpgCalendar.current()
	var friends := RpgFriendship.current()
	var state := _state()
	var title := RpgFarmEvents.event_name(entry)
	var hours := RpgFarmEvents.hours_of(entry)
	await _events_hour(hours[0] + 1)
	var failure: String = await _animals_go(EVENTS_VILLAGE)
	if failure != "":
		return failure
	var scene := _tree().current_scene
	# the shop
	var shop := RpgShopDefinition.load_shop(&"village_shop") as RpgFarmShop
	if shop == null or shop.is_open() or not shop.closed_reason().contains(title):
		return "the shop is not closed for the %s at %s" % [title, calendar.clock()]
	var asked: RpgShopMenu = await _ask_for_shop()
	if asked != null:
		asked.close()
		return "the shop opened on the day of the %s" % title
	# the people, on the square
	var place := JsonUtil.to_str(entry.get("place", ""))
	var centre := RpgSchedule.find_place(scene, place)
	if centre == null:
		return "the village has no place '%s' for the %s" % [place, title]
	for id in friends.order:
		var npc := _person_node(id)
		if npc == null or npc.schedule() == null:
			return "%s has no NPC in the village" % id
		var schedule := npc.schedule()
		var sent := schedule.entry_in_force()
		if not JsonUtil.to_str(sent.get("place", "")).begins_with(place) or not schedule.here(sent):
			return "%s is sent to %s on the %s" % [id, sent, title]
		var at := schedule.place_position(sent)
		if not at.is_finite():
			return "the village has no place for %s" % [sent]
		var there := func() -> bool: return not schedule.walking() and not schedule.away() and npc.visible and npc.global_position.distance_to(at) <= 4.0
		if not await _wait_for(there, 600):
			return "%s is %.0f px from %s on the %s" % [id, npc.global_position.distance_to(at), sent.get("place"), title]
	# the farmer looks at the square for a moment
	failure = await _forage_stand(RpgUtil.world_position(centre) + Vector2(0.0, float(RpgUtil.map_tile_px(scene))), "up")
	if failure != "":
		return failure
	await _frames(40)
	# the eggs
	var spots := JsonUtil.to_array(entry.get("spots", []))
	var things := events.things()
	if spots.is_empty() or things.size() != spots.size() - events.found().size():
		return "%d eggs lie in the village, the hunt has %d spots (%d found)" % [things.size(), spots.size(), events.found().size()]
	var each := JsonUtil.to_int(entry.get("each", 0))
	var prize := JsonUtil.to_int(JsonUtil.to_dict(entry.get("prize", {})).get("gold", 0))
	var goal := RpgFarmEvents.goal_of(entry)
	for raw: Variant in spots:
		var spot := JsonUtil.to_str(raw)
		var egg := events.thing_at(spot)
		if egg == null:
			if events.found().has(spot):
				continue
			return "no egg lies at %s" % spot
		if RpgSchedule.find_place(scene, spot) == null:
			print("[rpggen] INFO egg_hunt: the village has no marker %s (a village from before the card): the egg lies by the square" % spot)
		var gold: int = state.gold
		var count := events.count()
		# standing on its cell: it is walked over, and `interact` finds it under the feet
		var foot := egg.global_position
		if RpgIso.footprint_of(scene) == Vector2i.ZERO:
			foot -= Vector2(0.0, RpgUtil.map_tile_px(scene) * 0.5 - 1.0)
		failure = await _forage_stand(foot, "down")
		if failure != "":
			return failure
		if not await _interact_until(func() -> bool: return events.found().has(spot)):
			return "`interact` at %s did not find its egg" % spot
		await _frames(3)
		var paid := each + (prize if count + 1 == goal else 0)
		if events.count() != count + 1 or state.gold != gold + paid:
			return "the egg at %s made %d eggs and paid %d, expected %d and %d" % [spot, events.count(), state.gold - gold, count + 1, paid]
		if events.thing_at(spot) != null:
			return "the egg at %s still lies there" % spot
	if events.count() < goal or not events.is_done():
		return "%d eggs were found and the prize of %d is not won" % [events.count(), goal]
	if not events.things().is_empty():
		return "%d things of the hunt still lie in the village" % events.things().size()
	return ""

## What a save holds of the festivals: what was done today, what was added, what was shipped.
func _events_snapshot() -> Dictionary:
	var events := RpgFarmEvents.current()
	if events == null:
		return {}
	return {"found": events.found(), "count": events.count(), "done": events.is_done(), "added": events.added(), "shipped": RpgShippingBin.shipped()}

## Before the save of the last step: an event is added at run time (a day for everybody some
## days on), so that a save has one to keep. After it: the event is taken away again.
func _events_mark(on: bool) -> void:
	var events := RpgFarmEvents.current()
	var calendar := RpgCalendar.current()
	if events == null:
		return
	if not on:
		events.remove_event("smoke_wedding")
		return
	var date := RpgCalendar.date_after(calendar.day, calendar.season, calendar.year, 3, calendar.days_per_season)
	events.add_event({"id": "smoke_wedding", "kind": RpgFarmEvents.WEDDING, "name": "Wedding", "season": date[1], "day": date[0], "year": date[2]})

# ---------------------------------------------------------------- marriage (T17.26)
#
# These steps come after the festivals and before the last: the bouquet and the pendant are
# bought at the shop, a person who can be courted is courted and asked with `interact` while
# each is held, the days to the wedding are ended (the people on the square on its day), the
# wedding's night is ended with crops on the plot, and the next morning the spouse is at home
# in the farmhouse and part of the plot is watered. The hearts in between are given, not
# earned: a run that earns ten hearts with gifts would take a game's year. In a farm without
# marriage (`starter_map.courtable` 0) each passes with a note.

const MARRIAGE_HOUSE := "res://game/maps/farm_house.tscn"
const MARRIAGE_FARM := "res://game/maps/farm.tscn"
const MARRIAGE_VILLAGE := "res://game/maps/starter_map.tscn"
## How many cells the step plants for the spouse to water on the first morning.
const MARRIAGE_CROPS := 4

## The marriage of the game, or null, with an INFO line, in a farm that has none.
func _marriage_or_skip(step_name: String) -> RpgMarriage:
	var marriage := RpgMarriage.current()
	if marriage == null:
		print("[rpggen] INFO %s: the farm has no marriage (starter_map.courtable is 0), step passes" % step_name)
	elif marriage.courtable().is_empty():
		print("[rpggen] INFO %s: nobody of the village can be courted, step passes" % step_name)
		return null
	return marriage

## The person the steps court: the first who can be courted, or the one courted already.
func _marriage_person(marriage: RpgMarriage) -> String:
	for id in marriage.courtable():
		if marriage.stage_of(id) != "":
			return id
	return marriage.courtable()[0]

## Goes to the village at 11:00 of today and stands below the person, the thing `item_id` held;
## "" when it stands there.
func _marriage_meet(id: String, item_id: StringName) -> String:
	var calendar := RpgCalendar.current()
	if calendar.minute < 11 * 60:
		calendar.pass_minutes(11 * 60 - calendar.minute)
	RpgFarmMode.current().weather.force(RpgFarmWeather.SUN)
	var failure: String = await _animals_go(MARRIAGE_VILLAGE)
	if failure != "":
		return failure
	var npc := _person_node(id)
	if npc == null or npc.schedule() == null:
		return "%s has no NPC in the village" % id
	var schedule := npc.schedule()
	if not await _wait_for(func() -> bool: return not schedule.walking() and not schedule.away() and npc.visible, 600):
		return "%s is not in the village at %s" % [id, calendar.clock()]
	failure = await _animals_hold(item_id)
	if failure == "":
		failure = await _stand(_below(npc, 9.0), "up")
	return failure

## `interact` with the person until `done` says so, standing below it again before each try:
## the clock goes on while the step waits, and a person whose hour has come walks off.
func _marriage_give(id: String, done: Callable) -> bool:
	var npc := _person_node(id)
	for attempt in 4:
		var schedule := npc.schedule()
		await _wait_for(func() -> bool: return not schedule.walking() and not schedule.away() and npc.visible, 600)
		if await _stand(_below(npc, 9.0), "up") != "":
			return false
		await _tap("interact")
		if await _wait_for(done, 30):
			return true
		for i in 20:  # a talk the press may have begun instead (the person had walked on)
			if not _farmer().move_locked:
				break
			await _shared._press("confirm")
			await _frames(3)
		await _frames(4)
	return false

## The bouquet and the pendant are rows of the shop in its hours and are bought with its menu.
func _buy_a_bouquet() -> String:
	var marriage := _marriage_or_skip("buy_a_bouquet")
	if marriage == null:
		return ""
	var shop := RpgShopDefinition.load_shop(&"village_shop") as RpgFarmShop
	if shop == null:
		return "game/data/shops/village_shop.tres is not the shop of a farm"
	for item_id: StringName in [RpgMarriage.BOUQUET, RpgMarriage.PENDANT]:
		if not _state().items.has(item_id):
			return "the game has no item %s (game/data/items/%s.tres)" % [item_id, item_id]
	await _animals_shop_hour(shop)
	if not shop.is_open():
		return "the shop is closed at %s" % [RpgCalendar.current().clock()]
	var menu: RpgShopMenu = await _ask_for_shop()
	if menu == null:
		return "the shop did not open in its hours"
	var failure := ""
	for item_id: StringName in [RpgMarriage.BOUQUET, RpgMarriage.PENDANT]:
		var price := shop.buy_price(item_id, _state().items)
		_state().gold += price
		var had := _state().inventory.count(item_id)
		var row: Button = null
		for candidate in menu.rows():
			if menu.item_of(candidate) == item_id:
				row = candidate
		if row == null:
			failure = "the shop has no row for %s: %s" % [item_id, shop.offered(_state().items)]
			break
		row.pressed.emit()
		await _animals_frames(2)
		if _state().inventory.count(item_id) != had + 1 or price <= 0:
			failure = "the shop sold %d of %s for %d" % [_state().inventory.count(item_id) - had, item_id, price]
			break
	if is_instance_valid(menu):
		menu.close()
	await _animals_frames(2)
	_tree().paused = false
	return failure

## Below eight hearts the bouquet is not taken; from eight it is, with `interact`, and the
## courting begins: the atom of the dialogue says so, and the two last hearts are open.
func _court_with_a_bouquet() -> String:
	var marriage := _marriage_or_skip("court_with_a_bouquet")
	if marriage == null:
		return ""
	var friends := RpgFriendship.current()
	var id := _marriage_person(marriage)
	if marriage.stage_of(id) != "":
		return "%s is courted already before the bouquet" % id
	if not _state().inventory.has(RpgMarriage.BOUQUET):
		_state().inventory.add(RpgMarriage.BOUQUET, 1)
	var failure: String = await _marriage_meet(id, RpgMarriage.BOUQUET)
	if failure != "":
		return failure
	# below eight hearts it is not taken
	friends.points[id] = (RpgMarriage.COURT_HEARTS - 1) * RpgFriendship.HEART_POINTS
	if marriage.refusal(id, RpgMarriage.BOUQUET) == "":
		return "%s would take the bouquet at %d hearts" % [id, friends.hearts(id)]
	friends.add_points(id, 5 * RpgFriendship.HEART_POINTS)
	if friends.hearts(id) != RpgMarriage.COURT_HEARTS:
		return "%s has %d hearts before the courting, at most %d" % [id, friends.hearts(id), RpgMarriage.COURT_HEARTS]
	print("[rpggen] INFO court_with_a_bouquet: %s is given eight hearts (a run cannot earn them)" % id)
	if not await _marriage_give(id, func() -> bool: return marriage.stage_of(id) == RpgMarriage.COURTING):
		return "`interact` with the bouquet held did not court %s" % id
	await _frames(4)
	if _state().inventory.has(RpgMarriage.BOUQUET):
		return "the bouquet is still in the bag"
	if not RpgCondition.evaluate("courting:%s" % id):
		return "the atom courting:%s is false" % id
	friends.add_points(id, 2 * RpgFriendship.HEART_POINTS)
	if friends.hearts(id) != RpgMarriage.PROPOSE_HEARTS:
		return "%s has %d hearts while courted, expected the two last open" % [id, friends.hearts(id)]
	return ""

## At ten hearts the pendant, given with `interact`, is a yes: the wedding is three days on (or
## the next day that is no festival), a day of the calendar for everybody.
func _propose_with_a_pendant() -> String:
	var marriage := _marriage_or_skip("propose_with_a_pendant")
	if marriage == null:
		return ""
	var calendar := RpgCalendar.current()
	var id := _marriage_person(marriage)
	if marriage.stage_of(id) != RpgMarriage.COURTING:
		return "%s is not courted (%s)" % [id, marriage.stage_of(id)]
	if not _state().inventory.has(RpgMarriage.PENDANT):
		_state().inventory.add(RpgMarriage.PENDANT, 1)
	var failure: String = await _marriage_meet(id, RpgMarriage.PENDANT)
	if failure != "":
		return failure
	var today := calendar.today()
	if not await _marriage_give(id, func() -> bool: return marriage.engaged() == id):
		return "`interact` with the pendant held did not make %s engaged" % id
	await _frames(40)  # the yes is looked at
	if _state().inventory.has(RpgMarriage.PENDANT):
		return "the pendant is still in the bag"
	if marriage.wedding_day() < today + RpgMarriage.WEDDING_AFTER:
		return "the wedding is on day %d, the proposal was on %d" % [marriage.wedding_day(), today]
	if not RpgCondition.evaluate("engaged:%s" % id) or RpgCondition.evaluate("courting:%s" % id):
		return "the atoms do not say that %s is engaged" % id
	var events := RpgFarmEvents.current()
	if events != null:
		var day := events.events_of(marriage.wedding_day())
		if JsonUtil.to_str(RpgFarmEvents.festival_of(day).get("kind", "")) != RpgFarmEvents.WEDDING:
			return "the wedding's day is %s in the calendar" % [day]
	return ""

## The days to the wedding are ended. On its day the shop is closed and the people stand on the
## square, the one to be married with them; at its night the farmer is married.
func _the_wedding() -> String:
	var marriage := _marriage_or_skip("the_wedding")
	if marriage == null:
		return ""
	var calendar := RpgCalendar.current()
	var id := marriage.engaged()
	if id == "":
		return "nobody is engaged"
	var guard := 0
	while calendar.today() < marriage.wedding_day() and guard < 10:
		await _weather_end_day()
		guard += 1
		if marriage.spouse() != "":
			return "married before the wedding's day"
	if calendar.today() != marriage.wedding_day():
		return "the wedding's day did not come (today %d, the wedding %d)" % [calendar.today(), marriage.wedding_day()]
	if not RpgCondition.evaluate("event:wedding"):
		return "the atom event:wedding is false on the wedding's day"
	var shop := RpgShopDefinition.load_shop(&"village_shop") as RpgFarmShop
	await _events_hour(11)
	if shop != null and shop.is_open():
		return "the shop is open on the wedding's day"
	var failure: String = await _animals_go(MARRIAGE_VILLAGE)
	if failure != "":
		return failure
	var npc := _person_node(id)
	if npc == null or npc.schedule() == null:
		return "%s has no NPC in the village" % id
	var schedule := npc.schedule()
	var sent := schedule.entry_in_force()
	if not JsonUtil.to_str(sent.get("place", "")).begins_with("square"):
		return "%s is sent to %s on its wedding's day" % [id, sent]
	var at := schedule.place_position(sent)
	if not await _wait_for(func() -> bool: return not schedule.walking() and not schedule.away() and npc.global_position.distance_to(at) <= 4.0, 600):
		return "%s is not on the square on its wedding's day" % id
	failure = await _forage_stand(_below(npc, float(RpgUtil.map_tile_px(_tree().current_scene)) * 1.5), "up")
	if failure != "":
		return failure
	await _frames(40)  # the square is looked at
	# crops on the plot for the morning after, dry
	failure = await _animals_go(MARRIAGE_FARM)
	if failure != "":
		return failure
	var field := RpgField.current()
	var mode := RpgFarmMode.current()
	if field == null:
		return "the farm has no field"
	var in_season := mode.crops.of_season(calendar.season_name())
	var planted := 0
	for i in MARRIAGE_CROPS:
		var found: Variant = _weather_free_cell(field)
		if found == null or in_season.is_empty():
			break
		var cell: Vector2i = found
		if field.till(cell) and field.plant(cell, in_season[0]):
			planted += 1
	_box["marriage_crops"] = planted
	mode.weather.force_tomorrow(RpgFarmWeather.SUN)
	await _weather_end_day()
	if marriage.spouse() != id:
		return "the wedding's night did not marry %s (spouse '%s')" % [id, marriage.spouse()]
	if not RpgCondition.evaluate("spouse:%s" % id) or RpgCondition.evaluate("engaged:%s" % id):
		return "the atoms do not say that %s is the spouse" % id
	return ""

## The morning after the wedding: part of the plot is watered, and the spouse is at home in the
## farmhouse, on its cell, and says what it did.
func _spouse_at_home() -> String:
	var marriage := _marriage_or_skip("spouse_at_home")
	if marriage == null:
		return ""
	var id := marriage.spouse()
	if id == "":
		return "nobody is married"
	var help := marriage.help_today()
	if JsonUtil.to_str(help.get("kind", "")) != RpgMarriage.WATER:
		if JsonUtil.to_int(_box.get("marriage_crops", 0)) == 0:
			print("[rpggen] INFO spouse_at_home: the plot had no free cell to plant, nothing was dry to water")
		else:
			return "the first morning's help is %s, not watering" % [help]
	var field := RpgField.current()
	if field != null and field.resolved_id() == RpgMarriage.FARM_FIELD and JsonUtil.to_int(help.get("count", 0)) > 0:
		var wet := 0
		var dry := 0
		for key: Variant in field.to_dict().keys():
			if field.is_watered(RpgField.cell_of(JsonUtil.to_str(key))):
				wet += 1
			else:
				dry += 1
		if wet < JsonUtil.to_int(help.get("count", 0)) or dry == 0:
			return "the plot shows %d wet and %d dry cells after %s: not part of it" % [wet, dry, help]
	var failure: String = await _animals_go(MARRIAGE_HOUSE)
	if failure != "":
		return failure
	var npc := marriage.spouse_node() as Node2D
	if npc == null:
		return "the farmhouse has no spouse"
	var schedule := npc.get_node_or_null(RpgSchedule.NODE_NAME) as RpgSchedule
	var cell := marriage.home_cell()
	if schedule == null or schedule.away() or not npc.visible or cell.size() != 2:
		return "the spouse is not seen at home (cell %s)" % [cell]
	var scene := _tree().current_scene as Node2D
	var at := RpgSchedule.cell_position(scene, Vector2i(JsonUtil.to_int(cell[0]), JsonUtil.to_int(cell[1])))
	if npc.global_position.distance_to(at) > 4.0:
		return "the spouse stands %.0f px from its place" % npc.global_position.distance_to(at)
	var said := ""
	var lines: Variant = npc.get(&"dialogue")
	if lines is RpgDialogueResource:
		var dialogue: RpgDialogueResource = lines
		if not dialogue.lines.is_empty():
			said = dialogue.lines[0].text
	if said == "":
		return "the spouse has nothing to say"
	# the farmer stands below the spouse and looks at it for a moment
	failure = await _forage_stand(_below(npc, float(RpgUtil.map_tile_px(scene))), "up")
	if failure != "":
		return failure
	await _frames(40)
	print("[rpggen] INFO spouse_at_home: %s says \"%s\"; the help: %s" % [id, said, help])
	return ""

## What a save holds of the marriage: who is courted, engaged and married, the wedding's day,
## this morning's help and what lies on the table.
func _marriage_snapshot() -> Dictionary:
	var marriage := RpgMarriage.current()
	if marriage == null:
		return {}
	return {"courting": marriage.courting(), "engaged": marriage.engaged(), "wedding": marriage.wedding_day(), "spouse": marriage.spouse(), "help": marriage.help_today(), "table": String(marriage.on_table())}
