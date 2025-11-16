# Ideas Directory

## Overview

This directory contains **feature ideas** and **enhancement proposals** for the repom project. Ideas documented here are in the conceptual or planning stage.

## 📏 Document Guidelines

### STRICT LIMITS
- **Total length**: 250-350 lines maximum
- **Code examples**: 5-10 lines maximum per example
- **Approaches**: Present ONE recommended approach only

### What to EXCLUDE
❌ Complete code implementations (will become outdated)  
❌ Multiple detailed approach comparisons (choose one)  
❌ Deep technical implementation details (belongs in code/comments)  
❌ Redundant code examples (one per concept maximum)  
❌ "Additional Ideas" sections (create separate docs)

### What to INCLUDE
✅ Problem definition and scope  
✅ Impact on existing commands/features  
✅ Constraints (backward compatibility, etc.)  
✅ Validation criteria  
✅ Conceptual explanations with minimal code

## 📋 Required Template

**Copy this template when creating new idea documents**:

```markdown
# [Feature Name]

## ステータス
- **段階**: アイディア
- **優先度**: 高/中/低
- **複雑度**: 高/中/低
- **作成日**: YYYY-MM-DD
- **最終更新**: YYYY-MM-DD

## 概要 (2-3 sentences)
Brief description of what this idea proposes.

## モチベーション

### 現在の問題 (50-80 lines)
- What is broken or missing?
- Which commands/features are affected?
- Example error cases (brief, no full code)

### 理想の動作 (30-50 lines)
- What should happen instead?
- Key benefits (bullet points)
- ONE simple usage example (5 lines max)

## ユースケース (60-80 lines)

[3-5 use cases, each with]:
- Brief description (2-3 sentences)
- Minimal code example (3-5 lines)
- Why it matters

## 推奨アプローチ (50-70 lines)

**ONE approach only**. Include:
- Why this approach?
- Key concepts (explain, don't code)
- Trade-offs
- Integration points

❌ DO NOT include:
- Complete implementations
- Multiple approach comparisons
- Deep technical details

## 統合ポイント (30-50 lines)

- Affected files (list only)
- Existing features impacted
- Backward compatibility considerations

## 次のステップ (40-60 lines)

### 実装優先順位
#### Phase 1: 基本機能（高優先度）
- [ ] Implementation tasks

#### Phase 2: 統合とドキュメント（中優先度）
- [ ] Integration tasks

#### Phase 3: 高度な機能（低優先度）
- [ ] Advanced features

### 検証項目
- [ ] Validation checklist

### 実装決定事項
1. Decision 1
2. Decision 2

## 解決すべき質問 (20-40 lines)

- Key decisions needed
- Open questions
- Risks to consider

## 関連ドキュメント (10-20 lines)

- Links to related files
```

**TOTAL TARGET**: 250-350 lines

## 💡 Usage Tips for AI Agents

When creating an idea document:

1. **Start with outline** → Present structure first, get user approval
2. **Confirm scope** → Ask if full detail needed or concise version
3. **Write in phases** → Get feedback per section (avoid 800-line dumps)
4. **Check length** → Report line count at end
5. **Be concise** → Prefer explanation over code

### Red Flags 🚩
If you're writing:
- Complete implementations → **STOP**, ask user
- 3+ approaches in detail → **Choose ONE**
- Code examples > 10 lines → **Simplify or remove**
- Similar code blocks → **Consolidate**

## Idea Lifecycle

```
docs/ideas/         → Initial concept and exploration
    ↓
docs/research/      → Technical investigation and feasibility study
    ↓
docs/issue/active/  → Concrete implementation plan
    ↓
docs/issue/completed/ → Implementation complete
```

## 🎯 User Instruction Template

When requesting an idea document from AI, use:

```
Please create an idea document following the template in docs/ideas/README.md.

Requirements:
- Follow the template structure exactly
- Keep total length under 350 lines
- Use conceptual explanations, not code implementations
- Present ONE recommended approach only

[Attach: docs/ideas/README.md]
```

## Current Ideas

### 1. Schema Validation Command
**File**: `schema_validation_command.md`
**Purpose**: CLI command to validate all model schemas before deployment
**Priority**: Medium
**Status**: Idea stage

### 2. Schema File Generation
**File**: `schema_file_generation.md`
**Purpose**: Export Pydantic schemas to JSON Schema files for API documentation
**Priority**: Low
**Status**: Idea stage

### 3. API Type Resolution
**File**: `api_type_resolution.md`
**Purpose**: Automatic type resolution in FastAPI/Flask response models
**Priority**: Low
**Status**: Idea stage

## Contributing Ideas

### For Project Contributors
1. Create a new markdown file in `docs/ideas/` using the template
2. Use a descriptive filename (e.g., `caching_layer_implementation.md`)
3. Fill out all sections with as much detail as possible
4. Link to related research or issues if applicable
5. Commit with message: `docs(ideas): Add [idea title]`

### For External Contributors
1. Open a GitHub Discussion in the "Ideas" category
2. Use the idea template in your discussion post
3. Maintainers will create a corresponding file in `docs/ideas/` if appropriate

## Idea Evaluation Criteria

When evaluating ideas, consider:
- **Value**: Does it solve a real problem for users?
- **Scope**: Is it aligned with repom's purpose as a shared foundation?
- **Complexity**: Is the implementation effort justified?
- **Compatibility**: Does it maintain backward compatibility?
- **Maintenance**: Can it be maintained long-term?

## Moving Ideas Forward

### To Research Phase
When an idea requires technical investigation:
1. Create detailed analysis in `docs/research/[idea_name].md`
2. Update idea status to "Research"
3. Link research document in the idea file

### To Implementation Phase
When an idea is ready for implementation:
1. Create issue file in `docs/issue/active/XXX_[idea_name].md`
2. Update status to "Planning" or "Ready for Implementation"

## Archived Ideas

Ideas that are no longer relevant or have been superseded can be archived by updating their status in the document itself.

## Questions?

For questions about the ideas process, refer to:
- `docs/issue/README.md` - Issue management workflow
- `docs/research/README.md` - Research documentation guidelines
- Project maintainers via GitHub Discussions
