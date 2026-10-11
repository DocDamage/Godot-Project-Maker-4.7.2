class_name RpgSpreadGun
extends RpgGun
## Five bullets in a fan: wide, and slower to fire.

func _init() -> void:
	weapon = "spread"
	rate = 4.0
	bullets_per_shot = 5
	spread_deg = 40.0
	speed_tiles = 14.0
	range_tiles = 0.0
	damage = 1
	bullet_kind = "bullet"
	pierce = false
