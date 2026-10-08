class_name RpgStatusMenu
extends Control
## Player stats as labels.

func _ready() -> void:
	var back := get_node("%Back") as Button
	back.pressed.connect(close)
	back.focus_neighbor_top = back.get_path_to(back)
	back.focus_neighbor_bottom = back.get_path_to(back)
	var list := get_node("%Stats") as VBoxContainer
	for child in list.get_children():
		list.remove_child(child)
		child.queue_free()
	var state := RpgUtil.state()
	if state != null:
		var s: RpgStats = state.player_stats
		var rows := [
			["UI_LEVEL", str(s.level)],
			["UI_HP", "%d / %d" % [s.hp, s.max_hp]],
			["UI_XP", "%d / %d" % [s.experience, s.xp_to_next()]],
			["UI_ATTACK", str(s.attack)],
			["UI_DEFENSE", str(s.defense)],
			["UI_SPEED", str(s.speed)],
			["UI_MAGIC", str(s.magic)],
			["UI_RESISTANCE", str(s.resistance)],
			["UI_GOLD", str(state.gold)],
		]
		for row: Array in rows:
			var label := Label.new()
			var row_key: String = row[0]
			label.text = "%s: %s" % [tr(row_key), row[1]]
			list.add_child(label)
	back.grab_focus.call_deferred()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	queue_free()
