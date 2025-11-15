# Alembic バージョン配置の設定改善

## ステータス
- **段階**: アイディア
- **優先度**: 低
- **複雑度**: 低
- **作成日**: 2025-11-15
- **最終更新**: 2025-11-15

## 概要

Alembic のマイグレーションファイル（versions ディレクトリ）の配置を設定で柔軟に指定できるようにし、`alembic.ini` の配置場所と設定の一貫性を改善します。

## モチベーション

### 現在の問題

**現状の構成**:
```
repom/
├── alembic.ini                    # ルートの alembic.ini（必須）
├── alembic/
│   ├── env.py                     # version_locations を動的に上書き
│   └── versions/                  # 実際のマイグレーションファイル置き場
└── repom/
    └── (パッケージコード)
```

**問題点**:
1. **ルートの `alembic.ini` が必須**
   - パッケージとして配布する際にルートの設定ファイルが必要
   - `repom` 配下で完結できない構造

2. **設定の二重管理**
   - `alembic.ini` で `version_locations` と `version_path_separator` を設定
   - `env.py` で `version_locations` を動的に上書き
   - どちらが実際に使われているか不明確

3. **混乱を招く構成**
   - 設定ファイルと実際の動作が一致しない
   - 新しい開発者が理解しづらい
   - メンテナンス時に混乱の原因

**Copilot からの提案**:
> バージョン配置について、実際のリビジョンファイルはルートの versions に生成されています。一方で env.py では version_locations を動的に上書きしています。現状動いているのでそのままでも問題ありませんが、混乱防止のためバージョンの保存先は:
> - ルートの versions に統一する（env.py の上書きをやめる）
> - もしくは alembic/versions に統一する（alembic.ini も合わせる）
> どちらかに揃えるのをおすすめします。

## ユースケース

### 1. パッケージとしての配布
```
# 理想: repom パッケージ内で完結
repom/
├── pyproject.toml
└── repom/
    ├── alembic.ini           # パッケージ内の設定
    ├── alembic/
    │   ├── env.py
    │   └── versions/
    └── (その他のコード)

# インストール先プロジェクトでは
my_project/
├── pyproject.toml
└── (repom パッケージを使用するだけ)
```

### 2. 複数環境での使用
```python
# 環境ごとにマイグレーションファイルの配置を変更
# dev: ローカルの alembic/versions/
# test: テスト用の独立したディレクトリ
# prod: 本番用の検証済みマイグレーション

# 設定で切り替え可能に
ALEMBIC_VERSION_LOCATION = os.getenv('ALEMBIC_VERSION_LOCATION', 'alembic/versions')
```

### 3. モノレポでの使用
```
workspace/
├── repom/                    # 共有パッケージ
│   └── alembic/versions/
├── app1/                     # アプリ1
│   └── migrations/
└── app2/                     # アプリ2
    └── migrations/

# 各アプリが独自のマイグレーションを管理
# repom の基本マイグレーションは共有
```

## 検討可能なアプローチ

### アプローチ 1: alembic/versions に統一
**説明**: すべての設定を `alembic/versions` を指すように統一

**長所**:
- パッケージ内で完結
- 設定が一箇所に集約
- シンプルで理解しやすい
- 標準的な Alembic の構成に近い

**短所**:
- ルートの `alembic.ini` が残る可能性
- 既存の構成からの移行が必要

**実装**:
```ini
# alembic.ini（ルートまたは repom/ 配下）
[alembic]
script_location = alembic
version_locations = alembic/versions
version_path_separator = os

[alembic:exclude]
tables = alembic_version
```

```python
# alembic/env.py
# version_locations の動的上書きを削除
def run_migrations_online():
    config = context.config
    # 以下の行を削除
    # config.set_main_option('version_locations', 'alembic/versions')
    
    # 設定ファイルの値をそのまま使用
    ...
```

### アプローチ 2: 設定ファイルで柔軟に指定
**説明**: Python の設定クラスでマイグレーションディレクトリを管理

**長所**:
- 環境ごとに柔軟に変更可能
- コードで制御できる
- 複数のマイグレーションパスをサポート可能

**短所**:
- やや複雑
- Alembic の標準パターンから外れる

**実装**:
```python
# repom/config.py
class MineDbConfig:
    ALEMBIC_CONFIG_PATH: str = 'alembic.ini'
    ALEMBIC_VERSION_LOCATIONS: List[str] = ['alembic/versions']
    ALEMBIC_SCRIPT_LOCATION: str = 'alembic'

# alembic/env.py
from repom.config import CONFIG

def run_migrations_online():
    config = context.config
    
    # 設定クラスから動的に読み込み
    version_locations = CONFIG.ALEMBIC_VERSION_LOCATIONS
    config.set_main_option(
        'version_locations',
        os.pathsep.join(version_locations)
    )
    ...
```

### アプローチ 3: alembic.ini を repom/ 配下に移動
**説明**: `alembic.ini` を `repom/` ディレクトリに移動してパッケージ化

**長所**:
- パッケージとして完全に自己完結
- ルートディレクトリがクリーンになる
- パッケージの独立性が向上

**短所**:
- Alembic コマンドの実行時にパスを指定する必要がある
- 標準的な構成から外れる

**実装**:
```
repom/
├── pyproject.toml
├── alembic/
│   ├── env.py
│   └── versions/
└── repom/
    ├── alembic.ini           # ここに移動
    └── (コード)

# コマンド実行時
poetry run alembic -c repom/alembic.ini upgrade head
```

**pyproject.toml でエイリアスを作成**:
```toml
[tool.poetry.scripts]
db-migrate = "repom.scripts.db_migrate:main"

# スクリプト内で自動的に -c repom/alembic.ini を追加
```

## 技術的考慮事項

### 既存マイグレーションへの影響
- 既存のマイグレーションファイルの移動が必要な場合がある
- `alembic_version` テーブルの整合性を保つ必要がある
- バージョン履歴の保持

### 環境変数との統合
```python
# 環境変数で上書き可能にする
ALEMBIC_VERSION_LOCATION = os.getenv(
    'ALEMBIC_VERSION_LOCATION',
    'alembic/versions'
)
```

### 複数バージョンディレクトリのサポート
```ini
# 複数のバージョンディレクトリを指定
version_locations = alembic/versions;repom/migrations
version_path_separator = ;
```

### Poetry スクリプトとの統合
```toml
[tool.poetry.scripts]
alembic-upgrade = "repom.scripts.alembic_wrapper:upgrade"
alembic-revision = "repom.scripts.alembic_wrapper:revision"

# ラッパースクリプトで設定を自動適用
```

## 統合ポイント

### 影響を受けるコンポーネント
- `alembic.ini` - 設定の見直しと移動の可能性
- `alembic/env.py` - `version_locations` の上書きロジック削除
- `repom/config.py` - Alembic 設定の追加（オプション）
- `pyproject.toml` - スクリプトエイリアスの追加（オプション）
- `README.md` - マイグレーション手順の更新

### 既存機能との相互作用
- 既存のマイグレーションコマンド（`alembic upgrade head` など）
- 環境別データベース（`EXEC_ENV=dev/test/prod`）
- Poetry スクリプト（`db_create`, `db_backup` など）

### 移行手順例（アプローチ 1 を選択した場合）

1. **設定ファイルの更新**
```bash
# alembic.ini を確認
[alembic]
version_locations = alembic/versions
version_path_separator = os
```

2. **env.py の修正**
```python
# alembic/env.py から動的上書きを削除
# Before:
config.set_main_option('version_locations', 'alembic/versions')

# After:
# この行を削除（alembic.ini の設定を使用）
```

3. **動作確認**
```bash
# マイグレーション生成が正しい場所に作成されるか確認
poetry run alembic revision --autogenerate -m "test"

# versions ディレクトリを確認
ls alembic/versions/

# マイグレーション適用
poetry run alembic upgrade head
```

4. **ドキュメント更新**
```markdown
# README.md に追記
## マイグレーション

マイグレーションファイルは `alembic/versions/` に配置されます。

```bash
# マイグレーション生成
poetry run alembic revision --autogenerate -m "description"

# マイグレーション適用
poetry run alembic upgrade head
```
```

## 次のステップ

- [ ] 現在の `alembic.ini` と `env.py` の設定を詳細に確認
- [ ] どのアプローチを採用するか決定（推奨: アプローチ 1）
- [ ] 既存マイグレーションファイルの配置を確認
- [ ] テスト環境で設定変更を試行
- [ ] すべての環境（dev/test/prod）で動作確認
- [ ] ドキュメントの更新
- [ ] 移行手順の作成
- [ ] 実装する場合は `docs/research/` に移動

## 関連ドキュメント

- `alembic.ini` - 現在の Alembic 設定
- `alembic/env.py` - マイグレーション実行環境の設定
- `README.md` - マイグレーション手順
- Alembic 公式ドキュメント: [Multiple Version Directories](https://alembic.sqlalchemy.org/en/latest/branches.html#working-with-multiple-bases)

## 解決すべき質問

1. **最優先**: どのアプローチを採用するか？
   - 推奨: アプローチ 1（`alembic/versions` に統一）
   - 理由: シンプルで標準的、移行も容易

2. ルートの `alembic.ini` を維持するか、`repom/` 配下に移動するか？

3. 複数のバージョンディレクトリをサポートする必要があるか？

4. 環境変数でマイグレーションディレクトリを上書きする機能は必要か？

5. 既存のマイグレーションファイルの移動が必要な場合、どう対処するか？

6. パッケージとして配布する際の `alembic.ini` の扱いは？

7. CI/CD パイプラインでのマイグレーション実行への影響は？

## 推奨事項

**短期的な対応（すぐに実施可能）**:
1. `alembic/env.py` から `version_locations` の動的上書きを削除
2. `alembic.ini` の設定値をそのまま使用
3. 動作確認とドキュメント更新

**長期的な対応（パッケージ化を見据えて）**:
1. `alembic.ini` を `repom/` 配下に移動
2. Poetry スクリプトでパスを自動指定
3. 環境変数でのカスタマイズをサポート

## 参考: 他のプロジェクトの構成例

### FastAPI プロジェクトの例
```
project/
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
└── app/
    └── (コード)
```

### Django の例（参考）
```
project/
├── manage.py
└── app/
    └── migrations/
        └── 0001_initial.py

# Django は app ごとにマイグレーションを管理
```

### Flask-Migrate の例
```
project/
├── migrations/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
└── app/
    └── (コード)

# Flask-Migrate は migrations/ ディレクトリに統一
```

**repom への適用案**:
```
repom/
├── alembic.ini              # 設定ファイル
├── alembic/
│   ├── env.py              # 実行環境
│   └── versions/           # マイグレーションファイル
└── repom/
    └── (コード)

# シンプルで標準的な構成
```
