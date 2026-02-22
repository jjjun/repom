-- 環境別のデータベースを作成
-- repom_dev は docker-compose.yml で自動作成されるため不要

-- テスト環境用
CREATE DATABASE repom_test;
GRANT ALL PRIVILEGES ON DATABASE repom_test TO repom;

-- 本番環境用
CREATE DATABASE repom_prod;
GRANT ALL PRIVILEGES ON DATABASE repom_prod TO repom;
