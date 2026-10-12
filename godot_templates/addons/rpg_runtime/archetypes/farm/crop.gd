class_name RpgCrop
extends Area2D
## One crop standing in a field (T17.05): a scene of `generated/scenes/farm/crops/`, placed by
## RpgField among the entities of the map so that it Y-sorts with the farmer. The field keeps
## what it is (the data); this node only shows it and, when it is ripe, can be picked with
## `interact` (layer 5, the interactables).
##
## Its picture is the child `Visual`: a Sprite2D over a growth strip (one frame a stage), or the
## drawn stand-in, a `Stem` that grows and a `Fruit` that is there when the crop is ripe.

## Asked to be harvested (the field does it: it knows the cell and the inventory).
signal picked(cell: Vector2i)

const WITHERED := Color(0.55, 0.45, 0.3)

@export var crop_id: String = ""
var cell := Vector2i.ZERO
var ripe := false
var withered := false
var stage := 0

## Shows stage `index` of `count`, ripe or withered.
func show_stage(index: int, count: int, is_ripe: bool, is_withered: bool) -> void:
	stage = clampi(index, 0, maxi(1, count) - 1)
	ripe = is_ripe and not is_withered
	withered = is_withered
	var sprite := get_node_or_null("Visual") as Sprite2D
	if sprite != null:
		sprite.frame = clampi(stage, 0, maxi(1, sprite.hframes * sprite.vframes) - 1)
	var stem := get_node_or_null("Visual/Stem") as Node2D
	if stem != null:
		stem.scale = Vector2(1.0, lerpf(0.25, 1.0, float(stage) / maxf(1.0, float(count - 1))))
	var fruit := get_node_or_null("Visual/Fruit") as CanvasItem
	if fruit != null:
		fruit.visible = ripe
	modulate = WITHERED if withered else Color.WHITE
	var shape := get_node_or_null("Shape") as CollisionShape2D
	if shape != null:
		shape.set_deferred(&"disabled", not ripe)

## `interact` on a ripe crop harvests it (RpgInteraction calls this).
func interact(_actor: Node = null) -> void:
	if ripe:
		picked.emit(cell)
