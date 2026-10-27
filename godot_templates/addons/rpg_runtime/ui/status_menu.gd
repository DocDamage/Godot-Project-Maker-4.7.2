class_name RpgStatusMenu
extends Control
## Stats as labels (with the equipment applied) and the equipment slots of one party member:
## pressing a slot opens the equip picker. With more than one member a first button, or left /
## right, pages through them.

var _slot_buttons: Array[Button] = []
var _members: Array[StringName] = []
var _index := 0  # the member on show
var _picker_open := false
var _pager: Button = null

## The member on show.
func shown_actor() -> StringName:
	return _members[_index] if _index < _members.size() else &""

## Shows the next member (previous for -1), wrapping around.
func page(step: int) -> void:
	if _members.size() < 2:
		return
	_index = (_index + step + _members.size()) % _members.size()
	_build(&"member")

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
	_pager = null
	var state := RpgUtil.state()
	if state != null:
		_members = state.party_ids()
		_index = clampi(_index, 0, _members.size() - 1)
		var id := shown_actor()
		var s: RpgStats = state.stats_of(id)
		if _members.size() > 1:
			_pager = Button.new()
			_pager.name = "Member"
			_pager.text = "< %s (%d/%d) >" % [state.actor_name(id), _index + 1, _members.size()]
			_pager.pressed.connect(page.bind(1))
			list.add_child(_pager)
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
		if RpgUtil.max_mp(s) > 0:
			rows.insert(2, ["UI_MP", "%d / %d" % [s.mp, RpgUtil.max_mp(s)]])
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
			var wear := state.wear_of(id, slot)
			if wear[1] > 0:  # a piece that wears (1.5.0)
				b.text += "  " + tr("UI_WEAR") % [wear[0], wear[1]]
			b.alignment = HORIZONTAL_ALIGNMENT_LEFT
			b.pressed.connect(_open_picker.bind(slot))
			list.add_child(b)
			_slot_buttons.append(b)
		for worn_set in state.worn_sets(id):  # the sets worn (1.5.0)
			var item_set := state.item_set_of(StringName(str(worn_set["set_id"])))
			var set_label := Label.new()
			set_label.name = "Set_%s" % worn_set["set_id"]
			set_label.text = tr("UI_SET_BONUS") % [tr(item_set.title) if item_set != null and item_set.title != "" else str(worn_set["set_id"]), RpgUtil.to_int(worn_set["worn"])]
			list.add_child(set_label)
	var ring: Array = _slot_buttons.duplicate()
	if _pager != null:
		ring.push_front(_pager)
	ring.append(back)
	RpgMenuUtil.wire_vertical(ring)
	var start: Button = back
	if focus_slot == &"member" and _pager != null:
		start = _pager
	for b in _slot_buttons:
		if b.name == "Slot_%s" % focus_slot:
			start = b
	start.grab_focus.call_deferred()

func _open_picker(slot: StringName) -> void:
	var state := RpgUtil.state()
	if state == null:
		return
	var picker := RpgEquipPicker.new()
	picker.actor_id = shown_actor()
	picker.slot = slot
	_picker_open = true
	add_child(picker)
	picker.closed.connect(_on_picker_closed.bind(slot), CONNECT_ONE_SHOT)

func _on_picker_closed(_changed: bool, slot: StringName) -> void:
	_picker_open = false
	_build.call_deferred(slot)

## Left / right page through the members (the first button does the same for the mouse).
func _input(event: InputEvent) -> void:
	if _picker_open or _members.size() < 2:
		return
	var step := 0
	if _pressed(event, "move_left") or _pressed(event, "ui_left"):
		step = -1
	elif _pressed(event, "move_right") or _pressed(event, "ui_right"):
		step = 1
	if step != 0:
		get_viewport().set_input_as_handled()
		page(step)

static func _pressed(event: InputEvent, action: String) -> bool:
	return InputMap.has_action(action) and event.is_action_pressed(action)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	queue_free()
