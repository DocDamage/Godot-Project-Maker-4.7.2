# Godot API verification log

Every Godot class, method or command-line flag used by rpggen is listed here with how it was
verified. Add a row before using an API for the first time (see `00_START_HERE.md` §2).

Results below were verified on **Godot 4.7.1 stable** (the version installed on the developer
machine). CI re-runs the probes on 4.7.2 (`python -m rpggen.dev godot-test`); if a row differs on
4.7.2, update it and note the difference in `IMPLEMENTATION_NOTES.md`.

| API | Signature / usage | Verified by | Date | Result |
|-----|-------------------|-------------|------|--------|
| CLI `--import` | `godot --headless --path <proj> --import` | ran on `godot_templates`; exit 0, creates `.godot/`, `*.uid`, `*.import` | 2026-10-06 | OK. Does not rewrite `project.godot` or `config_version`. Used by `godot.import_project()`. |
| CLI `--version` | `godot --version` (no `--path`) | `integration/test_godot_runner.py::test_detect_version` | 2026-10-06 | OK. Prints `4.7.1.stable.official.<hash>`. |
| CLI `--script` | `godot --headless --path <proj> --script res://x.gd` | probe in scratch project; script extends `SceneTree`, `_initialize()` runs | 2026-10-06 | OK. `quit(3)` inside `_initialize()` makes the process exit with code 3. |
| CLI `--check-only` | `godot --headless --path <proj> --script res://x.gd --check-only` | probe with a valid and a deliberately broken script | 2026-10-06 | OK. Exit 0 for valid script; exit 1 and `Parse error` in the log for a broken one. |
| CLI `--quit-after` | `godot --headless --path <proj> --quit-after N` | probe | 2026-10-06 | OK with a main scene or a `--script`. NOTE: on a project **without a main scene**, `--quit` and `--quit-after` print "Can't run project: no main scene defined" and the process hangs until killed. Test projects therefore need a main scene (see `test_godot_runner.py`). |
| CLI `--quit` | `godot --headless --path <proj> --quit` | `integration/test_godot_runner.py::test_run_godot_quit` | 2026-10-06 | OK when the project has a main scene (exit 0). |
