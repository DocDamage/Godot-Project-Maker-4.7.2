extends RefCounted
## Builds one TileSet resource per TileSetDef in the catalog.

const RECIPE_VERSION := 2

const Paths := preload("../lib/paths.gd")
const Geometry := preload("../lib/geometry.gd")

func outputs(ctx) -> PackedStringArray:
	var out := PackedStringArray()
	for def in ctx.catalog.tileset_defs():
		out.append(Paths.TILESETS_DIR + "%s.tres" % def["name"])
	return out

func input_hash(ctx) -> String:
	var parts: Array = []
	for def in ctx.catalog.tileset_defs():
		var sources: Array = []
		for s in def.get("sources", []):
			var asset: Dictionary = ctx.catalog.asset(s["asset"])
			var eff: Dictionary = ctx.catalog.effective(asset)
			sources.append({
				"asset": s["asset"],
				"sha256": asset.get("sha256", ""),
				"grid": eff.get("grid"),
				"collision": eff.get("collision"),
				"tile_overrides": eff.get("tile_overrides"),
				"tileset": eff.get("tileset"),
				"role": eff.get("role"),
			})
		var objects: Array = []
		if def.get("patterns_from_objects", true):
			objects = ctx.catalog.objects()
		parts.append({"def": def, "sources": sources, "objects": objects})
	return ctx.stable_hash({"v": RECIPE_VERSION, "tilesets": parts})

func build(ctx) -> Array:
	var issues: Array = []
	for def in ctx.catalog.tileset_defs():
		_build_tileset(ctx, def, issues)
	return issues

func _build_tileset(ctx, def: Dictionary, issues: Array) -> void:
	var out_path: String = Paths.TILESETS_DIR + "%s.tres" % def["name"]
	if def.get("sources", []).is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": def["name"]}, out_path))
		return
	var ts: TileSet = null
	if FileAccess.file_exists(out_path):
		# Merge path (completed in T5.04): reuse the existing resource.
		ts = ResourceLoader.load(out_path, "TileSet", ResourceLoader.CACHE_MODE_IGNORE) as TileSet
	if ts == null:
		ts = TileSet.new()
	var cell: Vector2i = ctx.vec2i(def["tile_size"])
	ts.tile_size = cell

	var physics: Array = def.get("physics_layers", [])
	while ts.get_physics_layers_count() < physics.size():
		ts.add_physics_layer()
	for i in physics.size():
		ts.set_physics_layer_collision_layer(i, int(physics[i]["layer_bits"]))
		ts.set_physics_layer_collision_mask(i, int(physics[i]["mask_bits"]))

	var custom_types := {"string": TYPE_STRING, "float": TYPE_FLOAT, "int": TYPE_INT, "bool": TYPE_BOOL}
	for layer in def.get("custom_data", []):
		var idx := ts.get_custom_data_layer_by_name(layer["name"])
		if idx == -1:
			ts.add_custom_data_layer()
			idx = ts.get_custom_data_layers_count() - 1
			ts.set_custom_data_layer_name(idx, layer["name"])
		ts.set_custom_data_layer_type(idx, custom_types.get(layer.get("type", "string"), TYPE_STRING))

	var sources: Array = def["sources"].duplicate()
	sources.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a["source_id"]) < int(b["source_id"]))
	for s in sources:
		_build_source(ctx, ts, s, cell, issues)
	if def.get("patterns_from_objects", true):
		_build_patterns(ctx, ts, sources)

	DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
	var err := ResourceSaver.save(ts, out_path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": out_path, "err": err}, out_path))

func _build_source(ctx, ts: TileSet, s: Dictionary, cell: Vector2i, issues: Array) -> void:
	var asset: Dictionary = ctx.catalog.asset(s["asset"])
	if asset.is_empty():
		issues.append(ctx.make_issue("CAT-004", {"asset": s["asset"], "file": "(catalog)"}))
		return
	var eff: Dictionary = ctx.catalog.effective(asset)
	var tex_path: String = "res://" + str(asset["path"])
	var tex := load(tex_path) as Texture2D
	if tex == null:
		issues.append(ctx.make_issue("VAL-002", {"file": tex_path}, tex_path))
		return
	var source_id := int(s["source_id"])
	var src: TileSetAtlasSource
	if ts.has_source(source_id):
		src = ts.get_source(source_id) as TileSetAtlasSource
	else:
		src = TileSetAtlasSource.new()
		ts.add_source(src, source_id)  # always pass the explicit id
	var grid: Dictionary = eff.get("grid", {})
	var atlas_cell: Vector2i = ctx.vec2i(grid.get("cell", [cell.x, cell.y]))
	var margin: Vector2i = ctx.vec2i(grid.get("margin", [0, 0]))
	var sep: Vector2i = ctx.vec2i(grid.get("separation", [0, 0]))
	src.texture = tex
	src.texture_region_size = atlas_cell
	src.margins = margin
	src.separation = sep

	var tex_size := tex.get_size()
	var cols := int(floor((tex_size.x - 2.0 * margin.x + sep.x) / (atlas_cell.x + sep.x)))
	var rows := int(floor((tex_size.y - 2.0 * margin.y + sep.y) / (atlas_cell.y + sep.y)))

	var img: Image = tex.get_image()
	if img == null or img.is_empty():
		img = Image.load_from_file(ProjectSettings.globalize_path(tex_path))
	if img == null or img.is_empty():
		issues.append(ctx.make_issue("ASSET-002", {"file": tex_path}, tex_path))
		return
	if img.is_compressed():
		img.decompress()

	var overrides: Dictionary = eff.get("tile_overrides", {})
	# A WALL sheet blocks movement unless the catalog says otherwise.
	var sheet_collision: Dictionary = eff.get("collision", {"profile": "FULL" if eff.get("role", "") == "WALL" else "NONE"})
	for cy in rows:
		for cx in cols:
			var key := "%d,%d" % [cx, cy]
			var ov: Dictionary = overrides.get(key, {})
			if ov.get("skip", false):
				continue
			var rect := Rect2i(
				margin.x + cx * (atlas_cell.x + sep.x), margin.y + cy * (atlas_cell.y + sep.y),
				atlas_cell.x, atlas_cell.y)
			var cell_img := img.get_region(rect)
			if cell_img.is_invisible():
				continue
			var coords := Vector2i(cx, cy)
			if not src.has_tile(coords):
				src.create_tile(coords)
			_configure_tile(src.get_tile_data(coords, 0), asset, ov.get("collision", sheet_collision), atlas_cell, cell_img)

func _configure_tile(td: TileData, asset: Dictionary, collision: Dictionary, atlas_cell: Vector2i, cell_img: Image) -> void:
	while td.get_collision_polygons_count(0) > 0:
		td.remove_collision_polygon(0, 0)
	var profile: String = collision.get("profile", "NONE")
	if profile == "ALPHA_POLYGON":
		var bm := BitMap.new()
		bm.create_from_image_alpha(cell_img, 0.5)
		for poly in bm.opaque_to_polygons(Rect2i(0, 0, atlas_cell.x, atlas_cell.y), 1.0):
			td.add_collision_polygon(0)
			td.set_collision_polygon_points(0, td.get_collision_polygons_count(0) - 1, Geometry.to_tile_space(poly, atlas_cell))
	elif profile != "NONE":
		var pts := Geometry.profile_polygon(profile, atlas_cell, collision.get("polygon", []))
		if pts.size() >= 3:
			td.add_collision_polygon(0)
			td.set_collision_polygon_points(0, 0, Geometry.to_tile_space(pts, atlas_cell))
	td.set_custom_data("asset_id", asset["id"])

## TileMapPatterns from sheet objects (T4.06): one pattern per object, in object id order. Every
## existing pattern is removed first, so a rebuild never duplicates them.
func _build_patterns(ctx, ts: TileSet, sources: Array) -> void:
	while ts.get_patterns_count() > 0:
		ts.remove_pattern(0)
	var source_of := {}
	for s in sources:
		source_of[s["asset"]] = int(s["source_id"])
	for o in ctx.catalog.objects():
		if o.get("status", "") == "UNUSED" or o.get("role", "NONE") == "NONE" or not source_of.has(o["sheet"]):
			continue
		var source_id: int = source_of[o["sheet"]]
		var src := ts.get_source(source_id) as TileSetAtlasSource
		if src == null:
			continue
		var grid: Dictionary = ctx.catalog.effective(ctx.catalog.asset(o["sheet"])).get("grid", {})
		var atlas_cell: Vector2i = ctx.vec2i(grid.get("cell", [16, 16]))
		var margin: Vector2i = ctx.vec2i(grid.get("margin", [0, 0]))
		var sep: Vector2i = ctx.vec2i(grid.get("separation", [0, 0]))
		var step := atlas_cell + sep
		var region: Array = o["region"]
		var first := Vector2i((int(region[0]) - margin.x) / step.x, (int(region[1]) - margin.y) / step.y)
		var last := Vector2i((int(region[0]) + int(region[2]) - 1 - margin.x) / step.x, (int(region[1]) + int(region[3]) - 1 - margin.y) / step.y)
		var pattern := TileMapPattern.new()
		for cy in range(first.y, last.y + 1):
			for cx in range(first.x, last.x + 1):
				var coords := Vector2i(cx, cy)
				if src.has_tile(coords):
					pattern.set_cell(coords - first, source_id, coords, 0)
		if not pattern.is_empty():
			ts.add_pattern(pattern)
