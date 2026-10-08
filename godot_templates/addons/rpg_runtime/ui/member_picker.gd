class_name RpgMemberPicker
extends Control
## Chooses a party member (for an item used from the inventory menu). One button per member with
## their hit points; `chosen` carries the actor id, `closed` always follows. Built in code.

signal chosen(actor_id: StringName)
signal closed

var _buttons: Array[Button] = []

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	process_mode = Node.PROCESS_MODE_ALWAYS
	var dim := ColorRect.new()
	dim.name = "Dim"
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center)
	var panel := PanelContainer.new()
	center.add_child(panel)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(200, 0)
	panel.add_child(box)
	var heading := Label.new()
	heading.name = "Heading"
	heading.text = tr("UI_USE_ON")
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(heading)
	var state := RpgUtil.state()
	if state != null:
		for actor_id in state.party_ids():
			var member_stats := state.stats_of(actor_id)
			var b := Button.new()
			b.name = "Member_%s" % actor_id
			b.text = "%s  %s %d/%d" % [state.actor_name(actor_id), tr("UI_HP"), member_stats.hp, RpgUtil.max_hp(member_stats)]
			b.alignment = HORIZONTAL_ALIGNMENT_LEFT
			b.pressed.connect(_choose.bind(actor_id))
			box.add_child(b)
			_buttons.append(b)
	var back := Button.new()
	back.name = "Back"
	back.text = tr("UI_BACK")
	back.pressed.connect(close)
	box.add_child(back)
	var ring: Array = _buttons.duplicate()
	ring.append(back)
	RpgMenuUtil.wire_vertical(ring)
	var start: Button = _buttons[0] if not _buttons.is_empty() else back
	start.grab_focus.call_deferred()

func _choose(actor_id: StringName) -> void:
	chosen.emit(actor_id)
	close()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	closed.emit()
	queue_free()
