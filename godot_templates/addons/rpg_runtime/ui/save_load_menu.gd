class_name RpgSaveLoadMenu
extends Control
## Three slot buttons showing their headers. `mode` is "save" or "load" (set before it enters the tree).

@export var mode: String = "save"
## Answers "overwrite slot N?" without a dialog (tests and the smoke run set it): a Callable
## taking the slot and returning a bool. Empty: the player is asked.
var confirm_overwrite: Callable = Callable()

func _slots() -> Array[int]:
	var out: Array[int] = []
	for slot in range(RpgSaveManager.AUTOSAVE_SLOT, RpgSaveManager.SLOTS + 1):
		out.append(slot)
	return out

func _ready() -> void:
	(get_node("%Heading") as Label).text = tr("UI_LOAD" if mode == "load" else "UI_SAVE")
	(get_node("%Back") as Button).pressed.connect(close)
	for slot: int in _slots():  # slot 0 is the autosave, listed first and load-only
		(get_node("%%Slot%d" % slot) as Button).pressed.connect(_on_slot.bind(slot))
	_refresh()
	_focus_first.call_deferred()

func _slot_text(slot: int) -> String:
	var save := RpgUtil.save_manager()
	var h: Dictionary = save.header(slot) if save != null else {}
	var label := tr("UI_AUTOSAVE") if slot == 0 else "%s %d" % [tr("UI_SLOT"), slot]
	return slot_text(label, h, RpgUtil.to_int(Time.get_time_zone_from_system().get("bias", 0)))

## "Slot 2 — Village · Lv 3 · 1:12 played · 12 Oct 14:05": the map's name, the level, the playtime
## and the local time of saving (`bias_minutes` is the offset from UTC). A save made before the
## time was kept shows no date.
static func slot_text(label: String, h: Dictionary, bias_minutes: int) -> String:
	if h.is_empty():
		return "%s — %s" % [label, TranslationServer.translate(&"UI_EMPTY")]
	var parts: Array[String] = [_map_label(h)]
	parts.append("%s %d" % [TranslationServer.translate(&"UI_LV"), RpgUtil.to_int(h.get("level", 1))])
	var minutes := int(RpgUtil.to_float(h.get("playtime_s", 0.0)) / 60.0)
	parts.append("%d:%02d %s" % [int(minutes / 60.0), minutes % 60, TranslationServer.translate(&"UI_PLAYED")])
	var stamp := _local_stamp(RpgUtil.to_int(h.get("saved_unix", 0)), bias_minutes)
	if stamp != "":
		parts.append(stamp)
	return "%s — %s" % [label, " · ".join(parts)]

static func _map_label(h: Dictionary) -> String:
	var key := str(h.get("map_name", ""))
	if key != "":
		var shown := str(TranslationServer.translate(StringName(key)))
		if shown != key:
			return shown
	var id := str(h.get("map", ""))
	return id.replace("_", " ").capitalize() if id != "" else "?"

static func _local_stamp(unix: int, bias_minutes: int) -> String:
	if unix <= 0:
		return ""
	var d := Time.get_datetime_dict_from_unix_time(unix + bias_minutes * 60)
	var month := str(TranslationServer.translate(StringName("UI_MONTH_%d" % RpgUtil.to_int(d["month"]))))
	return "%d %s %02d:%02d" % [RpgUtil.to_int(d["day"]), month, RpgUtil.to_int(d["hour"]), RpgUtil.to_int(d["minute"])]

## The picture kept beside a slot, or null.
func _thumbnail(slot: int) -> Texture2D:
	var save := RpgUtil.save_manager()
	if save == null or not FileAccess.file_exists(save.thumbnail_path(slot)):
		return null
	var image := Image.load_from_file(save.thumbnail_path(slot))
	return ImageTexture.create_from_image(image) if image != null else null

func _refresh() -> void:
	var save := RpgUtil.save_manager()
	var buttons: Array = []
	for slot: int in _slots():
		var b := get_node("%%Slot%d" % slot) as Button
		b.text = _slot_text(slot)
		b.icon = _thumbnail(slot)
		b.expand_icon = false
		b.icon_alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.add_theme_constant_override("icon_max_width", 96)
		b.disabled = mode == "load" and (save == null or not save.has_save(slot))
		if slot == 0:
			# The autosave can be loaded, never chosen as the place to save to.
			b.visible = mode == "load" and save != null and save.has_save(0)
			b.disabled = false
			if not b.visible:
				continue
		buttons.append(b)
	buttons.append(get_node("%Back"))
	var live := buttons.filter(func(c: Button) -> bool: return not c.disabled)
	RpgMenuUtil.wire_vertical(live)

func _focus_first() -> void:
	for slot: int in _slots():
		var b := get_node("%%Slot%d" % slot) as Button
		if b.visible and not b.disabled:
			b.grab_focus()
			return
	(get_node("%Back") as Button).grab_focus()

func _on_slot(slot: int) -> void:
	var save := RpgUtil.save_manager()
	if save == null:
		return
	if mode == "save":
		if slot == 0:
			return  # the autosave is never a place to save to
		if save.has_save(slot) and not await _ask_overwrite(slot):
			return
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

## True when the player agrees to replace the save in a used slot. The dialog's focus starts on
## "No", so a stray press of Confirm never destroys a save.
func _ask_overwrite(slot: int) -> bool:
	if confirm_overwrite.is_valid():
		return RpgUtil.to_bool(confirm_overwrite.call(slot))
	var dialog := ConfirmationDialog.new()
	dialog.dialog_text = tr("UI_OVERWRITE_SAVE")
	dialog.ok_button_text = tr("UI_YES")
	dialog.cancel_button_text = tr("UI_NO")
	dialog.process_mode = Node.PROCESS_MODE_ALWAYS
	var answer: Array[bool] = []
	dialog.confirmed.connect(func() -> void: answer.append(true))
	dialog.canceled.connect(func() -> void: answer.append(false))
	add_child(dialog)
	dialog.popup_centered()
	dialog.get_cancel_button().grab_focus()
	while answer.is_empty() and is_inside_tree():
		await get_tree().process_frame
	dialog.queue_free()
	return not answer.is_empty() and answer[0]


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
