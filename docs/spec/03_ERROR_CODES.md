# 03 — Error Codes

This table is the single source of truth. T1.03 turns it into `rpggen/errors_table.py` (Python) and `godot_templates/builder/lib/error_codes.gd` (GDScript), using `tools/gen_error_codes.py`, which parses this markdown table. `docs/errors.md` is generated from the same table.

Severity: **E** = error (blocks delivery), **W** = warning, **I** = info.

| Code | Sev | Message template | Recommended fix |
|------|-----|------------------|-----------------|
| ENV-001 | E | Godot executable not found at {path}. | Select the Godot 4.7.2 executable (the `_console.exe` build if available). |
| ENV-002 | E | Godot version {found} is not supported (need 4.7.x). | Install Godot 4.7.2 and select it. |
| ENV-003 | W | Godot {found} is not the validated version 4.7.2. | Use 4.7.2 for guaranteed results. |
| ENV-004 | E | Output folder {path} is not writable. | Choose a folder you can write to. |
| ENV-005 | E | Not enough disk space: need {need_mb} MB, have {have_mb} MB. | Free disk space or choose another drive. |
| ENV-006 | W | Output folder is inside a cloud-sync folder ({provider}). | Prefer a local folder; sync can lock files during generation. |
| ENV-007 | W | Some output paths may exceed 260 characters (longest: {length}). | Use a shorter output folder or enable Windows long paths. |
| ENV-008 | E | Output folder is inside the asset pack folder. | Choose an output folder outside the pack. |
| ENV-009 | E | Output folder is not empty and is not an rpggen project. | Choose an empty folder or an existing generated project. |
| ENV-010 | I | Export templates for 4.7.2 not installed; export check skipped. | Install export templates from the Godot editor to enable the check. |
| ARCH-001 | E | Archive {path} cannot be opened: {reason}. | Re-download the pack or extract it and select the folder. |
| ARCH-002 | E | Archive is password-protected. | Extract it manually and select the folder. |
| ARCH-003 | E | Unsafe path in archive: {entry}. | The archive is malformed; contact the vendor. |
| ARCH-004 | E | Archive exceeds limits ({reason}). | Extract manually if you trust the archive. |
| ARCH-005 | W | Case-insensitive name collision: {a} vs {b}; kept {kept}. | Rename one file in a copy of the pack if both are needed. |
| ARCH-006 | I | Nested archive {entry} extracted. | — |
| ARCH-007 | W | RAR archives need 7-Zip or UnRAR installed. | Install 7-Zip, or extract manually. |
| ARCH-008 | I | Skipped OS junk file {entry}. | — |
| ASSET-001 | W | Tile size could not be confidently determined for {file} (best {cell} at {score}). | Confirm the grid in the audit. |
| ASSET-002 | W | Image {file} could not be decoded. | Replace or exclude the file. |
| ASSET-003 | W | Grid for {file} does not divide the image evenly; {remainder} px ignored. | Check margin/separation in the grid editor. |
| ASSET-010 | W | No asset with role {role} found; required by {feature}. | Assign one in Mapping, or use a placeholder. |
| ASSET-011 | I | Placeholder used for role {role}. | Replace before shipping. |
| ASSET-014 | W | Multiple candidates for {role}: {candidates}. | Pick one in Mapping. |
| ASSET-020 | W | RPG Maker RTP asset detected: {file}. | RTP assets are licensed for RPG Maker only; replace them. |
| ASSET-021 | I | Pack {pack_id} has no license file. | Check the vendor's license terms. |
| ADAPT-001 | W | Adapter {adapter} failed on {file}: {reason}. | Report a bug with a diagnostic bundle. |
| ADAPT-002 | W | Tiled tileset {file} references missing image {image}. | Fix the pack or map the image manually. |
| ADAPT-003 | I | Pack profile {profile_id} matched ({ratio}). | — |
| CAT-001 | E | {file} is not valid JSON: {reason}. | Restore from backup or regenerate. |
| CAT-002 | E | {file} does not match schema: {reason}. | Restore from backup or regenerate. |
| CAT-003 | E | Catalog version {found} is newer than this generator supports. | Update rpggen. |
| CAT-004 | W | Asset {asset} references missing file {file}. | Re-add the file or remove the asset. |
| CAT-005 | E | Duplicate source_id {source_id} in tileset {tileset}. | Report a bug; do not edit source ids by hand. |
| TILE-001 | E | TileSet {tileset} has no sources. | Assign at least one tile sheet to it. |
| TILE-002 | W | Tile region outside texture in {asset} at {coords}. | Fix grid margin/separation. |
| TILE-003 | W | Collision profile for {asset} could not be inferred. | Set a collision profile in the audit. |
| TILE-004 | W | Atlas {asset} changed size; painted tiles may be shifted. | Review the asset (status CONFLICT). |
| TILE-005 | W | Tiles at {coords} in {asset} became empty but are kept. | Remove them in Godot if unused. |
| TILE-006 | W | Terrain layout in {asset} not recognized; terrain skipped. | Paint manually or set terrain in the audit. |
| TILE-007 | I | Collision on {asset} {coords} was edited in Godot and kept. | — |
| TILE-008 | I | Tile animation at {coords} in {asset} is not a horizontal run and was skipped. | Rearrange frames in a copy of the sheet if needed. |
| ANIM-001 | W | Animation {anim} of {asset} has no frames. | Fix frames in the animation preview. |
| ANIM-002 | I | {anim} generated by mirroring {source_anim}. | — |
| BUILD-001 | E | Godot import failed (exit {code}). | See the godot_import log. |
| BUILD-002 | E | Recipe {recipe} failed: {reason}. | See the godot_build log. |
| BUILD-003 | E | Godot {phase} timed out after {seconds}s. | Retry; if it repeats, file a bug with diagnostics. |
| BUILD-004 | E | Could not save {file}: Godot error {err}. | Check disk space and permissions. |
| VAL-001 | E | Script failed to parse: {file}. | Fix the script (see log). |
| VAL-002 | E | Resource failed to load: {file}. | See the validate log. |
| VAL-003 | E | Missing dependency {dep} of {file}. | Regenerate, or restore the missing file. |
| VAL-004 | E | Scene failed to instantiate: {file}. | See the validate log. |
| VAL-005 | E | Main scene missing or invalid. | Regenerate. |
| VAL-006 | E | Autoload {name} failed to load. | Regenerate. |
| VAL-007 | E | Input action {action} has no events. | Check generator_config input. |
| VAL-008 | E | Duplicate entity_id {id} in {files}. | Change one id in the Inspector. |
| VAL-009 | W | Empty entity_id on {node} in {file}. | Use the dock's "Fix entity IDs". |
| VAL-010 | E | Map round-trip failed on layer {layer}. | Report a bug with diagnostics. |
| VAL-011 | W | Menu {scene} has focus problems: {reason}. | Fix focus neighbors. |
| VAL-012 | W | Debug placeholder still referenced by {file}. | Assign a real asset before shipping. |
| VAL-013 | E | Runtime error logged: {line}. | See the log. |
| VAL-014 | W | Visual of {file} is not aligned to its origin (bottom at {y}). | Set the origin in the animation/object editor. |
| VAL-015 | W | Entity {node} in {file} is not under a Y-sorted parent. | Move it under YSorted/Entities. |
| VAL-016 | E | Door {node} in {file} targets missing map {target}. | Fix target_map in the Inspector. |
| VAL-017 | E | Door {node} in {file} targets unknown spawn {spawn} in {target}. | Add the spawn point or fix target_spawn. |
| VAL-018 | W | Dialogue {file} line {n} mixes and/or; evaluation is left-to-right. | Split the condition or reorder it. |
| VAL-019 | W | Dialogue {file} references unknown item {item}. | Create the item or fix the id. |
| SMOKE-001 | E | Smoke step {step} "{name}" failed: {detail}. | See smoke log and smoke_results.json. |
| SMOKE-002 | E | Smoke test timed out at step {step}. | See smoke log. |
| REGEN-001 | W | User-modified generated file {file} not overwritten; new version at {file}.rpggen-new. | Merge changes manually. |
| REGEN-002 | I | File {file} was deleted by the user and was not recreated. | — |
| REGEN-003 | W | Source {asset} removed from pack; tileset source {source_id} kept. | Confirm removal in the audit. |
| REGEN-004 | E | Staging promotion failed: {reason}. Target restored from backup. | See log. |
| GUI-001 | E | Unexpected error: {reason}. | Export a diagnostic bundle and report it. |

## Rules for adding codes

1. Add a row here with the next free number in the area.
2. Run `python tools/gen_error_codes.py`.
3. Commit the regenerated files with the change that uses the code.

Message templates use `{name}` placeholders, which are filled from the `detail` dict. The generator script fails if a placeholder is not a valid identifier.
