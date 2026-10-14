"""Tests for api/routes/health.py"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from structlog.testing import capture_logs

from api.routes.health import health_check


async def _health_body(db):
    """Return the health payload, whether the route returns it or raises 503.

    The route still returns 503 because of the Redis bug (#62), so the
    payload is read from HTTPException.detail in that case.
    """
    try:
        return await health_check(db=db)
    except HTTPException as exc:
        return exc.detail


@pytest.mark.unit
class TestHealthCheck:
    """Test suite for the health check route."""

    @pytest.mark.asyncio
    async def test_postgres_healthy_when_session_runs_the_probe(self):
        """Test postgres is healthy when a real SQLAlchemy session runs the probe."""
        # A real Session on in-memory SQLite (stdlib sqlite3, no new dependency).
        # Session.execute rejects a plain SQL string, like AsyncSession.execute.
        session = Session(create_engine("sqlite://"))
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=session.execute)

        with capture_logs() as logs:
            body = await _health_body(db)
        session.close()

        failures = [entry for entry in logs if entry["event"] == "postgres_health_check_failed"]
        assert failures == []
        assert body["dependencies"]["postgres"] == "healthy"

    @pytest.mark.asyncio
    async def test_postgres_unhealthy_when_database_call_fails(self):
        """Test postgres is unhealthy when the database call raises."""
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=OSError("connection refused"))

        body = await _health_body(db)

        assert body["dependencies"]["postgres"] == "unhealthy"
