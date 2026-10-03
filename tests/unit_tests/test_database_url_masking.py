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


def test_safe_db_url_masks_credentials_in_embedded_dsn():
    secret = "known-dsn-password"
    url = (
        "postgresql://localhost:5432/app?"
        "dsn=postgresql%3A%2F%2Fuser%3Aknown-dsn-password%40"
        "db.example%3A5432%2Fapp"
    )

    result = database.safe_db_url(url)

    assert secret not in result
    assert "dsn=***" in result


def test_safe_db_url_masks_query_string_password_alongside_userinfo_password():
    secret = "known-password"
    query_secret = "known-query-password"
    ssl_password = "known-ssl-passphrase"
    url = (
        f"postgresql://user:{secret}@localhost:5432/app?"
        f"password={query_secret}&sslpassword={ssl_password}"
    )

    result = database.safe_db_url(url)

    assert secret not in result
    assert query_secret not in result
    assert ssl_password not in result
    assert result == (
        "postgresql://user:***@localhost:5432/app?"
        "password=***&sslpassword=***"
    )


@pytest.mark.parametrize(
    ("query", "secrets"),
    [
        ("sslpassword=known-ssl-passphrase", ("known-ssl-passphrase",)),
        ("SSLPassword=known-ssl-passphrase", ("known-ssl-passphrase",)),
        (
            "%73slpassword=known%2Bssl%2Fpassphrase",
            ("known%2Bssl%2Fpassphrase", "known+ssl/passphrase"),
        ),
        (
            "sslpassword=first-passphrase&SSLPassword=second-passphrase",
            ("first-passphrase", "second-passphrase"),
        ),
        (
            "oauth_client_secret=known-oauth-secret&scram_client_key=known-client-key"
            "&scram_server_key=known-server-key",
            ("known-oauth-secret", "known-client-key", "known-server-key"),
        ),
    ],
)
def test_safe_db_url_masks_secret_query_parameters(query, secrets):
    result = database.safe_db_url(f"postgresql://localhost:5432/app?{query}")

    for secret in secrets:
        assert secret not in result
    assert "***" in result


def test_safe_db_url_masks_secret_query_parameters_with_ambiguous_credentials():
    url = (
        "postgresql://user:p@ssword@localhost:5432/app?"
        "sslpassword=known-ssl-passphrase&application_name=repom"
    )

    result = database.safe_db_url(url)

    assert result == (
        "postgresql://***@localhost:5432/app?"
        "sslpassword=***&application_name=repom"
    )
    assert "known-ssl-passphrase" not in result


def test_safe_db_url_hides_secrets_when_url_is_malformed():
    secret = "known-ssl-passphrase"

    result = database.safe_db_url(
        f"postgresql://[malformed?sslpassword={secret}"
    )

    assert result == "<invalid database URL>"
    assert secret not in result


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
    ssl_password = "known-ssl-passphrase"
    db_url = (
        f"postgresql://user:{password}@localhost:5432/app"
        f"?sslpassword={ssl_password}"
    )
    monkeypatch.setattr(
        database.config,
        "db_url",
        db_url,
    )
    manager = database.DatabaseManager()

    with patch.object(
        database, "create_engine", return_value=Mock()
    ) as mock_create_engine:
        with caplog.at_level("DEBUG", logger=database.logger.name):
            manager.get_sync_engine()

    assert password not in caplog.text
    assert ssl_password not in caplog.text
    assert "postgresql://user:***@localhost:5432/app" in caplog.text
    assert "sslpassword=***" in caplog.text
    assert ssl_password in mock_create_engine.call_args.args[0]


@pytest.mark.asyncio
async def test_async_engine_log_masks_password(caplog, monkeypatch):
    password = "known-password"
    ssl_password = "known-ssl-passphrase"
    db_url = (
        f"postgresql://user:{password}@localhost:5432/app"
        f"?sslpassword={ssl_password}"
    )
    monkeypatch.setattr(
        database.config,
        "db_url",
        db_url,
    )
    manager = database.DatabaseManager()

    with patch.object(
        database, "create_async_engine", return_value=Mock()
    ) as mock_create_async_engine:
        with caplog.at_level("DEBUG", logger=database.logger.name):
            await manager.get_async_engine()

    assert password not in caplog.text
    assert ssl_password not in caplog.text
    assert "postgresql+asyncpg://user:***@localhost:5432/app" in caplog.text
    assert "sslpassword=***" in caplog.text
    assert ssl_password not in mock_create_async_engine.call_args.args[0]
    assert ssl_password in mock_create_async_engine.call_args.kwargs["connect_args"][
        "dsn"
    ]
