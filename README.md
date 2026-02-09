# superdash

Terminal dashboard for monitoring [Claude Code](https://docs.anthropic.com/en/docs/claude-code) sessions with [Superpowers](https://github.com/anthropics/claude-code-plugins/tree/main/superpowers) skills.

Read-only. No hooks, no configuration required. Just run it alongside Claude Code.

## Install

```bash
uv tool install .
```

Or for development:

```bash
git clone <repo-url>
cd superpowers-tui
uv sync
uv run superdash
```

## Usage

```bash
# Monitor sessions for the current directory
superdash

# Monitor a specific project
superdash --project-dir /path/to/project
```

### Panels

| Panel | Location | Shows |
|-------|----------|-------|
| **Skills** | Left | All registered skills with active/used/available status |
| **Hooks** | Left | Configured hook events and their scripts |
| **Workflow** | Center | Timeline of skill invocations with tokens, cost, duration |
| **Stats** | Right | Session cost, context usage, compactions, tool counts, per-model breakdown |

### Keybindings

- `q` -- Quit
- `t` -- Toggle theme (Terminal / Mainframe)

## How It Works

Superdash reads Claude Code session files (`~/.claude/projects/<project>/*.jsonl`) and polls for new data every 500ms. It detects skill invocations, token usage, compactions, and subagent dispatches from the JSONL stream.

Session files are matched to the current working directory -- each `superdash` instance only shows data for its own project.
