class_name RpgWallCalendar
extends Area2D
## The calendar on the wall of the farmhouse (T17.25). The farm's map recipe hangs it in the
## room of a new farm that has festivals (layer 5, the interactables; it blocks nothing: it is
## on the wall). `interact` opens the page of the season over the paused game
## (RpgFarmEvents.open_calendar). In a farm whose festivals were switched off afterwards it
## shows the date as a toast: the room is never built again, so the calendar stays on its wall.

## `interact` (RpgInteraction calls this).
func interact(_actor: Node = null) -> void:
	var events := RpgFarmEvents.current()
	if events != null:
		events.open_calendar()
		return
	var calendar := RpgCalendar.current()
	if calendar != null:
		RpgUtil.notify(RpgFarmHud.date_text(calendar))
