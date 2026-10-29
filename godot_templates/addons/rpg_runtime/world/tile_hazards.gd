class_name RpgTileHazards
extends RefCounted
## One timer per player, carried across tile boundaries to prevent overlapping or alternating
## hazards from stacking hits. Settings live on the actual tile, including packed iso tiles.
var remaining := 0.0
var _map: Node = null
var _layers: Array[TileMapLayer] = []

static func at(layers: Array[TileMapLayer], points: Array[Vector2], default_cooldown: float = 1.0) -> Dictionary:
	var found := {}
	for layer in layers:
		if not is_instance_valid(layer) or not layer.enabled or layer.tile_set == null:
			continue
		var ts := layer.tile_set
		if ts.get_custom_data_layer_by_name("hazard") < 0:
			continue
		for point in points:
			var local := layer.to_local(point) if layer.is_inside_tree() else point - layer.position
			var td := layer.get_cell_tile_data(layer.local_to_map(local))
			if td == null or not RpgUtil.to_bool(td.get_custom_data("hazard")):
				continue
			var damage := 1
			var cooldown := default_cooldown
			if ts.get_custom_data_layer_by_name("hazard_damage") >= 0:
				damage = maxi(1, RpgUtil.to_int(td.get_custom_data("hazard_damage")))
			if ts.get_custom_data_layer_by_name("hazard_cooldown") >= 0:
				var value := RpgUtil.to_float(td.get_custom_data("hazard_cooldown"), 1.0)
				cooldown = maxf(0.05, value) if value > 0.0 else default_cooldown
			if damage > RpgUtil.to_int(found.get("damage", 0)):
				found = {"damage": damage, "cooldown": cooldown}
	return found

func tick(delta: float) -> void:
	remaining = maxf(0.0, remaining - delta)

func consume(spec: Dictionary) -> bool:
	if spec.is_empty() or remaining > 0.0:
		return false
	remaining = RpgUtil.to_float(spec["cooldown"], 1.0)
	return true

func on_map(map: Node, point: Vector2) -> Dictionary:
	if map != _map:
		_map = map
		_layers.clear()
		if map != null:
			for node in map.find_children("*", "TileMapLayer", true, false):
				_layers.append(node as TileMapLayer)
	var points: Array[Vector2] = [point]
	return at(_layers, points)
