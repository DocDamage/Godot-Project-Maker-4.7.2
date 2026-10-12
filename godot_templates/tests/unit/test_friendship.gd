extends RefCounted
## T17.09: friendship. Points and hearts, talking once a day, gifts by taste and two a week, the
## counters the calendar resets, the dialogue atom, the save, and the People page.

const Fixtures := preload("../lib/fixtures.gd")
const ActorBuild := preload("res://builder/lib/actor_build.gd")

const PEOPLE := [
	{
		"id": "anna", "name": "Anna", "home": 1, "job": "shopkeeper",
		"loves": ["crop_corn"], "likes": ["crop_turnip", "fish_carp"], "dislikes": ["stone"],
		"schedule": [{"hour": 6, "map": "village", "place": "home_1"}, {"hour": 9, "map": "village", "place": "shop"}],
	},
	{"id": "bert", "name": "Bert", "home": 2, "job": "", "loves": ["stone"], "likes": [], "dislikes": ["crop_corn"], "schedule": []},
]
const ITEMS: Array[StringName] = [&"crop_corn", &"crop_turnip", &"fish_carp", &"stone", &"wood"]

func _saves() -> RpgSaveManager:
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER) as RpgSaveManager
	save.dir = "user://test_friendship_saves_%d" % Time.get_ticks_usec()
	return save

func _drop_saves(save: RpgSaveManager) -> void:
	if DirAccess.dir_exists_absolute(save.dir):
		for file: String in DirAccess.get_files_at(save.dir):
			DirAccess.remove_absolute(save.dir.path_join(file))
		DirAccess.remove_absolute(save.dir)
	Fixtures.uninstall("SaveManager")

## A farm's game: the items, a bag with ten of each, a calendar and the friendships.
func _game() -> RpgFriendship:
	var registry := {}
	for id in ITEMS:
		registry[id] = Fixtures.item(id)
	var state := Fixtures.install_state(registry) as RpgGameState
	state.inventory.registry = state.items
	for id in ITEMS:
		state.inventory.add(id, 10)
	RpgCalendar.ensure()
	var friends := RpgFriendship.ensure()
	friends.add_list(PEOPLE)
	return friends

func _clear() -> void:
	Fixtures.uninstall_state()
	RpgSchedule.source = Callable()

# ---------------------------------------------------------------- finding it

func test_a_mode_makes_the_friendships_and_others_find_them(t) -> void:
	Fixtures.uninstall_state()
	t.ok(RpgFriendship.current() == null and RpgFriendship.ensure() == null, "no game: none")
	var state := Fixtures.install_state() as RpgGameState
	t.ok(RpgFriendship.current() == null, "a game has none until a mode asks for them")
	var friends := RpgFriendship.ensure()
	t.ok(friends != null and friends.get_parent() == state)
	t.ok(RpgFriendship.ensure() == friends and RpgFriendship.current() == friends, "there is one")
	t.eq(friends.people.size(), 0, "the template project has no people.json")
	friends.add_list(PEOPLE)
	friends.add_list(PEOPLE)
	t.eq(friends.order, ["anna", "bert"] as Array[String], "a person is listed once")
	t.eq(friends.display_name("anna"), "Anna")
	t.eq(friends.display_name("old_tom"), "Old Tom", "somebody the file does not list")
	t.eq(friends.schedule_of("anna").size(), 2)
	t.ok(RpgSchedule.source.is_valid(), "the schedules of the people are offered to the NPCs")
	t.eq(RpgSchedule.source.call("anna"), friends.schedule_of("anna"))
	_clear()
	t.ok(not RpgSchedule.source.is_valid())

# ---------------------------------------------------------------- talking

func test_talking_twice_a_day_counts_once(t) -> void:
	var friends := _game()
	var calendar := RpgCalendar.current()
	var seen: Array[String] = []
	friends.changed.connect(func(person: String) -> void: seen.append(person))
	t.ok(not friends.has_met("anna"))
	t.eq(friends.talk("anna"), RpgFriendship.TALK_POINTS)
	t.ok(friends.has_met("anna"))
	t.eq(friends.talk("anna"), 0, "the second talk of a day gives nothing")
	t.eq(friends.points_of("anna"), RpgFriendship.TALK_POINTS)
	t.eq(friends.talk("bert"), RpgFriendship.TALK_POINTS, "everybody has a talk a day")
	t.ok(seen.has("anna") and seen.has("bert"))
	calendar.end_day()
	t.eq(friends.talk("anna"), RpgFriendship.TALK_POINTS, "the next day counts again")
	t.eq(friends.points_of("anna"), 2 * RpgFriendship.TALK_POINTS)
	t.eq(friends.talk(""), 0)
	_clear()

func test_interacting_with_the_npc_of_a_person_is_a_talk(t) -> void:
	var friends := _game()
	var bus := RpgUtil.events()
	var npc := ActorBuild.build("npc", "Villager", null, Vector2i(16, 24), Vector2i(8, 23), 16) as RpgNpc
	npc.entity_id = "bert"
	t.eq(friends.person_of(npc), "bert", "by the entity id")
	bus.interaction_started.emit(npc)
	t.eq(friends.points_of("bert"), RpgFriendship.TALK_POINTS)
	bus.interaction_started.emit(npc)
	t.eq(friends.points_of("bert"), RpgFriendship.TALK_POINTS, "once a day")
	# an NPC placed with an id of its map, whose schedule names the person
	npc.entity_id = "village_npc_003"
	t.eq(friends.person_of(npc), "")
	var schedule := RpgSchedule.new()
	schedule.name = RpgSchedule.NODE_NAME
	schedule.person = "anna"
	npc.add_child(schedule)
	t.eq(friends.person_of(npc), "anna")
	bus.interaction_started.emit(npc)
	t.ok(friends.has_met("anna"))
	# a chest is nobody
	var chest := Node2D.new()
	bus.interaction_started.emit(chest)
	t.eq(friends.met, ["bert", "anna"] as Array[String])
	chest.free()
	npc.free()
	_clear()

# ---------------------------------------------------------------- gifts

func test_a_loved_gift_gives_more_than_a_liked_one_and_a_third_in_a_week_none(t) -> void:
	var friends := _game()
	var state := RpgUtil.state()
	var calendar := RpgCalendar.current()
	t.eq(friends.taste_of("anna", &"crop_corn"), RpgFriendship.LOVES)
	t.eq(friends.taste_of("anna", &"fish_carp"), RpgFriendship.LIKES)
	t.eq(friends.taste_of("anna", &"stone"), RpgFriendship.DISLIKES)
	t.eq(friends.taste_of("anna", &"wood"), RpgFriendship.NEUTRAL)
	t.ok(RpgFriendship.LOVE_POINTS > RpgFriendship.LIKE_POINTS and RpgFriendship.LIKE_POINTS > RpgFriendship.NEUTRAL_POINTS)
	t.ok(RpgFriendship.DISLIKE_POINTS < 0)
	t.eq(friends.gift("anna", &"crop_corn"), RpgFriendship.LOVES)
	t.eq(friends.gift("bert", &"crop_turnip"), RpgFriendship.NEUTRAL)
	var loved := friends.points_of("anna")
	t.eq(loved, RpgFriendship.LOVE_POINTS)
	t.eq(state.inventory.count(&"crop_corn"), 9, "the gift left the bag")
	t.ok(friends.has_met("anna"))
	t.eq(friends.gift("anna", &"fish_carp"), RpgFriendship.LIKES)
	var liked := friends.points_of("anna") - loved
	t.eq(liked, RpgFriendship.LIKE_POINTS)
	t.ok(loved > liked, "a loved gift gives more than a liked one")
	t.eq(friends.gifts_left("anna"), 0)
	t.eq(friends.gift("anna", &"crop_corn"), "", "a third gift in a week is not taken")
	t.eq(friends.points_of("anna"), loved + liked, "and gives nothing")
	t.eq(state.inventory.count(&"crop_corn"), 9, "it stays in the bag")
	t.eq(friends.gifts_left("bert"), 1, "the week is counted a person")
	# the days of the week pass: still none; the new week: two again
	for i in 6:
		calendar.end_day()
		t.eq(friends.gifts_left("anna"), 0, "day %d of the week" % (i + 2))
	calendar.end_day()
	t.eq(calendar.weekday(), 0)
	t.eq(friends.gifts_left("anna"), 2, "a new week")
	t.eq(friends.gift("anna", &"stone"), RpgFriendship.DISLIKES)
	t.eq(friends.points_of("anna"), loved + liked + RpgFriendship.DISLIKE_POINTS, "a disliked gift costs")
	t.eq(friends.gift("anna", &"wood"), RpgFriendship.NEUTRAL)
	# what the bag does not hold cannot be given
	t.eq(friends.gift("bert", &"gem"), "")
	t.eq(friends.gifts_left("bert"), 2, "and is no gift of the week")
	t.eq(friends.gift("bert", &"gem", false), RpgFriendship.NEUTRAL, "unless it is not taken from the bag")
	t.eq(friends.gifts_left("bert"), 1)
	# points stay within no heart and ten
	friends.add_points("bert", -99999)
	t.eq(friends.points_of("bert"), 0)
	friends.add_points("bert", 99999)
	t.eq(friends.points_of("bert"), RpgFriendship.MAX_POINTS)
	t.eq(friends.hearts("bert"), 10)
	_clear()

# ---------------------------------------------------------------- hearts and the atom

func test_hearts_and_the_dialogue_atom(t) -> void:
	var friends := _game()
	t.eq(RpgFriendship.HEARTS * RpgFriendship.HEART_POINTS, 2500, "ten hearts of 250 points")
	t.eq(friends.hearts("anna"), 0)
	friends.add_points("anna", 249)
	t.eq(friends.hearts("anna"), 0)
	friends.add_points("anna", 1)
	t.eq(friends.hearts("anna"), 1)
	friends.add_points("anna", 3 * 250 - 1)
	t.eq(friends.hearts("anna"), 3)
	t.ok(RpgCondition.evaluate("friendship:anna>=3"))
	t.ok(not RpgCondition.evaluate("friendship:anna>=4"), "false at three hearts")
	friends.add_points("anna", 1)
	t.eq(friends.hearts("anna"), 4)
	t.ok(RpgCondition.evaluate("friendship:anna>=4"), "true at four")
	t.ok(RpgCondition.evaluate("friendship:anna>=4 and not friendship:bert>=1"))
	t.ok(RpgCondition.evaluate("friendship:bert>=0"), "everybody has no heart at least")
	t.ok(RpgCondition.ATOMS.has("friendship:"), "the dock's completion knows it")
	t.eq(RpgCondition.atom_problem("friendship:anna>=4"), "")
	t.ok(RpgCondition.atom_problem("friendship:anna") != "")
	t.ok(RpgCondition.atom_problem("friendship:anna>=many") != "")
	t.ok(RpgCondition.atom_problem("friendship:>=2") != "")
	# a line that needs four hearts is said at four
	var dialogue := RpgDialogueResource.new()
	var warm := RpgDialogueLine.new()
	warm.id = "warm"
	warm.text = "I kept this for you."
	warm.condition = "friendship:anna>=4"
	t.ok(RpgCondition.evaluate(warm.condition))
	friends.add_points("anna", -1)
	t.ok(not RpgCondition.evaluate(warm.condition))
	dialogue.lines = [warm] as Array[RpgDialogueLine]
	_clear()
	# a game without friendships: the atom is false, and nothing is logged
	Fixtures.install_state()
	t.ok(not RpgCondition.evaluate("friendship:anna>=0"))
	t.ok(RpgCondition.evaluate("not friendship:anna>=1"))
	_clear()

# ---------------------------------------------------------------- the save

func test_the_save_round_trips_and_other_games_have_no_key(t) -> void:
	var plain := Fixtures.install_state() as RpgGameState
	t.ok(not plain.to_dict().has("friendship"), "a game without friendships writes no key")
	plain.from_dict({"friendship": {"points": {"anna": 500}}})
	t.ok(RpgFriendship.current() == null, "and ignores one")
	Fixtures.uninstall_state()

	var friends := _game()
	var state := RpgUtil.state()
	var save := _saves()
	friends.talk("anna")
	friends.gift("anna", &"crop_corn")
	friends.gift("anna", &"wood")
	friends.gift("bert", &"stone")
	var before := friends.to_dict()
	t.eq(before["points"], {"anna": 20 + 80 + 20, "bert": 80})
	t.eq(before["met"], ["anna", "bert"])
	t.eq(before["talked"], ["anna"])
	t.eq(before["gifts"], {"anna": 2, "bert": 1})
	t.eq(before["known"], {"anna": ["crop_corn", "wood"], "bert": ["stone"]})
	t.eq(state.to_dict()["friendship"], before)
	t.ok(save.save(1))
	var written: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(save.dir.path_join("slot_1.json")))
	t.eq(int(written["save_version"]), 1, "the save version stays 1")
	state.new_game()
	t.eq(friends.to_dict(), {"points": {}, "met": [], "talked": [], "gifts": {}, "known": {}}, "a new game: nobody is met")
	t.eq(friends.people.size(), 2, "the people stay")
	t.ok(save.load(1))
	t.eq(friends.to_dict(), before, "the round trip")
	t.eq(friends.hearts("anna"), 0)
	t.eq(friends.gifts_left("anna"), 0, "the week's gifts are saved with it")
	t.eq(friends.talk("anna"), 0, "and the day's talk")
	t.eq(friends.known_of("anna", RpgFriendship.LOVES), ["crop_corn"] as Array[String])
	# a save without the key: nobody is met; a damaged one is read as far as it makes sense
	var old := state.to_dict()
	old.erase("friendship")
	state.from_dict(old)
	t.eq(friends.met, [] as Array[String])
	old["friendship"] = {"points": {"anna": 99999, "bert": "x"}, "met": "anna", "gifts": {"anna": -3}, "known": {"anna": "corn"}}
	state.from_dict(old)
	t.eq(friends.points_of("anna"), RpgFriendship.MAX_POINTS)
	t.eq(friends.points_of("bert"), 0)
	t.eq(friends.met, [] as Array[String])
	t.eq(friends.gifts_left("anna"), 2)
	t.eq(friends.known_of("anna", RpgFriendship.LOVES), [] as Array[String])
	old["friendship"] = "nothing"
	state.from_dict(old)
	t.eq(friends.points, {})
	_drop_saves(save)
	_clear()

# ---------------------------------------------------------------- the People page

func test_the_people_page_lists_what_is_known(t) -> void:
	var friends := _game()
	var page := RpgPeoplePage.new()
	page.friendship = friends
	page.build()
	page.build()
	t.eq(page.find_children("Back", "Button", true, false).size(), 1, "built once")
	page.refresh()
	t.eq(page.rows().size(), 0, "nobody is met")
	t.eq(page.detail(), "You have met nobody yet.")
	friends.talk("bert")
	friends.add_points("anna", 3 * 250)
	friends.gift("anna", &"crop_corn")
	page.refresh()
	t.eq(page.rows().size(), 2, "who was met, and nobody else")
	t.eq(page.person_of(page.rows()[0]), "bert", "in the order they were met")
	t.eq(page.rows()[0].text, "Bert   0 of 10 hearts")
	t.eq(page.rows()[1].text, "Anna   3 of 10 hearts")
	t.eq(page.detail(), "Bert   0 of 10 hearts\nNothing is known of their taste yet.", "the first is described")
	page.describe("anna")
	t.eq(page.detail(), "Anna   3 of 10 hearts\nLoves: Crop Corn", "an item is known once it was given")
	t.ok(not page.detail().contains("Fish"), "what was never given is not told")
	calendar_week()
	friends.gift("anna", &"stone")
	friends.gift("anna", &"fish_carp")
	page.refresh()
	page.describe("anna")
	t.eq(page.detail(), "Anna   3 of 10 hearts\nLoves: Crop Corn\nLikes: Fish Carp\nDislikes: Stone")
	t.eq(friends.known_of("anna", RpgFriendship.NEUTRAL), [] as Array[String])
	# the focus ring: the people, then Back
	var back := page.find_children("Back", "Button", true, false)[0] as Button
	t.eq(page.rows()[0].get_node(page.rows()[0].focus_neighbor_bottom), page.rows()[1])
	t.eq(page.rows()[1].get_node(page.rows()[1].focus_neighbor_bottom), back)
	t.eq(back.get_node(back.focus_neighbor_bottom), page.rows()[0])
	page.free()
	_clear()

## A week later: the gifts of the week are counted anew.
func calendar_week() -> void:
	for i in 7:
		RpgCalendar.current().end_day()

func test_the_page_is_added_to_a_pause_menu_with_one_call(t) -> void:
	await Fixtures.tree().process_frame
	var friends := _game()
	friends.talk("anna")
	# what the pause menu's scene is to the page: a column of buttons with %Resume
	var menu := Control.new()
	menu.name = "PauseMenu"
	var box := VBoxContainer.new()
	box.name = "Box"
	menu.add_child(box)
	for button_name: String in ["Resume", "Inventory", "Status", "Journal", "Save", "Title"]:
		var button := Button.new()
		button.name = button_name
		box.add_child(button)
		button.owner = menu
		button.unique_name_in_owner = true
	Fixtures.tree().root.add_child(menu)
	menu.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var people := RpgPeoplePage.add_to(menu)
	t.ok(people != null and people.get_parent() == box)
	t.eq(people.text, "People")
	t.eq(people.get_index(), 4, "after Journal")
	t.ok(RpgPeoplePage.add_to(menu) == people, "added once")
	t.eq(box.get_child_count(), 7)
	var journal := box.get_node("Journal") as Button
	var save := box.get_node("Save") as Button
	t.eq(journal.get_node(journal.focus_neighbor_bottom), people, "it is in the focus ring")
	t.eq(people.get_node(people.focus_neighbor_bottom), save)
	people.pressed.emit()
	var page := menu.get_node_or_null(RpgPeoplePage.PAGE_NAME) as RpgPeoplePage
	t.ok(page != null, "pressing it opens the page over the menu")
	if page != null:
		t.eq(page.rows().size(), 1)
		t.eq(page.rows()[0].text, "Anna   0 of 10 hearts")
		t.eq(page.size, menu.get_viewport_rect().size, "as large as the screen")
		page.close()
		await Fixtures.tree().process_frame
		t.ok(menu.get_node_or_null(RpgPeoplePage.PAGE_NAME) == null, "Back closes it")
	var bare := Control.new()
	t.ok(RpgPeoplePage.add_to(null) == null and RpgPeoplePage.add_to(bare) == null, "no column: no button")
	bare.free()
	Fixtures.tree().root.remove_child(menu)
	menu.free()
	_clear()
