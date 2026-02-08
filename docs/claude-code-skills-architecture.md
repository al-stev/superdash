# Claude Code Skills Architecture: A Complete Reference

How skills, hooks, subagents, and enforcement work in Claude Code, with specific focus on the superpowers plugin ecosystem.

## The Three Layers of Influence

Claude Code provides three mechanisms to shape agent behavior, in descending order of reliability:

### Layer 1: Hooks (Mechanical)

Hooks fire on specific events and inject text into context or block actions. They cannot be rationalized away by the model.

**Available hook events:**

| Event | When it fires | Can block? | Available in subagents? |
|-------|--------------|------------|------------------------|
| `SessionStart` | Session begins (startup, resume, clear, compact) | No | No |
| `SessionEnd` | Session ends | No | No |
| `UserPromptSubmit` | Every user message | Yes (exit 2) | No |
| `PreToolUse` | Before any tool call | Yes (exit 2) | Only if defined in subagent frontmatter |
| `PostToolUse` / `ToolResult` | After tool completes | No | Only if defined in subagent frontmatter |
| `Stop` | Agent wants to stop | Yes (exit 2) | Converted to `SubagentStop` in subagent frontmatter |
| `SubagentStop` | Subagent wants to stop | Yes (exit 2) | N/A (fires in parent) |
| `SubagentStart` | Subagent spawned | No, but can inject `additionalContext` | N/A (fires in parent) |
| `PreCompact` | Before context compaction | No | No |
| `Notification` | On notifications | No | No |

**Where hooks are defined:**

1. **Plugin `hooks/hooks.json`** — ships with a plugin, applies when plugin is enabled
2. **`~/.claude/settings.json`** — user-level, applies to all projects
3. **`.claude/settings.json`** — project-level (permissions only, not hooks)
4. **Subagent frontmatter** — hooks scoped to that subagent's lifetime

**Hook output format** (JSON to stdout):

```json
{
  "hookSpecificOutput": {
    "additionalContext": "Text injected into the conversation"
  }
}
```

Exit code 0 = success, exit code 2 = block the action, other = warning.

**Key limitation:** `UserPromptSubmit` hooks are more effective than `SessionStart` because they reinforce on every message rather than once at the start. SessionStart context fades as conversation grows and gets compacted.

### Layer 2: CLAUDE.md (Persistent Instructions)

CLAUDE.md files are loaded into every conversation's context, including subagents. They are strong but advisory — the model can choose to weight them less heavily.

**Loading order (all are loaded, later ones can override):**

1. `~/.claude/CLAUDE.md` — global, all projects
2. `./CLAUDE.md` — project root
3. `./.claude/CLAUDE.md` — project .claude directory
4. Nested `CLAUDE.md` files in subdirectories (loaded when files in that directory are referenced)

**Key property for enforcement:** Subagents receive CLAUDE.md even though they don't receive SessionStart hook context. This makes CLAUDE.md the only reliable way to influence subagent behavior without preloading skills in frontmatter.

### Layer 3: Skill Descriptions (Weakest)

Skills are listed in the system-reminder with their name and description. The model must choose to invoke them via the Skill tool. This is the current primary enforcement mechanism for superpowers, and it is the weakest.

**How skills work mechanically:**

1. Skill descriptions appear in the system-reminder (subject to a 15,000-character budget — skills beyond this are silently dropped)
2. Claude decides whether to invoke a skill
3. If invoked, the `Skill` tool reads the `SKILL.md` file, strips YAML frontmatter, performs argument substitution, and returns the content as tool output
4. Claude then follows (or ignores) the instructions

**The budget problem:** Claude Code has a default 15,000-character budget for skill descriptions in the system prompt. If total descriptions exceed this, skills are silently dropped. Workaround: `SLASH_COMMAND_TOOL_CHAR_BUDGET=30000 claude`.

## Subagents

### What Subagents Receive

| Context element | Inherited? | Notes |
|----------------|-----------|-------|
| System prompt | No | Gets its own prompt from Task description or subagent markdown body |
| CLAUDE.md | Yes | All levels loaded |
| Conversation history | No | Starts fresh |
| Skill descriptions | Yes | Visible in system-reminder |
| Full skill content | Only if preloaded | Must be listed in subagent's `skills:` frontmatter |
| SessionStart hook context | No | This is the enforcement gap (superpowers issue #237) |
| Hook-injected context | No | Parent session hooks don't fire in subagents |
| Permissions | Yes | Inherited from parent |
| Task tool | No | Subagents cannot spawn subagents |

### Preloading Skills into Subagents

For custom subagent definitions (in YAML frontmatter):

```yaml
---
name: my-subagent
skills:
  - test-driven-development
  - systematic-debugging
---
```

The full content of listed skills is injected into the subagent's context. But this only works for subagent definitions you control, not ad-hoc `Task` tool calls.

### Subagent Hooks

Hooks defined in a subagent's YAML frontmatter fire during that subagent's execution. Project-level `PreToolUse` hooks in settings.json do NOT fire inside subagents.

### Subagent Transcripts

Stored at `~/.claude/projects/{project-dir-name}/{session-id}/subagents/agent-{agent-id}.jsonl`. These contain the full conversation within each subagent and persist independently of the main conversation's compaction.

## Skill Chaining

There is no first-class skill chaining mechanism. However:

- A loaded skill's text can instruct Claude to invoke another skill via the Skill tool (emergent chaining)
- Skills with `context: fork` run in an isolated subagent that cannot chain further (no Task tool)
- The system prompt says "Do not invoke a skill that is already running" but this is advisory, not enforced

## The Superpowers Enforcement Problem

### Current Mechanism

Superpowers uses a `SessionStart` hook (`hooks/session-start.sh`) that injects the full `using-superpowers` skill content wrapped in `<EXTREMELY_IMPORTANT>` tags. This skill contains:

- A "1% rule": if there's even a 1% chance a skill applies, invoke it
- A red flags table listing 11 rationalization patterns
- Explicit "this is not negotiable" language

### Why It Fails

1. **SessionStart fires once** and its context fades as the conversation grows
2. **Context compaction** may lose or weaken the enforcement text
3. **The model rationalizes** — diagnostic tests show Claude finding applicable skills and choosing not to use them because tasks "seemed straightforward"
4. **Subagents don't receive it** at all (issue #237)
5. **The skill scored 68/100** in a grading report (issue #202)

### Community Solutions (by effectiveness)

**`UserPromptSubmit` hook (most proven):**
Injects enforcement on every user message instead of just session start. Built by udecode/dotai, @umputun, and the Hyperpowers fork. Key insight from @zbeyens: "Prompt has much more weight than CLAUDE.md or a previous message (SessionStart), especially if the task looks trivial."

**RFC 2119 keywords in descriptions:**
Using MUST/SHOULD/MAY in skill descriptions gives Claude "much less room to argue" about skipping. Documented in ADR-006 from the human-in-loop project.

**`PreToolUse` guard (proposed, not built):**
Would block Edit/Write tool calls on production files unless TDD skill has been invoked. This is the only approach that could provide hard enforcement (~95% theoretical). Proposed in issue #384.

**CLAUDE.md with skill text:**
Pasting the `using-superpowers` content directly into CLAUDE.md ensures it's always in context, including in subagents. Brute force but effective as a fallback.

**Skill description budget increase:**
`SLASH_COMMAND_TOOL_CHAR_BUDGET=30000` prevents skills from being silently dropped.

### Estimated Compliance by Approach

| Approach | Estimated compliance |
|----------|---------------------|
| Skill descriptions alone (Layer 3) | ~50-60% |
| + SessionStart hook (current superpowers) | ~68-70% |
| + UserPromptSubmit hook | ~80-85% |
| + CLAUDE.md reinforcement | ~85-90% |
| + PreToolUse blocking guards | ~95% (theoretical) |
| + Anthropic platform-level mandatory skills | ~100% (not available) |

## Observability

### JSONL Session Files

The raw data source for monitoring. Located at `~/.claude/projects/{project-dir-name}/{session-id}.jsonl`.

Each line is a JSON object with a `type` field:

- `assistant`: Contains `content` array with `text` and `tool_use` blocks, plus `usage` (token counts) and `model` fields
- `user`: User messages, `isMeta` flag for system-generated responses (like skill confirmations)
- `system`: Events including `compact_boundary`, `microcompact_boundary`, `local_command` (for /clear), `turn_duration`

Subagent transcripts are separate files in a `subagents/` subdirectory.

### OpenTelemetry

Claude Code has native OTEL support:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp  # or prometheus, console
export OTEL_LOGS_EXPORTER=otlp     # or console
```

Available metrics include session counts, token usage, cost, lines of code, and tool decisions. Events include skill invocations (with `skill_name` when `OTEL_LOG_TOOL_DETAILS=1`).

### Hook-Based Observability

The claude-code-hooks-multi-agent-observability project demonstrates a full pipeline: hooks capture events, POST to a Bun server, store in SQLite, stream via WebSocket to a Vue dashboard.

## Key References

- [Superpowers issue #54: Skills don't auto trigger](https://github.com/obra/superpowers/issues/54) — canonical enforcement discussion
- [Superpowers issue #237: Subagents miss context](https://github.com/obra/superpowers/issues/237)
- [Superpowers issue #384: TDD enforcement hook proposal](https://github.com/obra/superpowers/issues/384)
- [Superpowers issue #202: Skill grading report (68/100)](https://github.com/obra/superpowers/issues/202)
- [Blog: Claude Code skills not triggering](https://blog.fsck.com/2025/12/17/claude-code-skills-not-triggering/) — budget problem
- [udecode/dotai UserPromptSubmit implementation](https://github.com/udecode/dotai)
- [Hyperpowers fork](https://github.com/withzombies/hyperpowers) — UserPromptSubmit + Stop hooks
- [Mandatory skill activation gist](https://gist.github.com/umputun/570c77f8d5f3ab621498e1449d2b98b6)
- [ADR-006: RFC 2119 keywords](https://github.com/deepeshBodh/human-in-loop/blob/main/docs/decisions/006-rfc2119-skill-auto-invocation.md)
- [Claude Code hooks docs](https://code.claude.com/docs/en/hooks)
- [Claude Code skills docs](https://code.claude.com/docs/en/skills)
- [Claude Code subagents docs](https://code.claude.com/docs/en/sub-agents)
- [Claude Code monitoring docs](https://code.claude.com/docs/en/monitoring-usage)
