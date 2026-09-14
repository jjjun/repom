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


@pytest.mark.parametrize("query_param", ["password", "pgpassword"])
def test_safe_db_url_masks_query_string_password(query_param):
    secret = "known-password"
    url = f"postgresql://localhost:5432/app?{query_param}={secret}"

    result = database.safe_db_url(url)

    assert secret not in result
    assert f"{query_param}=***" in result


def test_safe_db_url_masks_query_string_password_alongside_userinfo_password():
    secret = "known-password"
    query_secret = "known-query-password"
    url = f"postgresql://user:{secret}@localhost:5432/app?password={query_secret}"

    result = database.safe_db_url(url)

    assert secret not in result
    assert query_secret not in result
    assert result == "postgresql://user:***@localhost:5432/app?password=***"


def test_safe_db_url_leaves_unrelated_query_params_untouched():
    url = "postgresql://user@localhost:5432/app?sslmode=require"

    result = database.safe_db_url(url)

    assert result == "postgresql://user@localhost:5432/app?sslmode=require"


def test_convert_to_async_uri_error_masks_password():
    secret = "known-password"
    url = f"oracle://user:{secret}@localhost:5432/app"

    with pytest.raises(ValueError) as excinfo:
        database.convert_to_async_uri(url)

    assert secret not in str(excinfo.value)
    assert "***" in str(excinfo.value)


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
