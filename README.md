# Network Route Optimization API

Backend service built with FastAPI and SQLite (SQLAlchemy) to manage network nodes/edges and compute the lowest-latency route using Dijkstra's algorithm.

## Tech Stack
- **Python 3.12+**
- **FastAPI & Uvicorn**
- **SQLAlchemy (SQLite)**
- **Pytest & HTTPX** (for API test suite)

## Setup & Running Locally

### Option 1: Using `uv` (Recommended)
```bash
# Install dependencies (including dev group)
uv sync

# Run the server
uv run uvicorn main:app --reload
```

### Please reach http://127.0.0.1:8000/docs for the whole API suite
