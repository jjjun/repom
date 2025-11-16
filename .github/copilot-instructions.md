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
- Run tests with: `poetry run pytest tests/unit_tests`
- Use fixtures from `tests/db_test_fixtures.py`
- Test scope: `function` (default), `module`, or `session`

### Configuration
- Use environment variable: `EXEC_ENV` (dev/test/prod)
- Config class: `MineDbConfig` from `repom.config`
- Database files: `db.dev.sqlite3`, `db.test.sqlite3`, `db.sqlite3`

### Commands
- Always use `poetry run` prefix for commands
- Migration: `poetry run alembic upgrade head`
- DB creation: `poetry run db_create`
- Tests: `poetry run pytest tests/unit_tests`

### Alembic Configuration
- **Migration file location**: Controlled by `alembic.ini` only
- **repom**: `version_locations = alembic/versions`
- **External projects**: Must create `alembic.ini` with `version_locations = %(here)s/alembic/versions`
- **Key point**: `alembic.ini` is the single source of truth for both file creation and execution

**For external projects (e.g., mine-py)**:
```ini
# mine-py/alembic.ini
[alembic]
script_location = submod/repom/alembic
version_locations = %(here)s/alembic/versions
```

## VS Code Tasks Available

- `⭐Pytest/unit_tests` - Run unit tests
- `🧪Pytest/all` - Run all tests
- `🤖Poetry/scaffold` - Scaffold new models
- `💾Poetry/db_backup` - Backup database
- `Alembic/migration/all` - Run migrations for all environments

## Common Patterns

### Creating a Model
```python
from repom.base_model import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

class MyModel(BaseModel):
    __tablename__ = 'my_table'
    
    # use_id=True がデフォルトなので id は自動追加される
    name: Mapped[str] = mapped_column(String(100))
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
- Always test changes with `poetry run pytest`
- Keep dependencies minimal

## � Documentation Guidelines

### When Creating Idea Documents (docs/ideas/)

**MUST follow** `docs/ideas/README.md` template:
- **Length limit**: 250-350 lines maximum
- **Code examples**: 5-10 lines max per example
- **Approaches**: ONE recommended approach only
- **Focus**: Problem definition and solution approach, NOT implementation details

**Before writing**:
1. Read `docs/ideas/README.md` template
2. Present outline first, get user approval
3. Write in sections, not all at once
4. Report line count at end

**Red Flags 🚩** - STOP and ask user if you're writing:
- Complete implementations (will become outdated)
- 3+ approaches in detail (choose ONE)
- Code examples > 10 lines (simplify)
- Similar code blocks (consolidate)

### When Creating Issue Documents (docs/issue/)

Follow the workflow in `docs/issue/README.md`:
- Problem description → Expected behavior → Solution → Test results
- Mark completed issues automatically when user confirms
- Use sequential numbering (001, 002, ...)

## �📚 重要なドキュメントファイル

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

### Technical Deep Dive

- **docs/technical/alembic_version_locations_limitation.md**: Alembic の制約と将来的な改善案
- **docs/technical/get_response_schema_technical.md**: スキーマ生成の内部実装

### Issue Tracking

- **docs/issue/README.md**: Issue 管理システムの使い方

---

## 📚 Documentation Structure & AI Workflow

### Directory Organization

```
docs/
├── guides/             # 📘 Usage guides (concise, practical, for teaching other AI agents)
├── ideas/              # 💡 Feature proposals and enhancement ideas
├── research/           # 🔬 Investigation for ideal implementations (future improvements)
├── technical/          # 🔧 Implementation decisions and constraints (for AI improvement work)
└── issue/              # 📋 Problem tracking and resolution
    ├── README.md      # Issue index (MUST update when moving files)
    ├── active/        # 🚧 Planned and active work (backlog + in_progress merged)
    └── completed/     # ✅ Resolved issues (XXX_name.md with sequential numbering)
```

### 🤖 AI Agent Collaborative Workflow

#### When User Reports a Problem or Bug

1. **Clarify & Confirm**
   - Ask clarifying questions to fully understand the issue
   - Confirm scope, expected behavior, and actual behavior
   - Get user approval before creating documentation

2. **Create Issue File**
   ```markdown
   # Location: docs/issue/active/XXX_issue_name.md
   # Use descriptive snake_case naming
   ```

3. **Update Issue Index**
   - Add entry to `docs/issue/README.md` in appropriate section
   - Include status, overview, and file path

4. **Work Together**
   - Implement solution collaboratively
   - Update issue file with progress and findings
   - Run tests and validate fix

5. **Mark as Complete** (when user confirms "完了" / "done" / "finished")
   - **AUTOMATICALLY** move file: `active/XXX_*.md` → `completed/NNN_*.md`
   - Assign sequential number (001, 002, 003...)
   - **AUTOMATICALLY** update `docs/issue/README.md`:
     * Remove from "📝 実装予定・作業中の Issue"
     * Add to "📋 完了済み Issue" with summary
   - Commit with message: `docs(issue): Complete issue #NNN - [title]`

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
           → issue/active/ (if ready to implement)
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

### 📋 Issue Lifecycle (Automated)

```
User reports problem
    ↓
AI confirms understanding
    ↓
Create: active/XXX_name.md
    ↓
Update: docs/issue/README.md (add to appropriate section)
    ↓
Work on solution together (testing, debugging, implementing)
    ↓
User says "完了" / "done" / "finished"
    ↓
AI AUTOMATICALLY:
  1. Move: active/XXX_name.md → completed/NNN_name.md
  2. Update: docs/issue/README.md (move entry to completed section)
  3. Commit: "docs(issue): Complete issue #NNN - [title]"
```

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
If needs research → docs/research/topic.md
If ready → docs/issue/active/XXX_name.md
```
### 🔄 Automatic Completion Triggers

When user says any of these phrases, **AUTOMATICALLY** complete the issue:
- "完了しました" / "完了した" / "完了です"
- "終わりました" / "終わった"
- "This issue is done" / "This is complete"
- "Issue完了" / "これで完了"
- "解決しました" / "解決した"

**Automatic Actions:**
1. Move file to `completed/` with next sequential number
2. Update `docs/issue/README.md` (remove from active, add to completed)
3. Git commit with descriptive message
4. Confirm completion to user

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

**Research Template**: Use guidelines from `docs/research/README.md`

### 🎯 Best Practices for AI Agents

1. **Always confirm** before creating documentation
2. **Update indexes** (README.md files) when moving/creating files
3. **Use sequential numbering** for completed issues (001, 002, ...)
4. **Link related documents** (issue ↔ research ↔ technical)
5. **Commit frequently** with descriptive messages
6. **Ask clarifying questions** rather than making assumptions
7. **Validate with tests** before marking issues complete
8. **Automatically handle completion** when user confirms issue is done
