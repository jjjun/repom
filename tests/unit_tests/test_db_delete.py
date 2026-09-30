"""Confirmation-guard tests for the db_delete console script (repom#135)."""


import sys
from io import StringIO
from unittest.mock import MagicMock

import pytest

from repom.scripts import db_delete
from repom.scripts._destructive import confirm_destructive_operation


def _mock_config(
    exec_env="dev",
    db_url="sqlite:///data/repom_dev.sqlite3",
    db_type="sqlite",
    db_url_overridden=False,
):
    config = MagicMock()
    config.exec_env = exec_env
    config.db_url = db_url
    config.db_type = db_type
    config.db_url_overridden = db_url_overridden
    return config


def test_db_delete_requires_confirmation(monkeypatch):
    monkeypatch.setattr(db_delete, "config", _mock_config())
    monkeypatch.setattr(sys, "argv", ["db_delete"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    fake_base = MagicMock()
    monkeypatch.setattr(db_delete, "Base", fake_base)
    monkeypatch.setattr(db_delete, "load_models", MagicMock())
    monkeypatch.setattr(db_delete, "get_sync_engine", MagicMock())

    with pytest.raises(SystemExit) as exc_info:
        db_delete.main()

    assert exc_info.value.code != 0
    fake_base.metadata.drop_all.assert_not_called()


@pytest.mark.parametrize("exec_env", ["prod", "production", " Production "])
def test_db_delete_refuses_prod_env(monkeypatch, capsys, exec_env):
    monkeypatch.setattr(db_delete, "config", _mock_config(exec_env=exec_env))
    monkeypatch.setattr(sys, "argv", ["db_delete", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    fake_base = MagicMock()
    monkeypatch.setattr(db_delete, "Base", fake_base)
    monkeypatch.setattr(db_delete, "load_models", MagicMock())
    monkeypatch.setattr(db_delete, "get_sync_engine", MagicMock())

    with pytest.raises(SystemExit) as exc_info:
        db_delete.main()

    assert exc_info.value.code != 0
    fake_base.metadata.drop_all.assert_not_called()
    assert f"EXEC_ENV={exec_env!r} (production)" in capsys.readouterr().out


def test_db_delete_proceeds_with_yes_flag_on_non_tty(monkeypatch):
    monkeypatch.setattr(db_delete, "config", _mock_config())
    monkeypatch.setattr(sys, "argv", ["db_delete", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    fake_base = MagicMock()
    monkeypatch.setattr(db_delete, "Base", fake_base)
    monkeypatch.setattr(db_delete, "load_models", MagicMock())
    fake_engine = MagicMock()
    monkeypatch.setattr(db_delete, "get_sync_engine", MagicMock(return_value=fake_engine))

    db_delete.main()

    fake_base.metadata.drop_all.assert_called_once_with(bind=fake_engine)


def test_db_delete_starts_postgres_before_getting_engine(monkeypatch):
    events = []
    monkeypatch.setattr(db_delete, "config", _mock_config(db_type="postgres"))
    monkeypatch.setattr(sys, "argv", ["db_delete", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    monkeypatch.setattr(db_delete, "load_models", lambda **_kwargs: events.append("models"))

    fake_engine = MagicMock()
    fake_engine.url = "postgresql://localhost/app"
    monkeypatch.setattr(
        db_delete,
        "get_sync_engine",
        lambda: events.append("engine") or fake_engine,
    )
    monkeypatch.setattr(db_delete.Base.metadata, "drop_all", lambda **_kwargs: events.append("drop"))

    from repom.postgres import manage as postgres_manage

    monkeypatch.setattr(postgres_manage, "ensure_running", lambda: events.append("postgres"))

    db_delete.main()

    assert events == ["models", "postgres", "engine", "drop"]


def test_db_delete_does_not_start_managed_postgres_for_url_override(monkeypatch):
    monkeypatch.setattr(
        db_delete,
        "config",
        _mock_config(db_type="postgres", db_url_overridden=True),
    )
    monkeypatch.setattr(sys, "argv", ["db_delete", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    monkeypatch.setattr(db_delete, "load_models", MagicMock())
    monkeypatch.setattr(db_delete, "get_sync_engine", MagicMock())
    monkeypatch.setattr(db_delete.Base.metadata, "drop_all", MagicMock())

    from repom.postgres import manage as postgres_manage

    ensure_running = MagicMock(side_effect=AssertionError("managed container must not start"))
    monkeypatch.setattr(postgres_manage, "ensure_running", ensure_running)

    db_delete.main()

    ensure_running.assert_not_called()


@pytest.mark.parametrize("answer", ["y", "Y"])
def test_destructive_guard_accepts_tty_confirmation(monkeypatch, answer):
    stdin = MagicMock()
    stdin.isatty.return_value = True
    monkeypatch.setattr("builtins.input", lambda _prompt: answer)

    result = confirm_destructive_operation(
        operation="drop tables",
        target="sqlite:///:memory:",
        exec_env="dev",
        yes=False,
        stdin=stdin,
    )

    assert result is None


@pytest.mark.parametrize("answer", ["", "n", "yes"])
def test_destructive_guard_cancels_without_exact_tty_confirmation(monkeypatch, answer):
    stdin = MagicMock()
    stdin.isatty.return_value = True
    monkeypatch.setattr("builtins.input", lambda _prompt: answer)

    with pytest.raises(SystemExit) as exc_info:
        confirm_destructive_operation(
            operation="drop tables",
            target="sqlite:///:memory:",
            exec_env="dev",
            yes=True,
            stdin=stdin,
        )

    assert exc_info.value.code == 1
