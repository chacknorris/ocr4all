.PHONY: help dev prod down logs test lint build clean

# Default target
help:
	@echo "OCR4All - Document Processing Pipeline"
	@echo ""
	@echo "Development:"
	@echo "  make dev          Start development environment"
	@echo "  make dev-api      Start only API server"
	@echo "  make dev-worker   Start only Celery worker"
	@echo "  make dev-web      Start only frontend"
	@echo ""
	@echo "Production:"
	@echo "  make prod         Start production environment"
	@echo "  make build        Build production images"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate   Run database migrations"
	@echo "  make db-seed      Seed default data"
	@echo ""
	@echo "Utilities:"
	@echo "  make logs         Show logs"
	@echo "  make down         Stop all services"
	@echo "  make clean        Remove all containers and volumes"
	@echo "  make test         Run tests"
	@echo "  make lint         Run linters"

# Development
dev:
	docker-compose up -d db redis minio
	@echo "Waiting for services..."
	@sleep 3
	@echo "Infrastructure ready. Run in separate terminals:"
	@echo "  make dev-api"
	@echo "  make dev-worker"
	@echo "  make dev-web"

dev-api:
	PYTHONPATH=. uvicorn api.main:app --reload --port 8000

dev-worker:
	PYTHONPATH=. celery -A workers.celery_app worker -l info -Q ocr,extract

dev-web:
	cd web && bun dev

# Production
prod:
	docker-compose -f docker-compose.prod.yml up -d

build:
	docker-compose -f docker-compose.prod.yml build

# Database
db-migrate:
	PYTHONPATH=. alembic upgrade head

db-seed:
	@echo "Seeding default templates..."
	curl -X POST http://localhost:8000/api/v1/templates/seed-defaults
	@echo ""
	@echo "Seeding default categories..."
	curl -X POST http://localhost:8000/api/v1/categories/seed-defaults
	@echo ""

# Utilities
logs:
	docker-compose logs -f

logs-prod:
	docker-compose -f docker-compose.prod.yml logs -f

down:
	docker-compose down
	docker-compose -f docker-compose.prod.yml down 2>/dev/null || true

clean:
	docker-compose down -v --remove-orphans
	docker-compose -f docker-compose.prod.yml down -v --remove-orphans 2>/dev/null || true
	rm -rf storage/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

test:
	PYTHONPATH=. pytest tests/ -v

lint:
	ruff check .
	cd web && bun run lint

# Scale workers
scale-ocr:
	docker-compose -f docker-compose.prod.yml up -d --scale worker-ocr=4

scale-extract:
	docker-compose -f docker-compose.prod.yml up -d --scale worker-extract=2
