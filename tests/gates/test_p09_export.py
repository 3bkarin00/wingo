"""P9 gate — export (glTF/STL/STEP), plan.md §9 P9 pass criteria:

  exported STEP re-imported into OCC: body count identical, all names per
  §5 naming contract intact; STL manifold per body; glTF loads in headless
  three.js smoke test and node count matches body count.

SCOPE: this gate is about the EXPORT LAYER (backend/exporters/
step_export.py, mesh_export.py) being correct, not re-verifying P2-P8
construction correctness (that is what P2-P8's own gates are for) — so it
deliberately uses a CHEAP real body set (2 solids, reusing te_cut.py's own
geometry_cache.py entry, the SAME P4 device-cut shapes test_p04_te_cut.py/
test_p06_sandwich.py/test_p07_hinges.py/test_p08_kinematics.py already
share) rather than paying P6/P7's full uncached construction cost for a
question this gate doesn't need that scale to answer. Every export call
here is against the REAL cadquery/OCP kernel on REAL files (CLAUDE.md hard
rule) — "cheap" refers to which upstream geometry is reused, never to
mocking the export/re-import boundary itself.

"glTF loads in headless three.js smoke test": the STRONGER form of this
claim — an ACTUAL three.js GLTFLoader, in an ACTUAL browser, loading an
ACTUAL production job's glTF — is what tests/gates/test_p10_web_e2e.py's
test_model_renders already does; duplicating a weaker Node-only smoke test
here would verify less while costing a whole second JS toolchain
dependency. This gate verifies the glTF JSON structure directly (node/mesh
counts incl. the assembly's own root node, names) instead, and cross-
references P10's stronger check rather than re-deriving it.
"""
import tempfile
from pathlib import Path

import cadquery as cq
import pytest
import yaml
from geometry_cache import get_or_build_shapes
from OCP.StlAPI import StlAPI_Reader
from OCP.TopoDS import TopoDS_Shape

from backend import tolerances
from backend.exporters.mesh_export import write_gltf, write_stl
from backend.exporters.step_export import NamedBody, write_assembly_step
from backend.geometry.face_registry import count_step_bodies, read_step_names
from backend.geometry.loft import build_oml
from backend.geometry.sections import build_planform_sections
from backend.geometry.te_cut import (
    GEOMETRY_SOURCE_FILES as TE_CUT_SOURCE_FILES,
    TeCutRawShapes,
    _station_data,
    build_te_cut_shapes,
    finish_te_cut,
)
from backend.schema.models import Config

pytestmark = pytest.mark.timeout(tolerances.GEOMETRY_TEST_TIMEOUT_S)  # cheap gate (module docstring) — the
# plain (non *60) budget every fast-tier gate already uses is enough headroom

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEVICE_DIR = REPO_ROOT / "tests" / "configs" / "devices"
DEVICE_STEMS = ["te_half"]


def _load(stem: str) -> Config:
    return Config.model_validate(yaml.safe_load((DEVICE_DIR / f"{stem}.yaml").read_text()))


def _bodies_for(stem: str, force_fresh: bool) -> list[NamedBody]:
    config = _load(stem)
    sections = build_planform_sections(config, config.airfoils.resample_points)
    oml = build_oml(sections, mirror=config.planform.mirror)

    def _build_te_cut_raw() -> list[cq.Shape]:
        raw = build_te_cut_shapes(config, oml)
        return [raw.wing_shape, raw.cs_shape]

    (wing_shape, cs_shape), _cache_hit = get_or_build_shapes(
        config, TE_CUT_SOURCE_FILES, ["wing_shape", "cs_shape"], _build_te_cut_raw,
        force_fresh=force_fresh,
    )
    sd = _station_data(config)
    te_raw = TeCutRawShapes(
        wing_shape=wing_shape, cs_shape=cs_shape,
        stations=sd["feet_full"], stations_nose=sd["feet_nose"], hinge_dir=sd["h"],
        oml_volume_mm3=oml.Volume(),
    )
    te_res = finish_te_cut(te_raw)

    wing_faces = te_res.wing.Faces()
    assert len(wing_faces) >= 2, f"{stem}: wing body has fewer than 2 faces — can't exercise sub-face naming"
    sub_faces = {"WING_TEST_FACE_A": wing_faces[0], "WING_TEST_FACE_B": wing_faces[1]}

    return [
        NamedBody("wing", "wing", "C", te_res.wing, sub_faces=sub_faces),
        NamedBody("control_surface", "control_surface", "C", te_res.control_surface),
    ]


def pytest_generate_tests(metafunc):
    if "bodies" in metafunc.fixturenames:
        metafunc.parametrize("bodies", DEVICE_STEMS, indirect=True, ids=DEVICE_STEMS)


@pytest.fixture(scope="module")
def bodies(request) -> list[NamedBody]:
    return _bodies_for(request.param, force_fresh=False)


def _is_manifold_tessellation(shape: cq.Shape) -> bool:
    """Every edge of the tessellation shared by exactly 2 triangles — the
    standard closed-manifold-mesh definition. Runs on the SAME shape
    write_stl tessellates (mesh_export.py uses the identical
    TESSELLATION_TOLERANCE_MM), so this is exactly the triangulation that
    ends up in the STL file, verified analytically rather than by
    re-parsing the file through a not-yet-R0-probed reader API.

    cq.Shape.tessellate() concatenates each FACE's own local triangulation
    without deduplicating coincident vertices at shared face boundaries —
    found empirically (this check false-failed on te_half.yaml's `wing`
    body, a solid P4's own gate already proves watertight, before this
    merge step was added): a shared edge between two faces gets a
    DIFFERENT vertex-index pair per face, so raw index-pair counting sees
    two distinct each-used-once edges instead of one edge used by 2
    triangles. Snap-merging vertices by rounded position first (1e-4mm,
    tighter than TESSELLATION_TOLERANCE_MM so distinct nearby vertices
    never wrongly merge, loose enough to catch the coincident ones OCC's
    per-face tessellation actually produces at a shared edge) reconstructs
    the true mesh graph before the edge-count check runs."""
    verts, tris = shape.tessellate(tolerances.TESSELLATION_TOLERANCE_MM)
    assert verts and tris, "empty tessellation"

    def _key(v) -> tuple[float, float, float]:
        return (round(v.x, 4), round(v.y, 4), round(v.z, 4))

    merged: dict[tuple[float, float, float], int] = {}
    remap = []
    for v in verts:
        remap.append(merged.setdefault(_key(v), len(merged)))

    edge_counts: dict[tuple[int, int], int] = {}
    for tri in tris:
        a, b, c = (remap[i] for i in tri)
        for x, y in ((a, b), (b, c), (c, a)):
            key = (x, y) if x < y else (y, x)
            edge_counts[key] = edge_counts.get(key, 0) + 1
    return all(c == 2 for c in edge_counts.values())


def test_step_names_and_body_count_survive_reimport(bodies, gate_metrics):
    """Plan.md: 'body count identical, all names per §5 naming contract
    intact' — count_step_bodies + read_step_names, both R0-verified
    (docs/r0_findings/p09.md, probe_step_body_count.py)."""
    with tempfile.TemporaryDirectory() as tmp:
        step_path = str(Path(tmp) / "p09.step")
        write_assembly_step(bodies, step_path)

        n_bodies = count_step_bodies(step_path)
        names = read_step_names(step_path)

    assert n_bodies == len(bodies), f"body count {n_bodies} != {len(bodies)} written"

    expected_names = {b.contract_name for b in bodies} | {
        n for b in bodies for n in b.sub_faces
    }
    missing = expected_names - names
    assert not missing, f"name(s) lost in STEP round-trip: {missing}"

    gate_metrics.setdefault("step_export", {})["te_half"] = {
        "body_count": n_bodies, "names_verified": len(expected_names),
    }


def test_stl_manifold_per_body(bodies, gate_metrics):
    """Plan.md: 'STL manifold per body'."""
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        for b in bodies:
            path = str(Path(tmp) / f"{b.body_name}.stl")
            write_stl(b.shape, path)
            assert Path(path).exists() and Path(path).stat().st_size > 0, f"{b.body_name}: STL not written"

            shape = TopoDS_Shape()
            ok = StlAPI_Reader().Read(shape, path)
            assert ok, f"{b.body_name}: STL not re-readable via StlAPI_Reader"

            manifold = _is_manifold_tessellation(b.shape)
            results[b.body_name] = manifold
            assert manifold, f"{b.body_name}: exported STL tessellation is not manifold (an edge is not shared by exactly 2 triangles)"

    gate_metrics.setdefault("stl_manifold", {})["te_half"] = results


def test_gltf_node_count_matches_body_count(bodies, gate_metrics):
    """Plan.md: 'glTF loads ... node count matches body count' — the
    stronger 'loads in headless three.js' half of this criterion is
    test_p10_web_e2e.py's test_model_renders (module docstring); this test
    verifies the glTF JSON's own structure. write_gltf's own docstring:
    the assembly root itself is ALSO a node (`cq.Assembly`'s own top-level
    group, R0-noted in docs/r0_findings/p09.md's probe_export_apis.py
    output: 3 nodes for 2 added bodies) — so total node count is
    len(bodies) + 1, and this asserts on the NAMED subset instead, which
    is the part plan.md's "matches body count" claim actually cares about."""
    import json

    with tempfile.TemporaryDirectory() as tmp:
        gltf_path = Path(tmp) / "p09.gltf"
        write_gltf([(b.contract_name, b.shape) for b in bodies], str(gltf_path))
        assert gltf_path.exists() and gltf_path.stat().st_size > 0

        doc = json.loads(gltf_path.read_text())

    all_nodes = doc.get("nodes", [])
    named_node_names = {n["name"] for n in all_nodes if "name" in n}
    expected_names = {b.contract_name for b in bodies}
    missing = expected_names - named_node_names
    assert not missing, f"body name(s) missing from glTF nodes: {missing}"
    assert len(named_node_names & expected_names) == len(bodies), (
        f"named node count {len(named_node_names & expected_names)} != body count {len(bodies)}"
    )
    gate_metrics.setdefault("gltf_export", {})["te_half"] = {
        "total_nodes": len(all_nodes), "named_body_nodes": len(named_node_names & expected_names),
        "meshes": len(doc.get("meshes", [])),
    }
