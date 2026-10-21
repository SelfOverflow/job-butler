.PHONY: help test lint format dev up down build clean

help:
	@echo "Job Butler - Developer & Agent Command Center"
	@echo "---------------------------------------------"
	@echo "make test         Run Python pytest & Frontend tests (TDD)"
	@echo "make lint         Run ruff and mypy static type checking"
	@echo "make format       Format code with ruff"
	@echo "make dev-backend  Run FastAPI backend locally"
	@echo "make dev-frontend Run Next.js frontend locally"
	@echo "make dev          Run both backend and frontend concurrently"
	@echo "make up           Start full stack in Docker Compose"
	@echo "make down         Stop Docker Compose containers"
	@echo "make build        Build Docker images"
	@echo "make clean        Remove cache and temporary files"

test:
	pytest tests/unit tests/integration -v --cov=src
	@if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then \
		cd frontend && npm test; \
	fi

lint:
	ruff check src tests
	mypy --strict src

format:
	ruff format src tests

dev-backend:
	uvicorn src.server.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	@if [ -d "frontend" ]; then \
		cd frontend && npm run dev; \
	fi

dev:
	@echo "Starting backend on :8000 and frontend on :3000..."
	@make -j 2 dev-backend dev-frontend

up:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov

