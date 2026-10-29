extends RefCounted
## Explicit per-tile settings. Isometric pictures use their local key "0,0" before packing.
const JsonUtil := preload("json_util.gd")
const LAYERS := {"hazard": TYPE_BOOL, "hazard_damage": TYPE_INT, "hazard_cooldown": TYPE_FLOAT}

static func configure(ts: TileSet, td: TileData, override: Dictionary, side_view: bool = false) -> void:
	var custom := JsonUtil.to_dict(override.get("custom", {}))
	if not custom.has("hazard"):
		if not side_view and ts.get_custom_data_layer_by_name("hazard") >= 0:
			td.set_custom_data("hazard", false)
		for pair: Array in [["hazard_damage", 0], ["hazard_cooldown", 0.0]]:
			var key := JsonUtil.to_str(pair[0])
			if ts.get_custom_data_layer_by_name(key) >= 0:
				td.set_custom_data(key, pair[1])
		return
	for key: String in LAYERS:
		if ts.get_custom_data_layer_by_name(key) < 0:
			ts.add_custom_data_layer()
			var index := ts.get_custom_data_layers_count() - 1
			ts.set_custom_data_layer_name(index, key)
			var type: Variant.Type = LAYERS[key]
			ts.set_custom_data_layer_type(index, type)
	td.set_custom_data("hazard", JsonUtil.to_bool(custom["hazard"]))
	td.set_custom_data("hazard_damage", maxi(1, JsonUtil.to_int(custom.get("hazard_damage", 1))))
	td.set_custom_data("hazard_cooldown", maxf(0.05, JsonUtil.to_float(custom.get("hazard_cooldown", 1.0))))
