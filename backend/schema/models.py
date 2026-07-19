"""Pydantic v2 models mirroring the input schema in plan.md §6.

Field-level constraints (ranges, literals) live directly on the models.
Cross-field business rules that need a `ConfigErrorCode` live in
`validators.py` and are invoked from `Config.model_validator` below — kept
separate so the rule set (which changes phase by phase, see plan.md §6 vs
the P0 scoping note in changelog.md) doesn't bloat the field definitions.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.schema import validators as v


class Segment(BaseModel):
    name: str
    y_end_frac: float = Field(gt=0, le=1)
    dihedral_deg: float = 0.0
    sweep_le_deg: float = 0.0


class Station(BaseModel):
    y_frac: float = Field(ge=0, le=1)
    chord_mm: float = Field(gt=0)
    twist_deg: float = 0.0
    airfoil: str


class Planform(BaseModel):
    span_mm: float = Field(gt=0)
    segments: list[Segment] = Field(min_length=1)
    stations: list[Station] = Field(min_length=2)
    twist_axis_xc: float = Field(ge=0, le=1)
    mirror: bool = True


class Airfoils(BaseModel):
    sources: list[Literal["naca4", "naca5", "uiuc", "dat_upload"]] = Field(
        default_factory=lambda: ["naca4", "naca5", "uiuc", "dat_upload"]
    )
    resample_points: int = Field(gt=0)
    te_min_thickness_mm: float = Field(gt=0)

    @model_validator(mode="after")
    def _odd_resample_points(self) -> "Airfoils":
        if self.resample_points % 2 == 0:
            raise ValueError("resample_points must be odd (conventions.md §airfoils)")
        return self


class FaceSheet(BaseModel):
    material: str
    plies: int = Field(gt=0)


class Core(BaseModel):
    material: str
    thickness_mm: float = Field(gt=0)


class Skin(BaseModel):
    face_sheet: FaceSheet
    core: Core
    ramp_ratio: float = Field(gt=0)


class Tongue(BaseModel):
    cross_section: Literal["rect_hollow", "circular_tube"]
    engagement_mm: float = Field(gt=0)
    clearance_mm: float = Field(ge=0)
    wall_mm: float = Field(gt=0)


class SparWeb(BaseModel):
    material: str
    plies: int = Field(gt=0)


class Spar(BaseModel):
    name: str
    xc_root: float = Field(ge=0, le=1)
    xc_tip: float = Field(ge=0, le=1)
    web: SparWeb
    tongue: Tongue
    # D23 spar shape variants (plan.md §8.7 step 7a). `web` is the original
    # plain thickened-surface behavior — the default keeps every pre-D23
    # config byte-identical.
    shape: Literal["web", "c_channel", "i_beam", "box", "tube"] = "web"
    # c_channel / i_beam only:
    cap_width_mm: float | None = Field(default=None, gt=0)
    cap_thickness_mm: float | None = Field(default=None, gt=0)
    inside_iml: bool = False  # cap skin-side face stood off the inner face sheet by the bond gap
    # box only:
    web_spacing_mm: float | None = Field(default=None, gt=0)
    # tube only:
    od_root_mm: float | None = Field(default=None, gt=0)
    od_tip_mm: float | None = Field(default=None, gt=0)
    wall_mm: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _shape_fields_present(self) -> "Spar":
        if self.shape in ("c_channel", "i_beam"):
            if self.cap_width_mm is None or self.cap_thickness_mm is None:
                raise ValueError(
                    f"spar '{self.name}': shape={self.shape} requires cap_width_mm and cap_thickness_mm (D23)"
                )
        if self.shape == "box" and self.web_spacing_mm is None:
            raise ValueError(f"spar '{self.name}': shape=box requires web_spacing_mm (D23)")
        if self.shape == "tube":
            if self.od_root_mm is None or self.od_tip_mm is None or self.wall_mm is None:
                raise ValueError(
                    f"spar '{self.name}': shape=tube requires od_root_mm, od_tip_mm and wall_mm (D23)"
                )
            min_od = min(self.od_root_mm, self.od_tip_mm)
            if 2 * self.wall_mm >= min_od:
                raise ValueError(
                    f"spar '{self.name}': tube wall_mm={self.wall_mm} leaves no bore "
                    f"(2*wall >= min od {min_od})"
                )
        return self


class RibConstruction(BaseModel):
    material: str
    plies: int = Field(gt=0)


class LighteningHoles(BaseModel):
    enabled: bool = True
    margin_mm: float = Field(gt=0)


class RibOverride(BaseModel):
    """Per-rib override (plan.md §6, D25) — `index` is the rib PLANE's
    position in spanwise order (reference.build_rib_planes output), which
    is stable even when a plane yields no rib at a device edge."""

    index: int = Field(ge=0)
    interlock_enabled: bool = True


class Ribs(BaseModel):
    count: int = Field(gt=0)
    construction: RibConstruction
    lightening_holes: LighteningHoles
    overrides: list[RibOverride] = Field(default_factory=list)


class Interlock(BaseModel):
    """D25 tab-and-slot rib×spar interlock — web-bearing spar shapes only
    (web/c_channel/i_beam); box/tube crossings keep the plain D23 cutout.
    Default disabled: a config without a `structure:` block must produce
    pre-D25 geometry unchanged."""

    enabled: bool = False
    style: Literal["tab_slot"] = "tab_slot"
    tabs_per_crossing: int = Field(default=2, gt=0)
    tab_width_mm: float = Field(default=6.0, gt=0)
    protrusion_mm: float = Field(default=0.0, ge=0)  # 0 = flush with far web face; >0 = proud
    fit_clearance_mm: float = Field(default=0.1, gt=0)
    edge_margin_mm: float = Field(default=3.0, gt=0)


class Structure(BaseModel):
    interlock: Interlock = Field(default_factory=Interlock)


class Hinges(BaseModel):
    mode: Literal["generated", "cots"] = "generated"
    count: int = Field(gt=0)
    cots_pin_dia_mm: float | None = Field(default=None, gt=0)


class DeviceWindow(BaseModel):
    enabled: bool = True
    span_start_frac: float = Field(ge=0, le=1)
    span_end_frac: float = Field(ge=0, le=1)
    hinge_xc_start: float = Field(ge=0, le=1)
    hinge_xc_end: float = Field(ge=0, le=1)
    gap_mm: float = Field(gt=0)
    max_deflection_deg: float = Field(gt=0)
    hinges: Hinges
    # Anti-unporting angular overlap (ADR-003): the nose arc is extended
    # beyond the tangent points by (max_deflection_deg + this margin) so it
    # never rotates out of the wing cove at full deflection. None -> use
    # tolerances.OVERLAP_MARGIN_DEG; per-config override for an unusual
    # deflection/geometry combination.
    overlap_margin_deg: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _span_ordered(self) -> "DeviceWindow":
        if self.span_end_frac <= self.span_start_frac:
            raise ValueError("span_end_frac must be > span_start_frac")
        return self


class FuselageBolt(BaseModel):
    y_mm: float
    x_c: float = Field(ge=0, le=1)
    dia_mm: float = Field(gt=0)


class FuselageAttachment(BaseModel):
    bolts: list[FuselageBolt] = Field(default_factory=list)


class Hardpoints(BaseModel):
    auto: list[Literal["hinge_lands", "joint_housing_zones", "fuselage_bosses"]] = (
        Field(default_factory=list)
    )
    fuselage_attachment: FuselageAttachment = Field(default_factory=FuselageAttachment)


class JointBolt(BaseModel):
    dia_mm: float = Field(gt=0)
    axis: Literal["global_z"] = "global_z"
    head: Literal["countersunk_flush"] = "countersunk_flush"


class HousingLip(BaseModel):
    mode: Literal["flat_capped", "curvature_matched"] = "flat_capped"
    flush_tol_mm: float = Field(gt=0)


class Housing(BaseModel):
    material: str
    side_wall_mm: float = Field(gt=0)
    boss_thread: str
    lip: HousingLip


class JointRetention(BaseModel):
    insertion_axis: Literal["horizontal_y"] = "horizontal_y"
    bolts_per_housing: int = Field(gt=0)
    bolt: JointBolt
    housing: Housing


class AlignmentPins(BaseModel):
    dia_mm: float = Field(gt=0)
    count_min: int = Field(gt=0)
    fit: Literal["sliding", "press"] = "sliding"


class Stock(BaseModel):
    slab_lwh_mm: tuple[float, float, float]
    auto_section: bool = True


class Molds(BaseModel):
    bodies: Literal["all"] = "all"
    flange_width_mm: float = Field(gt=0)
    alignment_pins: AlignmentPins
    stock: Stock
    parting: Literal["auto_max_width"] = "auto_max_width"


class AnsysExport(BaseModel):
    routes: list[Literal["step_midsurface", "cdb"]] = Field(min_length=1)
    target_element_size_mm: float = Field(gt=0)
    named_selections: bool = True


class Output(BaseModel):
    formats: list[
        Literal["step", "stl", "gltf", "cdb", "dxf", "pdf", "layup_csv", "layup_json"]
    ] = Field(min_length=1)


class Config(BaseModel):
    """Root config model — the whole §6 input schema."""

    planform: Planform
    airfoils: Airfoils
    skin: Skin
    spars: list[Spar] = Field(min_length=1)
    ribs: Ribs
    structure: Structure = Field(default_factory=Structure)
    te_surface: DeviceWindow | None = None
    hardpoints: Hardpoints = Field(default_factory=Hardpoints)
    joint_retention: JointRetention | None = None
    molds: Molds | None = None
    ansys_export: AnsysExport | None = None
    output: Output

    @model_validator(mode="after")
    def _p0_cross_field_rules(self) -> "Config":
        v.validate_device_windows(self)
        v.validate_hinge_vs_spar(self)
        v.validate_gaps(self)
        v.validate_sandwich_stack(self)
        return self
