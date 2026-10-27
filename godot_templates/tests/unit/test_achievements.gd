extends RefCounted
## Achievements (1.5.0): counters, conditions that unlock by themselves, the dialogue events,
## rewards that never get lost, secrets, the save and the menu.

const Fixtures := preload("../lib/fixtures.gd")

var _english: Translation = null

func _achievement(id: StringName, when: String, points: int = 10) -> RpgAchievement:
	var def := RpgAchievement.new()
	def.id = id
	def.title = String(id).capitalize()
	def.when = when
	def.points = points
	return def

func _state() -> Node:
	if _english == null:
		_english = Fixtures.install_english()
	var log := Fixtures.item(&"log")
	log.display_name = "Log"
	var state := Fixtures.install_state({&"log": log, &"potion": Fixtures.item(&"potion")})
	state.new_game()
	state.inventory.slots.clear()
	state.gold = 0
	var hunter := _achievement(&"wolf_hunter", "count:defeated:wolf>=3")
	hunter.rewards = {"gold": 20, "items": [{"item_id": "potion", "qty": 1}]}
	state.achievement_defs[&"wolf_hunter"] = hunter
	state.achievement_defs[&"lumberjack"] = _achievement(&"lumberjack", "count:items:log>=5", 5)
	return state

func _end() -> void:
	Fixtures.uninstall_state()
	if _english != null:
		Fixtures.uninstall_english(_english)
		_english = null

func test_counters_unlock_achievements_by_themselves(t) -> void:
	var state := _state()
	var toasts := []
	RpgUtil.events().notify.connect(func(text: String) -> void: toasts.append(text))
	state.note_defeat(&"wolf")
	state.note_defeat(&"wolf")
	state.note_defeat(&"bat")
	t.eq([state.counter("defeated"), state.counter("defeated:wolf")], [3, 2])
	t.ok(not state.achievement_unlocked(&"wolf_hunter"))
	state.note_defeat(&"wolf")
	t.ok(state.achievement_unlocked(&"wolf_hunter"))
	t.ok(RpgCondition.evaluate("achievement:wolf_hunter"))
	t.ok(toasts.has("Achievement unlocked: Wolf Hunter"), str(toasts))
	t.eq([state.gold, state.inventory.count(&"potion")], [20, 1], "its rewards")
	state.note_defeat(&"wolf")
	t.eq(state.gold, 20, "once")
	_end()

func test_items_gained_are_counted_but_not_gear_moved_or_what_a_game_starts_with(t) -> void:
	var state := _state()
	state.inventory.add(&"log", 3)
	t.eq(state.counter("items:log"), 3)
	state.inventory.remove(&"log", 3)
	state.inventory.add(&"log", 2)
	t.ok(state.achievement_unlocked(&"lumberjack"), "gained five in all")
	t.eq(state.achievement_points(), 5)
	_end()

func test_the_events_count_and_unlock(t) -> void:
	var state := _state()
	state.achievement_defs[&"talker"] = _achievement(&"talker", "count:chats>=2")
	state.achievement_defs[&"story"] = _achievement(&"story", "")
	t.ok(RpgDialogueRunner.execute_event("count:chats"))
	t.ok(RpgDialogueRunner.execute_event("count:chats:1"))
	t.ok(state.achievement_unlocked(&"talker"))
	t.ok(not RpgDialogueRunner.execute_event("count:"))
	t.eq(RpgDialogueRunner.event_problem("count:chats:many"), "count needs <name>[:N]")
	t.ok(not state.achievement_unlocked(&"story"), "nothing unlocks an achievement without a condition by itself")
	t.ok(RpgDialogueRunner.execute_event("unlock_achievement:story"))
	t.ok(state.achievement_unlocked(&"story"))
	t.ok(not state.unlock_achievement(&"story"), "once")
	t.ok(not state.unlock_achievement(&"nope"))
	t.eq(RpgCondition.problems("count:chats"), ["count needs <name>>=N: 'count:chats'"] as PackedStringArray)
	_end()

func test_a_reward_that_does_not_fit_waits(t) -> void:
	var state := _state()
	state.inventory.capacity = 0
	for i in 3:
		state.note_defeat(&"wolf")
	t.eq(state.pending_items, [{"item_id": "potion", "qty": 1}] as Array[Dictionary])
	_end()

func test_the_save_keeps_counters_and_unlocks(t) -> void:
	var state := _state()
	state.note_defeat(&"wolf")
	state.unlock_achievement(&"lumberjack")
	var back: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	t.eq(back["achievements"], ["lumberjack"])
	state.new_game()
	t.ok(not state.to_dict().has("counters") and not state.to_dict().has("achievements"))
	state.from_dict(back)
	t.ok(state.achievement_unlocked(&"lumberjack"))
	t.eq(state.counter("defeated:wolf"), 1)
	state.achievement_defs.clear()
	state.new_game()
	state.inventory.add(&"log")
	state.note_defeat(&"wolf")
	t.ok(not state.to_dict().has("counters"), "a game without achievements counts nothing")
	_end()

func test_the_menu_lists_progress_and_hides_secrets(t) -> void:
	var state := _state()
	var secret := _achievement(&"hidden", "flag:cave.found")
	secret.secret = true
	secret.description = "Find the cave"
	state.achievement_defs[&"hidden"] = secret
	state.note_defeat(&"wolf")
	state.inventory.add(&"log", 5)
	t.eq(RpgAchievementsMenu.row_text(state, &"wolf_hunter"), "[ ] Wolf Hunter (10): 1/3")
	t.eq(RpgAchievementsMenu.row_text(state, &"lumberjack"), "[x] Lumberjack (5)")
	t.eq(RpgAchievementsMenu.row_text(state, &"hidden"), "[ ] ???")
	var menu := RpgAchievementsMenu.new()
	Fixtures.tree().root.add_child(menu)
	t.eq(menu.rows().size(), 3)
	t.eq(String(menu.rows()[0].name), "Achievement_lumberjack", "unlocked first")
	t.eq((menu.find_child("Total", true, false) as Label).text, "1 of 3 unlocked · 5 points")
	menu.free()
	state.set_flag("cave", "found", true)
	t.eq(RpgAchievementsMenu.row_text(state, &"hidden"), "[x] Hidden (10)\nFind the cave")
	_end()

func test_problems(t) -> void:
	var def := RpgAchievement.new()
	def.when = "count:x"
	def.rewards = {"gold": -3}
	var found := def.problems()
	t.ok(found.has("the achievement has no id"), str(found))
	t.ok(found.any(func(why: String) -> bool: return why.begins_with("what unlocks it: ")), str(found))
	t.ok(found.has("its rewards: 'gold' must be a number, 0 or more"), str(found))
