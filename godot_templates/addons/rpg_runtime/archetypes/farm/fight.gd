class_name RpgFarmFight
extends Node
## Fighting on a farm (T17.24). A child of the farm's mode (`Fight`), made by it like the
## weather and the end of the day; it does nothing in a farm that does not fight (`enabled`
## off: the mode's `fights`, which the recipe sets for a farm with *Combat* on or a cave).
##
## * **The cave** is an added map of the kind `cave` (recipes/farm/added_maps_recipe.gd) with
##   the action RPG's enemies (archetypes/arpg/, which a farm that fights has), each remembered
##   as `<id of the map>_enemy_<n>`. A defeated one stays away for the rest of the day (the
##   flag `defeated`, RpgPersistent) and is back the next morning: the flags are cleared then.
## * **What an enemy leaves**: besides its own loot, one of the things of a cave (the forage
##   entries with `maps: ["cave"]`), as a pickup (RpgPickup) where it fell: walked over, it is in
##   the bag, and it is sold in the bin or at the counter like anything found.
## * **The farmer** gets what the action RPG's player has of combat when a map is entered: a
##   `Health` (its hit points are the game's player stats), a `Hurtbox` (layer 9) and a `Blade`
##   (RpgFarmBlade, layer 7). They are made here, at run time, so that the player scene of a
##   farm that does not fight is what it was.
## * **The weapon** (`farm_sword`, written once by recipes/farm/farmer_recipe.gd) is sold at the
##   shop (a stock source) and kept like a tool. Held in the hotbar, `use` swings it
##   (`swing`): no energy is spent, and the blade can hit for a moment.
## * **Being defeated is passing out**: at 0 hit points the farmer drops, and a moment later the
##   day ends as it does at 2:00 (RpgDayEnd.pass_out): the farmer wakes at the bed with half the
##   energy, and with `pass_out_loss` a tenth of the money gone. Every morning the hit points
##   are full again.
##
## Nothing of this is kept beyond the flags of the game state, so a save gains no key.

signal knocked_out
## The farmer's hit points changed (a hit, the morning): the HUD's health bar follows.
signal health_changed(hp: int, max_hp: int)

const NODE_NAME := "Fight"
const HEALTH_NODE := "Health"
const HURTBOX_NODE := "Hurtbox"
const BLADE_NODE := "Blade"
## The item of the weapon, and what the shop asks for it (FarmBuild.WEAPON, WEAPON_PRICE).
const WEAPON := &"farm_sword"
const WEAPON_PRICE := 200
## The kind of an added map that is a cave (RpgForage.KIND_META), and the marks of the ids of
## its enemies.
const CAVE := "cave"
const MAP_PREFIX := "farm_map_"
const ENEMY_MARK := "_enemy_"
## Seconds the farmer cannot be hit again after a hit, and how long it lies before the day ends.
const INVULN_S := 0.6
const DOWN_S := 1.2
const KNOCKBACK := 140.0
const FLASH := Color(1.0, 0.35, 0.35)

## False: a farm that does not fight; nothing here does anything.
var enabled := false
## The weapon as a tool of the farmer: how long a swing takes and what it shows.
var weapon_tool: RpgFarmTool = null
## True from the hit that took the last hit point to the morning after.
var down := false
## The last thing an enemy left (tests look at it), or null.
var last_drop: RpgPickup = null

var _attached := false

## The fighting of the running game, or null in a game that is no farm or does not fight.
static func current() -> RpgFarmFight:
	var mode := RpgFarmMode.current()
	return mode.fight if mode != null and mode.fight != null and mode.fight.enabled else null

func _init() -> void:
	weapon_tool = RpgFarmTool.new()
	weapon_tool.id = WEAPON
	weapon_tool.energy_cost = 0
	weapon_tool.use_time_s = 0.3
	weapon_tool.animation = "attack"

## Listens to the maps, to the defeated enemies, to the mornings and to the loads, and puts the
## weapon into the shop. The mode calls it once the calendar exists; a second call changes
## nothing, and a farm that does not fight is not listened to.
func attach() -> void:
	if not enabled or _attached:
		return
	_attached = true
	var bus := RpgUtil.events()
	if bus != null:
		bus.map_entered.connect(_on_map)
		bus.entity_defeated.connect(_on_defeated)
		bus.game_loaded.connect(_on_loaded)
	var calendar := RpgCalendar.current()
	if calendar != null:
		calendar.day_began.connect(_on_morning)
	RpgFarmShop.add_stock_source(stock)

## The weapon leaves the shop with the mode (a mode made anew, a test).
func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		RpgFarmShop.remove_stock_source(stock)

## The shop's row of the weapon (a stock source of RpgFarmShop).
func stock(_season_name: String) -> Array:
	return [{"item_id": String(WEAPON), "price": WEAPON_PRICE}]

# ------------------------------------------------------------------ the farmer

func _player() -> Node2D:
	var router := RpgUtil.router()
	return router.current_map.get_player() if router != null and router.current_map != null else null

## Gives the farmer its health, its hurtbox and its blade, once. False when nobody is there
## or the farm does not fight.
func arm(who: Node2D) -> bool:
	if who == null or not enabled:
		return false
	var visual := who.get_node_or_null("Visual") as AnimatedSprite2D
	var frame := Vector2(16.0, 16.0)
	if visual != null and visual.sprite_frames != null and visual.sprite_frames.has_animation(visual.animation):
		var texture := visual.sprite_frames.get_frame_texture(visual.animation, 0)
		if texture != null:
			frame = texture.get_size()
	var router := RpgUtil.router()
	var tile := float(RpgUtil.map_tile_px(router.current_map if router != null else null))
	var middle := Vector2(0.0, -frame.y * 0.5)
	var health := who.get_node_or_null(HEALTH_NODE) as RpgHealth
	if health == null:
		health = RpgHealth.new()
		health.name = HEALTH_NODE
		who.add_child(health)
	if not health.died.is_connected(_on_died):
		health.died.connect(_on_died)
	var hurtbox := who.get_node_or_null(HURTBOX_NODE) as RpgHurtbox
	if hurtbox == null:
		hurtbox = RpgHurtbox.new()
		hurtbox.name = HURTBOX_NODE
		hurtbox.team = &"player"
		hurtbox.invuln_s = INVULN_S
		_layers(hurtbox, 9, 0)
		hurtbox.monitoring = false
		hurtbox.monitorable = true
		hurtbox.position = middle
		hurtbox.add_child(_shape(Vector2(clampf(frame.x * 0.5, 6.0, maxf(6.0, tile * 0.75)), clampf(frame.y * 0.6, 8.0, maxf(8.0, tile * 1.25))), false))
		who.add_child(hurtbox)
		hurtbox.damaged.connect(_on_hurt.bind(who))  # once: with the hurtbox it is made with
	if who.get_node_or_null(BLADE_NODE) == null:
		var blade := RpgFarmBlade.new()
		blade.name = BLADE_NODE
		blade.team = &"player"
		blade.center = middle
		var limit := maxf(4.0, tile * 0.75)
		blade.reach = Vector2(minf(frame.x * 0.5, limit), minf(frame.y * 0.5, limit))
		_layers(blade, 7, 10)
		blade.position = middle
		blade.add_child(_shape(Vector2(tile, tile) * 0.9, true))
		who.add_child(blade)
	return true

static func _layers(area: Area2D, layer: int, mask: int) -> void:
	area.collision_layer = 0
	area.collision_mask = 0
	area.set_collision_layer_value(layer, true)
	if mask > 0:
		area.set_collision_mask_value(mask, true)

static func _shape(size: Vector2, disabled: bool) -> CollisionShape2D:
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = size
	shape.shape = rect
	shape.disabled = disabled
	return shape

## The farmer's health (its hit points are the game's player stats), or null.
func health_of(who: Node) -> RpgHealth:
	return who.get_node_or_null(HEALTH_NODE) as RpgHealth if who != null else null

# ------------------------------------------------------------------ the weapon

## True for an item that is swung: the farm's weapon.
func is_weapon(item_id: StringName) -> bool:
	return enabled and item_id == WEAPON

## Swings the weapon `item_id` the farmer holds: the blade can hit what stands ahead for a
## moment, and the farmer shows the swing (RpgFarmer.show_use). False when nothing was swung
## (the farm does not fight, the farmer lies down, it has no blade).
func swing(who: RpgFarmer, item_id: StringName) -> bool:
	if not enabled or down or who == null:
		return false
	arm(who)
	var blade := who.get_node_or_null(BLADE_NODE) as RpgFarmBlade
	if blade == null:
		return false
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(item_id) if state != null else null
	# on diamonds the blade goes to the cell the farmer faces (the frame on the ground shows it)
	var toward := Vector2.ZERO
	var plot := who.the_field()
	if who.diamond() != Vector2i.ZERO and plot != null:
		toward = plot.cell_center(who.tile_ahead()) - RpgUtil.world_position(who)
	blade.swing(who.facing, RpgFarmBlade.bonus_of(def), toward)
	who.show_use(weapon_tool, item_id)
	RpgUtil.emit(&"attack_started", [who])
	return true

# ------------------------------------------------------------------ hits and defeat

func _on_hurt(info: RpgDamageInfo, who: Node2D) -> void:
	_tell_health()
	if not is_instance_valid(who):
		return
	var movement: RpgMovement = null
	if who.has_method(&"component"):
		var found: Variant = who.call(&"component", "Movement")
		if found is RpgMovement:
			movement = found
	if movement != null and info != null:
		movement.external_velocity = info.knockback.normalized() * KNOCKBACK if info.knockback.length() > 0.0 else Vector2.ZERO
	var sprite := who.get_node_or_null("Visual") as CanvasItem
	if sprite != null:
		sprite.modulate = FLASH
		var fade := sprite.create_tween()
		fade.tween_property(sprite, "modulate", Color.WHITE, INVULN_S * 0.5)

## The last hit point is gone: the farmer drops, and after DOWN_S the day ends as at 2:00.
func _on_died() -> void:
	if not begin_down():
		return
	var tree := RpgUtil.tree()
	if tree != null:
		await tree.create_timer(DOWN_S).timeout
	var mode := get_parent() as RpgFarmMode
	if mode != null and mode.day_end != null:
		mode.day_end.pass_out()

## The farmer drops: it lies down and takes no input. False when it lies down already.
func begin_down() -> bool:
	if down:
		return false
	down = true
	knocked_out.emit()
	var who := _player()
	if who != null and who.get("input_enabled") != null:
		who.set("input_enabled", false)
	return true

## Full hit points, and nobody lies down any longer (the morning, or a game that was loaded).
func heal_full() -> void:
	down = false
	var state := RpgUtil.state()
	if state != null:
		state.player_stats.hp = RpgUtil.max_hp(state.player_stats)
	var who := _player()
	var health := health_of(who)
	if health != null:
		health.revive()
	if who != null and who.get("input_enabled") != null:
		who.set("input_enabled", true)
	var sprite := who.get_node_or_null("Visual") as CanvasItem if who != null else null
	if sprite != null:
		sprite.modulate = Color.WHITE
	_tell_health()

## The farmer's hit points as they are now: [hp, max].
static func hit_points() -> Array[int]:
	var state := RpgUtil.state()
	if state == null:
		return [0, 0]
	return [state.player_stats.hp, RpgUtil.max_hp(state.player_stats)]

func _tell_health() -> void:
	var now := hit_points()
	health_changed.emit(now[0], now[1])

# ------------------------------------------------------------------ the enemies of a cave

## True for the id of an enemy of an added map (`farm_map_<n>_enemy_<m>`).
static func is_cave_enemy(entity_id: String) -> bool:
	return entity_id.begins_with(MAP_PREFIX) and entity_id.contains(ENEMY_MARK)

## Brings every defeated enemy of the caves back: their flags `defeated` are cleared. Returns
## how many came back.
func revive_enemies() -> int:
	var state := RpgUtil.state()
	if state == null:
		return 0
	var count := 0
	for key: Variant in state.flags.keys():
		var id := str(key)
		if is_cave_enemy(id) and RpgUtil.to_bool(state.get_flag(id, "defeated", false)):
			state.set_flag(id, "defeated", false)
			count += 1
	return count

## The things of a cave (the forage entries whose `maps` name it): their item ids.
func cave_things() -> Array[StringName]:
	var out: Array[StringName] = []
	var mode := get_parent() as RpgFarmMode
	var forage := mode.forage if mode != null and mode.forage != null else RpgForage.current()
	if forage == null:
		return out
	forage.table()
	for entry in forage.things:
		if RpgUtil.to_array(entry.get("maps", [])).has(CAVE):
			out.append(StringName(RpgUtil.to_str(entry.get("item", ""))))
	return out

## A node of `under` (itself among them) whose `entity_id` is `id`, or null.
static func _find_entity(under: Node, id: String) -> Node2D:
	if under is Node2D and str(under.get("entity_id")) == id:
		return under as Node2D
	for child in under.get_children():
		var found := _find_entity(child, id)
		if found != null:
			return found
	return null

## What a defeated enemy of a cave leaves where it fell: one of the things of a cave, as a
## pickup beside its own loot. Returns the pickup, or null.
func drop_for(entity_id: String) -> RpgPickup:
	var router := RpgUtil.router()
	var map: Node = router.current_map if router != null else null
	var state := RpgUtil.state()
	var things := cave_things()
	if map == null or state == null or things.is_empty() or not is_cave_enemy(entity_id):
		return null
	var enemy := _find_entity(map, entity_id)
	if enemy == null or enemy.get_parent() == null:
		return null
	var item := things[state.rng.randi_range(0, things.size() - 1)]
	var def: RpgItemDefinition = state.items.get(item)
	var pickup := RpgPickup.create(item, 1, def.icon if def != null else null)
	pickup.name = "CaveDrop_%s" % entity_id
	pickup.position = enemy.position + Vector2(0.0, 4.0)
	enemy.get_parent().add_child.call_deferred(pickup)
	last_drop = pickup
	var enemy_name := entity_id
	var defined: Variant = enemy.get("definition")
	if defined is RpgEnemyDefinition:
		var who: RpgEnemyDefinition = defined
		if who.display_name != "":
			enemy_name = who.display_name
	RpgUtil.notify(RpgFarmCaveStrings.t("FARM_CAVE_LEFT", [enemy_name, RpgFarmStrings.item_name(item)]))
	return pickup

# ------------------------------------------------------------------ the events

func _on_map(_id: StringName) -> void:
	arm(_player())

## A game that was loaded has the hit points it was saved with; nobody lies down.
func _on_loaded(_slot: int) -> void:
	down = false
	arm(_player())
	_tell_health()

func _on_morning(_day: int) -> void:
	revive_enemies()
	heal_full()

func _on_defeated(entity_id: String) -> void:
	if is_cave_enemy(entity_id):
		drop_for(entity_id)
