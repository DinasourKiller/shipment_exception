# Shipment Exception Control Tower

Enterprise-Grade Shipment Exception Management Platform built with FastAPI, PostgreSQL, Mendix enterprise integration, and Ollama AI runtime.

## Project Overview

The Shipment Exception Control Tower is an operational platform designed to ingest shipment information from external systems (ERP, TMS, Mendix), monitor transit milestones, detect exceptions (delays, breakdowns, route deviations, road closures), assess business impact and SLA risk, and coordinate multi-party recovery workflows (Re-route, Alternate Carrier, Expedite, Split).

## Approved Technology Stack

- **Architecture:** Modular Monolith
- **Backend Framework:** FastAPI (Python 3.12+)
- **Database:** PostgreSQL (SQLAlchemy 2.x ORM, Alembic migrations)
- **Authentication:** JWT (RS256/ES256), Refresh Token Rotation, Argon2id password hashing
- **Integration Layer:** Dedicated adapter modules (initial: Mendix REST API)
- **AI Runtime:** Ollama (Provider-based architecture, Pydantic structured output)
- **Testing:** Pytest (Unit, Integration, Security, E2E)
- **Containerization:** Docker & Docker Compose

## Quick Start (Development)

### 1. Prerequisites
- Python 3.12+
- PostgreSQL 16+ (or Docker)
- Docker & Docker Compose (optional for local containerized development)

### 2. Environment Setup
```bash
# Clone or navigate to the repository
cd d:\AShipmentExceptionProject

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Create .env from template
cp .env.example .env
```

### 3. Running the Server Locally
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Running via Docker Compose
```bash
docker-compose up --build
```

### 5. Running Tests
```bash
pytest tests/ -v
```

## API Documentation
Once running, interactive documentation is available at:
- Swagger UI: `http://localhost:8000/api/v1/docs`
- ReDoc: `http://localhost:8000/api/v1/redoc`
- OpenAPI Specification: `http://localhost:8000/api/v1/openapi.json`
