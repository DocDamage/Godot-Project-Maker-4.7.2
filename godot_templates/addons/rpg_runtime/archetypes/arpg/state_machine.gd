class_name RpgStateMachine
extends Node
## A tiny finite state machine. A state is {enter, update, exit}; every callable is optional.

signal changed(from: StringName, to: StringName)

var state: StringName = &""
var states: Dictionary = {}  # name -> {enter: Callable, update: Callable, exit: Callable}
var time_in_state := 0.0
var enabled := true

func add(state_name: StringName, enter: Callable = Callable(), update: Callable = Callable(), exit: Callable = Callable()) -> void:
	states[state_name] = {"enter": enter, "update": update, "exit": exit}

func has_state(state_name: StringName) -> bool:
	return states.has(state_name)

## Leaves the current state and enters `to`. Going to the current state restarts it.
func go(to: StringName) -> void:
	if not states.has(to):
		push_error("[RPG-ARPG] unknown state %s" % to)
		return
	var from := state
	if states.has(from):
		var exit_fn: Callable = states[from]["exit"]
		if exit_fn.is_valid():
			exit_fn.call()
	state = to
	time_in_state = 0.0
	var enter_fn: Callable = states[to]["enter"]
	if enter_fn.is_valid():
		enter_fn.call()
	changed.emit(from, to)

func _physics_process(delta: float) -> void:
	if not enabled or not states.has(state):
		return
	time_in_state += delta
	var update_fn: Callable = states[state]["update"]
	if update_fn.is_valid():
		update_fn.call(delta)
