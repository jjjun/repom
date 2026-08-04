"""Tests for safe database URL display and logging."""

from unittest.mock import Mock, patch

import pytest

from repom import database


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite:///:memory:", "sqlite:///:memory:"),
        (
            "postgresql://user@localhost:5432/app",
            "postgresql://user@localhost:5432/app",
        ),
    ],
)
def test_safe_db_url_handles_urls_without_password(url, expected):
    assert database.safe_db_url(url) == expected


def test_safe_db_url_handles_malformed_values():
    secret = "known-password"
    assert database.safe_db_url(f"://{secret}") == "<invalid database URL>"


def test_safe_db_url_masks_ambiguous_credentials():
    url = "postgresql://user:p@ssw0rd@localhost:5432/app"

    result = database.safe_db_url(url)

    assert result == "postgresql://***@localhost:5432/app"
    assert "p@ssw0rd" not in result
    assert "ssw0rd" not in result


def test_sync_engine_log_masks_password(caplog, monkeypatch):
    password = "known-password"
    monkeypatch.setattr(
        database.config,
        "db_url",
        f"postgresql://user:{password}@localhost:5432/app",
    )
    manager = database.DatabaseManager()

    with patch.object(database, "create_engine", return_value=Mock()):
        with caplog.at_level("DEBUG", logger=database.logger.name):
            manager.get_sync_engine()

    assert password not in caplog.text
    assert "postgresql://user:***@localhost:5432/app" in caplog.text


@pytest.mark.asyncio
async def test_async_engine_log_masks_password(caplog, monkeypatch):
    password = "known-password"
    monkeypatch.setattr(
        database.config,
        "db_url",
        f"postgresql://user:{password}@localhost:5432/app",
    )
    manager = database.DatabaseManager()

    with patch.object(database, "create_async_engine", return_value=Mock()):
        with caplog.at_level("DEBUG", logger=database.logger.name):
            await manager.get_async_engine()

    assert password not in caplog.text
    assert "postgresql+asyncpg://user:***@localhost:5432/app" in caplog.text
