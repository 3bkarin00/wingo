"""initial schema — configs, jobs, gate_results, materials, airfoils, ansys_acceptance

Revision ID: 0001
Revises:
Create Date: 2026-07-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("schema_version", sa.String, nullable=False),
        sa.Column("data", postgresql.JSONB, nullable=False),
        sa.Column(
            "parent_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("configs.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("configs.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("checkpoint", postgresql.JSONB, nullable=True),
        sa.Column("worker_id", sa.String, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timing", postgresql.JSONB, nullable=True),
        sa.Column("artifact_manifest", postgresql.JSONB, nullable=True),
    )

    op.create_table(
        "gate_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True
        ),
        sa.Column("phase", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("metrics", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("e1_mpa", sa.Float, nullable=True),
        sa.Column("e2_mpa", sa.Float, nullable=True),
        sa.Column("g12_mpa", sa.Float, nullable=True),
        sa.Column("nu12", sa.Float, nullable=True),
        sa.Column("density_kg_m3", sa.Float, nullable=True),
        sa.Column("ply_thickness_mm", sa.Float, nullable=True),
        sa.Column("allowables", postgresql.JSONB, nullable=True),
        sa.Column("is_custom", sa.Boolean, nullable=False, server_default="false"),
    )

    op.create_table(
        "airfoils",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("raw_points", postgresql.JSONB, nullable=True),
        sa.Column("normalized_points", postgresql.JSONB, nullable=True),
        sa.Column("format_detected", sa.String, nullable=True),
        sa.Column("validation_flags", postgresql.JSONB, nullable=True),
    )

    op.create_table(
        "ansys_acceptance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True
        ),
        sa.Column("checklist_version", sa.String, nullable=False),
        sa.Column("ansys_version", sa.String, nullable=False),
        sa.Column("tester", sa.String, nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("results", postgresql.JSONB, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ansys_acceptance")
    op.drop_table("airfoils")
    op.drop_table("materials")
    op.drop_table("gate_results")
    op.drop_table("jobs")
    op.drop_table("configs")
