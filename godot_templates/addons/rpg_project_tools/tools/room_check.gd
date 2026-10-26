@tool
extends RefCounted
# Parts of this file are ported from MDSRoomCheck of the Metroidvania Developer System
# (https://github.com/arunsrajan/MetroidvaniaDeveloperSystem), under this license:
#
# MIT License
#
# Copyright (c) 2026 Arun Soundararajan
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

## Physics-level checks of a side-view room as it is painted (VAL-033): whether the player gets
## through it. The world plan says an exit is there; these catch the rock painted over it.
## Ported from the Metroidvania Developer System's MDSRoomCheck (MIT, Arun Soundararajan; see
## THIRD_PARTY_NOTICES.md), for rpggen's rooms: exits on the room's edges, ladders, the platform
## actor's jump.
##
## The room's collision (its tile layers and static bodies) is copied into a physics proxy under a
## host node in the tree, and then:
## - passage: every exit is open at its edge of the room, wide enough for the player;
## - landing, headroom: every one-way platform can be landed on at its top, with room above it;
## - buried, floating: what stands (a save station, an NPC, a sign, a chest) has ground under its
##   feet and is not inside rock; a pickup is not inside rock;
## - climb: every exit up out of the room is reached from where the player comes in, by jumping
##   and climbing ladders, holding every ability (which ability a way needs is the plan's
##   business, VAL-027 and the lock-and-key planner).
##
## [codeblock]
## var check := RoomCheck.new()
## var issues := check.check_room(room_instance, host)   # host: a node in the tree
## [/codeblock]

const JsonIo := preload("json_io.gd")

const GROUND := 1
const PLATFORM := 2
const DT := 1.0 / 60.0
## The most jumps tried in one room.
const MAX_JUMPS := 500
## Exits are tested this many tiles either side of their opening along the room's edge.
const EXIT_WINDOW_TILES := 4.0
const KINDS := {"passage": "the exit is blocked", "headroom": "no headroom", "landing": "a platform can't be landed on", "floating": "floating", "buried": "buried", "climb": "an exit is out of reach"}
const ROOM_SUFFIX := "/archetypes/metroidvania/room.gd"
const EXIT_SUFFIX := "/archetypes/metroidvania/room_exit.gd"
const PLAYER_SUFFIX := "/archetypes/metroidvania/platform_player.gd"
## What stands on the floor, and what only must not be inside rock.
const STANDING_SUFFIXES: Array[String] = ["/archetypes/metroidvania/save_station.gd", "/archetypes/metroidvania/side_npc.gd", "/world/sign.gd", "/world/chest.gd"]
const PICKUP_SUFFIXES: Array[String] = ["/archetypes/metroidvania/ability_pickup.gd", "/archetypes/metroidvania/item_pickup.gd"]
## The platform actor's defaults (RpgPlatformActor), at 16 px tiles.
const RUN_SPEED := 110.0
const JUMP_TILES := 3.25
const HIGH_JUMP_TILES := 1.25
const TIME_TO_PEAK := 0.38
const FALL_MUL := 1.6
const DASH_S := 0.18
const DASH_SPEED_MUL := 3.0
const MAX_FALL := 360.0
const INWARD := {"W": Vector2.RIGHT, "E": Vector2.LEFT, "N": Vector2.DOWN, "S": Vector2.UP}

var tile := 16.0
var player_size := Vector2(12, 24)
## Up at take-off, px/s, for a jump as high as a double jump with the high jump goes.
var jump_velocity := 0.0
var gravity := 0.0
var fall_mul := FALL_MUL
var run_speed := RUN_SPEED
var max_fall := MAX_FALL
var head_clearance := 24.0

## The room's rectangle (scene-local).
var room_rect := Rect2()
## Ways in and out: [{name, pos (scene-local, the middle of the opening on the edge), edge}].
var passages: Array = []
## Where players arrive (scene-local): the room's spawn points.
var arrivals: Array[Vector2] = []
## Found by run(): [{kind, message, pos, node}].
var issues: Array = []
## Floors found by run(): [{points: PackedVector2Array, reachable: bool}].
var surfaces: Array = []
## One-way platforms: [{name, outline (scene-local)}].
var platforms: Array = []
## [{name, feet, stands}]: `stands` false for a pickup, which may hang in the air.
var standing: Array = []
## Ladders: [{rect (scene-local), reachable}], one a column of ladder tiles.
var ladders: Array = []

var proxy: Node2D
var _ground: StaticBody2D
var _platforms: StaticBody2D
var _probe: CharacterBody2D
var _space: PhysicsDirectSpaceState2D
var _jumps := 0

static func _script_ends_with(node: Node, suffix: String) -> bool:
	var script: Script = node.get_script()
	return script != null and script.resource_path.ends_with(suffix)

static func is_room(node: Node) -> bool:
	return node != null and _script_ends_with(node, ROOM_SUFFIX)

## Every check of one room scene instance (in the tree or not). `host` must be in the tree: the
## physics copy lives in a SubViewport under it (a physics space of its own, so nothing of the
## editor's or the game's world is in the way) while the checks run, and is freed after.
func check_room(root: Node, host: Node) -> Array:
	read_room(root)
	var space := SubViewport.new()
	space.name = "RpgRoomCheckSpace"
	space.disable_3d = true
	space.size = Vector2i(2, 2)
	space.render_target_update_mode = SubViewport.UPDATE_DISABLED
	host.add_child(space)
	build_from_scene(root, space)
	var out := run()
	free_proxy()
	host.remove_child(space)
	space.free()
	return out

## The room's size, exits and arrivals, and the player's size and jump: the room's own player
## when it has one (the first room), else the platform actor's defaults at the room's tile size.
func read_room(root: Node) -> void:
	tile = maxf(1.0, JsonIo.to_float(root.get("tile_size"), 16.0))
	var size: Variant = root.get("room_size")
	var cells: Vector2i = size if size is Vector2i else Vector2i.ZERO
	room_rect = Rect2(Vector2.ZERO, Vector2(cells) * tile)
	var scale := tile / 16.0
	var jump_tiles := JUMP_TILES
	var peak := TIME_TO_PEAK
	run_speed = RUN_SPEED * scale
	fall_mul = FALL_MUL
	max_fall = MAX_FALL * scale
	player_size = Vector2(tile * 0.75, tile * 1.5)
	passages.clear()
	arrivals.clear()
	var nodes: Array[Node] = []
	_walk(root, nodes)
	for node in nodes:
		if _script_ends_with(node, PLAYER_SUFFIX):
			jump_tiles = JsonIo.to_float(node.get("jump_height_tiles"))
			peak = maxf(0.01, JsonIo.to_float(node.get("jump_time_to_peak")))
			run_speed = JsonIo.to_float(node.get("run_speed")) * scale
			fall_mul = JsonIo.to_float(node.get("fall_gravity_mul"))
			max_fall = JsonIo.to_float(node.get("max_fall_speed")) * scale
			for child in node.get_children():
				if child is CollisionShape2D and (child as CollisionShape2D).shape is RectangleShape2D:
					player_size = ((child as CollisionShape2D).shape as RectangleShape2D).size
					break
		elif _script_ends_with(node, EXIT_SUFFIX):
			var edge := str(node.get("edge"))
			var pos := local_transform(node, root).origin
			if edge == "E" or edge == "W":
				pos.y -= 1.5 * tile  # an exit in a wall stands on the floor of its opening
			passages.append({"name": String(root.get_path_to(node)), "pos": pos, "edge": edge})
		elif node is Marker2D and node.get_parent() != null and node.get_parent().name == &"SpawnPoints":
			arrivals.append(local_transform(node, root).origin)
	# every ability: the high jump on each jump, and the double jump's two reach as high as one
	# jump of twice the height
	gravity = 2.0 * jump_tiles * tile / (peak * peak)
	var height := 2.0 * (jump_tiles + HIGH_JUMP_TILES) * tile
	jump_velocity = sqrt(2.0 * gravity * height)
	head_clearance = player_size.y + 2.0

## How high a jump reaches: v² / 2g.
func max_jump_height() -> float:
	return jump_velocity * jump_velocity / (2.0 * maxf(gravity, 1.0))

static func _walk(node: Node, out: Array[Node]) -> void:
	out.append(node)
	for child in node.get_children():
		_walk(child, out)

## The transform of `node` in the coordinates of `root` (an ancestor), in the tree or not.
static func local_transform(node: Node, root: Node) -> Transform2D:
	var xform := Transform2D.IDENTITY
	var at := node
	while at != null and at != root:
		if at is Node2D:
			xform = (at as Node2D).transform * xform
		at = at.get_parent()
	return xform

# ---------------------------------------------------------------- the physics copy

## Builds the physics copy of a room scene instance under `host`, which must be in the tree.
func build_from_scene(root: Node, host: Node) -> void:
	_begin()
	_add_node(root, root)
	_collect_standing(root)
	_finish(host)

func free_proxy() -> void:
	if is_instance_valid(proxy):
		if proxy.get_parent():
			proxy.get_parent().remove_child(proxy)
		proxy.free()
	proxy = null
	_space = null

func _begin() -> void:
	free_proxy()
	platforms.clear()
	standing.clear()
	ladders.clear()
	proxy = Node2D.new()
	proxy.name = "RpgRoomCheckProxy"
	_ground = StaticBody2D.new()
	_ground.collision_layer = GROUND
	_ground.collision_mask = 0
	proxy.add_child(_ground)
	_platforms = StaticBody2D.new()
	_platforms.collision_layer = PLATFORM
	_platforms.collision_mask = 0
	proxy.add_child(_platforms)

func _finish(host: Node) -> void:
	_probe = CharacterBody2D.new()
	_probe.collision_layer = 0
	_probe.collision_mask = GROUND | PLATFORM
	var cs := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = player_size
	cs.shape = rect
	_probe.add_child(cs)
	_probe.position = Vector2(-1e6, -1e6)
	proxy.add_child(_probe)
	host.add_child(proxy)
	# a motion test makes the physics server take in the new shapes now, even where it is not
	# stepping (the editor, a validation run's first frame)
	_probe.test_move(_probe.global_transform, Vector2(0, 1))
	_space = proxy.get_world_2d().direct_space_state

func _add_node(node: Node, root: Node) -> void:
	if node is TileMapLayer:
		_add_tile_layer(node as TileMapLayer, local_transform(node, root))
		return
	# a body with a script is a thing of the room (a gate, a breakable wall): its own checks
	# are its own; plain static bodies are terrain
	if node is StaticBody2D and node.get_script() == null and node.process_mode != Node.PROCESS_MODE_DISABLED:
		for c in node.get_children():
			if c is CollisionShape2D or c is CollisionPolygon2D:
				_add_shape(c as Node2D, local_transform(c, root), String(node.name))
	for c in node.get_children():
		_add_node(c, root)

static func _rect_polygon(r: Rect2) -> PackedVector2Array:
	return PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])

static func _bounds(poly: PackedVector2Array) -> Rect2:
	if poly.is_empty():
		return Rect2()
	var r := Rect2(poly[0], Vector2.ZERO)
	for p in poly:
		r = r.expand(p)
	return r

func _add_polygon(poly: PackedVector2Array, one_way: bool, solids := true) -> void:
	var cp := CollisionPolygon2D.new()
	cp.build_mode = CollisionPolygon2D.BUILD_SOLIDS if solids else CollisionPolygon2D.BUILD_SEGMENTS
	cp.polygon = poly
	cp.one_way_collision = one_way
	(_platforms if one_way else _ground).add_child(cp)

## Full cells merged into rectangles, row by row: runs along x, then runs of equal runs down.
static func _cells_to_rects(cells: Dictionary, cell: Vector2, origin: Vector2) -> Array[Rect2]:
	var rows: Dictionary = {}  # y -> sorted xs
	for c: Vector2i in cells:
		if not rows.has(c.y):
			rows[c.y] = []
		var row: Array = rows[c.y]
		row.append(c.x)
	var open: Dictionary = {}  # Vector2i(x0, x1) -> Rect2i of cells
	var out: Array[Rect2] = []
	var ys: Array = rows.keys()
	ys.sort()
	var last_y := -2147483648
	for y: int in ys:
		var xs: Array = rows[y]
		xs.sort()
		var runs: Array[Vector2i] = []
		var start: int = xs[0]
		var prev: int = xs[0]
		for i in range(1, xs.size()):
			if xs[i] != prev + 1:
				runs.append(Vector2i(start, prev))
				start = xs[i]
			prev = xs[i]
		runs.append(Vector2i(start, prev))
		var next: Dictionary = {}
		for run in runs:
			if open.has(run) and y == last_y + 1:
				var r: Rect2i = open[run]
				r.size.y += 1
				next[run] = r
				open.erase(run)
			else:
				next[run] = Rect2i(run.x, y, run.y - run.x + 1, 1)
		for r: Rect2i in open.values():
			out.append(Rect2(origin + Vector2(r.position) * cell, Vector2(r.size) * cell))
		open = next
		last_y = y
	for r: Rect2i in open.values():
		out.append(Rect2(origin + Vector2(r.position) * cell, Vector2(r.size) * cell))
	return out

func _add_tile_layer(layer: TileMapLayer, xform: Transform2D) -> void:
	if not layer.enabled or layer.tile_set == null:
		return
	var ts := layer.tile_set
	var half := Vector2(ts.tile_size) / 2.0
	var full: Dictionary = {}
	var one_way_full: Dictionary = {}
	var ladder_cells: Dictionary = {}
	var one_way_cells: Dictionary = {}  # cell -> the bounds of its one-way polygons
	var has_ladders := ts.get_custom_data_layer_by_name("ladder") >= 0
	var has_breakable := ts.get_custom_data_layer_by_name("breakable") >= 0
	for cell in layer.get_used_cells():
		var td := layer.get_cell_tile_data(cell)
		if td == null:
			continue  # a tile the tileset no longer has
		var center := layer.map_to_local(cell)
		if has_ladders and JsonIo.to_bool(td.get_custom_data("ladder")):
			ladder_cells[cell] = true
		# a block that breaks is no rock to a player who holds every ability
		if not layer.collision_enabled or (has_breakable and JsonIo.to_bool(td.get_custom_data("breakable"))):
			continue
		for pl in ts.get_physics_layers_count():
			for pi in td.get_collision_polygons_count(pl):
				var pts := td.get_collision_polygon_points(pl, pi)
				var one_way := td.is_collision_polygon_one_way(pl, pi)
				if pts.size() == 4 and _bounds(pts).is_equal_approx(Rect2(-half, half * 2.0)) and ts.tile_shape == TileSet.TILE_SHAPE_SQUARE:
					(one_way_full if one_way else full)[cell] = true
				elif pts.size() >= 3:
					var poly := PackedVector2Array()
					for p in pts:
						poly.append(xform * (center + p))
					_add_polygon(poly, one_way)
					if one_way:
						var box := _bounds(poly)
						var had: Rect2 = one_way_cells.get(cell, box)
						one_way_cells[cell] = had.merge(box)
	var origin := layer.map_to_local(Vector2i.ZERO) - half
	for which in 2:
		var cells: Dictionary = full if which == 0 else one_way_full
		for r in _cells_to_rects(cells, Vector2(ts.tile_size), origin):
			var poly := xform * _rect_polygon(r)
			_add_polygon(poly, which == 1)
			if which == 1:
				platforms.append({"name": "%s tiles" % layer.name, "outline": poly})
	# a plank is a row of one-way tiles side by side: one platform, checked once
	var planks: Dictionary = {}
	for r in _cells_to_rects(one_way_cells, Vector2.ONE, Vector2.ZERO):
		for y in int(r.size.y):
			planks[Vector2i(int(r.position.x), int(r.position.y) + y)] = int(r.size.x)
	for start: Vector2i in planks:
		var box: Rect2 = one_way_cells[start]
		for x in range(1, JsonIo.to_int(planks[start])):
			var next_box: Rect2 = one_way_cells[start + Vector2i(x, 0)]
			box = box.merge(next_box)
		platforms.append({"name": "the plank of %s at %s" % [layer.name, start], "outline": _rect_polygon(box)})
	# a ladder is a column of ladder tiles: one entry each, its rectangle in the room
	for r in _cells_to_rects(ladder_cells, Vector2(ts.tile_size), origin):
		for x in roundi(r.size.x / ts.tile_size.x):
			var column := Rect2(r.position + Vector2(x * ts.tile_size.x, 0.0), Vector2(ts.tile_size.x, r.size.y))
			ladders.append({"rect": _bounds(xform * _rect_polygon(column)), "reachable": false})

func _add_shape(c: Node2D, xform: Transform2D, body_name: String) -> void:
	if c is CollisionShape2D:
		var cs := c as CollisionShape2D
		if cs.disabled or cs.shape == null:
			return
		var copy := CollisionShape2D.new()
		copy.shape = cs.shape
		copy.transform = xform
		copy.one_way_collision = cs.one_way_collision
		(_platforms if cs.one_way_collision else _ground).add_child(copy)
		if cs.one_way_collision:
			platforms.append({"name": body_name, "outline": xform * _rect_polygon(cs.shape.get_rect())})
	else:
		var cp := c as CollisionPolygon2D
		if cp.disabled or cp.polygon.size() < 3:
			return
		var poly := xform * cp.polygon
		_add_polygon(poly, cp.one_way_collision, cp.build_mode == CollisionPolygon2D.BUILD_SOLIDS)
		if cp.one_way_collision:
			platforms.append({"name": body_name, "outline": poly})

func _collect_standing(root: Node) -> void:
	var nodes: Array[Node] = []
	_walk(root, nodes)
	for node in nodes:
		var stands := false
		var counts := false
		for suffix in STANDING_SUFFIXES:
			if _script_ends_with(node, suffix):
				stands = true
				counts = true
		for suffix in PICKUP_SUFFIXES:
			if _script_ends_with(node, suffix):
				counts = true
		if counts:
			standing.append({"name": String(root.get_path_to(node)), "feet": local_transform(node, root).origin, "stands": stands})

# ---------------------------------------------------------------- queries

func solid_at(p: Vector2, mask := GROUND) -> bool:
	var q := PhysicsPointQueryParameters2D.new()
	q.position = p
	q.collision_mask = mask
	return not _space.intersect_point(q, 1).is_empty()

func ray(a: Vector2, b: Vector2, mask := GROUND | PLATFORM) -> Dictionary:
	var q := PhysicsRayQueryParameters2D.create(a, b, mask)
	return _space.intersect_ray(q)

func box_free(center: Vector2, size: Vector2, mask := GROUND) -> bool:
	var q := PhysicsShapeQueryParameters2D.new()
	var r := RectangleShape2D.new()
	r.size = size
	q.shape = r
	q.transform = Transform2D(0.0, center)
	q.collision_mask = mask
	return _space.intersect_shape(q, 1).is_empty()

## Where a ray hit.
static func _at(hit: Dictionary) -> Vector2:
	var at: Vector2 = hit["position"]
	return at

## The first point of a surface.
static func _first(s: Dictionary) -> Vector2:
	var pts: PackedVector2Array = s["points"]
	return pts[0]

func in_room(p: Vector2) -> bool:
	return room_rect.size == Vector2.ZERO or room_rect.grow(1.0).has_point(p)

# ---------------------------------------------------------------- checks

## Runs every check on the built proxy.
func run() -> Array:
	issues.clear()
	surfaces.clear()
	_jumps = 0
	if _space == null:
		return issues
	for p: Dictionary in passages:
		_check_passage(p)
	for pl: Dictionary in platforms:
		_check_platform(pl)
	for s: Dictionary in standing:
		_check_standing(s)
	if room_rect.size != Vector2.ZERO:
		_reachability()
	return issues

func _issue(kind: String, message: String, pos: Vector2, node: String = "") -> void:
	issues.append({"kind": kind, "message": message, "pos": pos, "node": node})

func _check_passage(p: Dictionary) -> void:
	var pos: Vector2 = p["pos"]
	var edge: String = p["edge"]
	if not INWARD.has(edge):
		return
	var along_x := edge == "N" or edge == "S"
	var inward: Vector2 = INWARD[edge]
	var window := EXIT_WINDOW_TILES * tile
	var lo := (pos.x if along_x else pos.y) - window
	var hi := (pos.x if along_x else pos.y) + window
	lo = maxf(lo, room_rect.position.x if along_x else room_rect.position.y)
	hi = minf(hi, room_rect.end.x if along_x else room_rect.end.y)
	var need := (player_size.x if along_x else player_size.y) + 2.0
	var best := 0.0
	var run_len := 0.0
	var t := lo + 2.0
	while t <= hi - 2.0:
		var probe := (Vector2(t, pos.y) if along_x else Vector2(pos.x, t)) + inward * minf(8.0, tile * 0.5)
		if solid_at(probe):
			run_len = 0.0
		else:
			run_len += 2.0
			best = maxf(best, run_len)
		t += 2.0
	if best < need:
		_issue("passage", "rock closes its opening: the widest gap along the edge near it is %d px, the player needs %d" % [int(best), int(need)], pos, JsonIo.to_str(p["name"]))

## The top of `outline` at `x` (going down), or INF.
static func _top_at(outline: PackedVector2Array, x: float) -> float:
	var b := _bounds(outline)
	var y := b.position.y - 2.0 + 0.137
	var run := 0
	while y < b.end.y + 1.0:
		run = run + 1 if Geometry2D.is_point_in_polygon(Vector2(x + 0.071, y), outline) else 0
		if run == 4:
			return y - 1.5
		y += 0.5
	return INF

func _check_platform(pl: Dictionary) -> void:
	var outline: PackedVector2Array = pl["outline"]
	var b := _bounds(outline)
	var x := b.get_center().x
	var top := _top_at(outline, x)
	if top == INF:
		return
	var hit := ray(Vector2(x, top - tile * 2.0), Vector2(x, top + tile * 2.0))
	if hit.is_empty() or absf(_at(hit).y - top) > 3.0:
		_issue("landing", "the platform %s can't be landed on at its top: something covers it" % pl["name"], Vector2(x, top))
		return
	var blocked := 0
	var center_blocked := false
	var least := head_clearance
	for k in 3:
		var xx: float = [x, lerpf(b.position.x, b.end.x, 0.25), lerpf(b.position.x, b.end.x, 0.75)][k]
		var t := _top_at(outline, xx)
		if t == INF:
			continue
		var up := ray(Vector2(xx, t - 3.0), Vector2(xx, t - head_clearance), GROUND)
		if not up.is_empty():
			blocked += 1
			center_blocked = center_blocked or k == 0
			least = minf(least, t - _at(up).y)
	if center_blocked or blocked >= 2:
		_issue("headroom", "the platform %s has %d px of room above it, the player needs %d" % [pl["name"], int(least), int(head_clearance)], Vector2(x, top))

func _check_standing(s: Dictionary) -> void:
	var f: Vector2 = s["feet"]
	if solid_at(f + Vector2(0, -minf(4.0, tile * 0.25))) and solid_at(f + Vector2(0, -player_size.y * 0.5)):
		_issue("buried", "it is inside rock", f, JsonIo.to_str(s["name"]))
		return
	if JsonIo.to_bool(s["stands"]) and ray(f + Vector2(0, -tile), f + Vector2(0, tile * 2.0)).is_empty():
		_issue("floating", "it floats: no ground within %d px under it" % int(tile * 2.0), f, JsonIo.to_str(s["name"]))

# ---------------------------------------------------------------- reachability and climbs

## Floors in a column: where solid starts with room for the player above, going down.
func _floors_in_column(x: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	var b := room_rect
	var y := b.position.y + 2.0
	var was_solid := solid_at(Vector2(x + 0.31, y), GROUND | PLATFORM)
	while y < b.end.y + tile * 3.0:
		y += 2.0
		var solid := solid_at(Vector2(x + 0.31, y), GROUND | PLATFORM)
		if solid and not was_solid:
			var hit := ray(Vector2(x + 0.31, y - 3.0), Vector2(x + 0.31, y + 1.0))
			var top: float = _at(hit).y if not hit.is_empty() else y
			if in_room(Vector2(x, top - 4.0)) and box_free(Vector2(x, top - player_size.y / 2.0 - 1.5), Vector2(player_size.x * 0.6, player_size.y - 2.0)):
				out.append(top)
		was_solid = solid
	return out

## Groups column floors into surfaces (runs of floor the player can walk along).
func _build_surfaces() -> void:
	var b := room_rect
	var step := maxf(4.0, tile * 0.5)
	var open: Array = []  # surfaces of the previous column
	var x := b.position.x + maxf(4.0, player_size.x * 0.5)
	while x <= b.end.x - maxf(4.0, player_size.x * 0.5):
		var next: Array = []
		for y in _floors_in_column(x):
			var joined: Dictionary = {}
			for s: Dictionary in open:
				var pts_open: PackedVector2Array = s["points"]
				if absf(pts_open[pts_open.size() - 1].y - y) <= tile * 0.75:
					joined = s
					break
			if joined.is_empty():
				joined = {"points": PackedVector2Array(), "reachable": false}
				surfaces.append(joined)
			else:
				open.erase(joined)
			var pts: PackedVector2Array = joined["points"]
			pts.append(Vector2(x, y))
			joined["points"] = pts
			next.append(joined)
		open = next
		x += step

func _surface_near(p: Vector2) -> Dictionary:
	var best: Dictionary = {}
	var best_d := tile * 2.5
	for s: Dictionary in surfaces:
		for q: Vector2 in s["points"]:
			var d: float = q.distance_to(p)
			if d < best_d:
				best_d = d
				best = s
	return best

## Where the player stands after coming in at `at`: straight down from it.
func _arrival(at: Vector2) -> Dictionary:
	var hit := ray(at + Vector2(0, -2.0), at + Vector2(0, room_rect.size.y + tile * 10.0))
	return _surface_near(_at(hit)) if not hit.is_empty() else {}

## True when `s` has a point standing at the ladder `l` (on its column, between its top and its
## foot, or within a jump below it).
func _touches(s: Dictionary, l: Dictionary, below: float) -> bool:
	var r: Rect2 = l["rect"]
	for q: Vector2 in s["points"]:
		if q.x >= r.position.x - tile * 0.5 and q.x <= r.end.x + tile * 0.5 and q.y >= r.position.y - tile and q.y <= r.end.y + below:
			return true
	return false

func _mark(s: Dictionary, queue: Array) -> void:
	if not JsonIo.to_bool(s["reachable"]):
		s["reachable"] = true
		queue.append(s)

func _reachability() -> void:
	_build_surfaces()
	if surfaces.is_empty():
		return
	var queue: Array = []
	for at in arrivals:
		var s := _arrival(at)
		if not s.is_empty():
			_mark(s, queue)
	if queue.is_empty():
		var lowest: Dictionary = surfaces[0]
		for s: Dictionary in surfaces:
			if _first(s).y > _first(lowest).y:
				lowest = s
		_mark(lowest, queue)
	var h := max_jump_height()
	while not queue.is_empty() and _jumps < MAX_JUMPS:
		var s: Dictionary = queue.pop_front()
		# a ladder the player stands at, or jumps up to, takes it to every floor along it
		for l: Dictionary in ladders:
			if not JsonIo.to_bool(l["reachable"]) and _touches(s, l, h):
				l["reachable"] = true
				for t: Dictionary in surfaces:
					if _touches(t, l, tile):
						_mark(t, queue)
		for t: Dictionary in surfaces:
			if JsonIo.to_bool(t["reachable"]) or not _may_reach(s, t, h):
				continue
			if _jump_between(s, t):
				_mark(t, queue)
	# exits up out of the room
	for p: Dictionary in passages:
		if p["edge"] != "N":
			continue
		var pos: Vector2 = p["pos"]
		var out := false
		for l: Dictionary in ladders:
			var r: Rect2 = l["rect"]
			if JsonIo.to_bool(l["reachable"]) and r.position.y <= pos.y + tile and pos.x >= r.position.x - tile * 0.5 and pos.x <= r.end.x + tile * 0.5:
				out = true
		for s: Dictionary in surfaces:
			if out:
				break
			if JsonIo.to_bool(s["reachable"]) and _may_exit(s, p, h) and _jump_out(s, p):
				out = true
		if not out:
			var highest := INF
			for s: Dictionary in surfaces:
				if JsonIo.to_bool(s["reachable"]):
					for q: Vector2 in s["points"]:
						highest = minf(highest, q.y)
			_issue("climb", "no ladder reaches it and no jump does: the highest floor the player gets to is %d px below it, a jump with every ability rises %d px" % [int(highest - pos.y) if highest != INF else 0, int(h)], pos, JsonIo.to_str(p["name"]))

func _span(s: Dictionary) -> Vector2:
	var pts: PackedVector2Array = s["points"]
	return Vector2(pts[0].x, pts[pts.size() - 1].x)

func _top(s: Dictionary) -> float:
	var y := INF
	for q: Vector2 in s["points"]:
		y = minf(y, q.y)
	return y

## Seconds in the air of a jump that lands `rise` px higher (negative: lower).
func _air_time(rise: float) -> float:
	var up := jump_velocity / gravity
	var fall := sqrt(maxf(0.0, 2.0 * (max_jump_height() - rise) / (gravity * fall_mul)))
	return up + fall

## The run (with a dash) of `seconds` in the air.
func _run_in(seconds: float) -> float:
	return run_speed * seconds + run_speed * (DASH_SPEED_MUL - 1.0) * minf(seconds, DASH_S)

## Rough reach of a jump from `s` to `t`: not too high, not too far.
func _may_reach(s: Dictionary, t: Dictionary, h: float) -> bool:
	var rise := _top(s) - _top(t)  # > 0: t is higher
	if rise > h - 2.0:
		return false
	var a := _span(s)
	var b := _span(t)
	var gap := maxf(0.0, maxf(b.x - a.y, a.x - b.y))
	return gap <= _run_in(_air_time(rise)) + player_size.x

func _may_exit(s: Dictionary, p: Dictionary, h: float) -> bool:
	var pos: Vector2 = p["pos"]
	var rise: float = _top(s) - pos.y
	if rise > h + player_size.y * 0.5:
		return false
	var a := _span(s)
	var gap := maxf(0.0, maxf(pos.x - a.y, a.x - pos.x))
	return gap <= _run_in(2.0 * jump_velocity / gravity) + player_size.x

## The point of `s` nearest x.
func _point_toward(s: Dictionary, x: float) -> Vector2:
	var pts: PackedVector2Array = s["points"]
	var best: Vector2 = pts[0]
	for q in pts:
		if absf(q.x - x) < absf(best.x - x):
			best = q
	return best

func _jump_between(s: Dictionary, t: Dictionary) -> bool:
	var tb := _span(t)
	var from_mid := (_span(s).x + _span(s).y) / 2.0
	for tries in 2:
		var tx := clampf(from_mid, tb.x + tile * 0.5, tb.y - tile * 0.5) if tb.y - tb.x > tile else (tb.x + tb.y) / 2.0
		var from := _point_toward(s, tx) if tries == 0 else _point_toward(s, from_mid)
		var r := simulate_jump(from, tx)
		if JsonIo.to_bool(r["landed"]):
			var at: Vector2 = r["pos"]
			if at.x >= tb.x - tile * 0.75 and at.x <= tb.y + tile * 0.75 and absf(at.y - _point_toward(t, at.x).y) <= tile * 0.9:
				return true
	return false

func _jump_out(s: Dictionary, p: Dictionary) -> bool:
	var pos: Vector2 = p["pos"]
	return JsonIo.to_bool(simulate_jump(_point_toward(s, pos.x), pos.x, pos.y)["exited"])

## Jumps a player-sized body from a floor point toward `target_x`, steering in the air (a dash
## at the start of it). Returns {landed, exited (passed above `exit_y`), pos (feet)}.
func simulate_jump(from: Vector2, target_x: float, exit_y := -INF) -> Dictionary:
	_jumps += 1
	var half := player_size.y / 2.0
	_probe.position = from + Vector2(0, -half - 1.0)
	var vel := Vector2(0, -jump_velocity)
	var floor_y := room_rect.end.y + tile * 25.0
	for i in 300:
		var cap := run_speed * (DASH_SPEED_MUL if i * DT < DASH_S else 1.0)
		var here := _probe.position
		vel.x = clampf((target_x - here.x) * 6.0, -cap, cap)
		vel.y = minf(vel.y + gravity * (fall_mul if vel.y > 0.0 else 1.0) * DT, maxf(max_fall, jump_velocity))
		var motion := vel * DT
		for k in 3:
			var col := _probe.move_and_collide(motion)
			if col == null:
				break
			var n := col.get_normal()
			if n.y < -0.65 and vel.y >= 0.0 and i > 2:
				return {"landed": true, "exited": false, "pos": _probe.position + Vector2(0, half)}
			if n.y > 0.65:
				vel.y = maxf(vel.y, 0.0)
			motion = col.get_remainder().slide(n)
			vel = vel.slide(n)
		here = _probe.position
		if here.y < exit_y:
			return {"landed": false, "exited": true, "pos": here + Vector2(0, half)}
		if here.y + half > floor_y:
			break
	return {"landed": false, "exited": false, "pos": _probe.position + Vector2(0, half)}
