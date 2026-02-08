# superpowers-tui

Terminal dashboard for monitoring Claude Code superpowers skill usage.

## Commands
- `uv run python -m superpowers_dashboard` — run the dashboard
- `uv run pytest` — run tests
- `uv run pytest tests/test_file.py -x` — run a specific test file

## Architecture
- `src/superpowers_dashboard/` — all source code
- `watcher.py` — JSONL parser and session discovery (the data layer)
- `app.py` — Textual app, layout, polling loop, UI refresh
- `widgets/` — individual panel widgets (skill_list, workflow, costs_panel, activity, hooks_panel)
- `registry.py` — reads skill definitions from superpowers plugin
- `costs.py` — token-to-cost calculation
- `config.py` — pricing config with TOML override

## Key Patterns
- SessionParser processes JSONL lines incrementally (streaming, not batch)
- Polling is 500ms interval on the latest session file
- All state lives in SessionParser; widgets are stateless renderers
- Subagent JSONL files are at {session-id}/subagents/agent-{id}.jsonl

## Gotchas
- Token accumulation attributes to active skill or overhead — no skill means overhead
- Claude's project dir naming: replaces / with - in the CWD path
- Skill confirmation requires an isMeta user entry after the Skill tool_use
