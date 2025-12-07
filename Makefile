.PHONY: format-frontend format-backend format lint-frontend lint-backend lint test-frontend test-backend test \
	backend-install backend-dev backend-format backend-lint backend-test backend-clean \
	docker-build docker-up docker-up-detached docker-down docker-logs docker-shell \
	docker-test docker-test-coverage docker-format docker-lint help

# ============================================================================
# Frontend Commands
# ============================================================================

# Format frontend code using Prettier
format-frontend:
	@echo "Formatting frontend code..."
	cd frontend && npm run format

# Lint frontend code (placeholder - add ESLint if needed)
lint-frontend:
	@echo "Linting frontend code..."
	@echo "Frontend linting not configured yet"

# Test frontend code (placeholder - add tests if needed)
test-frontend:
	@echo "Testing frontend code..."
	@echo "Frontend tests not configured yet"

# Format both frontend and backend
format: format-frontend format-backend
	@echo "Formatting complete!"

# ============================================================================
# Backend Commands (Local)
# ============================================================================

# Install backend dependencies
backend-install:
	@echo "Installing backend dependencies..."
	cd backend && pip install -e ".[dev]"

# Run backend development server
backend-dev:
	@echo "Starting backend development server..."
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Format backend code with Black
format-backend:
	@echo "Formatting backend code..."
	cd backend && black app tests

# Lint backend code with Ruff
lint-backend:
	@echo "Linting backend code..."
	cd backend && ruff check app tests

# Lint both frontend and backend
lint: lint-frontend lint-backend
	@echo "Linting complete!"

# Run backend tests
test-backend:
	@echo "Running backend tests..."
	cd backend && pytest

# Test both frontend and backend
test: test-frontend test-backend
	@echo "Testing complete!"

# Clean backend Python cache files
backend-clean:
	@echo "Cleaning backend Python cache files..."
	cd backend && find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	cd backend && find . -type f -name "*.pyc" -delete
	cd backend && find . -type f -name "*.pyo" -delete
	cd backend && find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	cd backend && find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true

# ============================================================================
# Docker Commands (Backend)
# ============================================================================

# Build Docker image
docker-build:
	@echo "Building Docker image..."
	cd backend && docker build -t cronos-x402-backend .

# Start Docker containers
docker-up:
	@echo "Starting Docker containers..."
	@if [ ! -f backend/.env ]; then \
		echo "Creating backend/.env file from backend/.env.example..."; \
		cp backend/.env.example backend/.env 2>/dev/null || echo "Warning: backend/.env.example not found, using defaults"; \
	fi
	cd backend && docker compose up --build

# Start Docker containers in detached mode
docker-up-detached:
	@echo "Starting Docker containers in detached mode..."
	cd backend && docker compose up -d --build

# Stop Docker containers
docker-down:
	@echo "Stopping Docker containers..."
	cd backend && docker compose down

# Show Docker logs
docker-logs:
	@echo "Showing Docker logs..."
	cd backend && docker compose logs -f

# Open shell in Docker container
docker-shell:
	@echo "Opening shell in Docker container..."
	cd backend && docker compose exec backend /bin/bash

# Run tests in Docker
docker-test:
	@echo "Running tests in Docker..."
	cd backend && docker compose --profile test run --rm test

# Run tests with coverage in Docker
docker-test-coverage:
	@echo "Running tests with coverage in Docker..."
	cd backend && docker compose --profile test run --rm test pytest --cov=app --cov-report=html --cov-report=term

# Format code in Docker
docker-format:
	@echo "Formatting code in Docker..."
	cd backend && docker compose --profile format run --rm format

# Lint code in Docker
docker-lint:
	@echo "Linting code in Docker..."
	cd backend && docker compose --profile lint run --rm lint

# ============================================================================
# Help
# ============================================================================

help:
	@echo "Available targets:"
	@echo ""
	@echo "Frontend commands:"
	@echo "  make format-frontend  - Format frontend code using Prettier"
	@echo ""
	@echo "Backend commands (local):"
	@echo "  make backend-install  - Install backend dependencies"
	@echo "  make backend-dev     - Run backend development server"
	@echo "  make format-backend   - Format backend code with Black"
	@echo "  make lint-backend     - Lint backend code with Ruff"
	@echo "  make test-backend     - Run backend tests"
	@echo "  make backend-clean    - Clean backend Python cache files"
	@echo ""
	@echo "Combined commands:"
	@echo "  make format           - Format both frontend and backend"
	@echo "  make lint             - Lint both frontend and backend"
	@echo "  make test             - Test both frontend and backend"
	@echo ""
	@echo "Docker commands (backend):"
	@echo "  make docker-build     - Build Docker image"
	@echo "  make docker-up        - Start Docker containers"
	@echo "  make docker-up-detached - Start Docker containers in detached mode"
	@echo "  make docker-down      - Stop Docker containers"
	@echo "  make docker-logs      - Show Docker logs"
	@echo "  make docker-shell     - Open shell in Docker container"
	@echo ""
	@echo "Docker test commands:"
	@echo "  make docker-test      - Run tests in Docker"
	@echo "  make docker-test-coverage - Run tests with coverage in Docker"
	@echo ""
	@echo "Docker format/lint commands:"
	@echo "  make docker-format    - Format code with Black in Docker"
	@echo "  make docker-lint      - Lint code with Ruff in Docker"
	@echo ""
	@echo "  make help             - Show this help message"

