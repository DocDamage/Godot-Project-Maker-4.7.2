class_name RpgDialogueBox
extends CanvasLayer
## Shows a dialogue at the bottom of the screen. Scene unique names: Panel, Portrait, Speaker, Body,
## Choices. Joins the group "rpg_dialogue_box" so NPCs and signs can find it.
##
## The panel stands on the bottom edge of the screen and grows upward: a line with choices needs
## more room than the panel's own height, and that room is above it, not under the screen.
##
## 1.5.0 (T18.08): it grows to at most MAX_SHARE of the screen's height; when the choices need
## more, they scroll. The script puts %Choices into a ScrollContainer (`ChoicesScroll`, with
## `follow_focus`) when the box is made, so the scene of an older game scrolls too: the keyboard
## and the gamepad bring the focused choice into view, and the mouse wheel scrolls.

## The most of the screen's height the box may take.
const MAX_SHARE := 0.7

var runner := RpgDialogueRunner.new()
var _actor: Node = null
var _open := false
var _tween: Tween = null

func _ready() -> void:
	add_to_group("rpg_dialogue_box")
	layer = 50
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false
	var panel := get_node_or_null("%Panel") as Control
	if panel != null:
		panel.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_wrap_choices()

## Puts %Choices into a ScrollContainer in its place (once; the scene has none).
func _wrap_choices() -> void:
	var choices := get_node_or_null("%Choices") as Control
	if choices == null or choices.get_parent() is ScrollContainer:
		return
	var holder := choices.get_parent()
	var scroll := ScrollContainer.new()
	scroll.name = "ChoicesScroll"
	scroll.follow_focus = true
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var at := choices.get_index()
	holder.remove_child(choices)
	holder.add_child(scroll)
	holder.move_child(scroll, at)
	choices.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(choices)
	choices.owner = owner if owner != null else self

## The scroll the choices are in (null in a box that was never ready).
func choices_scroll() -> ScrollContainer:
	return _choices().get_parent() as ScrollContainer

## Gives the scroll the height of the choices, but no more than leaves the box within MAX_SHARE
## of the screen.
func _fit_choices() -> void:
	var scroll := choices_scroll()
	var panel := get_node_or_null("%Panel") as Control
	if scroll == null or panel == null:
		return
	scroll.custom_minimum_size.y = 0.0
	var screen := get_viewport().get_visible_rect().size.y if get_viewport() != null else 360.0
	var rest := panel.get_combined_minimum_size().y  # the box without its choices
	var want := _choices().get_combined_minimum_size().y
	var room := maxf(MAX_SHARE * screen - rest, 0.0)
	var one := 0.0
	if _choices().get_child_count() > 0:
		one = (_choices().get_child(0) as Control).get_combined_minimum_size().y
	scroll.custom_minimum_size.y = minf(want, maxf(room, one))

func is_open() -> bool:
	return _open

## Opens the dialogue. The actor (if any) cannot move while it is open.
func open(res: RpgDialogueResource, actor: Node = null) -> void:
	if _open or res == null:
		return
	runner.start(res)
	if runner.is_finished():
		return
	_open = true
	_actor = actor
	if _actor != null and "input_enabled" in _actor:
		_actor.set("input_enabled", false)
	visible = true
	RpgUtil.emit(&"dialogue_started", [res])
	_show_current()

## Runs the rest of the open dialogue without showing it (its events, the first choice at every
## choice) and closes the box. A skipped sequence uses this.
func fast_forward() -> void:
	if not _open:
		return
	runner.fast_forward()
	_close()

func _body() -> RichTextLabel:
	return get_node("%Body") as RichTextLabel

func _choices() -> Container:
	return get_node("%Choices") as Container

func _show_current() -> void:
	var line := runner.current()
	if line == null:
		_close()
		return
	(get_node("%Speaker") as Label).text = tr(line.speaker) if line.speaker != "" else ""
	var portrait := get_node("%Portrait") as TextureRect
	portrait.texture = line.portrait
	portrait.visible = line.portrait != null
	var body := _body()
	body.bbcode_enabled = false
	body.text = tr(line.text)
	_clear_choices()
	var cps := _cps()
	if _tween != null:
		_tween.kill()
	if cps <= 0.0 or body.text.length() == 0:
		body.visible_ratio = 1.0
		_show_choices()
	else:
		body.visible_ratio = 0.0
		_tween = create_tween()
		_tween.tween_property(body, "visible_ratio", 1.0, float(body.text.length()) / cps)
		_tween.finished.connect(_show_choices)

func _cps() -> float:
	var settings := RpgUtil.settings()
	return RpgUtil.to_float(settings.text_cps()) if settings != null else 40.0

func _clear_choices() -> void:
	for child in _choices().get_children():
		_choices().remove_child(child)
		child.queue_free()
	var scroll := choices_scroll()
	if scroll != null:
		scroll.custom_minimum_size.y = 0.0

func _show_choices() -> void:
	if not _open or not _choices().get_children().is_empty():
		return
	var options := runner.visible_choices()
	for i in options.size():
		var button := Button.new()
		button.text = tr(options[i].text)
		button.name = "Choice%d" % i
		button.pressed.connect(_on_choice.bind(i))
		_choices().add_child(button)
	var buttons := _choices().get_children()
	for i in buttons.size():
		var b := buttons[i] as Button
		var prev := buttons[(i - 1 + buttons.size()) % buttons.size()] as Button
		var nxt := buttons[(i + 1) % buttons.size()] as Button
		b.focus_neighbor_top = b.get_path_to(prev)
		b.focus_neighbor_bottom = b.get_path_to(nxt)
	_fit_choices()
	if not buttons.is_empty():
		(buttons[0] as Button).grab_focus()

func _on_choice(i: int) -> void:
	runner.choose(i)
	_show_current()

func _unhandled_input(event: InputEvent) -> void:
	if not _open or not event.is_action_pressed("confirm"):
		return
	get_viewport().set_input_as_handled()
	var body := _body()
	if body.visible_ratio < 1.0:
		if _tween != null:
			_tween.kill()
		body.visible_ratio = 1.0
		_show_choices()
		return
	var buttons := _choices().get_children()
	if not buttons.is_empty():
		var focus := get_viewport().gui_get_focus_owner()
		var index := buttons.find(focus)
		_on_choice(maxi(index, 0))
		return
	runner.advance()
	_show_current()

func _close() -> void:
	var res := runner.resource
	_open = false
	visible = false
	_clear_choices()
	if _tween != null:
		_tween.kill()
	RpgUtil.emit(&"dialogue_finished", [res])
	var actor := _actor
	_actor = null
	if actor != null and is_instance_valid(actor) and "input_enabled" in actor:
		# Wait two physics frames so the confirm key that closed the box is not also read as
		# a new "interact" press.
		await get_tree().physics_frame
		await get_tree().physics_frame
		if is_instance_valid(actor):
			actor.set("input_enabled", true)
