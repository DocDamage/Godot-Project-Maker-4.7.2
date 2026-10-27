@tool
extends RefCounted
## The height layers of an isometric level (2026-10-26): what a pack stacks (a block on the
## ground, a storey on a block, a roof on the last storey, an awning on a storey's face) is
## painted on a TileMapLayer of its own, drawn higher by its height. Such a layer
##
## * lies `height` px higher (`position.y = -height`) and sorts as its cells' ground does
##   (`y_sort_origin = height`), so what stands on a cell in front of a building is drawn
##   in front of all of its storeys, and what stands behind is drawn behind them;
## * is y-sorted with the level's things (it is a child of the level's YSorted node, or of the
##   y-sorted node the layer it is made from is in), and paints with the level's tile set;
## * says its height in its meta `rpg_height`.
##
## How high a piece raises what stands on it is its tile's custom data `lift` (a block 16 px, a
## storey 20, from the catalog's facet; rpggen/core/adapters/gridwright.py). The top of a stack
## on a cell is the highest layer with a tile there and that tile's lift: a thing placed from
## the dock stands on it (placement.gd).

const JsonIo := preload("json_io.gd")

const HEIGHT_META := "rpg_height"
const YSORT_PATH := "YSorted"
const LIFT := "lift"
## The step a level's first layer above the ground is given when nothing painted says one.
const DEFAULT_STEP := 16

## The height a layer is drawn at: its meta, 0 for a layer without one (the level's ground).
static func height_of(layer: TileMapLayer) -> int:
	if layer == null or not layer.has_meta(HEIGHT_META):
		return 0
	return JsonIo.to_int(layer.get_meta(HEIGHT_META))

## The tile layers of a level with a tile set, in the order of the tree.
static func tile_layers(root: Node) -> Array[TileMapLayer]:
	var out: Array[TileMapLayer] = []
	if root == null:
		return out
	for node in root.find_children("*", "TileMapLayer", true, false):
		var layer := node as TileMapLayer
		if layer.tile_set != null:
			out.append(layer)
	return out

## The height layers of a level (the layers with the meta), lowest first.
static func layers(root: Node) -> Array[TileMapLayer]:
	var out: Array[TileMapLayer] = []
	for layer in tile_layers(root):
		if layer.has_meta(HEIGHT_META):
			out.append(layer)
	out.sort_custom(func(a: TileMapLayer, b: TileMapLayer) -> bool: return height_of(a) < height_of(b))
	return out

## How high the tile painted on `cell` of `layer` raises what stands on it (0 for none).
static func lift_at(layer: TileMapLayer, cell: Vector2i) -> int:
	var data := layer.get_cell_tile_data(cell)
	if data == null or layer.tile_set.get_custom_data_layer_by_name(LIFT) == -1:
		return 0
	return JsonIo.to_int(data.get_custom_data(LIFT))

## The highest lift of the tiles painted on `layer` (0 when none lifts).
static func highest_lift(layer: TileMapLayer) -> int:
	var best := 0
	for cell in layer.get_used_cells():
		best = maxi(best, lift_at(layer, cell))
	return best

## The top of the stack on `cell`: the highest of every layer's height and the lift of its tile
## there, over the layers that have a tile on the cell (0 for bare ground).
static func top_at(root: Node, cell: Vector2i) -> int:
	var top := 0
	for layer in tile_layers(root):
		if layer.get_cell_source_id(cell) == -1:
			continue
		top = maxi(top, height_of(layer) + lift_at(layer, cell))
	return top

## The height the next layer is drawn at: on the highest height layer, as high as its tiles
## lift (a storey on a block, the next storey on a storey); 0 when the level has none (the
## first is for what stands on the ground: blocks, walls, the ground storeys of houses), and a
## step higher when its tiles lift nothing.
static func suggested(root: Node) -> int:
	var existing := layers(root)
	if existing.is_empty():
		return 0
	# of the layers at the top (a storey's and its awning's), the one that lifts most
	var top := height_of(existing[existing.size() - 1])
	var lift := 0
	for layer in existing:
		if height_of(layer) == top:
			lift = maxi(lift, highest_lift(layer))
	return top + (lift if lift > 0 else DEFAULT_STEP)

## Where a new height layer goes: the y-sorted node of the level (YSorted), else the parent of
## `beside` when that is y-sorted, else the level's root.
static func parent_for(root: Node, beside: TileMapLayer = null) -> Node:
	var ysorted := root.get_node_or_null(YSORT_PATH)
	if ysorted != null:
		return ysorted
	if beside != null and beside.get_parent() is CanvasItem and (beside.get_parent() as CanvasItem).y_sort_enabled:
		return beside.get_parent()
	return root

## A new height layer at `height` for the level `root` (not yet in the tree): the tile set of
## `like` (the selected layer, else the level's ground), y-sorted, drawn `height` px higher and
## sorted by its cells' ground. Named "Height <height>".
static func make_layer(root: Node, height: int, like: TileMapLayer = null) -> TileMapLayer:
	var from := like if like != null else RpgIso.ground_layer(root)
	var layer := TileMapLayer.new()
	layer.name = "Height %d" % height
	if from != null:
		layer.tile_set = from.tile_set
	layer.y_sort_enabled = true
	layer.position = Vector2(0, -height)
	layer.y_sort_origin = height
	layer.set_meta(HEIGHT_META, height)
	return layer

## Adds a height layer at `height` to the open level with undo ("Add height layer"); returns it.
static func add_layer(root: Node, height: int, undo: EditorUndoRedoManager, like: TileMapLayer = null) -> TileMapLayer:
	var parent := parent_for(root, like)
	var layer := make_layer(root, height, like)
	var layer_name := String(layer.name)
	var taken := {}
	for child in parent.get_children(true):
		taken[String(child.name)] = true
	var n := 2
	while taken.has(layer_name):
		layer_name = "Height %d (%d)" % [height, n]
		n += 1
	layer.name = layer_name
	undo.create_action("Add height layer %d" % height, UndoRedo.MERGE_DISABLE, root)
	undo.add_do_method(parent, "add_child", layer, true)
	undo.add_do_method(layer, "set_owner", root)
	undo.add_do_reference(layer)
	undo.add_undo_method(parent, "remove_child", layer)
	undo.commit_action()
	return layer
