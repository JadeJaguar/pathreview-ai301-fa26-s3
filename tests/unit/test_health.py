"""Tests for api/routes/health.py"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.sql import coercions, roles

from api.routes.health import health_check


def _coerce_like_sqlalchemy(statement, *args, **kwargs):
    """Run the statement check AsyncSession.execute runs first.

    Raises ArgumentError for a plain string and accepts text().
    """
    return coercions.expect(roles.StatementRole, statement)


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
    async def test_postgres_healthy_when_session_accepts_the_probe(self):
        """Test postgres is healthy when the probe passes SQLAlchemy's statement check."""
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=_coerce_like_sqlalchemy)

        body = await _health_body(db)

        assert body["dependencies"]["postgres"] == "healthy"

    @pytest.mark.asyncio
    async def test_postgres_unhealthy_when_database_call_fails(self):
        """Test postgres is unhealthy when the database call raises."""
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=OSError("connection refused"))

        body = await _health_body(db)

        assert body["dependencies"]["postgres"] == "unhealthy"
