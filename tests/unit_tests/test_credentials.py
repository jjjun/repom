from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from repom.credentials import (
    DEFAULT_CREDENTIAL_PLACEHOLDER,
    reject_default_credential,
    resolve_password,
)


def test_resolve_password_prefers_explicit_password():
    password = resolve_password(
        password="argument-password",
        read_stdin=True,
        allow_config_password=True,
        config_password="configured-password",
        prompt="Password: ",
        option_name="--password",
        stdin=StringIO("stdin-password\n"),
    )

    assert password == "argument-password"


def test_resolve_password_prefers_stdin_over_config_password():
    password = resolve_password(
        password=None,
        read_stdin=True,
        allow_config_password=True,
        config_password="configured-password",
        prompt="Password: ",
        option_name="--password",
        stdin=StringIO("stdin-password\n"),
    )

    assert password == "stdin-password"


def test_resolve_password_uses_config_password_before_tty_prompt():
    stdin = MagicMock()
    stdin.isatty.return_value = True

    with patch("repom.credentials.getpass.getpass") as prompt:
        password = resolve_password(
            password=None,
            read_stdin=False,
            allow_config_password=True,
            config_password="configured-password",
            prompt="Password: ",
            option_name="--password",
            stdin=stdin,
        )

    assert password == "configured-password"
    prompt.assert_not_called()


@pytest.mark.parametrize(
    ("password", "read_stdin", "allow_config_password", "config_password", "stdin"),
    [
        ("", False, False, None, StringIO()),
        (None, True, False, None, StringIO("\n")),
        (None, False, True, "", StringIO()),
    ],
)
def test_resolve_password_rejects_empty_passwords(
    password,
    read_stdin,
    allow_config_password,
    config_password,
    stdin,
):
    with pytest.raises(ValueError, match="--password must not be empty"):
        resolve_password(
            password=password,
            read_stdin=read_stdin,
            allow_config_password=allow_config_password,
            config_password=config_password,
            prompt="Password: ",
            option_name="--password",
            stdin=stdin,
        )


def test_resolve_password_rejects_empty_tty_password():
    stdin = MagicMock()
    stdin.isatty.return_value = True

    with patch("repom.credentials.getpass.getpass", return_value=""):
        with pytest.raises(ValueError, match="--password must not be empty"):
            resolve_password(
                password=None,
                read_stdin=False,
                prompt="Password: ",
                option_name="--password",
                stdin=stdin,
            )


def test_reject_default_credential_rejects_the_placeholder():
    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        reject_default_credential(DEFAULT_CREDENTIAL_PLACEHOLDER, env_var="POSTGRES_PASSWORD")


def test_reject_default_credential_rejects_empty_string():
    with pytest.raises(ValueError, match="REDIS_PASSWORD"):
        reject_default_credential("", env_var="REDIS_PASSWORD")


def test_reject_default_credential_rejects_none():
    with pytest.raises(ValueError, match="REDIS_PASSWORD"):
        reject_default_credential(None, env_var="REDIS_PASSWORD")


def test_reject_default_credential_accepts_a_real_value():
    assert reject_default_credential("s3cret", env_var="POSTGRES_PASSWORD") == "s3cret"
