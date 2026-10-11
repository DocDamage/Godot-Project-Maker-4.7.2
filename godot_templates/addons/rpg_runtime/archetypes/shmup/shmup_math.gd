class_name RpgShmupMath
extends RefCounted
## What follows from the orientation of a shoot-em-up, `vertical` (seen from the top, scrolling
## up) or `horizontal` (seen from the side, scrolling right): the way the ship looks, the axis of
## the scroller, the play area and where the ship starts. Kept apart from the mode and the ship,
## which both read it, so that neither script has to name the other.

const ORIENTATIONS: Array[String] = ["vertical", "horizontal"]

## The way a ship looks: up when the game scrolls up, right when it scrolls right.
static func forward_of(way: String) -> Vector2:
	return Vector2.RIGHT if way == "horizontal" else Vector2.UP

## The axis of the scroller (RpgArcadeScroller.axis) for an orientation.
static func axis_of(way: String) -> String:
	return "right" if way == "horizontal" else "up"

## Where the ship may fly, relative to the middle of a screen of `view` px. A vertical game is
## played in the middle of a wide screen, in an area four wide for every three high at most (the
## sides are left to the HUD, as an arcade board does); a horizontal game uses the whole screen.
static func play_area(view: Vector2, way: String) -> Rect2:
	var size := view
	if way != "horizontal":
		size.x = minf(view.x, floorf(view.y * 4.0 / 3.0))
	return Rect2(-size * 0.5, size)

## Where the ship starts, relative to the middle of the screen: near the bottom, or near the left.
static func start_offset(view: Vector2, way: String) -> Vector2:
	var area := play_area(view, way)
	if way == "horizontal":
		return Vector2(area.position.x + area.size.x * 0.15, 0.0)
	return Vector2(0.0, area.end.y - area.size.y * 0.15)
