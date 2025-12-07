# Cronos x402 Paytech - Backend

**AI-Powered Multi-Agent Backend for Cronos DeFi**

FastAPI backend orchestrating 9 specialized AI agents using LangGraph, A2A Protocol, and AG-UI Protocol.

## Setup

### Prerequisites

- Python 3.11 or higher
- pip or uv

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```

4. Update `.env` with your configuration values.

### Running the Server

#### Local Development

Development server with auto-reload:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the Makefile:
```bash
make dev
```

#### Docker Development

Build and run with Docker:
```bash
docker build -t movement-backend .
docker run -p 8000:8000 --env-file .env movement-backend
```

Or use Docker Compose (recommended):
```bash
docker-compose up --build
```

To run in detached mode:
```bash
docker-compose up -d
```

To view logs:
```bash
docker-compose logs -f
```

To stop:
```bash
docker-compose down
```

### API Documentation

Once the server is running, access the interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

### Code Formatting

#### Local Formatting

Format code with Black:
```bash
make format
```

#### Docker Formatting

Format code in Docker:
```bash
make docker-format
```

Or directly:
```bash
docker-compose --profile format run --rm format
```

### Linting

#### Local Linting

Lint code with Ruff:
```bash
make lint
```

#### Docker Linting

Lint code in Docker:
```bash
make docker-lint
```

Or directly:
```bash
docker-compose --profile lint run --rm lint
```

### Testing

#### Local Testing

Run tests:
```bash
make test
```

#### Docker Testing

Run tests in Docker:
```bash
make docker-test
```

Or directly:
```bash
docker-compose --profile test run --rm test
```

Run tests with coverage:
```bash
make docker-test-coverage
```

Or directly:
```bash
docker-compose --profile test run --rm test pytest --cov=app --cov-report=html --cov-report=term
```

The coverage report will be generated in `htmlcov/` directory.

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       └── router.py
│   ├── core/
│   │   └── config.py
│   └── main.py
├── tests/
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

