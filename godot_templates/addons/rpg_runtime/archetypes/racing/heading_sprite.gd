class_name RpgHeadingSprite
extends Sprite2D
## The picture of a car seen from above. A sheet of N headings (16: steps of 22.5 degrees)
## shows the frame nearest the car's heading; the first frame points up and each next one is a
## step clockwise, row by row. A picture of one frame, drawn pointing up, is rotated instead.

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
