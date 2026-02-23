# fast-domain Redis 統合 資料一覧

**作成日**: 2026-02-23  
**対象**: fast-domain プロジェクトでの Redis Docker Manager 実装

---

## 📚 提供ドキュメント一覧

| # | ファイル | 内容 | 対象者 |
|-|-|-|-|
| 1 | [redis_manager_implementation.md](./redis_manager_implementation.md) | RedisManager クラス実装テンプレート＆ガイド | アーキテクト/開発者 |
| 2 | [redis_docker_compose_examples.md](./redis_docker_compose_examples.md) | docker-compose.yml 設定例 | インフラ/開発者 |
| 3 | [redis_testing_guide.md](./redis_testing_guide.md) | Unit/Integration テスト実装ガイド | テスト実装者 |
| 4 | [redis_cli_integration.md](./redis_cli_integration.md) | CLI コマンド統合ガイド | 統合/デプロイ担当 |

---

## 🚀 実装ロードマップ

### Phase 1: 基盤実装（1-2時間）
1. RedisManager クラス作成
   - 📖 参考: [redis_manager_implementation.md](./redis_manager_implementation.md)
   - 実装ファイル: `src/fast_domain/docker/redis_manager.py`
   
2. docker-compose.yml 生成
   - 📖 参考: [redis_docker_compose_examples.md](./redis_docker_compose_examples.md)
   - サンプル: 基本的な Redis, Redis + RedisInsight

### Phase 2: テスト実装（1-2時間）
1. Unit テスト（12-15個）
   - 📖 参考: [redis_testing_guide.md](./redis_testing_guide.md)
   - テストファイル: `tests/test_redis_manager.py`
   
2. Docker Integration テスト（CI/CD 対応）
   - pytest markers 使用
   - GitHub Actions 例付き

### Phase 3: CLI 統合（30分-1時間）
1. 4つのコマンド実装
   - 📖 参考: [redis_cli_integration.md](./redis_cli_integration.md)
   - コマンド: `redis_generate`, `redis_start`, `redis_stop`, `redis_remove`
   - オプション: `redis_status`

---

## 📊 実装規模見積もり

| 項目 | 行数 | 時間 | 難度 |
|-----|------|------|------|
| RedisManager クラス | ~80行 | 30分 | ⭐ |
| CLI コマンド | ~120行 | 1時間 | ⭐ |
| テストケース | ~250行 | 1-2時間 | ⭐⭐ |
| **合計** | **~450行** | **2.5-3時間** | **簡単** |

---

## 🎯 削減効果（予想）

| メトリック | 削減前 | 削減後 | 削減率 |
|----------|--------|--------|---------|
| Redis 管理コード | ~150行 | ~60行 | **60%削減** |
| テストコード | 独立実装 | 共通基盤利用 | **コード共有化** |

---

## ✅ 各ドキュメントの使い方

### 1. redis_manager_implementation.md
**何をするか**: RedisManager クラスの実装方法を学ぶ

**含まれるもの**:
- ✅ RedisManager クラステンプレート（コピペ可能）
- ✅ 実装例（待機ロジック、エラーハンドリング）
- ✅ generate() 関数実装例
- ✅ テスト例（スタート地点）

**使用シーン**:
```
開発者が RedisManager.py を書く → このドキュメントを参照
```

---

### 2. redis_docker_compose_examples.md
**何をするか**: より良い docker-compose.yml を作成する

**含まれるもの**:
- ✅ 基本的な Redis（シンプル）
- ✅ Redis + RedisInsight（管理UI）
- ✅ Redis Cluster（将来拡張用）
- ✅ Python での使用例
- ✅ Redis CLI コマンドリファレンス

**使用シーン**:
```
docker-compose.yml をカスタマイズしたい → このドキュメントを参照
Redis のコマンドが分からない → CLI リファレンスを確認
```

---

### 3. redis_testing_guide.md
**何をするか**: 包括的なテストを実装する

**含まれるもの**:
- ✅ Unit テスト例（モック使用）
- ✅ Integration テスト例
- ✅ Docker 実際テスト例
- ✅ CI/CD 統合例（GitHub Actions）
- ✅ テスト実行コマンド

**使用シーン**:
```
テストを書く → このドキュメントをコピペして実装
CI/CD を設定 → GitHub Actions 例を参照
```

---

### 4. redis_cli_integration.md
**何をするか**: Poetry コマンドとしてを統合する

**含まれるもの**:
- ✅ pyproject.toml 設定例
- ✅ CLI コマンド実装コード
- ✅ 使用例
- ✅ 環境変数カスタマイズ
- ✅ トラブルシューティング

**使用シーン**:
```
poetry run redis_* コマンドを作成 → このドキュメントを参照
ポート競合が起きた → トラブルシューティング確認
```

---

## 🔗 参考資料（repom 内）

### Phase 1/2 の実装例
- 📂 [repom/postgres/manage.py](../../repom/postgres/manage.py) - PostgreSQL 統合の完全な実装例
- 📂 [repom/_/docker_manager.py](../../repom/_/docker_manager.py) - DockerManager 基盤クラス
- 📂 [tests/unit_tests/test_postgres_manager.py](../../tests/unit_tests/test_postgres_manager.py) - PostgreSQL テスト例

### ガイドドキュメント
- 📖 [docs/guides/features/docker_manager_guide.md](../features/docker_manager_guide.md) - Docker Manager 使用ガイド
- 📖 [docs/technical/docker_manager_code_reduction_analysis.md](../technical/docker_manager_code_reduction_analysis.md) - 削減効果分析

---

## 📋 実装手順（ステップバイステップ）

### ステップ 1: RedisManager 作成（30分）
```bash
# ファイル作成
mkdir -p src/fast_domain/docker
touch src/fast_domain/docker/{__init__.py,redis_manager.py}

# 実装
# → redis_manager_implementation.md を参照してコーディング
```

### ステップ 2: docker-compose 生成（15分）
```python
# generate() 関数を実装
# → redis_docker_compose_examples.md のテンプレートを使用
```

### ステップ 3: テスト実装（1-2時間）
```bash
# テストファイル作成
touch tests/test_redis_manager.py

# テスト実装
# → redis_testing_guide.md のテストコードをコピペして実装
```

### ステップ 4: CLI 統合（1時間）
```python
# pyproject.toml に script entry 追加
# → redis_cli_integration.md の設定例を参照

# CLI コマンド実装
# → redis_cli_integration.md のコード例をコピペ
```

### ステップ 5: 動作確認
```bash
poetry run redis_generate
poetry run redis_start
poetry run pytest tests/test_redis_manager.py
poetry run redis_stop
```

---

## 🎓 学習ポイント

### 重要な概念
1. **DockerManager 基盤の活用** - repom の基盤クラスを使って重複コード削減
2. **テンプレートメソッドパターン** - 共通処理と特化処理の分離
3. **健全性確認（Readiness Check）** - サービス起動を確実に待機
4. **pytest + モック** - Docker 不要なテストの実装

### 参考教材（repom から学べること）
- PostgreSQL 実装 - Redis でも同じパターンを使用
- Unit テスト - 同じテストパターンをコピーして利用可能
- CLI 統合 - poetry コマンド統合の同じ方式

---

## ❓ FAQ

**Q: 全部実装するのにどのくらい時間がかかる？**  
A: 2.5～3時間程度。experienced 開発者なら 1.5～2時間。

**Q: docker-compose.yml はどこに置く？**  
A: `infrastructure/docker-compose.generated.yml` 推奨（PostgreSQL と同じ場所）

**Q: Redis のポートをカスタマイズしたい**  
A: [redis_cli_integration.md](./redis_cli_integration.md) の「環境変数での制御」を参照

**Q: テストを Docker で実行したい（CI/CD）**  
A: [redis_testing_guide.md](./redis_testing_guide.md) の「GitHub Actions 例」を参照

**Q: すでに存在する Redis 管理コードを統合したい**  
A: [redis_manager_implementation.md](./redis_manager_implementation.md) の RedisManager に統合

---

## 🚨 よくあるエラー

| エラー | 原因 | 解決策 |
|--------|------|--------|
| `ModuleNotFoundError: No module named 'repom'` | repom が見つからない | pyproject.toml で repom を依存関係に追加 |
| `docker-compose: command not found` | Docker Desktop 未インストール | Docker Desktop をインストール |
| `Port 6379 is already in use` | 別の Redis が起動中 | REDIS_PORT=6380 で別ポート指定 |
| `redis-cli: command not found` | redis-cli が見つからない | Docker exec で内部実行：`docker exec fast_domain_redis redis-cli` |

---

## 📞 支援リソース

- **repom PostgreSQL 実装**: `../../repom/postgres/manage.py` を参照
- **DockerManager 基盤**: `../../repom/_/docker_manager.py` を参照
- **テスト実装例**: `../../tests/unit_tests/test_postgres_manager.py` を参照

---

## ✨ 完成イメージ

実装完了後：

```bash
# Redis を簡単に起動
$ poetry run redis_start
✅ Redis started

# アプリケーション実行
$ poetry run app
📦 Connected to Redis

# テスト実行
$ poetry run pytest
======= 15 passed in 1.23s =======

# Redis を停止
$ poetry run redis_stop
✅ Redis stopped
```

---

**次のステップ**: 各ドキュメントを順に読んで、実装してください！  
**質問がある場合**: repom 内の PostgreSQL 実装例（`repom/postgres/manage.py`）を参照してください。  
**完成後**: 削減効果を測定し、fast-domain リポジトリに PR してください！ 🚀
