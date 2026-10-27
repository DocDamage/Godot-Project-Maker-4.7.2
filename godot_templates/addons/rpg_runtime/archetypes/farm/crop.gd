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
## Asked to be cleared away by hand: a crop whose kind the game no longer has (T18.09).
signal cleared(cell: Vector2i)

const WITHERED := Color(0.55, 0.45, 0.3)
## A crop of a kind that was removed: its last picture, greyed (T18.09).
const GONE := Color(0.5, 0.5, 0.5, 0.85)

@export var crop_id: String = ""
var cell := Vector2i.ZERO
var ripe := false
var withered := false
var stage := 0
## True for a crop of a kind the game no longer has: `interact` clears it.
var gone := false

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

## The picture it shows now, to be shown again when its kind is gone: [texture path, hframes,
## vframes, frame] of its `Visual` sprite, or [] for the drawn stand-in.
func look() -> Array:
	var sprite := get_node_or_null("Visual") as Sprite2D
	if sprite == null or sprite.texture == null or sprite.texture.resource_path == "":
		return []
	return [sprite.texture.resource_path, sprite.hframes, sprite.vframes, sprite.frame]

## Shows `last` (what look() gave) greyed, or a drawn stem when there is none; `interact` clears
## it (T18.09).
func show_gone(last: Array) -> void:
	gone = true
	ripe = false
	withered = true
	var known := last.size() == 4 and ResourceLoader.exists(str(last[0]))
	var sprite := get_node_or_null("Visual") as Sprite2D
	if sprite == null and known:
		sprite = Sprite2D.new()
		sprite.name = "Visual"
		add_child(sprite)
	if sprite != null and known:
		sprite.texture = load(str(last[0])) as Texture2D
		sprite.hframes = maxi(1, RpgUtil.to_int(last[1], 1))
		sprite.vframes = maxi(1, RpgUtil.to_int(last[2], 1))
		sprite.frame = clampi(RpgUtil.to_int(last[3]), 0, sprite.hframes * sprite.vframes - 1)
		if sprite.offset == Vector2.ZERO and sprite.centered:
			sprite.offset = Vector2(0.0, -float(sprite.texture.get_height()) / float(sprite.vframes) / 2.0)
	elif get_node_or_null("Visual") == null:
		var stem := Polygon2D.new()
		stem.name = "Visual"
		stem.polygon = PackedVector2Array([Vector2(-1, 0), Vector2(1, 0), Vector2(1, -8), Vector2(-1, -8)])
		stem.color = Color(0.4, 0.35, 0.25)
		add_child(stem)
	modulate = GONE
	var shape := get_node_or_null("Shape") as CollisionShape2D
	if shape == null:
		shape = CollisionShape2D.new()
		shape.name = "Shape"
		var box := RectangleShape2D.new()
		box.size = Vector2(12, 12)
		shape.shape = box
		shape.position = Vector2(0, -6)
		add_child(shape)
		collision_layer = 0
		set_collision_layer_value(5, true)  # interactables
		collision_mask = 0
	shape.set_deferred(&"disabled", false)

## `interact` on a ripe crop harvests it (RpgInteraction calls this); on a crop whose kind is
## gone it clears it away.
func interact(_actor: Node = null) -> void:
	if gone:
		cleared.emit(cell)
	elif ripe:
		picked.emit(cell)
