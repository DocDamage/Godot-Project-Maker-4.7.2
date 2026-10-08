class_name RpgStatusMenu
extends Control
## Player stats as labels (with the equipment applied) and the equipment slots: pressing a slot opens
## the equip picker.

var _slot_buttons: Array[Button] = []

func _ready() -> void:
	var back := get_node("%Back") as Button
	back.pressed.connect(close)
	_build()

## (Re)builds the stat labels and the slot buttons; called again after the equipment changed.
func _build(focus_slot: StringName = &"") -> void:
	var back := get_node("%Back") as Button
	var list := get_node("%Stats") as VBoxContainer
	for child in list.get_children():
		list.remove_child(child)
		child.queue_free()
	_slot_buttons.clear()
	var state := RpgUtil.state()
	if state != null:
		var s: RpgStats = state.player_stats
		var id: StringName = state.player_actor_id
		var rows := [
			["UI_LEVEL", str(s.level)],
			["UI_HP", "%d / %d" % [s.hp, RpgUtil.max_hp(s)]],
			["UI_XP", "%d / %d" % [s.experience, s.xp_to_next()]],
			["UI_ATTACK", str(roundi(state.stat_of(id, &"attack")))],
			["UI_DEFENSE", str(roundi(state.stat_of(id, &"defense")))],
			["UI_SPEED", str(roundi(state.stat_of(id, &"speed")))],
			["UI_MAGIC", str(roundi(state.stat_of(id, &"magic")))],
			["UI_RESISTANCE", str(roundi(state.stat_of(id, &"resistance")))],
			["UI_GOLD", str(state.gold)],
		]
		for row: Array in rows:
			var label := Label.new()
			var row_key: String = row[0]
			label.text = "%s: %s" % [tr(row_key), row[1]]
			list.add_child(label)
		var heading := Label.new()
		heading.name = "EquipmentHeading"
		heading.text = tr("UI_EQUIPMENT")
		list.add_child(heading)
		for slot in RpgGameState.EQUIP_SLOTS:
			var worn := state.equipped_in(id, slot)
			var def: RpgItemDefinition = state.items.get(worn)
			var b := Button.new()
			b.name = "Slot_%s" % slot
			b.text = "%s: %s" % [tr(RpgEquipPicker.slot_key(slot)), tr(def.display_name) if def != null else tr("UI_EMPTY")]
			b.alignment = HORIZONTAL_ALIGNMENT_LEFT
			b.pressed.connect(_open_picker.bind(slot))
			list.add_child(b)
			_slot_buttons.append(b)
	var ring: Array = _slot_buttons.duplicate()
	ring.append(back)
	RpgMenuUtil.wire_vertical(ring)
	var start: Button = back
	for b in _slot_buttons:
		if b.name == "Slot_%s" % focus_slot:
			start = b
	start.grab_focus.call_deferred()

func _open_picker(slot: StringName) -> void:
	var state := RpgUtil.state()
	if state == null:
		return
	var picker := RpgEquipPicker.new()
	picker.actor_id = state.player_actor_id
	picker.slot = slot
	add_child(picker)
	picker.closed.connect(_on_picker_closed.bind(slot), CONNECT_ONE_SHOT)

func _on_picker_closed(_changed: bool, slot: StringName) -> void:
	_build.call_deferred(slot)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	queue_free()
