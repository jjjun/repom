# Alembic マイグレーション運用ガイド

## 重要：環境変数の扱い

PowerShellでは `$env:EXEC_ENV` を一度設定すると、**セッション内で保持され続けます**。

### ❌ 間違った使い方
```powershell
# 開発環境を設定
$env:EXEC_ENV='dev'; poetry run alembic upgrade head

# この後、本番環境のつもりで実行しても dev のまま！
poetry run alembic upgrade head  # ← 危険！まだ dev を参照
```

### ✅ 正しい使い方

#### 本番環境（デフォルト）
```powershell
# 環境変数をクリア（本番環境）
Remove-Item Env:\EXEC_ENV -ErrorAction SilentlyContinue
poetry run alembic upgrade head

# または明示的に prod を指定
$env:EXEC_ENV='prod'; poetry run alembic upgrade head
```

#### 開発環境
```powershell
# 毎回明示的に指定
$env:EXEC_ENV='dev'; poetry run alembic upgrade head
```

## 基本コマンド

### マイグレーション作成
```powershell
# 自動生成（モデル変更を検出）
poetry run alembic revision --autogenerate -m "description"

# 空のマイグレーション
poetry run alembic revision -m "description"
```

### マイグレーション適用（アップグレード）
```powershell
# 本番環境
Remove-Item Env:\EXEC_ENV -ErrorAction SilentlyContinue
poetry run alembic upgrade head

# 開発環境
$env:EXEC_ENV='dev'; poetry run alembic upgrade head
```

### マイグレーション取り消し（ダウングレード）
```powershell
# 1つ前のバージョンに戻す
poetry run alembic downgrade -1

# 特定のバージョンに戻す
poetry run alembic downgrade <revision_id>

# すべてのマイグレーションを取り消す
poetry run alembic downgrade base
```

### 状態確認
```powershell
# 現在のバージョンを確認
poetry run alembic current

# マイグレーション履歴を確認
poetry run alembic history

# 環境変数の確認
echo $env:EXEC_ENV
```

### 既存DBをマイグレーション管理下に置く
```powershell
# 現在のDB構造を特定のバージョンとしてマーク
poetry run alembic stamp head
```

## トラブルシューティング

### 本番環境のつもりが開発環境を操作してしまった場合

1. 環境変数を確認
   ```powershell
   echo $env:EXEC_ENV
   ```

2. 環境変数をクリア
   ```powershell
   Remove-Item Env:\EXEC_ENV
   ```

3. 再度正しい環境で実行

### 両環境のバージョンを確認
```powershell
# 本番環境
Remove-Item Env:\EXEC_ENV -ErrorAction SilentlyContinue
poetry run alembic current

# 開発環境
$env:EXEC_ENV='dev'; poetry run alembic current
```

### 直接DBのバージョンを確認
```powershell
# 本番環境
sqlite3 data\repom\db.sqlite3 "SELECT * FROM alembic_version;"

# 開発環境
sqlite3 data\repom\db.dev.sqlite3 "SELECT * FROM alembic_version;"
```

## ベストプラクティス

1. **マイグレーション前に必ずバックアップ**
   ```powershell
   Copy-Item data\repom\db.sqlite3 data\repom\backups\db_$(Get-Date -Format 'yyyyMMdd_HHmmss').sqlite3
   ```

2. **開発環境で先にテスト**
   ```powershell
   $env:EXEC_ENV='dev'; poetry run alembic upgrade head
   # 問題なければ本番環境へ
   Remove-Item Env:\EXEC_ENV
   poetry run alembic upgrade head
   ```

3. **マイグレーション後は必ず確認**
   ```powershell
   poetry run alembic current
   ```

4. **コマンド実行前に環境変数を明示的に設定**
   - 本番環境: `Remove-Item Env:\EXEC_ENV` または `$env:EXEC_ENV='prod'`
   - 開発環境: `$env:EXEC_ENV='dev'`

## SQLiteの制約

SQLiteは `ALTER TABLE` に制限があるため、複雑な変更は `batch_alter_table` を使用するか、手動SQLで対応する必要があります。
