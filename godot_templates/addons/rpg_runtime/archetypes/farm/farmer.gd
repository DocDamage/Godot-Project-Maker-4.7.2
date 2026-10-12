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

func _ready() -> void:
	super._ready()
	_frame = get_node_or_null(FRAME_NODE) as Node2D
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
	return Vector2i(floori(at.x / tile_px), floori(at.y / tile_px))

## The cell in front of the farmer: what a tool acts on.
func tile_ahead() -> Vector2i:
	return ahead_of(cell(), facing)

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
		_frame.global_position = found.cell_center(tile_ahead())

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
	if plot != null and plot.state_of(target) == RpgField.RIPE:
		return plot.harvest(target)
	var tool := found.tool_for(item)
	if tool != null:
		return _use_tool(found, plot, tool, target, item)
	var crop_id := found.crops.crop_of_seed(item) if found.crops != null else ""
	if crop_id != "" and plot != null and plot.state_of(target) == RpgField.SOIL:
		return _plant(found, plot, target, crop_id, item)
	return found.eat(item)

func _use_tool(found: RpgFarmMode, plot: RpgField, tool: RpgFarmTool, target: Vector2i, item: StringName) -> bool:
	if found.energy.is_exhausted():
		RpgUtil.notify(RpgFarmStrings.t("FARM_TIRED"))
		return false
	if plot == null or not tool.can_use(plot, target):
		if tool is RpgFarmWateringCan and plot != null and plot.can_water(target):
			RpgUtil.notify(RpgFarmStrings.t("FARM_CAN_EMPTY"))
		return false
	var cost := tool.cost(plot, target)
	if not tool.apply(plot, target):
		return false
	found.energy.spend(cost)
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
	return true

## The farmer stands still for the tool's use time and shows its use.
func _begin_use(tool: RpgFarmTool, item: StringName) -> void:
	_busy = maxf(0.0, tool.use_time_s)
	if _busy <= 0.0:
		return
	move_locked = true
	move_dir(Vector2.ZERO)
	if hold_animation(tool.animation) or hold_animation("attack"):
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
