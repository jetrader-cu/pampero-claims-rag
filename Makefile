SHELL := /bin/bash

.PHONY: help up down restart logs ps test test-backend test-frontend lint lint-backend lint-frontend eval seed clean reset

help:
	@echo "Pampero Claims Assistant — Comandos disponibles:"
	@echo "  make up             Levanta los servicios de docker compose en segundo plano"
	@echo "  make down           Detiene y remueve los contenedores de compose"
	@echo "  make restart        Reinicia los servicios de compose"
	@echo "  make logs           Muestra los logs de los contenedores en tiempo real"
	@echo "  make ps             Muestra el estado de los contenedores"
	@echo "  make lint           Ejecuta linters y comprobación de tipos (backend y frontend)"
	@echo "  make test           Ejecuta la suite de pruebas (backend y frontend)"
	@echo "  make seed           Crea tenants, usuarios y carga documentos de ejemplo"
	@echo "  make eval           Ejecuta la evaluación de respuestas y citas"
	@echo "  make clean          Limpia artefactos temporales y cachés"

up:
	docker compose up -d --build --wait

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps

psql:
	docker compose exec db psql -U postgres -d pampero

psql-app:
	docker compose exec db psql -U pampero_app -d pampero

redis-cli:
	docker compose exec redis redis-cli

lint-backend:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app

lint-frontend:
	cd frontend && pnpm lint && pnpm typecheck

lint: lint-backend lint-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && pnpm test

test: test-backend test-frontend

# Datos de ejemplo: se ejecutan dentro del worker (mismo parser con OCR y misma base de datos)
TOOLS = docker compose run --rm -e PYTHONPATH=/app -e OTEL_EXPORT_ENABLED=false \
	-v ./scripts:/app/scripts:ro -v ./samples:/app/samples:ro -v ./eval:/app/eval:ro worker

seed:
	$(TOOLS) python scripts/seed.py

eval:
	$(TOOLS) python scripts/eval.py --inprocess $(ARGS)

reset:
	docker compose down -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
