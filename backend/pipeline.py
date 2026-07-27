"""P10 production geometry pipeline (plan.md §8, §9 P10) — the single entry
point that wires every P1-P8 geometry module into one whole-wing build, for
the worker (backend/worker/runner.py) and any other caller that wants "the
real geometry for this config" without re-deriving the construction order
gate-by-gate.

Production code always builds fresh (CLAUDE.md: geometry_cache.py is
test-only performance infrastructure) — no caching here, ever.

SCOPE (honest, not a shortcut): the FULL internal build (sandwich shells,
ribs, D23-shaped spars, false spar, D24 π-joints, D25 interlock) only runs
for `not config.planform.mirror` — reference geometry (rib planes, spar
surfaces) has never been verified against a mirrored half-span (every
P6/P7 gate battery is mirror:false te_half.yaml only; scripts/
export_viewer_data.py's own dev script carries the identical restriction,
independently arrived at). A mirror:true config (every current
tests/golden/*.yaml) gets a REDUCED build instead — watertight OML solid +
spar reference surfaces + rib reference planes only — honestly flagged via
WingBuild.warnings rather than silently built wrong. Device-cut/control-
surface/false-spar/hinges additionally require `config.te_surface`
present+enabled (meaningless without a device window): a mirror:false
config with no te_surface still gets the full sandwich/rib/spar internal
build, just no control surface or hinge hardware.

Naming: every body gets `SEG-C/BODY-<name>/ROLE-<role>` (docs/
conventions.md's naming contract) — segment is always "C" because no
config in R1 (pre-P11 segmentation) has more than one panel; L/R/segment-
name bodies are P11 (3-piece wing) follow-on work, not invented here.

Solid-body sanity (watertight + no shards, F3): re-asserted here, not just
trusted from each module's own construction, because a job submitted
through the web UI can hit config edge cases the narrow te_half.yaml-only
gate batteries never sampled (P6 gate's own module docstring: modules were
ALSO independently probed against tests/configs/edge/high_taper.yaml, but
never gated on it) — same posture as export_viewer_data.py's own in-run
assertions, carried forward here rather than re-invented.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import cadquery as cq

from backend.exporters.step_export import NamedBody
from backend.geometry.booleans import filter_shards
from backend.geometry.false_spar import build_false_spar
from backend.geometry.hinges_pin_tube import build_pin_tube_hinges
from backend.geometry.iml import build_sandwich_body, build_sandwich_lofts
from backend.geometry.interlock import WEB_BEARING_SHAPES, cut_slots
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.midsurface import build_skin_midsurface
from backend.geometry.pi_joints import build_pi_preforms
from backend.geometry.reference import build_rib_planes, build_spar_surfaces
from backend.geometry.ribs import build_ribs, rib_thickness_mm
from backend.geometry.sections import build_planform_sections
from backend.geometry.spars import build_spar_bodies
from backend.geometry.te_cut import cut_te_surface
from backend.schema.models import Config

# Roles that must be a single watertight solid (post shard-filter) before
# export — everything this pipeline builds EXCEPT the pure-shell reference/
# midsurface bodies, which cq.Shape.Solids()-based checks don't apply to.
_SOLID_ROLES = {
    "oml", "skin", "rib", "spar", "false_spar", "control_surface",
    "pi_joint", "hinge_tube", "hinge_carrier",
}


@dataclass
class KinematicsInfo:
    axis_p0: list[float]
    axis_dir: list[float]
    max_deflection_deg: float
    wing_body_names: list[str]  # contract_name, static (does not move)
    cs_body_names: list[str]    # contract_name, rotates about the axis with deflection


@dataclass
class WingBuild:
    config: Config
    named_bodies: list[NamedBody] = field(default_factory=list)
    kinematics: KinematicsInfo | None = None
    warnings: list[str] = field(default_factory=list)
    timings_s: dict = field(default_factory=dict)


def _stage(on_stage: "Callable[[str], None] | None", name: str) -> None:
    if on_stage is not None:
        on_stage(name)


def _verify_solid_bodies(named_bodies: list[NamedBody]) -> None:
    """`len(kept) >= 1`, NOT `== 1` — found empirically (P10's first real
    job run): ribs and spars legitimately split into multiple DISCONNECTED
    but individually watertight solids (a rib crossing a spar footprint, a
    spar discontinued at a device window where the hinge/false-spar take
    over structurally) — this is already-accepted, gate-verified behavior
    (test_p06_sandwich.py's test_ribs_watertight_after_holes uses the same
    `len(solids) >= 1` check; spar_trim.py's own module docstring states
    the same for spars), not a construction defect. Requiring exactly one
    solid here was stricter than the modules it wraps and rejected every
    multi-piece rib/spar in a real te_half.yaml build."""
    bad = []
    for b in named_bodies:
        if b.role not in _SOLID_ROLES:
            continue
        kept, shards = filter_shards(b.shape)
        if shards or not kept or not all(is_watertight(s) for s in kept):
            bad.append(f"{b.contract_name} (solids={len(kept)}, shards={len(shards)})")
    if bad:
        raise RuntimeError(f"pipeline: {len(bad)} body(s) failed watertight/shard check: {bad}")


def build_wing(config: Config, on_stage: "Callable[[str], None] | None" = None) -> WingBuild:
    t_start = time.perf_counter()
    build = WingBuild(config=config)

    sections = build_planform_sections(config, config.airfoils.resample_points)
    _stage(on_stage, "sections")

    oml = build_oml(sections, mirror=config.planform.mirror)
    if not is_watertight(oml):
        raise RuntimeError("pipeline: OML loft not watertight — refusing to build on broken geometry")
    _stage(on_stage, "oml")

    full_internal = not config.planform.mirror
    has_device = config.te_surface is not None and config.te_surface.enabled

    if not full_internal:
        build.warnings.append(
            "mirror:true config: reduced build (OML + reference surfaces/planes only) — "
            "sandwich/rib/spar/hinge construction has never been verified for a mirrored "
            "half-span, see backend/pipeline.py module docstring"
        )
        build.named_bodies.append(NamedBody("oml", "oml", "C", oml))
        for name, shell in build_spar_surfaces(config, sections).items():
            build.named_bodies.append(NamedBody(f"spar_ref_{name}", "spar_ref", "C", shell))
        rib_planes = build_rib_planes(config)
        _verify_solid_bodies(build.named_bodies)
        build.timings_s["total_s"] = time.perf_counter() - t_start
        build.timings_s["rib_plane_count"] = len(rib_planes)
        return build

    # --- Full internal build (mirror:false) --------------------------------
    wing_body_names: list[str] = []
    cs_body_names: list[str] = []

    def _add(body: NamedBody, moves: bool = False) -> None:
        build.named_bodies.append(body)
        (cs_body_names if moves else wing_body_names).append(body.contract_name)

    if has_device:
        te_res = cut_te_surface(config, oml)
        wing_solid: cq.Shape = te_res.wing
        cs_solid: cq.Shape | None = te_res.control_surface
        _stage(on_stage, "device_cut")
    else:
        wing_solid = oml
        cs_solid = None

    lofts = build_sandwich_lofts(config, sections)
    sandwich = build_sandwich_body(wing_solid, lofts, include_hollow_interior=True)
    _stage(on_stage, "sandwich")
    for label in (
        "face_outer_upper", "face_outer_lower", "core_upper", "core_lower",
        "face_inner_upper", "face_inner_lower",
    ):
        _add(NamedBody(f"skin_{label}", "skin", "C", getattr(sandwich, label)))

    fs = build_false_spar(config, sections, lofts.hollow_iml_solid) if has_device else None

    # Hinges built here (immediately after the false spar exists, before
    # ribs/spars/π-joints — those don't depend on hinge output at all) so
    # the false-spar/control-surface bodies actually EXPORTED can be the
    # POCKETED derived bodies hinges_pin_tube.py produces, not the plain
    # pre-hinge inputs — module docstring's own "Purely ADDITIVE... the
    # pocketed/notched variants are new derived bodies on the RESULT": the
    # plain cs_solid/false_spar would genuinely collide with the installed
    # hinge hardware if shipped as-is, so it is never the right export.
    hinge_set = None
    if has_device and fs is not None and cs_solid is not None and config.te_surface.hinges.mode == "generated":
        hinge_set = build_pin_tube_hinges(config, sections, cs_solid, fs.solid)
        if hinge_set.failed:
            build.warnings.append(f"hinge construction failures: {hinge_set.failed}")
        _stage(on_stage, "hinges")

    false_spar_solid = (
        hinge_set.false_spar_pocketed
        if hinge_set is not None and hinge_set.false_spar_pocketed is not None
        else (fs.solid if fs is not None else None)
    )
    if false_spar_solid is not None:
        _add(NamedBody("false_spar", "false_spar", "C", false_spar_solid))
    _stage(on_stage, "false_spar")

    rib_planes = build_rib_planes(config)
    rib_t = rib_thickness_mm(config)
    rib_set = build_ribs(config, sandwich.hollow_interior, rib_planes)
    for rib in rib_set.ribs:
        _add(NamedBody(
            f"rib_{rib.y_mm:.0f}", "rib", "C", rib.solid, sub_faces=dict(rib.tab_bond_faces),
        ))
    _stage(on_stage, "ribs")

    spar_bodies = build_spar_bodies(config, sections, sandwich.hollow_interior)
    plane_ys = [p.origin.y for p in rib_planes]
    plane_idxs = list(range(len(rib_planes)))
    for sb in spar_bodies:
        solid = sb.solid
        sub_faces: dict = {}
        spar_cfg = next(s for s in config.spars if s.name == sb.name)
        if config.structure.interlock.enabled and spar_cfg.shape in WEB_BEARING_SHAPES:
            slotted, registry = cut_slots(config, spar_cfg, solid, plane_ys, plane_idxs, rib_t)
            solid = slotted
            sub_faces = registry.match(solid)
        _add(NamedBody(f"spar_{sb.name}", "spar", "C", solid, sub_faces=sub_faces))
    _stage(on_stage, "spars")

    pi_set = build_pi_preforms(
        config, sandwich.hollow_interior,
        [(r.y_mm, r.outline_pts) for r in rib_set.ribs if r.outline_pts is not None],
        rib_t,
    )
    for i, seg in enumerate(pi_set.segments):
        _add(NamedBody(
            f"pi_{seg.side}{i}_rib{seg.rib_y_mm:.0f}", "pi_joint", "C", seg.solid,
            sub_faces=dict(seg.bond_faces),
        ))
    _stage(on_stage, "pi_joints")

    skin_midsurface = build_skin_midsurface(config, sections)
    _add(NamedBody("skin_midsurface", "midsurface", "C", skin_midsurface))
    for name, shell in build_spar_surfaces(config, sections).items():
        _add(NamedBody(f"spar_midsurface_{name}", "midsurface", "C", shell))
    _stage(on_stage, "midsurfaces")

    if has_device and cs_solid is not None:
        cs_export_solid = (
            hinge_set.cs_pocketed
            if hinge_set is not None and hinge_set.cs_pocketed is not None
            else cs_solid
        )
        _add(NamedBody("control_surface", "control_surface", "C", cs_export_solid), moves=True)

        if hinge_set is not None:
            for st in hinge_set.stations:
                # hinges_pin_tube.build_pin_tube_hinges matches bond faces
                # against the CARRIER bodies specifically (never against
                # cs_pocketed/false_spar_pocketed) — HINGE<index>_WING_...
                # vs HINGE<index>_CS_... naming (its own module code), so
                # the sub_faces split here mirrors that exactly rather than
                # guessing at the naming convention independently.
                wing_faces = {
                    n: f for n, f in hinge_set.bond_faces.items()
                    if n.startswith(f"HINGE{st.index}_") and "WING" in n
                }
                cs_faces = {
                    n: f for n, f in hinge_set.bond_faces.items()
                    if n.startswith(f"HINGE{st.index}_") and "WING" not in n
                }
                _add(NamedBody(f"hinge_wing_tube_{st.s_center:.0f}", "hinge_tube", "C", st.wing_tube))
                _add(NamedBody(
                    f"hinge_wing_carrier_{st.s_center:.0f}", "hinge_carrier", "C", st.wing_carrier,
                    sub_faces=wing_faces,
                ))
                _add(NamedBody(f"hinge_cs_tube_{st.s_center:.0f}", "hinge_tube", "C", st.cs_tube), moves=True)
                _add(NamedBody(
                    f"hinge_cs_carrier_{st.s_center:.0f}", "hinge_carrier", "C", st.cs_carrier,
                    sub_faces=cs_faces,
                ), moves=True)

            build.kinematics = KinematicsInfo(
                axis_p0=[float(x) for x in hinge_set.axis_p0],
                axis_dir=[float(x) for x in hinge_set.axis_dir],
                max_deflection_deg=config.te_surface.max_deflection_deg,
                wing_body_names=wing_body_names,
                cs_body_names=cs_body_names,
            )

    _verify_solid_bodies(build.named_bodies)
    _stage(on_stage, "verified")

    build.timings_s["total_s"] = time.perf_counter() - t_start
    return build
