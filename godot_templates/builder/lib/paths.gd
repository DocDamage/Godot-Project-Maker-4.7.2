extends RefCounted
## Path constants of a generated project. Keep identical to rpggen/paths.py
## (tests/unit/test_paths_sync.py compares them).

const META_DIR := "res://rpggen/"
const CATALOG := "res://rpggen/asset_catalog.json"
const CONFIG := "res://rpggen/generator_config.json"
const LEDGER := "res://rpggen/ownership_ledger.json"
const BUILD_STATE := "res://rpggen/build_state.json"
const RESULTS_BUILD := "res://rpggen/results/build_results.json"
const RESULTS_VALIDATE := "res://rpggen/results/validation_results.json"
const RESULTS_SMOKE := "res://rpggen/results/smoke_results.json"
const PACKS_DIR := "res://assets/packs/"
const GEN_DIR := "res://generated/"
const TILESETS_DIR := "res://generated/tilesets/"
const SPRITE_FRAMES_DIR := "res://generated/sprite_frames/"
const GEN_SCENES_DIR := "res://generated/scenes/"
const PLACEHOLDER_DIR := "res://generated/debug_placeholders/"
const BUILDER_DIR := "res://generated/builder/"
const GAME_DIR := "res://game/"
const RUNTIME_ADDON := "res://addons/rpg_runtime/"
const TOOLS_ADDON := "res://addons/rpg_project_tools/"
