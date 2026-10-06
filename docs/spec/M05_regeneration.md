# M5 — Regeneration Safety

**Goal:** a user can regenerate after editing the project and updating a pack. Painted tiles never change. User-owned files are never touched. User-edited generated files are never silently overwritten. Every change can be rolled back.

**The three invariants.** Each one has a dedicated test in T5.08.
1. **Tile invariant:** for every TileMapLayer in every map under `game/`, the tuple list `(cell, source_id, atlas_coords, alternative)` is identical before and after regeneration, unless the user explicitly resolved a CONFLICT.
2. **Ownership invariant:** no file under `game/` changes, and no file that the user modified or created changes.
3. **Atomicity invariant:** if generation fails at any point, the target folder is byte-identical to before.

---

## T5.01 — Ledger

**Depends on:** M4 gate
**Files:** `rpggen/core/ledger.py`, `tests/unit/test_ledger.py`

```python
TEXT_EXTS = {".gd", ".tscn", ".tres", ".json", ".cfg", ".godot", ".md", ".import", ".uid", ".txt", ".csv", ".gitignore", ".gitattributes"}

def file_hash(path: Path) -> str:
    """sha256. Text files (by extension, or name for dotfiles): read bytes, replace b"\\r\\n"
    with b"\\n", then hash. Others: raw bytes."""

@dataclass
class LedgerEntry:
    sha256: str
    written_by: str
    owner: Literal["generated", "user_seed"]

@dataclass
class Ledger:
    files: dict[str, LedgerEntry]
    deleted_by_user: list[str]
    def load(path) / save(path)

class FileState(StrEnum):
    UNTOUCHED = "untouched"          # exists, hash == ledger
    MODIFIED = "modified"            # exists, hash != ledger
    DELETED = "deleted"              # in ledger, missing on disk (and not already in deleted_by_user)
    UNKNOWN = "unknown"              # exists, not in ledger (user-created or pre-existing)
    ABSENT = "absent"                # not in ledger, not on disk

def classify(target: Path, rel: str, ledger: Ledger) -> FileState
```

**Which paths the ledger covers:** everything the generator writes under `generated/`, `addons/rpg_runtime/`, `addons/rpg_project_tools/`, `rpggen/` (except `rpggen/logs/` and `rpggen/results/`), `assets/packs/`, `project.godot`, `.gitignore`, `.gitattributes`, `README.md` and `GENERATION_REPORT.md`. Files in `game/` are recorded with owner `user_seed` at the time they are created.

`project.godot` special case: users change project settings constantly. Treat it as **merge-managed**: never conflict on it. The builder applies only the keys it owns (T1.07 table) on top of the user's file, so it is excluded from MODIFIED conflict handling. Its ledger entry is informational.

---

## T5.02 — Regeneration staging

**Depends on:** T5.01
**Files:** `rpggen/core/staging.py` (extend), `tests/unit/test_staging_regen.py`

`create_staging(target)` now supports three modes:

| Target state | Mode | Behavior |
|--------------|------|----------|
| Missing or empty | `new` | Fresh staging (as before). |
| Contains `rpggen/generator_config.json` | `regenerate` | Copy the whole target into staging, except `.rpggen_*` folders. **Include `.godot/`** so the import cache is reused. Use `shutil.copytree(dirs_exist_ok=False, copy_function=shutil.copy2)`. Where the volume supports it, try hard links for `assets/packs/**` (`os.link`), falling back to copy. Hard links are safe because files under `assets/packs` are never modified in place; they are only replaced. |
| Anything else | — | ENV-009 error. |

`install_templates` and `install_pack` in regenerate mode:
* Write template files only if their content differs (compare `file_hash`), so untouched files keep their mtime.
* Pack files: remove files that are no longer in any pack's inventory **only** if their ledger owner is `generated` and their state is UNTOUCHED. Otherwise keep them and report REGEN-003.

The builder then runs in staging as usual. Recipes skip unchanged outputs (build_state), and user_seed recipes skip existing files.

---

## T5.03 — Promotion with backup and conflicts

**Depends on:** T5.02
**Files:** `rpggen/core/promote.py`, `rpggen/core/staging.py` (remove the old `promote`), `tests/unit/test_promote.py`

```python
@dataclass
class PromotionPlan:
    write: list[str]          # staging → target (new or changed, allowed)
    conflicts: list[str]      # target MODIFIED by user and staging differs → write .rpggen-new
    delete: list[str]         # generated files removed this run, UNTOUCHED in target
    skipped_deleted: list[str]# user deleted; staging would recreate → skip (REGEN-002)

def plan(target: Path, staging: Path, ledger: Ledger, new_ledger: Ledger) -> PromotionPlan
def execute(plan, target, staging, backup_root) -> None
```

**Planning rules**, for each path in `new_ledger.files ∪ old ledger.files`:
* Staging bytes equal target bytes (hash) → nothing to do.
* `owner == user_seed` and the file exists in the target → nothing to do. User_seed files are only ever **created**.
* State `UNTOUCHED` or `ABSENT` → `write`.
* State `MODIFIED` → `conflicts`. The staging version is written to `<path>.rpggen-new`, and REGEN-001 is raised.
* State `DELETED` → `skipped_deleted`. The path is added to `deleted_by_user`, and REGEN-002 is raised.
* The path is in the old ledger but not in the new one, and the target state is UNTOUCHED → `delete`.
* Paths that are UNKNOWN in the target (user-created) are never touched.
* **`.godot/` is not ledger-managed.** Copy staging's `.godot/` over the target's, except `.godot/editor/` (per-user editor state). The import cache must match the new imports.

**Execution:**
1. Create `target/.rpggen_backups/<YYYYmmdd-HHMMSS>/`. Copy every target file that will be overwritten or deleted, plus the old ledger, keeping relative paths.
2. Apply the writes. Copy each one to `<dest>.rpggen-tmp`, then `os.replace` it. Retry 3 times with 200 ms sleeps on `PermissionError`; Windows file locks come from antivirus software and from the Godot editor. If a write still fails, roll back from the backup and raise REGEN-004.
3. Apply the deletes (after backup).
4. Write the conflict `.rpggen-new` files.
5. Write the new ledger last. It is the commit point.
6. Keep the 3 newest backups and delete older ones.
7. Remove staging.

**Godot editor open:** before promotion, check for `target/.godot/editor/*.lock`-style indicators. The exact marker is ⚠ VERIFY; otherwise, try opening `project.godot` with exclusive write. If the editor appears to be open, warn: "Close the Godot editor before regenerating; open scenes may be overwritten when the editor saves." In the GUI this is a modal dialog with Retry and Cancel; in the CLI it is a failure unless `--force-while-open` is given.

**Tests:** all planning rules, with a temporary target; a simulated write failure in the middle of the batch → the target is restored and REGEN-004 is raised; backup rotation.

---

## T5.04 — TileSet merge (complete the builder path)

**Depends on:** T5.02
**Files:** `godot_templates/builder/recipes/tileset_recipe.gd`, `godot_templates/tests/unit/test_tileset_merge.gd`

Merge rules when `generated/tilesets/<name>.tres` already exists:
1. Load it. **Never** create a new TileSet object when the file exists.
2. Tile size changed in the def → don't change it; report TILE-004 (the user must resolve it).
3. For each def source:
   * The source exists by id → update the texture, region size, margins and separation **only if** they changed in the catalog AND the asset status is not CONFLICT. CONFLICT assets are left completely untouched.
   * New id → add it with the explicit id.
4. Sources that exist in the TileSet but not in the def, with their id in `retired` → **keep them**, and report REGEN-003. The user removes them in the audit; once confirmed, the asset's status becomes UNUSED with a `remove_source: true` override. Only then does the recipe call `ts.remove_source(id)`.
5. Within a source:
   * Create tiles for new non-empty cells.
   * Never remove tiles. Cells that became empty → TILE-005.
   * Collision: replace a tile's collision **only if** the catalog's effective collision for that tile changed since the last build. Store the hash of the last-applied collision spec per tile in TileData custom metadata: `td.set_meta("rpggen_col_hash", h)` ⚠ VERIFY that meta on TileData persists. If it doesn't, keep the hashes in `rpggen/tileset_apply_state.json`.
   * If the current polygons differ from what rpggen last applied (the user edited collision in the Godot editor), keep the user's polygons and emit an info issue. Add the code **TILE-007** `"Collision on {asset} {coords} was edited in Godot and kept."`.
6. Physics layers, custom data layers and terrain sets: add missing ones by name; never remove or reorder them.

**Tests (GDScript):** build a TileSet; paint a map; change the catalog (add a sheet, change one tile's collision, delete another sheet); rebuild; the map cells are unchanged; the new source has the next id; the removed source is still present.

---

## T5.05 — Pack updates and diffing

**Depends on:** T5.03
**Files:** `rpggen/core/pack_diff.py`, `rpggen/gui/pages/project_page.py` (an update flow), `tests/unit/test_pack_diff.py`

```python
@dataclass
class PackDiff:
    added: list[str]; removed: list[str]; changed_same_size: list[str]
    changed_resized: list[str]; unchanged: list[str]

def diff(old_inv: Inventory, new_inv: Inventory) -> PackDiff
```

* Match files by **path**. When paths differ but the hash matches a removed file (the vendor renamed it), treat it as a rename: map the asset id to the new path and keep overrides and source ids. Record the change in the catalog as `renamed_from`.
* The GUI shows "Update pack…" on page 1 when regenerating. The user selects the new archive for an existing pack_id, and a summary dialog lists the counts and the resized assets (which will become CONFLICT).
* The audit opens with the filter "Changed in update" (added, resized, missing).

---

## T5.06 — Generated project VCS files and git init

**Depends on:** T5.03
**Files:** `godot_templates/project_files/gitignore.txt`, `godot_templates/project_files/gitattributes.txt`, `rpggen/core/staging.py`, `rpggen/core/vcs.py`

`.gitignore` (written as `.gitignore`):
```
.godot/
*.tmp
*.rpggen-tmp
.rpggen_staging/
.rpggen_failed/
.rpggen_backups/
rpggen/logs/
export/
```

`.gitattributes`:
```
* text=auto eol=lf
*.png binary
*.jpg binary
*.webp binary
*.wav binary
*.ogg binary
*.mp3 binary
*.ttf binary
*.otf binary
# Optional Git LFS (uncomment to enable; requires git-lfs):
# *.png filter=lfs diff=lfs merge=lfs -text
# *.wav filter=lfs diff=lfs merge=lfs -text
# *.ogg filter=lfs diff=lfs merge=lfs -text
```

`vcs.py`: `git_available() -> bool`; `init_and_commit(target, message) -> bool`. It runs `git init`, `git add -A` and `git commit -m` with `-c user.name=rpggen -c user.email=rpggen@localhost` **only if** no global identity is configured. It never pushes. The Options page gets a checkbox "Initialize git repository" (default on when git is available and the target is new). On regeneration, it offers "Commit regeneration" (default off).

---

## T5.07 — Restore previous generation

**Depends on:** T5.03
**Files:** `rpggen/core/promote.py` (`restore`), `rpggen/cli.py` (`restore` subcommand), the Results page button

* `restore(target, backup_dir)`:
  1. Make a fresh backup of the current state of the files about to be restored.
  2. Copy the backup's files back.
  3. Restore the backed-up ledger.
  4. Remove files that the later generation created, which the old ledger doesn't list, if they are UNTOUCHED.
* The CLI command `rpggen restore --target X [--backup NAME]` defaults to the newest backup.

---

## T5.08 — Regeneration test suite and report completion

**Depends on:** T5.04, T5.05, T5.06, T5.07
**Files:** `tests/integration/test_regeneration.py`, `godot_templates/builder/tools/dump_map_cells.gd`, `rpggen/core/report.py` (complete)

`dump_map_cells.gd` (an `--script` tool) writes `{map_path: {layer_name: [[x,y,source,ax,ay,alt], …sorted]}}` for every map under `res://game/maps`. It is used to compare before and after.

Integration scenarios (each starts by generating the sample pack into a temporary target):
1. **No-op regenerate:** regenerate immediately. Assert zero changed files apart from `rpggen/logs`, `rpggen/results`, `.godot/` and `GENERATION_REPORT.md` timestamps. **Also: if git is available, `git status --porcelain` is empty after committing the first generation and regenerating.**
2. **User paints:** use `--script` to add 50 cells across layers in `starter_map.tscn` (simulating user work), and add `game/scripts/my_thing.gd`. Regenerate. The cell dump is equal and `my_thing.gd` is unchanged.
3. **User edits a generated scene:** change a property in `generated/scenes/objects/<x>.tscn`. Change that object's catalog footprint, then regenerate. The target file is unchanged, `.rpggen-new` exists and REGEN-001 is reported.
4. **Pack update:** replace one tile sheet with a same-size modified one, add a new sheet and remove one sheet. Regenerate. The cell dump is equal; the new source id is `next_source_id`; the removed source is still in the TileSet; REGEN-003 is reported.
5. **Resized sheet:** CONFLICT is reported and the TileSet source is untouched.
6. **Failure atomicity:** inject a smoke failure (sabotage hook) during regeneration. The target is byte-identical (recursive hash) to before.
7. **Restore:** regenerate with a change, restore, and the target equals the pre-regeneration state.

`report.py`, the final structure of `GENERATION_REPORT.md`:
```markdown
# Generation Report
- Generator: rpggen <ver> · Godot <ver> · Archetype <x> · Result: SUCCESS|FAILED
## What to review          ← every warning with a fix, grouped by priority (conflicts, placeholders, needs-review assets, assumed doors, licenses)
## Packs and licenses      ← pack_id, source file name, license files, warnings (RTP etc.)
## Summary                 ← counts table
## TileSets                ← name, tile size, sources (id → asset), terrains
## Scenes                  ← generated scenes count by folder
## Animations              ← per asset: animation names
## Regeneration            ← written / skipped / conflicts / deleted-by-user lists (regenerate mode)
## Validation              ← per check: pass/fail counts
## Smoke test              ← per step: ok, ms
## Issues                  ← full table: code, severity, file, message, fix
```
Write the report in staging, and also in the failed folder on failure.

---

## T5.09 — Milestone Gate M5

- [ ] All 7 regeneration scenarios pass in CI.
- [ ] The three invariants are documented in the generated `README.md` (T6.15) and in `docs/regeneration.md`.
- [ ] Manual check: regenerate while the Godot editor is open → the warning appears; close the editor → regeneration succeeds; reopen the project → the painted map is intact.
