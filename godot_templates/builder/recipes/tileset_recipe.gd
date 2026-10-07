extends RefCounted
## Builds one TileSet resource per TileSetDef in the catalog.

const RECIPE_VERSION := 3

const Paths := preload("../lib/paths.gd")
const Geometry := preload("../lib/geometry.gd")
const JsonUtil := preload("../lib/json_util.gd")

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
	_load_apply_state()
	for def in ctx.catalog.tileset_defs():
		_build_tileset(ctx, def, issues)
	_save_apply_state(issues, ctx)
	return issues

# Collision bookkeeping (T5.04): per tile, the hash of the collision spec rpggen last applied and
# the hash of the polygons it produced. Kept in a state file, because TileData metadata is not
# known to survive a save.
const APPLY_STATE := "res://rpggen/tileset_apply_state.json"
var _apply: Dictionary = {}
var _apply_dirty := false

func _load_apply_state() -> void:
	_apply = {}
	if FileAccess.file_exists(APPLY_STATE):
		var data: Variant = JsonUtil.read(APPLY_STATE)
		if data is Dictionary and data.get("tiles") is Dictionary:
			_apply = data["tiles"]

func _save_apply_state(issues: Array, ctx) -> void:
	if not _apply_dirty:
		return
	var err := JsonUtil.write(APPLY_STATE, {"apply_state_version": 1, "tiles": _apply})
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": APPLY_STATE, "err": err}, APPLY_STATE))

func _build_tileset(ctx, def: Dictionary, issues: Array) -> void:
	var out_path: String = Paths.TILESETS_DIR + "%s.tres" % def["name"]
	if def.get("sources", []).is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": def["name"]}, out_path))
		return
	var ts: TileSet = null
	var merging := FileAccess.file_exists(out_path)
	if merging:
		# Never create a new TileSet when the file exists: painted maps reference its source ids.
		ts = ResourceLoader.load(out_path, "TileSet", ResourceLoader.CACHE_MODE_IGNORE) as TileSet
		if ts == null:
			issues.append(ctx.make_issue("BUILD-002", {"recipe": "tileset_recipe", "reason": "the existing TileSet %s could not be loaded; it was not touched" % out_path}, out_path))
			return
	else:
		ts = TileSet.new()
	var cell: Vector2i = ctx.vec2i(def["tile_size"])
	if not merging:
		ts.tile_size = cell
	elif ts.tile_size != cell:
		# The user has to resolve a tile size change; the existing size stays.
		issues.append(ctx.make_issue("TILE-004", {"asset": def["name"]}, out_path))

	# Physics and custom data layers: add the missing ones, never remove, reorder or retype.
	var physics: Array = def.get("physics_layers", [])
	while ts.get_physics_layers_count() < physics.size():
		var idx := ts.get_physics_layers_count()
		ts.add_physics_layer()
		ts.set_physics_layer_collision_layer(idx, int(physics[idx]["layer_bits"]))
		ts.set_physics_layer_collision_mask(idx, int(physics[idx]["mask_bits"]))
	var custom_types := {"string": TYPE_STRING, "float": TYPE_FLOAT, "int": TYPE_INT, "bool": TYPE_BOOL}
	for layer in def.get("custom_data", []):
		if ts.get_custom_data_layer_by_name(layer["name"]) == -1:
			ts.add_custom_data_layer()
			var idx := ts.get_custom_data_layers_count() - 1
			ts.set_custom_data_layer_name(idx, layer["name"])
			ts.set_custom_data_layer_type(idx, custom_types.get(layer.get("type", "string"), TYPE_STRING))

	var sources: Array = def["sources"].duplicate()
	sources.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a["source_id"]) < int(b["source_id"]))
	var in_def := {}
	for s in sources:
		in_def[int(s["source_id"])] = true
		_build_source(ctx, ts, def["name"], s, cell, issues)
	# Sources the TileSet has but the definition no longer lists stay (painted maps may use them).
	var retired: Array = ctx.catalog.catalog.get("id_allocations", {}).get("tilesets", {}).get(def["name"], {}).get("retired", [])
	for i in ts.get_source_count():
		var source_id := ts.get_source_id(i)
		if not in_def.has(source_id) and retired.has(source_id):
			issues.append(ctx.make_issue("REGEN-003", {"asset": "(retired source)", "source_id": source_id}, out_path))
	if def.get("patterns_from_objects", true):
		_build_patterns(ctx, ts, sources)

	DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
	var err := ResourceSaver.save(ts, out_path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": out_path, "err": err}, out_path))

func _build_source(ctx, ts: TileSet, ts_name: String, s: Dictionary, cell: Vector2i, issues: Array) -> void:
	var asset: Dictionary = ctx.catalog.asset(s["asset"])
	if asset.is_empty():
		issues.append(ctx.make_issue("CAT-004", {"asset": s["asset"], "file": "(catalog)"}))
		return
	var eff: Dictionary = ctx.catalog.effective(asset)
	var source_id := int(s["source_id"])
	var exists := ts.has_source(source_id)
	var status: String = asset.get("status", "")
	if exists and eff.get("remove_source", false) == true:
		# The user confirmed the removal in the audit (T5.04): the only place a source goes.
		ts.remove_source(source_id)
		return
	if status == "MISSING":
		if exists:
			issues.append(ctx.make_issue("REGEN-003", {"asset": s["asset"], "source_id": source_id}, "res://" + str(asset["path"])))
		return
	if exists and status == "CONFLICT":
		# A resized sheet: painted tiles could shift, so the source is left completely alone.
		issues.append(ctx.make_issue("TILE-004", {"asset": s["asset"]}, "res://" + str(asset["path"])))
		return
	var tex_path: String = "res://" + str(asset["path"])
	var tex := load(tex_path) as Texture2D
	if tex == null:
		issues.append(ctx.make_issue("VAL-002", {"file": tex_path}, tex_path))
		return
	var src: TileSetAtlasSource
	if exists:
		src = ts.get_source(source_id) as TileSetAtlasSource
	else:
		src = TileSetAtlasSource.new()
		ts.add_source(src, source_id)  # always pass the explicit id
	var grid: Dictionary = eff.get("grid", {})
	var atlas_cell: Vector2i = ctx.vec2i(grid.get("cell", [cell.x, cell.y]))
	var margin: Vector2i = ctx.vec2i(grid.get("margin", [0, 0]))
	var sep: Vector2i = ctx.vec2i(grid.get("separation", [0, 0]))
	# Only touch what changed: assigning geometry to a source can drop tiles that no longer fit.
	if src.texture == null or src.texture.resource_path != tex_path:
		src.texture = tex
	if src.texture_region_size != atlas_cell:
		src.texture_region_size = atlas_cell
	if src.margins != margin:
		src.margins = margin
	if src.separation != sep:
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
	var filled := {}
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
			filled[coords] = true
			var is_new := not src.has_tile(coords)
			if is_new:
				src.create_tile(coords)
			var tile_key := "%s/%d/%s" % [ts_name, source_id, key]
			_configure_tile(ctx, src.get_tile_data(coords, 0), asset, ov.get("collision", sheet_collision), atlas_cell, cell_img, is_new, tile_key, issues)
	# Tiles are never removed. Cells that became empty are reported (TILE-005).
	var emptied: Array = []
	for i in src.get_tiles_count():
		var coords := src.get_tile_id(i)
		if not filled.has(coords):
			emptied.append("%d,%d" % [coords.x, coords.y])
	if not emptied.is_empty():
		emptied.sort()
		var shown: String = ", ".join(emptied.slice(0, 8)) + (" ..." if emptied.size() > 8 else "")
		issues.append(ctx.make_issue("TILE-005", {"asset": s["asset"], "coords": shown}, tex_path))

## Tile-space collision polygons a collision spec produces for one cell.
func _desired_polygons(collision: Dictionary, atlas_cell: Vector2i, cell_img: Image) -> Array:
	var polys: Array = []
	var profile: String = collision.get("profile", "NONE")
	if profile == "ALPHA_POLYGON":
		var bm := BitMap.new()
		bm.create_from_image_alpha(cell_img, 0.5)
		for poly in bm.opaque_to_polygons(Rect2i(0, 0, atlas_cell.x, atlas_cell.y), 1.0):
			polys.append(Geometry.to_tile_space(poly, atlas_cell))
	elif profile != "NONE":
		var pts := Geometry.profile_polygon(profile, atlas_cell, collision.get("polygon", []))
		if pts.size() >= 3:
			polys.append(Geometry.to_tile_space(pts, atlas_cell))
	return polys

func _tile_polygons(td: TileData) -> Array:
	var polys: Array = []
	for i in td.get_collision_polygons_count(0):
		polys.append(td.get_collision_polygon_points(0, i))
	return polys

func _polys_hash(polys: Array) -> String:
	var parts: PackedStringArray = []
	for poly in polys:
		var pts: PackedStringArray = []
		for p in poly:
			pts.append("%.3f,%.3f" % [p.x, p.y])
		parts.append(";".join(pts))
	return "|".join(parts).sha256_text()

## Sets up one tile. Collision is replaced only when the catalog's collision for the tile changed
## since the last build and the polygons are still the ones rpggen applied; polygons edited in
## Godot are kept (TILE-007).
func _configure_tile(ctx, td: TileData, asset: Dictionary, collision: Dictionary, atlas_cell: Vector2i, cell_img: Image, is_new: bool, tile_key: String, issues: Array) -> void:
	var desired := _desired_polygons(collision, atlas_cell, cell_img)
	var pixels := ""
	if collision.get("profile", "NONE") == "ALPHA_POLYGON":
		pixels = cell_img.get_data().hex_encode().sha256_text()
	var spec_hash: String = ctx.stable_hash({"c": collision, "cell": [atlas_cell.x, atlas_cell.y], "px": pixels})
	var desired_hash := _polys_hash(desired)
	var current_hash := _polys_hash(_tile_polygons(td))
	var record: Dictionary = _apply.get(tile_key, {})
	var apply := is_new
	var last_polys := desired_hash
	if not is_new:
		if record.is_empty():
			# A tile from before the bookkeeping existed: rpggen's own if it matches the spec.
			apply = current_hash == desired_hash
		else:
			last_polys = String(record.get("polys", ""))
			apply = record.get("spec", "") != spec_hash and current_hash == last_polys
		if not apply and current_hash != last_polys:
			issues.append(ctx.make_issue("TILE-007", {"asset": asset["id"], "coords": tile_key.get_slice("/", 2)}, "res://" + str(asset["path"])))
	if apply:
		while td.get_collision_polygons_count(0) > 0:
			td.remove_collision_polygon(0, 0)
		for poly in desired:
			td.add_collision_polygon(0)
			td.set_collision_polygon_points(0, td.get_collision_polygons_count(0) - 1, poly)
		last_polys = desired_hash
	var new_record := {"spec": spec_hash, "polys": last_polys}
	if record != new_record:
		_apply[tile_key] = new_record
		_apply_dirty = true
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
