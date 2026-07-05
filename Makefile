.DEFAULT_GOAL := help

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
ALEMBIC := $(VENV)/bin/alembic

export DATABASE_URL ?= postgresql+psycopg://wingstructgen:wingstructgen@localhost:5432/wingstructgen
export REDIS_URL ?= redis://localhost:6379/0

.PHONY: help venv up down migrate seed probes gate regress sync-agents

help:
	@echo "targets: venv up down migrate seed probes gate PHASE=pXX regress sync-agents"

venv:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

up:
	docker compose up -d
	@echo "waiting for postgres + redis to report healthy..."
	@until [ "$$(docker compose ps -q postgres | xargs docker inspect -f '{{.State.Health.Status}}')" = "healthy" ] && \
	       [ "$$(docker compose ps -q redis | xargs docker inspect -f '{{.State.Health.Status}}')" = "healthy" ]; do \
	  sleep 1; \
	done
	@echo "postgres + redis healthy"

down:
	docker compose down

migrate:
	$(ALEMBIC) upgrade head

seed: migrate
	@echo "no seed data required at P0 (materials/airfoil seeding lands in P1+)"

probes:
	@echo "# R0 Findings — P0" > docs/r0_findings/p00.md
	@echo "" >> docs/r0_findings/p00.md
	$(PY) scripts/r0_probes/probe_ocp.py
	$(PY) scripts/r0_probes/probe_gmsh.py

gate:
	@if [ -z "$(PHASE)" ]; then echo "usage: make gate PHASE=p00"; exit 1; fi
	$(PYTEST) tests/gates/test_$(PHASE)_*.py -v

regress:
	@$(PY) scripts/run_regress.py

sync-agents:
	@{ \
	  echo "<!-- GENERATED from CLAUDE.md by 'make sync-agents' — do not hand-edit. -->"; \
	  echo; \
	  cat CLAUDE.md; \
	} > AGENTS.md
	@echo "AGENTS.md regenerated from CLAUDE.md"
