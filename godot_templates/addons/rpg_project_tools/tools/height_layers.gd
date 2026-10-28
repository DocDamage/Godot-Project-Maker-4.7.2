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
const CatalogEdit := preload("catalog_edit.gd")

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

# ---------------------------------------------------------------- the sides of raised ground

## The tile data layer that names a tile's asset (what the catalog says of it).
const ASSET_ID := "asset_id"

## The pieces of a level's tile set that are the sides of raised ground (T18.20): for each
## surface (`grass`, `sidewalk`, ...: the catalog's `side_terrain` of a block), its blocks as
## {source, coords, lift}, the lowest first.
static func side_pieces(ts: TileSet, catalog: Dictionary) -> Dictionary:
	var out := {}
	if ts == null or ts.get_custom_data_layer_by_name(ASSET_ID) == -1:
		return out
	for i in ts.get_source_count():
		var id := ts.get_source_id(i)
		var src := ts.get_source(id) as TileSetAtlasSource
		if src == null:
			continue
		for t in src.get_tiles_count():
			var coords := src.get_tile_id(t)
			var data := src.get_tile_data(coords, 0)
			var asset := CatalogEdit.find_asset(catalog, JsonIo.to_str(data.get_custom_data(ASSET_ID)))
			var surface := JsonIo.to_str(CatalogEdit.effective(asset).get("side_terrain", "")) if not asset.is_empty() else ""
			if surface == "":
				continue
			var lift := JsonIo.to_int(data.get_custom_data(LIFT)) if ts.get_custom_data_layer_by_name(LIFT) != -1 else 0
			if lift <= 0:
				continue
			if not out.has(surface):
				out[surface] = []
			var found: Array = out[surface]
			found.append({"source": id, "coords": coords, "lift": lift})
	for surface: String in out:
		var found: Array = out[surface]
		found.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return JsonIo.to_int(a["lift"]) < JsonIo.to_int(b["lift"]))
	return out

## What the tile on `cell` of `layer` is made of: the first of `surfaces` its asset's name says
## (`floor_grass_02` is grass), "" when none.
static func surface_of(layer: TileMapLayer, cell: Vector2i, surfaces: Array) -> String:
	var data := layer.get_cell_tile_data(cell)
	if data == null or layer.tile_set.get_custom_data_layer_by_name(ASSET_ID) == -1:
		return ""
	var asset_id := JsonIo.to_str(data.get_custom_data(ASSET_ID)).to_lower()
	var words := asset_id.get_file().replace(".", "_").replace("-", "_").replace(" ", "_").split("_", false)
	for word in words:
		if surfaces.has(word):
			return word
	return ""

## The cells of a raised `layer` whose sides face the camera (e, the lower right, and s, the
## lower left) over lower ground, and that nothing below holds up yet.
static func open_sides(root: Node, layer: TileMapLayer) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	var height := height_of(layer)
	if height <= 0:
		return out
	for cell in layer.get_used_cells():
		if top_at(root, cell + Vector2i(1, 0)) >= height and top_at(root, cell + Vector2i(0, 1)) >= height:
			continue
		var held := false
		for other in tile_layers(root):
			if other != layer and height_of(other) < height and other.get_cell_source_id(cell) != -1 and height_of(other) + lift_at(other, cell) >= height:
				held = true
		if not held:
			out.append(cell)
	return out

## What giving the raised ground of `layer` its sides (T18.20) puts: under each of its
## `open_sides`, blocks of its surface (`side_pieces`; another surface's when it has none) stacked
## down to the ground, each on the height layer of its height. {made: the layers to make (not yet
## in the tree), puts: [[layer, cell, source, coords]]}; nothing to put when the tile set has no
## block that is a side.
static func plan_sides(root: Node, layer: TileMapLayer, catalog: Dictionary) -> Dictionary:
	var made: Array[TileMapLayer] = []
	var puts: Array[Array] = []
	var out := {"made": made, "puts": puts}
	var pieces := side_pieces(layer.tile_set, catalog)
	if pieces.is_empty():
		return out
	var surfaces := pieces.keys()
	var by_height := {}
	for other in layers(root):
		by_height[height_of(other)] = other
	for cell in open_sides(root, layer):
		var surface := surface_of(layer, cell, surfaces)
		var blocks: Array = pieces[surface] if surface != "" else pieces[surfaces[0]]
		var block: Dictionary = blocks[0]
		var lift := JsonIo.to_int(block["lift"])
		var at := height_of(layer) - lift
		while at >= 0:
			var holder: TileMapLayer = by_height.get(at)
			if holder == null:
				holder = make_layer(root, at, layer)
				by_height[at] = holder
				made.append(holder)
			if holder.get_cell_source_id(cell) == -1:
				puts.append([holder, cell, JsonIo.to_int(block["source"]), block["coords"]])
			at -= lift
	return out

## Gives the raised ground of `layer` its sides (`plan_sides`) as one undo step ("Give the raised
## ground its sides"). Returns how many blocks were put.
static func face_sides(root: Node, layer: TileMapLayer, undo: EditorUndoRedoManager, catalog: Dictionary) -> int:
	var plan := plan_sides(root, layer, catalog)
	var made: Array[TileMapLayer] = plan["made"]
	var puts: Array[Array] = plan["puts"]
	if puts.is_empty():
		for holder in made:
			holder.free()
		return 0
	undo.create_action("Give the raised ground its sides", UndoRedo.MERGE_DISABLE, root)
	var parent := parent_for(root, layer)
	for holder in made:
		undo.add_do_method(parent, "add_child", holder, true)
		undo.add_do_method(holder, "set_owner", root)
		undo.add_do_reference(holder)
	for put in puts:
		var target: TileMapLayer = put[0]
		undo.add_do_method(target, "set_cell", put[1], put[2], put[3])
	for put in puts:
		var target: TileMapLayer = put[0]
		undo.add_undo_method(target, "erase_cell", put[1])
	for holder in made:
		undo.add_undo_method(parent, "remove_child", holder)
	undo.commit_action()
	return puts.size()
