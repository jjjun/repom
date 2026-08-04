import logging
from pathlib import Path

import pytest

from repom.config import RepomConfig
from repom.logging import get_logger


@pytest.fixture(autouse=True)
def reset_logging_state():
    import repom.logging as logging_module

    repom_root_logger = logging.getLogger("repom")
    root_logger = logging.getLogger()
    original_root_handlers = list(root_logger.handlers)
    logging_module._logger_initialized = False
    logging_module._sqlalchemy_logging_initialized = False

    for handler in original_root_handlers:
        root_logger.removeHandler(handler)
    for handler in repom_root_logger.handlers[:]:
        handler.close()
        repom_root_logger.removeHandler(handler)

    yield

    logging_module._logger_initialized = False
    logging_module._sqlalchemy_logging_initialized = False
    for handler in repom_root_logger.handlers[:]:
        handler.close()
        repom_root_logger.removeHandler(handler)
    for handler in root_logger.handlers[:]:
        if handler not in original_root_handlers:
            handler.close()
            root_logger.removeHandler(handler)
    for handler in original_root_handlers:
        if handler not in root_logger.handlers:
            root_logger.addHandler(handler)


def test_prod_logging_uses_info_level_for_file_handler(tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    config = RepomConfig(exec_env="prod")
    config.log_path = str(tmp_path)
    config.log_file = "prod"
    monkeypatch.setattr("repom.config.config", config)

    logger = get_logger("prod_level")
    logger.debug("debug message")
    logger.info("info message")

    file_handler = next(
        handler
        for handler in logging.getLogger("repom").handlers
        if isinstance(handler, logging.FileHandler)
    )
    file_handler.flush()

    assert file_handler.level == logging.INFO
    content = Path(file_handler.baseFilename).read_text(encoding="utf-8")
    assert "debug message" not in content
    assert "info message" in content


def test_non_prod_logging_keeps_debug_file_level(tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    config = RepomConfig(exec_env="dev")
    config.log_path = str(tmp_path)
    config.log_file = "dev"
    monkeypatch.setattr("repom.config.config", config)

    logger = get_logger("dev_level")
    logger.debug("debug message")

    file_handler = next(
        handler
        for handler in logging.getLogger("repom").handlers
        if isinstance(handler, logging.FileHandler)
    )
    console_handler = next(
        handler
        for handler in logging.getLogger("repom").handlers
        if isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
    )
    file_handler.flush()

    assert file_handler.level == logging.DEBUG
    assert console_handler.level == logging.INFO
    assert "debug message" in Path(file_handler.baseFilename).read_text(encoding="utf-8")
