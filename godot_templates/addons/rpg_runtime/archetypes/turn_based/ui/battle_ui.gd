class_name RpgBattleUi
extends CanvasLayer
## The battle's interface. The scene recipe builds the nodes (unique names below); this script
## fills them: one button per command, the item list, the target arrow, the log and the status
## panels. It answers the controller's questions with `request_command` and the log calls.
##
##   %CommandPanel > %Commands   buttons, one per command (attack / defend / item / skill / run)
##   %ItemSubmenu  > %ItemList   consumables, or the skills of the Skill command
##   %TargetCursor               blinking arrow over the selected battler
##   %BattleLog    > %LogLabel   one entry at a time; `confirm` or LOG_SECONDS moves on
##   %PartyStatus, %EnemyStatus  name (+ statuses) + HP bar per battler, HP and MP numbers

signal choice_made(choice: Dictionary)

const LOG_SECONDS := 0.8
const MESSAGE_SECONDS := 1.2
const REWARD_SECONDS := 1.6
## From this many battlers a side's status panel uses small text, so four rows still fit the screen.
const COMPACT_FROM := 3
const COMPACT_FONT := 9

var controller: RpgBattleController = null

var _anchor_of: Callable = Callable()  # actor -> Vector2, the tip of the target arrow
var _actor: RpgBattleActor = null
var _active: RpgBattleActor = null  # marked in the party panel while choosing
var _buttons: Dictionary = {}  # command id -> Button
var _mode: StringName = &"none"  # none, commands, items (items or skills), target, log
var _candidates: Array[RpgBattleActor] = []
var _target_index := 0
var _pending: Dictionary = {}  # {command, extra} while a target is being chosen
var _from_items := false
var _advance := false
var _rows: Dictionary = {}  # actor -> {bar, text}

func _node(unique_name: String) -> Node:
	return get_node_or_null("%" + unique_name)

func _ready() -> void:
	layer = 20
	for hidden: String in ["CommandPanel", "ItemSubmenu", "BattleLog"]:
		var panel := _node(hidden) as Control
		if panel != null:
			panel.visible = false

## Builds the command buttons and the status rows for `p_controller`'s battlers.
## `anchor_of` maps an actor to the canvas point the target arrow should touch.
func bind(p_controller: RpgBattleController, anchor_of: Callable) -> void:
	controller = p_controller
	_anchor_of = anchor_of
	_build_commands()
	_build_status(_node("PartyStatus"), controller.party, true)
	_build_status(_node("EnemyStatus"), controller.enemies, false)
	refresh()

func _clear(box: Node) -> void:
	for child in box.get_children():
		box.remove_child(child)
		child.queue_free()

func _build_commands() -> void:
	var box := _node("Commands") as VBoxContainer
	if box == null:
		return
	_clear(box)
	_buttons.clear()
	for command in controller.commands:
		var b := Button.new()
		b.name = "Cmd_" + String(command.id)
		b.text = RpgBattleText.t(command.label)
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.pressed.connect(_on_command_pressed.bind(command))
		box.add_child(b)
		_buttons[command.id] = b

func _build_status(box: Node, actors: Array[RpgBattleActor], with_numbers: bool) -> void:
	if box == null:
		return
	_clear(box)
	var compact := actors.size() >= COMPACT_FROM
	for actor in actors:
		var row := VBoxContainer.new()
		row.name = "Row_" + String(actor.id)
		row.add_theme_constant_override("separation", 0 if compact else 4)
		var name_label := Label.new()
		name_label.text = actor.display_name
		if compact:
			name_label.add_theme_font_size_override("font_size", COMPACT_FONT)
		row.add_child(name_label)
		var bar := ProgressBar.new()
		bar.show_percentage = false
		bar.custom_minimum_size = Vector2(88, 6)
		bar.add_theme_stylebox_override("fill", _bar_style(Color("#5cc96a") if with_numbers else Color("#d9534f")))
		bar.add_theme_stylebox_override("background", _bar_style(Color(0, 0, 0, 0.55)))
		bar.max_value = maxi(1, actor.max_hp())
		bar.value = actor.stats.hp
		row.add_child(bar)
		var numbers: Label = null
		if with_numbers:
			numbers = Label.new()
			if compact:
				numbers.add_theme_font_size_override("font_size", COMPACT_FONT)
			row.add_child(numbers)
		box.add_child(row)
		_rows[actor] = {"bar": bar, "text": numbers, "name": name_label}

static func _bar_style(color: Color) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = color
	box.set_corner_radius_all(2)
	return box

## Updates every HP bar and number from the battlers' stats.
func refresh() -> void:
	for actor: RpgBattleActor in _rows.keys():
		var row: Dictionary = _rows[actor]
		var bar: ProgressBar = row["bar"]
		bar.max_value = maxi(1, actor.max_hp())
		bar.value = maxi(0, actor.stats.hp)
		var numbers: Label = row["text"]
		if numbers != null:
			numbers.text = numbers_text(actor)
		var name_label: Label = row["name"]
		name_label.modulate = Color.WHITE if actor.alive else Color(1, 1, 1, 0.45)
		name_label.text = _name_text(actor)

## "> Name [Poison, Sleep]": the arrow for whose turn it is, then the statuses.
func _name_text(actor: RpgBattleActor) -> String:
	var text := ("> " if actor == _active else "") + actor.display_name
	var shown := PackedStringArray()
	for status in actor.status_list():
		shown.append(RpgBattleStatus.label(status))
	if not shown.is_empty():
		text += " [%s]" % ", ".join(shown)
	return text

static func numbers_text(actor: RpgBattleActor) -> String:
	var text := "%s %d/%d" % [TranslationServer.translate("UI_HP"), maxi(0, actor.stats.hp), actor.max_hp()]
	if actor.max_mp() > 0:
		text += "  %s %d/%d" % [TranslationServer.translate("UI_MP"), actor.stats.mp, actor.max_mp()]
	return text

# ---------------------------------------------------------------- asking for a command

## The controller's question: which command, and for whom? Returns
## {command_id, target_index, item_id} once the player has decided.
func request_command(actor: RpgBattleActor, _battle: RpgBattleController = null) -> Dictionary:
	_actor = actor
	_show_commands()
	var choice: Dictionary = await choice_made
	_hide_input_panels()
	return choice

## Marks whose turn it is in the party panel (nobody for null): "> Name".
func _mark_active(active: RpgBattleActor) -> void:
	_active = active
	for actor: RpgBattleActor in _rows.keys():
		var name_label: Label = _rows[actor]["name"]
		name_label.text = _name_text(actor)

func _show_commands() -> void:
	_mode = &"commands"
	_mark_active(_actor)
	_hide(_node("ItemSubmenu"))
	_hide_cursor()
	_show_log_text("")
	var panel := _node("CommandPanel") as Control
	panel.visible = true
	var enabled: Array[Button] = []
	for command in controller.commands:
		var b: Button = _buttons[command.id]
		b.disabled = not command.can_use(_actor, controller)
		if not b.disabled:
			enabled.append(b)
	RpgMenuUtil.wire_vertical(enabled)
	if not enabled.is_empty():
		enabled[0].grab_focus()

func _on_command_pressed(command: RpgBattleCommand) -> void:
	if _mode != &"commands":
		return
	match command.id:
		&"item":
			_show_items(command)
		&"skill":
			_show_skills(command)
		_:
			match command.targets:
				RpgBattleCommand.TARGET_SELF, RpgBattleCommand.TARGET_ALL_ENEMIES:
					_decide(command, 0, {})
				_:
					_begin_target(command, {}, false)

func _show_items(command: RpgBattleCommand) -> void:
	var list := _node("ItemList") as VBoxContainer
	var submenu := _node("ItemSubmenu") as Control
	_clear(list)
	var buttons: Array[Button] = []
	for slot in (command as RpgItemCommand).usable_items(_actor, controller):
		var inv := controller.inventory_of(_actor)
		var b := Button.new()
		var item_id: StringName = slot["item_id"]
		b.name = "Item_" + String(item_id)
		b.text = "%s x%d" % [RpgBattleText.item_name(inv.definition(item_id), item_id), slot["qty"]]
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.pressed.connect(_on_item_pressed.bind(command, item_id))
		list.add_child(b)
		buttons.append(b)
	if buttons.is_empty():
		var none := Label.new()
		none.text = RpgBattleText.t("BATTLE_NO_ITEMS")
		list.add_child(none)
		return
	RpgMenuUtil.wire_vertical(buttons)
	_mode = &"items"
	submenu.visible = true
	buttons[0].grab_focus()

func _on_item_pressed(command: RpgBattleCommand, item_id: StringName) -> void:
	if _mode != &"items":
		return
	_hide(_node("ItemSubmenu"))
	_begin_target(command, {"item_id": item_id}, true)

## The skill list (in the item submenu): "Fire  3 MP" for each skill the actor can use now.
func _show_skills(command: RpgBattleCommand) -> void:
	var list := _node("ItemList") as VBoxContainer
	var submenu := _node("ItemSubmenu") as Control
	_clear(list)
	var buttons: Array[Button] = []
	for skill in (command as RpgSkillCommand).usable_skills(_actor, controller):
		var b := Button.new()
		b.name = "Skill_" + String(skill.id)
		b.text = skill.label() if skill.mp_cost <= 0 else "%s  %d %s" % [skill.label(), skill.mp_cost, tr("UI_MP")]
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.pressed.connect(_on_skill_pressed.bind(command, skill.id))
		list.add_child(b)
		buttons.append(b)
	if buttons.is_empty():
		var none := Label.new()
		none.text = RpgBattleText.t("BATTLE_NO_SKILLS")
		list.add_child(none)
		return
	RpgMenuUtil.wire_vertical(buttons)
	_mode = &"items"
	submenu.visible = true
	buttons[0].grab_focus()

func _on_skill_pressed(command: RpgBattleCommand, skill_id: StringName) -> void:
	if _mode != &"items":
		return
	_hide(_node("ItemSubmenu"))
	var kind := controller.targets_of(command, skill_id)
	if kind == RpgBattleCommand.TARGET_SELF or RpgBattleController.aims_at_all(kind):
		_decide(command, 0, {"skill_id": skill_id})
		return
	_begin_target(command, {"skill_id": skill_id}, true)

func _begin_target(command: RpgBattleCommand, extra: Dictionary, from_items: bool) -> void:
	var skill_id := StringName(str(extra.get("skill_id", "")))
	_candidates = controller.candidates(_actor, command, skill_id)
	if _candidates.is_empty():
		_show_commands()
		return
	if controller.targets_of(command, skill_id) == RpgBattleCommand.TARGET_ONE_ALLY and _candidates.size() == 1:
		_decide(command, 0, extra)
		return
	_pending = {"command": command, "extra": extra}
	_from_items = from_items
	_target_index = 0
	_mode = &"target"
	get_viewport().gui_release_focus()  # arrows and confirm now reach _unhandled_input
	_show_log_text(RpgBattleText.t("BATTLE_CHOOSE_TARGET"))
	_point_cursor()

func _point_cursor() -> void:
	var cursor := _node("TargetCursor") as RpgTargetCursor
	if cursor != null and _anchor_of.is_valid():
		var tip: Vector2 = _anchor_of.call(_candidates[_target_index])
		cursor.point_at(tip)

func _hide_cursor() -> void:
	var cursor := _node("TargetCursor") as RpgTargetCursor
	if cursor != null:
		cursor.hide_cursor()

func _decide(command: RpgBattleCommand, target_index: int, extra: Dictionary) -> void:
	var choice := {"command_id": command.id, "target_index": target_index}
	choice.merge(extra)
	_mode = &"none"
	choice_made.emit(choice)

func _hide(node: Node) -> void:
	if node is Control:
		(node as Control).visible = false

func _hide_input_panels() -> void:
	_mark_active(null)
	_hide(_node("CommandPanel"))
	_hide(_node("ItemSubmenu"))
	_hide_cursor()
	_show_log_text("")

func _show_log_text(text: String) -> void:
	var panel := _node("BattleLog") as Control
	var label := _node("LogLabel") as Label
	if panel == null or label == null:
		return
	label.text = text
	panel.visible = text != ""

# ---------------------------------------------------------------- input

static func _pressed(event: InputEvent, action: String) -> bool:
	return InputMap.has_action(action) and event.is_action_pressed(action)

func _unhandled_input(event: InputEvent) -> void:
	match _mode:
		&"target":
			_target_input(event)
		&"items":
			if _pressed(event, "cancel") or _pressed(event, "ui_cancel"):
				get_viewport().set_input_as_handled()
				_show_commands()
		&"log":
			if _pressed(event, "confirm") or _pressed(event, "ui_accept"):
				get_viewport().set_input_as_handled()
				_advance = true

func _target_input(event: InputEvent) -> void:
	var n := _candidates.size()
	if _pressed(event, "move_left") or _pressed(event, "ui_left"):
		_target_index = (_target_index - 1 + n) % n
		_point_cursor()
	elif _pressed(event, "move_right") or _pressed(event, "ui_right"):
		_target_index = (_target_index + 1) % n
		_point_cursor()
	elif _pressed(event, "confirm") or _pressed(event, "ui_accept"):
		_hide_cursor()
		var picked_command: RpgBattleCommand = _pending["command"]
		var picked_extra: Dictionary = _pending["extra"]
		_decide(picked_command, _target_index, picked_extra)
	elif _pressed(event, "cancel") or _pressed(event, "ui_cancel"):
		_hide_cursor()
		if _from_items:
			_show_commands()
			var back_command: RpgBattleCommand = _pending["command"]
			if back_command.id == &"skill":
				_show_skills(back_command)
			else:
				_show_items(back_command)
		else:
			_show_commands()
	else:
		return
	get_viewport().set_input_as_handled()

## The index of the selected target (tests and the arrow use it).
func target_index() -> int:
	return _target_index

# ---------------------------------------------------------------- showing results

func _wait_advance(seconds: float) -> void:
	_advance = false
	var waited := 0.0
	while waited < seconds and not _advance and is_inside_tree():
		await get_tree().process_frame
		waited += get_process_delta_time()

## Shows the entries one after the other; `confirm` skips ahead, otherwise each stays 0.8 s.
func show_log(entries: Array[Dictionary]) -> void:
	refresh()
	_mode = &"log"
	for entry: Dictionary in entries:
		var text := RpgUtil.to_str(entry.get("text", ""))
		if text == "":
			continue
		_show_log_text(text)
		await _wait_advance(LOG_SECONDS)
	_show_log_text("")
	_mode = &"none"
	refresh()

func show_message(text: String) -> void:
	_mode = &"log"
	_show_log_text(text)
	await _wait_advance(MESSAGE_SECONDS)
	_show_log_text("")
	_mode = &"none"

## Victory text: XP and gold, found items, level ups.
func show_rewards(result: RpgEncounterResult, level_ups: Array) -> void:
	var lines: PackedStringArray = [RpgBattleText.t("BATTLE_VICTORY"), RpgBattleText.t("BATTLE_REWARDS", [result.xp, result.gold])]
	if not result.items.is_empty():
		var names: PackedStringArray = []
		var inv: RpgInventory = null
		if not controller.party.is_empty():
			inv = controller.inventory_of(controller.party[0])
		for drop in result.items:
			var drop_id: StringName = drop["item_id"]
			var drop_def: RpgItemDefinition = null
			if inv != null:
				drop_def = inv.definition(drop_id)
			var item_label := RpgBattleText.item_name(drop_def, drop_id)
			names.append(item_label if RpgUtil.to_int(drop["qty"]) == 1 else "%s x%d" % [item_label, drop["qty"]])
		lines.append(RpgBattleText.t("BATTLE_FOUND", [", ".join(names)]))
	for up: Dictionary in level_ups:
		var leveled: RpgBattleActor = up["actor"]
		lines.append(RpgBattleText.t("BATTLE_LEVEL_UP", [leveled.display_name, up["level"]]))
	_mode = &"log"
	for line in lines:
		_show_log_text(line)
		await _wait_advance(REWARD_SECONDS if line == lines[lines.size() - 1] else LOG_SECONDS * 1.5)
	_show_log_text("")
	_mode = &"none"
