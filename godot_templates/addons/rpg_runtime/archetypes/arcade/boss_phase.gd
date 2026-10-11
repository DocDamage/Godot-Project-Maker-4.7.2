class_name RpgArcadeBossPhase
extends RefCounted
## One phase of a boss: how it moves and what it attacks with, until its health has fallen to the
## fraction `until`. The kinds give the patterns their meaning (RpgArcadeBoss._move, _perform).

## The phase lasts while the health is above this fraction of the full health (0 for the last).
var until := 0.0
var movement := "still"
## The attacks of the phase, used in turn.
var attacks := PackedStringArray()
## Seconds from one attack to the next, and how long before each the boss shows it is coming.
var interval := 2.0
var telegraph_s := 0.5
## How fast the movement is, in the units of the pattern.
var speed := 1.0

static func from_dict(d: Dictionary) -> RpgArcadeBossPhase:
	var phase := RpgArcadeBossPhase.new()
	phase.until = clampf(RpgUtil.to_float(d.get("until", 0.0)), 0.0, 1.0)
	phase.movement = RpgUtil.to_str(d.get("movement", "still"))
	for raw: Variant in RpgUtil.to_array(d.get("attacks", [])):
		phase.attacks.append(RpgUtil.to_str(raw))
	phase.interval = maxf(0.1, RpgUtil.to_float(d.get("interval", 2.0), 2.0))
	phase.telegraph_s = clampf(RpgUtil.to_float(d.get("telegraph_s", 0.5), 0.5), 0.0, phase.interval)
	phase.speed = RpgUtil.to_float(d.get("speed", 1.0), 1.0)
	return phase

## The phases of `raw` in the order they are fought: the one that ends at the highest health
## first, and the last one always lasts to the end. No entry gives one plain phase.
static func list_from(raw: Array) -> Array[RpgArcadeBossPhase]:
	var out: Array[RpgArcadeBossPhase] = []
	for entry: Variant in raw:
		if entry is Dictionary:
			var d: Dictionary = entry
			out.append(from_dict(d))
	if out.is_empty():
		out.append(RpgArcadeBossPhase.new())
	out.sort_custom(func(a: RpgArcadeBossPhase, b: RpgArcadeBossPhase) -> bool: return a.until > b.until)
	out[out.size() - 1].until = 0.0
	return out

## Which of `phases` is fought at `fraction` of the full health.
static func index_at(phases: Array[RpgArcadeBossPhase], fraction: float) -> int:
	for i in phases.size():
		if fraction > phases[i].until:
			return i
	return maxi(0, phases.size() - 1)
