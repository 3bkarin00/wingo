"""Bilingual report generation (P19).

Generates a bilingual (EN/AR) PDF report from gate_results data using
lualatex in a Docker container.

Usage:
    from backend.report.bilingual import generate_report
    pdf_bytes = generate_report(job_id, db_session)
"""
