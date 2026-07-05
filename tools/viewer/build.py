#!/usr/bin/env python3
"""Assemble the standalone backend-capability viewer (tools/viewer/) into one
self-contained HTML file: template + vendored three.js + exported geometry
JSON + app.js, spliced together (no external requests at view time).

NOT the product UI (that's P10, React+three.js against the real API) — this
is a throwaway diagnostic to see what the backend geometry pipeline can build
right now. Regenerate whenever the exported data or app.js changes:

    .venv/bin/python scripts/export_viewer_data.py <config.yaml>
    python3 tools/viewer/build.py
"""
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
VIEWER_DIR = ROOT / "tools" / "viewer"
CACHE_DIR = VIEWER_DIR / ".cache"
THREE_JS_URL = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"


def _get_three_js() -> str:
    cached = CACHE_DIR / "three.min.js"
    if cached.exists():
        return cached.read_text()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"fetching {THREE_JS_URL} ...")
    with urllib.request.urlopen(THREE_JS_URL) as resp:
        text = resp.read().decode("utf-8")
    cached.write_text(text)
    return text


def main() -> int:
    data_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts" / "viewer_data.json"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else VIEWER_DIR / "dist" / "viewer.html"

    if not data_path.exists():
        print(f"no {data_path} — run scripts/export_viewer_data.py on the workspace first", file=sys.stderr)
        return 1

    template = (VIEWER_DIR / "index_template.html").read_text()
    three_js = _get_three_js()
    viewer_data = data_path.read_text()
    app_js = (VIEWER_DIR / "app.js").read_text()

    html = template.replace("<!-- __THREE_JS__ -->", three_js)
    html = html.replace("/* __VIEWER_DATA__ */ {}", viewer_data)
    html = html.replace("<!-- __APP_JS__ -->", app_js)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    print(f"wrote {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
