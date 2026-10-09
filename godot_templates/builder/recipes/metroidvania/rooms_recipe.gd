extends RefCounted
## The rooms of a metroidvania (T14.06): game/maps/rooms/<room_id>.tscn for every room of the
## stored world plan (rpggen/world_plan.json, the `rooms` section, written by rpggen from the
## *Starter world* options). A room is built once (user_seed ownership): a room whose scene exists
## is never rebuilt, whatever the plan says now, so a regeneration only adds the rooms that are
## missing.
##
## A room is painted cell by cell as the plan says (`tiles`), with the tiles the TileSet offers for
## each kind (side_kit.gd). Its exits, the spawn point beside each exit, the camera, the player and
## what stands in it (the sign, the pickups, the hermit of the last room, a chest, the enemies and
## the guardian) come from the plan too.

const RECIPE_VERSION := 1

const Paths := preload("../../lib/paths.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const SceneUtil := preload("../../lib/scene_util.gd")
const SeedUtil := preload("../../lib/seed_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const ObjectEntries := preload("../../lib/object_entries.gd")
const ObjectIndex := preload("../../lib/object_index.gd")
const BuildContext := preload("../../lib/build_context.gd")
const WorldPlan := preload("../../lib/world_plan.gd")
const ActorRecipes := preload("../actor_recipes.gd")
const MvBuild := preload("metroidvania_build.gd")
const SideKit := preload("side_kit.gd")
const Parallax := preload("parallax_recipe.gd")
const Objects := preload("objects_recipe.gd")
const EnemyRecipes := preload("enemy_recipes.gd")

const ROOM_SCRIPT := MvBuild.DIR + "room.gd"
const EXIT_SCRIPT := MvBuild.DIR + "room_exit.gd"
const GATE_MARK_SCRIPT := MvBuild.DIR + "ability_gate.gd"
const GATE_SCRIPT := "res://addons/rpg_runtime/world/gate.gd"
## A flyer is put this many tiles above the floor its cell stands on.
const FLYER_LIFT_TILES := 3
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const SIGN_PATH := "res://game/data/dialogue/room_sign.tres"
const END_PATH := "res://game/data/dialogue/end_npc.tres"
const DLG_RES := "res://addons/rpg_runtime/dialogue/dialogue_resource.gd"
const DLG_LINE := "res://addons/rpg_runtime/dialogue/dialogue_line.gd"
## The flag the hermit of the last room sets: the game has been played through.
const END_FLAG := "game.finished"
const LAYERS: Array[String] = ["Ground", "Platforms", "Hazards", "Decoration", "Foreground"]
const SOLID_LAYERS: Array[String] = ["Ground", "Platforms"]

# ---------------------------------------------------------------- the plan

## The `rooms` section of the stored plan, or {}.
static func rooms_plan() -> Dictionary:
	return JsonUtil.to_dict(WorldPlan.read().get("rooms", {}))

static func rooms(plan: Dictionary) -> Array[Dictionary]:
	return WorldPlan.list_of(plan, "list")

static func room_path(room: Dictionary) -> String:
	return "res://" + JsonUtil.to_str(room.get("map", ""))

static func room_by_id(plan: Dictionary, id: String) -> Dictionary:
	for room in rooms(plan):
		if JsonUtil.to_str(room.get("id", "")) == id:
			return room
	return {}

## The scene of the room the game starts in ("" without a plan).
static func start_path() -> String:
	var plan := rooms_plan()
	var start := room_by_id(plan, JsonUtil.to_str(plan.get("start", "")))
	return room_path(start) if not start.is_empty() else ""

func _missing(plan: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for room in rooms(plan):
		if not FileAccess.file_exists(room_path(room)):
			out.append(room)
	return out

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	var plan := rooms_plan()
	for room in _missing(plan):
		out.append(room_path(room))
	if not plan.is_empty():
		out.append_array(SeedUtil.missing([SIGN_PATH, END_PATH]))
	return out

func input_hash(ctx: BuildContext) -> String:
	var plan := rooms_plan()
	var missing: Array = []
	for room in _missing(plan):
		missing.append(room)
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"rooms": missing,
		"tileset": _tileset_def(ctx),
		"starter": ctx.config.get("starter", {}),
		"music": JsonUtil.to_str(ctx.section("sounds").get("music_map", "")),
		"backgrounds": Parallax.layers(ctx),
		"entries": ObjectEntries.entries(ctx),
		"enemies": EnemyRecipes.new().input_hash(ctx),
	})

static func _tileset_def(ctx: BuildContext) -> Dictionary:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return def

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var plan := rooms_plan()
	if plan.is_empty():
		return issues
	_seed_dialogue(ctx, issues)
	var missing := _missing(plan)
	if missing.is_empty():
		return issues
	var def := _tileset_def(ctx)
	if def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, room_path(missing[0])))
		return issues
	var tileset_path: String = Paths.TILESETS_DIR + "%s.tres" % def["name"]
	var tile_set := load(tileset_path) as TileSet
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": tileset_path}, tileset_path))
		return issues
	if not ResourceLoader.exists(PLAYER_SCENE):
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		return issues
	var kit := SideKit.find(ctx, def, tile_set)
	if JsonUtil.to_dict(kit["top"]).is_empty():
		issues.append(ctx.make_issue("BUILD-002", {"recipe": "rooms_recipe", "reason": "the tile set has no solid tile to build a floor from"}, tileset_path))
		return issues
	for room in missing:
		var root := build_room(ctx, plan, room, tile_set, kit)
		var err := SceneUtil.save_scene(root, room_path(room))
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": room_path(room), "err": err}, room_path(room)))
	return issues

# ---------------------------------------------------------------- one room

static func _cell(value: Variant) -> Vector2i:
	return WorldPlan.cell(value)

## Where something whose feet cell is `cell` stands: the middle of the bottom edge of that cell.
static func feet(cell: Vector2i, tile: int) -> Vector2:
	return Vector2((cell.x + 0.5) * tile, (cell.y + 1.0) * tile)

## The node tree of one room, not yet saved.
func build_room(ctx: BuildContext, plan: Dictionary, room: Dictionary, tile_set: TileSet, kit: Dictionary) -> Node2D:
	var tile := tile_set.tile_size.x
	var id := JsonUtil.to_str(room["id"])
	var size := _cell(room["size"])
	var root := Node2D.new()
	root.name = "Room"
	SceneUtil.attach_script(root, ROOM_SCRIPT)
	root.set("map_id", StringName(id))
	root.set("room_size", size)
	root.set("tile_size", tile)
	root.set("grid_cell", _cell(room["cell"]))
	root.set("kind", JsonUtil.to_str(room.get("kind", "corridor")))
	root.set("is_interior", true)  # a cave: no day and night down here
	root.set("music_asset_id", JsonUtil.to_str(ctx.section("sounds").get("music_map", "")))

	var view: Array = ctx.config.get("resolution", [640, 360])
	var background := Parallax.build(ctx, Vector2(size * tile), Vector2(JsonUtil.to_float(view[0]), JsonUtil.to_float(view[1])))
	if background != null:
		root.add_child(background)
	var layers := {}
	for layer_name in LAYERS:
		var layer := TileMapLayer.new()
		layer.name = layer_name
		layer.tile_set = tile_set
		layer.collision_enabled = SOLID_LAYERS.has(layer_name)
		if layer_name == "Foreground":
			layer.z_index = 10
		root.add_child(layer)
		layers[layer_name] = layer
	paint(JsonUtil.to_array(room["tiles"]), layers, kit)

	var entities := Node2D.new()
	entities.name = "Entities"
	root.add_child(entities)
	var triggers := Node2D.new()
	triggers.name = "Triggers"
	root.add_child(triggers)
	var spawns := Node2D.new()
	spawns.name = "SpawnPoints"
	root.add_child(spawns)

	var arrival := Vector2.ZERO
	var has_arrival := false
	if room.has("spawn"):
		arrival = feet(_cell(room["spawn"]), tile)
		has_arrival = true
		var marker := MapUtil.add_marker(spawns, root, "default", arrival, true, "right")
		marker.set("side_view", true)
	for exit_spec in WorldPlan.list_of(room, "exits"):
		var at := add_exit(exit_spec, plan, size, tile, triggers, spawns, root)
		if not has_arrival:
			arrival = at
			has_arrival = true
	var player := MapUtil.place(PLAYER_SCENE, entities, root, arrival, "Player")
	if player != null:
		player.z_index = 5
	if ResourceLoader.exists(Objects.CAMERA_PATH):
		MapUtil.place(Objects.CAMERA_PATH, root, root, arrival, "Camera")
	_place_things(ctx, room, id, tile, entities, root)
	return root

## Paints the plan's rows into the layers: ground and breakable blocks on Ground, planks on
## Platforms, spikes on Hazards and ladders on Decoration.
static func paint(rows: Array, layers: Dictionary, kit: Dictionary) -> void:
	var ground: TileMapLayer = layers["Ground"]
	var platforms: TileMapLayer = layers["Platforms"]
	var hazards: TileMapLayer = layers["Hazards"]
	var decoration: TileMapLayer = layers["Decoration"]
	var top := JsonUtil.to_dict(kit["top"])
	var fill := JsonUtil.to_dict(kit["fill"])
	var ladder := JsonUtil.to_dict(kit["ladder"])
	var hazard := JsonUtil.to_dict(kit["hazard"])
	var breakable := JsonUtil.to_dict(kit["breakable"])
	for y in rows.size():
		var row := JsonUtil.to_str(rows[y])
		var above := JsonUtil.to_str(rows[y - 1]) if y > 0 else ""
		for x in row.length():
			var cell := Vector2i(x, y)
			match row[x]:
				"#":
					var covered := above != "" and (above[x] == "#" or above[x] == "B")
					MapUtil.put(ground, cell, fill if covered else top)
				"B":
					MapUtil.put(ground, cell, breakable if not breakable.is_empty() else top)
				"=":
					var plank := SideKit.plank(kit, x > 0 and row[x - 1] == "=", x + 1 < row.length() and row[x + 1] == "=")
					if not plank.is_empty():
						MapUtil.put(platforms, cell, plank)
				"^":
					if not hazard.is_empty():
						MapUtil.put(hazards, cell, hazard)
				"H", "T":
					if not ladder.is_empty():
						MapUtil.put(decoration, cell, ladder)
					if row[x] == "T":
						var cover := SideKit.plank(kit, true, true)
						if not cover.is_empty():
							MapUtil.put(platforms, cell, cover)

## The geometry of an exit on `edge` of a room `size` tiles large: where the exit node is, the
## rectangle of its area (relative to the node, just outside the room), where a player who comes
## in through it arrives, and the side that player looks to.
static func exit_layout(edge: String, cell: Vector2i, size: Vector2i, tile: int) -> Dictionary:
	var t := float(tile)
	match edge:
		"E":
			var floor_y := (cell.y + 1.0) * t
			return {"position": Vector2(size.x * t, floor_y), "area": Rect2(0.0, -3.0 * t, t, 3.0 * t), "arrival": Vector2((size.x - 1.5) * t, floor_y), "facing": "left"}
		"W":
			var floor_y := (cell.y + 1.0) * t
			return {"position": Vector2(0.0, floor_y), "area": Rect2(-t, -3.0 * t, t, 3.0 * t), "arrival": Vector2(1.5 * t, floor_y), "facing": "right"}
		"N":
			var x := (cell.x + 0.5) * t
			return {"position": Vector2(x, 0.0), "area": Rect2(-0.5 * t, -t, t, t), "arrival": Vector2(x, 1.9 * t), "facing": "right"}
	var x := (cell.x + 0.5) * t
	return {"position": Vector2(x, size.y * t), "area": Rect2(-0.5 * t, 0.0, t, t), "arrival": Vector2(x, size.y * t - 6.0), "facing": "right"}

## An RpgRoomExit of the plan with the spawn point beside it. Returns where its players arrive.
static func add_exit(exit_spec: Dictionary, plan: Dictionary, size: Vector2i, tile: int, triggers: Node, spawns: Node, root: Node2D) -> Vector2:
	var id := JsonUtil.to_str(exit_spec["id"])
	var edge := JsonUtil.to_str(exit_spec["edge"])
	var layout := exit_layout(edge, _cell(exit_spec["cell"]), size, tile)
	var target := room_by_id(plan, JsonUtil.to_str(exit_spec.get("to", "")))
	var node := build_exit(id, edge, room_path(target) if not target.is_empty() else "", JsonUtil.to_str(exit_spec.get("to_exit", "")), layout)
	SceneUtil.add(triggers, node, root, id)
	var arrival: Vector2 = layout["arrival"]
	var marker := MapUtil.add_marker(spawns, root, id, arrival, true, JsonUtil.to_str(layout["facing"]))
	marker.set("side_view", true)
	return arrival

## An exit node (not yet in a tree): an Area2D on the triggers layer that looks for the player.
static func build_exit(id: String, edge: String, target_room: String, target_exit: String, layout: Dictionary) -> Area2D:
	var node := Area2D.new()
	node.name = id
	SceneUtil.attach_script(node, EXIT_SCRIPT)
	MvBuild.set_layers(node, [6], [2])
	node.set("exit_id", id)
	node.set("edge", edge)
	node.set("target_room", target_room)
	node.set("target_exit", target_exit)
	node.position = layout["position"]
	var area: Rect2 = layout["area"]
	var shape := MvBuild.rect_shape(area.size)
	shape.position = area.get_center()
	node.add_child(shape)
	return node

# ---------------------------------------------------------------- what stands in a room

func _place_things(ctx: BuildContext, room: Dictionary, id: String, tile: int, entities: Node2D, root: Node2D) -> void:
	for gate in WorldPlan.list_of(room, "gates"):
		var marker := Marker2D.new()
		SceneUtil.attach_script(marker, GATE_MARK_SCRIPT)
		marker.set("ability", StringName(JsonUtil.to_str(gate.get("ability", ""))))
		marker.set("kind", JsonUtil.to_str(gate.get("kind", "ledge")))
		marker.position = feet(_cell(gate["cell"]), tile)
		SceneUtil.add(entities, marker, root, "Gate_%s" % JsonUtil.to_str(gate.get("ability", "")))
	if room.has("sign"):
		var sign_scene := _scene_tagged(ctx, "sign")
		if sign_scene != "":
			var sign_node := MapUtil.place(sign_scene, entities, root, feet(_cell(room["sign"]), tile), "Sign")
			if sign_node != null and ResourceLoader.exists(SIGN_PATH):
				sign_node.set("dialogue", load(SIGN_PATH))
	if room.has("npc"):
		var npc_scene := _npc_scene(ctx)
		if npc_scene != "":
			var npc := MapUtil.place(npc_scene, entities, root, feet(_cell(room["npc"]), tile), "Hermit")
			if npc != null:
				npc.set("entity_id", "%s_npc_001" % id)
				npc.set("start_facing", -1)
				if ResourceLoader.exists(END_PATH):
					npc.set("dialogue", load(END_PATH))
	if room.has("pickup"):
		var pickup := JsonUtil.to_dict(room["pickup"])
		var ability := JsonUtil.to_str(pickup.get("ability", ""))
		var node := MapUtil.place(Objects.ability_scene(ability), entities, root, feet(_cell(pickup["cell"]), tile), "Ability_%s" % ability)
		if node != null:
			node.set("entity_id", "%s_ability_001" % id)
	var items := JsonUtil.to_array(room.get("items", []))
	for i in items.size():
		var item := MapUtil.place(Objects.item_scene(i), entities, root, feet(_cell(items[i]), tile), "Item%d" % (i + 1))
		if item != null:
			item.set("entity_id", "%s_item_%03d" % [id, i + 1])
	_place_enemies(ctx, room, id, tile, entities, root)
	if room.has("chest"):
		var entry := ObjectEntries.chest_entry(ctx)
		if not entry.is_empty() and not JsonUtil.to_bool(entry.get("fallback", false)):
			var entry_id: String = entry["id"]
			var chest := MapUtil.place(ObjectIndex.scene_path(entry_id), entities, root, feet(_cell(room["chest"]), tile), "Chest")
			if chest != null:
				chest.set("entity_id", "%s_chest_001" % id)
				chest.set("loot", SeedUtil.dict_array([{"item_id": "potion", "qty": 1}]))
				chest.set("gold", 20)

## The enemies of the plan (the kinds the packs have take turns), and in the guardian's room the
## guardian with a gate in each side exit that opens when it is defeated. A project without any
## enemy art gets the guardian's ability as a pickup where the guardian would stand.
func _place_enemies(ctx: BuildContext, room: Dictionary, id: String, tile: int, entities: Node2D, root: Node2D) -> void:
	var recipe := EnemyRecipes.new()
	var kinds := recipe.entries(ctx)
	var cells := JsonUtil.to_array(room.get("enemies", []))
	var offset := absi(hash(id)) % maxi(1, kinds.size())
	for i in cells.size():
		var scene := recipe.scene_for(ctx, offset + i)
		if scene == "" or not ResourceLoader.exists(scene):
			break
		var at := feet(_cell(cells[i]), tile)
		var kind := JsonUtil.to_str(kinds[(offset + i) % kinds.size()]["kind"])
		if kind == "flyer":
			at.y -= FLYER_LIFT_TILES * tile
		var enemy := MapUtil.place(scene, entities, root, at, "Enemy%d" % (i + 1))
		if enemy != null:
			enemy.set("entity_id", "%s_enemy_%03d" % [id, i + 1])
	if not room.has("guardian"):
		return
	var spec := JsonUtil.to_dict(room["guardian"])
	var grants := JsonUtil.to_str(spec.get("grants", ""))
	var where := feet(_cell(spec["cell"]), tile)
	var guardian_scene := recipe.guardian_scene(ctx)
	if guardian_scene == "" or not ResourceLoader.exists(guardian_scene):
		if grants != "":
			var pickup := MapUtil.place(Objects.ability_scene(grants), entities, root, where, "Ability_%s" % grants)
			if pickup != null:
				pickup.set("entity_id", "%s_ability_001" % id)
		return
	var guardian_id := "%s_guardian" % id
	var guardian := MapUtil.place(guardian_scene, entities, root, where, "Guardian")
	if guardian != null:
		guardian.set("entity_id", guardian_id)
		guardian.set("grants", StringName(grants))
	var size := _cell(room["size"])
	for exit_spec in WorldPlan.list_of(room, "exits"):
		var edge := JsonUtil.to_str(exit_spec["edge"])
		if edge != "E" and edge != "W":
			continue
		var cell := _cell(exit_spec["cell"])
		var gate := StaticBody2D.new()
		SceneUtil.attach_script(gate, GATE_SCRIPT)
		gate.set("entity_id", "%s_gate_%s" % [id, edge.to_lower()])
		gate.set("open_when", "flag:%s.defeated" % guardian_id)
		gate.set("size", Vector2(tile, tile * 3))
		gate.position = Vector2((size.x - 0.5 if edge == "E" else 0.5) * tile, (cell.y + 1.0) * tile)
		SceneUtil.add(entities, gate, root, "Gate_%s" % edge)

## The scene of the first object tagged `tag` (a sign), or "".
static func _scene_tagged(ctx: BuildContext, tag: String) -> String:
	for e in ObjectEntries.entries(ctx):
		var tags: Array = e["tags"]
		var entry_id: String = e["id"]
		if tags.has(tag) and ResourceLoader.exists(ObjectIndex.scene_path(entry_id)):
			return ObjectIndex.scene_path(entry_id)
	return ""

## The NPC of the last room: the starter NPC, else any NPC character, else the fallback built
## from the player's sprite. "" when none exists.
static func _npc_scene(ctx: BuildContext) -> String:
	var wanted := JsonUtil.to_str(ctx.section("starter").get("npc", ""))
	if wanted != "" and ResourceLoader.exists(ActorRecipes.character_scene_path(wanted)):
		return ActorRecipes.character_scene_path(wanted)
	for a in ctx.catalog.assets_by_role("NPC"):
		var npc_id: String = a["id"]
		if ResourceLoader.exists(ActorRecipes.character_scene_path(npc_id)):
			return ActorRecipes.character_scene_path(npc_id)
	return ActorRecipes.FALLBACK_NPC_PATH if ResourceLoader.exists(ActorRecipes.FALLBACK_NPC_PATH) else ""

# ---------------------------------------------------------------- the seeded dialogue

static func _line(line_id: String, speaker: String, text: String, next: String, events: Array) -> Resource:
	var line := SeedUtil.make(DLG_LINE)
	line.set("id", StringName(line_id))
	line.set("speaker", speaker)
	line.set("text", text)
	line.set("next", StringName(next))
	line.set("events", PackedStringArray(events))
	return line

static func _dialogue(lines: Array) -> Resource:
	var res := SeedUtil.make(DLG_RES)
	var res_lines: Array = res.get("lines")
	res_lines.assign(lines)
	return res

## The sign of the first room and the hermit of the last one (user_seed: written once).
func _seed_dialogue(ctx: BuildContext, issues: Array) -> void:
	if not FileAccess.file_exists(SIGN_PATH):
		var sign_text := _dialogue([
			_line("read", "", "Rest on a bench to save. Somewhere below, something guards what you need to go on.", "", []),
		])
		_save_seed(ctx, sign_text, SIGN_PATH, issues)
	if not FileAccess.file_exists(END_PATH):
		var end_text := _dialogue([
			_line("greet", "Hermit", "You made it all the way down here. Nobody has, in years.", "thanks", []),
			_line("thanks", "Hermit", "That is the end of the cave, and of this little game. Thank you for playing.", "", ["set_flag:%s=true" % END_FLAG, "emit:credits"]),
		])
		_save_seed(ctx, end_text, END_PATH, issues)

func _save_seed(ctx: BuildContext, res: Resource, path: String, issues: Array) -> void:
	var err := SeedUtil.save(res, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
