extends RefCounted
## Dialogue: condition language, runner flow, events and JSON import (T6.06).

const Fixtures := preload("../lib/fixtures.gd")
const UiRecipes := preload("res://builder/recipes/ui_recipes.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")

const BOX_TMP := "user://test_dialogue_box.tscn"
## The base resolution of a generated game (the config's default), in both views.
const BASE_RESOLUTION := Vector2i(640, 360)

func _state() -> Node:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion", 99, &"heal", 10)})
	state.new_game()
	return state

func _line(id: String, text: String, next: String = "", condition: String = "", events: Array = []) -> RpgDialogueLine:
	var line := RpgDialogueLine.new()
	line.id = StringName(id)
	line.text = text
	line.next = StringName(next)
	line.condition = condition
	line.events = PackedStringArray(events)
	return line

func _choice(text: String, next: String, condition: String = "") -> RpgDialogueChoice:
	var c := RpgDialogueChoice.new()
	c.text = text
	c.next = StringName(next)
	c.condition = condition
	return c

func _res(lines: Array) -> RpgDialogueResource:
	var res := RpgDialogueResource.new()
	res.lines.assign(lines)
	return res

# ---------------------------------------------------------------- conditions

func test_condition_atoms(t) -> void:
	var state := _state()
	state.gold = 30
	state.player_stats.level = 3
	state.inventory.add(&"potion", 2)
	state.set_flag("npc", "talked", true)
	state.set_flag("npc", "mood", false)
	state.quests["q1"] = "started"
	var table := {
		"flag:npc.talked": true,
		"flag:npc.mood": false,
		"flag:npc.unknown": false,
		"item:potion": true,
		"item:potion>=2": true,
		"item:potion>=3": false,
		"item:sword": false,
		"gold>=30": true,
		"gold>=31": false,
		"level>=3": true,
		"level>=4": false,
		"quest:q1=started": true,
		"quest:q1=done": false,
		"quest:other=started": false,
		"": true,
	}
	for expr in table.keys():
		t.eq(RpgCondition.evaluate(expr), table[expr], "'%s'" % expr)
	Fixtures.uninstall_state()

func test_condition_not_and_or_left_to_right(t) -> void:
	var state := _state()
	state.set_flag("a", "x", true)
	t.eq(RpgCondition.evaluate("not flag:a.x"), false)
	t.eq(RpgCondition.evaluate("not not flag:a.x"), true)
	t.eq(RpgCondition.evaluate("flag:a.x and gold>=999"), false)
	t.eq(RpgCondition.evaluate("flag:a.x or gold>=999"), true)
	# No precedence: (false and false) or true -> true; with precedence it would be the same,
	# so use true or false and false: left to right gives (true or false) and false = false.
	t.eq(RpgCondition.evaluate("flag:a.x or gold>=999 and gold>=999"), false)
	t.ok(RpgCondition.mixes_operators("flag:a.x or gold>=1 and gold>=2"))
	t.ok(not RpgCondition.mixes_operators("flag:a.x and gold>=1"))
	Fixtures.uninstall_state()

func test_unknown_atom_is_false(t) -> void:
	var state := _state()
	t.eq(RpgCondition.evaluate("banana:split"), false)
	t.eq(RpgCondition.evaluate("flag:nodot"), false)
	t.ok(state != null)
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- runner

func test_runner_walks_lines_in_order(t) -> void:
	_state()
	var runner := RpgDialogueRunner.new()
	runner.start(_res([_line("a", "one"), _line("b", "two")]))
	t.eq(runner.current().text, "one")
	runner.advance()
	t.eq(runner.current().text, "two")
	t.ok(not runner.is_finished())
	runner.advance()
	t.ok(runner.is_finished())
	t.ok(runner.current() == null)
	Fixtures.uninstall_state()

func test_runner_choice_jumps_and_next_overrides(t) -> void:
	_state()
	var ask := _line("ask", "?")
	ask.choices.assign([_choice("yes", "yes_line"), _choice("no", "no_line")])
	var res := _res([ask, _line("yes_line", "Yes!", "end"), _line("no_line", "No!"), _line("end", "bye")])
	var runner := RpgDialogueRunner.new()
	runner.start(res)
	runner.advance()  # a line with choices does not advance by itself
	t.eq(runner.current().id, &"ask")
	runner.choose(5)  # out of range: ignored
	t.eq(runner.current().id, &"ask")
	runner.choose(0)
	t.eq(runner.current().text, "Yes!")
	runner.advance()
	t.eq(runner.current().text, "bye", "the next field jumps over no_line")
	Fixtures.uninstall_state()

func test_runner_hides_choices_whose_condition_fails(t) -> void:
	_state()
	var ask := _line("ask", "?")
	ask.choices.assign([_choice("secret", "x", "gold>=9999"), _choice("open", "x")])
	var runner := RpgDialogueRunner.new()
	runner.start(_res([ask, _line("x", "x")]))
	t.eq(runner.visible_choices().size(), 1)
	t.eq(runner.visible_choices()[0].text, "open")
	Fixtures.uninstall_state()

func test_runner_skips_lines_with_false_conditions(t) -> void:
	_state()
	var runner := RpgDialogueRunner.new()
	runner.start(_res([_line("a", "first", "", "gold>=9999"), _line("b", "second"), _line("c", "third", "", "gold>=0")]))
	t.eq(runner.current().text, "second")
	runner.advance()
	t.eq(runner.current().text, "third")
	Fixtures.uninstall_state()

func test_runner_events_run_once_when_a_line_becomes_current(t) -> void:
	var state := _state()
	var before: int = state.gold
	var runner := RpgDialogueRunner.new()
	runner.start(_res([_line("a", "pay", "", "", ["give_gold:5"]), _line("b", "end")]))
	t.eq(state.gold, before + 5)
	runner.current()
	runner.visible_choices()
	t.eq(state.gold, before + 5, "reading the line again does not rerun events")
	runner.advance()
	t.eq(state.gold, before + 5)
	Fixtures.uninstall_state()

func test_runner_empty_and_missing_target(t) -> void:
	_state()
	var runner := RpgDialogueRunner.new()
	runner.start(null)
	t.ok(runner.is_finished())
	runner.start(_res([]))
	t.ok(runner.is_finished())
	runner.start(_res([_line("a", "x", "nowhere")]))
	runner.advance()
	t.ok(runner.is_finished(), "an unknown jump target ends the dialogue")
	Fixtures.uninstall_state()

func test_runner_condition_loop_is_bounded(t) -> void:
	_state()
	var lines: Array = []
	for i in 1200:
		lines.append(_line("l%d" % i, "x", "", "gold>=99999"))
	var runner := RpgDialogueRunner.new()
	runner.start(_res(lines))
	t.ok(runner.is_finished(), "gives up instead of looping forever")
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- events

func test_events(t) -> void:
	var state := _state()
	var seen := []
	RpgUtil.events().dialogue_event.connect(func(n: String, a: String) -> void: seen.append([n, a]))
	t.ok(RpgDialogueRunner.execute_event("set_flag:npc.talked=true"))
	t.eq(state.get_flag("npc", "talked"), true)
	RpgDialogueRunner.execute_event("set_flag:npc.count=3")
	t.eq(state.get_flag("npc", "count"), 3)
	RpgDialogueRunner.execute_event("set_flag:npc.name=Ann")
	t.eq(state.get_flag("npc", "name"), "Ann")
	var potions: int = state.inventory.count(&"potion")
	RpgDialogueRunner.execute_event("give_item:potion:3")
	t.eq(state.inventory.count(&"potion"), potions + 3)
	RpgDialogueRunner.execute_event("take_item:potion:2")
	t.eq(state.inventory.count(&"potion"), potions + 1)
	RpgDialogueRunner.execute_event("give_item:potion")
	t.eq(state.inventory.count(&"potion"), potions + 2)
	state.gold = 10
	RpgDialogueRunner.execute_event("give_gold:15")
	t.eq(state.gold, 25)
	RpgDialogueRunner.execute_event("set_quest:q1=started")
	t.eq(state.quests["q1"], "started")
	state.player_stats.hp = 1
	RpgDialogueRunner.execute_event("heal_full")
	t.eq(state.player_stats.hp, state.player_stats.max_hp)
	RpgDialogueRunner.execute_event("emit:door_opened:north")
	RpgDialogueRunner.execute_event("emit:ping")
	t.eq(seen, [["door_opened", "north"], ["ping", ""]])
	t.ok(not RpgDialogueRunner.execute_event("explode"))
	t.ok(not RpgDialogueRunner.execute_event("give_gold:many"))
	t.ok(not RpgDialogueRunner.execute_event("set_flag:nodot=1"))
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- JSON import

func test_json_import(t) -> void:
	var text := '{"lines": [{"id": "a", "speaker": "Ann", "text": "Hi", "events": ["give_gold:1"], "next": "b", "condition": "gold>=0", "choices": [{"text": "Go", "next": "b", "condition": ""}]}, {"id": "b", "text": "Bye"}]}'
	var res := RpgDialogueJson.from_json(text)
	t.eq(res.lines.size(), 2)
	t.eq(res.lines[0].id, &"a")
	t.eq(res.lines[0].speaker, "Ann")
	t.eq(res.lines[0].next, &"b")
	t.eq(res.lines[0].events[0], "give_gold:1")
	t.eq(res.lines[0].choices.size(), 1)
	t.eq(res.lines[0].choices[0].next, &"b")
	t.eq(res.lines[1].text, "Bye")
	var bare := RpgDialogueJson.from_json('[{"text": "only"}]')
	t.eq(bare.lines.size(), 1)
	t.ok(RpgDialogueJson.from_json("not json") == null)

# ---------------------------------------------------------------- the box on the screen

## The dialogue box of a generated game (the recipe's scene, the runtime's script) on a screen of
## the base resolution, with the text as large as the theme of the game makes it: 8 px for a
## pack of 16 px tiles, 16 px for one of 32 px and for the isometric sample.
func _box_on_screen(font_size: int) -> RpgDialogueBox:
	var screen := SubViewport.new()
	screen.name = "DialogueScreen"
	screen.size = BASE_RESOLUTION
	Fixtures.tree().root.add_child(screen)
	var root: Node = UiRecipes.new().call("_build_dialogue_box")
	SceneUtil.save_scene(root, BOX_TMP)
	var box := (load(BOX_TMP) as PackedScene).instantiate() as RpgDialogueBox
	var look := Theme.new()
	look.default_font_size = font_size
	(box.get_node("Panel") as Control).theme = look
	screen.add_child(box)
	if not box.is_node_ready():
		box._ready()
	return box

func test_every_choice_of_a_line_is_on_the_screen(t) -> void:
	for font_size: int in [8, 16]:
		var box := _box_on_screen(font_size)
		var screen := box.get_parent() as SubViewport
		var line := _line("ask", "Is there anything I can help you with?")
		line.speaker = "Villager"
		line.choices = [_choice("Any tips?", ""), _choice("Would you like to trade with me?", ""), _choice("No, thank you.", "")]
		box.open(_res([line]))
		t.ok(box.is_open())
		(box.get_node("%Body") as RichTextLabel).visible_ratio = 1.0
		box.call("_show_choices")
		await Fixtures.tree().process_frame
		await Fixtures.tree().process_frame
		var seen := Rect2(Vector2.ZERO, Vector2(BASE_RESOLUTION))
		var panel := box.get_node("%Panel") as Control
		var buttons := (box.get_node("%Choices") as Container).get_children()
		t.eq(buttons.size(), 3, "font %d" % font_size)
		t.ok(seen.encloses(panel.get_global_rect()), "font %d: the panel %s lies on the screen %s" % [font_size, panel.get_global_rect(), seen])
		t.near(panel.get_global_rect().end.y, float(BASE_RESOLUTION.y) - 8.0, 0.01, "font %d: it stands on the bottom edge" % font_size)
		for i in buttons.size():
			var button := buttons[i] as Button
			t.ok(seen.encloses(button.get_global_rect()), "font %d: choice %d %s lies on the screen" % [font_size, i, button.get_global_rect()])
			t.ok(panel.get_global_rect().encloses(button.get_global_rect()), "font %d: choice %d lies in the panel" % [font_size, i])
		# a line without choices is as low as it always was
		var plain := _line("plain", "Good morning.")
		box.call("_close")
		box.open(_res([plain]))
		(box.get_node("%Body") as RichTextLabel).visible_ratio = 1.0
		await Fixtures.tree().process_frame
		await Fixtures.tree().process_frame
		if font_size == 8:
			t.near(panel.get_global_rect().position.y, float(BASE_RESOLUTION.y) - 92.0, 0.01, "the panel of a plain line starts where the recipe puts it")
		t.near(panel.get_global_rect().end.y, float(BASE_RESOLUTION.y) - 8.0, 0.01)
		box.call("_close")
		screen.get_parent().remove_child(screen)
		screen.free()
	DirAccess.remove_absolute(BOX_TMP)
