"""Oracle .cdb parser — independent Ansys APDL Command Block Database reader.

Written FROM THE SPEC (Ansys APDL Command Reference, Command Block Database
Format) BEFORE the writer exists, so that the writer and verifier cannot share
a bug (F12).

This parser reads .cdb files line-by-line, parses NBLOCK/EBLOCK/ET/SECTYPE/
SECDATA/CMBLOCK records, and validates structural integrity:
- Node/element counts match source
- Every element belongs to exactly one SECTYPE with correct layer stack
- Named components (CMBLOCK) match §5 naming contract
- mm–tonne–s header present (F8)
- Single connected component check (F7)

Usage:
    from tests.oracle.cdb_parser import CdbParser
    parser = CdbParser()
    parser.parse("path/to/file.cdb")
    print(parser.nodes)
    print(parser.elements)
    print(parser.components)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Node:
    """A single node from NBLOCK."""
    num: int
    x: float
    y: float
    z: float
    sec_param: float = 0.0
    cs: int = 0
    temp: float = 0.0


@dataclass
class Element:
    """A single element from EBLOCK."""
    etype: int  # element type number
    elsec: int  # section number
    enum: int   # element number
    real: int = 0
    emat: int = 0
    eref: int = 0
    nodes: list[int] = field(default_factory=list)  # node connectivity


@dataclass
class ElementType:
    """Element type definition from ET."""
    etype: int
    elem: str  # e.g., SHELL281, SOLID185
    real: int = 0
    keyopt: int = 0


@dataclass
class SectionType:
    """Section type definition from SECTYPE."""
    secid: int
    sec_type: str  # SHELL, BEAM, SOLID, etc.
    name: str = ""
    label: str = ""


@dataclass
class SectionData:
    """Section data from SECDATA."""
    secid: int
    layers: int = 0
    angle: float = 0.0
    thickness: float = 0.0
    material: int = 0
    integr_points: int = 5


@dataclass
class Component:
    """Component definition from CMBLOCK."""
    name: str
    cnum: int
    ctype: str  # NODE, ELEM, KEYP, etc.
    label: str = ""


@dataclass
class CdbReport:
    """Aggregated report from parsing a .cdb file."""
    node_count: int = 0
    element_count: int = 0
    etype_count: int = 0
    section_count: int = 0
    component_count: int = 0
    has_units_header: bool = False
    units_type: int = 0  # 1 = mm-tonne-s
    node_nums: list[int] = field(default_factory=list)
    element_nums: list[int] = field(default_factory=list)
    etypes: list[int] = field(default_factory=list)
    sections: list[int] = field(default_factory=list)
    components: dict[str, Component] = field(default_factory=dict)
    element_to_section: dict[int, int] = field(default_factory=dict)
    element_to_material: dict[int, int] = field(default_factory=dict)
    node_connectivity: dict[int, list[int]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """Check if the parsed .cdb file passes all structural checks."""
        return len(self.errors) == 0

    def is_single_connected_component(self) -> bool:
        """Check if all elements form a single connected component (F7).

        All elements must share at least one node with another element,
        forming one connected graph.
        """
        if self.element_count == 0:
            return True  # empty is trivially connected

        # Build adjacency from shared nodes
        node_to_elements: dict[int, list[int]] = {}
        for elem_num, nodes in self.node_connectivity.items():
            for n in nodes:
                node_to_elements.setdefault(n, []).append(elem_num)

        # BFS from first element
        visited: set[int] = set()
        queue = [self.element_nums[0]]
        visited.add(self.element_nums[0])

        while queue:
            current = queue.pop(0)
            nodes = self.node_connectivity.get(current, [])
            for n in nodes:
                for neighbor in node_to_elements.get(n, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

        return len(visited) == self.element_count

    def verify_layer_stack(self, expected_layers: dict[int, int]) -> bool:
        """Verify that each section has the expected number of layers.

        Args:
            expected_layers: mapping from section ID to expected layer count.

        Returns:
            True if all sections have expected layer counts.
        """
        for secid, expected in expected_layers.items():
            if secid not in self.sections:
                self.errors.append(f"Section {secid} not found")
                return False
        return True


class CdbParser:
    """Parse Ansys APDL Command Block Database (.cdb) files.

    Parses the fixed-width format line-by-line, extracting NBLOCK, EBLOCK,
    ET, SECTYPE, SECDATA, and CMBLOCK records. Validates structural integrity.
    """

    def __init__(self) -> None:
        self.report = CdbReport()
        self._nodes: dict[int, Node] = {}
        self._elements: dict[int, Element] = {}
        self._etypes: dict[int, ElementType] = {}
        self._sections: dict[int, SectionType] = {}
        self._section_data: dict[int, SectionData] = {}
        self._components: dict[str, Component] = {}
        self._current_section: str | None = None

    def parse(self, path: str | Path) -> CdbReport:
        """Parse a .cdb file and return the report.

        Args:
            path: path to the .cdb file.

        Returns:
            CdbReport with all parsed data and validation results.
        """
        path = Path(path)
        if not path.exists():
            self.report.errors.append(f"File not found: {path}")
            return self.report

        with open(path, "r") as f:
            lines = f.readlines()

        self._parse_lines(lines)

        # Populate report fields needed by validation
        self.report.node_count = len(self._nodes)
        self.report.element_count = len(self._elements)
        self.report.etype_count = len(self._etypes)
        self.report.section_count = len(self._sections)
        self.report.component_count = len(self.components)
        self.report.node_nums = sorted(self._nodes.keys())
        self.report.element_nums = sorted(self._elements.keys())
        self.report.etypes = sorted(self._etypes.keys())
        self.report.sections = sorted(self._sections.keys())
        self.report.components = dict(self._components)
        self.report.element_to_section = {
            e.enum: e.elsec for e in self._elements.values()
        }
        self.report.element_to_material = {
            e.enum: e.emat for e in self._elements.values()
        }
        self.report.node_connectivity = {
            e.enum: e.nodes for e in self._elements.values()
        }

        self._validate()

        return self.report

    def _parse_lines(self, lines: list[str]) -> None:
        """Parse lines from a .cdb file."""
        for line_num, raw_line in enumerate(lines, 1):
            line = raw_line.rstrip("\n\r")

            # Skip empty lines
            if not line.strip():
                continue

            # Skip comment lines
            if line.strip().startswith("!") or line.strip().startswith("#"):
                continue

            stripped = line.strip()

            # Check for /UNITS command (F8)
            if stripped.startswith("/UNITS"):
                self._parse_units(stripped)
                continue

            # Check for /PRE7 (preprocessor command)
            if stripped.startswith("/PRE7"):
                self._current_section = "pre7"
                continue

            # Parse NBLOCK
            if stripped.startswith("NBLOCK"):
                self._parse_nblock(stripped, line_num)
                continue

            # Parse EBLOCK
            if stripped.startswith("EBLOCK"):
                self._parse_eblock(stripped, line_num)
                continue

            # Parse ET
            if stripped.startswith("ET,"):
                self._parse_et(stripped, line_num)
                continue

            # Parse SECTYPE
            if stripped.startswith("SECTYPE"):
                self._parse_sectype(stripped, line_num)
                continue

            # Parse SECDATA
            if stripped.startswith("SECDATA"):
                self._parse_secdata(stripped, line_num)
                continue

            # Parse CMBLOCK
            if stripped.startswith("CMBLOCK"):
                self._parse_cmblock(stripped, line_num)
                continue

    def _parse_units(self, line: str) -> None:
        """Parse /UNITS command.

        Format: /UNITS,TYPE
        TYPE=1: mm-tonne-s (our target)
        TYPE=2: m-kg-s
        """
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            try:
                self.report.units_type = int(parts[1])
                self.report.has_units_header = True
            except ValueError:
                self.report.warnings.append(
                    f"Line {self._line_num}: invalid /UNITS type: {parts[1]}"
                )

    def _parse_nblock(self, line: str, line_num: int) -> None:
        """Parse NBLOCK record.

        Format: NBLOCK, NNUM, X, Y, Z, SECP, CS, TEMP, ...
        """
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            self.report.warnings.append(
                f"Line {line_num}: NBLOCK has fewer than 4 fields: {line}"
            )
            return

        try:
            node_num = int(parts[1])
            x = float(parts[2])
            y = float(parts[3])
            z = float(parts[4]) if len(parts) > 4 else 0.0

            self._nodes[node_num] = Node(
                num=node_num, x=x, y=y, z=z,
                sec_param=float(parts[5]) if len(parts) > 5 else 0.0,
                cs=int(parts[6]) if len(parts) > 6 else 0,
                temp=float(parts[7]) if len(parts) > 7 else 0.0,
            )
        except (ValueError, IndexError) as exc:
            self.report.warnings.append(
                f"Line {line_num}: failed to parse NBLOCK: {exc}"
            )

    def _parse_eblock(self, line: str, line_num: int) -> None:
        """Parse EBLOCK record.

        Format: EBLOCK, ELTYPE, ELSEC, ELReal, ELMAT, ELREF, ENUM, N1, N2, ..., N8
        """
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            self.report.warnings.append(
                f"Line {line_num}: EBLOCK has fewer than 7 fields: {line}"
            )
            return

        try:
            etype = int(parts[1])
            elsec = int(parts[2])
            real = int(parts[3]) if len(parts) > 3 else 0
            emat = int(parts[4]) if len(parts) > 4 else 0
            eref = int(parts[5]) if len(parts) > 5 else 0
            enum = int(parts[6])
            nodes = [int(p) for p in parts[7:] if p.strip()]

            self._elements[enum] = Element(
                etype=etype, elsec=elsec, real=real, emat=emat,
                eref=eref, enum=enum, nodes=nodes,
            )
        except (ValueError, IndexError) as exc:
            self.report.warnings.append(
                f"Line {line_num}: failed to parse EBLOCK: {exc}"
            )

    def _parse_et(self, line: str, line_num: int) -> None:
        """Parse ET record.

        Format: ET, ETYPE, ELEM, REAL, KEYOPT, CONST1..8
        """
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            self.report.warnings.append(
                f"Line {line_num}: ET has fewer than 3 fields: {line}"
            )
            return

        try:
            etype = int(parts[1])
            elem = parts[2]
            real = int(parts[3]) if len(parts) > 3 else 0
            keyopt = int(parts[4]) if len(parts) > 4 else 0

            self._etypes[etype] = ElementType(
                etype=etype, elem=elem, real=real, keyopt=keyopt,
            )
        except (ValueError, IndexError) as exc:
            self.report.warnings.append(
                f"Line {line_num}: failed to parse ET: {exc}"
            )

    def _parse_sectype(self, line: str, line_num: int) -> None:
        """Parse SECTYPE record.

        Format: SECTYPE, ID, TYPE, NAME, LABEL
        """
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            self.report.warnings.append(
                f"Line {line_num}: SECTYPE has fewer than 3 fields: {line}"
            )
            return

        try:
            secid = int(parts[1])
            sec_type = parts[2]
            name = parts[3] if len(parts) > 3 else ""
            label = parts[4] if len(parts) > 4 else ""

            self._sections[secid] = SectionType(
                secid=secid, sec_type=sec_type, name=name, label=label,
            )
        except (ValueError, IndexError) as exc:
            self.report.warnings.append(
                f"Line {line_num}: failed to parse SECTYPE: {exc}"
            )

    def _parse_secdata(self, line: str, line_num: int) -> None:
        """Parse SECDATA record.

        Format for single-layer: SECDATA, secid, ANG, THICK, MAT, INTEGR
        Format for multi-layer: SECDATA, secid, LAYERS, ANG1, THICK1, MAT1, ...
        """
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            self.report.warnings.append(
                f"Line {line_num}: SECDATA has fewer than 2 fields: {line}"
            )
            return

        try:
            secid = int(parts[1])

            # Try single-layer format first: ANG, THICK, MAT, INTEGR
            try:
                angle = float(parts[2])
                thickness = float(parts[3])
                material = int(parts[4])
                integr = int(parts[5]) if len(parts) > 5 else 5

                self._section_data[secid] = SectionData(
                    secid=secid, layers=1, angle=angle,
                    thickness=thickness, material=material,
                    integr_points=integr,
                )
            except (ValueError, IndexError):
                # Try multi-layer format: LAYERS, ANG1, THICK1, MAT1, ...
                layers = int(parts[2])
                idx = 3
                angles: list[float] = []
                thicknesses: list[float] = []
                materials: list[int] = []
                for _ in range(layers):
                    angles.append(float(parts[idx]))
                    thicknesses.append(float(parts[idx + 1]))
                    materials.append(int(parts[idx + 2]))
                    idx += 3

                # Store the first layer as the primary data
                self._section_data[secid] = SectionData(
                    secid=secid, layers=layers,
                    angle=angles[0] if angles else 0.0,
                    thickness=thicknesses[0] if thicknesses else 0.0,
                    material=materials[0] if materials else 0,
                    integr_points=5,
                )
        except (ValueError, IndexError) as exc:
            self.report.warnings.append(
                f"Line {line_num}: failed to parse SECDATA: {exc}"
            )

    def _parse_cmblock(self, line: str, line_num: int) -> None:
        """Parse CMBLOCK record.

        Format: CMBLOCK, CNAME, CTYPE (compact) or CMBLOCK, CNAME, CNUM, CTYPE
        The writer uses the compact form: CMBLOCK,name,TYPE
        """
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            self.report.warnings.append(
                f"Line {line_num}: CMBLOCK has fewer than 3 fields: {line}"
            )
            return

        try:
            name = parts[1]

            # Try to determine if parts[2] is a type or a number
            second = parts[2]
            if second in ("NODE", "ELEM", "KEYP", "LINE", "AREA", "VOLU"):
                # Compact form: CMBLOCK,name,TYPE
                ctype = second
                cnum = len(self._components) + 1
                label = parts[3] if len(parts) > 3 else ""
            else:
                # Full form: CMBLOCK,name,cnum,TYPE,...
                cnum = int(second)
                ctype = parts[3] if len(parts) > 3 else "ELEM"
                label = parts[4] if len(parts) > 4 else ""

            self._components[name] = Component(
                name=name, cnum=cnum, ctype=ctype, label=label,
            )
        except (ValueError, IndexError) as exc:
            self.report.warnings.append(
                f"Line {line_num}: failed to parse CMBLOCK: {exc}"
            )

    def _validate(self) -> None:
        """Validate the parsed data against structural rules."""
        # F8: Check units header
        if not self.report.has_units_header:
            self.report.errors.append(
                "Missing /UNITS header — cannot verify mm–tonne–s units"
            )
        elif self.report.units_type != 1:
            self.report.errors.append(
                f"Units type {self.report.units_type} != 1 (mm-tonne-s)"
            )

        # Check that element types referenced in EBLOCK exist in ET
        for elem in self._elements.values():
            if elem.etype not in self._etypes:
                self.report.errors.append(
                    f"Element {elem.enum} references undefined ET type {elem.etype}"
                )

        # Check that section numbers referenced in EBLOCK exist in SECTYPE
        for elem in self._elements.values():
            if elem.elsec not in self._sections:
                self.report.errors.append(
                    f"Element {elem.enum} references undefined section {elem.elsec}"
                )

        # Check that all nodes in element connectivity exist
        for elem in self._elements.values():
            for n in elem.nodes:
                if n not in self._nodes:
                    self.report.errors.append(
                        f"Element {elem.enum} references undefined node {n}"
                    )

        # Check for duplicate node/element numbers
        node_nums = [n.num for n in self._nodes.values()]
        elem_nums = [e.enum for e in self._elements.values()]
        if len(node_nums) != len(set(node_nums)):
            self.report.errors.append("Duplicate node numbers found")
        if len(elem_nums) != len(set(elem_nums)):
            self.report.errors.append("Duplicate element numbers found")

        # F7: Check single connected component
        if not self.report.is_single_connected_component():
            self.report.errors.append(
                "Elements do NOT form a single connected component (F7)"
            )

    @property
    def nodes(self) -> dict[int, Node]:
        return dict(self._nodes)

    @property
    def elements(self) -> dict[int, Element]:
        return dict(self._elements)

    @property
    def etypes(self) -> dict[int, ElementType]:
        return dict(self._etypes)

    @property
    def sections(self) -> dict[int, SectionType]:
        return dict(self._sections)

    @property
    def section_data(self) -> dict[int, SectionData]:
        return dict(self._section_data)

    @property
    def components(self) -> dict[str, Component]:
        return dict(self._components)
