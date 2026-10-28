class_name RpgStation
extends Area2D
## A crafting station of a map (1.5.0, T18.14): a workbench, a stove, a forge... `interact` opens
## the crafting window on its tab, with the recipes whose `station` is this one's `station_id`.
## Its queue and its tray are kept by RpgCrafting under its `entity_id` (in the flags of the game
## state), so they are saved and go on working while the map is not shown. Layer: interactables
## (5).

## Which recipes it makes (RpgRecipe.station).
@export var station_id: StringName = &"workbench"
## The id its queue and tray are kept under; the node's path in its map when empty.
@export var entity_id: String = ""
## What its tab is called (a tr() key or text); the station id, capitalized, when empty.
@export var title: String = ""

func _ready() -> void:
	if collision_layer == 1:
		collision_layer = 0
		set_collision_layer_value(5, true)  # interactables
	collision_mask = 0
	var state := RpgUtil.state()
	if state != null:
		RpgCrafting.update(state, key())

## The key of its queue and tray.
func key() -> String:
	if entity_id != "":
		return entity_id
	var map := get_parent()
	while map != null and not (map is RpgMapRoot):
		map = map.get_parent()
	var where := String((map as RpgMapRoot).map_id) if map != null else ""
	return "%s/%s" % [where, name]

## What its tab says.
func tab_title() -> String:
	return tr(title) if title != "" else String(station_id).capitalize()

## `interact` (RpgInteraction calls it): the crafting window, on this station's tab.
func interact(_actor: Node = null) -> void:
	RpgCraftingMenu.open(self)
