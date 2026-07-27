#!/usr/bin/env python3
"""R0 probe: does cq.Assembly.export(..., exportType="GLTF") preserve a
name containing '/' as ONE literal node name, or split it into a nested
hierarchy (OCCT's XCAF label system sometimes treats '/' as a hierarchy
separator)? Found necessary empirically: P10's naming contract
(SEG-C/BODY-x/ROLE-y) uses '/', and the P10 gate's real glTF body-toggle
test returns zero matches for every body despite the file loading fine.

Cheap, no real geometry needed — same toy-box pattern as the original P9
export-API probe.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p10.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def main() -> int:
    lines = ["## probe_gltf_slash_names.py (P10 — does '/' in a glTF node name survive as one literal name?)"]
    try:
        import cadquery as cq

        box = cq.Solid.makeBox(10, 20, 5)
        slash_name = "SEG-C/BODY-test/ROLE-test"

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "probe.gltf")
            assy = cq.Assembly()
            assy.add(cq.Workplane(obj=box), name=slash_name)
            assy.export(path, exportType="GLTF")
            doc = json.loads(Path(path).read_text())

        node_names = [n.get("name") for n in doc.get("nodes", []) if n.get("name")]
        lines.append(f"- input name: {slash_name!r}")
        lines.append(f"- nodes in output: {len(doc.get('nodes', []))}, named: {node_names}")
        exact_match = slash_name in node_names
        lines.append(f"- exact literal match present: {exact_match}")
        if not exact_match:
            split_present = all(part in node_names for part in slash_name.split("/"))
            lines.append(f"- split-into-hierarchy-by-'/' hypothesis (each segment as its own node name): {split_present}")
        lines.append(f"- CONCLUSION: {'literal name preserved' if exact_match else 'name NOT preserved literally — see split hypothesis above'}")

    except Exception as exc:  # noqa: BLE001
        import traceback
        lines.append(f"- **PROBE FAILED**: {type(exc).__name__}: {exc}")
        lines.append("```\n" + traceback.format_exc() + "```")
        _append(lines)
        print("\n".join(lines))
        return 1

    _append(lines)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
