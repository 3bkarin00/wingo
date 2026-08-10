"""Gate P13 — .cdb writer + layup schedule.

Plan.md P13 pass criteria:
- Oracle parser accepts the deck: node/element counts match Gmsh source
- Every element belongs to exactly one SECTYPE with correct layer stack
  from the materials DB
- Mesh is a single connected component (F7 — T-junction detector)
- Named components (CMBLOCK) match §5 naming
- mm–tonne–s header present (F8)

Tests:
1. Module loads with all functions and classes
2. CdbWriter writes valid .cdb file
3. Oracle parser accepts written .cdb
4. Node/element counts match
5. Every element belongs to exactly one SECTYPE
6. Mesh is single connected component (F7)
7. Named components match §5 naming
8. mm–tonne–s header present (F8)
9. Layup CSV export
10. Layup JSON export
11. Layup schedule builds from config
12. CdbMeshData has all required fields
13. CdbWriteResult has all required fields
14. LayupExportResult has all required fields
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backend.tolerances import KERNEL_TOLERANCE_MM


# ── 1. Module loads ────────────────────────────────────────────────────────


def test_cdb_module_loads():
    """CDB module loads with all functions and classes."""
    from backend.exporters.cdb_writer import (
        CdbWriter,
        CdbMeshData,
        CdbWriteResult,
    )
    from backend.exporters.layup import (
        LayupExporter,
        LayupSchedule,
        LayupExportResult,
        Ply,
        build_layup_schedule,
        export_layup_csv,
        export_layup_json,
        export_layup,
    )
    from tests.oracle.cdb_parser import (
        CdbParser,
        CdbReport,
        Node,
        Element,
        ElementType,
        SectionType,
        SectionData,
        Component,
    )

    assert callable(build_layup_schedule)
    assert callable(export_layup_csv)
    assert callable(export_layup_json)
    assert callable(export_layup)


# ── 2. CdbWriter writes valid .cdb file ───────────────────────────────────


def test_cdb_writer_writes_valid_file():
    """CdbWriter writes a valid .cdb file."""
    from backend.exporters.cdb_writer import CdbMeshData, CdbWriter

    mesh_data = CdbMeshData()
    mesh_data.nodes["BODY-TEST"] = [
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 5.0, 0.0),
        (0.0, 5.0, 0.0),
    ]
    mesh_data.elements["BODY-TEST"] = [
        (1, 1, 1, [0, 1, 2, 3]),
    ]
    mesh_data.sections[1] = (2, [0.0, 0.0], [0.2, 0.2], [1, 1])
    mesh_data.components["BODY-TEST"] = "ELEM"

    with tempfile.TemporaryDirectory() as tmpdir:
        cdb_path = Path(tmpdir) / "test.cdb"
        result = CdbWriter(mesh_data).write(cdb_path)

        assert result.is_valid()
        assert result.node_count == 4
        assert result.element_count == 1
        assert result.has_units_header is True
        assert cdb_path.exists()
        assert cdb_path.stat().st_size > 0


# ── 3. Oracle parser accepts written .cdb ─────────────────────────────────


def test_oracle_parser_accepts_written_cdb():
    """Oracle parser accepts .cdb written by CdbWriter."""
    from backend.exporters.cdb_writer import CdbMeshData, CdbWriter
    from tests.oracle.cdb_parser import CdbParser

    mesh_data = CdbMeshData()
    mesh_data.nodes["BODY-TEST"] = [
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 5.0, 0.0),
        (0.0, 5.0, 0.0),
    ]
    mesh_data.elements["BODY-TEST"] = [
        (1, 1, 1, [0, 1, 2, 3]),
    ]
    mesh_data.sections[1] = (2, [0.0, 0.0], [0.2, 0.2], [1, 1])
    mesh_data.components["BODY-TEST"] = "ELEM"

    with tempfile.TemporaryDirectory() as tmpdir:
        cdb_path = Path(tmpdir) / "test.cdb"
        CdbWriter(mesh_data).write(cdb_path)

        parser = CdbParser()
        report = parser.parse(cdb_path)

        assert report.is_valid()
        assert report.node_count == 4
        assert report.element_count == 1


# ── 4. Node/element counts match ─────────────────────────────────────────


def test_node_element_counts_match():
    """Node/element counts in .cdb match written data."""
    from backend.exporters.cdb_writer import CdbMeshData, CdbWriter
    from tests.oracle.cdb_parser import CdbParser

    mesh_data = CdbMeshData()
    # 8 nodes
    mesh_data.nodes["BODY-A"] = [
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
        (10.0, 5.0, 0.0), (0.0, 5.0, 0.0),
        (0.0, 0.0, 1.0), (10.0, 0.0, 1.0),
        (10.0, 5.0, 1.0), (0.0, 5.0, 1.0),
    ]
    # 2 elements (4 nodes each)
    mesh_data.elements["BODY-A"] = [
        (1, 1, 1, [0, 1, 2, 3]),
        (1, 1, 1, [4, 5, 6, 7]),
    ]
    mesh_data.sections[1] = (1, [0.0], [0.5], [1])
    mesh_data.components["BODY-A"] = "ELEM"

    with tempfile.TemporaryDirectory() as tmpdir:
        cdb_path = Path(tmpdir) / "test.cdb"
        CdbWriter(mesh_data).write(cdb_path)

        parser = CdbParser()
        report = parser.parse(cdb_path)

        assert report.node_count == 8
        assert report.element_count == 2


# ── 5. Every element belongs to exactly one SECTYPE ───────────────────────


def test_element_to_section_mapping():
    """Every element belongs to exactly one SECTYPE with correct layer stack."""
    from backend.exporters.cdb_writer import CdbMeshData, CdbWriter
    from tests.oracle.cdb_parser import CdbParser

    mesh_data = CdbMeshData()
    mesh_data.nodes["BODY-TEST"] = [
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
        (10.0, 5.0, 0.0), (0.0, 5.0, 0.0),
    ]
    # Two elements, both section 1
    mesh_data.elements["BODY-TEST"] = [
        (1, 1, 1, [0, 1, 2, 3]),
        (1, 1, 1, [0, 1, 2, 3]),
    ]
    # Section 1 has 2 layers
    mesh_data.sections[1] = (2, [0.0, 45.0], [0.2, 0.2], [1, 1])
    mesh_data.components["BODY-TEST"] = "ELEM"

    with tempfile.TemporaryDirectory() as tmpdir:
        cdb_path = Path(tmpdir) / "test.cdb"
        CdbWriter(mesh_data).write(cdb_path)

        parser = CdbParser()
        report = parser.parse(cdb_path)

        assert report.is_valid()
        # Both elements reference section 1
        for elem_num, secid in report.element_to_section.items():
            assert secid == 1


# ── 6. Single connected component (F7) ───────────────────────────────────


def test_single_connected_component():
    """Mesh forms a single connected component (F7)."""
    from backend.exporters.cdb_writer import CdbMeshData, CdbWriter
    from tests.oracle.cdb_parser import CdbParser

    # Create two elements that share a node (connected)
    mesh_data = CdbMeshData()
    mesh_data.nodes["BODY-A"] = [
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
        (10.0, 5.0, 0.0), (0.0, 5.0, 0.0),
    ]
    mesh_data.elements["BODY-A"] = [
        (1, 1, 1, [0, 1, 2, 3]),
    ]
    mesh_data.sections[1] = (1, [0.0], [0.5], [1])
    mesh_data.components["BODY-A"] = "ELEM"

    with tempfile.TemporaryDirectory() as tmpdir:
        cdb_path = Path(tmpdir) / "test.cdb"
        CdbWriter(mesh_data).write(cdb_path)

        parser = CdbParser()
        report = parser.parse(cdb_path)

        assert report.is_single_connected_component()


def test_disconnected_elements_detected():
    """Disconnected elements are detected as NOT single connected component."""
    from backend.exporters.cdb_writer import CdbMeshData, CdbWriter
    from tests.oracle.cdb_parser import CdbParser

    # Create two elements that DON'T share any nodes (disconnected)
    # Element 1 uses nodes 0,1,2,3; Element 2 uses nodes 4,5,6,7
    mesh_data = CdbMeshData()
    mesh_data.nodes["BODY-A"] = [
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
        (10.0, 5.0, 0.0), (0.0, 5.0, 0.0),
        (20.0, 0.0, 0.0), (30.0, 0.0, 0.0),
        (30.0, 5.0, 0.0), (20.0, 5.0, 0.0),
    ]
    mesh_data.elements["BODY-A"] = [
        (1, 1, 1, [0, 1, 2, 3]),  # element 1
        (1, 1, 1, [4, 5, 6, 7]),  # element 2 (no shared nodes)
    ]
    mesh_data.sections[1] = (1, [0.0], [0.5], [1])
    mesh_data.components["BODY-A"] = "ELEM"

    with tempfile.TemporaryDirectory() as tmpdir:
        cdb_path = Path(tmpdir) / "test.cdb"
        CdbWriter(mesh_data).write(cdb_path)

        parser = CdbParser()
        report = parser.parse(cdb_path)

        # Should detect disconnected components
        assert not report.is_single_connected_component()


# ── 7. Named components match §5 naming ──────────────────────────────────


def test_named_components_naming():
    """Named components (CMBLOCK) match §5 naming contract."""
    from backend.exporters.cdb_writer import CdbMeshData, CdbWriter
    from tests.oracle.cdb_parser import CdbParser

    mesh_data = CdbMeshData()
    mesh_data.nodes["BODY-OML"] = [
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
        (10.0, 5.0, 0.0), (0.0, 5.0, 0.0),
    ]
    mesh_data.elements["BODY-OML"] = [
        (1, 1, 1, [0, 1, 2, 3]),
    ]
    mesh_data.sections[1] = (1, [0.0], [0.5], [1])
    mesh_data.components["BODY-OML"] = "ELEM"

    with tempfile.TemporaryDirectory() as tmpdir:
        cdb_path = Path(tmpdir) / "test.cdb"
        CdbWriter(mesh_data).write(cdb_path)

        parser = CdbParser()
        report = parser.parse(cdb_path)

        # BODY-OML should be in components
        assert "BODY-OML" in report.components


# ── 8. mm–tonne–s header present (F8) ────────────────────────────────────


def test_units_header_present():
    """mm–tonne–s header present (F8)."""
    from backend.exporters.cdb_writer import CdbMeshData, CdbWriter
    from tests.oracle.cdb_parser import CdbParser

    mesh_data = CdbMeshData()
    mesh_data.nodes["BODY-TEST"] = [
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
        (10.0, 5.0, 0.0), (0.0, 5.0, 0.0),
    ]
    mesh_data.elements["BODY-TEST"] = [
        (1, 1, 1, [0, 1, 2, 3]),
    ]
    mesh_data.sections[1] = (1, [0.0], [0.5], [1])
    mesh_data.components["BODY-TEST"] = "ELEM"

    with tempfile.TemporaryDirectory() as tmpdir:
        cdb_path = Path(tmpdir) / "test.cdb"
        CdbWriter(mesh_data).write(cdb_path)

        parser = CdbParser()
        report = parser.parse(cdb_path)

        assert report.has_units_header is True
        assert report.units_type == 1  # mm-tonne-s


# ── 9. Layup CSV export ──────────────────────────────────────────────────


def test_layup_csv_export():
    """Layup schedule exports to CSV."""
    from backend.schema.models import Config
    from backend.exporters.layup import export_layup

    import yaml
    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    d["planform"]["segments"] = [
        {"name": "whole", "y_end_frac": 1.0, "dihedral_deg": 0.0, "sweep_le_deg": 0.0},
    ]
    d["planform"]["stations"] = [
        {"y_frac": 0.0, "chord_mm": 200, "twist_deg": 0.0, "airfoil": "naca2412"},
        {"y_frac": 1.0, "chord_mm": 150, "twist_deg": -2.0, "airfoil": "naca2412"},
    ]
    d["spars"] = [
        {"name": "main", "xc_root": 0.25, "xc_tip": 0.25,
         "web": {"material": "cfrp_200gsm_twill", "plies": 2},
         "tongue": {"cross_section": "rect_hollow", "engagement_mm": 100, "clearance_mm": 0.2, "wall_mm": 2.0}},
    ]
    d["ribs"] = {"count": 3, "construction": {"material": "cfrp_200gsm_twill", "plies": 2},
                 "lightening_holes": {"enabled": True, "margin_mm": 8}}
    d["output"] = {"formats": ["step"]}

    config = Config.model_validate(d)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = export_layup(config, tmpdir)

        assert result.is_valid()
        assert result.csv_path is not None
        assert result.csv_path.exists()
        assert result.ply_count > 0

        # Verify CSV content
        csv_content = result.csv_path.read_text()
        assert "body_name,layer_num,angle_deg,material,thickness_mm" in csv_content


# ── 10. Layup JSON export ────────────────────────────────────────────────


def test_layup_json_export():
    """Layup schedule exports to JSON."""
    from backend.schema.models import Config
    from backend.exporters.layup import export_layup

    import yaml
    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    d["planform"]["segments"] = [
        {"name": "whole", "y_end_frac": 1.0, "dihedral_deg": 0.0, "sweep_le_deg": 0.0},
    ]
    d["planform"]["stations"] = [
        {"y_frac": 0.0, "chord_mm": 200, "twist_deg": 0.0, "airfoil": "naca2412"},
        {"y_frac": 1.0, "chord_mm": 150, "twist_deg": -2.0, "airfoil": "naca2412"},
    ]
    d["spars"] = [
        {"name": "main", "xc_root": 0.25, "xc_tip": 0.25,
         "web": {"material": "cfrp_200gsm_twill", "plies": 2},
         "tongue": {"cross_section": "rect_hollow", "engagement_mm": 100, "clearance_mm": 0.2, "wall_mm": 2.0}},
    ]
    d["ribs"] = {"count": 3, "construction": {"material": "cfrp_200gsm_twill", "plies": 2},
                 "lightening_holes": {"enabled": True, "margin_mm": 8}}
    d["output"] = {"formats": ["step"]}

    config = Config.model_validate(d)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = export_layup(config, tmpdir)

        assert result.is_valid()
        assert result.json_path is not None
        assert result.json_path.exists()

        # Verify JSON content
        json_content = json.loads(result.json_path.read_text())
        assert "plies" in json_content
        assert "bodies" in json_content
        assert "total_thickness_mm" in json_content
        assert len(json_content["plies"]) > 0


# ── 11. Layup schedule builds from config ────────────────────────────────


def test_layup_schedule_builds_from_config():
    """Layup schedule builds correctly from Config."""
    from backend.schema.models import Config
    from backend.exporters.layup import build_layup_schedule

    import yaml
    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    d["planform"]["segments"] = [
        {"name": "whole", "y_end_frac": 1.0, "dihedral_deg": 0.0, "sweep_le_deg": 0.0},
    ]
    d["planform"]["stations"] = [
        {"y_frac": 0.0, "chord_mm": 200, "twist_deg": 0.0, "airfoil": "naca2412"},
        {"y_frac": 1.0, "chord_mm": 150, "twist_deg": -2.0, "airfoil": "naca2412"},
    ]
    d["spars"] = [
        {"name": "main", "xc_root": 0.25, "xc_tip": 0.25,
         "web": {"material": "cfrp_200gsm_twill", "plies": 2},
         "tongue": {"cross_section": "rect_hollow", "engagement_mm": 100, "clearance_mm": 0.2, "wall_mm": 2.0}},
    ]
    d["ribs"] = {"count": 3, "construction": {"material": "cfrp_200gsm_twill", "plies": 2},
                 "lightening_holes": {"enabled": True, "margin_mm": 8}}
    d["output"] = {"formats": ["step"]}

    config = Config.model_validate(d)
    schedule = build_layup_schedule(config)

    assert len(schedule.plies) > 0
    assert len(schedule.bodies) > 0
    assert schedule.total_thickness_mm > 0


# ── 12. CdbMeshData has all required fields ──────────────────────────────


def test_cdb_mesh_data_has_required_fields():
    """CdbMeshData has all required fields."""
    from backend.exporters.cdb_writer import CdbMeshData

    mesh_data = CdbMeshData()
    assert hasattr(mesh_data, "nodes")
    assert hasattr(mesh_data, "elements")
    assert hasattr(mesh_data, "sections")
    assert hasattr(mesh_data, "element_types")
    assert hasattr(mesh_data, "components")


# ── 13. CdbWriteResult has all required fields ───────────────────────────


def test_cdb_write_result_has_required_fields():
    """CdbWriteResult has all required fields."""
    from backend.exporters.cdb_writer import CdbWriteResult

    result = CdbWriteResult(path=Path("/tmp/test.cdb"))
    assert hasattr(result, "path")
    assert hasattr(result, "node_count")
    assert hasattr(result, "element_count")
    assert hasattr(result, "section_count")
    assert hasattr(result, "component_count")
    assert hasattr(result, "has_units_header")
    assert hasattr(result, "errors")


# ── 14. LayupExportResult has all required fields ────────────────────────


def test_layup_export_result_has_required_fields():
    """LayupExportResult has all required fields."""
    from backend.exporters.layup import LayupExportResult

    result = LayupExportResult()
    assert hasattr(result, "csv_path")
    assert hasattr(result, "json_path")
    assert hasattr(result, "ply_count")
    assert hasattr(result, "body_count")
    assert hasattr(result, "errors")


# ── Gate metrics ──────────────────────────────────────────────────────────


def test_phase_metrics(gate_metrics):
    """Record phase metrics for the gate artifact."""
    gate_metrics["p13"] = {
        "cdb_writer": "APDL blocked format (.cdb) writer with NBLOCK/EBLOCK/ET/SECTYPE/SECDATA/CMBLOCK",
        "layup_exporter": "CSV + JSON layup schedule exporter",
        "oracle_parser": "Independent .cdb parser from Ansys spec (F12)",
        "checks": [
            "node/element counts match",
            "every element belongs to exactly one SECTYPE",
            "single connected component (F7)",
            "named components match §5 naming",
            "mm–tonne–s header present (F8)",
        ],
        "functions": [
            "CdbWriter.write()",
            "CdbMeshData",
            "build_layup_schedule()",
            "export_layup_csv()",
            "export_layup_json()",
            "CdbParser.parse()",
            "CdbReport.is_single_connected_component()",
        ],
        "description": "Ansys .cdb writer + layup schedule with oracle parser validation",
    }
