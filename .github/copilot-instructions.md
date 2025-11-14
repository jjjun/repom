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
- Always test changes with `poetry run pytest`
- Keep dependencies minimal

## 📚 Documentation Structure & AI Workflow

### Directory Organization

```
docs/
├── issue/              # Problem tracking and resolution
│   ├── README.md      # Issue index (MUST update when moving files)
│   ├── completed/     # ✅ Resolved issues (XXX_name.md with sequential numbering)
│   ├── in_progress/   # 🚧 Active work
│   └── backlog/       # 📝 Planned issues
├── research/           # 🔬 Technical investigation and feasibility studies
├── ideas/              # 💡 Feature proposals and enhancement ideas
└── technical/          # 📖 API references and implementation guides
```

### 🤖 AI Agent Collaborative Workflow

#### When User Reports a Problem or Bug

1. **Clarify & Confirm**
   - Ask clarifying questions to fully understand the issue
   - Confirm scope, expected behavior, and actual behavior
   - Get user approval before creating documentation

2. **Create Issue File**
   ```markdown
   # Choose location based on urgency:
   # - Immediate work: docs/issue/in_progress/XXX_issue_name.md
   # - Future work: docs/issue/backlog/XXX_issue_name.md
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
   - **AUTOMATICALLY** move file: `in_progress/XXX_*.md` → `completed/NNN_*.md`
   - Assign sequential number (001, 002, 003...)
   - **AUTOMATICALLY** update `docs/issue/README.md`:
     * Remove from "🚧 作業中の Issue"
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

### 📋 Issue Lifecycle (Automated)

```
User reports problem
    ↓
AI confirms understanding
    ↓
Create: backlog/XXX_name.md OR in_progress/XXX_name.md
    ↓
Update: docs/issue/README.md (add to appropriate section)
    ↓
Work on solution together (testing, debugging, implementing)
    ↓
User says "完了" / "done" / "finished"
    ↓
AI AUTOMATICALLY:
  1. Move: in_progress/XXX_name.md → completed/NNN_name.md
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
If ready → docs/issue/backlog/XXX_name.md
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
2. Update `docs/issue/README.md` (remove from in_progress, add to completed)
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
