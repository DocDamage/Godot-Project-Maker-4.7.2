class_name RpgRaceView
extends Node
## How an isometric race is seen (T17.15): the child `View` of a track that is painted on
## diamonds. A track seen from above has none, and everything below is then the plan itself.
##
## A race is driven on the flat plan of its track, whatever the view: the cars, the barriers,
## the checkpoints, the waypoints, the pickups and the weapons all have the positions the plan
## gave them (px of the plan, x east and y south), and the physics of a car (RpgCarPhysics, its
## body and what it bumps into) never hears of the view. Only what is *drawn* is somewhere else:
## this node says where. A square of the plan `cell_px` wide, with its corner at `origin`, is
## one diamond of the map (`footprint`), laid out as RpgIso lays out the cells of every
## isometric map: east runs down and to the right of the screen, south down and to the left.
##
##     var view := RpgRaceView.of(car)            # null on a track seen from above
##     view.to_screen(car.position)               # where the car is drawn
##     view.screen_heading(car.heading)           # the way it points there
##     view.plan_vector(stick)                    # a direction of the screen, in the plan
##
## A car heading east in the plan points down and to the right of the screen, and what the
## player sees is squeezed in height, as the genre has it.

## The name of the node in a track's scene.
const NODE := "View"

## The diamond of the map, in px.
@export var footprint: Vector2i = Vector2i(64, 32)
## How many px of the plan one diamond is wide and high.
@export var cell_px: float = 48.0
## The point of the plan that is the top corner of the cell (0, 0) of the map.
@export var origin: Vector2 = Vector2.ZERO

## The view of the track `node` is in (a sibling `View` of it or of one of its parents), or
## null: the track is seen from above.
static func of(node: Node) -> RpgRaceView:
	var at := node
	while at != null:
		var found := at.get_node_or_null(NODE)
		if found is RpgRaceView:
			return found as RpgRaceView
		at = at.get_parent()
	return null

## A point of the plan in cells of the map: (1.5, 0.5) is the middle of the cell (1, 0).
func grid_point(plan: Vector2) -> Vector2:
	return (plan - origin) / cell_px if cell_px > 0.0 else Vector2.ZERO

## How a step of the plan looks on the screen (a direction, a velocity, a length along it).
func screen_vector(plan: Vector2) -> Vector2:
	if cell_px <= 0.0:
		return Vector2.ZERO
	return (plan.x * RpgIso.step("e", footprint) + plan.y * RpgIso.step("s", footprint)) / cell_px

## Where a point of the plan is drawn.
func to_screen(plan: Vector2) -> Vector2:
	# the middle of the cell (0, 0) is the grid's point (0.5, 0.5)
	return RpgIso.cell_to_screen(Vector2i.ZERO, footprint) + screen_vector(plan - origin - Vector2(cell_px, cell_px) * 0.5)

## The point of the plan that is drawn at `screen`.
func to_plan(screen: Vector2) -> Vector2:
	return origin + RpgIso.grid_point(screen, footprint) * cell_px

## The step of the plan that looks like `screen` (the stick of *absolute* steering).
func plan_vector(screen: Vector2) -> Vector2:
	return to_plan(screen) - to_plan(Vector2.ZERO)

## The way something that heads along `rad` in the plan points on the screen (rad, 0 is to the
## right, a quarter turn clockwise is down).
func screen_heading(rad: float) -> float:
	return screen_vector(Vector2.from_angle(rad)).angle()

## The heading in the plan that points along `rad` on the screen.
func plan_heading(rad: float) -> float:
	return plan_vector(Vector2.from_angle(rad)).angle()

## How long one px of the plan is on the screen, along the axes of the map.
func scale_px() -> float:
	return screen_vector(Vector2.RIGHT).length()

## What is drawn in front of what: a greater number is nearer the camera. Things that stand up
## (a car, a tree) take it as their `z_index`; it is the row of diamonds across the screen.
func depth(plan: Vector2) -> int:
	var g := grid_point(plan)
	return floori(g.x + g.y)

## The rectangle of the screen around a rectangle of the plan.
func screen_rect(plan: Rect2) -> Rect2:
	var out := Rect2(to_screen(plan.position), Vector2.ZERO)
	for corner: Vector2 in [Vector2(plan.end.x, plan.position.y), plan.end, Vector2(plan.position.x, plan.end.y)]:
		out = out.expand(to_screen(corner))
	return out

## The corners of a rectangle of the plan on the screen, in the order of the rectangle's own
## (top left, top right, bottom right, bottom left of the plan).
func screen_corners(plan: Rect2) -> PackedVector2Array:
	return PackedVector2Array([to_screen(plan.position), to_screen(Vector2(plan.end.x, plan.position.y)), to_screen(plan.end), to_screen(Vector2(plan.position.x, plan.end.y))])
