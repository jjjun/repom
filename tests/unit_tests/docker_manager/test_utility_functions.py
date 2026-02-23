"""Tests for utility functions"""

from pathlib import Path

import pytest

from repom._.docker_manager import (
    format_connection_info,
    print_message,
    validate_compose_file_exists,
)


class TestPrintMessage:
    """print_message() テスト"""

    def test_print_message_simple(self, capsys):
        """シンプルなメッセージ表示"""
        print_message("✅", "Test message")
        captured = capsys.readouterr()
        assert "✅ Test message" in captured.out

    def test_print_message_with_details(self, capsys):
        """詳細情報付きメッセージ"""
        print_message("ℹ️", "Connection info", ["Host: localhost", "Port: 5432"])
        captured = capsys.readouterr()
        assert "ℹ️ Connection info" in captured.out
        assert "  Host: localhost" in captured.out
        assert "  Port: 5432" in captured.out


class TestValidateComposeFileExists:
    """validate_compose_file_exists() テスト"""

    def test_file_exists(self, tmp_path):
        """ファイルが存在する場合"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\n")
        # エラーが発生しないことを確認
        validate_compose_file_exists(compose_file, "PostgreSQL")

    def test_file_not_exists(self, tmp_path, capsys):
        """ファイルが見つからない場合"""
        compose_file = tmp_path / "docker-compose.yml"
        with pytest.raises(FileNotFoundError):
            validate_compose_file_exists(compose_file, "PostgreSQL")
        captured = capsys.readouterr()
        assert "docker-compose.generated.yml が見つかりません" in captured.out
        assert "poetry run postgresql_generate" in captured.out


class TestFormatConnectionInfo:
    """format_connection_info() テスト"""

    def test_single_item(self):
        """単一項目"""
        result = format_connection_info(Host="localhost")
        assert result == ["Host: localhost"]

    def test_multiple_items(self):
        """複数項目"""
        result = format_connection_info(
            Host="localhost", Port=5432, User="postgres", Database="mydb"
        )
        assert "Host: localhost" in result
        assert "Port: 5432" in result
        assert "User: postgres" in result
        assert "Database: mydb" in result

    def test_empty_kwargs(self):
        """空の kwargs"""
        result = format_connection_info()
        assert result == []
