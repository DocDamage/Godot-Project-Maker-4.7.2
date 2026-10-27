extends RefCounted
## Quests of 1.5.0: what a quest requires and quests that start by themselves (chains), quests
## that fail, stages that wait to be turned in and take their items, counts kept live, and the
## HUD's tracker.

const Fixtures := preload("../lib/fixtures.gd")

var _english: Translation = null

func _state() -> Node:
	if _english == null:
		_english = Fixtures.install_english()
	var log := Fixtures.item(&"log")
	log.display_name = "Log"
	var state := Fixtures.install_state({&"log": log, &"potion": Fixtures.item(&"potion")})
	state.new_game()
	state.inventory.slots.clear()
	state.gold = 0
	return state

func _end() -> void:
	Fixtures.uninstall_state()
	if _english != null:
		Fixtures.uninstall_english(_english)
		_english = null

func _quest(id: StringName, stages: Array) -> RpgQuestDefinition:
	var def := RpgQuestDefinition.new()
	def.id = id
	def.title = String(id).capitalize()
	var typed: Array[Dictionary] = []
	for stage: Dictionary in stages:
		typed.append(stage)
	def.stages = typed
	return def

## Bring eight logs to the carpenter: the stage counts them, waits to be turned in and takes them.
func _logs(state: Node) -> RpgQuestDefinition:
	var def := _quest(&"logs", [
		{"id": "gather", "description": "Bring logs", "complete_when": "item:log>=8", "turn_in": true,
			"take": [{"item_id": "log", "qty": 8}], "rewards": {"gold": 5}},
		{"id": "thanks", "description": "Rest", "complete_when": ""},
	])
	def.rewards = {"gold": 40}
	state.quest_defs[&"logs"] = def
	return def

func test_a_quest_waits_for_what_it_requires(t) -> void:
	var state := _state()
	var second := _quest(&"second", [{"id": "a", "complete_when": ""}])
	second.requires = "quest_done:first"
	state.quest_defs[&"first"] = _quest(&"first", [{"id": "a", "complete_when": ""}])
	state.quest_defs[&"second"] = second
	t.ok(not state.quest_available(&"second"))
	t.ok(not RpgCondition.evaluate("quest_available:second"))
	t.ok(not state.quest_start(&"second"), "refused while the first is not done")
	t.eq(state.quest_state(&"second"), "")
	t.ok(state.quest_start(&"first"))
	state.quest_complete(&"first")
	t.ok(RpgCondition.evaluate("quest_available:second"))
	t.ok(state.quest_start(&"second"))
	t.ok(not state.quest_available(&"second"), "a started quest is no longer available")
	_end()

func test_a_chained_quest_starts_by_itself(t) -> void:
	var state := _state()
	state.quest_defs[&"first"] = _quest(&"first", [{"id": "a", "complete_when": "flag:q.a"}])
	var second := _quest(&"second", [{"id": "b", "complete_when": "flag:q.b"}])
	second.requires = "quest_done:first"
	second.auto_start = true
	state.quest_defs[&"second"] = second
	state.quest_start(&"first")
	t.eq(state.quest_state(&"second"), "")
	state.set_flag("q", "a", true)
	t.ok(state.quest_is_done(&"first"))
	t.eq(state.quest_state(&"second"), "b", "started as soon as the first was done")
	t.eq(state.tracked_quest, &"second", "the tracker moves to it")
	state.set_flag("q", "b", true)
	t.ok(state.quest_is_done(&"second"), "and it moves on like any other")
	_end()

func test_a_quest_fails_and_stays_failed(t) -> void:
	var state := _state()
	var toasts := []
	RpgUtil.events().notify.connect(func(text: String) -> void: toasts.append(text))
	var escort := _quest(&"escort", [{"id": "walk", "complete_when": "flag:q.arrived"}])
	escort.fail_when = "flag:q.lost"
	escort.rewards = {"gold": 50}
	state.quest_defs[&"escort"] = escort
	state.quest_start(&"escort")
	state.set_flag("q", "lost", true)
	t.ok(state.quest_is_failed(&"escort"))
	t.ok(RpgCondition.evaluate("quest_failed:escort"))
	t.ok(RpgCondition.evaluate("quest:escort=failed"), "the older atom sees the same state")
	t.ok(not state.quest_is_active(&"escort"))
	t.ok(toasts.has("Quest failed: Escort"), str(toasts))
	state.set_flag("q", "arrived", true)
	t.ok(not state.quest_complete(&"escort"), "a failed quest cannot be completed")
	t.eq(state.gold, 0, "and gives nothing")
	t.ok(not state.quest_start(&"escort"), "nor started again")
	t.eq(state.journal_ids(true), [&"escort"] as Array[StringName], "listed with the finished ones")
	t.eq(state.journal_ids(false), [] as Array[StringName])
	t.eq(RpgJournalMenu.row_text(state, &"escort"), "Escort (failed)")
	_end()

func test_the_fail_event_and_a_quest_not_under_way(t) -> void:
	var state := _state()
	state.quest_defs[&"q"] = _quest(&"q", [{"id": "a", "complete_when": ""}])
	t.ok(not state.quest_fail(&"q"), "not started")
	state.quest_start(&"q")
	t.ok(RpgDialogueRunner.execute_event("quest_fail:q"))
	t.ok(state.quest_is_failed(&"q"))
	t.ok(not RpgDialogueRunner.execute_event("quest_fail:"))
	t.eq(RpgDialogueRunner.event_problem("quest_fail:q", {"quest": ["q"]}), "")
	t.eq(RpgDialogueRunner.event_problem("quest_turn_in:nope", {"quest": ["q"]}), "unknown quest 'nope'")
	_end()

func test_a_stage_waits_to_be_turned_in_and_counts_live(t) -> void:
	var state := _state()
	_logs(state)
	state.quest_start(&"logs")
	t.eq(state.quest_progress(&"logs")[0]["have"], 0)
	state.inventory.add(&"log", 5)
	t.eq(RpgQuestTracker.progress_text(state, &"logs"), "Log 5/8")
	state.inventory.add(&"log", 4)
	t.eq(state.quest_state(&"logs"), "gather", "it does not move on by itself")
	t.ok(state.quest_ready(&"logs"))
	t.ok(RpgCondition.evaluate("quest_ready:logs"))
	t.eq(RpgQuestTracker.step_text(state, &"logs"), "Bring logs (Log 8/8)\nReady to turn in", "capped at what it needs")
	state.inventory.remove(&"log", 3)
	t.ok(not state.quest_ready(&"logs"), "dropping logs makes it not ready again")
	t.eq(RpgQuestTracker.progress_text(state, &"logs"), "Log 6/8")
	t.ok(not state.quest_turn_in(&"logs"), "refused, and nothing changes")
	t.eq(state.inventory.count(&"log"), 6)
	state.inventory.add(&"log", 3)
	t.ok(RpgDialogueRunner.execute_event("quest_turn_in:logs"))
	t.eq(state.inventory.count(&"log"), 1, "the eight logs are taken")
	t.eq(state.gold, 5, "the stage's own reward")
	t.eq(state.quest_state(&"logs"), "thanks")
	t.ok(not state.quest_turn_in(&"logs"), "a stage that does not wait is not turned in")
	_end()

func test_a_stage_that_takes_items_does_not_finish_without_them(t) -> void:
	var state := _state()
	var def := _quest(&"toll", [
		{"id": "pay", "complete_when": "flag:q.asked", "take": [{"item_id": "potion", "qty": 2}]},
		{"id": "pass", "complete_when": ""},
	])
	state.quest_defs[&"toll"] = def
	state.quest_start(&"toll")
	state.set_flag("q", "asked", true)
	t.eq(state.quest_state(&"toll"), "pay", "the potions are not in the bag")
	state.inventory.add(&"potion", 3)
	t.eq(state.quest_state(&"toll"), "pass", "moved on by itself when they came")
	t.eq(state.inventory.count(&"potion"), 1)
	_end()

func test_progress_reads_the_counting_atoms(t) -> void:
	var state := _state()
	state.gold = 30
	state.set_var("planks", 2)
	var counts := RpgQuestDefinition.progress_of("flag:a.b and item:log>=3 and gold>=100 and var:planks>4 and var:nails>=1 and level>=2", state)
	t.eq(counts.size(), 5, "the flag counts nothing")
	t.eq([counts[0]["what"], counts[0]["have"], counts[0]["need"]], ["log", 0, 3])
	t.eq([counts[1]["what"], counts[1]["have"], counts[1]["need"]], ["gold", 30, 100])
	t.eq([counts[2]["what"], counts[2]["have"], counts[2]["need"]], ["planks", 2, 5], "more than 4 is 5")
	t.eq([counts[3]["what"], counts[3]["need"]], ["nails", 1])
	t.eq([counts[4]["what"], counts[4]["have"], counts[4]["need"]], ["level", 1, 2])
	t.eq(RpgQuestDefinition.progress_of("item:log quest_done:x var:a<3", state), [] as Array[Dictionary], "no counts")
	_end()

func test_the_tracker_follows_the_quests(t) -> void:
	var state := _state()
	state.quest_defs[&"a"] = _quest(&"a", [{"id": "s", "description": "Do a", "complete_when": ""}])
	state.quest_defs[&"b"] = _quest(&"b", [{"id": "s", "description": "Do b", "complete_when": ""}])
	state.quest_start(&"a")
	state.quest_start(&"b")
	t.eq(state.tracked_quest, &"a", "the first quest started")
	t.ok(RpgDialogueRunner.execute_event("track_quest:b"))
	t.eq(state.tracked_quest, &"b")
	t.eq(RpgJournalMenu.row_text(state, &"b"), "B  [Tracked]")
	t.eq(RpgQuestTracker.step_text(state, &"b"), "Do b")
	var back: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	t.eq(back.get("tracked_quest"), "b", "saved")
	state.quest_complete(&"b")
	t.eq(state.tracked_quest, &"a", "the tracker moves to a quest still under way")
	state.from_dict(back)
	t.eq(state.tracked_quest, &"b", "loaded")
	t.ok(not state.track_quest(&"nope"))
	t.eq(state.tracked_quest, &"", "an unknown quest tracks nothing")
	t.ok(not state.to_dict().has("tracked_quest"), "nothing tracked, nothing saved")
	back.erase("tracked_quest")
	state.from_dict(back)
	t.eq(state.tracked_quest, &"", "an older save tracks nothing")
	_end()

func test_the_tracker_shows_the_tracked_quest(t) -> void:
	var state := _state()
	_logs(state)
	var tracker := RpgQuestTracker.new()
	Fixtures.tree().root.add_child(tracker)
	tracker.refresh()
	t.ok(not tracker.visible, "nothing tracked")
	state.quest_start(&"logs")
	tracker.refresh()
	# (no map is active in a unit test: the tracker stays hidden, its text is step_text's)
	t.ok(not tracker.visible, "no map")
	tracker.free()
	_end()

func test_the_new_keys_are_checked_and_kept(t) -> void:
	var quest := _quest(&"q", [
		{"id": "a", "complete_when": "", "turn_in": "yes", "take": [{"qty": 2}]},
		{"id": "b", "complete_when": "", "take": "log"},
	])
	quest.requires = "banana:"
	quest.fail_when = "quest_done:"
	var found := quest.problems()
	t.ok(found.has("stage 1 (a): 'turn_in' must be true or false"), str(found))
	t.ok(found.has("stage 1 (a): every item it takes needs an 'item_id'"), str(found))
	t.ok(found.has("stage 2 (b): 'take' must be a list"), str(found))
	t.ok(found.any(func(why: String) -> bool: return why.begins_with("what the quest requires: ")), str(found))
	t.ok(found.any(func(why: String) -> bool: return why.begins_with("what fails the quest: ")), str(found))
	var lone := _quest(&"lone", [{"id": "a", "complete_when": ""}])
	lone.auto_start = true
	t.eq(lone.problems(), ["the quest starts by itself but requires nothing: give it a condition"])
	var data := {"id": "c", "title": "C", "stages": [{"id": "a", "complete_when": "item:log>=2", "turn_in": true}],
		"rewards": {}, "requires": "quest_done:b", "auto_start": true, "fail_when": "flag:x.y"}
	t.eq(RpgQuestDefinition.from_dict(data).to_dict(), data)
	var plain := _quest(&"p", [{"id": "a", "complete_when": ""}])
	t.ok(not plain.to_dict().has("requires") and not plain.to_dict().has("auto_start"), "written only when set")
	var turn := _quest(&"t", [{"id": "a", "complete_when": "gold>=0", "turn_in": true}, {"id": "b", "complete_when": ""}])
	var pretend := RpgGameState.new()
	t.eq(turn.reached(pretend), "a", "a stage that waits stops the editor's test")
	turn.stages[0].erase("turn_in")
	t.eq(turn.reached(pretend), "b", "one that does not wait is passed")
	pretend.free()
