class_name RpgWallCannon
extends RpgGunEnemy
## A cannon that is part of the scenery: closed, nothing hurts it; every `interval` seconds it
## opens for `open_s`, fires one shot at the soldier, and can be hit.

signal opened
signal closed

@export var interval: float = 3.0
@export var open_s: float = 1.2
const SHUT := Color(0.6, 0.6, 0.65)

var open := false
var _since := 0.0
var _fired := false

func _init() -> void:
	fixed = true

func _ready() -> void:
	super._ready()
	_show()

func vulnerable() -> bool:
	return open

func think(delta: float) -> void:
	var side := side_of_soldier()
	if side != 0:
		set_facing(side)
	_since += delta
	if not open and _since >= interval:
		_since = 0.0
		open = true
		_fired = false
		_show()
		opened.emit()
	elif open:
		if not _fired and _since >= open_s * 0.4:
			_fired = true
			fire_at_soldier()
		if _since >= open_s:
			_since = 0.0
			open = false
			_show()
			closed.emit()

func _show() -> void:
	if _driver.sprite != null:
		_driver.sprite.modulate = Color.WHITE if open else SHUT
	var visual := get_node_or_null("Visual") as CanvasItem
	if visual != null and _driver.sprite == null:
		visual.modulate = Color.WHITE if open else SHUT
