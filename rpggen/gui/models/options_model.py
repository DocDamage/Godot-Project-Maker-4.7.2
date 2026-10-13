"""What the Options page decides, without its widgets: the draft config, feature dependencies,
the starter and imported maps, the input table, presets, the summary and validation. The pure
rules are in ``rpggen.core.options``; this class keeps the page's state around them."""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpggen import features
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
EXISTING_STAGES_TEXT = (
    "This project has its stages: the ones that exist are kept as they are. "
    "You can still add a stage below; it comes after the last."
)
EXISTING_TRACKS_TEXT = (
    "This project has its tracks: the ones that exist are kept as they are. "
    "You can still add a track below; it comes after the last."
)
EXISTING_FARM_TEXT = (
    "This project has its farm: the field, the plot and the buildings are kept as they are. "
    "The days, fishing and what passing out costs can still change, and you can add a map below."
)
# a farm's options that are read on every generation (the rest is fixed once the farm exists)
FARM_LIVE = ("days_per_season", "day_length", "fishing", "pass_out_loss", "added_maps")
VIEW_FIXED_TEXT = "the view of a generated project cannot be changed"
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


@dataclass(frozen=True)
class ViewState:
    """The *View* choice of a kind that can be isometric (T17.16)."""

    shown: bool  # the kind has the view and the wizard offers it
    projection: str = config_mod.PROJECTION_TOP_DOWN
    controls: str = config_mod.ISO_CONTROLS_SCREEN
    can_choose: bool = False  # False: the packs have no isometric ground, or the project exists
    reason: str = ""  # why not, for the tooltip and the line under the choice


def view_offered(archetype: str) -> bool:
    """True when the wizard offers the isometric view for this kind of game (its flag)."""
    return features.ISOMETRIC_AVAILABLE and archetype in config_mod.ISOMETRIC_KINDS


def project_exists(state: WizardState | None) -> bool:
    """True when the state's target is a project rpggen has generated: one that was opened
    to be generated again, or one this session has just made."""
    if state is None:
        return False
    return state.regenerating or (
        state.target is not None and preflight.is_rpggen_project(state.target)
    )


def apply_default_view(state: WizardState) -> None:
    """The view of a new project is the one its packs are drawn for (``options.
    default_projection``) until somebody chooses on the Options page; a kind without the
    isometric view is seen as it always was. A project that exists keeps its view, and with
    the flag off nothing is decided here."""
    cfg = state.config
    if cfg is None:
        return
    if cfg.archetype not in config_mod.ISOMETRIC_KINDS:
        cfg.projection = config_mod.PROJECTION_TOP_DOWN
        cfg.iso_controls = config_mod.ISO_CONTROLS_SCREEN
        return
    if not features.ISOMETRIC_AVAILABLE or project_exists(state) or state.view_chosen:
        return
    cfg.projection = options.default_projection(state.catalog, cfg.archetype)


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
        self.farm_locked = False  # the project has its farm (a farm's own map and its plan)
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
        self.farm_locked = self.farm_exists()
        if (
            self.draft.projection == config_mod.PROJECTION_ISOMETRIC
            and view_offered(self.draft.archetype)
            and not project_exists(state)
            and options.isometric_problem(self.catalog)
        ):  # the audit took the isometric ground away: the view goes with it
            self.draft.projection = config_mod.PROJECTION_TOP_DOWN

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
        cfg.iso_controls = self.draft.iso_controls
        if cfg.projection != self.draft.projection:
            # what was chosen on the Mapping page for the other view may not fit this one
            from rpggen.core import mapping

            cfg.projection = self.draft.projection
            if self.catalog is not None:
                cfg.starter = mapping.resolve_starter(
                    self.catalog, cfg.archetype, cfg.starter, cfg.projection
                )
        if self.is_farm or not self.starter_locked:
            # (a farm's draft already holds what a farm that exists keeps: ``store_starter``)
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

    @property
    def kind(self) -> str:
        return self.draft.archetype if self.draft is not None else ""

    def dependent_features(self, current: dict[str, bool]) -> dict[str, FeatureState]:
        """A feature whose dependencies are off is unchecked and disabled and says what it needs;
        it returns to the user's choice once they are on again."""
        out = {}
        for key in options.DEPENDENCIES:
            missing = options.missing_deps(current, key, self.kind)
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
                    True,
                    self.wishes.get(key, False),
                    self.tr(options.feature_text(key, self.kind)),
                    "",
                )
        return out

    def default_features(self) -> dict[str, bool]:
        # a farm's own defaults: the page would otherwise switch on what a farm has off
        defaults = config_mod.default_features(self.kind if self.is_farm else "turn_based")
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
    def is_arcade(self) -> bool:
        """A shoot 'em up, a run and gun or a racing game (M16): a run of stages or tracks
        instead of a starter map."""
        return self.draft is not None and self.draft.archetype in config_mod.ARCADE_KINDS

    @property
    def is_farm(self) -> bool:
        """A farm (M17): the starter map is its village, and it has a map of its own, planned
        as a whole, with a box of its own above the village's."""
        return self.draft is not None and self.draft.archetype == "farm"

    @property
    def planned(self) -> bool:
        """The kinds whose world is planned as a whole (rooms, stages, tracks): they have a
        box of their own in place of the starter map, and no imported maps."""
        return self.is_side or self.is_arcade

    @property
    def kept_key(self) -> str:
        """The one starter option that still counts once the map or the world exists: the
        table a new area, a new room, a new stage or a new track is added in."""
        if self.is_arcade:
            assert self.draft is not None
            return "added_tracks" if self.draft.archetype == "racing" else "added_stages"
        return "added_rooms" if self.is_side else "areas"

    def starter_exists(self) -> bool:
        state = self.state
        if state is None or not state.regenerating or state.target is None:
            return False
        if self.is_side:
            from rpggen.core import room_plan

            return room_plan.exists(state.target)
        if self.is_arcade:
            from rpggen.core import wave_plan

            return wave_plan.exists(state.target)
        return (state.target / "game" / "maps" / "starter_map.tscn").is_file()

    def farm_exists(self) -> bool:
        """True when the project is a farm that has its own map already."""
        from rpggen.core import farm_plan

        state = self.state
        if not self.is_farm or state is None or not state.regenerating or state.target is None:
            return False
        return farm_plan.exists(state.target)

    def frozen_keys(self) -> set[str]:
        """The options of a farm that are kept as the config has them: the village's once its
        map exists (but its areas: one can be added), and what the stored plan of the farm
        fixes once the farm exists."""
        from rpggen.core import farm_plan

        frozen: set[str] = set()
        if self.starter_locked:
            frozen |= set(config_mod.starter_map_defaults("turn_based"))
        if self.farm_locked:
            frozen |= {*farm_plan.defaults(), "starting_money"} - set(FARM_LIVE)
        return frozen

    def imported_starter(self) -> str:
        return str((self.draft.imported_maps if self.draft else {}).get("starter", ""))

    def starter_state(self) -> StarterState:
        """The layout options apply to a planned starter map: not to one that already exists and
        not to an imported one."""
        locked = self.starter_locked
        if self.planned:
            text = EXISTING_WORLD_TEXT
            if self.is_arcade:
                assert self.draft is not None
                racing = self.draft.archetype == "racing"
                text = EXISTING_TRACKS_TEXT if racing else EXISTING_STAGES_TEXT
            return StarterState(
                layout_enabled=not locked,
                imported_enabled=False,
                note=self.tr(text),
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
        if self.is_farm:
            self.draft.starter_map = self.merged_farm(self.draft.starter_map, values)
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

    def merged_farm(self, old: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
        """The ``starter_map`` of a farm from what the widgets show: only what differs from the
        defaults, with the frozen options (``frozen_keys``) as ``old`` has them."""
        defaults = self.starter_defaults()
        frozen = self.frozen_keys()
        out = {k: copy.deepcopy(v) for k, v in old.items() if k in frozen}
        for key, value in values.items():
            if key not in frozen and (key not in defaults or value != defaults[key]):
                out[key] = copy.deepcopy(value)
        return out

    def farm_state(self) -> StarterState:
        """Which options of the farm's box can change: all of them until the farm exists, then
        the ones that are read on every generation."""
        return StarterState(
            layout_enabled=not self.farm_locked,
            imported_enabled=False,
            note=self.tr(EXISTING_FARM_TEXT),
            note_visible=self.farm_locked,
        )

    def farm_preview(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """What the options of a farm plan now (``options.plan_farm``: the farm's map, how many
        crops and people), for the box's preview: the stored plan with the maps that were
        added once the project has its farm, else a fresh one from the seed and the packs.
        ``(None, why)`` when the options make no farm."""
        if self.draft is None or not self.is_farm:
            return None, ""
        state = self.state
        target = state.target if state is not None and self.farm_locked else None
        cfg = dataclasses.replace(self.draft, starter_map=copy.deepcopy(values))
        try:
            return options.plan_farm(cfg, self.catalog, target), ""
        except ValueError as error:  # FarmPlanError, PeoplePlanError
            return None, str(error)

    def farm_footprint(self) -> tuple[int, int] | None:
        """The diamond the farm's preview is drawn on: the project's when it is isometric
        (its tile set's, else its ground's), None for a farm seen from above."""
        from rpggen.core import iso_atlas

        if self.draft is None or self.draft.projection != config_mod.PROJECTION_ISOMETRIC:
            return None
        if self.catalog is None:
            return None
        found = iso_atlas.project_footprint(self.catalog, self.draft)
        return found or options.pack_footprint(self.catalog)

    def built_added_maps(self) -> int:
        """How many rows of the draft's ``added_maps`` the stored plan of the farm has."""
        from rpggen.core import farm_plan, world_plan

        state = self.state
        if self.draft is None or state is None or not self.farm_locked or state.target is None:
            return 0
        stored = farm_plan.stored_in(world_plan.load(state.target)) or {}
        have = {str(name).casefold() for name in stored.get("added_maps", [])}
        built = 0
        for row in self.draft.starter_map.get("added_maps", []):
            if str(row.get("name", "")).strip().casefold() not in have:
                break
            built += 1
        return built

    def farm_error(self) -> str:
        """Why the draft's options make no farm ("" when they do)."""
        from rpggen.core import farm_plan

        if self.draft is None or not self.is_farm:
            return ""
        try:
            farm_plan.normalized(self.draft.starter_map_options())
        except farm_plan.FarmPlanError as error:
            return str(error)
        return ""

    # ------------------------------------------------------------------ the view (T17.16)

    def view_state(self) -> ViewState:
        """The *View* choice: shown for a kind that has the isometric view while the wizard
        offers it; preselected (the draft's); fixed once the project exists; and without
        isometric ground it stays *From above*, with the reason the run would give."""
        if self.draft is None or not view_offered(self.draft.archetype):
            return ViewState(False)
        draft = self.draft
        if project_exists(self.state):
            return ViewState(
                True, draft.projection, draft.iso_controls, False, self.tr(VIEW_FIXED_TEXT)
            )
        problem = options.isometric_problem(self.catalog)
        return ViewState(True, draft.projection, draft.iso_controls, not problem, problem)

    def set_view(self, projection: str, controls: str) -> bool:
        """The view and the pad as the user chose them; False when nothing changed. A view
        that cannot be chosen is not taken (the widget is disabled then)."""
        state = self.view_state()
        if self.draft is None or not state.shown:
            return False
        if not state.can_choose or projection not in config_mod.PROJECTIONS:
            projection = self.draft.projection
        if controls not in config_mod.ISO_CONTROLS:
            controls = self.draft.iso_controls
        if (projection, controls) == (self.draft.projection, self.draft.iso_controls):
            return False
        if projection != self.draft.projection and self.state is not None:
            self.state.view_chosen = True
        self.draft.projection, self.draft.iso_controls = projection, controls
        return True

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

    def planner(self):  # noqa: ANN201 - one of the three plan modules
        """The module that plans the stages of the draft's arcade kind."""
        from rpggen.core import stage_plan, track_plan, wave_plan

        assert self.draft is not None
        return {"run_and_gun": stage_plan, "racing": track_plan}.get(
            self.draft.archetype, wave_plan
        )

    def stages_preview(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """The stages (or the tracks) the options of an arcade kind give now, for the box's
        preview: the stored plan with what was added once the project has its stages, else a
        fresh plan from the seed, the screen and the tile size. ``(None, why)`` when the
        options make no plan."""
        if self.draft is None or not self.is_arcade:
            return None, ""
        planner = self.planner()
        state = self.state
        target = state.target if state is not None and self.starter_locked else None
        facts = planner.facts_of(self.draft.resolution, self.draft.base_tile_size)
        try:
            world, _notes = planner.for_project(target, values, self.draft.seed, facts)
        except ValueError as error:  # the plan errors of the three kinds
            return None, str(error)
        return world["stages"], ""

    def built_added_stages(self) -> int:
        """How many rows of the draft's added stages (or tracks) the project already has."""
        from rpggen.core import world_plan

        state = self.state
        if self.draft is None or state is None or not self.starter_locked or state.target is None:
            return 0
        stored = world_plan.load(state.target) or {}
        have = {str(name).casefold() for name in (stored.get("stages") or {}).get("added", [])}
        built = 0
        for row in self.draft.starter_map.get(self.kept_key, []):
            if str(row.get("name", "")).strip().casefold() not in have:
                break
            built += 1
        return built

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

        if self.draft is None or not self.planned:
            return ""
        try:
            if self.is_arcade:
                self.planner().normalized(self.draft.starter_map_options())
            else:
                room_plan.normalized(self.draft.starter_map_options())
        except ValueError as error:  # RoomPlanError and the three plan errors
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
        if self.imported_starter() or self.planned:
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
        hidden = options.hidden_features(self.kind) if self.is_arcade or self.is_farm else ()
        # what the page does not show for an arcade kind or a farm stays as it was
        kept = {key: bool(self.draft.features.get(key, False)) for key in hidden}
        self.draft.features = {**options.effective_features(values.features, self.kind), **kept}
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
        if self.is_arcade and (why := self.world_error()):
            racing = self.draft.archetype == "racing"
            what = self.tr("Tracks") if racing else self.tr("Stages")
            return [self.tr("{0}: {1}.").format(what, why), *self.input_errors]
        if why := self.farm_error():
            layer_problems.append(self.tr("{0}: {1}.").format(self.tr("Farm"), why))
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
            options.farm_crop_count(self.catalog, self.draft.projection) if self.is_farm else None,
        )
        settings = app_settings.get()
        assets = len(self.catalog.assets) if self.catalog else 0
        # what the last run of this kind took, when there was one (T16.16); else the last run
        seconds = options.estimate_kind_seconds(
            settings.kind_timings, self.draft.archetype, assets
        ) or options.estimate_generation_seconds(
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
        items = [
            (self.tr(label), BUILTIN_PREFIX + key)
            for key, (label, _on) in options.BUILTIN_PRESETS.items()
        ]
        kind = self.draft.archetype if self.draft is not None else ""
        return items + [  # the presets of the chosen arcade kind (T16.16)
            (self.tr(options.builtin_label(key)), BUILTIN_PREFIX + key)
            for key in options.kind_preset_keys(kind)
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
        if name.startswith(BUILTIN_PREFIX):
            key, kind = name.removeprefix(BUILTIN_PREFIX), self.draft.archetype
            preset = options.builtin_preset(key, kind) or options.kind_preset(
                key, kind, self.draft.starter_map
            )
        else:
            preset = app_settings.get().option_presets.get(name)
        if preset is None:
            return False
        old = self.draft.starter_map
        new = options.apply_preset(self.draft, preset)
        self.draft = dataclasses.replace(new, seed=self.draft.seed)  # a preset keeps the seed
        if self.is_farm:  # what a farm that exists keeps is kept; the rest is the preset's
            self.draft.starter_map = self.merged_farm(old, new.starter_map_options())
        elif self.starter_locked:  # the starter map is the user's: only the other options change
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
