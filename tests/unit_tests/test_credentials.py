from io import StringIO
import os
from unittest.mock import MagicMock, patch

import pytest

from repom.credentials import (
    DEFAULT_CREDENTIAL_PLACEHOLDER,
    mask_secret,
    reject_default_credential,
    resolve_password,
    run_masked_command,
    secret_env_file,
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


def test_mask_secret_masks_every_non_empty_secret():
    result = mask_secret("old=old-secret new=new-secret", ("old-secret", "new-secret"))

    assert result == "old=*** new=***"


def test_mask_secret_ignores_falsy_secrets():
    result = mask_secret("value=new-secret", (None, "", "new-secret"))

    assert result == "value=***"


def test_secret_env_file_yields_none_for_a_falsy_secret():
    with secret_env_file("PGPASSWORD", None) as path:
        assert path is None


def test_secret_env_file_writes_a_0600_file_and_removes_it_afterward():
    with secret_env_file("PGPASSWORD", "sentinel-secret", prefix="repom-test-") as path:
        assert path is not None
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as handle:
            assert handle.read() == "PGPASSWORD=sentinel-secret\n"

    assert not os.path.exists(path)


def test_run_masked_command_returns_completed_process_on_success():
    runner = MagicMock(return_value=MagicMock(returncode=0, stdout="ok", stderr=""))

    completed = run_masked_command(
        ("echo", "hi"),
        runner=runner,
        secrets=("sentinel-secret",),
        error_type=RuntimeError,
        action="test command",
    )

    assert completed.returncode == 0
    kwargs = runner.call_args.kwargs
    assert kwargs["check"] is False
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert "input" not in kwargs


def test_run_masked_command_raises_masked_error_type_on_failure():
    runner = MagicMock(
        return_value=MagicMock(
            returncode=1,
            stdout="",
            stderr="failed with sentinel-secret",
        )
    )

    class SentinelError(RuntimeError):
        pass

    with pytest.raises(SentinelError) as excinfo:
        run_masked_command(
            ("echo", "hi"),
            runner=runner,
            secrets=("sentinel-secret",),
            error_type=SentinelError,
            action="test command",
            input="payload",
        )

    assert "sentinel-secret" not in str(excinfo.value)
    assert "***" in str(excinfo.value)
    assert runner.call_args.kwargs["input"] == "payload"
