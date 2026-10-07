class_name RpgSaveLoadMenu
extends Control
## Three slot buttons showing their headers. `mode` is "save" or "load" (set before it enters the tree).

@export var mode: String = "save"

func _ready() -> void:
	(get_node("%Heading") as Label).text = tr("UI_LOAD" if mode == "load" else "UI_SAVE")
	(get_node("%Back") as Button).pressed.connect(close)
	for slot in range(1, 4):
		(get_node("%%Slot%d" % slot) as Button).pressed.connect(_on_slot.bind(slot))
	_refresh()
	_focus_first.call_deferred()

func _slot_text(slot: int) -> String:
	var save := RpgUtil.autoload(&"SaveManager")
	var h: Dictionary = save.header(slot) if save != null else {}
	if h.is_empty():
		return "%s %d: %s" % [tr("UI_SLOT"), slot, tr("UI_EMPTY")]
	var minutes := int(float(h.get("playtime_s", 0.0)) / 60.0)
	return "%s %d: %s  %s %d  %s %d  %dm" % [tr("UI_SLOT"), slot, str(h.get("map", "")), tr("UI_LEVEL"), int(h.get("level", 1)), tr("UI_GOLD"), int(h.get("gold", 0)), minutes]

func _refresh() -> void:
	var save := RpgUtil.autoload(&"SaveManager")
	var buttons: Array = []
	for slot in range(1, 4):
		var b := get_node("%%Slot%d" % slot) as Button
		b.text = _slot_text(slot)
		b.disabled = mode == "load" and (save == null or not save.has_save(slot))
		buttons.append(b)
	buttons.append(get_node("%Back"))
	var live := buttons.filter(func(c: Button) -> bool: return not c.disabled)
	RpgMenuUtil.wire_vertical(live)

func _focus_first() -> void:
	for slot in range(1, 4):
		var b := get_node("%%Slot%d" % slot) as Button
		if not b.disabled:
			b.grab_focus()
			return
	(get_node("%Back") as Button).grab_focus()

func _on_slot(slot: int) -> void:
	var save := RpgUtil.autoload(&"SaveManager")
	if save == null:
		return
	if mode == "save":
		if save.save(slot):
			RpgUtil.notify(tr("UI_GAME_SAVED"))
			_refresh()
		else:
			RpgUtil.notify(tr("UI_SAVE_FAILED"))
	else:
		get_tree().paused = false
		if save.load(slot):
			_close_all_menus()
		else:
			RpgUtil.notify(tr("UI_LOAD_FAILED"))

## After a successful load the whole menu stack closes.
func _close_all_menus() -> void:
	var node: Node = self
	while node.get_parent() is Control:
		node = node.get_parent()
	if node.has_method("close"):
		node.call("close")
	else:
		node.queue_free()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	queue_free()
