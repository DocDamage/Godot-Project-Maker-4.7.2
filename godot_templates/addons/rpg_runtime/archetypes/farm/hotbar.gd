class_name RpgHotbar
extends Node
## The hotbar of a farm (T17.04): the first ten stacks of the inventory the game has, one of
## them held. `next_item`, `prev_item` and the number keys choose (the farmer reads them). Tools,
## seeds and produce are items like any other. A child of the farm's mode.
##
## Which slot is held is kept in the flags of the game state (`farm.held`).

signal changed

const SLOTS := 10
const FLAG_ENTITY := "farm"
const FLAG_KEY := "held"

var held: int:
	get = get_held, set = select

var _own := 0  # in a test without a game state

func _ready() -> void:
	var bus := RpgUtil.events()
	if bus != null:
		bus.item_added.connect(_on_items)
		bus.item_removed.connect(_on_items)
		bus.game_loaded.connect(_on_loaded)

func _on_items(_item_id: StringName, _qty: int) -> void:
	changed.emit()

func _on_loaded(_slot: int) -> void:
	changed.emit()

func get_held() -> int:
	var state := RpgUtil.state()
	return clampi(RpgUtil.to_int(state.get_flag(FLAG_ENTITY, FLAG_KEY, 0)) if state != null else _own, 0, SLOTS - 1)

## Holds slot `index` (0 to 9); one beyond the ends wraps round.
func select(index: int) -> void:
	var wanted := posmod(index, SLOTS)
	if wanted == get_held():
		return
	_own = wanted
	var state := RpgUtil.state()
	if state != null:
		state.set_flag(FLAG_ENTITY, FLAG_KEY, wanted)
	changed.emit()

func next() -> void:
	select(get_held() + 1)

func prev() -> void:
	select(get_held() - 1)

## The item of a slot, or &"" for an empty one.
func item_at(index: int) -> StringName:
	var state := RpgUtil.state()
	if state == null or index < 0 or index >= mini(SLOTS, state.inventory.slots.size()):
		return &""
	return RpgUtil.to_name(state.inventory.slots[index].get("item_id", ""))

## How many of its item a slot holds.
func qty_at(index: int) -> int:
	var state := RpgUtil.state()
	if state == null or index < 0 or index >= mini(SLOTS, state.inventory.slots.size()):
		return 0
	return RpgUtil.to_int(state.inventory.slots[index].get("qty", 0))

## The item that is held, or &"".
func held_item() -> StringName:
	return item_at(get_held())

## Holds the slot of `item_id`. False when it is not among the ten.
func hold_item(item_id: StringName) -> bool:
	for i in SLOTS:
		if item_at(i) == item_id:
			select(i)
			return true
	return false
