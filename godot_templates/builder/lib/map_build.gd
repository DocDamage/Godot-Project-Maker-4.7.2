extends RefCounted
## Layout planning and painting helpers shared by the map recipes (T11.23, T11.25).
##
## `plan` is the same algorithm as `plan` in rpggen/core/map_preview.py (the Python twin that draws
## the preview). godot_templates/tests/fixtures/map_plan_cases.json holds 20 option sets with the
## expected plan and both sides check it, so keep the two in step: integers only, and no random
## numbers except the small LCG below. With the default options the plan is the map of every
## project made before M11.

const MapUtil := preload("map_util.gd")
const SceneUtil := preload("scene_util.gd")
const JsonUtil := preload("json_util.gd")
const BuildContext := preload("build_context.gd")

const DEFAULT_SIZE := Vector2i(40, 24)
const DEFAULT_HOUSE := Vector2i(8, 6)
const DEFAULT_SPAWN := Vector2i(12, 12)
const DEFAULT_NPC := Vector2i(16, 12)
const DEFAULT_CHEST := Vector2i(18, 8)
const DEFAULT_ENEMY := Vector2i(28, 12)
const ENEMY_OFFSET_TILES := 4
const DEFAULT_DECOR: Array[Vector2i] = [Vector2i(20, 4), Vector2i(24, 5), Vector2i(30, 8), Vector2i(33, 14),
	Vector2i(6, 17), Vector2i(14, 19), Vector2i(26, 18), Vector2i(35, 20)]
const ENEMY_MIN_DISTANCE := 8
const CLEARANCE := 3
const ATTEMPTS := 20

# ---------------------------------------------------------------- random numbers

static func fnv1a32(text: String) -> int:
	var h := 2166136261
	for byte in text.to_utf8_buffer():
		h = h ^ byte
		h = (h * 16777619) & 0xFFFFFFFF
	return h

## The seed of one named random stream of a map ("starter_map", "field_1", ...).
static func stream_seed(map_seed: int, label: String) -> int:
	return fnv1a32("%d:%s" % [map_seed, label])

## A 32-bit LCG; `range_inclusive` includes both ends.
class Lcg extends RefCounted:
	var state := 0

	func _init(start: int) -> void:
		state = start & 0xFFFFFFFF

	func next_value() -> int:
		state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
		return state >> 8

	func range_inclusive(lo: int, hi: int) -> int:
		return lo + next_value() % (hi - lo + 1)

	func shuffle(items: Array) -> void:
		for i in range(items.size() - 1, 0, -1):
			var j := range_inclusive(0, i)
			var tmp: Variant = items[i]
			items[i] = items[j]
			items[j] = tmp

	## A random item of `items`, or null when it is empty.
	func pick(items: Array) -> Variant:
		if items.is_empty():
			return null
		return items[range_inclusive(0, items.size() - 1)]

# ---------------------------------------------------------------- the plan

## The options with every key filled in from the archetype's defaults.
static func merged_options(options: Dictionary, archetype: String) -> Dictionary:
	var out := {
		"size": [DEFAULT_SIZE.x, DEFAULT_SIZE.y], "buildings": 1, "npcs": 1,
		"enemies": 2 if archetype == "arpg" else 1, "chests": 1, "decorations": 8,
		"ground_patches": 6, "ground": "",
	}
	for key: Variant in options.keys():
		out[key] = options[key]
	return out

static func is_default(options: Dictionary, archetype: String) -> bool:
	var defaults := merged_options({}, archetype)
	for key: String in defaults.keys():
		if key == "ground":
			continue
		if key == "size":
			if JsonUtil.to_int(options["size"][0]) != DEFAULT_SIZE.x or JsonUtil.to_int(options["size"][1]) != DEFAULT_SIZE.y:
				return false
		elif JsonUtil.to_int(options[key]) != JsonUtil.to_int(defaults[key]):
			return false
	return true

## A road from the spawn along its row to the door's column, then up to the door.
static func path_cells(spawn: Vector2i, door: Vector2i) -> Array[Vector2i]:
	var cells: Array[Vector2i] = []
	var step := 1 if door.x >= spawn.x else -1
	for x in range(spawn.x, door.x + step, step):
		cells.append(Vector2i(x, spawn.y))
	for y in range(door.y, spawn.y + 1):
		cells.append(Vector2i(door.x, y))
	return cells

## The east exit: the gap in the east wall and the road to it.
class ExitRoute extends RefCounted:
	var gap := Vector2i.ZERO
	var cells: Array[Vector2i] = []

## The east exit. The road goes down from the spawn to a row three tiles lower, then east to the wall.
static func exit_route(spawn: Vector2i, size: Vector2i) -> ExitRoute:
	var exit_y := mini(spawn.y + 3, size.y - 3)
	var route := ExitRoute.new()
	for y in range(spawn.y, exit_y + 1):
		route.cells.append(Vector2i(spawn.x, y))
	for x in range(spawn.x + 1, size.x - 1):
		route.cells.append(Vector2i(x, exit_y))
	route.gap = Vector2i(size.x - 1, exit_y)
	return route

static func _rect_has(r: Rect2i, x: int, y: int) -> bool:
	return x >= r.position.x and x < r.position.x + r.size.x and y >= r.position.y and y < r.position.y + r.size.y

static func _rects_intersect(a: Rect2i, b: Rect2i) -> bool:
	return a.position.x < b.position.x + b.size.x and b.position.x < a.position.x + a.size.x \
		and a.position.y < b.position.y + b.size.y and b.position.y < a.position.y + a.size.y

static func _default_plan(opts: Dictionary, building: Dictionary) -> Dictionary:
	var has_building := not building.is_empty() and JsonUtil.to_int(opts["buildings"]) > 0
	var buildings: Array[Vector2i] = []
	if has_building:
		buildings.append(DEFAULT_HOUSE)
	var doors: Array[Vector2i] = []
	var path: Array[Vector2i] = []
	if has_building:
		var door := DEFAULT_HOUSE + Vector2i(JsonUtil.to_int(building["door"][0]), JsonUtil.to_int(building["door"][1]))
		doors.append(door)
		path = path_cells(DEFAULT_SPAWN, door)
	var enemies: Array[Vector2i] = []
	for i in JsonUtil.to_int(opts["enemies"]):
		enemies.append(DEFAULT_ENEMY + Vector2i(ENEMY_OFFSET_TILES * i, 0))
	var npcs: Array[Vector2i] = []
	if JsonUtil.to_int(opts["npcs"]) >= 1:
		npcs.append(DEFAULT_NPC)
	var chests: Array[Vector2i] = []
	if JsonUtil.to_int(opts["chests"]) >= 1:
		chests.append(DEFAULT_CHEST)
	var size := Vector2i(JsonUtil.to_int(opts["size"][0]), JsonUtil.to_int(opts["size"][1]))
	var route := exit_route(DEFAULT_SPAWN, size)
	var no_patches: Array[Dictionary] = []
	var no_warnings: Array[String] = []
	return {
		"size": size, "exit_gap": route.gap, "exit_path": route.cells,
		"buildings": buildings, "doors": doors, "spawn": DEFAULT_SPAWN,
		"npcs": npcs, "chests": chests, "enemies": enemies,
		"decorations": DEFAULT_DECOR.duplicate(), "path": path,
		"patches": no_patches, "legacy_patches": true, "patch_count": JsonUtil.to_int(opts["ground_patches"]),
		"warnings": no_warnings, "is_default": true,
	}

## State of one planning run.
class Grid extends RefCounted:
	var w := 0
	var h := 0
	var rects: Array[Rect2i] = []
	var reserved := {}
	var occupied := {}

	func inside(x: int, y: int) -> bool:
		return x >= 1 and x <= w - 2 and y >= 1 and y <= h - 2

	func in_building(x: int, y: int) -> bool:
		for r in rects:
			if x >= r.position.x and x < r.position.x + r.size.x and y >= r.position.y and y < r.position.y + r.size.y:
				return true
		return false

	func is_free(x: int, y: int) -> bool:
		var cell := Vector2i(x, y)
		return inside(x, y) and not in_building(x, y) and not occupied.has(cell) and not reserved.has(cell)

	func free_tiles() -> Array[Vector2i]:
		var out: Array[Vector2i] = []
		for y in range(1, h - 1):
			for x in range(1, w - 1):
				if is_free(x, y):
					out.append(Vector2i(x, y))
		return out

## The layout of a starter map. `building` is {"size": [w, h], "door": [dx, dy]} in tiles (the door
## relative to the building's top-left corner, one row below its base) or {} for none. Returns
## {size, buildings, doors, spawn, npcs, chests, enemies, decorations, path, patches, warnings,
## legacy_patches, patch_count, is_default} with Vector2i tiles and, for patches,
## {rect: Rect2i, index: int}.
static func plan(options: Dictionary, map_seed: int, building: Dictionary = {}, archetype: String = "turn_based") -> Dictionary:
	var opts := merged_options(options, archetype)
	if is_default(opts, archetype):
		return _default_plan(opts, building)
	var w := JsonUtil.to_int(opts["size"][0])
	var h := JsonUtil.to_int(opts["size"][1])
	var rng := Lcg.new(stream_seed(map_seed, "starter_map"))
	var warnings: Array[String] = []
	var grid := Grid.new()
	grid.w = w
	grid.h = h

	# buildings on a coarse grid with 3 tiles of clearance; the door side stays free
	var doors: Array[Vector2i] = []
	if not building.is_empty() and JsonUtil.to_int(opts["buildings"]) > 0:
		var bw := JsonUtil.to_int(building["size"][0])
		var bh := JsonUtil.to_int(building["size"][1])
		var candidates: Array[Vector2i] = []
		var y := 2
		while y + bh + 2 <= h - 2:
			var x := CLEARANCE
			while x + bw + CLEARANCE <= w - 1:
				candidates.append(Vector2i(x, y))
				x += bw + 2 * CLEARANCE
			y += bh + 2 * CLEARANCE
		rng.shuffle(candidates)
		var count := mini(JsonUtil.to_int(opts["buildings"]), candidates.size())
		for i in count:
			var at: Vector2i = candidates[i]
			grid.rects.append(Rect2i(at.x, at.y, bw, bh))
			doors.append(Vector2i(at.x + JsonUtil.to_int(building["door"][0]), at.y + JsonUtil.to_int(building["door"][1])))

	# the spawn in front of the first door, else the centre
	var spawn := Vector2i(w >> 1, h >> 1)
	if not doors.is_empty():
		spawn = Vector2i(mini(maxi(doors[0].x, 2), w - 3), mini(doors[0].y + 3, h - 3))

	# No road may run through a house: the road to the east exit and the roads to the doors. The
	# first house cannot be in its own way; the others are dropped when they are.
	var route := exit_route(spawn, Vector2i(w, h))
	if grid.rects.size() > 1:
		var kept_rects: Array[Rect2i] = [grid.rects[0]]
		var kept_doors: Array[Vector2i] = [doors[0]]
		var roads := {}
		for cell in route.cells:
			roads[cell] = true
		for cell in path_cells(spawn, doors[0]):
			roads[cell] = true
		for i in range(1, grid.rects.size()):
			var road := path_cells(spawn, doors[i])
			var blocked := false
			for cell: Vector2i in roads.keys():
				if _rect_has(grid.rects[i], cell.x, cell.y):
					blocked = true
					break
			if not blocked:
				for kept in kept_rects:
					for cell in road:
						if _rect_has(kept, cell.x, cell.y):
							blocked = true
							break
					if blocked:
						break
			if not blocked:
				kept_rects.append(grid.rects[i])
				kept_doors.append(doors[i])
				for cell in road:
					roads[cell] = true
		grid.rects = kept_rects
		doors = kept_doors
	if not building.is_empty() and grid.rects.size() < JsonUtil.to_int(opts["buildings"]):
		warnings.append("buildings: placed %d of %d" % [grid.rects.size(), JsonUtil.to_int(opts["buildings"])])
	var path: Array[Vector2i] = []
	var seen_path := {}
	for door in doors:
		for cell in path_cells(spawn, door):
			if not seen_path.has(cell):
				seen_path[cell] = true
				path.append(cell)
	for cell: Vector2i in seen_path.keys():
		grid.reserved[cell] = true
	for cell in route.cells:
		grid.reserved[cell] = true
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			grid.reserved[Vector2i(spawn.x + dx, spawn.y + dy)] = true
	for door in doors:
		grid.reserved[door] = true
		grid.reserved[Vector2i(door.x, door.y + 1)] = true
		grid.reserved[Vector2i(door.x, door.y + 2)] = true

	# NPCs beside the road
	var npcs: Array[Vector2i] = []
	for _i in JsonUtil.to_int(opts["npcs"]):
		var beside: Array[Vector2i] = []
		for cell in path:
			for cand: Vector2i in [Vector2i(cell.x - 1, cell.y), Vector2i(cell.x + 1, cell.y)]:
				if grid.is_free(cand.x, cand.y) and not beside.has(cand):
					beside.append(cand)
		var near: Array[Vector2i] = beside
		if near.is_empty():
			for y in range(1, h - 1):
				for x in range(1, w - 1):
					if absi(x - spawn.x) <= 4 and absi(y - spawn.y) <= 4 and grid.is_free(x, y):
						near.append(Vector2i(x, y))
		var found: Variant = rng.pick(near)
		if found == null:
			warnings.append("npcs: placed %d of %d" % [npcs.size(), JsonUtil.to_int(opts["npcs"])])
			break
		grid.occupied[found] = true
		npcs.append(found)

	# chests against a building or the border
	var chests: Array[Vector2i] = []
	for _i in JsonUtil.to_int(opts["chests"]):
		var against: Array[Vector2i] = []
		for y in range(1, h - 1):
			for x in range(1, w - 1):
				if not grid.is_free(x, y):
					continue
				var hit := x == 1 or y == 1 or x == w - 2 or y == h - 2
				if not hit:
					for n: Vector2i in [Vector2i(x - 1, y), Vector2i(x + 1, y), Vector2i(x, y - 1), Vector2i(x, y + 1)]:
						if grid.in_building(n.x, n.y):
							hit = true
							break
				if hit:
					against.append(Vector2i(x, y))
		var found: Variant = rng.pick(against)
		if found == null:
			found = rng.pick(grid.free_tiles())
		if found == null:
			warnings.append("chests: placed %d of %d" % [chests.size(), JsonUtil.to_int(opts["chests"])])
			break
		grid.occupied[found] = true
		chests.append(found)

	# enemies at least 8 tiles from the spawn
	var enemies: Array[Vector2i] = []
	for _i in JsonUtil.to_int(opts["enemies"]):
		var found: Variant = rng.pick(_far_tiles(grid, spawn, ENEMY_MIN_DISTANCE))
		if found == null:
			found = rng.pick(_far_tiles(grid, spawn, 4))
		if found == null:
			warnings.append("enemies: placed %d of %d" % [enemies.size(), JsonUtil.to_int(opts["enemies"])])
			break
		grid.occupied[found] = true
		enemies.append(found)

	# decorations anywhere left: never on the road, a door approach or within 1 tile of an entity
	var keep_clear := {}
	for cell: Vector2i in grid.occupied.keys():
		keep_clear[cell] = true
	for cell: Vector2i in seen_path.keys():
		keep_clear[cell] = true
	for cell in route.cells:
		keep_clear[cell] = true
	for door in doors:
		keep_clear[door] = true
		keep_clear[Vector2i(door.x, door.y + 1)] = true
		keep_clear[Vector2i(door.x, door.y + 2)] = true
	var spots: Array[Vector2i] = []
	for y in range(1, h - 1):
		for x in range(1, w - 1):
			if grid.is_free(x, y) and _clear_of_entities(grid, keep_clear, x, y):
				spots.append(Vector2i(x, y))
	var decorations: Array[Vector2i] = []
	for _i in JsonUtil.to_int(opts["decorations"]):
		if spots.is_empty():
			warnings.append("decorations: placed %d of %d" % [decorations.size(), JsonUtil.to_int(opts["decorations"])])
			break
		decorations.append(spots.pop_at(rng.range_inclusive(0, spots.size() - 1)))

	# patches of other ground, away from the buildings
	var patches: Array[Dictionary] = []
	for i in JsonUtil.to_int(opts["ground_patches"]):
		var pw := rng.range_inclusive(2, 4)
		var ph := rng.range_inclusive(2, 4)
		var rect := Rect2i()
		var placed := false
		for _attempt in ATTEMPTS:
			var px := rng.range_inclusive(2, w - pw - 2)
			var py := rng.range_inclusive(2, h - ph - 2)
			var candidate := Rect2i(px, py, pw, ph)
			var clear := true
			for r in grid.rects:
				if _rects_intersect(candidate, Rect2i(r.position.x - 2, r.position.y - 2, r.size.x + 4, r.size.y + 4)):
					clear = false
					break
			if clear:
				rect = candidate
				placed = true
				break
		if placed:
			patches.append({"rect": rect, "index": i})

	var buildings: Array[Vector2i] = []
	for r in grid.rects:
		buildings.append(r.position)
	return {
		"size": Vector2i(w, h), "exit_gap": route.gap, "exit_path": route.cells,
		"buildings": buildings, "doors": doors, "spawn": spawn,
		"npcs": npcs, "chests": chests, "enemies": enemies, "decorations": decorations,
		"path": path, "patches": patches, "legacy_patches": false,
		"patch_count": JsonUtil.to_int(opts["ground_patches"]), "warnings": warnings, "is_default": false,
	}

static func _far_tiles(grid: Grid, spawn: Vector2i, distance: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y in range(1, grid.h - 1):
		for x in range(1, grid.w - 1):
			if grid.is_free(x, y) and maxi(absi(x - spawn.x), absi(y - spawn.y)) >= distance:
				out.append(Vector2i(x, y))
	return out

static func _clear_of_entities(grid: Grid, keep_clear: Dictionary, x: int, y: int) -> bool:
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			if keep_clear.has(Vector2i(x + dx, y + dy)) or grid.in_building(x + dx, y + dy):
				return false
	return true

## The plan as plain arrays ([x, y] tiles, [x, y, w, h] rectangles), the shape of the fixture file.
static func to_json(p: Dictionary) -> Dictionary:
	var out := {}
	for key: Variant in p.keys():
		var v: Variant = p[key]
		if key == "patches":
			var list: Array = []
			var patch_items: Array = v
			for item: Dictionary in patch_items:
				var r: Rect2i = item["rect"]
				list.append({"rect": [r.position.x, r.position.y, r.size.x, r.size.y], "index": item["index"]})
			out[key] = list
		elif v is Vector2i:
			out[key] = [v.x, v.y]
		elif v is Array and key != "warnings":
			var tiles: Array = []
			var tile_items: Array = v
			for item: Vector2i in tile_items:
				tiles.append([item.x, item.y])
			out[key] = tiles
		else:
			out[key] = v
	return out

# ---------------------------------------------------------------- painting

## One-tile-per-cell fill of the whole map with the base ground tile.
static func fill_ground(ground: TileMapLayer, size: Vector2i, base: Dictionary) -> void:
	MapUtil.fill(ground, Rect2i(Vector2i.ZERO, size), base)

## The legacy patches: sizes and places come from Godot's seeded generator (the map every project
## before M11 has); `avoid` is the area around the house that they stay away from.
static func paint_legacy_patches(ground: TileMapLayer, size: Vector2i, others: Array, map_seed: int, count: int, avoid: Rect2i) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = map_seed
	for i in count:
		var psize := Vector2i(rng.randi_range(2, 4), rng.randi_range(2, 4))
		var rect := Rect2i()
		for attempt in 20:
			var pos := Vector2i(rng.randi_range(2, size.x - psize.x - 2), rng.randi_range(2, size.y - psize.y - 2))
			rect = Rect2i(pos, psize)
			if not rect.intersects(avoid):
				break
			rect = Rect2i()
		if rect.size != Vector2i.ZERO:
			var other_tile: Dictionary = others[i % others.size()]
			MapUtil.fill(ground, rect, other_tile)

## The planned patches (see `plan`).
static func paint_planned_patches(ground: TileMapLayer, patches: Array, others: Array) -> void:
	for item: Dictionary in patches:
		var patch_rect: Rect2i = item["rect"]
		var patch_tile: Dictionary = others[JsonUtil.to_int(item["index"]) % others.size()]
		MapUtil.fill(ground, patch_rect, patch_tile)

## The border: wall tiles when the map has a Walls layer, else ground tiles that look like a wall
## plus invisible collision rectangles.
static func paint_walls(root: Node2D, nodes: Dictionary, size: Vector2i, wall: Dictionary, tile_px: int, skip: Array = []) -> void:
	var rect := Rect2i(Vector2i.ZERO, size)
	if not wall.is_empty() and nodes.has("Walls"):
		var walls: TileMapLayer = nodes["Walls"]
		MapUtil.border(walls, rect, wall, skip)
	else:
		if not wall.is_empty():
			var ground: TileMapLayer = nodes["Ground"]
			MapUtil.border(ground, rect, wall, skip)  # looks like a wall; the rectangles block
		MapUtil.border_collision(root, size, tile_px, skip)

## A trigger in a wall gap that sends the player to another map (the same node as a building's
## door: an RpgDoor on the triggers layer that reacts to the player).
static func add_exit_door(triggers: Node, root: Node, node_name: String, cell: Vector2i, tile_px: int, target_map: String, target_spawn: StringName) -> Area2D:
	var door := Area2D.new()
	SceneUtil.attach_script(door, MapUtil.DOOR_SCRIPT)
	door.collision_layer = 0
	door.collision_mask = 0
	door.set_collision_layer_value(6, true)  # triggers
	door.set_collision_mask_value(2, true)  # player
	door.position = MapUtil.tile_center(cell, tile_px)
	door.set("target_map", target_map)
	door.set("target_spawn", target_spawn)
	SceneUtil.add(triggers, door, root, node_name)
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = Vector2(tile_px, tile_px)
	shape.shape = rect
	door.add_child(shape)
	return door

# ---------------------------------------------------------------- imported maps (T12.49)

## The transform bits of the catalog's cells (adapters/maps.py): flip x, flip y, transpose.
const BIT_FLIP_H := 1
const BIT_FLIP_V := 2
const BIT_TRANSPOSE := 4

## The alternative-tile id of a cell with the catalog's transform bits. Godot keeps the flips of a
## cell in the bits of its alternative tile, so the tile set needs no extra tiles for them.
static func transform_alt(bits: int) -> int:
	var alt := 0
	if bits & BIT_FLIP_H:
		alt |= TileSetAtlasSource.TRANSFORM_FLIP_H
	if bits & BIT_FLIP_V:
		alt |= TileSetAtlasSource.TRANSFORM_FLIP_V
	if bits & BIT_TRANSPOSE:
		alt |= TileSetAtlasSource.TRANSFORM_TRANSPOSE
	return alt

## Paints the run-length encoded cells of a tile layer (`[count, source_id, column, row, bits]`,
## source id -1 for an empty cell, row by row on a map `width` cells wide). Returns the number of
## cells whose tile does not exist in the tile set; they stay empty.
static func paint_runs(layer: TileMapLayer, tile_set: TileSet, width: int, runs: Array) -> int:
	var missing := 0
	var index := 0
	for item: Variant in runs:
		var run: Array = item
		var count := JsonUtil.to_int(run[0])
		var source_id := JsonUtil.to_int(run[1])
		if source_id >= 0 and width > 0:
			var coords := Vector2i(JsonUtil.to_int(run[2]), JsonUtil.to_int(run[3]))
			var source: TileSetAtlasSource = null
			if tile_set.has_source(source_id):
				source = tile_set.get_source(source_id) as TileSetAtlasSource
			if source == null or not source.has_tile(coords):
				missing += count
			else:
				var alt := transform_alt(JsonUtil.to_int(run[4]))
				for k in count:
					var at := index + k
					@warning_ignore("integer_division")
					var row := at / width
					layer.set_cell(Vector2i(at % width, row), source_id, coords, alt)
		index += count
	return missing

## The values of an IntGrid layer's `values` list that are solid.
static func solid_values(values: Array) -> Array[int]:
	var out: Array[int] = []
	for item: Variant in values:
		var v: Dictionary = item
		if JsonUtil.to_bool(v.get("solid", false)):
			out.append(JsonUtil.to_int(v["value"]))
	return out

## The cells of an IntGrid layer whose value is in `solid`, as few rectangles as a simple merge
## finds: runs along each row, joined with an identical run on the row above.
static func solid_rects(width: int, runs: Array, solid: Array[int]) -> Array[Rect2i]:
	var cells: Array[int] = []
	for item: Variant in runs:
		var run: Array = item
		var value := JsonUtil.to_int(run[1])
		for k in JsonUtil.to_int(run[0]):
			cells.append(value)
	var done: Array[Rect2i] = []
	var open := {}  # "x:w" -> the rectangle that ends on the row above
	var rows := 0
	if width > 0:
		@warning_ignore("integer_division")
		rows = cells.size() / width
	for y in rows:
		var next_open := {}
		var x := 0
		while x < width:
			if not solid.has(cells[y * width + x]):
				x += 1
				continue
			var start := x
			while x < width and solid.has(cells[y * width + x]):
				x += 1
			var key := "%d:%d" % [start, x - start]
			if open.has(key):
				var rect: Rect2i = open[key]
				rect.size.y += 1
				next_open[key] = rect
				open.erase(key)
			else:
				next_open[key] = Rect2i(start, y, x - start, 1)
		for key: String in open.keys():
			done.append(open[key])
		open = next_open
	for key: String in open.keys():
		done.append(open[key])
	done.sort_custom(func(a: Rect2i, b: Rect2i) -> bool: return a.position.y < b.position.y or (a.position.y == b.position.y and a.position.x < b.position.x))
	return done

## A static body with one invisible rectangle per solid area (layer 1, the world), the way the
## border of a map without a wall tile blocks. Returns null for no rectangles.
static func add_solid_body(root: Node2D, body_name: String, rects: Array[Rect2i], tile_px: int) -> StaticBody2D:
	if rects.is_empty():
		return null
	var body := StaticBody2D.new()
	body.name = body_name
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)
	root.add_child(body)
	body.owner = root
	for r in rects:
		var shape := CollisionShape2D.new()
		shape.name = "Solid_%d_%d" % [r.position.x, r.position.y]
		var rect := RectangleShape2D.new()
		rect.size = Vector2(r.size) * tile_px
		shape.shape = rect
		shape.position = (Vector2(r.position) + Vector2(r.size) / 2.0) * tile_px
		body.add_child(shape)
		shape.owner = root
	return body

## The cell nearest to the middle of the map that is not solid; Vector2i(-1, -1) when all are.
static func free_cell_near_centre(size: Vector2i, solid_cells: Dictionary) -> Vector2i:
	var centre := Vector2i(size.x >> 1, size.y >> 1)
	var best := Vector2i(-1, -1)
	var best_distance := 1 << 30
	for y in size.y:
		for x in size.x:
			var cell := Vector2i(x, y)
			if solid_cells.has(cell):
				continue
			var d := absi(x - centre.x) + absi(y - centre.y)
			if d < best_distance:
				best_distance = d
				best = cell
	return best

## {source_id, coords} of the first tile of the `nth` (0-based) tile sheet that has `role`, or {}.
static func nth_tile_with_role(ctx: BuildContext, def: Dictionary, tile_set: TileSet, role: String, nth: int) -> Dictionary:
	var seen := 0
	for s in MapUtil._sorted_sources(def):
		var asset_id: String = s["asset"]
		var asset: Dictionary = ctx.catalog.asset(asset_id)
		if asset.is_empty() or ctx.catalog.effective(asset).get("role", "") != role:
			continue
		var tile := MapUtil.first_tile(tile_set, JsonUtil.to_int(s["source_id"]))
		if tile.is_empty():
			continue
		if seen == nth:
			return tile
		seen += 1
	return {}

## Roads on `layer` for every cell of a plan's path.
static func paint_path(layer: TileMapLayer, path: Array[Vector2i], road: Dictionary) -> void:
	if road.is_empty():
		return
	for cell in path:
		MapUtil.put(layer, cell, road)
