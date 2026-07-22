# ──────────────────────────────────────────────
# Makefile — AI-Powered Predictive Maintenance
# ──────────────────────────────────────────────

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

# ─── Help ─────────────────────────────────────
help:
	@echo "Usage:"
	@echo "  make install     Install dependencies"
	@echo "  make lint        Run ruff linter"
	@echo "  make format      Format code with ruff"
	@echo "  make typecheck   Run mypy type checker"
	@echo "  make check       Run all checks (lint + typecheck)"
	@echo "  make test        Run tests"
	@echo "  make clean       Remove cache files"

# ─── Install ──────────────────────────────────
install:
	pip install -r requirements.txt
	pip install ruff mypy

# ─── Lint ─────────────────────────────────────
lint:
	ruff check .

# ─── Format ───────────────────────────────────
format:
	ruff format .

# ─── Type check ───────────────────────────────
typecheck:
	mypy . --ignore-missing-imports

# ─── All checks ───────────────────────────────
check: lint typecheck

# ─── Test ─────────────────────────────────────
test:
	./.venv/bin/python -m pytest tests/ -v

# ─── Run & Services ───────────────────────────
api:
	./.venv/bin/uvicorn api.main:app --reload --port 8000 --reload-exclude "frontend/node_modules/*"

run:
	cd frontend && npm run dev

# ─── Database ─────────────────────────────────
migrate:
	./.venv/bin/alembic upgrade head

migrate-fresh:
	rm -f vehicle_health.db
	./.venv/bin/alembic upgrade head

# ─── Simulators & Data ────────────────────────
simulate:
	./.venv/bin/python -m simulator.obd_simulator --interval 5 --profile healthy

fleet:
	./.venv/bin/python -m simulator.fleet_simulator --vehicles 5 --interval 10

generate-data:
	./.venv/bin/python scripts/generate_data.py

# ─── Clean ────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache .mypy_cache

.PHONY: help install lint format typecheck check test clean api run migrate migrate-fresh simulate fleet generate-data
