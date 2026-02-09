# Fixes & Model Usage Tracking Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the clear-event mislabeling regression in the workflow timeline, and add per-model token/cost tracking to the stats panel.

**Architecture:** Modifications to existing modules — workflow widget fix, watcher enhancement for model accumulation, stats panel new section.

**Tech Stack:** Python 3.11+, Textual, existing test infrastructure (pytest)

---

### Task 1: Fix clear events mislabeled as COMPACTION in workflow timeline

The `format_compaction()` method in `workflow.py` only checks for "microcompaction" kind, so "clear" events fall through to the "COMPACTION" label. They should display as "CLEAR".

**Files:**
- Modify: `src/superpowers_dashboard/widgets/workflow.py`
- Modify: `tests/test_widget_workflow.py`

**Step 1: Write the failing test**

Add to `tests/test_widget_workflow.py`:

```python
def test_workflow_format_clear():
    """format_compaction renders clear events with CLEAR label."""
    w = WorkflowWidget()
    text = w.format_compaction(
        timestamp="2026-02-07T09:30:00.000Z",
        kind="clear",
        pre_tokens=0,
    )
    assert "CLEAR" in text
    assert "COMPACTION" not in text
    assert "09:30" in text
```

**Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_widget_workflow.py::test_workflow_format_clear -x
```

Expected: fails because "clear" currently gets the "COMPACTION" label.

**Step 3: Fix `format_compaction` in `workflow.py`**

Change the label logic in `format_compaction()` (around line 80):

```python
def format_compaction(self, timestamp: str, kind: str, pre_tokens: int) -> str:
    """Render a compaction event in the timeline."""
    time_str = _parse_time(timestamp) if timestamp else ""
    time_prefix = f"{time_str}  " if time_str else ""
    if kind == "microcompaction":
        label = "MICROCOMPACTION"
    elif kind == "clear":
        label = "CLEAR"
    else:
        label = "COMPACTION"
    return f"{time_prefix}   ── {label} ──  {pre_tokens:,} tok"
```

**Step 4: Run test, verify it passes**

```bash
uv run pytest tests/test_widget_workflow.py -x
```

Expected: all workflow tests pass.

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/widgets/workflow.py tests/test_widget_workflow.py
git commit -m "fix: label clear events correctly in workflow timeline"
```

---

### Task 2: Track per-model token and cost accumulation in the parser

The watcher's `SessionParser` currently accumulates tokens globally per-skill or as overhead. It does not track which model generated those tokens. We need a new data structure to accumulate tokens per model across the whole session.

**Files:**
- Modify: `src/superpowers_dashboard/watcher.py`
- Modify: `tests/test_watcher.py`

**Step 1: Write the failing test**

Add to `tests/test_watcher.py`:

```python
def test_parser_tracks_model_usage():
    """Parser accumulates tokens per model across all assistant messages."""
    parser = SessionParser()
    # Opus message
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "hello"}],
            "usage": {"input_tokens": 1000, "output_tokens": 200,
                      "cache_read_input_tokens": 500, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-09T10:00:00.000Z",
    }))
    # Haiku message
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-haiku-4-5-20251001",
            "content": [{"type": "text", "text": "hi"}],
            "usage": {"input_tokens": 300, "output_tokens": 50,
                      "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-09T10:01:00.000Z",
    }))
    # Another opus message
    parser.process_line(json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-6",
            "content": [{"type": "text", "text": "world"}],
            "usage": {"input_tokens": 800, "output_tokens": 150,
                      "cache_read_input_tokens": 200, "cache_creation_input_tokens": 0},
        },
        "timestamp": "2026-02-09T10:02:00.000Z",
    }))
    assert "claude-opus-4-6" in parser.model_usage
    assert "claude-haiku-4-5-20251001" in parser.model_usage
    opus = parser.model_usage["claude-opus-4-6"]
    assert opus["input_tokens"] == 1800  # 1000 + 800
    assert opus["output_tokens"] == 350  # 200 + 150
    assert opus["cache_read_tokens"] == 700  # 500 + 200
    haiku = parser.model_usage["claude-haiku-4-5-20251001"]
    assert haiku["input_tokens"] == 300
    assert haiku["output_tokens"] == 50
```

**Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_watcher.py::test_parser_tracks_model_usage -x
```

Expected: fails because `model_usage` attribute does not exist.

**Step 3: Add `model_usage` tracking to `SessionParser`**

In `watcher.py`, add to `__init__`:

```python
self.model_usage: dict[str, dict[str, int]] = {}
```

In `_accumulate_tokens()`, add after the existing accumulation logic:

```python
# Track per-model usage
if model:
    if model not in self.model_usage:
        self.model_usage[model] = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
    self.model_usage[model]["input_tokens"] += input_tok
    self.model_usage[model]["output_tokens"] += output_tok
    self.model_usage[model]["cache_read_tokens"] += cache_read
    self.model_usage[model]["cache_write_tokens"] += cache_write
```

**Step 4: Run test, verify it passes**

```bash
uv run pytest tests/test_watcher.py -x
```

**Step 5: Commit**

```bash
git add src/superpowers_dashboard/watcher.py tests/test_watcher.py
git commit -m "feat: track per-model token usage in session parser"
```

---

### Task 3: Display per-model usage in the stats panel

Add a "Models" section to the stats panel showing each model with its token count and cost.

**Files:**
- Modify: `src/superpowers_dashboard/widgets/costs_panel.py`
- Modify: `tests/test_widget_costs.py`
- Modify: `src/superpowers_dashboard/app.py`

**Step 1: Write the failing test**

Add to `tests/test_widget_costs.py`:

```python
def test_stats_widget_shows_model_usage():
    """Stats panel should display per-model token counts and costs."""
    w = StatsWidget()
    model_stats = [
        {"model": "opus", "input_tokens": 50000, "output_tokens": 10000, "cost": 4.50},
        {"model": "haiku", "input_tokens": 5000, "output_tokens": 1000, "cost": 0.08},
    ]
    text = w.format_model_usage(model_stats)
    assert "opus" in text
    assert "haiku" in text
    assert "$4.50" in text
    assert "$0.08" in text
```

**Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_widget_costs.py::test_stats_widget_shows_model_usage -x
```

**Step 3: Add `format_model_usage` to StatsWidget**

In `costs_panel.py`, add a method:

```python
def format_model_usage(self, model_stats: list[dict]) -> str:
    """Format per-model token and cost breakdown.

    Each entry: {"model": str, "input_tokens": int, "output_tokens": int, "cost": float}
    """
    if not model_stats:
        return ""
    lines = ["  Models:"]
    for m in model_stats:
        total_tok = m["input_tokens"] + m["output_tokens"]
        if total_tok >= 1000:
            tok_str = f"{total_tok / 1000:.1f}k"
            if tok_str.endswith(".0k"):
                tok_str = tok_str[:-3] + "k"
        else:
            tok_str = str(total_tok)
        lines.append(f"    {m['model']:<20} {tok_str:>6} tok  ${m['cost']:.2f}")
    return "\n".join(lines)
```

**Step 4: Wire it into `update_stats`**

Add an optional `model_stats` parameter to `update_stats()` and append the section after the subagent stats block:

```python
if model_stats:
    parts.append("")
    parts.append("  " + "─" * 38)
    parts.append(self.format_model_usage(model_stats))
```

**Step 5: Build model_stats in `app.py:_refresh_ui()`**

After the existing stats computation, before calling `stats_widget.update_stats()`:

```python
from superpowers_dashboard.costs import calculate_cost, resolve_model

# Build per-model stats
model_stats = []
for model_id, usage in self.parser.model_usage.items():
    model_name = resolve_model(model_id)
    cost = calculate_cost(
        model_name,
        usage["input_tokens"], usage["output_tokens"],
        usage["cache_read_tokens"], usage.get("cache_write_tokens", 0),
        pricing,
    )
    # Use short display name
    display_name = model_id.split("-")[1] if "-" in model_id else model_id
    model_stats.append({
        "model": display_name,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cost": cost,
    })
model_stats.sort(key=lambda m: -m["cost"])
```

Then pass `model_stats=model_stats` to `stats_widget.update_stats()`.

**Step 6: Run all tests**

```bash
uv run pytest -x
```

**Step 7: Commit**

```bash
git add src/superpowers_dashboard/widgets/costs_panel.py src/superpowers_dashboard/app.py tests/test_widget_costs.py
git commit -m "feat: display per-model token usage and cost in stats panel"
```

---

### Task 4: Include subagent model usage in per-model totals

Subagent transcripts use different models (e.g., haiku for quick tasks). The per-model stats should include tokens from subagent transcripts, not just the main session.

**Files:**
- Modify: `src/superpowers_dashboard/app.py`
- Modify: `tests/test_widget_costs.py`

**Step 1: Write the failing test**

Add to `tests/test_widget_costs.py`:

```python
def test_stats_widget_model_usage_with_multiple_entries():
    """Model usage should handle multiple models sorted by cost descending."""
    w = StatsWidget()
    model_stats = [
        {"model": "haiku", "input_tokens": 5000, "output_tokens": 1000, "cost": 0.08},
        {"model": "opus", "input_tokens": 50000, "output_tokens": 10000, "cost": 4.50},
        {"model": "sonnet", "input_tokens": 20000, "output_tokens": 5000, "cost": 1.20},
    ]
    text = w.format_model_usage(model_stats)
    # All three models present
    assert "opus" in text
    assert "sonnet" in text
    assert "haiku" in text
```

**Step 2: In `app.py:_refresh_ui()`, after computing model_stats from `self.parser.model_usage`, also fold in subagent token usage**

For each resolved subagent detail, add its tokens to the appropriate model entry. The subagent's model is available from `SubagentEvent.model` and can be resolved with `resolve_model()`.

```python
# Fold subagent tokens into per-model stats
for s in self.parser.subagents:
    if s.detail is not None:
        sa_model = resolve_model(s.model)
        sa_cost = s.detail.cost
        sa_model_id = s.model
        display_name = sa_model_id.split("-")[1] if "-" in sa_model_id else sa_model_id
        # Find or create entry
        existing = next((m for m in model_stats if m["model"] == display_name), None)
        if existing:
            existing["input_tokens"] += s.detail.input_tokens
            existing["output_tokens"] += s.detail.output_tokens
            existing["cost"] += sa_cost
        else:
            model_stats.append({
                "model": display_name,
                "input_tokens": s.detail.input_tokens,
                "output_tokens": s.detail.output_tokens,
                "cost": sa_cost,
            })
model_stats.sort(key=lambda m: -m["cost"])
```

**Step 3: Run all tests**

```bash
uv run pytest -x
```

**Step 4: Commit**

```bash
git add src/superpowers_dashboard/app.py tests/test_widget_costs.py
git commit -m "feat: include subagent tokens in per-model usage stats"
```

---

### Task 5: Final verification and push

**Step 1: Run full test suite**

```bash
uv run pytest -x -v
```

**Step 2: Launch the dashboard and verify visually**

```bash
uv run superdash
```

Check that:
- Workflow timeline shows timestamps, compactions with correct labels (COMPACTION/MICROCOMPACTION/CLEAR)
- Stats panel shows per-model breakdown with costs
- Three-column layout renders correctly

**Step 3: Push**

```bash
git push
```
