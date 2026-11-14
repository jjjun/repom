"""Tests for safe database URL display and logging."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.engine import make_url

from repom import database


def _url_parts(url):
    parsed = make_url(url)
    return (
        parsed.drivername,
        parsed.username,
        parsed.password,
        parsed.host,
        parsed.port,
        parsed.database,
        dict(parsed.query),
    )


def assert_same_url(result, expected):
    """Compare parsed URL parts instead of the rendered text.

    SQLAlchemy 2.1 percent-encodes the database name when it renders a URL
    (``#`` as ``%23``, ``:memory:`` as ``%3Amemory%3A``) where 2.0 prints it
    unchanged. Both read back as the same database, so the masked userinfo
    password and query values are still checked exactly.
    """
    assert _url_parts(result) == _url_parts(expected)


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
    assert_same_url(database.safe_db_url(url), expected)


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


_SECRET_KEYS = sorted(database._SECRET_QUERY_PARAM_NAMES)

# make_url() keeps '#' in the host or database name and parses what follows the
# first '?' as query parameters, so a secret key after '#' is still a real one.
_HASH_URL_TEMPLATES = [
    pytest.param(
        "{driver}://app:pw@h/my#db?{key}=known-secret",
        "{driver}://app:***@h/my#db?{key}=***",
        id="in-database-name",
    ),
    pytest.param(
        "{driver}://app:pw@h/db#frag?{key}=known-secret",
        "{driver}://app:***@h/db#frag?{key}=***",
        id="before-query",
    ),
    pytest.param(
        "{driver}://app:pw@h#x/db?{key}=known-secret",
        "{driver}://app:***@h#x/db?{key}=***",
        id="in-host",
    ),
]


@pytest.mark.parametrize("key", _SECRET_KEYS)
@pytest.mark.parametrize("driver", ["postgresql", "postgresql+psycopg2", "postgresql+asyncpg"])
@pytest.mark.parametrize(("template", "expected"), _HASH_URL_TEMPLATES)
def test_safe_db_url_masks_secret_query_after_hash_in_postgresql_url(
    template, expected, driver, key
):
    result = database.safe_db_url(template.format(driver=driver, key=key))

    assert "known-secret" not in result
    assert_same_url(result, expected.format(driver=driver, key=key))


@pytest.mark.parametrize("key", _SECRET_KEYS)
@pytest.mark.parametrize("driver", ["sqlite", "sqlite+aiosqlite"])
def test_safe_db_url_masks_secret_query_after_hash_in_sqlite_url(driver, key):
    url = f"{driver}:///data#v1.sqlite3?{key}=known-secret"

    result = database.safe_db_url(url)

    assert "known-secret" not in result
    assert_same_url(result, f"{driver}:///data#v1.sqlite3?{key}=***")


@pytest.mark.parametrize(
    ("query", "expected_query"),
    [
        ("SSLPassword=known-secret", "SSLPassword=***"),
        ("%73slpassword=known-secret", "sslpassword=***"),
        (
            "application_name=repom&password=known-secret&dsn=known-dsn",
            "application_name=repom&dsn=***&password=***",
        ),
    ],
)
def test_safe_db_url_masks_secret_query_variants_after_hash(query, expected_query):
    result = database.safe_db_url(f"postgresql://app:pw@h/my#db?{query}")

    assert "known-secret" not in result
    assert "known-dsn" not in result
    assert_same_url(result, f"postgresql://app:***@h/my#db?{expected_query}")


def test_safe_db_url_masks_secret_query_in_hostless_url():
    result = database.safe_db_url("postgresql:///db?password=known-secret")

    assert result == "postgresql:///db?password=***"


def test_safe_db_url_masks_hash_url_with_ambiguous_credentials():
    url = "postgresql://user:p@known-userinfo@h/db#frag?password=known-secret"

    result = database.safe_db_url(url)

    assert result == "postgresql://***@h/db#frag?password=***"
    assert "known-secret" not in result
    assert "known-userinfo" not in result


def test_safe_db_url_keeps_hash_in_names_without_secret_query():
    url = "postgresql://app:pw@h#x/my#db?sslmode=require"

    assert_same_url(
        database.safe_db_url(url), "postgresql://app:***@h#x/my#db?sslmode=require"
    )


def test_convert_to_async_uri_error_masks_secret_query_after_hash():
    url = "oracle://user:pw@localhost:5432/app#v1?password=known-secret"

    with pytest.raises(ValueError) as excinfo:
        database.convert_to_async_uri(url)

    message = str(excinfo.value)
    assert "known-secret" not in message
    # SQLAlchemy 2.1 renders the '#' in the database name as '%23'.
    assert "app#v1?password=***" in message or "app%23v1?password=***" in message


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
