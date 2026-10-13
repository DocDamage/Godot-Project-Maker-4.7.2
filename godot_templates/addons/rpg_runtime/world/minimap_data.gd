class_name RpgMinimapData
extends RefCounted
## The minimap of a map (T12.64): one pixel per cell, the average colour of the cell's tile, made
## by the builder's minimap recipe from the map's TileMapLayers and saved as an ImageTexture in
## res://generated/minimaps/<key>.tres. The texture's metadata says where it sits:
## "origin_cell" (Vector2i, the map cell of pixel 0,0) and "tile_size" (Vector2i). The minimap
## of an isometric map (T17.14) is the plan from above too, a pixel per cell: its metadata has
## "isometric" (true), and "tile_size" is the diamond the cells are found by.

const DIR := "res://generated/minimaps/"

## The key of a map scene: its project path without "res://" and ".tscn", "/" made "__"
## (".../maps/imported/pack/cave.tscn" -> "game__maps__imported__pack__cave").
static func key_for(scene_path: String) -> String:
	return scene_path.trim_prefix("res://").trim_suffix(".tscn").replace("/", "__")

static func path_for(map_key: String) -> String:
	return DIR + map_key + ".tres"

## The minimap texture of a map key, or null.
static func load_texture(map_key: String) -> Texture2D:
	var path := path_for(map_key)
	return load(path) as Texture2D if ResourceLoader.exists(path) else null

static func origin_of(texture: Texture2D) -> Vector2i:
	if texture == null:
		return Vector2i.ZERO
	var origin: Vector2i = texture.get_meta("origin_cell", Vector2i.ZERO)
	return origin

static func tile_of(texture: Texture2D) -> Vector2i:
	if texture == null:
		return Vector2i(16, 16)
	var tile: Vector2i = texture.get_meta("tile_size", Vector2i(16, 16))
	return tile

## The minimap pixel (cell from the origin) of a map-local position.
static func cell_at(texture: Texture2D, local_position: Vector2) -> Vector2i:
	var tile := tile_of(texture)
	if is_isometric(texture) and tile.x > 0 and tile.y > 0:
		return RpgIso.screen_to_cell(local_position, tile) - origin_of(texture)
	var cell := Vector2i(floori(local_position.x / maxf(tile.x, 1.0)), floori(local_position.y / maxf(tile.y, 1.0)))
	return cell - origin_of(texture)

## True for the minimap of an isometric map.
static func is_isometric(texture: Texture2D) -> bool:
	return texture != null and RpgUtil.to_bool(texture.get_meta("isometric", false))

## What the minimap marks in `map`: doors, unopened chests and the entities quest stages point
## at. [{kind: "door" | "chest" | "quest", position: map-local Vector2}].
static func markers(map: Node, quest_targets: Array[String]) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	_collect(map, map, quest_targets, out)
	return out

static func _collect(map: Node, node: Node, targets: Array[String], out: Array[Dictionary]) -> void:
	for child in node.get_children():
		if child is Node2D:
			var spot: Node2D = child
			var at := (map as Node2D).to_local(spot.global_position) if map is Node2D else spot.position
			var entity := str(child.get("entity_id")) if "entity_id" in child else ""
			if entity != "" and targets.has(entity):
				out.append({"kind": "quest", "position": at})
			elif child is RpgDoor:
				out.append({"kind": "door", "position": at})
			elif child is RpgChest and not (child as RpgChest).opened:
				out.append({"kind": "chest", "position": at})
		_collect(map, child, targets, out)

# ---------------------------------------------------------------- the room map (T14.08)
# A metroidvania's map is its rooms on the world's grid of screens (rpggen/world_plan.json, the
# `rooms` section): a box per room the player has been in, the current one outlined, a notch per
# exit, a mark for a save station and for an ability that still lies there.

const ROOM_BOX := Vector2i(14, 9)
const ROOM_GAP := 2
# (whole 8-bit values, so a pixel read back from the picture is the colour that was drawn)
const ROOM_BACK := Color("0d0d14d9")
const ROOM_SEEN := Color("545e85")
const ROOM_EDGE := Color("b8bfd6")
const ROOM_HERE := Color("ffffff")
const ROOM_STATION := Color("73d98c")
const ROOM_PICKUP := Color("ffd14d")

## The rooms of a world plan ({} entries of its `rooms.list`); empty for a plan without rooms.
static func room_list(plan: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in RpgUtil.to_array(RpgUtil.to_dict(plan.get("rooms", {})).get("list", [])):
		out.append(RpgUtil.to_dict(raw))
	return out

static func _grid_cell(room: Dictionary) -> Vector2i:
	var pair := RpgUtil.to_array(room.get("cell", [0, 0]))
	return Vector2i(RpgUtil.to_int(pair[0]), RpgUtil.to_int(pair[1])) if pair.size() == 2 else Vector2i.ZERO

## {room id: Rect2i}: the box of every room of the plan in the room map's picture.
static func room_boxes(plan: Dictionary) -> Dictionary:
	var rooms := room_list(plan)
	var boxes := {}
	if rooms.is_empty():
		return boxes
	var low := _grid_cell(rooms[0])
	for room in rooms:
		var at := _grid_cell(room)
		low = Vector2i(mini(low.x, at.x), mini(low.y, at.y))
	var pitch := ROOM_BOX + Vector2i(ROOM_GAP, ROOM_GAP)
	for room in rooms:
		boxes[str(room.get("id", ""))] = Rect2i((_grid_cell(room) - low) * pitch + Vector2i(ROOM_GAP, ROOM_GAP), ROOM_BOX)
	return boxes

## The room map as a picture: the rooms in `visited` ({room id: true}) filled, `current` outlined
## in white, a notch for each exit, a green mark for a save station and a yellow one for an
## ability that is not in `held` yet. Rooms the player has not been in are not drawn.
static func room_map(plan: Dictionary, visited: Dictionary, current: String, held: Array) -> Image:
	var boxes := room_boxes(plan)
	var size := Vector2i(ROOM_GAP, ROOM_GAP)
	for id: String in boxes:
		var box: Rect2i = boxes[id]
		size = Vector2i(maxi(size.x, box.end.x + ROOM_GAP), maxi(size.y, box.end.y + ROOM_GAP))
	var image := Image.create(maxi(1, size.x), maxi(1, size.y), false, Image.FORMAT_RGBA8)
	image.fill(ROOM_BACK)
	for room in room_list(plan):
		var id := str(room.get("id", ""))
		if not visited.has(id) and id != current:
			continue
		var box: Rect2i = boxes[id]
		image.fill_rect(box, ROOM_HERE if id == current else ROOM_EDGE)
		image.fill_rect(box.grow(-1), ROOM_SEEN)
		for raw: Variant in RpgUtil.to_array(room.get("exits", [])):
			var notch := _notch(box, str(RpgUtil.to_dict(raw).get("edge", "")))
			if notch.has_area():
				image.fill_rect(notch, ROOM_EDGE)
		if room.has("station"):
			image.fill_rect(Rect2i(box.position + Vector2i(3, 5), Vector2i(2, 2)), ROOM_STATION)
		var ability := str(RpgUtil.to_dict(room.get("pickup", {})).get("ability", ""))
		if ability != "" and not held.has(ability):
			image.fill_rect(Rect2i(box.position + Vector2i(9, 5), Vector2i(2, 2)), ROOM_PICKUP)
	return image

## The little bar that sticks out of a room's box where an exit is.
static func _notch(box: Rect2i, edge: String) -> Rect2i:
	var middle := box.position + box.size / 2
	match edge:
		"E":
			return Rect2i(box.end.x, middle.y - 1, ROOM_GAP, 3)
		"W":
			return Rect2i(box.position.x - ROOM_GAP, middle.y - 1, ROOM_GAP, 3)
		"N":
			return Rect2i(middle.x - 1, box.position.y - ROOM_GAP, 3, ROOM_GAP)
		"S":
			return Rect2i(middle.x - 1, box.end.y, 3, ROOM_GAP)
	return Rect2i()
