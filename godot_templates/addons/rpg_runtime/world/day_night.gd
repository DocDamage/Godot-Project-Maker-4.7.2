class_name RpgDayNight
extends RefCounted
## The ambient light of a map (T12.62): through a CanvasModulate, white by day outdoors, dimmer in
## interiors. The optional time-of-day cycle (RpgSettings.day_night, off by default) tints the
## outdoor maps from the play time, so the same moment of a save always looks the same.

const DAY := Color(1.0, 1.0, 1.0)
const INTERIOR := Color(0.78, 0.74, 0.68)
const NIGHT := Color(0.32, 0.36, 0.55)
## (hour, colour) through a day; colours in between are blended.
const KEYS: Array = [
	[0.0, NIGHT],
	[5.0, NIGHT],
	[6.5, Color(0.85, 0.66, 0.58)],
	[8.0, DAY],
	[17.0, DAY],
	[19.0, Color(0.92, 0.62, 0.52)],
	[20.5, NIGHT],
	[24.0, NIGHT],
]
## The cycle: a whole day in this many minutes of play, starting at this hour.
const CYCLE_MINUTES := 24.0
const START_HOUR := 8.0

## The hour (0..24) after `playtime_s` seconds of play.
static func hour_at(playtime_s: float, cycle_minutes: float = CYCLE_MINUTES, start_hour: float = START_HOUR) -> float:
	return fposmod(start_hour + playtime_s / (maxf(cycle_minutes, 0.01) * 60.0) * 24.0, 24.0)

## The outdoor ambient colour at `hour`.
static func ambient_at(hour: float) -> Color:
	var h := fposmod(hour, 24.0)
	for i in range(1, KEYS.size()):
		var later: Array = KEYS[i]
		var earlier: Array = KEYS[i - 1]
		var t1: float = later[0]
		if h <= t1:
			var t0: float = earlier[0]
			var c0: Color = earlier[1]
			var c1: Color = later[1]
			return c0.lerp(c1, (h - t0) / maxf(t1 - t0, 0.0001))
	return NIGHT

## The ambient of a map: dimmer indoors; outdoors the cycle's colour when it is on, else day.
static func map_ambient(interior: bool, cycle_on: bool, playtime_s: float) -> Color:
	if interior:
		return INTERIOR
	return ambient_at(hour_at(playtime_s)) if cycle_on else DAY
