.DEFAULT_GOAL := help
SHELL := /bin/bash

BACKEND := backend
FRONTEND := frontend

.PHONY: help setup setup-backend setup-frontend dev dev-backend dev-frontend \
	contracts openapi seed test test-backend test-frontend lint lint-backend \
	lint-frontend format up down

## help: lista los objetivos disponibles
help:
	@echo "Sommelier de juegos de mesa"

## setup: instala dependencias de backend y frontend
setup: setup-backend setup-frontend

setup-backend:
	cd $(BACKEND) && uv sync --extra dev

setup-frontend:
	cd $(FRONTEND) && npm install --force

## dev: inicia backend y frontend en paralelo
dev:
	@$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd $(BACKEND) && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd $(FRONTEND) && npm start

## openapi: genera el contrato OpenAPI del backend
openapi:
	cd $(BACKEND) && uv run python scripts/dump_openapi.py ../$(FRONTEND)/openapi.json

## contracts: genera los tipos TypeScript del contrato OpenAPI
contracts: openapi
	cd $(FRONTEND) && npx openapi-typescript openapi.json -o src/app/core/api/schema.d.ts

## seed: crea las tablas y siembra catalogo, usuario y coleccion demo
seed:
	cd $(BACKEND) && uv run python -m app.db.seed

## test: ejecuta las pruebas sin red
test: test-backend test-frontend

test-backend:
	cd $(BACKEND) && uv run pytest

test-frontend:
	cd $(FRONTEND) && npm test -- --watch=false

## lint: valida formato y tipos
lint: lint-backend lint-frontend

lint-backend:
	cd $(BACKEND) && uv run ruff check app tests scripts
	cd $(BACKEND) && uv run ruff format --check app tests scripts
	cd $(BACKEND) && uv run mypy app

lint-frontend:
	cd $(FRONTEND) && npx tsc --noEmit -p tsconfig.app.json

## format: aplica formato a los archivos del proyecto
format:
	cd $(BACKEND) && uv run ruff format app tests scripts
	cd $(BACKEND) && uv run ruff check --fix app tests scripts
	cd $(FRONTEND) && npx prettier --write "src/**/*.{ts,html,css}"

## up: construye e inicia los servicios Docker
up:
	docker compose up --build

## down: detiene los servicios Docker
down:
	docker compose down
