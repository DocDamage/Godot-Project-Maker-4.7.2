extends RefCounted
## The smoke runner's save folder (T17.18). Godot keeps `user://` by the project's name, so two
## smoke runs of projects of one name at one time shared `user://smoke_saves` and failed each
## other's save steps: a run that is given a name saves into a folder of its own.

const SmokeRunner := preload("res://addons/rpg_runtime/debug/smoke_runner.gd")

func test_a_run_without_a_name_saves_where_every_run_did(t) -> void:
	t.eq(SmokeRunner.save_dir_for(PackedStringArray()), "user://smoke_saves")
	t.eq(SmokeRunner.save_dir_for(PackedStringArray(["--rpg-smoke", "--rpg-smoke-steps=res://a.gd"])), "user://smoke_saves")
	t.eq(SmokeRunner.save_dir_for(PackedStringArray(["--rpg-smoke", "--rpg-smoke-run="])), "user://smoke_saves")

func test_two_runs_have_two_folders(t) -> void:
	var one := SmokeRunner.save_dir_for(PackedStringArray(["--rpg-smoke", "--rpg-smoke-run=3fa9c2d1"]))
	var two := SmokeRunner.save_dir_for(PackedStringArray(["--rpg-smoke", "--rpg-smoke-run=77b0e4aa"]))
	t.eq(one, "user://smoke_saves_3fa9c2d1")
	t.eq(two, "user://smoke_saves_77b0e4aa")
	t.ok(one != two)

func test_a_name_cannot_leave_the_user_folder(t) -> void:
	t.eq(SmokeRunner.save_dir_for(PackedStringArray(["--rpg-smoke-run=../../x y:z"])), "user://smoke_saves_xyz")
	t.eq(SmokeRunner.save_dir_for(PackedStringArray(["--rpg-smoke-run=../.."])), "user://smoke_saves")

func test_a_runs_folder_is_removed_with_its_files(t) -> void:
	var own := SmokeRunner.save_dir_for(PackedStringArray(["--rpg-smoke-run=unit_test_%d" % OS.get_process_id()]))
	DirAccess.make_dir_recursive_absolute(own)
	var file := FileAccess.open(own.path_join("slot_1.save"), FileAccess.WRITE)
	file.store_string("{}")
	file.close()
	SmokeRunner.clear_saves(own)
	t.ok(not DirAccess.dir_exists_absolute(own), "the run's folder is gone with its files")
	SmokeRunner.clear_saves(own)  # a folder that is not there is no error
