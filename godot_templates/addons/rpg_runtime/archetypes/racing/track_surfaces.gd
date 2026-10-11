class_name RpgTrackSurfaces
extends Node2D
## What a track is made of, cell by cell: the rows of the track's plan, one character a cell
## (`r` road, `s` the start line, `g` grass, `d` dirt, `o` oil, `b` a boost arrow, `.` nothing:
## grass). The track
## recipe writes it into the track's scene; a car asks it what it drives on. A track without
## this node is driven by what its tiles say (their `footstep`, as a walking player hears it).

const GROUP := &"rpg_track_surfaces"
const LETTERS := {"r": "road", "s": "road", "g": "grass", "d": "dirt", "o": "oil", "b": "boost", ".": "grass"}

## The size of a cell in px.
@export var cell: float = 16.0
@export var rows: PackedStringArray = PackedStringArray()

func _ready() -> void:
	add_to_group(GROUP)

func size_cells() -> Vector2i:
	return Vector2i(rows[0].length() if not rows.is_empty() else 0, rows.size())

## The surface of the cell (grass outside the track).
func at_cell(at_cell_xy: Vector2i) -> String:
	if at_cell_xy.y < 0 or at_cell_xy.y >= rows.size() or at_cell_xy.x < 0 or at_cell_xy.x >= rows[at_cell_xy.y].length():
		return "grass"
	var found: String = LETTERS.get(rows[at_cell_xy.y][at_cell_xy.x], "grass")
	return found

## The surface at a global point.
func at(point: Vector2) -> String:
	if cell <= 0.0:
		return "grass"
	var local := point - RpgUtil.world_position(self)
	return at_cell(Vector2i(floori(local.x / cell), floori(local.y / cell)))

## The rectangle of the whole track, in the coordinates this node is in.
func bounds() -> Rect2:
	return Rect2(position, Vector2(size_cells()) * cell)
