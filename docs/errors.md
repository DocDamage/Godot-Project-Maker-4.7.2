# Error codes

<!-- GENERATED from docs/spec/03_ERROR_CODES.md by tools/gen_error_codes.py -->

## Environment (ENV)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| ENV-001 | error | Godot executable not found at {path}. | Select the Godot 4.7.2 executable (the `_console.exe` build if available). |
| ENV-002 | error | Godot version {found} is not supported (need 4.7.x). | Install Godot 4.7.2 and select it. |
| ENV-003 | warning | Godot {found} is not the validated version 4.7.2. | Use 4.7.2 for guaranteed results. |
| ENV-004 | error | Output folder {path} is not writable. | Choose a folder you can write to. |
| ENV-005 | error | Not enough disk space: need {need_mb} MB, have {have_mb} MB. | Free disk space or choose another drive. |
| ENV-006 | warning | Output folder is inside a cloud-sync folder ({provider}). | Prefer a local folder; sync can lock files during generation. |
| ENV-007 | warning | Some output paths may exceed 260 characters (longest: {length}). | Use a shorter output folder or enable Windows long paths. |
| ENV-008 | error | Output folder is inside the asset pack folder. | Choose an output folder outside the pack. |
| ENV-009 | error | Output folder is not empty and is not an rpggen project. | Choose an empty folder or an existing generated project. |
| ENV-010 | info | Export templates for 4.7.2 not installed; export check skipped. | Install export templates from the Godot editor to enable the check. |

## Archives (ARCH)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| ARCH-001 | error | Archive {path} cannot be opened: {reason}. | Re-download the pack or extract it and select the folder. |
| ARCH-002 | error | Archive is password-protected. | Extract it manually and select the folder. |
| ARCH-003 | error | Unsafe path in archive: {entry}. | The archive is malformed; contact the vendor. |
| ARCH-004 | error | Archive exceeds limits ({reason}). | Extract manually if you trust the archive. |
| ARCH-005 | warning | Case-insensitive name collision: {a} vs {b}; kept {kept}. | Rename one file in a copy of the pack if both are needed. |
| ARCH-006 | info | Nested archive {entry} extracted. | — |
| ARCH-007 | warning | RAR archives need 7-Zip or UnRAR installed. | Install 7-Zip, or extract manually. |
| ARCH-008 | info | Skipped OS junk file {entry}. | — |

## Assets (ASSET)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| ASSET-001 | warning | Tile size could not be confidently determined for {file} (best {cell} at {score}). | Confirm the grid in the audit. |
| ASSET-002 | warning | Image {file} could not be decoded. | Replace or exclude the file. |
| ASSET-003 | warning | Grid for {file} does not divide the image evenly; {remainder} px ignored. | Check margin/separation in the grid editor. |
| ASSET-010 | warning | No asset with role {role} found; required by {feature}. | Assign one in Mapping, or use a placeholder. |
| ASSET-011 | info | Placeholder used for role {role}. | Replace before shipping. |
| ASSET-014 | warning | Multiple candidates for {role}: {candidates}. | Pick one in Mapping. |
| ASSET-020 | warning | RPG Maker RTP asset detected: {file}. | RTP assets are licensed for RPG Maker only; replace them. |
| ASSET-021 | info | Pack {pack_id} has no license file. | Check the vendor's license terms. |

## Adapters (ADAPT)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| ADAPT-001 | warning | Adapter {adapter} failed on {file}: {reason}. | Report a bug with a diagnostic bundle. |
| ADAPT-002 | warning | Tiled tileset {file} references missing image {image}. | Fix the pack or map the image manually. |
| ADAPT-003 | info | Pack profile {profile_id} matched ({ratio}). | — |

## Catalog (CAT)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| CAT-001 | error | {file} is not valid JSON: {reason}. | Restore from backup or regenerate. |
| CAT-002 | error | {file} does not match schema: {reason}. | Restore from backup or regenerate. |
| CAT-003 | error | Catalog version {found} is newer than this generator supports. | Update rpggen. |
| CAT-004 | warning | Asset {asset} references missing file {file}. | Re-add the file or remove the asset. |
| CAT-005 | error | Duplicate source_id {source_id} in tileset {tileset}. | Report a bug; do not edit source ids by hand. |

## Tiles (TILE)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| TILE-001 | error | TileSet {tileset} has no sources. | Assign at least one tile sheet to it. |
| TILE-002 | warning | Tile region outside texture in {asset} at {coords}. | Fix grid margin/separation. |
| TILE-003 | warning | Collision profile for {asset} could not be inferred. | Set a collision profile in the audit. |
| TILE-004 | warning | Atlas {asset} changed size; painted tiles may be shifted. | Review the asset (status CONFLICT). |
| TILE-005 | warning | Tiles at {coords} in {asset} became empty but are kept. | Remove them in Godot if unused. |
| TILE-006 | warning | Terrain layout in {asset} not recognized; terrain skipped. | Paint manually or set terrain in the audit. |
| TILE-007 | info | Collision on {asset} {coords} was edited in Godot and kept. | — |
| TILE-008 | info | Tile animation at {coords} in {asset} is not a horizontal run and was skipped. | Rearrange frames in a copy of the sheet if needed. |

## Animation (ANIM)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| ANIM-001 | warning | Animation {anim} of {asset} has no frames. | Fix frames in the animation preview. |
| ANIM-002 | info | {anim} generated by mirroring {source_anim}. | — |

## Build (BUILD)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| BUILD-001 | error | Godot import failed (exit {code}). | See the godot_import log. |
| BUILD-002 | error | Recipe {recipe} failed: {reason}. | See the godot_build log. |
| BUILD-003 | error | Godot {phase} timed out after {seconds}s. | Retry; if it repeats, file a bug with diagnostics. |
| BUILD-004 | error | Could not save {file}: Godot error {err}. | Check disk space and permissions. |

## Validation (VAL)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| VAL-001 | error | Script failed to parse: {file}. | Fix the script (see log). |
| VAL-002 | error | Resource failed to load: {file}. | See the validate log. |
| VAL-003 | error | Missing dependency {dep} of {file}. | Regenerate, or restore the missing file. |
| VAL-004 | error | Scene failed to instantiate: {file}. | See the validate log. |
| VAL-005 | error | Main scene missing or invalid. | Regenerate. |
| VAL-006 | error | Autoload {name} failed to load. | Regenerate. |
| VAL-007 | error | Input action {action} has no events. | Check generator_config input. |
| VAL-008 | error | Duplicate entity_id {id} in {files}. | Change one id in the Inspector. |
| VAL-009 | warning | Empty entity_id on {node} in {file}. | Use the dock's "Fix entity IDs". |
| VAL-010 | error | Map round-trip failed on layer {layer}. | Report a bug with diagnostics. |
| VAL-011 | warning | Menu {scene} has focus problems: {reason}. | Fix focus neighbors. |
| VAL-012 | warning | Debug placeholder still referenced by {file}. | Assign a real asset before shipping. |
| VAL-013 | error | Runtime error logged: {line}. | See the log. |
| VAL-014 | warning | Visual of {file} is not aligned to its origin (bottom at {y}). | Set the origin in the animation/object editor. |
| VAL-015 | warning | Entity {node} in {file} is not under a Y-sorted parent. | Move it under YSorted/Entities. |
| VAL-016 | error | Door {node} in {file} targets missing map {target}. | Fix target_map in the Inspector. |
| VAL-017 | error | Door {node} in {file} targets unknown spawn {spawn} in {target}. | Add the spawn point or fix target_spawn. |
| VAL-018 | warning | Dialogue {file} line {n} mixes and/or; evaluation is left-to-right. | Split the condition or reorder it. |
| VAL-019 | warning | Dialogue {file} references unknown item {item}. | Create the item or fix the id. |

## Smoke test (SMOKE)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| SMOKE-001 | error | Smoke step {step} "{name}" failed: {detail}. | See smoke log and smoke_results.json. |
| SMOKE-002 | error | Smoke test timed out at step {step}. | See smoke log. |

## Regeneration (REGEN)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| REGEN-001 | warning | User-modified generated file {file} not overwritten; new version at {file}.rpggen-new. | Merge changes manually. |
| REGEN-002 | info | File {file} was deleted by the user and was not recreated. | — |
| REGEN-003 | warning | Source {asset} removed from pack; tileset source {source_id} kept. | Confirm removal in the audit. |
| REGEN-004 | error | Staging promotion failed: {reason}. Target restored from backup. | See log. |
| REGEN-005 | error | The Godot editor appears to be open for {path}. | Close the Godot editor before regenerating; open scenes may be overwritten when the editor saves. |

## GUI (GUI)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| GUI-001 | error | Unexpected error: {reason}. | Export a diagnostic bundle and report it. |
