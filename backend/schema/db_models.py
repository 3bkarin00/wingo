"""SQLAlchemy ORM models — the §7 data model. One table per bullet in
plan.md §7; `gate_results` is what the P19 report renders from, so its
shape can't diverge from what gates actually write (conftest.py)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConfigRow(Base):
    __tablename__ = "configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parent_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("configs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("configs.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    checkpoint: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)
    timing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    artifact_manifest: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class GateResultRow(Base):
    __tablename__ = "gate_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True
    )
    phase: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    passed: Mapped[bool] = mapped_column(nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class MaterialRow(Base):
    __tablename__ = "materials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    e1_mpa: Mapped[float | None] = mapped_column(nullable=True)
    e2_mpa: Mapped[float | None] = mapped_column(nullable=True)
    g12_mpa: Mapped[float | None] = mapped_column(nullable=True)
    nu12: Mapped[float | None] = mapped_column(nullable=True)
    density_kg_m3: Mapped[float | None] = mapped_column(nullable=True)
    ply_thickness_mm: Mapped[float | None] = mapped_column(nullable=True)
    allowables: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_custom: Mapped[bool] = mapped_column(default=False)


class AirfoilRow(Base):
    __tablename__ = "airfoils"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    raw_points: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    normalized_points: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    format_detected: Mapped[str | None] = mapped_column(String, nullable=True)
    validation_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AnsysAcceptanceRow(Base):
    __tablename__ = "ansys_acceptance"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True
    )
    checklist_version: Mapped[str] = mapped_column(String, nullable=False)
    ansys_version: Mapped[str] = mapped_column(String, nullable=False)
    tester: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[datetime] = mapped_column(nullable=False)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False)
