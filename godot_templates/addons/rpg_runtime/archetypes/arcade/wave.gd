class_name RpgArcadeWave
extends RefCounted
## One wave of a stage: `count` enemies of one kind in a formation, and what makes them appear.
## A stage's waves are written by the kind's planner into game/data/stages.json; the runtime only
## reads them, so a run is the same every time.

const FORMATIONS: Array[String] = ["line", "column", "v", "circle", "sine"]
const TRIGGERS: Array[String] = ["start", "progress", "time", "after"]

var id := ""
## The enemy's id in the kind's own table, and (or) the scene to instance.
var enemy := ""
var scene := ""
var formation := "line"
var count := 1
## Px between two enemies of the formation.
var gap := 24.0
## Seconds between two of them appearing; 0 puts the whole formation there at once.
var interval := 0.0
## Where the middle of the formation is: on the screen (relative to the camera) or in the stage.
var position := Vector2.ZERO
var anchor := "screen"
## "start" (at once), "progress" (the scroller has come `at` px), "time" (`at` seconds into the
## stage) or "after" (the wave `after` is cleared).
var trigger := "start"
var at := 0.0
var after := ""
## The scroller waits until this wave is cleared.
var blocking := false
## Points per enemy when the enemy does not say.
var points := 100
## A bonus for a formation of which every enemy was shot (none got away); 0 gives none.
var bonus := 0
## The whole entry of the wave: what a kind adds to it (a path, a drop) is read from here by
## its enemies.
var data: Dictionary = {}

static func from_dict(d: Dictionary) -> RpgArcadeWave:
	var wave := RpgArcadeWave.new()
	wave.id = RpgUtil.to_str(d.get("id", ""))
	wave.enemy = RpgUtil.to_str(d.get("enemy", ""))
	wave.scene = RpgUtil.to_str(d.get("scene", ""))
	var shape := RpgUtil.to_str(d.get("formation", "line"))
	wave.formation = shape if FORMATIONS.has(shape) else "line"
	wave.count = maxi(1, RpgUtil.to_int(d.get("count", 1), 1))
	wave.gap = RpgUtil.to_float(d.get("gap", 24.0), 24.0)
	wave.interval = maxf(0.0, RpgUtil.to_float(d.get("interval", 0.0)))
	var where := RpgUtil.to_array(d.get("position", []))
	if where.size() >= 2:
		wave.position = Vector2(RpgUtil.to_float(where[0]), RpgUtil.to_float(where[1]))
	wave.anchor = "stage" if RpgUtil.to_str(d.get("anchor", "screen")) == "stage" else "screen"
	var cause := RpgUtil.to_str(d.get("trigger", "start"))
	wave.trigger = cause if TRIGGERS.has(cause) else "start"
	wave.at = RpgUtil.to_float(d.get("at", 0.0))
	wave.after = RpgUtil.to_str(d.get("after", ""))
	wave.blocking = RpgUtil.to_bool(d.get("blocking", false))
	wave.points = RpgUtil.to_int(d.get("points", 100), 100)
	wave.bonus = maxi(0, RpgUtil.to_int(d.get("bonus", 0)))
	wave.data = d
	return wave

## Where each of `count` enemies stands, relative to the middle of the formation.
static func offsets(shape: String, count: int, gap: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	var n := maxi(1, count)
	var half := (n - 1) * 0.5
	for i in n:
		match shape:
			"column":
				out.append(Vector2(0.0, (i - half) * gap))
			"v":
				# the first one leads at the point; the others fall back to the left and right
				var rank := floorf((i + 1) * 0.5)
				var side := -1.0 if i % 2 == 1 else 1.0
				out.append(Vector2(side * rank * gap, -rank * gap))
			"circle":
				var radius := maxf(gap, gap * n / TAU)
				var angle := TAU * i / n - PI * 0.5
				out.append(Vector2(cos(angle), sin(angle)) * radius)
			"sine":
				out.append(Vector2((i - half) * gap, sin(i * PI * 0.5) * gap))
			_:
				out.append(Vector2((i - half) * gap, 0.0))
	return out
