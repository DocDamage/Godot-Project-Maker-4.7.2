# M1 — Walking Skeleton

**Goal:** `rpggen generate --config cfg.json` takes one synthetic folder pack and produces a Godot project. The project has one TileSet, a starter map whose ground is painted, and a player that moves with the keyboard. Godot validates the project headless, and CI runs all of this on Windows for every commit.

M1 deliberately uses a **temporary minimal catalog builder** (T1.10), which assumes the synthetic pack layout. M2 replaces it with real analysis. Everything else built in M1 is permanent.

---

## T1.01 — Repository scaffold

**Depends on:** nothing
**Files:** `pyproject.toml`, `README.md`, `LICENSE` (MIT), `IMPLEMENTATION_NOTES.md`, `.gitignore`, `.gitattributes`, `rpggen/__init__.py`, `rpggen/__main__.py`, `rpggen/cli.py`, `tests/conftest.py`, `tests/unit/test_smoke_import.py`

**Spec**
1. Create the layout from `01_CONVENTIONS.md` §1. Create only the directories you need now, each with an `__init__.py` where it is a Python package.
2. Copy `pyproject.toml` exactly from `01_CONVENTIONS.md` §2.
3. `.gitignore`:
   ```
   __pycache__/
   *.pyc
   .venv/
   dist/
   build/
   .godot/
   *.tmp
   /out/
   ```
4. `.gitattributes`: `* text=auto eol=lf`, `*.png binary`, `*.zip binary`, `*.wav binary`, `*.ogg binary`.
5. `rpggen/cli.py` uses `argparse` with subcommands `generate`, `analyze`, `version`. In this card only `version` works: it prints `rpggen <version>` and exits 0. The others print "not implemented" and exit 2.
6. `rpggen/__main__.py`: `from rpggen.cli import main; raise SystemExit(main())`.
7. `cli.main(argv: list[str] | None = None) -> int` returns an exit code. It never calls `sys.exit` inside.

**Tests**
* `test_smoke_import.py`: import `rpggen`; `cli.main(["version"]) == 0`; `cli.main(["generate"]) == 2`.

**Done when**
* `pip install -e .[dev]` works in a fresh venv.
* `python -m rpggen version` prints the version.
* pytest and ruff pass.

---

## T1.02 — Schemas, deterministic JSON, IDs, paths

**Depends on:** T1.01
**Files:** `rpggen/jsonio.py`, `rpggen/ids.py`, `rpggen/paths.py`, `rpggen/schema/*.schema.json`, `rpggen/schema/__init__.py`, `tests/unit/test_jsonio.py`, `tests/unit/test_ids.py`, `tests/unit/test_paths.py`, `tests/unit/test_schemas.py`

**Spec**
1. Implement `jsonio` exactly as specified in `01_CONVENTIONS.md` §2.1.
2. Implement `ids` exactly as specified in `01_CONVENTIONS.md` §4.
3. `paths.py` contains:
   * The path constants from `01_CONVENTIONS.md` §7, as POSIX strings without `res://`: `CATALOG = "rpggen/asset_catalog.json"`, and so on.
   * `to_posix_rel(path: Path, root: Path) -> str`. Raises `ValueError` if `path` is not inside `root`.
   * `from_posix_rel(rel: str, root: Path) -> Path`. Rejects `..` parts and absolute paths with `ValueError`.
   * `glob_match(rel: str, pattern: str) -> bool`. Supports `*` (no `/`), `**` (any depth, including zero) and `?`. Matching is case-insensitive.
   * `local_cache_dir() -> Path`. Returns `%LOCALAPPDATA%/rpggen/cache` on Windows and `~/.cache/rpggen` elsewhere. **This is the only place in the codebase that checks the platform.**
4. Write one JSON Schema file for each schema in `02_SCHEMAS.md`: config, inventory, catalog, ledger, profile and results. Use `"additionalProperties": false` on every object whose fields are fully listed. Enums must match the document exactly.
5. `rpggen/schema/__init__.py`: `validate(kind: str, obj: Any) -> None`. Loads the schema with `importlib.resources`. Raises `RpgGenError("CAT-002", ...)` with the first error's JSON path in the message. (Until T1.03 exists, raise `ValueError` and switch to `RpgGenError` in T1.03.)

**Tests**
* jsonio: key order is sorted; float `0.1+0.2` is written as `0.3`; output ends with `\n`; writing is atomic (patch `os.replace` to raise, and check that the original file is unchanged); unicode round-trips.
* ids: every example in the conventions; `disambiguate(["a","a","b","a"]) == ["a","a__2","b","a__3"]`.
* paths: `glob_match("Characters/Enemies/bat.png", "characters/enemies/**")` is true; `"a/b"` against `"*"` is false; `"x.png"` against `"**/*.png"` is true; `from_posix_rel("../x", root)` raises.
* schemas: a valid example of each schema (copy from `02_SCHEMAS.md`) passes; removing a required field fails; an unknown field fails.

**Done when:** all tests pass, and every example in `02_SCHEMAS.md` validates against its schema.

---

## T1.03 — Error codes and issue lists

**Depends on:** T1.02
**Files:** `tools/gen_error_codes.py`, `rpggen/errors.py`, `rpggen/errors_table.py` (generated), `godot_templates/builder/lib/error_codes.gd` (generated), `docs/errors.md` (generated), `tests/unit/test_errors.py`

**Spec**
1. `tools/gen_error_codes.py` reads `rpggen_spec/03_ERROR_CODES.md` (path given as argv[1], defaulting to `docs/spec/03_ERROR_CODES.md`; copy the spec folder into `docs/spec/` in this card). It parses the markdown table rows that start with `| <AREA>-<NNN> |` and writes:
   * `rpggen/errors_table.py`: `CODES: dict[str, CodeInfo]`, where `CodeInfo(code, severity, message, fix)`. The file starts with `# GENERATED — do not edit`.
   * `godot_templates/builder/lib/error_codes.gd`: `extends RefCounted` with `const CODES := { "ENV-001": {"severity": "error", "message": "...", "fix": "..."}, ... }`.
   * `docs/errors.md`: the same table, grouped by area under headings.
2. `rpggen/errors.py` implements `Severity`, `Issue`, `RpgGenError` and `IssueList` as specified in `01_CONVENTIONS.md` §2.3.
   * Message formatting: `CODES[code].message.format_map(SafeDict(detail))`, where `SafeDict.__missing__` returns `"{key}"`.
   * `IssueList.has_errors() -> bool`; `IssueList.to_json() -> list[dict]`, sorted by `(severity order E<W<I, code, file or "")`.

**Tests**
* Every code in the markdown file is present in `CODES`.
* An unknown code raises `KeyError`.
* Formatting with a missing detail key leaves the placeholder in place.
* Running the generator twice produces byte-identical outputs.

**Done when:** the generated files are committed, and a CI step (added in T1.12) checks that regenerating them produces no diff.

---

## T1.04 — Synthetic pack generator (M1 subset)

**Depends on:** T1.02
**Files:** `tools/make_synthetic_packs.py`, `test_packs/synthetic/basic16/**`, `tests/unit/test_synthetic_packs.py`

**Spec**
`python tools/make_synthetic_packs.py --out test_packs/synthetic` creates packs deterministically with Pillow (no randomness; colors come from fixed lists). For M1, only `basic16` is created. M2 extends the script with more packs (T2.01).

`basic16/` layout:
```text
basic16/
├── LICENSE.txt                       "CC0-1.0 synthetic test pack"
├── tiles/
│   └── terrain.png                   128×64, 16px grid, no margin, no separation
│                                      8 cols × 4 rows. Row 0: 8 solid ground colors.
│                                      Row 1: 8 "wall" tiles (dark gray with 1px black border).
│                                      Rows 2–3: transparent except (0,2) water blue, (1,2) sand.
└── characters/
    └── hero.png                      64×96, frame 16×24, 4 cols × 4 rows.
                                       Rows = down, left, right, up. Each frame: transparent bg,
                                       a filled rounded rect 10×18 at x=3,y=5 in a row color,
                                       with a 2px "eye" whose x shifts per column (so frames differ),
                                       and a 1px black line at y=23 (the feet baseline).
```

* Draw every pixel explicitly. Do not use antialiasing (`ImageDraw` with integer coordinates only).
* Save PNGs with `optimize=False` and no metadata, so the bytes are deterministic. Write the PNG with `pnginfo=None`, and verify determinism by hashing two consecutive runs.
* Also write `test_packs/synthetic/basic16.expected.json`:

```json
{ "tiles/terrain.png": { "cell": [16,16], "margin": [0,0], "separation": [0,0], "nonempty": 18, "role": "GROUND" },
  "characters/hero.png": { "frame": [16,24], "rows": ["down","left","right","up"], "cols": 4, "role": "PLAYER", "baseline_y": 23 } }
```

**Tests:** two runs into temporary directories produce identical file hashes; the image sizes match the spec; the pixel at (0,0) of `terrain.png` matches the first ground color.

**Done when:** the pack is committed and the determinism test passes.

---

## T1.05 — Godot discovery, version check and runner

**Depends on:** T1.03
**Files:** `rpggen/core/godot.py`, `tests/unit/test_godot_version.py`, `tests/integration/test_godot_runner.py`

**Spec**
1. `parse_version(text: str) -> tuple[int, int, int, str]`. Uses the regex `^(\d+)\.(\d+)(?:\.(\d+))?\.([a-z0-9]+)` against the first non-empty line, with the patch defaulting to 0. Examples:
   * `"4.7.2.stable.official.abc123"` → `(4,7,2,"stable")`
   * `"4.7.stable.official.x"` → `(4,7,0,"stable")`
   * Garbage → `RpgGenError("ENV-002", found=text[:40])`
2. `check_version(v) -> list[Issue]`:
   * `(4,7,2,"stable")` → no issues.
   * `(4,7,x,"stable")` with `x != 2` → `ENV-003` (warning).
   * Anything else → raises `RpgGenError("ENV-002")`.
3. `find_console_exe(exe: Path) -> Path`. If `exe.name` ends with `.exe` and does not contain `_console`, look for `<stem>_console.exe` in the same folder; return it if it exists, otherwise return `exe`.
4. `detect_version(exe: Path) -> tuple`. Runs `[console_exe, "--version"]` with a 30 s timeout and **without** `--path` (no project), then parses the result.
5. Implement `run_godot` as specified in `01_CONVENTIONS.md` §8.
6. `auto_find_godot() -> list[Path]`. Returns candidate executables from the `RPGGEN_GODOT` environment variable, `PATH` entries matching `godot*.exe`, and `%LOCALAPPDATA%\Programs\Godot*`. Deduplicate and sort. Used by the GUI later.

**Tests**
* Unit: the parse examples above; check_version behavior; `find_console_exe` with temp files.
* Integration (skipped without `RPGGEN_GODOT`): `detect_version` returns `(4,7,2,"stable")`; `run_godot` on an empty temp project with args `["--quit"]` returns code 0 within the timeout.

**Done when:** the tests pass, and they also pass with `RPGGEN_GODOT` set on your machine, if you have Godot available.

---

## T1.06 — Template Godot project skeleton

**Depends on:** T1.01
**Files:** `godot_templates/project.godot`, `godot_templates/icon.svg`, `godot_templates/addons/rpg_runtime/plugin.cfg`, `godot_templates/addons/rpg_runtime/README.md`, `docs/godot_api_verified.md`

**Spec**
1. `godot_templates/project.godot`, with exactly this text (this is the only hand-written `project.godot` content):
   ```ini
   ; Engine configuration file.
   ; Template project for rpggen. Settings are applied by the builder.

   config_version=5

   [application]

   config/name="rpggen templates"
   config/features=PackedStringArray("4.7")
   ```
   ⚠ VERIFY that Godot 4.7.2 opens it without rewriting `config_version`. If Godot rewrites it, commit Godot's rewritten version instead.
2. Python writes the **same text** into generated projects (constant `MINIMAL_PROJECT_GODOT` in `rpggen/core/staging.py`, created in T1.10), with `config/name` replaced by the project name. Escape quotes and backslashes.
3. `icon.svg`: a 128×128 simple shield shape, hand-written SVG (not copied from anywhere).
4. Do **not** add `.gdignore` to `builder/`. The builder scripts must be importable.
5. Run `godot --headless --path godot_templates --import` once. ⚠ VERIFY that the `--import` flag exists in 4.7.2. If it does not, use `--editor --quit-after 300`. Record which one works in `docs/godot_api_verified.md`, and use the same mechanism in `godot.py: import_project()` (add that function now: it runs the verified command with the import timeout).
6. Commit the generated `*.uid` files; never edit them. Do not commit `.godot/`.
7. Create `docs/godot_api_verified.md` with a header row and the first entries (`--import`, `--version`, `--script`, `--check-only`, `--quit-after`).

**Tests:** the integration test `test_template_project_imports` runs `import_project` on a temporary copy of `godot_templates` and asserts exit code 0 and no `ERROR:` lines in the log.

**Done when:** the template project imports cleanly in Godot 4.7.2.

---

## T1.07 — Builder library and the first recipes

**Depends on:** T1.06
**Files (all under `godot_templates/`):**
`builder/build.gd`, `builder/lib/paths.gd`, `builder/lib/json_util.gd`, `builder/lib/log.gd`, `builder/lib/results.gd`, `builder/lib/build_context.gd`, `builder/lib/catalog_reader.gd`, `builder/lib/geometry.gd`, `builder/recipes/project_settings_recipe.gd`, `builder/recipes/tileset_recipe.gd`, `builder/recipes/sprite_frames_recipe.gd`, `tests/unit/test_geometry.gd`, `tests/unit/test_catalog_reader.gd`, `tests/probes/*.gd`, plus Python `tests/unit/test_paths_sync.py`.

### build.gd (entry point)

```gdscript
extends SceneTree
# Run: godot --headless --path <proj> --script res://generated/builder/build.gd
# During template tests the path is res://builder/build.gd; find the builder dir from
# get_script().resource_path.get_base_dir().

const RECIPE_ORDER := [
	"project_settings_recipe",
	"tileset_recipe",
	"sprite_frames_recipe",
	# M1 adds: "player_recipe", "boot_recipe", "starter_map_recipe" (T1.09)
]

func _initialize() -> void:
	var code := _run()
	quit(code)

func _run() -> int:
	# 1. ctx := BuildContext.new(builder_dir)
	# 2. ctx.load_inputs() -> reads CONFIG and CATALOG; on failure add CAT-001/CAT-002 and
	#    write results, return 1.
	# 3. ctx.load_build_state()
	# 4. for name in RECIPE_ORDER: recipe := load(builder_dir + "/recipes/" + name + ".gd").new()
	#      for out in recipe.outputs(ctx): decide skip via ctx.should_skip(out, recipe.input_hash(ctx))
	#      if not all skipped: issues := recipe.build(ctx); ctx.results.add_issues(issues)
	#      record items (written/skipped/failed)
	#      a recipe raising an engine error -> BUILD-002 and continue with the next recipe
	# 5. ctx.save_build_state() (only hashes of outputs that were successfully written)
	# 6. ctx.results.write(RESULTS_BUILD); return 0 if results.ok else 1
```

⚠ VERIFY: under `--script`, `_initialize()` runs and `quit()` ends the process with that exit code. Probe: `tests/probes/probe_quit_code.gd` calls `quit(3)`; check that the process exit code is 3.

### lib files

* `paths.gd`: constants identical to `01_CONVENTIONS.md` §7. `test_paths_sync.py` parses `paths.gd` with a regex (`const (\w+) := "res://([^"]*)"`) and compares the values with `rpggen/paths.py`.
* `json_util.gd`:
  * `read(path) -> Variant`: returns `null` and pushes an error on failure.
  * `write(path, data) -> int`: `JSON.stringify(data, "  ", true)` + `"\n"`, written to `path + ".tmp"`, then `DirAccess.rename_absolute` over the target. On Windows, rename may fail if the target exists; if it does, remove the target first and then rename. ⚠ VERIFY with a probe.
* `log.gd`: `info(msg)`, `warn(msg)`, `error(msg)`. Each prints `[rpggen] LEVEL msg`. The Python side parses lines starting with `[rpggen]`.
* `results.gd`: collects issues and items; `add_issue(code, detail: Dictionary, file := "")` looks up severity and message in `error_codes.gd` and formats `{key}` placeholders; `write(path)` writes results JSON (`02_SCHEMAS.md` §6) with `started_ms = 0`.
* `catalog_reader.gd`:
  * `effective(asset: Dictionary) -> Dictionary`: deep merge, where an override value of `null` deletes the key.
  * `assets_by_role(role) -> Array`, sorted by id.
  * `tileset_defs() -> Array`.
  * `asset(id) -> Dictionary`.
* `build_context.gd`: holds `config`, `catalog` (a reader), `results`, `builder_dir` and `build_state`.
  * `should_skip(out_path, hash) -> bool`: true when `build_state.outputs[out] == hash` and `FileAccess.file_exists(out)`.
  * `stable_hash(v: Variant) -> String`: `JSON.stringify(v, "", true).sha256_text()`.
* `geometry.gd`:
  * `rect_poly(x, y, w, h) -> PackedVector2Array`.
  * `profile_polygon(profile: String, cell: Vector2i, custom: Array) -> PackedVector2Array`: returns points in **top-left pixel space**. FULL → whole cell; BOTTOM_HALF → `y` from `h/2` to `h`; BOTTOM_EDGE → bottom 4 px (or `max(2, h/4)`); TOP_EDGE / LEFT_EDGE / RIGHT_EDGE likewise; NONE → empty; CUSTOM → the given points.
  * `to_tile_space(points, cell) -> PackedVector2Array`: subtracts `cell / 2.0`, because tile collision polygons are centered on the tile. ⚠ VERIFY with probe `probe_tile_collision.gd`: create a TileSet, add a FULL polygon via `to_tile_space`, paint one tile, and check that a `PhysicsDirectSpaceState2D.intersect_point` at the tile's top-left+1px hits. This needs a physics frame, so run it in `_process` after 2 frames.

### project_settings_recipe.gd

* `outputs` → `["res://project.godot"]`. `input_hash` covers the config fields it uses plus `RECIPE_VERSION`.
* `build`: call `ProjectSettings.set_setting` for each row below, then `ProjectSettings.save()`. ⚠ VERIFY every key name against 4.7.2 by reading it back with `ProjectSettings.has_setting`, and record each one in the API doc.

| Key | Value |
|-----|-------|
| `application/config/name` | `config.project_name` |
| `application/run/main_scene` | `"res://generated/scenes/bootstrap/boot.tscn"` |
| `display/window/size/viewport_width` / `viewport_height` | `config.resolution` |
| `display/window/size/window_width_override` / `window_height_override` | `config.window_size` |
| `display/window/stretch/mode` | `"canvas_items"` |
| `display/window/stretch/aspect` | `"keep"` |
| `display/window/stretch/scale_mode` | `"integer"` |
| `rendering/textures/canvas_textures/default_texture_filter` | `0` (Nearest) |
| `rendering/2d/snap/snap_2d_transforms_to_pixel` | `true` |
| `rendering/2d/snap/snap_2d_vertices_to_pixel` | `true` |
| `layer_names/2d_physics/layer_1` … `layer_10` | names from ARCHITECTURE §17 table |
| `input/<action>` | `{"deadzone": 0.2, "events": [InputEvent…]}` built from `config.input` |
| `autoload/<Name>` | added in M6; M1 adds none |

* Building input events:
  * Keys: `var e := InputEventKey.new(); e.physical_keycode = OS.find_keycode_from_string(name)`.
  * Joy buttons: `InputEventJoypadButton`, with `button_index` set.
  * Axes: `InputEventJoypadMotion`, with `axis` and `axis_value`.
  * Mouse: `InputEventMouseButton`, with `button_index`.

### tileset_recipe.gd

* `outputs`: one path per TileSetDef → `res://generated/tilesets/<name>.tres`.
* `input_hash(ctx)`: a hash of the TileSetDefs plus the effective facets of each source asset (grid, collision, tile_overrides, tileset) plus each asset's `sha256` plus `RECIPE_VERSION`.
* `build`, for each TileSetDef:
  1. If the file exists, `load` it (this is the merge path; M1 implements the create path, and T5.04 completes the merge). Otherwise `TileSet.new()`.
  2. `ts.tile_size = Vector2i(def.tile_size)`.
  3. Ensure physics layers exist up to `def.physics_layers.size()`: `while ts.get_physics_layers_count() < n: ts.add_physics_layer()`. Then `ts.set_physics_layer_collision_layer(i, bits)` and `ts.set_physics_layer_collision_mask(i, mask)`.
  4. Ensure the custom data layers exist **by name**: `ts.get_custom_data_layer_by_name(name)` returns -1 if missing; if so, call `ts.add_custom_data_layer()`, `ts.set_custom_data_layer_name(i, name)` and `ts.set_custom_data_layer_type(i, TYPE_STRING or TYPE_FLOAT)`. ⚠ VERIFY these method names.
  5. For each `{asset, source_id}` in `def.sources`, in source_id order:
     * `var tex := load("res://" + asset.path)`. If null → TILE-001-style issue `VAL-002`; skip.
     * If `ts.has_source(source_id)`: `src = ts.get_source(source_id)`. Otherwise: `src = TileSetAtlasSource.new()` and `ts.add_source(src, source_id)`. **Always pass the explicit id.**
     * `src.texture = tex`; `src.texture_region_size = cell`; `src.margins = margin`; `src.separation = separation`.
     * Compute columns and rows as in `02_SCHEMAS.md` §4.4 (Grid).
     * Load the image once: `var img := tex.get_image()`. ⚠ VERIFY that this works headless for imported textures. Fallback: `Image.load_from_file(ProjectSettings.globalize_path(path))`.
     * For each cell `(cx, cy)` in row-major order: if the cell's pixel rectangle has any pixel with alpha > 0 (use `img.get_region(rect).is_invisible()`, ⚠ VERIFY) and `tile_overrides["cx,cy"].skip` is not true, then `src.create_tile(Vector2i(cx, cy))` if `not src.has_tile(...)`.
     * For each tile: `var td := src.get_tile_data(coords, 0)`.
       * Collision: compute the profile (the tile override wins over the sheet default). Remove existing polygons on physics layer 0 (`while td.get_collision_polygons_count(0) > 0: td.remove_collision_polygon(0, 0)`), then add one if the profile is not NONE: `td.add_collision_polygon(0)` and `td.set_collision_polygon_points(0, 0, geometry.to_tile_space(points, cell))`.
       * For ALPHA_POLYGON, use `BitMap.new()` with `create_from_image_alpha(cell_img, 0.5)`, then `opaque_to_polygons(Rect2i(0, 0, cell.x, cell.y), 1.0)`, and add each polygon. ⚠ VERIFY.
       * Custom data: `td.set_custom_data("asset_id", asset.id)`.
  6. `ResourceSaver.save(ts, out_path)`. On a non-OK result → BUILD-004.

### sprite_frames_recipe.gd

* `outputs`: `res://generated/sprite_frames/<asset_id>.tres` for each asset with `usage == "sprite"` and non-empty `animations`.
* `build`, for each such asset:
  * `var sf := SpriteFrames.new()`. If `sf.has_animation("default")`, call `sf.remove_animation("default")`.
  * For each animation name, sorted: `sf.add_animation(name)`; `sf.set_animation_speed(name, fps)`; `sf.set_animation_loop(name, loop)`.
  * For each frame `[col, row]`, create an `AtlasTexture` with `atlas = tex` and `region = Rect2(margin + Vector2(col,row) * (cell + separation), cell)`. Add it with `sf.add_frame(name, at, durations[i] if present else 1.0)`.
  * Store `flip_h` with `sf.set_meta("flip_h_" + name, true)` for animations whose `flip_h` is true. ⚠ VERIFY that meta survives `ResourceSaver` on SpriteFrames. If it does not, write a sidecar `<asset_id>.anim.json` instead and record the change.
  * Animations with zero frames → `ANIM-001`; skip that animation.
  * Save the resource.

**Tests (GDScript, run by the T1.08 runner)**
* `test_geometry.gd`: FULL for a 16×16 cell gives the 4 corners, and in tile space gives ±8; BOTTOM_HALF for 16×24 has its y range in [12, 24].
* `test_catalog_reader.gd`: the effective merge with a null-delete; the same fixture JSON as the Python test `tests/unit/test_effective.py` (create both; the expected output is stored in `tests/fixtures/effective_cases.json`, shared by both).
* Probes listed above, each recorded in `docs/godot_api_verified.md`.

**Done when:** the probes and tests pass. The recipes are exercised end-to-end in T1.11.

---

## T1.08 — GDScript test runner and the `dev godot-test` command

**Depends on:** T1.05, T1.06
**Files:** `godot_templates/tests/run_tests.gd`, `godot_templates/tests/lib/t.gd`, `rpggen/dev.py`, `tests/integration/test_godot_unit.py`

**Spec**
* `run_tests.gd` extends `SceneTree`. In `_initialize`:
  * Recursively list `res://tests/unit/` for `test_*.gd`, sorted.
  * For each file: `var inst = load(path).new()`. For each method in `inst.get_method_list()` whose name starts with `test_` (sorted), call it with a fresh `T` object (`tests/lib/t.gd`).
  * `T` provides `eq(a, b, msg := "")`, `ok(cond, msg := "")`, `near(a, b, eps := 0.001)` and `fail(msg)`. Each records failures; it does not throw.
  * After every test, print `PASS path::method` or `FAIL path::method: <failures>`.
  * Write `res://tests/results.json` with `{passed, failed, failures: [...]}` and `quit(0 if failed == 0 else 1)`.
* `rpggen/dev.py`: `python -m rpggen.dev godot-test` copies `godot_templates` to a temporary directory, runs `import_project`, then runs `run_godot(..., ["--script", "res://tests/run_tests.gd"])`, prints the PASS/FAIL lines and returns the exit code. `python -m rpggen.dev make-fixtures` runs `tools/make_synthetic_packs.py`.
* The pytest integration wrapper `test_godot_unit.py` calls `dev.godot_test()` and asserts 0.

**Done when:** `python -m rpggen.dev godot-test` runs T1.07's tests and they pass.

---

## T1.09 — Minimal runtime player, boot scene and starter map recipes

**Depends on:** T1.07
**Files:**
* Runtime: `godot_templates/addons/rpg_runtime/actors/player_controller.gd`, `godot_templates/addons/rpg_runtime/actors/animation_driver.gd`, `godot_templates/addons/rpg_runtime/core/boot.gd`
* Recipes: `godot_templates/builder/recipes/player_recipe.gd`, `boot_recipe.gd`, `starter_map_recipe.gd`
* Tests: `godot_templates/tests/unit/test_animation_driver.gd`

### player_controller.gd (M1 version; M6 replaces it with the component actor, T6.05)

```gdscript
class_name RpgPlayerController
extends CharacterBody2D

@export var speed: float = 80.0
@export var visual_path: NodePath = ^"Visual"
var facing: String = "down"
@onready var _driver: RpgAnimationDriver = RpgAnimationDriver.new()

func _ready() -> void:
	_driver.sprite = get_node(visual_path) as AnimatedSprite2D

func _physics_process(_delta: float) -> void:
	var dir := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	velocity = dir * speed
	move_and_slide()
	if dir != Vector2.ZERO:
		facing = RpgAnimationDriver.dir_to_facing(dir)
		_driver.play("walk", facing)
	else:
		_driver.play("idle", facing)
```

### animation_driver.gd

```gdscript
class_name RpgAnimationDriver
extends RefCounted
var sprite: AnimatedSprite2D

static func dir_to_facing(d: Vector2) -> String:
	# Horizontal wins on exact diagonal ties? NO: vertical wins ties (classic RPG feel).
	if absf(d.x) > absf(d.y):
		return "right" if d.x > 0.0 else "left"
	return "down" if d.y >= 0.0 else "up"

## Plays "<base>_<facing>". Falls back in order:
## 1. "<base>_<facing>"  2. mirrored counterpart with flip_h (left<->right)
## 3. "<base>_down"  4. "walk_<facing>" frame 0 (paused) when base == "idle"
## Does nothing if sprite or sprite_frames is null.
func play(base: String, facing: String) -> void: ...
```

* Apply flip_h when the chosen animation has `flip_h_<name>` meta (or a sidecar flag). Otherwise set `flip_h = false`.
* Do not restart an animation that is already playing.

### player_recipe.gd

Output: `res://generated/scenes/actors/player.tscn`. Built in code:

```text
Player (CharacterBody2D, script player_controller.gd, motion_mode = MOTION_MODE_FLOATING,
        collision_layer = bit 2 (player), collision_mask = bits 1 (world) + 3 (enemies) + 4 (npcs))
├── Visual (AnimatedSprite2D, sprite_frames = load(<player asset sprite_frames>),
│           centered = false, offset = -origin)   # origin from facets, so node origin = feet
├── Feet (CollisionShape2D, RectangleShape2D size = (frame.x * 0.6, 6), position = (0, -3))
└── Camera (Camera2D, enabled = true)
```

* Pick the player asset as the first asset with role PLAYER, sorted by id. If there is none, use a placeholder (T2.15). In M1, error if none.
* Collision bits: layer N corresponds to bit value `1 << (N-1)`. Use `set_collision_layer_value(n, true)`. ⚠ VERIFY.

### boot_recipe.gd

Output: `res://generated/scenes/bootstrap/boot.tscn`. It is a `Node` with script `addons/rpg_runtime/core/boot.gd`, and `boot.gd` has `@export var first_scene: String`. In `_ready`, it calls `get_tree().change_scene_to_file.call_deferred(first_scene)`. M1 sets `first_scene = "res://game/maps/starter_map.tscn"`. M6 changes this to the title screen.

### starter_map_recipe.gd

* Output: `res://game/maps/starter_map.tscn`. **user_seed** ownership: the recipe's `outputs()` returns it only when the file does not exist yet.
* Structure (M1 subset):
  ```text
  StarterMap (Node2D)
  ├── Ground (TileMapLayer, tile_set = overworld.tres)
  └── YSorted (Node2D, y_sort_enabled = true)
      └── Player (instance of player.tscn, position = center of map)
  ```
* Painting: a 30×20 cell area. Fill it with the first tile of the first GROUND sheet in the overworld tileset: `ground.set_cell(Vector2i(x, y), source_id, Vector2i(0, 0), 0)`. Draw a 1-tile border of the first WALL tile if one exists. If the overworld tileset has no WALL tile, leave the border empty.
* Player position: `Vector2(15, 10) * tile_size + tile_size / 2`.

**Tests:** `test_animation_driver.gd` checks `dir_to_facing` for 8 directions plus ties, and the fallback chain using a SpriteFrames built in the test with only `walk_down` and `walk_right`.

**Done when:** the tests pass. End-to-end checks happen in T1.11.

---

## T1.10 — Orchestrator, staging and CLI `generate` (M1 version)

**Depends on:** T1.04, T1.05, T1.07, T1.09
**Files:** `rpggen/core/config.py`, `rpggen/core/catalog.py` (M1: data classes, load/save and `build_minimal_catalog`), `rpggen/core/staging.py`, `rpggen/core/orchestrator.py`, `rpggen/cli.py` (generate), `tests/unit/test_config.py`, `tests/unit/test_catalog_minimal.py`, `tests/integration/test_generate_basic16.py`

### config.py

* `@dataclass class GeneratorConfig` mirrors `02_SCHEMAS.md` §1.
* `load(path) -> GeneratorConfig` validates against the schema. `save(cfg, path)`. `default_for(project_name, packs) -> GeneratorConfig` fills in the defaults.
* The `default_input(archetype)` function returns the §1.1 tables.

### catalog.py (M1 portion)

* Data classes: `Catalog`, `CatalogPack`, `Asset`, `TileSetDef`, `SheetObject`, `FolderRule`.
* `to_json()` / `from_json()` for each.
* `load(path)` and `save(catalog, path)` (validated; sorted as the schema notes require).
* `effective(asset) -> dict`: identical semantics to the GDScript version.
* **Temporary** `build_minimal_catalog(pack_dir: Path, pack_id: str, project_rel_root: str, tile_size: int) -> Catalog`. Docstring: `"TEMPORARY (M1). Replaced by analysis pipeline in T2.14."`
  * Every PNG under `tiles/` becomes `usage=tiles`, role GROUND, grid `cell=[tile_size]*2`, collision NONE, and gets a source in TileSetDef `overworld` with sequential ids.
  * For `terrain.png`, set `tile_overrides` for row 1 (the walls) with `collision FULL`, and set role WALL in `tags`. Hard-code this for basic16.
  * Every PNG under `characters/` becomes `usage=sprite`, role PLAYER, frame `[16,24]`, origin `[8,23]`, and animations `walk_{down,left,right,up}` from rows 0–3, 4 frames each, at 8 fps. `idle_*` uses frame 0 of the same row at 1 fps, with loop true.
  * The TileSetDef has `physics_layers [{name: "world", layer_bits: 1, mask_bits: 0}]` and the three standard custom data layers.

### staging.py

```python
MINIMAL_PROJECT_GODOT = """..."""   # from T1.06, with {name}

@dataclass
class Staging:
    target: Path
    staging: Path            # target / ".rpggen_staging"

def create_staging(target: Path) -> Staging:
    """M1: target must be empty or not exist. Remove any old staging, create fresh."""

def install_templates(stg: Staging, templates_root: Path) -> list[str]:
    """Copy:
      templates/addons/rpg_runtime        -> staging/addons/rpg_runtime
      templates/builder                    -> staging/generated/builder
      (tests/ and probes are NOT copied)
    Copy .uid files too. Return sorted posix list of written files."""

def install_pack(stg: Staging, pack_dir: Path, pack_id: str) -> list[str]:
    """Copy every file (inventory-approved in M2; in M1 every non-junk file) into
    staging/assets/packs/<pack_id>/<same relative path>. Preserve bytes exactly (shutil.copyfile).
    Return sorted posix list."""

def write_project_files(stg, cfg, catalog) -> None:
    """Write project.godot (minimal), rpggen/generator_config.json, rpggen/asset_catalog.json,
    .gitignore and .gitattributes for the generated project (content in T5.06; M1 uses the
    same content as defined there — copy it now)."""

def promote(stg: Staging) -> None:
    """M1: move every top-level entry of staging into target (target was empty), then remove
    staging. M5 replaces this with ledger-aware promotion."""

def discard(stg: Staging) -> Path:
    """Rename staging to target/.rpggen_failed/<YYYYmmdd-HHMMSS>/ and keep the 3 newest."""
```

The templates root is resolved by `rpggen.paths.templates_root()`. It returns `Path(sys._MEIPASS) / "godot_templates"` when the program is frozen (PyInstaller), and otherwise `repo_root / "godot_templates"`.

### orchestrator.py

```python
@dataclass
class Callbacks:
    on_phase: Callable[[str, int, int], None] = lambda name, i, n: None   # phase i of n
    on_log: Callable[[str], None] = lambda line: None
    is_cancelled: Callable[[], bool] = lambda: False

@dataclass
class RunResult:
    ok: bool
    target: Path
    issues: list[Issue]
    report_path: Path | None
    failed_staging: Path | None

PHASES_M1 = ["preflight", "stage", "install", "catalog", "import", "build", "validate", "smoke", "promote", "report"]

def run(cfg_path: Path, target: Path, godot_exe: Path, cb: Callbacks = Callbacks()) -> RunResult
```

* Each phase is a function `phase_<name>(state) -> None`. `state` is a dataclass with `cfg`, `catalog`, `staging`, `issues`, `godot_exe` and `log_dir`.
* Before each phase: if `cb.is_cancelled()`, call `discard()` and return `RunResult(ok=False, ...)`.
* After build, validate and smoke: read the results JSON, add its issues, and stop if it has any errors. On stop: `discard()`, write a report into the failed folder, and return `ok=False`.
* Godot log dir: `staging/rpggen/logs/`. These logs travel with the project.

### CLI

`rpggen generate --config <cfg.json> --target <dir> --godot <exe>`. Alternatively, `--pack <dir> --name <name>` creates a default config on the fly. The command prints phase lines, returns 0 on success and 1 on failure, and prints the issue summary.

**Tests**
* Unit: `build_minimal_catalog` on basic16 matches the golden file `tests/golden/basic16.catalog.json` (create it once, review it by hand, commit it).
* Integration: generating basic16 into a temporary folder returns `ok=True`. The target contains `generated/tilesets/overworld.tres`, `generated/sprite_frames/basic16.characters.hero.tres`, `generated/scenes/actors/player.tscn` and `game/maps/starter_map.tscn`, and has no `.rpggen_staging` folder left behind.

**Done when:** the integration test passes (it requires T1.11 for validate and smoke; implement T1.10 and T1.11 together and run the test after both).

---

## T1.11 — Validation and smoke test (M1 version)

**Depends on:** T1.10
**Files:** `godot_templates/builder/validate.gd`, `godot_templates/addons/rpg_runtime/debug/smoke_runner.gd`, `godot_templates/builder/smoke/smoke_steps_m1.gd`, `rpggen/core/orchestrator.py` (phases validate and smoke), `rpggen/core/godot_log.py`, `tests/unit/test_godot_log.py`

### validate.gd (extends SceneTree)

M1 checks, each adding items and issues:
1. **Scripts:** for every `.gd` under `res://addons`, `res://generated` and `res://game`: `var s = load(p)`. Fail with VAL-001 if `s == null` or `not (s as GDScript).can_instantiate()`. Exempt scripts with `@abstract` or `extends EditorPlugin` (check `can_instantiate` only for non-tool scripts). ⚠ VERIFY with probe `probe_parse_error.gd`, which uses a deliberately broken script inside `tests/probes/broken/` (place a `.gdignore` there so the template import ignores it; the probe copies it into a temp folder first).
2. **Resources:** load every `.tres` and `.tscn` under `res://generated` and `res://game`. Null → VAL-002.
3. **Dependencies:** for each of those files, `ResourceLoader.get_dependencies(p)`. Each entry may be formatted as `uid://…::Type::path` ⚠ VERIFY; extract the path part after the last `::`. Check `ResourceLoader.exists(dep)`. Missing → VAL-003.
4. **Scenes:** instantiate each `.tscn`, `root.add_child(inst)`, wait one frame, then `inst.queue_free()`. Errors → VAL-004. Because waiting needs frames, implement this as a small state machine in `_process` instead of in `_initialize`.
5. **Main scene:** `ProjectSettings.get_setting("application/run/main_scene")` exists → otherwise VAL-005.
6. **Input actions:** every action in `config.input` has at least one event in `InputMap` → otherwise VAL-007.
7. **Map round-trip** (VAL-010): load `starter_map.tscn`, find each `TileMapLayer`, record `get_used_cells()`, `set_cell` a test tile at (-100,-100), pack the scene to `user://rt_test.tscn`, reload it, check that the cell is present and the original cells are unchanged, then delete the temporary file. **Never save over the real map.**
8. Write `RESULTS_VALIDATE` and `quit(0/1)`.

### godot_log.py

* `scan(log_text: str) -> list[Issue]` turns runtime problems into issues:
  * Lines containing `SCRIPT ERROR:`, `Parse Error:`, `ERROR:` or `[RPG-` → VAL-013, with the line in detail.
  * Ignore the allowlist patterns in `IGNORED_ERROR_PATTERNS`, a module constant that starts empty. Each entry needs a comment explaining why it is ignored.
* The orchestrator applies `scan` to the validate and smoke logs.

### Smoke runner (runtime addon, inert in normal play)

* `smoke_runner.gd` extends Node and is **registered as an autoload named `RpgSmoke` by the project-settings recipe**.
* In `_ready`: if `"--rpg-smoke"` is not in `OS.get_cmdline_user_args()`, call `queue_free()` and return. Otherwise, load the steps script named by `--rpg-smoke-steps=<res path>` and run its steps.
* Step protocol: the steps script extends RefCounted, defines `func steps() -> Array[Dictionary]`, and each step is `{name, fn: Callable, timeout_s}`. Each `fn` is a coroutine that returns `""` on success or an error string. The runner awaits each step with a timeout: it races the step against a `get_tree().create_timer(timeout).timeout` using a flag.
* It writes `RESULTS_SMOKE` (§6 shape) and calls `get_tree().quit(code)`.
* M1 steps (`smoke_steps_m1.gd`):
  1. `boot`: wait until `get_tree().current_scene` is named `StarterMap` (timeout 10 s).
  2. `player_exists`: find exactly one node in group `player`. The player recipe adds the group with `add_to_group("player", true)` (persistent).
  3. `player_moves`: record the position, call `Input.action_press("move_right")`, wait 30 physics frames, release, and require that x increased by at least 8 px.
  4. `collision_blocks`: teleport the player 2 tiles from the right wall, press right for 120 frames, and require that x is less than the wall's left edge. Skip with a pass and a note if there is no wall tile.
* Command run by the orchestrator: `run_godot(exe, staging, ["--", "--rpg-smoke", "--rpg-smoke-steps=res://generated/builder/smoke/smoke_steps_m1.gd"], timeout_s=300)`. Godot runs the main scene. ⚠ VERIFY that user args after `--` reach `OS.get_cmdline_user_args()` in headless mode, and that physics processes headless.

**Tests:** `test_godot_log.py` covers sample logs with and without errors. Integration: the T1.10 test now runs fully. An extra integration test makes `player_controller.gd` broken in the staging copy before validation (through a test hook `RPGGEN_TEST_SABOTAGE=broken_player`, honored **only** when `RPGGEN_DEV=1`) and asserts `ok=False` with VAL-001 or SMOKE-001.

**Done when:** basic16 generates, validates and smoke-tests green, and the sabotage test fails as expected.

---

## T1.12 — Continuous integration

**Depends on:** T1.11
**Files:** `.github/workflows/ci.yml`, `tools/fetch_godot.py`

**Spec**
* `tools/fetch_godot.py --version 4.7.2 --out .cache/godot`:
  * Downloads the Windows build zip from the official release URL pattern `https://github.com/godotengine/godot/releases/download/{v}-stable/Godot_v{v}-stable_win64.exe.zip` ⚠ VERIFY the URL pattern.
  * Extracts it and prints the console exe path.
  * Verifies the SHA-512 against the `SHA512-SUMS.txt` published in the same release, if one exists.
* Workflow (windows-latest):
  1. checkout
  2. setup-python 3.12
  3. `pip install -e .[dev]`
  4. cache `.cache/godot` keyed on the version
  5. fetch Godot
  6. set `RPGGEN_GODOT`
  7. `python tools/gen_error_codes.py` and `git diff --exit-code`
  8. `python tools/make_synthetic_packs.py --out test_packs/synthetic` and `git diff --exit-code`
  9. ruff check and format check
  10. `pytest -q` (unit)
  11. `python -m rpggen.dev godot-test`
  12. `pytest -q -m integration`
  13. Upload `**/rpggen/logs/**`, `**/.rpggen_failed/**` and `tests/**/results.json` as artifacts on failure.
* Add a second job `ubuntu-latest` that runs only unit tests and ruff (path-case bugs show up there). It becomes a full job in M10.

**Done when:** CI is green on main.

---

## T1.13 — Milestone Gate M1

All of the following must be true:
- [ ] Every T1.x card has a "done" line in `IMPLEMENTATION_NOTES.md`.
- [ ] CI is green.
- [ ] Generating basic16 twice into two fresh folders gives identical files, except `rpggen/logs/**`, `*.import`, `.godot/**`, `elapsed_ms` values and `uid` attributes. A test `test_determinism_basic16` checks this with a recursive hash comparison and these exclusions.
- [ ] Opening the generated project in the Godot 4.7.2 editor (a manual check by the human maintainer, written in the notes) shows a painted map; pressing F5 shows a player walking with animation; walls block movement.
- [ ] `docs/godot_api_verified.md` lists every ⚠ VERIFY item from M1 with a result.
