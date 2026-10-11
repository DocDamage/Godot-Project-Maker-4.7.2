class_name RpgFlameGun
extends RpgGun
## A short flame that never stops: it reaches a few tiles and burns through everything in them.

func _init() -> void:
	weapon = "flame"
	rate = 20.0
	bullets_per_shot = 1
	spread_deg = 10.0
	speed_tiles = 9.0
	range_tiles = 4.0
	damage = 1
	bullet_kind = "flame"
	pierce = true
