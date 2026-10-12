extends RefCounted
## Builds one TileSet resource per TileSetDef in the catalog.

const RECIPE_VERSION := 5

const Paths := preload("../lib/paths.gd")
const Geometry := preload("../lib/geometry.gd")
const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")
const SideTileset := preload("../lib/side_tileset.gd")
const IsoTileset := preload("../lib/iso_tileset.gd")

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for def in ctx.catalog.tileset_defs():
		out.append(Paths.TILESETS_DIR + "%s.tres" % def["name"])
	return out

func input_hash(ctx: BuildContext) -> String:
	var parts: Array = []
	for def in ctx.catalog.tileset_defs():
		var sources: Array = []
		var def_sources: Array = def.get("sources", [])
		for s: Dictionary in def_sources:
			var asset_id: String = s["asset"]
			var asset: Dictionary = ctx.catalog.asset(asset_id)
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
	var hashed := {"v": RECIPE_VERSION, "tilesets": parts, "nav": _wants_navigation(ctx)}
	if SideTileset.wanted(ctx.config):
		# only a metroidvania's hash has the key: a top-down project's hash is the one of 1.1
		hashed["side"] = _side_inputs(ctx)
	var iso := IsoTileset.inputs(ctx.catalog)
	if not iso.is_empty():
		# only an isometric project's hash has the key (T17.13): no other hash moves, which is
		# why RECIPE_VERSION stays what it was
		hashed["iso"] = iso
	return ctx.stable_hash(hashed)

## What the side-view parts of the TileSets are built from: every sheet's tags.
func _side_inputs(ctx: BuildContext) -> Array:
	var out: Array = []
	for def in ctx.catalog.tileset_defs():
		var def_sources: Array = def.get("sources", [])
		for s: Dictionary in def_sources:
			var asset_id: String = s["asset"]
			out.append([asset_id, ctx.catalog.effective(ctx.catalog.asset(asset_id)).get("tags", [])])
	return out

## features.navigation: the TileSet gets a navigation layer (T9.06).
func _wants_navigation(ctx: BuildContext) -> bool:
	return JsonUtil.to_bool(ctx.section("features").get("navigation", false))

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	_load_apply_state()
	_nav_enabled = _wants_navigation(ctx)
	_side = SideTileset.wanted(ctx.config)
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
var _nav_enabled := false
## The project is a metroidvania (T14.03): the TileSets get their side-view parts. False for every
## other archetype, whose TileSets are built exactly as before.
var _side := false

func _load_apply_state() -> void:
	_apply = {}
	if FileAccess.file_exists(APPLY_STATE):
		var data: Variant = JsonUtil.read(APPLY_STATE)
		if data is Dictionary:
			var state: Dictionary = data
			if state.get("tiles") is Dictionary:
				_apply = state["tiles"]

func _save_apply_state(issues: Array, ctx: BuildContext) -> void:
	if not _apply_dirty:
		return
	var err := JsonUtil.write(APPLY_STATE, {"apply_state_version": 1, "tiles": _apply})
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": APPLY_STATE, "err": err}, APPLY_STATE))

# TileSet.CELL_NEIGHBOR_* for the peering keys of a terrain assignment (T8.06). The names map 1:1.
const PEERING_BITS := {
	"right_side": TileSet.CELL_NEIGHBOR_RIGHT_SIDE,
	"bottom_right_corner": TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_CORNER,
	"bottom_side": TileSet.CELL_NEIGHBOR_BOTTOM_SIDE,
	"bottom_left_corner": TileSet.CELL_NEIGHBOR_BOTTOM_LEFT_CORNER,
	"left_side": TileSet.CELL_NEIGHBOR_LEFT_SIDE,
	"top_left_corner": TileSet.CELL_NEIGHBOR_TOP_LEFT_CORNER,
	"top_side": TileSet.CELL_NEIGHBOR_TOP_SIDE,
	"top_right_corner": TileSet.CELL_NEIGHBOR_TOP_RIGHT_CORNER,
}
const TERRAIN_MODES := {
	"corners_and_sides": TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES,
	"corners": TileSet.TERRAIN_MODE_MATCH_CORNERS,
	"sides": TileSet.TERRAIN_MODE_MATCH_SIDES,
}

## Adds the terrain sets and terrains of the definition the TileSet does not have yet. Existing
## ones are never changed or removed: painted maps and terrain edits in Godot depend on them.
static func ensure_terrain_sets(ts: TileSet, sets: Array) -> void:
	for i in sets.size():
		var spec: Dictionary = sets[i]
		if ts.get_terrain_sets_count() <= i:
			ts.add_terrain_set()
			var mode: TileSet.TerrainMode = TERRAIN_MODES.get(JsonUtil.to_str(spec.get("mode", "corners_and_sides")), TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES)
			ts.set_terrain_set_mode(i, mode)
		var terrains: Array = spec.get("terrains", [])
		while ts.get_terrains_count(i) < terrains.size():
			var t_index := ts.get_terrains_count(i)
			ts.add_terrain(i)
			var terrain_spec: Dictionary = terrains[t_index]
			ts.set_terrain_name(i, t_index, JsonUtil.to_str(terrain_spec.get("name", "terrain")))
			ts.set_terrain_color(i, t_index, Color.from_string(JsonUtil.to_str(terrain_spec.get("color", "#ffffff")), Color.WHITE))

## Index of the terrain set called `set_name` in the definition's list, or -1.
static func terrain_set_index(sets: Array, set_name: String) -> int:
	for i in sets.size():
		var set_spec: Dictionary = sets[i]
		if JsonUtil.to_str(set_spec.get("name", "")) == set_name:
			return i
	return -1

## Gives a tile its terrain and peering bits from a tile_overrides entry. Bits the terrain mode does
## not use are skipped. Returns true when the tile was changed.
static func apply_terrain(td: TileData, ts: TileSet, sets: Array, terrain: Dictionary) -> bool:
	var set_index := terrain_set_index(sets, JsonUtil.to_str(terrain.get("set", "")))
	if set_index < 0 or set_index >= ts.get_terrain_sets_count():
		return false
	td.terrain_set = set_index
	td.terrain = JsonUtil.to_int(terrain.get("terrain", -1))
	var peering: Dictionary = terrain.get("peering", {})
	for key: String in PEERING_BITS.keys():
		var value := JsonUtil.to_int(peering.get(key, -1))
		var bit: TileSet.CellNeighbor = PEERING_BITS[key]
		if value >= 0 and td.is_valid_terrain_peering_bit(bit):
			td.set_terrain_peering_bit(bit, value)
	return true

## The horizontal run of an animation override, or [] when Godot's atlas animation cannot show
## it: the frames must be consecutive cells of one row starting at the tile itself.
static func animation_run(coords: Vector2i, anim: Dictionary) -> Array:
	var frames: Array = anim.get("frames", [])
	if frames.size() < 2:
		return []
	for i in frames.size():
		if JsonUtil.to_int(frames[i][0]) != coords.x + i or JsonUtil.to_int(frames[i][1]) != coords.y:
			return []
	return frames

func _build_tileset(ctx: BuildContext, def: Dictionary, issues: Array) -> void:
	var out_path: String = Paths.TILESETS_DIR + "%s.tres" % def["name"]
	var def_sources: Array = def.get("sources", [])
	if def_sources.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": def["name"]}, out_path))
		return
	if IsoTileset.wanted(def):
		# the tile set of an isometric project (T17.13): diamonds, tiles that are single
		# pictures in an atlas. Nothing below this line is run for it, and it is run for
		# nothing else.
		_build_iso_tileset(ctx, def, issues)
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
	_ensure_layers(ts, def)

	if _side:
		SideTileset.ensure_layers(ts)

	if _nav_enabled and ts.get_navigation_layers_count() == 0:
		ts.add_navigation_layer()  # layer 0: walkable ground, see _configure_navigation

	var terrain_sets: Array = def.get("terrain_sets", [])
	ensure_terrain_sets(ts, terrain_sets)

	var sources: Array[Dictionary] = []
	sources.assign(def_sources)
	sources.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return JsonUtil.to_int(a["source_id"]) < JsonUtil.to_int(b["source_id"]))
	var in_def := {}
	for s in sources:
		in_def[JsonUtil.to_int(s["source_id"])] = true
		_build_source(ctx, ts, def, s, cell, issues)
	# Sources the TileSet has but the definition no longer lists stay (painted maps may use them).
	var allocations: Dictionary = ctx.catalog.catalog.get("id_allocations", {})
	var by_tileset: Dictionary = allocations.get("tilesets", {})
	var allocated: Dictionary = by_tileset.get(def["name"], {})
	var retired: Array = allocated.get("retired", [])
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

func _build_source(ctx: BuildContext, ts: TileSet, def: Dictionary, s: Dictionary, cell: Vector2i, issues: Array) -> void:
	var ts_name: String = def["name"]
	var asset_id: String = s["asset"]
	var asset: Dictionary = ctx.catalog.asset(asset_id)
	if asset.is_empty():
		issues.append(ctx.make_issue("CAT-004", {"asset": s["asset"], "file": "(catalog)"}))
		return
	var eff: Dictionary = ctx.catalog.effective(asset)
	var source_id := JsonUtil.to_int(s["source_id"])
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
	var cols := JsonUtil.to_int(floor((tex_size.x - 2.0 * margin.x + sep.x) / (atlas_cell.x + sep.x)))
	var rows := JsonUtil.to_int(floor((tex_size.y - 2.0 * margin.y + sep.y) / (atlas_cell.y + sep.y)))

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
	if _side:  # in a side-view room the ground is solid, and a sheet's tags say what it is
		sheet_collision = SideTileset.sheet_collision(eff)
	var filled := {}
	# Animated tiles (T8.07): the cells after the first frame belong to the animation and get no
	# tile of their own (Godot refuses an animation over existing tiles).
	var runs := {}
	var covered := {}
	for key: String in overrides.keys():
		var override_spec: Dictionary = overrides[key]
		var anim: Variant = override_spec.get("anim")
		if not (anim is Dictionary):
			continue
		var parts: PackedStringArray = JsonUtil.to_str(key).split(",")
		var first := Vector2i(int(parts[0]), int(parts[1]))
		var anim_spec: Dictionary = anim
		var run := animation_run(first, anim_spec)
		if run.is_empty():
			issues.append(ctx.make_issue("TILE-008", {"asset": s["asset"], "coords": JsonUtil.to_str(key)}, "res://" + str(asset["path"])))
			continue
		runs[first] = {"count": run.size(), "durations_ms": anim_spec.get("durations_ms", [])}
		for i in range(1, run.size()):
			covered[Vector2i(first.x + i, first.y)] = true
	for cy in rows:
		for cx in cols:
			var key := "%d,%d" % [cx, cy]
			var ov: Dictionary = overrides.get(key, {})
			if ov.get("skip", false) or covered.has(Vector2i(cx, cy)):
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
			var tile_collision: Dictionary = ov.get("collision", sheet_collision)
			_configure_tile(ctx, src.get_tile_data(coords, 0), asset, tile_collision, atlas_cell, cell_img, is_new, tile_key, issues)
			if _side:
				SideTileset.configure_tile(src.get_tile_data(coords, 0), eff, ov, tile_collision, atlas_cell)
			if _nav_enabled:
				_configure_navigation(src.get_tile_data(coords, 0), JsonUtil.to_str(eff.get("role", "")), tile_collision, atlas_cell)
			var terrain: Variant = ov.get("terrain")
			if terrain is Dictionary:
				var td := src.get_tile_data(coords, 0)
				# A tile that already has a terrain keeps it: the user may have edited it in Godot.
				if is_new or td.terrain_set == -1:
					var terrain_spec: Dictionary = terrain
					var tile_terrain_sets: Array = def.get("terrain_sets", [])
					apply_terrain(td, ts, tile_terrain_sets, terrain_spec)
			if runs.has(coords):
				var run_spec: Dictionary = runs[coords]
				_apply_animation(ctx, src, coords, run_spec, asset, issues)
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

## Turns a tile into an animated tile of `run.count` frames in the cells to its right.
func _apply_animation(ctx: BuildContext, src: TileSetAtlasSource, coords: Vector2i, run: Dictionary, asset: Dictionary, issues: Array) -> void:
	var count: int = run["count"]
	if src.get_tile_animation_frames_count(coords) == count:
		return  # built before
	for i in range(1, count):
		if src.has_tile(Vector2i(coords.x + i, coords.y)):
			# Tiles exist there already (painted maps may use them): Godot cannot animate over them.
			issues.append(ctx.make_issue("TILE-008", {"asset": asset["id"], "coords": "%d,%d" % [coords.x, coords.y]}, "res://" + str(asset["path"])))
			return
	src.set_tile_animation_columns(coords, count)
	src.set_tile_animation_frames_count(coords, count)
	var durations: Array = run["durations_ms"]
	for i in count:
		var ms := JsonUtil.to_float(durations[i]) if i < durations.size() else 100.0
		src.set_tile_animation_frame_duration(coords, i, ms / 1000.0)

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
		var custom_polygon: Array = collision.get("polygon", [])
		var pts := Geometry.profile_polygon(profile, atlas_cell, custom_polygon)
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
	for poly: PackedVector2Array in polys:
		var pts: PackedStringArray = []
		for p in poly:
			pts.append("%.3f,%.3f" % [p.x, p.y])
		parts.append(";".join(pts))
	return "|".join(parts).sha256_text()

## Sets up one tile. Collision is replaced only when the catalog's collision for the tile changed
## since the last build and the polygons are still the ones rpggen applied; polygons edited in
## Godot are kept (TILE-007).
func _configure_tile(ctx: BuildContext, td: TileData, asset: Dictionary, collision: Dictionary, atlas_cell: Vector2i, cell_img: Image, is_new: bool, tile_key: String, issues: Array) -> void:
	var desired := _desired_polygons(collision, atlas_cell, cell_img)
	var pixels := ""
	if collision.get("profile", "NONE") == "ALPHA_POLYGON":
		pixels = cell_img.get_data().hex_encode().sha256_text()
	var spec_hash: String = ctx.stable_hash({"c": collision, "cell": [atlas_cell.x, atlas_cell.y], "px": pixels})
	_apply_collision(ctx, td, asset, spec_hash, desired, is_new, tile_key, issues)
	td.set_custom_data("asset_id", asset["id"])

## Gives a tile the polygons `desired` under the bookkeeping of T5.04: they replace what is there
## only when the spec (`spec_hash`) changed since the last build and the polygons are still the
## ones rpggen applied.
func _apply_collision(ctx: BuildContext, td: TileData, asset: Dictionary, spec_hash: String, desired: Array, is_new: bool, tile_key: String, issues: Array) -> void:
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
			last_polys = JsonUtil.to_str(record.get("polys", ""))
			apply = record.get("spec", "") != spec_hash and current_hash == last_polys
		if not apply and current_hash != last_polys:
			issues.append(ctx.make_issue("TILE-007", {"asset": asset["id"], "coords": tile_key.get_slice("/", 2)}, "res://" + str(asset["path"])))
	if apply:
		while td.get_collision_polygons_count(0) > 0:
			td.remove_collision_polygon(0, 0)
		for poly: PackedVector2Array in desired:
			td.add_collision_polygon(0)
			td.set_collision_polygon_points(0, td.get_collision_polygons_count(0) - 1, poly)
		last_polys = desired_hash
	var new_record := {"spec": spec_hash, "polys": last_polys}
	if record != new_record:
		_apply[tile_key] = new_record
		_apply_dirty = true

# --------------------------------------------------------------------------- isometric (T17.13)

## The tile set of an isometric project. The merge rules are the ones above: an existing file is
## loaded and added to, a source keeps its id, a tile its atlas coords, nothing is removed.
func _build_iso_tileset(ctx: BuildContext, def: Dictionary, issues: Array) -> void:
	var out_path: String = Paths.TILESETS_DIR + "%s.tres" % def["name"]
	var ts: TileSet = null
	var merging := FileAccess.file_exists(out_path)
	if merging:
		ts = ResourceLoader.load(out_path, "TileSet", ResourceLoader.CACHE_MODE_IGNORE) as TileSet
		if ts == null:
			issues.append(ctx.make_issue("BUILD-002", {"recipe": "tileset_recipe", "reason": "the existing TileSet %s could not be loaded; it was not touched" % out_path}, out_path))
			return
	else:
		ts = TileSet.new()
	var footprint: Vector2i = ctx.vec2i(def["tile_size"])
	if not merging:
		IsoTileset.shape(ts, footprint)
	elif ts.tile_size != footprint or not IsoTileset.has_shape(ts):
		# maps are painted on the diamonds the tile set has: they stay
		issues.append(ctx.make_issue("TILE-004", {"asset": def["name"]}, out_path))
	footprint = ts.tile_size
	_ensure_layers(ts, def)
	if _nav_enabled and ts.get_navigation_layers_count() == 0:
		ts.add_navigation_layer()
	var sources: Array[Dictionary] = []
	sources.assign(JsonUtil.to_array(def.get("sources", [])))
	sources.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return JsonUtil.to_int(a["source_id"]) < JsonUtil.to_int(b["source_id"]))
	for s in sources:
		_build_iso_source(ctx, ts, def, s, footprint, issues)
	DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
	var err := ResourceSaver.save(ts, out_path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": out_path, "err": err}, out_path))

## The physics and custom data layers of a definition the TileSet does not have yet.
func _ensure_layers(ts: TileSet, def: Dictionary) -> void:
	var physics: Array = def.get("physics_layers", [])
	while ts.get_physics_layers_count() < physics.size():
		var idx := ts.get_physics_layers_count()
		ts.add_physics_layer()
		ts.set_physics_layer_collision_layer(idx, JsonUtil.to_int(physics[idx]["layer_bits"]))
		ts.set_physics_layer_collision_mask(idx, JsonUtil.to_int(physics[idx]["mask_bits"]))
	var custom_types := {"string": TYPE_STRING, "float": TYPE_FLOAT, "int": TYPE_INT, "bool": TYPE_BOOL}
	var custom_layers: Array = def.get("custom_data", [])
	for layer: Dictionary in custom_layers:
		var layer_name: String = layer["name"]
		if ts.get_custom_data_layer_by_name(layer_name) == -1:
			ts.add_custom_data_layer()
			var idx := ts.get_custom_data_layers_count() - 1
			ts.set_custom_data_layer_name(idx, layer_name)
			var layer_type: Variant.Type = custom_types.get(layer.get("type", "string"), TYPE_STRING)
			ts.set_custom_data_layer_type(idx, layer_type)

## One atlas picture of single tiles as a source: every tile the definition places in it gets
## its tile, its origin, its custom data and its collision. A tile the source has and the
## definition no longer places (its picture left the pack) stays, and is reported (TILE-005).
func _build_iso_source(ctx: BuildContext, ts: TileSet, def: Dictionary, s: Dictionary, footprint: Vector2i, issues: Array) -> void:
	var ts_name: String = def["name"]
	var atlas_id: String = s["asset"]
	var atlas: Dictionary = ctx.catalog.asset(atlas_id)
	if atlas.is_empty():
		issues.append(ctx.make_issue("CAT-004", {"asset": atlas_id, "file": "(catalog)"}))
		return
	var source_id := JsonUtil.to_int(s["source_id"])
	var tex_path: String = "res://" + str(atlas["path"])
	var tex := load(tex_path) as Texture2D
	if tex == null:
		issues.append(ctx.make_issue("VAL-002", {"file": tex_path}, tex_path))
		return
	var src: TileSetAtlasSource
	if ts.has_source(source_id):
		src = ts.get_source(source_id) as TileSetAtlasSource
	else:
		src = TileSetAtlasSource.new()
		ts.add_source(src, source_id)
	var grid: Dictionary = ctx.catalog.effective(atlas).get("grid", {})
	var atlas_cell: Vector2i = ctx.vec2i(grid.get("cell", [footprint.x, footprint.y]))
	if src.texture == null or src.texture.resource_path != tex_path:
		src.texture = tex
	if src.texture_region_size != atlas_cell:
		src.texture_region_size = atlas_cell
	var placed := {}
	for tile in IsoTileset.tiles_of_source(def, source_id):
		var asset_id: String = tile["id"]
		var coords: Vector2i = tile["coords"]
		var at: Vector2i = tile["at"]
		var asset: Dictionary = ctx.catalog.asset(asset_id)
		if asset.is_empty():
			issues.append(ctx.make_issue("CAT-004", {"asset": asset_id, "file": "(catalog)"}))
			continue
		var eff: Dictionary = ctx.catalog.effective(asset)
		if (coords.x + 1) * atlas_cell.x > tex.get_width() or (coords.y + 1) * atlas_cell.y > tex.get_height():
			issues.append(ctx.make_issue("TILE-002", {"asset": atlas_id, "coords": "%d,%d" % [coords.x, coords.y]}, tex_path))
			continue
		placed[coords] = true
		var is_new := IsoTileset.configure_tile(ts, src, coords, at, atlas_cell, asset, eff)
		var td := src.get_tile_data(coords, 0)
		var collision := IsoTileset.default_collision(eff)
		var middle := atlas_cell / 2
		var origin: Vector2i = ctx.vec2i(eff.get("origin", [middle.x, middle.y]))
		var desired := IsoTileset.collision_polygons(collision, footprint, origin)
		var spec_hash: String = ctx.stable_hash({"c": collision, "iso": [footprint.x, footprint.y], "o": [origin.x, origin.y]})
		_apply_collision(ctx, td, asset, spec_hash, desired, is_new, "%s/%d/%d,%d" % [ts_name, source_id, coords.x, coords.y], issues)
		if _nav_enabled and JsonUtil.to_str(eff.get("role", "")) == "GROUND" and collision.get("profile", "NONE") == "NONE" and td.get_navigation_polygon(0) == null:
			td.set_navigation_polygon(0, IsoTileset.navigation_polygon(footprint))
	var emptied: Array = []
	for i in src.get_tiles_count():
		var coords := src.get_tile_id(i)
		if not placed.has(coords):
			emptied.append("%d,%d" % [coords.x, coords.y])
	if not emptied.is_empty():
		emptied.sort()
		var shown: String = ", ".join(emptied.slice(0, 8)) + (" ..." if emptied.size() > 8 else "")
		issues.append(ctx.make_issue("TILE-005", {"asset": atlas_id, "coords": shown}, tex_path))

## Every GROUND-role tile without collision gets a full-tile navigation polygon on layer 0. A tile
## that already has one (maybe edited in Godot) is left alone.
func _configure_navigation(td: TileData, role: String, collision: Dictionary, atlas_cell: Vector2i) -> void:
	if role != "GROUND" or collision.get("profile", "NONE") != "NONE" or td.get_navigation_polygon(0) != null:
		return
	var half := Vector2(atlas_cell) * 0.5
	var poly := NavigationPolygon.new()
	poly.vertices = PackedVector2Array([Vector2(-half.x, -half.y), Vector2(half.x, -half.y), Vector2(half.x, half.y), Vector2(-half.x, half.y)])
	poly.add_polygon(PackedInt32Array([0, 1, 2, 3]))
	td.set_navigation_polygon(0, poly)

## TileMapPatterns from sheet objects (T4.06): one pattern per object, in object id order. Every
## existing pattern is removed first, so a rebuild never duplicates them.
func _build_patterns(ctx: BuildContext, ts: TileSet, sources: Array[Dictionary]) -> void:
	while ts.get_patterns_count() > 0:
		ts.remove_pattern(0)
	var source_of := {}
	for s in sources:
		source_of[s["asset"]] = JsonUtil.to_int(s["source_id"])
	for o in ctx.catalog.objects():
		if o.get("status", "") == "UNUSED" or o.get("role", "NONE") == "NONE" or not source_of.has(o["sheet"]):
			continue
		var source_id: int = source_of[o["sheet"]]
		var src := ts.get_source(source_id) as TileSetAtlasSource
		if src == null:
			continue
		var sheet_id: String = o["sheet"]
		var grid: Dictionary = ctx.catalog.effective(ctx.catalog.asset(sheet_id)).get("grid", {})
		var atlas_cell: Vector2i = ctx.vec2i(grid.get("cell", [16, 16]))
		var margin: Vector2i = ctx.vec2i(grid.get("margin", [0, 0]))
		var sep: Vector2i = ctx.vec2i(grid.get("separation", [0, 0]))
		var step := atlas_cell + sep
		var region: Array = o["region"]
		var first := Vector2i((JsonUtil.to_int(region[0]) - margin.x) / step.x, (JsonUtil.to_int(region[1]) - margin.y) / step.y)
		var last := Vector2i((JsonUtil.to_int(region[0]) + JsonUtil.to_int(region[2]) - 1 - margin.x) / step.x, (JsonUtil.to_int(region[1]) + JsonUtil.to_int(region[3]) - 1 - margin.y) / step.y)
		var pattern := TileMapPattern.new()
		for cy in range(first.y, last.y + 1):
			for cx in range(first.x, last.x + 1):
				var coords := Vector2i(cx, cy)
				if src.has_tile(coords):
					pattern.set_cell(coords - first, source_id, coords, 0)
		if not pattern.is_empty():
			ts.add_pattern(pattern)
