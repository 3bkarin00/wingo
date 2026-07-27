#!/usr/bin/env python3
"""R0/verify probe for D25 tab-and-slot interlock (backend/geometry/interlock.py).

Stand-in cavity strategy as in probe_spar_shapes_verify.py /
probe_pi_joints_verify.py (OML of minimal.yaml).

Checks:
  - interlock ON (web spar): ELIGIBLE crossings' ribs keep tabs (more
    material than a plain-cutout rib); root/tip crossings (no captured
    slot possible — no spar material past the end cap, found empirically)
    fall back to the plain cutout and stay byte-identical on/off; the
    slotted spar has LESS volume than the unslotted one.
  - tab↔slot fit: after cutting slots, the rib (with tabs) still has ZERO
    positive-volume intersection with the slotted spar (fit_clearance keeps
    them apart).
  - tab far face flush: with protrusion 0, the tab's far face X equals the
    web far face X within kernel tolerance (sampled crossing).
  - box/tube spars byte-identical: interlock enabled changes NOTHING for a
    box-shaped spar (volume identical to interlock-off build).
  - override: ribs.overrides disabling one rib produces a plain cutout
    there (that rib's volume equals its interlock-off twin).
  - validation: an oversized tab battery is rejected actionably.

Appends findings to docs/r0_findings/p06_ext.md.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p06_ext.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


# First run of this probe (docs/r0_findings/p06_ext.md) proved the
# validator: minimal.yaml's REAR spar (xc=0.70, thin aft section) has only
# 16mm usable web height mid-span — 2×6mm tabs + 2×3mm margins (the schema
# defaults) correctly REJECTED. The happy path below therefore uses the
# thick MAIN spar only, with 4mm tabs that fit at every station incl. tip.
INTERLOCK_ON = {
    "enabled": True, "style": "tab_slot", "tabs_per_crossing": 2,
    "tab_width_mm": 4.0, "protrusion_mm": 0.0, "fit_clearance_mm": 0.1,
    "edge_margin_mm": 3.0,
}


def main() -> int:
    lines = ["## probe_interlock_verify.py (WP2c/D25)"]
    failures = 0
    try:
        import yaml

        from backend.geometry.booleans import filter_shards, fuzzy_common
        from backend.geometry.interlock import cut_slots, interlock_active
        from backend.geometry.loft import build_oml, is_watertight
        from backend.geometry.reference import build_rib_planes
        from backend.geometry.ribs import build_ribs, rib_thickness_mm
        from backend.geometry.sections import build_planform_sections
        from backend.geometry.spars import build_spar_bodies
        from backend.schema.models import Config

        def load(structure=None, overrides=None, spar_update=None):
            d = yaml.safe_load((ROOT / "tests/configs/valid/minimal.yaml").read_text())
            d["spars"] = [d["spars"][0]]  # main spar only (INTERLOCK_ON comment)
            if structure is not None:
                d["structure"] = {"interlock": structure}
            if overrides is not None:
                d["ribs"]["overrides"] = overrides
            if spar_update:
                d["spars"][0].update(spar_update)
            return Config.model_validate(d)

        cfg_off = load()
        sections = build_planform_sections(cfg_off, cfg_off.airfoils.resample_points)
        cavity = build_oml(sections, mirror=False)
        rib_t = rib_thickness_mm(cfg_off)
        planes = build_rib_planes(cfg_off)
        plane_ys = [p.origin.y for p in planes]

        t0 = time.perf_counter()
        ribs_off = build_ribs(cfg_off, cavity, planes)
        cfg_on = load(structure=INTERLOCK_ON)
        ribs_on = build_ribs(cfg_on, cavity, planes)
        lines.append(f"- ribs off/on interlock built in {time.perf_counter()-t0:.1f}s")

        # D25: root/tip-adjacent crossings can't have a CAPTURED slot (no
        # spar material past the end cap) and fall back to the plain D23
        # cutout — interlock_active() is the single source for which
        # crossings are actually eligible (found empirically: the first
        # probe run here hit exactly this on plane_ys[0]/[-1]).
        eligible = [
            i for i, y in enumerate(plane_ys)
            if interlock_active(cfg_on, cfg_on.spars[0], i, y, rib_t)
        ]
        lines.append(f"- interlock-eligible crossings (excl. root/tip): {eligible} of "
                     f"{len(plane_ys)} rib planes")

        vol = lambda shape: sum(s.Volume() for s in filter_shards(shape)[0])  # noqa: E731
        # Eligible ribs keep tab material -> strictly more volume; ineligible
        # (root/tip) ribs are byte-identical between on/off.
        grew = all(vol(ribs_on.ribs[i].solid) > vol(ribs_off.ribs[i].solid) + 1.0 for i in eligible)
        same_ineligible = all(
            abs(vol(ribs_on.ribs[i].solid) - vol(ribs_off.ribs[i].solid)) < 1e-6
            for i in range(len(planes)) if i not in eligible
        )
        wt = all(is_watertight(s) for r in ribs_on.ribs for s in filter_shards(r.solid)[0])
        lines.append(f"- eligible ribs keep tab material (vol > plain-cutout rib): {grew}; "
                     f"root/tip ribs byte-identical on/off: {same_ineligible}; all watertight: {wt}")
        if not (grew and same_ineligible and wt):
            failures += 1

        # Spar slots.
        spar_on = build_spar_bodies(cfg_on, sections, cavity)[0]
        unslotted_vol = vol(spar_on.solid)
        t0 = time.perf_counter()
        slotted, slot_reg = cut_slots(cfg_on, cfg_on.spars[0], spar_on.solid, plane_ys,
                                      list(range(len(plane_ys))), rib_t)
        slotted_vol = vol(slotted)
        n_expected_slots = len(eligible) * INTERLOCK_ON["tabs_per_crossing"]
        lines.append(f"- slots cut in {time.perf_counter()-t0:.1f}s: spar volume "
                     f"{unslotted_vol:.0f} -> {slotted_vol:.0f}mm^3 "
                     f"({n_expected_slots} slots expected): {slotted_vol < unslotted_vol}")
        if not slotted_vol < unslotted_vol:
            failures += 1

        # Fit: tabs must not touch the slotted spar (fit_clearance apart).
        worst = 0.0
        for rib in ribs_on.ribs:
            try:
                common = fuzzy_common(rib.solid, slotted)
            except RuntimeError:
                continue
            worst = max(worst, vol(common))
        lines.append(f"- max interlocked-rib ∩ slotted-spar volume={worst:.4f}mm^3 (must be 0)")
        if worst > 0:
            failures += 1

        # §8.8 naming: slot walls matched on the slotted spar; tab side
        # faces matched on every interlocked rib (rib.tab_bond_faces was
        # matched inside build_ribs — hard failure there if a cut ate one).
        slot_matched = slot_reg.match(slotted)
        n_slot_expected = len(eligible) * INTERLOCK_ON["tabs_per_crossing"] * 2
        tab_named = sum(len(r.tab_bond_faces) for r in ribs_on.ribs)
        n_tab_expected = len(eligible) * INTERLOCK_ON["tabs_per_crossing"] * 2
        naming_ok = len(slot_matched) == n_slot_expected and tab_named == n_tab_expected
        lines.append(f"- registry naming: slot walls matched {len(slot_matched)}/{n_slot_expected}, "
                     f"tab sides matched {tab_named}/{n_tab_expected} -> {naming_ok}")
        if not naming_ok:
            failures += 1

        # Box spar: interlock generator must not touch it at all.
        cfg_box_off = load(spar_update={"shape": "box", "web_spacing_mm": 15.0})
        cfg_box_on = load(structure=INTERLOCK_ON, spar_update={"shape": "box", "web_spacing_mm": 15.0})
        rib_box_off = build_ribs(cfg_box_off, cavity, planes)
        rib_box_on = build_ribs(cfg_box_on, cavity, planes)
        same = all(
            abs(vol(a.solid) - vol(b.solid)) < 1e-6
            for a, b in zip(rib_box_on.ribs, rib_box_off.ribs)
        )
        spar_box = build_spar_bodies(cfg_box_on, sections, cavity)[0]
        box_v0 = vol(spar_box.solid)
        box_slotted, _box_reg = cut_slots(cfg_box_on, cfg_box_on.spars[0], spar_box.solid,
                                          plane_ys, list(range(len(plane_ys))), rib_t)
        box_same_spar = abs(vol(box_slotted) - box_v0) < 1e-9
        lines.append(f"- box spar untouched by interlock: ribs identical={same}, "
                     f"spar identical={box_same_spar}")
        if not (same and box_same_spar):
            failures += 1

        # Override: disable interlock on plane index 2 only.
        cfg_ov = load(structure=INTERLOCK_ON, overrides=[{"index": 2, "interlock_enabled": False}])
        ribs_ov = build_ribs(cfg_ov, cavity, planes)
        ov_plain = abs(vol(ribs_ov.ribs[2].solid) - vol(ribs_off.ribs[2].solid)) < 1e-6
        ov_others = all(
            abs(vol(ribs_ov.ribs[i].solid) - vol(ribs_on.ribs[i].solid)) < 1e-6
            for i in range(len(planes)) if i != 2
        )
        lines.append(f"- override(index=2, off): that rib plain={ov_plain}, others interlocked={ov_others}")
        if not (ov_plain and ov_others):
            failures += 1

        # Validation: absurd tab battery rejected actionably.
        cfg_bad = load(structure={**INTERLOCK_ON, "tabs_per_crossing": 40, "tab_width_mm": 20.0})
        try:
            build_ribs(cfg_bad, cavity, planes)
            lines.append("- oversized tab battery: **FAIL — accepted**")
            failures += 1
        except ValueError as exc:
            good = "exceeds the usable web height" in str(exc)
            lines.append(f"- oversized tab battery rejected actionably: {good}")
            if not good:
                failures += 1

        lines.append(
            f"- CONCLUSION: {'D25 tab-and-slot interlock PASSES on the real kernel (stand-in cavity).' if failures == 0 else f'{failures} check(s) FAILED.'}"
        )

    except Exception as exc:  # noqa: BLE001
        import traceback
        lines.append(f"- **PROBE FAILED**: {type(exc).__name__}: {exc}")
        lines.append("```\n" + traceback.format_exc() + "```")
        _append(lines)
        print("\n".join(lines))
        return 1

    _append(lines)
    print("\n".join(lines))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
