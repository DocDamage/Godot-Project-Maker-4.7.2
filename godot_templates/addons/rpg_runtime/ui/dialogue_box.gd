class_name RpgDialogueBox
extends CanvasLayer
## Shows a dialogue at the bottom of the screen. Scene unique names: Panel, Portrait, Speaker, Body,
## Choices. Joins the group "rpg_dialogue_box" so NPCs and signs can find it.

var runner := RpgDialogueRunner.new()
var _actor: Node = null
var _open := false
var _tween: Tween = null

func _ready() -> void:
	add_to_group("rpg_dialogue_box")
	layer = 50
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false

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
	return float(settings.text_cps()) if settings != null else 40.0

func _clear_choices() -> void:
	for child in _choices().get_children():
		_choices().remove_child(child)
		child.queue_free()

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
