"""What the Options page decides, without its widgets: the draft config, feature dependencies,
the starter and imported maps, the input table, presets, the summary and validation. The pure
rules are in ``rpggen.core.options``; this class keeps the page's state around them."""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpggen.core import app_settings, options, preflight
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.gui.models.forms import Translate, no_translation
from rpggen.gui.state import WizardState

INPUT_COLUMNS = ("Action", "Keys", "Mouse buttons", "Joy buttons")
SEED_MAX = 2**31 - 1
LAYER_MESSAGES = {
    options.LAYER_GROUND_REQUIRED: "The Ground layer is required.",
    options.LAYER_EMPTY: "Layer names cannot be empty.",
    options.LAYER_DUPLICATE: "Layer names must be unique.",
}
BUILTIN_PREFIX = "__builtin__:"  # the combo's data of a built-in preset: the prefix and its key
DEFAULTS_ITEM = BUILTIN_PREFIX + "everything"  # the defaults: the built-in preset "Everything"
STARTER_COUNTS = (
    ("buildings", "Buildings"),
    ("npcs", "Villagers"),
    ("enemies", "Enemies"),
    ("chests", "Chests"),
    ("decorations", "Decorations"),
    ("ground_patches", "Ground patches"),
)
STARTER_SIZE_NAMES = {(32, 20): "Small", (40, 24): "Medium", (64, 40): "Large"}
EXISTING_MAP_TEXT = (
    "The starter map already exists and is yours; these options apply to new projects."
)
EXISTING_WORLD_TEXT = (
    "This project has its world: the rooms that exist are kept as they are. "
    "You can still add a room below; it is joined to the room you name."
)
ABILITY_LABELS = {
    "double_jump": "Double jump",
    "dash": "Dash",
    "wall_jump": "Wall jump",
    "high_jump": "High jump",
    "break_blocks": "Break blocks",
}
# what a room is made of (T14.06); a metroidvania's layer list shows these and cannot be edited
ROOM_LAYERS = ("Background", "Ground", "Platforms", "Hazards", "Decoration", "Foreground")
IMPORTED_STARTER_TEXT = (
    "The starter map is an imported map, so the layout options are not used. "
    "Set the starter map under Imported maps back to the layout options to use them."
)
PACK_ART_LABELS = {
    "commit": "Commit the pack art with the project",
    "lfs": "Use Git LFS for the pack art",
    "ignore": "Leave the pack art out of git",
}
EXPORT_TARGET_LABELS = {
    "windows": "Windows",
    "web": "Web (for itch.io)",
    "linux": "Linux",
    "macos": "macOS (unsigned)",
}


@dataclass(frozen=True)
class FeatureState:
    """A feature that depends on others: off and disabled while one of them is off."""

    enabled: bool
    checked: bool
    tooltip: str
    needs: str  # "" when nothing is missing


@dataclass(frozen=True)
class StarterState:
    """Which starter map controls can change, and the note that says why not."""

    layout_enabled: bool  # size, counts, ground set and reset
    imported_enabled: bool  # the imported-map starter combo
    note: str
    note_visible: bool  # also: the preview shows the note instead of a map


@dataclass
class OptionValues:
    """Everything the widgets show, read back in one go."""

    features: dict[str, bool]
    resolution: tuple[int, int]
    window_size: tuple[int, int]
    layers: list[str]
    seed: int
    starter: dict[str, Any]
    imported: dict[str, Any] | None  # None when the packs have no maps
    input_rows: list[tuple[str, list[str]]]


class OptionsModel:
    """The draft config of the Options page and the decisions about it."""

    def __init__(self, tr: Translate = no_translation) -> None:
        self.tr = tr
        self.state: WizardState | None = None
        self.draft: config_mod.GeneratorConfig | None = None
        self.input_map: dict[str, dict[str, Any]] = {}
        self.input_errors: list[str] = []
        self.wishes: dict[str, bool] = {}  # what the user wants of each dependent feature
        self.starter_locked = False
        self._pack_bytes_key: tuple | None = None
        self._pack_bytes = 0

    # ------------------------------------------------------------------ state

    def enter(self, state: WizardState) -> None:
        """Takes a copy of the state's config as the draft (None without a config)."""
        self.state = state
        cfg = state.config
        if cfg is None:
            self.draft = None
            return
        self.draft = dataclasses.replace(
            cfg,
            map_layers=list(cfg.map_layers),
            features=dict(cfg.features),
            input=copy.deepcopy(cfg.input),
            validation=dict(cfg.validation),
            starter_map=copy.deepcopy(cfg.starter_map),
            imported_maps=copy.deepcopy(cfg.imported_maps),
            git=dict(cfg.git),
            export_targets=cfg.selected_export_targets(),
        )
        self.starter_locked = self.starter_exists()

    def loaded(self) -> None:
        """The draft is about to be shown: the wishes start from it."""
        assert self.draft is not None
        self.wishes = {
            key: bool(self.draft.features.get(key, False)) for key in options.DEPENDENCIES
        }
        self.input_map = copy.deepcopy(self.draft.input)

    def apply_to(self, cfg: config_mod.GeneratorConfig) -> None:
        """Writes the draft into ``cfg`` (an existing starter map keeps its options)."""
        assert self.draft is not None
        cfg.features = dict(self.draft.features)
        cfg.resolution = self.draft.resolution
        cfg.window_size = self.draft.window_size
        cfg.map_layers = list(self.draft.map_layers)
        cfg.seed = self.draft.seed
        cfg.input = copy.deepcopy(self.draft.input)
        cfg.validation = dict(self.draft.validation)
        cfg.git = dict(self.draft.git)
        cfg.export_targets = self.draft.selected_export_targets()
        cfg.repair_world = self.draft.repair_world
        if not self.starter_locked:
            cfg.starter_map = copy.deepcopy(self.draft.starter_map)
        else:  # the map is the user's, but a world may still get a new area (or a new room)
            key = self.kept_key
            kept = {k: v for k, v in cfg.starter_map.items() if k != key}
            if self.draft.starter_map.get(key):
                kept[key] = copy.deepcopy(self.draft.starter_map[key])
            cfg.starter_map = kept
        cfg.imported_maps = copy.deepcopy(self.draft.imported_maps)

    @property
    def catalog(self) -> catalog_mod.Catalog | None:
        return self.state.catalog if self.state else None

    # ------------------------------------------------------------------ git

    def git_box(self, available: bool) -> tuple[str, str, bool]:
        """New project: "Initialize git repository" (on by default). Regeneration: "Commit
        regeneration" (off by default). Off without git. (text, tooltip, checked)"""
        state = self.state
        regenerating = bool(state and state.regenerating)
        text = (
            self.tr("Commit regeneration") if regenerating else self.tr("Initialize git repository")
        )
        tooltip = "" if available else self.tr("git was not found on this computer")
        want = state.git_commit if state and state.git_commit is not None else not regenerating
        return text, tooltip, bool(want) and available

    def set_git(self, checked: bool) -> None:
        if self.state is not None:
            self.state.git_commit = checked

    def set_pack_art(self, choice: str) -> None:
        assert self.draft is not None
        if choice == config_mod.GIT_DEFAULTS["pack_art"]:
            self.draft.git.pop("pack_art", None)
        else:
            self.draft.git["pack_art"] = choice

    # ------------------------------------------------------------------ export targets

    def set_export_target(self, key: str, checked: bool) -> bool:
        """Turns one export target on or off. False (and nothing changes) when it would leave
        no target: the project always has at least one export preset."""
        assert self.draft is not None
        chosen = set(self.draft.selected_export_targets())
        if checked:
            chosen.add(key)
        else:
            chosen.discard(key)
        if not chosen:
            return False
        self.draft.export_targets = [t for t in config_mod.EXPORT_TARGETS if t in chosen]
        return True

    # ------------------------------------------------------------------ features

    def feature_wish(self, key: str, checked: bool) -> None:
        if key in options.DEPENDENCIES:
            self.wishes[key] = checked

    @property
    def demo_wish(self) -> bool:  # the name before 1.1, when the demo was the only one
        return self.wishes.get("demo", True)

    def dependent_features(self, current: dict[str, bool]) -> dict[str, FeatureState]:
        """A feature whose dependencies are off is unchecked and disabled and says what it needs;
        it returns to the user's choice once they are on again."""
        out = {}
        for key in options.DEPENDENCIES:
            missing = options.missing_deps(current, key)
            if missing:
                names = ", ".join(self.tr(options.feature_label(m)) for m in missing)
                out[key] = FeatureState(
                    False,
                    False,
                    self.tr("Requires: {0}").format(names),
                    self.tr("Needs: {0}").format(names),
                )
            else:
                out[key] = FeatureState(
                    True, self.wishes.get(key, False), self.tr(options.FEATURE_INFO[key][2]), ""
                )
        return out

    def default_features(self) -> dict[str, bool]:
        defaults = config_mod.default_features()
        self.wishes = {key: bool(defaults.get(key, False)) for key in options.DEPENDENCIES}
        return defaults

    # ------------------------------------------------------------------ screen

    def tile(self) -> int:
        return self.draft.base_tile_size if self.draft else 16

    def screen_hint(self, resolution: tuple[int, int]) -> tuple[str, tuple[int, int] | None]:
        """The "tiles across" line and the suggested resolution preset."""
        tile = self.tile()
        return (
            options.tiles_hint(resolution, tile),
            options.suggested_preset(options.RESOLUTION_PRESETS, tile),
        )

    @staticmethod
    def default_screen() -> tuple[tuple[int, int], tuple[int, int]]:
        cfg = config_mod.GeneratorConfig("x", [])
        return cfg.resolution, cfg.window_size

    # ------------------------------------------------------------------ starter map

    def ground_choices(self) -> list[tuple[str, str]]:
        """(label, asset id) of the tile sheets that are GROUND."""
        catalog = self.catalog
        if catalog is None:
            return []
        return [
            (f"{a.path.rsplit('/', 1)[-1]} · {a.pack_id}", a.id)
            for a in sorted(catalog.assets, key=lambda a: a.id)
            if a.status not in ("UNUSED", "MISSING")
            and catalog_mod.effective(a).get("role") == "GROUND"
            and catalog_mod.effective(a).get("usage") == "tiles"
        ]

    @property
    def is_side(self) -> bool:
        """A metroidvania: a starter world of rooms instead of a starter map."""
        return self.draft is not None and self.draft.archetype == "metroidvania"

    @property
    def kept_key(self) -> str:
        """The one starter option that still counts once the map or the world exists: the
        table a new area or a new room is added in."""
        return "added_rooms" if self.is_side else "areas"

    def starter_exists(self) -> bool:
        state = self.state
        if state is None or not state.regenerating or state.target is None:
            return False
        if self.is_side:
            from rpggen.core import room_plan

            return room_plan.exists(state.target)
        return (state.target / "game" / "maps" / "starter_map.tscn").is_file()

    def imported_starter(self) -> str:
        return str((self.draft.imported_maps if self.draft else {}).get("starter", ""))

    def starter_state(self) -> StarterState:
        """The layout options apply to a planned starter map: not to one that already exists and
        not to an imported one."""
        locked = self.starter_locked
        if self.is_side:
            return StarterState(
                layout_enabled=not locked,
                imported_enabled=False,
                note=self.tr(EXISTING_WORLD_TEXT),
                note_visible=locked,
            )
        imported = bool(self.imported_starter()) and not locked
        text = self.tr(EXISTING_MAP_TEXT if locked else IMPORTED_STARTER_TEXT)
        return StarterState(
            layout_enabled=not locked and not imported,
            imported_enabled=not locked,  # the starter map of a project is its own
            note=text,
            note_visible=locked or imported,
        )

    def starter_defaults(self) -> dict[str, Any]:
        assert self.draft is not None
        return config_mod.starter_map_defaults(self.draft.archetype)

    def store_starter(self, values: dict[str, Any]) -> None:
        """Stores only what differs from the defaults of the archetype. The starter map of a
        project that exists keeps its options; only the areas table still counts (a new area)."""
        if self.draft is None:
            return
        key = self.kept_key
        if self.starter_locked:
            kept = {k: v for k, v in self.draft.starter_map.items() if k != key}
            if values.get(key):
                kept[key] = copy.deepcopy(values[key])
            self.draft.starter_map = kept
            return
        defaults = self.starter_defaults()
        self.draft.starter_map = {
            k: v for k, v in values.items() if k not in defaults or v != defaults[k]
        }

    def rooms_preview(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """The rooms the *Starter world* options give now, for the side-view preview: the
        stored plan (with the rooms added) once the world exists, else a fresh plan from the
        seed. ``(None, why)`` when the options do not make a world."""
        from rpggen.core import room_plan

        if self.draft is None:
            return None, ""
        state = self.state
        target = state.target if state is not None and self.starter_locked else None
        try:
            world, _notes = room_plan.for_project(target, values, self.draft.seed, self.catalog)
        except room_plan.RoomPlanError as error:
            return None, str(error)
        return world["rooms"], ""

    def built_added_rooms(self) -> int:
        """How many rows of the draft's ``added_rooms`` are rooms the project already has (they
        can no longer be renamed or removed)."""
        from rpggen.core import room_plan, world_plan

        state = self.state
        if self.draft is None or state is None or not self.starter_locked or state.target is None:
            return 0
        stored = world_plan.load(state.target) or {}
        names = {
            room_plan._slug(str(r.get("name", "")))
            for r in (stored.get("rooms") or {}).get("list", [])
        }
        rows = self.draft.starter_map.get("added_rooms", [])
        built = 0
        for row in rows:
            if room_plan._slug(str(row.get("name", ""))) not in names:
                break
            built += 1
        return built

    def world_error(self) -> str:
        """Why the draft's world options make no world ("" when they do)."""
        from rpggen.core import room_plan

        if not self.is_side or self.draft is None:
            return ""
        try:
            room_plan.normalized(self.draft.starter_map_options())
        except room_plan.RoomPlanError as error:
            return str(error)
        return ""

    def world_names(self) -> set[str]:
        """The names of the areas the project's world was built from (empty: no world yet, so
        the whole table can still change)."""
        from rpggen.core import world_plan

        state = self.state
        if state is None or not state.regenerating or state.target is None:
            return set()
        if not world_plan.exists(state.target):
            return set()
        stored = world_plan.load(state.target)
        return {str(a["name"]) for a in stored["areas"]} if stored else set()

    def world_preview(self, values: dict[str, Any]) -> dict[str, Any] | None:
        """The world plan the areas table gives now (the stored one with the new rows for a
        project that has its world), or None without a usable table."""
        from rpggen.core import world_plan

        areas = values.get("areas")
        if not areas or self.draft is None:
            return None
        size = tuple(values.get("size", (40, 30)))
        try:
            if self.world_names() and self.state is not None and self.state.target is not None:
                return world_plan.for_project(
                    self.state.target, areas, self.draft.seed, self.catalog, size
                )[0]
            return world_plan.plan(
                areas, self.draft.seed, self.catalog, (int(size[0]), int(size[1]))
            )
        except world_plan.WorldPlanError:
            return None

    def preview_options(self, values: dict[str, Any]) -> dict[str, Any] | None:
        """The options the starter map preview draws, or None when there is nothing to draw."""
        if self.starter_locked or self.draft is None or self.catalog is None:
            return None
        if self.imported_starter() or self.is_side:
            return None
        return {**self.starter_defaults(), **values}

    # ------------------------------------------------------------------ imported maps

    def imported_maps(self) -> list[dict[str, Any]]:
        catalog = self.catalog
        return list(catalog.maps) if catalog is not None else []

    def imported_map_ids(self) -> list[str]:
        """The ids of the maps the catalog read from the packs."""
        return [m["id"] for m in self.imported_maps()]

    def imported_rows(self) -> list[tuple[str, str, str]]:
        """(label, id, source) of each imported map."""
        return [(options.imported_map_label(m), m["id"], m["source"]) for m in self.imported_maps()]

    def has_intgrid(self) -> bool:
        return bool(options.intgrid_rows(self.imported_maps()))

    def chosen_imported(self) -> dict[str, Any] | None:
        """The draft's selection made to fit the catalog's maps; None without maps."""
        known = self.imported_map_ids()
        if not known or self.draft is None:
            return None  # no catalog: the selection of the config stays as it is
        chosen = options.normalize_imported_maps(self.draft.imported_maps, known)
        self.draft.imported_maps = chosen
        return chosen

    def normalize_imported(self, include: list[str], starter: str) -> dict[str, Any]:
        return options.normalize_imported_maps(
            {"include": include, "starter": starter}, self.imported_map_ids()
        )

    def solid_rows(self) -> list[dict[str, Any]]:
        return options.intgrid_rows(self.imported_maps())

    def set_solid(self, choices: dict[tuple[str, str, int], bool]) -> int:
        catalog = self.catalog
        return options.set_solid(catalog.maps, choices) if catalog is not None else 0

    # ------------------------------------------------------------------ input map

    def input_rows(self) -> list[tuple[str, list[str]]]:
        """Each action with the text of its binding cells."""
        return [
            (action, [options.format_list(b.get(f, [])) for f, _kind in options.BINDING_FIELDS])
            for action, b in self.input_map.items()
        ]

    def read_input(self, rows: list[tuple[str, list[str]]]) -> dict[str, dict[str, Any]]:
        """The bindings of the table; the cells that are not lists of numbers go to
        ``input_errors``."""
        self.input_errors = []
        result: dict[str, dict[str, Any]] = {}
        for action, cells in rows:
            bindings = copy.deepcopy(self.input_map.get(action, {}))
            for col, ((field, _kind), text) in enumerate(
                zip(options.BINDING_FIELDS, cells, strict=False), start=1
            ):
                try:
                    bindings = options.apply_binding_text(bindings, field, text)
                except ValueError:
                    self.input_errors.append(
                        self.tr("{0}: {1} must be whole numbers separated by commas.").format(
                            action, self.tr(INPUT_COLUMNS[col])
                        )
                    )
            result[action] = bindings
        return result

    # ------------------------------------------------------------------ collecting

    def collect(self, values: OptionValues) -> None:
        if self.draft is None:
            return
        self.draft.features = options.effective_features(values.features)
        self.draft.resolution = values.resolution
        self.draft.window_size = values.window_size
        if self.is_side:
            self.draft.features["navigation"] = False  # rooms have no pathfinding
        else:
            self.draft.map_layers = values.layers
        self.draft.seed = values.seed
        self.store_starter(values.starter)
        if values.imported is not None:
            self.draft.imported_maps = values.imported
        collected = self.read_input(values.input_rows)
        if not self.input_errors:
            self.draft.input = collected

    def validate(self) -> list[str]:
        if self.draft is None:
            return []
        layer_problems = [
            self.tr(LAYER_MESSAGES[m]) for m in options.layer_issues(self.draft.map_layers)
        ]
        if self.is_side:
            layer_problems = []  # the layers of a room are fixed
            if why := self.world_error():
                return [self.tr("Starter world: {0}.").format(why), *self.input_errors]
        return [*layer_problems, *self.input_errors, *options.config_errors(self.draft)]

    # ------------------------------------------------------------------ summary

    def summary(
        self, wanted: dict[str, bool], resolution: tuple[int, int]
    ) -> tuple[options.Summary, float | None, int | None]:
        """The summary card: what will be built, the time estimate and the project size."""
        assert self.draft is not None
        summary = options.summarize(
            self.draft.archetype,
            wanted,
            self.draft.starter_map_options(),
            self.draft.base_tile_size,
            resolution,
            self.draft.imported_maps,
        )
        settings = app_settings.get()
        assets = len(self.catalog.assets) if self.catalog else 0
        seconds = options.estimate_generation_seconds(
            settings.phase_timings, settings.timing_assets, assets
        )
        pack_bytes = self.pack_size()
        return summary, seconds, options.estimate_project_bytes(pack_bytes) if pack_bytes else None

    def pack_size(self) -> int:
        """The bytes of the packs (an archive counts as its unpacked size when it is a zip),
        read once per set of packs."""
        sources = tuple(str(p) for p in (self.state.pack_sources if self.state else []))
        if sources != self._pack_bytes_key:
            self._pack_bytes_key = sources
            self._pack_bytes = sum(preflight.pack_stats(Path(s))[2] or 0 for s in sources)
        return self._pack_bytes

    # ------------------------------------------------------------------ presets

    @staticmethod
    def preset_names() -> list[str]:
        """The user's presets (the built-in ones are ``builtin_items``)."""
        return sorted(app_settings.get().option_presets)

    def builtin_items(self) -> list[tuple[str, str]]:
        """``(label, combo data)`` of the built-in presets, in their order."""
        return [
            (self.tr(label), BUILTIN_PREFIX + key)
            for key, (label, _on) in options.BUILTIN_PRESETS.items()
        ]

    def user_items(self) -> list[tuple[str, str]]:
        """``(label, name)`` of the user's presets; one that has a built-in's name (a settings
        file from 1.0 may) is kept and marked as the user's."""
        taken = {label for label, _data in self.builtin_items()} | set(options.builtin_labels())
        return [
            (self.tr("{0} (yours)").format(name) if name in taken else name, name)
            for name in self.preset_names()
        ]

    def apply_preset(self, name: str) -> bool:
        """Applies a preset to the draft: a built-in one (``BUILTIN_PREFIX`` and its key;
        ``DEFAULTS_ITEM`` is "Everything") or a saved one by its name. False when there is no
        such preset. Raises ``ValueError`` when it does not fit."""
        if self.draft is None:
            return False
        preset = (
            options.builtin_preset(name.removeprefix(BUILTIN_PREFIX), self.draft.archetype)
            if name.startswith(BUILTIN_PREFIX)
            else app_settings.get().option_presets.get(name)
        )
        if preset is None:
            return False
        new = options.apply_preset(self.draft, preset)
        self.draft = dataclasses.replace(new, seed=self.draft.seed)  # a preset keeps the seed
        if self.starter_locked:  # the starter map is the user's: only the other options change
            self.draft.starter_map = {}
        return True

    def save_preset(self, name: str) -> bool:
        """Saves the draft as a user preset. A built-in's label is not a name of your own (pick
        the built-in instead); from a built-in, any other name makes your copy of it."""
        reserved = {self.tr("Defaults"), "Defaults", *options.builtin_labels()}
        reserved |= {label for label, _data in self.builtin_items()}
        if self.draft is None or not name or name in reserved or name.startswith(BUILTIN_PREFIX):
            return False
        preset = options.to_preset(self.draft)
        app_settings.store().update(lambda settings: settings.option_presets.update({name: preset}))
        return True

    @staticmethod
    def edit_presets(renames: dict[str, str], deleted: list[str]) -> None:
        def apply(settings: app_settings.AppSettings) -> None:
            for old, new in renames.items():
                if old in settings.option_presets and not new.startswith(BUILTIN_PREFIX):
                    settings.option_presets[new] = settings.option_presets.pop(old)
            for name in deleted:
                settings.option_presets.pop(name, None)

        app_settings.store().update(apply)
