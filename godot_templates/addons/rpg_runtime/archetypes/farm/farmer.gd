class_name RpgFarmer
extends RpgActor
## The farmer (T17.04): the top-down player the turn-based and action kinds share (walking,
## interaction, doors), with the **tile ahead**: the cell in front of it, shown by a frame on
## the ground (the child `TileFrame`), which the held item of the hotbar is used on.
##
## `use` uses what is held on the tile ahead: a ripe crop is harvested whatever is held, a tool
## works (and costs its energy only when it changed something), a seed is planted in tilled
## soil, food is eaten. `next_item`, `prev_item` and `hotbar_1` to `hotbar_10` choose the slot.
## A tool's use shows the animation of the sheet named after it (`hoe_down`, ...), else the
## attack, else the idle frame with the tool's icon over the hands (the child `ToolIcon`).
## At zero energy the farmer walks at SLOW of its speed and no tool works.
##
## **On diamonds** (T17.14) the tile ahead is the neighbour the farmer faces, asked as
## RpgActor.cell_ahead asks it (RpgIso.faced_cell): the one it last walked towards while that
## still agrees with its facing, else the one its facing names (up n, right e, down s, left w),
## with either setting of `iso_controls`. The frame on the ground is then that diamond.

const FRAME_NODE := "TileFrame"
const ICON_NODE := "ToolIcon"
const SLOW := 0.5

## The size of a cell when the map has no field to ask.
@export var tile_px: int = 16

## The farm's mode and the field of the map; found when they are needed (a test sets them).
var mode: RpgFarmMode = null
var field: RpgField = null

## True while a line is cast (RpgFishing sets it, T17.10): the farmer stands where it is
## beyond the rod's use time.
var fishing := false

var _busy := 0.0
var _base_speed := -1.0
var _frame: Node2D = null
var _icon: Sprite2D = null
## The frame as the player scene has it (a square and its width), and the diamond it was last
## given.
var _frame_square := PackedVector2Array()
var _frame_width := 1.0
var _frame_diamond := Vector2i.ZERO

func _ready() -> void:
	super._ready()
	_frame = get_node_or_null(FRAME_NODE) as Node2D
	if _frame is Line2D:
		_frame_square = (_frame as Line2D).points
		_frame_width = (_frame as Line2D).width
	_icon = get_node_or_null(ICON_NODE) as Sprite2D
	if _icon != null:
		_icon.visible = false
	var interaction := get_node_or_null("Interaction") as RpgInteraction
	if interaction != null:
		interaction.before = give_held

# ------------------------------------------------------------------ a gift

## True for an item that can be given: not a tool and not a bag of seeds (the people's plan
## gives nobody a taste for either).
func is_gift(item: StringName) -> bool:
	var found := the_mode()
	if item == &"" or found == null or found.tool_for(item) != null:
		return false
	return found.crops == null or found.crops.crop_of_seed(item) == ""

## `interact` on a person while a gift is held gives it (RpgFriendship.gift: one of the item
## leaves the bag, the points change by the person's taste). False when nothing was given: the
## target is nobody of the village, nothing that can be given is held, or the person has had
## two gifts this week; the farmer then talks as usual.
func give_held(target: Node) -> bool:
	var friends := RpgFriendship.current()
	var found := the_mode()
	if friends == null or found == null:
		return false
	var who := friends.person_of(target)
	var item := found.hotbar.held_item()
	if who == "" or not is_gift(item):
		return false
	var plan := target.get_node_or_null(RpgSchedule.NODE_NAME) as RpgSchedule
	if plan != null and plan.away():
		return false
	return friends.gift(who, item) != ""

# ------------------------------------------------------------------ the tile ahead

## One cell in the direction of a facing.
static func step_of(of_facing: String) -> Vector2i:
	match of_facing:
		"up":
			return Vector2i.UP
		"left":
			return Vector2i.LEFT
		"right":
			return Vector2i.RIGHT
	return Vector2i.DOWN

## The cell in front of `cell` for a facing.
static func ahead_of(cell: Vector2i, of_facing: String) -> Vector2i:
	return cell + step_of(of_facing)

## The cell the farmer stands in.
func cell() -> Vector2i:
	var at := RpgUtil.world_position(self)
	var found := the_field()
	if found != null:
		return found.cell_at(at)
	if is_inside_tree() and RpgIso.footprint_of(map_node()) != Vector2i.ZERO:
		return map_cell()  # a map of diamonds without a field (the farmhouse): the map is asked
	return Vector2i(floori(at.x / tile_px), floori(at.y / tile_px))

## The cell in front of the farmer: what a tool acts on. On squares it is the cell the facing
## points to; on diamonds the neighbour the farmer faces (RpgIso.faced_cell).
func tile_ahead() -> Vector2i:
	if diamond() == Vector2i.ZERO:
		return ahead_of(cell(), facing)
	return RpgIso.faced_cell(cell(), facing, look())

## The diamond of the cells the farmer works on: of the field's `Soil` layer, else of the map;
## Vector2i.ZERO on squares.
func diamond() -> Vector2i:
	var found := the_field()
	if found != null:
		return found.footprint()
	return RpgIso.footprint_of(map_node()) if is_inside_tree() else Vector2i.ZERO

## Turns the farmer to a cell beside the one it stands in, so that it is the tile ahead: the
## facing on squares; on diamonds the facing and where the farmer looks, as if it had taken a
## step towards that neighbour. False for a cell that is not one of the four neighbours.
func face_cell(target: Vector2i) -> bool:
	var by := target - cell()
	var footprint := diamond()
	for side in RpgIso.SIDES:
		var step: Vector2i = RpgIso.STEPS[side]
		if step != by:
			continue
		if footprint == Vector2i.ZERO:
			for way: String in RpgIso.FACING_SIDES.keys():
				if RpgIso.FACING_SIDES[way] == side:
					set_facing(way)
		else:
			_look = RpgIso.step(side, footprint)
			set_facing(RpgIso.facing_of(_look))
		return true
	return false

func the_field() -> RpgField:
	if field == null or not is_instance_valid(field):
		field = RpgField.current() if is_inside_tree() else null
	return field

func the_mode() -> RpgFarmMode:
	if mode == null or not is_instance_valid(mode):
		mode = RpgFarmMode.current()
	return mode

# ------------------------------------------------------------------ every frame

func _physics_process(delta: float) -> void:
	super._physics_process(delta)
	_place_frame()
	_pace()
	if _busy > 0.0:
		_busy -= delta
		if _busy <= 0.0:
			_end_use()
		return
	if not input_enabled or move_locked or RpgSequenceRunner.running():
		return
	if _pressed(&"use"):
		use_held()
	var found := the_mode()
	if found == null:
		return
	if _pressed(&"next_item"):
		found.hotbar.next()
	if _pressed(&"prev_item"):
		found.hotbar.prev()
	for i in RpgHotbar.SLOTS:
		if _pressed(StringName("hotbar_%d" % (i + 1))):
			found.hotbar.select(i)

static func _pressed(action: StringName) -> bool:
	return InputMap.has_action(action) and Input.is_action_just_pressed(action)

## The frame on the ground lies on the tile ahead while the map has a field.
func _place_frame() -> void:
	if _frame == null:
		return
	var found := the_field()
	_frame.visible = found != null and input_enabled
	if found != null:
		_shape_frame(found.footprint())
		_frame.global_position = found.cell_center(tile_ahead())

## The frame is the outline of a cell: the square of the scene, or the diamond of the field.
func _shape_frame(footprint: Vector2i) -> void:
	if footprint == _frame_diamond or not (_frame is Line2D):
		return
	_frame_diamond = footprint
	var outline := _frame as Line2D
	if footprint == Vector2i.ZERO:
		outline.points = _frame_square
		outline.width = _frame_width
		return
	var half := Vector2(footprint) / 2.0
	outline.points = PackedVector2Array([Vector2(0.0, -half.y), Vector2(half.x, 0.0), Vector2(0.0, half.y), Vector2(-half.x, 0.0)])
	# the camera of a game of large diamonds is drawn back: the line keeps its width on the screen
	var camera := get_node_or_null("Camera") as Camera2D
	var zoom := camera.zoom.x if camera != null else 1.0
	outline.width = _frame_width / zoom if zoom > 0.0 and zoom < 1.0 else _frame_width

## A farmer without energy walks slowly.
func _pace() -> void:
	var movement := component("Movement") as RpgMovement
	var found := the_mode()
	if movement == null or found == null:
		return
	if _base_speed < 0.0:
		_base_speed = movement.speed
	var wanted := _base_speed * (SLOW if found.energy.is_exhausted() else 1.0)
	if not is_equal_approx(movement.speed, wanted):
		movement.speed = wanted

# ------------------------------------------------------------------ using what is held

## Uses the held item on the tile ahead. False when nothing happened.
func use_held() -> bool:
	var found := the_mode()
	if found == null or _busy > 0.0:
		return false
	var plot := the_field()
	var target := tile_ahead()
	var item := found.hotbar.held_item()
	# a farm that fights (T17.24): the weapon is swung at what stands ahead, whatever lies there
	if found.fight != null and found.fight.is_weapon(item):
		return found.fight.swing(self, item)
	if plot != null and plot.state_of(target) == RpgField.RIPE:
		return plot.harvest(target)
	# a thing the workbench made (T18.15): put on the tile ahead
	if found.workshop != null and (found.workshop.enabled or found.workshop.cooking) and RpgFarmWorkshop.is_placeable(item):
		return found.workshop.place(item, target, plot)
	# a pail or shears (T18.12): used on the animal ahead, as `interact` with it would be
	if found.animals != null and found.animals.data != null and found.animals.data.tools().has(item):
		var animal := animal_ahead()
		if animal != null:
			animal.interact(self)
			return true
	var tool := found.tool_for(item)
	if tool != null:
		return _use_tool(found, plot, tool, target, item)
	var crop_id := found.crops.crop_of_seed(item) if found.crops != null else ""
	if crop_id != "" and plot != null and plot.state_of(target) == RpgField.SOIL:
		return _plant(found, plot, target, crop_id, item)
	return found.eat(item)

func _use_tool(found: RpgFarmMode, plot: RpgField, tool: RpgFarmTool, target: Vector2i, item: StringName) -> bool:
	if found.energy.is_exhausted():
		# the first try says so; with exhaustion on, the next ones end the day (T18.11)
		var ended := found.day_end != null and found.day_end.tried_exhausted()
		if not ended and (found.day_end == null or found.day_end.tries <= 1):
			RpgUtil.notify(RpgFarmStrings.t("FARM_TIRED"))
		return false
	if plot == null or not tool.can_use(plot, target):
		if tool is RpgFarmWateringCan and plot != null and plot.can_water(target):
			RpgUtil.notify(RpgFarmStrings.t("FARM_CAN_EMPTY"))
		return false
	var cost := tool.cost(plot, target)
	var sounds := RpgFarmSounds.count
	if not tool.apply(plot, target):
		return false
	found.energy.spend(cost)
	if RpgFarmSounds.count == sounds:  # a harvest with the sickle has sounded already
		RpgFarmSounds.play(tool.sound)
	_begin_use(tool, item)
	return true

func _plant(found: RpgFarmMode, plot: RpgField, target: Vector2i, crop_id: String, item: StringName) -> bool:
	var state := RpgUtil.state()
	if state == null or not state.inventory.has(item):
		return false
	if not plot.plant(target, crop_id):
		var crop_name := RpgUtil.to_str(found.crops.crop(crop_id).get("name", crop_id))
		RpgUtil.notify(RpgFarmStrings.t("FARM_WRONG_SEASON", [crop_name, RpgFarmStrings.season(RpgField.season_now())]))
		return false
	state.inventory.remove(item, 1)
	RpgFarmSounds.play(RpgFarmSounds.PLANT)
	return true

## The animal of the farm on the tile ahead, or null.
func animal_ahead() -> RpgFarmAnimal:
	var map := map_node()
	if map == null:
		return null
	var ahead := tile_ahead()
	for node in map.find_children("*", "CharacterBody2D", true, false):
		var animal := node as RpgFarmAnimal
		if animal != null and animal.visible and animal.map_cell() == ahead:
			return animal
	return null

## Shows the use of `tool` (the item `item`) as a tool's use is shown, without working a cell:
## what a swing of the weapon looks like (T17.24, RpgFarmFight.swing).
func show_use(tool: RpgFarmTool, item: StringName) -> void:
	_begin_use(tool, item)

## The farmer stands still for the tool's use time and shows its use.
func _begin_use(tool: RpgFarmTool, item: StringName) -> void:
	_busy = maxf(0.0, tool.use_time_s)
	if _busy <= 0.0:
		return
	move_locked = true
	move_dir(Vector2.ZERO)
	if hold_animation_any(tool.animation) or hold_animation("attack"):
		return
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(item) if state != null else null
	if _icon != null and def != null and def.icon != null:
		_icon.texture = def.icon
		_icon.visible = true

func _end_use() -> void:
	_busy = 0.0
	move_locked = fishing
	if animation_locked:
		release_animation()
	if _icon != null:
		_icon.visible = false

## True while a tool is being used.
func is_busy() -> bool:
	return _busy > 0.0
