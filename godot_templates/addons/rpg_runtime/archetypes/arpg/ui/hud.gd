class_name RpgArpgHud
extends CanvasLayer
## The action-RPG HUD (layer 20): HP bar and text, a thin XP bar, the level, the gold counter and
## the quick-item slot. It is refreshed by Events (never polled every frame) and shown only while
## a map is active. The `quick_item` input uses the quick item.

func _ready() -> void:
	layer = 20
	var bus := RpgUtil.events()
	if bus != null:
		for signal_name in [&"player_damaged", &"player_healed", &"gold_changed", &"experience_gained",
				&"level_up", &"item_added", &"item_removed", &"map_entered", &"game_loaded"]:
			if bus.has_signal(signal_name):
				bus.connect(signal_name, _on_event)
	var router := RpgUtil.router()
	if router != null:
		router.map_changed.connect(_on_event)
		var mode: Variant = router.get("combat")
		if mode != null and mode.has_signal("quick_item_changed"):
			mode.connect("quick_item_changed", _on_event)
	refresh()

## Every signal has a different argument list; the HUD re-reads the state anyway.
func _on_event(_a: Variant = null, _b: Variant = null) -> void:
	refresh()

func _mode() -> Node:
	var router := RpgUtil.router()
	var mode: Variant = router.get("combat") if router != null else null
	return mode as Node if mode != null and mode.has_method("quick_item") else null

func refresh() -> void:
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	visible = router != null and router.get("current_map") != null
	if state == null:
		return
	var stats: RpgStats = state.player_stats
	var hp_bar := get_node_or_null("%HpBar") as ProgressBar
	if hp_bar != null:
		hp_bar.max_value = maxf(1.0, stats.max_hp)
		hp_bar.value = stats.hp
	var hp_text := get_node_or_null("%HpText") as Label
	if hp_text != null:
		hp_text.text = "%d/%d" % [stats.hp, stats.max_hp]
	var xp_bar := get_node_or_null("%XpBar") as ProgressBar
	if xp_bar != null:
		xp_bar.max_value = maxf(1.0, stats.xp_to_next())
		xp_bar.value = stats.experience
	var level := get_node_or_null("%Level") as Label
	if level != null:
		level.text = "%s %d" % [tr("UI_LEVEL"), stats.level]
	var gold := get_node_or_null("%Gold") as Label
	if gold != null:
		gold.text = "%s: %d" % [tr("UI_GOLD"), int(state.gold)]
	_refresh_quick_item(state)

func _refresh_quick_item(state: Node) -> void:
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
	if router == null or router.is_busy() or player == null or not bool(player.get("input_enabled")):
		return
	var mode := _mode()
	if mode != null:
		mode.call("use_quick_item")
		get_viewport().set_input_as_handled()
