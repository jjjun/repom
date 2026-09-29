# Issue tracking

Repom issues live in the issuekit API under `project = "repom"`. This
directory contains this pointer only; do not store local issue files or
indexes here.

## Quick start for agents

Use the issuekit CLI or MCP tools for issue status and current workflow
instructions:

```bash
issuekit info
issuekit protocol --role <role>
```

The issuekit API is the source of truth for issue text and lifecycle state.
Follow the cross-project proposal flow in [AGENTS.md](../../AGENTS.md) when a
change belongs to another project.
