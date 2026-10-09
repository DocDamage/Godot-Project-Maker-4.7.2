class_name RpgArpgHud
extends CanvasLayer
## The action-RPG HUD (layer 20): HP bar and text, the party members' HP bars under it, a thin XP
## bar, the level, the gold counter and the quick-item slot. It is refreshed by Events (never polled every frame) and shown only while
## a map is active. The `quick_item` input uses the quick item.

func _ready() -> void:
	layer = 20
	var bus := RpgUtil.events()
	if bus != null:
		for signal_name: StringName in [&"player_damaged", &"player_healed", &"gold_changed", &"experience_gained",
				&"level_up", &"equipment_changed", &"item_added", &"item_removed", &"map_entered", &"game_loaded", &"party_changed"]:
			if bus.has_signal(signal_name):
				bus.connect(signal_name, _on_event)
	var router := RpgUtil.router()
	if router != null:
		router.map_changed.connect(_on_event)
		var mode: RpgCombatMode = router.combat
		if mode != null and mode.has_signal("quick_item_changed"):
			mode.connect("quick_item_changed", _on_event)
		if mode != null and mode.has_signal("party_health_changed"):
			mode.connect("party_health_changed", _on_event)
	refresh()

## Every signal has a different argument list; the HUD re-reads the state anyway.
func _on_event(_a: Variant = null, _b: Variant = null) -> void:
	refresh()

func _mode() -> Node:
	var router := RpgUtil.router()
	var mode: RpgCombatMode = router.combat if router != null else null
	return mode if mode != null and mode.has_method("quick_item") else null

func refresh() -> void:
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	visible = router != null and router.get("current_map") != null
	if state == null:
		return
	var stats: RpgStats = state.player_stats
	var max_hp := RpgUtil.max_hp(stats)
	var hp_bar := get_node_or_null("%HpBar") as ProgressBar
	if hp_bar != null:
		hp_bar.max_value = maxf(1.0, max_hp)
		hp_bar.value = stats.hp
	var hp_text := get_node_or_null("%HpText") as Label
	if hp_text != null:
		hp_text.text = "%d/%d" % [stats.hp, max_hp]
	var xp_bar := get_node_or_null("%XpBar") as ProgressBar
	if xp_bar != null:
		xp_bar.max_value = maxf(1.0, stats.xp_to_next())
		xp_bar.value = stats.experience
	var level := get_node_or_null("%Level") as Label
	if level != null:
		level.text = "%s %d" % [tr("UI_LEVEL"), stats.level]
	var gold := get_node_or_null("%Gold") as Label
	if gold != null:
		gold.text = "%s: %d" % [tr("UI_GOLD"), RpgUtil.to_int(state.gold)]
	_refresh_party(state, hp_bar)
	_refresh_quick_item(state)

## The members' bars: a "Party" column under the player's HP row, one "Member_<id>" bar each (made
## here, as a smaller copy of the HP bar, so a HUD scene from 1.0 shows them too).
func _refresh_party(state: RpgGameState, hp_bar: ProgressBar) -> void:
	if hp_bar == null or hp_bar.get_parent() == null or hp_bar.get_parent().get_parent() == null:
		return
	var column := hp_bar.get_parent().get_parent()
	var box := column.get_node_or_null("Party") as VBoxContainer
	if box == null:
		box = VBoxContainer.new()
		box.name = "Party"
		box.mouse_filter = Control.MOUSE_FILTER_IGNORE
		box.add_theme_constant_override("separation", 1)
		column.add_child(box)
		column.move_child(box, hp_bar.get_parent().get_index() + 1)
	var wanted: Array[String] = []
	for member in state.party:
		wanted.append("Member_%s" % member["actor_id"])
	for child in box.get_children():
		if not wanted.has(String(child.name)):
			box.remove_child(child)
			child.queue_free()
	box.visible = not wanted.is_empty()
	for i in state.party.size():
		var member_stats: RpgStats = state.party[i]["stats"]
		var bar := box.get_node_or_null(wanted[i]) as ProgressBar
		if bar == null:
			bar = hp_bar.duplicate() as ProgressBar
			bar.name = wanted[i]
			bar.unique_name_in_owner = false
			bar.custom_minimum_size = Vector2(hp_bar.custom_minimum_size.x * 0.75, maxf(3.0, hp_bar.custom_minimum_size.y * 0.6))
			bar.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
			var member_id: StringName = state.party[i]["actor_id"]
			bar.tooltip_text = state.actor_name(member_id)
			box.add_child(bar)
		box.move_child(bar, i)
		bar.max_value = maxf(1.0, RpgUtil.max_hp(member_stats))
		bar.value = member_stats.hp

func _refresh_quick_item(state: RpgGameState) -> void:
	var icon := get_node_or_null("%QuickIcon") as TextureRect
	var qty := get_node_or_null("%QuickQty") as Label
	var mode := _mode()
	var id: StringName = mode.call("quick_item") if mode != null else &""
	var def: RpgItemDefinition = state.items.get(id) if id != &"" else null
	if icon != null:
		icon.texture = def.icon if def != null else null
	if qty != null:
		qty.text = "x%d" % state.inventory.count(id) if id != &"" else "-"

func _unhandled_input(event: InputEvent) -> void:
	if not visible or not InputMap.has_action("quick_item") or not event.is_action_pressed("quick_item"):
		return
	var router := RpgUtil.router()
	var player := get_tree().get_first_node_in_group("player")
	if router == null or router.is_busy() or player == null or not RpgUtil.to_bool(player.get("input_enabled")):
		return
	var mode := _mode()
	if mode != null:
		mode.call("use_quick_item")
		get_viewport().set_input_as_handled()
