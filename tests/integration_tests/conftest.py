"""Integration tests configuration - PostgreSQL specific"""
import pytest
import os


# 統合テスト用の設定
# 親の conftest.py が EXEC_ENV='test' を設定しているため、そのまま使用
# PostgreSQL 統合テストは repom_test データベースに接続する

# Note: setup_postgres_tables fixture は親の conftest.py で定義されています。
# このファイルでは PostgreSQL 固有の設定のみを記述します。
