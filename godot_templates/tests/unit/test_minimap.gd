extends RefCounted
## The minimap and the world map (T12.64): the recipe's picture of a map, the markers, the fog
## and its save, and the world map menu.

const Fixtures := preload("../lib/fixtures.gd")
const MinimapRecipe := preload("res://builder/recipes/minimap_recipe.gd")
const UiRecipes := preload("res://builder/recipes/ui_recipes.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")

const MENU_TMP := "user://test_world_map_menu.tscn"
const RED := Color(1, 0, 0)
const BLUE := Color(0, 0, 1)

## A 16 px tile set: tile (0,0) red, tile (1,0) blue on its left half and clear on its right.
func _tile_set() -> TileSet:
	var image := Image.create(32, 16, false, Image.FORMAT_RGBA8)
	image.fill_rect(Rect2i(0, 0, 16, 16), RED)
	image.fill_rect(Rect2i(16, 0, 8, 16), BLUE)
	var tile_set := TileSet.new()
	tile_set.tile_size = Vector2i(16, 16)
	var source := TileSetAtlasSource.new()
	source.texture = ImageTexture.create_from_image(image)
	source.texture_region_size = Vector2i(16, 16)
	source.create_tile(Vector2i(0, 0))
	source.create_tile(Vector2i(1, 0))
	tile_set.add_source(source, 0)
	return tile_set

func _layer(tile_set: TileSet, cells: Dictionary) -> TileMapLayer:
	var layer := TileMapLayer.new()
	layer.tile_set = tile_set
	for cell: Vector2i in cells:
		var atlas: Vector2i = cells[cell]
		layer.set_cell(cell, 0, atlas)
	return layer

func test_the_picture_covers_the_used_cells_one_pixel_each(t) -> void:
	var tile_set := _tile_set()
	var ground := _layer(tile_set, {Vector2i(2, 3): Vector2i(0, 0), Vector2i(4, 5): Vector2i(0, 0)})
	var top := _layer(tile_set, {Vector2i(2, 3): Vector2i(1, 0), Vector2i(5, 3): Vector2i(1, 0)})
	var layers: Array[TileMapLayer] = [ground, top]
	var texture := MinimapRecipe.render_layers(layers)
	t.ok(texture != null)
	if texture != null:
		t.eq(texture.get_size(), Vector2(4, 3), "the union of the layers' used rects")
		t.eq(RpgMinimapData.origin_of(texture), Vector2i(2, 3))
		t.eq(RpgMinimapData.tile_of(texture), Vector2i(16, 16))
		var image := texture.get_image()
		t.ok(image.get_pixel(0, 0).is_equal_approx(BLUE), "a later layer covers an earlier one")
		t.ok(image.get_pixel(2, 2).is_equal_approx(RED))
		t.ok(image.get_pixel(3, 0).is_equal_approx(BLUE), "clear pixels are left out of the average")
		t.eq(image.get_pixel(1, 1).a, 0.0, "a cell with no tile is clear")
	ground.free()
	top.free()
	var empty: Array[TileMapLayer] = [_layer(tile_set, {})]
	t.ok(MinimapRecipe.render_layers(empty) == null, "a map without painted cells has no minimap")
	empty[0].free()

func test_a_map_scene_is_found_and_rendered(t) -> void:
	var dir := "user://test_minimap_maps_%d" % Time.get_ticks_usec()
	DirAccess.make_dir_recursive_absolute(dir.path_join("imported/pack"))
	var root := Node2D.new()
	root.name = "Cave"
	var layer := _layer(_tile_set(), {Vector2i(0, 0): Vector2i(0, 0), Vector2i(9, 4): Vector2i(0, 0)})
	layer.name = "Ground"
	root.add_child(layer)
	SceneUtil.save_scene(root, dir.path_join("imported/pack/cave.tscn"))  # (frees root)
	var found := MinimapRecipe.map_files(dir)
	t.eq(found, [dir.path_join("imported/pack/cave.tscn")] as Array[String])
	var texture := MinimapRecipe.render(found[0])
	t.ok(texture != null and texture.get_size() == Vector2(10, 5))
	t.eq(RpgMinimapData.key_for("res://game/maps/imported/pack/cave.tscn"), "game__maps__imported__pack__cave")
	t.eq(RpgMinimapData.path_for("starter_map"), "res://generated/minimaps/starter_map.tres")

func test_positions_become_minimap_cells(t) -> void:
	var texture := ImageTexture.create_from_image(Image.create(4, 4, false, Image.FORMAT_RGBA8))
	texture.set_meta("origin_cell", Vector2i(-2, 1))
	texture.set_meta("tile_size", Vector2i(32, 32))
	t.eq(RpgMinimapData.cell_at(texture, Vector2(-40, 70)), Vector2i(0, 1))
	t.eq(RpgMinimapData.cell_at(texture, Vector2(0, 32)), Vector2i(2, 0))

func test_the_markers_are_doors_unopened_chests_and_quest_targets(t) -> void:
	var map := Node2D.new()
	map.position = Vector2(100, 0)
	var door := RpgDoor.new()
	door.position = Vector2(10, 20)
	map.add_child(door)
	var chest := RpgChest.new()
	chest.position = Vector2(30, 40)
	map.add_child(chest)
	var opened := RpgChest.new()
	opened.opened = true
	map.add_child(opened)
	var group := Node2D.new()
	map.add_child(group)
	var target := RpgChest.new()
	target.entity_id = "villager"
	target.position = Vector2(5, 5)
	group.add_child(target)
	var marks := RpgMinimapData.markers(map, ["villager"] as Array[String])
	var kinds: Array[String] = []
	for mark in marks:
		kinds.append(str(mark["kind"]))
	t.eq(kinds, ["door", "chest", "quest"] as Array[String])
	t.eq(marks[0]["position"], Vector2(10, 20), "map-local positions")
	t.eq(marks[2]["position"], Vector2(5, 5), "a nested entity is found too")
	map.free()

func test_the_fog_is_marked_seen_and_saved(t) -> void:
	var state := Fixtures.install_state()
	state.new_game()
	t.eq(state.visited_maps().size(), 0)
	t.ok(not state.to_dict().has("map_fog"), "no fog, no key")
	state.fog_mark("starter_map", Vector2i(20, 10), Vector2i(5, 5), 2)
	t.ok(state.fog_seen("starter_map", Vector2i(5, 5)))
	t.ok(state.fog_seen("starter_map", Vector2i(7, 5)))
	t.ok(not state.fog_seen("starter_map", Vector2i(7, 7)), "a circle, not a square")
	t.ok(not state.fog_seen("starter_map", Vector2i(30, 5)), "outside the map")
	t.ok(not state.fog_seen("cave", Vector2i(0, 0)))
	state.fog_mark("cave", Vector2i(3, 3), Vector2i(0, 0), 0)
	t.eq(state.visited_maps(), ["cave", "starter_map"] as Array[String])
	var back: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	state.new_game()
	t.eq(state.visited_maps().size(), 0, "a new game forgets the fog")
	state.from_dict(back)
	t.ok(state.fog_seen("starter_map", Vector2i(7, 5)), "the fog survives a save")
	t.ok(not state.fog_seen("starter_map", Vector2i(7, 7)))
	t.ok(state.fog_seen("cave", Vector2i(0, 0)))
	back["map_fog"] = {"bad": {"w": 4, "h": 4, "bits": "AAAA"}, "worse": 3}
	state.from_dict(back)
	t.eq(state.visited_maps().size(), 0, "malformed fog is dropped")
	state.fog_mark("cave", Vector2i(3, 3), Vector2i(0, 0), 0)
	state.fog_mark("cave", Vector2i(5, 5), Vector2i(4, 4), 0)
	t.ok(not state.fog_seen("cave", Vector2i(0, 0)), "a map that changed size starts again")
	Fixtures.uninstall_state()

func test_quest_targets_are_the_current_stages_targets(t) -> void:
	var english := Fixtures.install_english()  # (the quest toasts format their text)
	var state := Fixtures.install_state()
	state.new_game()
	var def := RpgQuestDefinition.new()
	def.id = &"errand"
	def.title = "Errand"
	var stages: Array[Dictionary] = [
		{"id": "talk", "complete_when": "flag:npc.talked", "target": "npc"},
		{"id": "chest", "complete_when": "flag:chest.opened", "target": "chest"},
		{"id": "return", "complete_when": ""},
	]
	def.stages = stages
	state.quest_defs[&"errand"] = def
	t.eq(state.quest_targets().size(), 0, "not started")
	state.quest_start(&"errand")
	t.eq(state.quest_targets(), ["npc"] as Array[String])
	state.set_flag("npc", "talked", true)
	t.eq(state.quest_targets(), ["chest"] as Array[String])
	state.set_flag("chest", "opened", true)
	t.eq(state.quest_targets().size(), 0, "a stage without a target")
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

func test_the_world_map_covers_unseen_cells(t) -> void:
	var state := Fixtures.install_state()
	state.new_game()
	var image := Image.create(4, 2, false, Image.FORMAT_RGBA8)
	image.fill(RED)
	var texture := ImageTexture.create_from_image(image)
	state.fog_mark("cave", Vector2i(4, 2), Vector2i(0, 0), 0)
	var picture := RpgWorldMapMenu.fogged("cave", state, texture)
	t.eq(picture.get_size(), Vector2(16, 8), "scaled up")
	var shown := picture.get_image()
	t.ok(shown.get_pixel(1, 1).is_equal_approx(RED), "a seen cell")
	var fog := shown.get_pixel(15, 7)
	t.ok(Vector4(fog.r, fog.g, fog.b, fog.a).distance_to(Vector4(0.05, 0.05, 0.08, 1.0)) < 0.01, "an unseen cell")
	t.ok(RpgWorldMapMenu.fogged("nowhere", state) == null)
	Fixtures.uninstall_state()

func test_the_world_map_menu_lists_the_visited_maps(t) -> void:
	var state := Fixtures.install_state()
	state.new_game()
	state.fog_mark("game__maps__starter_map", Vector2i(2, 2), Vector2i(0, 0), 0)
	state.fog_mark("game__maps__imported__pack__cave", Vector2i(2, 2), Vector2i(0, 0), 0)
	var root: Node = UiRecipes.new().call("_build_world_map_menu")
	SceneUtil.save_scene(root, MENU_TMP)
	var menu := (load(MENU_TMP) as PackedScene).instantiate() as RpgWorldMapMenu
	Fixtures.tree().root.add_child(menu)
	if not menu.is_node_ready():
		menu._ready()
	var list := menu.get_node("%Maps") as ItemList
	t.eq(list.item_count, 2)
	t.eq(list.get_item_text(0), "MAP_CAVE", "named by the map's last part")
	t.eq(list.get_item_text(1), "MAP_STARTER_MAP")
	menu.free()
	Fixtures.uninstall_state()

func test_the_minimap_setting_is_on_by_default_and_saved(t) -> void:
	var path := "user://test_minimap_settings_%d.cfg" % Time.get_ticks_usec()
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS)
	settings.path = path
	t.eq(settings.minimap, true)
	settings.set_minimap(false)
	t.ok(settings.save_settings())
	settings.minimap = true
	settings.load_settings()
	t.eq(settings.minimap, false, "saved")
	Fixtures.uninstall("RpgSettings")
	DirAccess.remove_absolute(path)
