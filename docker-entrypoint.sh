#!/bin/sh
set -e

echo "[CONTROL TOWER] Starting Enterprise Shipment Exception Control Tower..."

# Run database migrations
echo "[CONTROL TOWER] Executing database schema migrations (Alembic)..."
python -m alembic upgrade head || {
    echo "[CONTROL TOWER] Migration failed or database not ready. Retrying in 3 seconds..."
    sleep 3
    python -m alembic upgrade head
}

echo "[CONTROL TOWER] Migrations complete. Launching application server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WORKERS:-2}"
