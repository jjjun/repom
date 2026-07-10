# GitHub Copilot Instructions for repom

## Project Context

This is **repom** - a shared SQLAlchemy foundation package for Python projects.

## Code Style Guidelines

### Imports
- Always use absolute imports: `from repom.base_model import BaseModel`
- Never use old package name `mine_db`

### Database Operations
- Use `BaseRepository` methods instead of raw SQLAlchemy queries
- Always work within transaction contexts using `db_session`

### Testing
- Run tests with: `uv run pytest tests/unit_tests`
- Use fixtures from `tests/db_test_fixtures.py`
- Test scope: `function` (default), `module`, or `session`

### Configuration
- Use environment variable: `EXEC_ENV` (dev/test/prod)
- Config class: `MineDbConfig` from `repom.config`
- Database files: `db.dev.sqlite3`, `db.test.sqlite3`, `db.sqlite3`

### Commands
- Always use `uv run` prefix for commands
- Migration: `uv run alembic upgrade head`
- DB creation: `uv run db_create`
- Tests: `uv run pytest tests/unit_tests`

## VS Code Tasks Available

- `🧪Pytest/unit_tests` - Run unit tests
- `🧪Pytest/all` - Run all tests
- `🤖uv/scaffold` - Scaffold new models
- `💾uv/db_backup` - Backup database
- `🧬Alembic/migration/all` - Run migrations for all environments

## Common Patterns

### Creating a Model
```python
from repom.base_model import BaseModel
from sqlalchemy import Column, Integer, String

class MyModel(BaseModel):
    __tablename__ = 'my_table'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
```

### Using Repository
```python
from repom.base_repository import BaseRepository

class MyRepository(BaseRepository[MyModel]):
    pass

repo = MyRepository()
item = repo.get_by_id(1)
items = repo.get_by(name="example")
```

## Important Notes

- This is a **shared package** - keep it framework-agnostic
- App-specific models should be in consuming projects
- Always test changes with `uv run pytest`
- Keep dependencies minimal

## 📚 重要なドキュメントファイル

### Core Documentation (必ず参照)

- **README.md**: プロジェクトの基本情報、セットアップ、コマンドリファレンス
- **AGENTS.md**: プロジェクト構造、技術スタック、開発ガイドライン

### Feature-Specific Guides (機能実装時に参照)

#### BaseModelAuto & スキーマ自動生成
**ファイル**: `docs/guides/base_model_auto_guide.md`

**対象機能**:
- BaseModelAuto による Pydantic スキーマ自動生成
- get_create_schema() / get_update_schema() / get_response_schema()
- @response_field デコレータの使い方
- 前方参照の解決方法
- スキーマ生成ルール表
- FastAPI 統合の実装例

**使用タイミング**:
- SQLAlchemy モデルから Pydantic スキーマを生成する場合
- FastAPI のエンドポイントで response_model を定義する場合
- Create/Update/Response スキーマが必要な場合

**ユーザーへの指示例**:
```
「docs/guides/base_model_auto_guide.md を見て、
 User モデルに FastAPI スキーマを追加してください」
```

---

#### BaseRepository, FilterParams & Utilities
**ファイル**: `docs/guides/repository_and_utilities_guide.md`

**対象機能**:
- BaseRepository（データアクセス層）
- FilterParams（検索パラメータ）
- as_query_depends()（FastAPI 統合）
- auto_import_models（モデル自動インポート）

**使用タイミング**:
- データベース操作を実装する場合
- 検索・フィルタ機能を実装する場合
- FastAPI のクエリパラメータを型安全に扱いたい場合
- モデルの自動インポートを設定する場合

**ユーザーへの指示例**:
```
「docs/guides/repository_and_utilities_guide.md を見て、
 FilterParams を使った検索機能を実装してください」
```

---

### Technical Deep Dive (トラブルシューティング時に参照)

- **docs/technical/get_response_schema_technical.md**: スキーマ生成の内部実装
- **docs/technical/ai_context_management.md**: AI コンテキスト管理の解説

### Issue Tracking

- Issues live in the **issuekit API** (`project = "repom"`); there is no local
  `docs/issue` / `docs/issues` tracker.
- Run `issuekit protocol --role <role>` (or the MCP `get_protocol` tool) for the
  authoritative workflow steps.

---

## 🤖 AI エージェント作業パターン

### パターン1: BaseModelAuto を使ったモデル作成

```
1. README.md を読んで基本を理解
2. docs/guides/base_model_auto_guide.md を読んで詳細を把握
3. 実装開始
```

**ユーザーからの指示**:
```
「docs/guides/base_model_auto_guide.md を参考にして、
 Task モデルに Create/Update/Response スキーマを追加してください」
```

### パターン2: FastAPI エンドポイント実装

```
1. README.md でプロジェクト構造を確認
2. docs/guides/base_model_auto_guide.md でスキーマ生成方法を確認
3. docs/guides/repository_and_utilities_guide.md で検索パラメータ実装を確認
4. 実装開始
```

**ユーザーからの指示**:
```
「docs/guides/base_model_auto_guide.md と
 docs/guides/repository_and_utilities_guide.md を参考にして、
 Task の CRUD エンドポイントと検索機能を実装してください」
```

### パターン3: トラブルシューティング

```
1. README.md のトラブルシューティングセクションを確認
2. 問題が複雑な場合は docs/technical/ を参照
3. Issue として記録 (issuekit author)
```

## 📚 Documentation Structure & AI Workflow

### Directory Organization

```
docs/
├── guides/             # 📘 Usage guides (testing, repository, model, ...)
├── ideas/              # 💡 Feature proposals and enhancement ideas
└── technical/          # 📖 Implementation details and constraint investigations
```

Issue tracking is **not** file-based: issues live in the issuekit API
(`project = "repom"`), not under `docs/`.

### 🤖 AI Agent Collaborative Workflow

#### When User Reports a Problem or Bug

1. **Clarify & Confirm**
   - Ask clarifying questions to fully understand the issue
   - Confirm scope, expected behavior, and actual behavior

2. **Author the Issue via issuekit**
   - `issuekit author --title "..." --body-file FILE --priority <high|medium|low> --agent <name>`
   - The API allocates the id (`repom#<id>`); do not create files or number ids by hand.
   - Issue text is English ASCII.

3. **Work Through the Lifecycle**
   - author -> claim (`claim_next_task` or `issuekit implement <id> --agent <name>`)
     -> `submit_for_review` -> `approve` / `request_changes`.
   - Implement the solution, run tests, and validate the fix.

4. **Complete via issuekit**
   - Reviewer `approve` completes the issue; `request_changes` returns it to the
     implementer. There is no manual file move or index update.

#### When User Proposes a Feature Idea

1. **Document the Idea**
   - Use template from `docs/ideas/README.md`
   - Include: Overview, Motivation, Use Cases, Approaches, Technical Considerations

2. **Create Idea File**
   ```bash
   docs/ideas/feature_name.md
   ```

3. **Discuss Feasibility**
   - Evaluate complexity, value, and alignment with project goals
   - Recommend next steps: research, prototype, or implement

4. **Lifecycle Progression**
   ```
   ideas/ → research/ (if needs investigation)
           → issue/backlog/ (if ready to implement)
   ```

#### When Technical Investigation is Needed

1. **Create Research Document**
   ```bash
   docs/research/topic_name.md
   ```

2. **Include Comprehensive Analysis**
   - Current state and problems
   - Multiple approaches with pros/cons
   - Implementation roadmap
   - Security, performance, compatibility considerations

3. **Link to Related Issues**
   - Reference related idea or issue files
   - Update issue files to reference research

### 📋 Issue Lifecycle (issuekit API)

```
User reports problem
    ↓
AI confirms understanding
    ↓
issuekit author --title "..." --body-file FILE --priority <...> --agent <name>
    ↓
claim (claim_next_task / issuekit implement <id> --agent <name>)
    ↓
Work on solution together (testing, debugging, implementing)
    ↓
submit_for_review
    ↓
Reviewer: approve (completes) / request_changes (returns to implementer)
```

See `issuekit protocol --role <role>` for the authoritative steps.

### 💡 Idea Lifecycle

```
User proposes feature
    ↓
AI helps document (use template)
    ↓
Create: docs/ideas/feature_name.md
    ↓
Evaluate feasibility
    ↓
If needs investigation → docs/technical/topic.md
If ready → issuekit author (new active issue)
```

### 🔄 Completion Triggers

When the user says any of these phrases, drive the issue to completion through
issuekit (submit for review, then approve):
- "完了しました" / "完了した" / "完了です"
- "終わりました" / "終わった"
- "This issue is done" / "This is complete"
- "Issue完了" / "これで完了"
- "解決しました" / "解決した"

**Actions:**
1. `submit_for_review` the implementing issue.
2. Reviewer `approve` completes it (or `request_changes` to iterate).
3. Confirm completion to the user.

### 📝 Documentation Templates

**Issue Template** (use for problems/bugs):
```markdown
# Issue: [Title]

## Status
- **Created**: YYYY-MM-DD
- **Priority**: High/Medium/Low
- **Complexity**: High/Medium/Low

## Problem Description
[Clear description of the issue]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Solution
[Implementation details]

## Test Results
[Test outcomes and validation]

## Related Documents
[Links to technical docs, research, etc.]
```

**Idea Template**: Use template from `docs/ideas/README.md`

**Technical Investigation**: Write findings under `docs/technical/`

### 🎯 Best Practices for AI Agents

1. **Always confirm** before creating documentation
2. **Track issues in issuekit** (`project = "repom"`), not in local files
3. **Let the API allocate ids** (`repom#<id>`); never number issues by hand
4. **Link related documents** (idea ↔ technical guide)
5. **Commit frequently** with descriptive messages
6. **Ask clarifying questions** rather than making assumptions
7. **Validate with tests** before submitting for review
8. **Drive completion through issuekit** when the user confirms an issue is done
