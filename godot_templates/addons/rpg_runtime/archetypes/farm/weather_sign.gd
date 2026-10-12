class_name RpgWeatherSign
extends StaticBody2D
## The sign by the farmhouse that tells tomorrow's weather (T17.11). Layers: world (1) +
## interactables (5). `interact` shows the forecast as a toast.

## `interact` (RpgInteraction calls this).
func interact(_actor: Node = null) -> void:
	RpgUtil.notify(reading())

## What the sign says now; "" in a game without weather.
func reading() -> String:
	var weather := RpgFarmWeather.current()
	return weather.forecast_text() if weather != null else ""
