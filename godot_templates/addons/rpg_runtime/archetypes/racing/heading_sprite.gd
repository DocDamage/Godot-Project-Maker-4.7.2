class_name RpgHeadingSprite
extends Sprite2D
## The picture of a car seen from above. A sheet of N headings (16: steps of 22.5 degrees)
## shows the frame nearest the car's heading; the first frame points up and each next one is a
## step clockwise, row by row. A picture of one frame, drawn pointing up, is rotated instead.
##
## The heading is the one **on the screen**. Seen from above that is the car's own. On a track
## seen at an angle (T17.15) the car gives the way its heading looks there
## (RpgRaceView.screen_heading): a car that heads east in the plan points down and to the right,
## and a car of eight headings (`taxi_N.png` to `taxi_NW.png`, N up on the screen) shows its
## `SE`. Eight headings turn in steps of 45 degrees, which shows; the car steers smoothly
## underneath.

## How many headings the sheet has; 1 for a single picture that is rotated.
@export var headings: int = 1

var heading := -PI * 0.5

func _ready() -> void:
	show_heading(heading)

## The frame for a heading (0 for a picture that is rotated).
func frame_for(rad: float) -> int:
	return RpgCarPhysics.heading_frame(rad, headings)

## Shows the car pointing along `rad` (0 is to the right, a quarter turn clockwise is down).
func show_heading(rad: float) -> void:
	heading = rad
	if headings > 1:
		rotation = 0.0
		frame = clampi(frame_for(rad), 0, maxi(0, hframes * vframes - 1))
	else:
		rotation = rad + PI * 0.5
