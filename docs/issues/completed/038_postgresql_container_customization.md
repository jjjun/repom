# Issue: PostgreSQL コンテナ設定のカスタマイズ対応

## Status
- **Created**: 2026-02-22
- **Completed**: 2026-02-23
- **Priority**: Medium
- **Complexity**: Medium
- **Implementation Status**: Phases 1-6 ✅ Complete

## Problem Description

現在の PostgreSQL Docker 環境は、コンテナ名・DB名・ポート・volume名が固定されており、複数プロジェクトを並行開発する際に以下の問題が発生します：

### 現状の固定値

```yaml
# repom/postgres/docker-compose.template.yml
services:
  postgres:
    container_name: repom_postgres  # ❌ 固定
    ports:
      - "5432:5432"                 # ❌ 固定
    environment:
      POSTGRES_DB: repom_dev        # ❌ 固定
    volumes:
      - postgres_data:/var/lib/postgresql/data  # ❌ 固定
```

### 問題点

1. **コンテナ名の衝突**
   - 複数の repom ベースプロジェクト（mine-py, other-project）を同時起動できない
   - エラー: `Container name "repom_postgres" is already in use`

2. **ポート衝突**
   - 複数コンテナを起動すると `5432` ポートが衝突
   - エラー: `Bind for 0.0.0.0:5432 failed: port is already allocated`

3. **Volume名の衝突**
   - 異なるプロジェクトで同じ volume を共有してしまう
   - データが混在する可能性

4. **DB名の固定**
   - プロジェクトごとに識別しやすい DB名を使えない
   - 環境別サフィックス（`_dev`, `_test`, `_prod`）は付くが、ベース名が `repom` 固定

## Expected Behavior

プロジェクトごとに独立した PostgreSQL 環境を構築できるようにする：

```yaml
# mine-py の場合
container_name: mine_py_postgres
ports:
  - "5433:5432"  # ホスト側ポートをずらす
environment:
  POSTGRES_DB: mine_py_dev
volumes:
  - mine_py_postgres_data:/var/lib/postgresql/data

# other-project の場合
container_name: other_project_postgres
ports:
  - "5434:5432"
environment:
  POSTGRES_DB: other_project_dev
volumes:
  - other_project_postgres_data:/var/lib/postgresql/data
```

## Proposed Solution

### CONFIG_HOOK + 汎用 Docker 基盤による設定集約（採用案）

環境変数ではなく、CONFIG_HOOK を使って Docker コンテナ設定を管理します。
Docker 環境構築の基盤処理を `repom._` 配下に配置し、PostgreSQL はその基盤を使う一例として実装します。
これにより、将来的に Redis, MongoDB などの他の Docker 環境でも同じ基盤を使えます。

#### 1. 汎用 Docker Compose 基盤の作成

```python
# repom/_/docker_compose.py
"""Docker Compose ファイル動的生成の基盤"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path

@dataclass
class DockerService:
    """Docker サービス設定"""
    name: str
    image: str
    container_name: str
    ports: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    volumes: List[str] = field(default_factory=list)
    healthcheck: Optional[Dict] = field(default=None)

@dataclass
class DockerVolume:
    """Docker Volume 設定"""
    name: str
    driver: str = "local"

class DockerComposeGenerator:
    """Docker Compose ファイル生成器"""
    
    def __init__(self, version: str = "3.8"):
        self.version = version
        self.services: List[DockerService] = []
        self.volumes: List[DockerVolume] = []
    
    def add_service(self, service: DockerService) -> "DockerComposeGenerator":
        """サービスを追加"""
        self.services.append(service)
        return self
    
    def add_volume(self, volume: DockerVolume) -> "DockerComposeGenerator":
        """Volume を追加"""
        self.volumes.append(volume)
        return self
    
    def generate(self) -> str:
        """docker-compose.yml を生成"""
        lines = [f"version: '{self.version}'", "", "services:"]
        
        for service in self.services:
            lines.extend(self._generate_service(service))
        
        if self.volumes:
            lines.extend(["", "volumes:"])
            for volume in self.volumes:
                lines.append(f"  {volume.name}:")
                if volume.driver != "local":
                    lines.append(f"    driver: {volume.driver}")
        
        return "\n".join(lines)
    
    def _generate_service(self, service: DockerService) -> List[str]:
        """サービス定義を生成"""
        lines = [
            f"  {service.name}:",
            f"    image: {service.image}",
            f"    container_name: {service.container_name}",
        ]
        
        if service.environment:
            lines.append("    environment:")
            for key, value in service.environment.items():
                lines.append(f"      {key}: {value}")
        
        if service.ports:
            lines.append("    ports:")
            for port in service.ports:
                lines.append(f"      - \"{port}\"")
        
        if service.volumes:
            lines.append("    volumes:")
            for volume in service.volumes:
                lines.append(f"      - {volume}")
        
        if service.healthcheck:
            lines.append("    healthcheck:")
            for key, value in service.healthcheck.items():
                if key == "test":
                    lines.append(f"      test: {value}")
                else:
                    lines.append(f"      {key}: {value}")
        
        return lines
    
    def write_to_file(self, filepath: Path) -> None:
        """ファイルに書き込む"""
        filepath.write_text(self.generate(), encoding="utf-8")
```

#### 2. RepomConfig に PostgreSQL コンテナ設定を追加

```python
# repom/config.py
@dataclass
class PostgresContainerConfig:
    """PostgreSQL Docker コンテナ設定
    
    Attributes:
        container_name: コンテナ名（None の場合は repom_postgres）
        host_port: ホスト側のポート番号
        volume_name: Volume名（None の場合は repom_postgres_data）
        image: PostgreSQL イメージ
    
    Note: プロジェクト名による自動導出ではなく、明示的に指定する設計
    """
    container_name: Optional[str] = field(default=None)
    host_port: int = field(default=5432)
    volume_name: Optional[str] = field(default=None)
    image: str = field(default="postgres:16-alpine")
    
    def get_container_name(self) -> str:
        """コンテナ名を取得（デフォルト: repom_postgres）"""
        return self.container_name or "repom_postgres"
    
    def get_volume_name(self) -> str:
        """Volume名を取得（デフォルト: repom_postgres_data）"""
        return self.volume_name or "repom_postgres_data"

@dataclass
class PostgresConfig:
    """PostgreSQL データベース設定"""
    host: str = field(default='localhost')
    port: int = field(default=5432)
    user: str = field(default='repom')
    password: str = field(default='repom_dev')
    database: Optional[str] = field(default=None)  # ← DB基本名（環境プレフィックスなし）
    
    # Docker コンテナ設定
    container: PostgresContainerConfig = field(default_factory=PostgresContainerConfig)
```

#### 3. CONFIG_HOOK でプロジェクトごとの設定を定義

```python
# mine_py/config.py
from repom.config import RepomConfig

def hook_config(config: RepomConfig) -> RepomConfig:
    # コンテナ名を明示的に指定
    config.postgres.container.container_name = "mine_py_postgres"
    
    # ポートをずらす（repom: 5432, mine_py: 5433）
    config.postgres.container.host_port = 5433
    
    # DB 基本名を設定（環境別プレフィックスが自動的に付く）
    config.postgres.database = "mine_py"  # → mine_py_dev, mine_py_test, mine_py_prod
    
    # DB ユーザー設定
    config.postgres.user = "mine_py"
    config.postgres.password = "mine_py_dev"
    
    return config
```

```bash
# mine_py/.env
CONFIG_HOOK=mine_py.config:hook_config
```

#### 4. manage.py が基盤を使って docker-compose.yml を動的生成

**重要**: docker-compose.yml は `config.data_path` 配下に保存されます。

```python
# repom/postgres/manage.py
from repom.config import config
from repom._.docker_compose import DockerComposeGenerator, DockerService, DockerVolume
from pathlib import Path

def get_compose_dir() -> Path:
    """docker-compose.yml の保存先ディレクトリを取得
    
    Returns:
        config.data_path のディレクトリ
    """
    compose_dir = Path(config.data_path)
    compose_dir.mkdir(parents=True, exist_ok=True)
    return compose_dir

def get_init_dir() -> Path:
    """PostgreSQL 初期化スクリプトのディレクトリを取得
    
    Returns:
        data/{project_name}/postgresql_init/ ディレクトリ
    """
    compose_dir = get_compose_dir()
    init_dir = compose_dir / "postgresql_init"
    init_dir.mkdir(parents=True, exist_ok=True)
    return init_dir

def generate_docker_compose() -> DockerComposeGenerator:
    """config から docker-compose.yml 生成器を作成"""
    pg = config.postgres
    container = pg.container
    
    # DB基本名を取得（config.postgres.database でカスタマイズ可能）
    base_db = config.postgres.database or "repom"
    db_dev = f"{base_db}_dev"  # 初期化スクリプトで作成される3つのDBのうち1つ
    
    # init スクリプトのパスを取得
    init_dir = get_init_dir()
    
    # PostgreSQL サービスを定義
    postgres_service = DockerService(
        name="postgres",
        image=container.image,
        container_name=container.get_container_name(),
        environment={
            "POSTGRES_USER": pg.user,
            "POSTGRES_PASSWORD": pg.password,
            "POSTGRES_DB": db_dev,
        },
        ports=[f"{container.host_port}:5432"],
        volumes=[
            f"{container.get_volume_name()}:/var/lib/postgresql/data",
            f"{init_dir.absolute()}:/docker-entrypoint-initdb.d",
        ],
        healthcheck={
            "test": f'["CMD-SHELL", "pg_isready -U {pg.user}"]',
            "interval": "5s",
            "timeout": "5s",
            "retries": 5,
        }
    )
    
    # Docker Volume を定義
    data_volume = DockerVolume(name=container.get_volume_name())
    
    # 生成器を作成
    generator = DockerComposeGenerator()
    generator.add_service(postgres_service)
    generator.add_volume(data_volume)
    
    return generator

def generate_init_sql() -> str:
    """環境別の DB 作成スクリプトを生成
    
    config.postgres.database でカスタマイズ可能（環境プレフィックスなしのベース名）
    デフォルト: repom → repom_dev, repom_test, repom_prod を作成
    """
    # ベース名を取得（環境プレフィックスなし）
    base = config.postgres.database or "repom"
    user = config.postgres.user
    
    return f"""-- {base} project databases
CREATE DATABASE {base}_dev;
CREATE DATABASE {base}_test;
CREATE DATABASE {base}_prod;

GRANT ALL PRIVILEGES ON DATABASE {base}_dev TO {user};
GRANT ALL PRIVILEGES ON DATABASE {base}_test TO {user};
GRANT ALL PRIVILEGES ON DATABASE {base}_prod TO {user};
"""

def generate():
    """docker-compose.yml を生成（コマンドから呼び出し可能）"""
    # 初期化スクリプトを生成
    init_dir = get_init_dir()
    init_sql = generate_init_sql()
    (init_dir / "01_init_databases.sql").write_text(init_sql, encoding="utf-8")
    
    # docker-compose.yml を生成
    generator = generate_docker_compose()
    compose_dir = get_compose_dir()
    output_path = compose_dir / "docker-compose.generated.yml"
    generator.write_to_file(output_path)
    
    print(f"✅ Generated: {output_path}")
    print(f"   Init SQL: {init_dir / '01_init_databases.sql'}")
    print(f"   Container: {config.postgres.container.get_container_name()}")
    print(f"   Port: {config.postgres.container.host_port}")
    print(f"   Volume: {config.postgres.container.get_volume_name()}")

def start():
    """PostgreSQL を起動"""
    # docker-compose.yml を生成
    generate()
    
    print(f"🐳 Starting PostgreSQL container...")
    
    # docker-compose を実行
    compose_dir = get_compose_dir()
    compose_file = compose_dir / "docker-compose.generated.yml"
    subprocess.run(
        ["docker-compose", "-f", str(compose_file), "up", "-d"],
        check=True,
        cwd=str(compose_dir)
    )

def stop():
    """PostgreSQL を停止"""
    compose_dir = get_compose_dir()
    compose_file = compose_dir / "docker-compose.generated.yml"
    
    if not compose_file.exists():
        print("⚠️  docker-compose.generated.yml が見つかりません")
        return
    
    subprocess.run(
        ["docker-compose", "-f", str(compose_file), "down"],
        check=True,
        cwd=str(compose_dir)
    )
```

## Implementation Plan

1. **Phase 1: 汎用 Docker Compose 基盤の実装**
   - `repom/_/docker_compose.py` を新規作成
   - `DockerComposeGenerator`, `DockerService`, `DockerVolume` クラスを実装
   - 単体テストを作成（基盤の動作確認）

2. **Phase 2: PostgresContainerConfig の追加**
   - `repom/config.py` に `PostgresContainerConfig` を追加
   - `PostgresConfig` に `container` フィールドを追加
   - デフォルト値で既存動作を維持（後方互換性）

3. **Phase 3: manage.py の動的生成対応**
   - 基盤を使って `generate_docker_compose()` を実装
   - `get_compose_dir()`, `get_init_dir()` を実装（保存先: `data/{project_name}/`）
   - `generate_init_sql()` を実装（プロジェクト名に応じた DB 作成）
   - `generate()` 関数を追加（設定ファイル生成用）
   - `docker-compose.generated.yml` と初期化スクリプトを `data/{project_name}/` に生成
   - 既存の `docker-compose.yml` は `docker-compose.template.yml` に改名

4. **Phase 4: コマンド追加**
   - `poetry run postgres_generate` - docker-compose.yml を生成
   - `poetry run postgres_start` - 既存（生成 + 起動）
   - `poetry run postgres_stop` - 既存

5. **Phase 5: テストとドキュメント**
   - 複数プロジェクトの同時起動をテスト
   - PostgreSQL セットアップガイドに設定例を追加
   - トラブルシューティングにポート衝突の対処法を追加
   - 基盤の使い方ガイドを作成（他の Docker 環境への適用例）

## Benefits

- ✅ 複数プロジェクトを同時に開発できる
- ✅ プロジェクトごとに独立した DB 環境
- ✅ ポート衝突を回避できる
- ✅ CONFIG_HOOK で設定が一元管理される
- ✅ 環境変数を使わず、repom の設計思想に合致
- ✅ 既存プロジェクトへの影響なし（デフォルト値で後方互換性維持）
- ✅ 汎用 Docker 基盤により、他の Docker 環境（Redis, MongoDB など）でも同じ仕組みを使える
- ✅ `postgres_generate` コマンドで設定ファイルを事前確認できる
- ✅ プロジェクトのデータが `data/{project_name}/` に一元化される

## Design Decisions

1. **環境変数ではなく CONFIG_HOOK を使用**
   - 理由: repom の設計思想に合致、設定を一箇所に集約できる
   - メリット: プロジェクトごとの .env ファイルで CONFIG_HOOK を指定するだけで完結

2. **汎用 Docker 基盤を `repom._` 配下に配置**
   - 理由: PostgreSQL 以外の Docker 環境でも再利用可能
   - 将来的な用途: Redis, MongoDB, Elasticsearch など
   - `repom._` は内部基盤のための名前空間

3. **docker-compose.yml の保存先は `data/{project_name}/`**
   - repom の場合: `data/repom/docker-compose.generated.yml`
   - mine-py の場合: `data/mine_py/docker-compose.generated.yml`
   - fast-domain の場合: `data/fast_domain/docker-compose.generated.yml`
   - 理由: プロジェクトごとのデータ（SQLite DB、バックアップ、ログ）と同じディレクトリで一元管理

4. **初期化スクリプトも動的生成**
   - 保存先: `data/{project_name}/postgresql_init/01_init_databases.sql`
   - プロジェクト名に応じた DB 名を動的に設定
   - docker-compose.yml と同じディレクトリで管理

5. **動的生成ファイルは `.generated` サフィックス**
   - `docker-compose.generated.yml` として生成
   - `.gitignore` に `data/*/docker-compose.generated.yml` と `data/*/postgresql_init/` を追加
   - `postgres_generate` コマンドで事前確認可能

6. **デフォルト値で後方互換性を維持**
   - `project_name: "repom"`, `host_port: 5432` がデフォルト
   - 既存プロジェクトは設定なしで動作し続ける

7. **データクラスによる型安全な設定**
   - `DockerService`, `DockerVolume` で構造を明確化
   - IDE の補完とバリデーションが効く

## Risks

- 動的生成した `docker-compose.generated.yml` のバージョン管理が必要
  - 解決策: `.gitignore` に `data/*/docker-compose.generated.yml` を追加し、実行時に生成
- 既存の `docker-compose.yml` を直接編集している場合は影響あり
  - 解決策: 既存ファイルは `docker-compose.template.yml` に改名し、参考用として残す
- `data/` ディレクトリが肥大化する可能性
  - 解決策: プロジェクトごとに `data/{project_name}/` で分離されるため、管理しやすい

## File Structure

実装後のファイル構造：

```
data/
├── repom/                                    # repom プロジェクト用
│   ├── db.dev.sqlite3                       # 既存: SQLite DB
│   ├── docker-compose.generated.yml         # 新規: Docker Compose 設定
│   ├── postgresql_init/                     # 新規: PostgreSQL 初期化スクリプト
│   │   └── 01_init_databases.sql
│   ├── backups/                            # 既存: バックアップ
│   └── logs/                               # 既存: ログ
│
├── mine_py/                                # mine-py プロジェクト用（例）
│   ├── docker-compose.generated.yml         # Docker Compose 設定
│   └── postgresql_init/                     # PostgreSQL 初期化スクリプト
│       └── 01_init_databases.sql
│
└── fast_domain/                            # fast-domain プロジェクト用（例）
    ├── docker-compose.generated.yml         # Docker Compose 設定
    └── postgresql_init/                     # PostgreSQL 初期化スクリプト
        └── 01_init_databases.sql
```

## Related Files

- **新規作成**:
  - `repom/_/docker_compose.py` - 汎用 Docker Compose 基盤
  - `tests/unit_tests/test_docker_compose.py` - 基盤のテスト
  - `data/{project_name}/docker-compose.generated.yml` - 動的生成される設定ファイル（実行時）
  - `data/{project_name}/postgresql_init/01_init_databases.sql` - 動的生成される初期化スクリプト（実行時）

- **変更**:
  - `repom/config.py` - PostgresContainerConfig 追加
  - `repom/postgres/manage.py` - 基盤を使用する実装、保存先を `data/{project_name}/` に変更
  - `pyproject.toml` - `postgres_generate` コマンド追加
  - `.gitignore` - `data/*/docker-compose.generated.yml` と `data/*/postgresql_init/` を追加

- **リネーム**:
  - `repom/postgres/docker-compose.template.yml` - 参考テンプレートとして残す
  - `repom/postgres/init.template/` - 初期化スクリプトテンプレート

- **ドキュメント**:
  - `docs/guides/postgresql/postgresql_setup_guide.md` - 設定例追加
  - `docs/guides/features/docker_compose_guide.md` - 基盤の使い方ガイド（新規）

## Related Documents

- [PostgreSQL セットアップガイド](../../guides/postgresql/postgresql_setup_guide.md)

## pgAdmin Integration（Phase 6 - 実装完了 ✅）

pgAdmin をオプショナルな Docker サービスとして統合し、DB管理を簡素化する。

### 実装状況

**Phase 6.1-6.3 完了**:
- ✅ PgAdminContainerConfig, PgAdminConfig クラス実装 (\
epom/config.py\)
- ✅ RepomConfig に pgadmin フィールド追加
- ✅ manage.py で条件付き pgAdmin サービス生成
- ✅ 15個の Unit tests 追加 → **660 tests 合格** (前: 645)
- ✅ postgres_generate コマンドで動作検証完了

### デフォルト（pgAdmin 無効時）

\\\
✅ Generated: data/repom/docker-compose.generated.yml
📦 PostgreSQL Service:
   Container: repom_postgres
   Port: 5432
   Volume: repom_postgres_data

⚪ pgAdmin: Disabled (set config.pgadmin.container.enabled=True to enable)
\\\

### 設定例

\\\python
# カスタムプロジェクト (CONFIG_HOOK)
class MyProjectConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        self.postgres.database = "myproject"
        
        # pgAdmin 有効化
        self.pgadmin.container.enabled = True
        self.pgadmin.email = "admin@myproject.local"
        self.pgadmin.password = "secure_password"
        self.pgadmin.container.host_port = 5051
\\\

### 生成される docker-compose.yml（pgAdmin 有効時）

pgAdmin が有効な場合、以下のサービスが生成されます:

\\\yaml
services:
  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: myproject_pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@myproject.local
      PGADMIN_DEFAULT_PASSWORD: secure_password
    ports:
      - "5051:80"
    volumes:
      - myproject_pgadmin_data:/var/lib/pgadmin
    depends_on:
      postgres:
        condition: service_healthy
\\\

### 特徴

- ✅ デフォルト無効 - 既存プロジェクト非影響
- ✅ CONFIG_HOOK でカスタマイズ可能
- ✅ PostgreSQL と同一設計パターン
- ✅ depends_on で起動順序制御済み
- ✅ プロジェクトごとに独立した pgAdmin instance
