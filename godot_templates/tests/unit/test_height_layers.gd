extends RefCounted
## The height layers of an isometric level (2026-10-26, tools/height_layers.gd): a layer drawn
## higher sorts by its cells' ground, the top of a stack on a cell is its highest layer's height
## and its tile's lift, the next layer is suggested on the top, and what the dock places on a cell
## with a stack stands on it (placement.gd's plan). The tile set is made here: a floor, a block
## that lifts 16 and a storey that lifts 20, on diamonds of 32 x 16.
##
## `add_layer` and `Placement.apply` take the editor's own undo manager, which exists only in a
## running editor: the level probe (tests/integration/level_probe) runs them there.

const HeightLayers := preload("res://addons/rpg_project_tools/tools/height_layers.gd")
const Placement := preload("res://addons/rpg_project_tools/dock/placement.gd")

const FLOOR := Vector2i(0, 0)
const BLOCK := Vector2i(1, 0)
const STOREY := Vector2i(2, 0)
const AWNING := Vector2i(3, 0)

var _roots: Array[Node] = []

func _tile_set() -> TileSet:
	var ts := TileSet.new()
	ts.tile_shape = TileSet.TILE_SHAPE_ISOMETRIC
	ts.tile_layout = TileSet.TILE_LAYOUT_DIAMOND_DOWN
	ts.tile_size = Vector2i(32, 16)
	ts.add_custom_data_layer()
	ts.set_custom_data_layer_name(0, "lift")
	ts.set_custom_data_layer_type(0, TYPE_INT)
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(Image.create(128, 48, false, Image.FORMAT_RGBA8))
	src.texture_region_size = Vector2i(32, 48)
	ts.add_source(src, 0)
	for pair: Array in [[FLOOR, 0], [BLOCK, 16], [STOREY, 20], [AWNING, 0]]:
		src.create_tile(pair[0])
		src.get_tile_data(pair[0], 0).set_custom_data("lift", pair[1])
	return ts

## A level as a user starts one: Ground with the floor everywhere, and YSorted/Entities.
func _level() -> Node2D:
	var root := Node2D.new()
	root.name = "Level"
	var ground := TileMapLayer.new()
	ground.name = "Ground"
	ground.tile_set = _tile_set()
	root.add_child(ground)
	for y in 6:
		for x in 6:
			ground.set_cell(Vector2i(x, y), 0, FLOOR)
	var ysorted := Node2D.new()
	ysorted.name = "YSorted"
	ysorted.y_sort_enabled = true
	root.add_child(ysorted)
	var entities := Node2D.new()
	entities.name = "Entities"
	entities.y_sort_enabled = true
	ysorted.add_child(entities)
	_roots.append(root)
	return root

## A height layer made as the dock makes one, put where the dock puts it.
func _add(root: Node, height: int) -> TileMapLayer:
	var layer := HeightLayers.make_layer(root, height)
	HeightLayers.parent_for(root).add_child(layer)
	return layer

func _cleanup() -> void:
	for root in _roots:
		if is_instance_valid(root):
			root.free()
	_roots.clear()

func test_a_height_layer_is_drawn_higher_and_sorts_by_its_ground(t) -> void:
	var root := _level()
	var layer := HeightLayers.make_layer(root, 36)
	t.eq(String(layer.name), "Height 36")
	t.eq(layer.position, Vector2(0, -36), "drawn 36 px higher")
	t.eq(layer.y_sort_origin, 36, "sorted where its cells' ground is")
	t.ok(layer.y_sort_enabled, "y-sorted with the level's things")
	t.eq(HeightLayers.height_of(layer), 36)
	t.ok(layer.tile_set == (root.get_node("Ground") as TileMapLayer).tile_set, "the level's tile set")
	t.eq(HeightLayers.parent_for(root), root.get_node("YSorted"), "beside what is placed")
	t.eq(HeightLayers.height_of(root.get_node("Ground") as TileMapLayer), 0, "the ground is at 0")
	layer.free()
	_cleanup()

func test_the_top_of_a_stack_and_the_next_layer(t) -> void:
	var root := _level()
	t.eq(HeightLayers.suggested(root), 0, "the first layer is for what stands on the ground")
	t.eq(HeightLayers.top_at(root, Vector2i(2, 2)), 0, "bare ground")
	var blocks := _add(root, 0)
	blocks.set_cell(Vector2i(2, 2), 0, BLOCK)
	t.eq(HeightLayers.top_at(root, Vector2i(2, 2)), 16, "a block lifts 16")
	t.eq(HeightLayers.suggested(root), 16, "the next layer stands on the blocks")
	var storey := _add(root, 16)
	storey.set_cell(Vector2i(2, 2), 0, STOREY)
	var awning := _add(root, 16)  # an awning on the storey's face: a layer of its own, no lift
	awning.set_cell(Vector2i(2, 2), 0, AWNING)
	t.eq(HeightLayers.top_at(root, Vector2i(2, 2)), 36, "a storey on a block")
	t.eq(HeightLayers.suggested(root), 36, "of the layers at the top, the one that lifts most")
	t.eq(HeightLayers.top_at(root, Vector2i(4, 4)), 0, "a cell without a stack")
	t.eq(HeightLayers.layers(root).size(), 3)
	_cleanup()

func test_what_is_placed_on_a_stack_stands_on_its_top(t) -> void:
	var root := _level()
	var blocks := _add(root, 0)
	blocks.set_cell(Vector2i(2, 2), 0, BLOCK)
	var ground := root.get_node("Ground") as TileMapLayer
	var placement := Placement.new()
	var thing := Node2D.new()
	thing.name = "Crate"
	var on_block := placement.plan(thing, root, {}, null, ground.map_to_local(Vector2i(2, 2)))
	t.eq(on_block["cell"], Vector2i(2, 2))
	t.eq(on_block["raise"], 16, "it stands on the block")
	var beside := placement.plan(thing, root, {}, null, ground.map_to_local(Vector2i(4, 1)))
	t.eq(beside["raise"], 0, "on the ground beside it")
	thing.free()
	_cleanup()

# ---------------------------------------------------------------- the sides of raised ground (T18.20)

## A tile set whose tiles name their assets: a floor of grass, a block of grass (a side of grass,
## lifting 16) and a block of stone (a side of stone).
func _sided_tile_set() -> TileSet:
	var ts := _tile_set()
	ts.add_custom_data_layer()
	ts.set_custom_data_layer_name(1, "asset_id")
	ts.set_custom_data_layer_type(1, TYPE_STRING)
	var src := ts.get_source(0) as TileSetAtlasSource
	src.get_tile_data(FLOOR, 0).set_custom_data("asset_id", "kit.floors.floor_grass_01")
	src.get_tile_data(BLOCK, 0).set_custom_data("asset_id", "kit.blocks.block_grass_01")
	src.get_tile_data(STOREY, 0).set_custom_data("asset_id", "kit.blocks.block_stone_01")
	src.get_tile_data(STOREY, 0).set_custom_data("lift", 16)
	return ts

const SIDED_CATALOG := {"assets": [
	{"id": "kit.floors.floor_grass_01", "detected": {"role": "GROUND"}},
	{"id": "kit.blocks.block_grass_01", "detected": {"stack": "block", "side_terrain": "grass"}},
	{"id": "kit.blocks.block_stone_01", "detected": {"stack": "block", "side_terrain": "stone"}},
]}

func test_raised_ground_gets_its_sides_where_they_are_seen(t) -> void:
	var root := _level()
	var ts := _sided_tile_set()
	(root.get_node("Ground") as TileMapLayer).tile_set = ts
	var pieces := HeightLayers.side_pieces(ts, SIDED_CATALOG)
	t.eq(pieces.keys().size(), 2, "a side of grass and one of stone")
	t.eq((pieces["grass"] as Array)[0]["coords"], BLOCK)
	# a plateau of grass floor 32 px up, on the cells (1..2, 1..2)
	var top := _add(root, 32)
	top.tile_set = ts
	for cell: Vector2i in [Vector2i(1, 1), Vector2i(2, 1), Vector2i(1, 2), Vector2i(2, 2)]:
		top.set_cell(cell, 0, FLOOR)
	t.eq(HeightLayers.surface_of(top, Vector2i(1, 1), pieces.keys()), "grass")
	var open := HeightLayers.open_sides(root, top)
	open.sort()
	t.eq(open, [Vector2i(1, 2), Vector2i(2, 1), Vector2i(2, 2)] as Array[Vector2i], "the cells whose sides face the camera; the back one is hidden")
	var plan := HeightLayers.plan_sides(root, top, SIDED_CATALOG)
	var made: Array[TileMapLayer] = plan["made"]
	var puts: Array[Array] = plan["puts"]
	t.eq(made.map(func(l: TileMapLayer) -> int: return HeightLayers.height_of(l)), [16, 0], "blocks at 16 and on the ground")
	t.eq(puts.size(), 6, "two blocks of grass under each of the three cells")
	for put in puts:
		t.eq(put[3], BLOCK, "of its own surface")
	for holder in made:
		holder.free()
	# a cell held up by a block below has no open side
	var under := _add(root, 16)
	under.tile_set = ts
	under.set_cell(Vector2i(2, 2), 0, BLOCK)
	t.ok(not HeightLayers.open_sides(root, top).has(Vector2i(2, 2)), "held up already")
	_cleanup()
