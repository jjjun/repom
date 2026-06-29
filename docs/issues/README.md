# Issue Tracker (issuekit, API-backed)

Issue lifecycle for this repository lives in the issuekit mine-py API, project
`repom`. There is no local issue tracker anymore: the `active/`, `completed/`,
and `indexes/` trees were retired. The API allocates issue ids and owns the
claim, review, approval, and completion transitions.

The workflow steps are owned by issuekit and are the single source of truth. Run
`issuekit protocol --role <role>` (or use the MCP `get_protocol` tool). Do not
duplicate the steps here.

## Configuration

- `[tool.issuekit] project = "repom"` is committed in `pyproject.toml`.
- `ISSUEKIT_API_URL` (and credentials) come from the environment. Run
  `issuekit login` once to cache a token.

## Common commands

```powershell
issuekit info                 # tracker status for project=repom
issuekit queue                # claimable / review queue
issuekit author --title "Short title" --body-file issue.md --priority medium --agent codex
issuekit implement <id> --agent <name>
issuekit approve <id> --reviewer <name> --verification "uv run pytest"
```

The API allocates the issue id (`repom#<id>`); do not create files or count ids
by hand. Issue text is English ASCII.

## This directory now

Only `docs/issues/incoming/` remains: the local inbox for cross-project
proposals (`issuekit propose --to <repo>`), which are still file-based until the
proposal flow is migrated. Adopt one with `issuekit adopt <file>` to create an
API issue.
