class_name RpgLaserGun
extends RpgGun
## A beam: fast, strong, and it goes through what it hits.

func _init() -> void:
	weapon = "laser"
	rate = 3.0
	bullets_per_shot = 1
	spread_deg = 0.0
	speed_tiles = 28.0
	range_tiles = 0.0
	damage = 3
	bullet_kind = "laser"
	pierce = true
