class_name RpgHudBasic
extends CanvasLayer
## Minimal HUD: the gold counter. Visible only while a map is active.

func _ready() -> void:
	layer = 20
	var bus := RpgUtil.events()
	if bus != null:
		bus.gold_changed.connect(_on_gold)
		bus.map_entered.connect(_on_map)
	var router := RpgUtil.router()
	if router != null:
		router.map_changed.connect(_on_map_changed)
	_refresh()

func _on_gold(_total: int) -> void:
	_refresh()

func _on_map(_id: StringName) -> void:
	_refresh()

func _on_map_changed(_id: StringName) -> void:
	_refresh()

func _refresh() -> void:
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	var label := get_node_or_null("%Gold") as Label
	if label != null and state != null:
		label.text = "%s: %d" % [tr("UI_GOLD"), int(state.gold)]
	visible = router != null and router.get("current_map") != null
