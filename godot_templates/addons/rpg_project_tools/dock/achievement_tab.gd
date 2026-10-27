@tool
extends "data_tab.gd"
## The Achievements tab (1.5.0): the achievements in res://game/data/achievements, one a file.
## The form: id, title, description, the condition that unlocks it (checked as you type, with
## the counters the game keeps by itself listed under it), secret, points, rewards and the icon
## (a texture's path); what is wrong with it; a test against a pretend game state (its counters
## and gold); JSON export and import. Every change is one undo step.

const ACHIEVEMENTS_DIR := "res://game/data/achievements"
const DialogueTab := preload("dialogue_tab.gd")
const QuestTab := preload("quest_tab.gd")
## What the game counts by itself, for the hint under the condition.
const COUNTERS_HINT := "Counted by the game: count:defeated>=N, count:defeated:<enemy id>>=N, count:items:<item id>>=N, count:quests_done>=N; the event count:<name>[:N] counts anything else."

var achievement: RpgAchievement = null
var test_state: RpgGameState = RpgGameState.new()
var achievements_dir := ACHIEVEMENTS_DIR  # tests point the tab at their own folder

var _id: LineEdit
var _title: LineEdit
var _description: LineEdit
var _when: LineEdit
var _when_note: Label
var _secret: CheckBox
var _points: SpinBox
var _rewards: TextEdit
var _icon: LineEdit
var _problems: Label
var _test_counter: LineEdit
var _test_count: SpinBox
var _test_gold: SpinBox
var _test_result: Label

func _init() -> void:
	name = "Achievements"
	build_top([["New", new_achievement]])
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(scroll)
	var form := VBoxContainer.new()
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(form)
	_id = _field(form, "Id", "id")
	_title = _field(form, "Title (a text key)", "title")
	_description = _field(form, "Description (a text key)", "description")
	_when = _field(form, "Unlocked when (a condition; empty: only the event unlock_achievement)", "when")
	_when.placeholder_text = "e.g. count:defeated>=10 and level>=5"
	_when.text_changed.connect(func(text: String) -> void: _when_note.text = DialogueTab.condition_preview(text, test_state))
	_when_note = note(form)
	var hint := Label.new()
	hint.text = COUNTERS_HINT
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.modulate = Color(1, 1, 1, 0.7)
	form.add_child(hint)
	_secret = CheckBox.new()
	_secret.text = "Secret: shown as ??? until it is unlocked"
	_secret.toggled.connect(func(on: bool) -> void: set_property("secret", on))
	form.add_child(_secret)
	_points = SpinBox.new()
	_points.max_value = 9999
	_points.rounded = true
	_points.value_changed.connect(func(value: float) -> void:
		if not _loading:
			set_property("points", roundi(value)))
	row(form, "Points", _points)
	_rewards = TextEdit.new()
	_rewards.custom_minimum_size = Vector2(0, 46)
	_rewards.placeholder_text = "one per line: gold 25, experience 5, potion x2"
	_rewards.focus_exited.connect(func() -> void: set_property("rewards", QuestTab.parse_rewards(_rewards.text)))
	row(form, "Rewards", _rewards)
	_icon = LineEdit.new()
	_icon.placeholder_text = "res://... a texture (empty: none)"
	_icon.text_submitted.connect(func(text: String) -> void: set_icon(text))
	_icon.focus_exited.connect(func() -> void: set_icon(_icon.text))
	row(form, "Icon", _icon)
	_problems = note(form)
	form.add_child(HSeparator.new())
	var test_title := Label.new()
	test_title.text = "Test (a pretend game state)"
	form.add_child(test_title)
	var counter_row := HBoxContainer.new()
	_test_counter = LineEdit.new()
	_test_counter.placeholder_text = "a counter, e.g. defeated"
	_test_counter.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	counter_row.add_child(_test_counter)
	_test_count = SpinBox.new()
	_test_count.max_value = 999999
	counter_row.add_child(_test_count)
	form.add_child(counter_row)
	_test_gold = SpinBox.new()
	_test_gold.max_value = 999999
	_test_gold.prefix = "gold "
	form.add_child(_test_gold)
	button(form, "Test", func() -> void: run_test())
	_test_result = Label.new()
	_test_result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	form.add_child(_test_result)
	build_status()

func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and test_state != null and is_instance_valid(test_state):
		test_state.free()

func _field(parent: Control, label_text: String, property: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.text_submitted.connect(func(text: String) -> void: set_property(property, _typed(property, text)))
	edit.focus_exited.connect(func() -> void: set_property(property, _typed(property, edit.text)))
	row(parent, label_text, edit)
	return edit

static func _typed(property: String, text: String) -> Variant:
	return StringName(text.strip_edges()) if property == "id" else text.strip_edges()

# ---------------------------------------------------------------- files

func folder() -> String:
	return achievements_dir

func context_object() -> Object:
	return achievement

func open(path: String) -> bool:
	var res := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgAchievement
	if res == null:
		say("%s is not an achievement." % path)
		return false
	achievement = res
	file_path = path
	dirty = false
	_refresh()
	say("%s." % path.get_file())
	return true

func save() -> bool:
	if achievement == null or file_path == "":
		return false
	var err := ResourceSaver.save(achievement, file_path)
	dirty = err != OK
	say("Saved %s." % file_path.get_file() if err == OK else "Could not save (error %d)." % err)
	return err == OK

func new_achievement() -> String:
	var made := RpgAchievement.new()
	DirAccess.make_dir_recursive_absolute(folder())
	var path := free_path("new_achievement")
	made.id = StringName(path.get_file().get_basename())
	made.title = "ACHIEVEMENT_%s_NAME" % String(made.id).to_upper()
	made.description = "ACHIEVEMENT_%s_DESC" % String(made.id).to_upper()
	made.when = "count:defeated>=1"
	if ResourceSaver.save(made, path) != OK:
		say("Could not save %s." % path)
		return ""
	file_path = path
	rescan()
	open(path)
	return path

func to_json_text() -> String:
	return JSON.stringify(achievement.to_dict(), "  ", false) + "\n" if achievement != null else ""

func import_json(json_path: String) -> String:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	if not (parsed is Dictionary) or not RpgUtil.to_dict(parsed).has("when"):
		say("%s is not achievement JSON." % json_path.get_file())
		return ""
	var made := RpgAchievement.from_dict(RpgUtil.to_dict(RpgUtil.restore_numbers(parsed)))
	DirAccess.make_dir_recursive_absolute(folder())
	var target := folder().path_join(json_path.get_file().get_basename() + ".tres")
	if ResourceSaver.save(made, target) != OK:
		say("Could not save %s." % target)
		return ""
	file_path = target
	rescan()
	open(target)
	return target

# ---------------------------------------------------------------- showing

func problems() -> Array[String]:
	var out: Array[String] = achievement.problems() if achievement != null else [] as Array[String]
	if achievement != null and _icon != null and _icon.text != "" and not ResourceLoader.exists(_icon.text):
		out.append("the icon %s does not exist" % _icon.text)
	return out

func _refresh() -> void:
	if achievement == null:
		return
	_loading = true
	_id.text = String(achievement.id)
	_title.text = achievement.title
	_description.text = achievement.description
	_when.text = achievement.when
	_when_note.text = DialogueTab.condition_preview(achievement.when, test_state)
	_secret.set_pressed_no_signal(achievement.secret)
	_points.value = achievement.points
	_rewards.text = QuestTab.rewards_text(achievement.rewards)
	_icon.text = achievement.icon.resource_path if achievement.icon != null else ""
	_loading = false
	_problems.text = "\n".join(PackedStringArray(problems()))
	run_test()

# ---------------------------------------------------------------- edits (one undo step each)

func _apply(value: Array) -> void:
	achievement.set(str(value[0]), value[1])
	dirty = true
	_refresh()

func set_property(property: String, value: Variant) -> void:
	if _loading or achievement == null:
		return
	var old: Variant = achievement.get(property)
	if typeof(old) == typeof(value) and old == value:
		return
	record("Edit achievement", &"_apply", [property, value], [property, old])

## The icon from a texture's path ("" takes it away; a path that is no texture is refused).
func set_icon(path: String) -> void:
	var clean := path.strip_edges()
	if clean == "":
		set_property("icon", null)
		return
	var texture := load(clean) as Texture2D if ResourceLoader.exists(clean) else null
	if texture == null:
		say("%s is not a texture." % clean)
		return
	set_property("icon", texture)

# ---------------------------------------------------------------- the test

## Whether the achievement unlocks with the pretend state (the counter and the gold of the test
## row), also shown.
func run_test() -> bool:
	if achievement == null:
		return false
	test_state.counters.clear()
	if _test_counter.text.strip_edges() != "":
		test_state.counters[_test_counter.text.strip_edges()] = roundi(_test_count.value)
	test_state.gold = roundi(_test_gold.value)
	var unlocked := achievement.when.strip_edges() != "" and RpgCondition.evaluate_on(achievement.when, test_state)
	var counts: PackedStringArray = []
	for count in RpgQuestDefinition.progress_of(achievement.when, test_state):
		counts.append("%s %d/%d" % [count["what"], RpgUtil.to_int(count["have"]), RpgUtil.to_int(count["need"])])
	_test_result.text = ("It unlocks." if unlocked else "It does not unlock yet.") + (" (%s)" % ", ".join(counts) if not counts.is_empty() else "")
	return unlocked
