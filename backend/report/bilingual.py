"""Bilingual (EN/AR) PDF report generation via lualatex Docker container.

Reads gate_results rows from Postgres, generates a lualatex document with
EN pages (LTR) and AR pages (RTL, Amiri font), compiles via Docker,
returns the PDF bytes.

Usage:
    from backend.report.bilingual import generate_report
    pdf_bytes = generate_report(job_id, db_session)
"""
from __future__ import annotations

import datetime
import logging
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DOCKER_IMAGE = "wingo-lualatex:probe"
ROOT = Path(__file__).resolve().parent.parent.parent


# ── LaTeX template ────────────────────────────────────────────────────────
# Uses {gate_rows_en} and {gate_rows_ar} as placeholders replaced by str.replace()

_TEMPLATE = (
    "% WingStructGen Bilingual Report — auto-generated\n"
    "\\documentclass[a4paper,11pt]{article}\n"
    "\\usepackage[margin=25mm]{geometry}\n"
    "\\usepackage{fontspec}\n"
    "\\usepackage{polyglossia}\n"
    "\\usepackage{graphicx}\n"
    "\\usepackage{booktabs}\n"
    "\\usepackage{longtable}\n"
    "\n"
    "% Amiri for Arabic, Latin Modern for English\n"
    "\\setmainfont{Latin Modern Roman}\n"
    "\\setsansfont{Latin Modern Sans}\n"
    "\\setmonofont{Latin Modern Mono}\n"
    "\\newfontfamily{\\arabicfont}[Script=Arabic]{Amiri}\n"
    "\\setotherlanguage{arabic}\n"
    "\n"
    "\\title{WingStructGen Report}\n"
    "\\author{Automated Gate Report}\n"
    "\\date{}\n"
    "\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\n"
    "\\section{Overview}\n"
    "\n"
    "This report summarizes all gate results for the job.\n"
    "\n"
    "% ── Gate results table (EN) ──────────────────────────────────────\n"
    "\\section{Gate Results}\n"
    "\n"
    "\\begin{tabular}{lll}\n"
    "\\toprule\n"
    "\\textbf{Phase} & \\textbf{Name} & \\textbf{Passed} \\\\\n"
    "\\midrule\n"
    "{gate_rows_en}\n"
    "\\bottomrule\n"
    "\\end{tabular}\n"
    "\n"
    "% ── Arabic section (RTL) ─────────────────────────────────────────\n"
    "\\begin{arabic}\n"
    "\\section{نتائج البوابات}\n"
    "\n"
    "{gate_rows_ar}\n"
    "\\end{arabic}\n"
    "\n"
    "\\end{document}\n"
)

_GATE_ROW_EN = "\\textbf{{{phase}}} & {name} & {passed} \\\\"
_GATE_ROW_AR = "\\textbf{{{phase}}} & {name} & {passed}"


def _escape_latex(text: str) -> str:
    """Escape LaTeX special characters."""
    return (
        text.replace("&", "\\&")
        .replace("%", "\\%")
        .replace("$", "\\$")
        .replace("#", "\\#")
        .replace("_", "\\_")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("~", "\\textasciitilde{}")
        .replace("^", "\\textasciicircum{}")
    )


def _build_latex(gate_rows_en: str, gate_rows_ar: str) -> str:
    """Build the complete LaTeX document from gate rows.

    Uses str.replace() instead of .format() to avoid brace conflicts.
    """
    latex = _TEMPLATE
    latex = latex.replace("{gate_rows_en}", gate_rows_en)
    latex = latex.replace("{gate_rows_ar}", gate_rows_ar)
    return latex


def generate_report(
    job_id: uuid.UUID,
    db_session: Any,
) -> bytes:
    """Generate a bilingual EN/AR PDF report for a job's gate results.

    Args:
        job_id: The job UUID to generate the report for.
        db_session: SQLAlchemy session for querying gate_results.

    Returns:
        PDF bytes.

    Raises:
        RuntimeError: If lualatex compilation fails.
    """
    # Query gate_results for this job
    from backend.schema.db_models import GateResultRow

    results = (
        db_session.query(GateResultRow)
        .filter(GateResultRow.job_id == job_id)
        .order_by(GateResultRow.phase)
        .all()
    )

    if not results:
        raise ValueError(f"No gate results found for job {job_id}")

    # Build gate rows
    gate_rows_en = []
    gate_rows_ar = []
    for r in results:
        phase = _escape_latex(r.phase)
        name = _escape_latex(r.name)
        passed = _escape_latex("Pass" if r.passed else "Fail")
        gate_rows_en.append(_GATE_ROW_EN.format(phase=phase, name=name, passed=passed))
        gate_rows_ar.append(_GATE_ROW_AR.format(phase=phase, name=name, passed=passed))

    gate_rows_en_str = "\n".join(gate_rows_en)
    gate_rows_ar_str = "\n".join(gate_rows_ar)

    # Build LaTeX document
    tex_content = _build_latex(gate_rows_en_str, gate_rows_ar_str)

    # Compile via Docker
    return _compile_latex(tex_content)


def _compile_latex(tex_content: str) -> bytes:
    """Compile a LaTeX document via the lualatex Docker container.

    Args:
        tex_content: Raw LaTeX source.

    Returns:
        PDF bytes.

    Raises:
        RuntimeError: If compilation fails.
    """
    image = DOCKER_IMAGE
    with tempfile.TemporaryDirectory(prefix="wingo_report_") as tmpdir:
        td = Path(tmpdir)
        tex_file = td / "report.tex"
        tex_file.write_text(tex_content)

        # Copy to writable location inside container and compile
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{td}:/src:rw",
            image,
            "bash", "-c",
            "cp /src/report.tex /tmp/report.tex && "
            "lualatex -interaction=nonstopmode "
            "-output-directory=/tmp /tmp/report.tex 2>&1; "
            "test -f /tmp/report.pdf",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )

        if result.returncode != 0:
            stderr = result.stderr[-2000:] if result.stderr else "no stderr"
            raise RuntimeError(
                f"lualatex compilation failed (exit {result.returncode}): {stderr}"
            )

        pdf_file = td / "report.pdf"
        if not pdf_file.exists():
            raise RuntimeError(
                f"No PDF produced. lualatex output:\n{result.stderr[-2000:]}"
            )

        return pdf_file.read_bytes()


# ── Data class for gate report summary ────────────────────────────────────

GateReportEntry = dict[str, Any]


def build_gate_report_entries(
    job_id: uuid.UUID,
    db_session: Any,
) -> list[GateReportEntry]:
    """Build a structured list of gate report entries from gate_results.

    Returns:
        List of dicts with keys: phase, name, passed, metrics, created_at.
    """
    from backend.schema.db_models import GateResultRow

    results = (
        db_session.query(GateResultRow)
        .filter(GateResultRow.job_id == job_id)
        .order_by(GateResultRow.phase)
        .all()
    )

    entries = []
    for r in results:
        entries.append(
            {
                "phase": r.phase,
                "name": r.name,
                "passed": r.passed,
                "metrics": r.metrics,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return entries
