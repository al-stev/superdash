# Superpowers Skills Guide

A practical guide to how the 15 superpowers skills work together, which ones you invoke directly, and which ones Claude chains automatically.

## The Two Things You Need to Know

**1. You only need to prompt for 4 skills.** The rest are chained automatically by those 4.

**2. The skill you pick depends on what you're doing:**

| You want to...            | Prompt for...                |
|---------------------------|------------------------------|
| Build something new       | `brainstorming`              |
| Fix a bug                 | `systematic-debugging`       |
| Investigate multiple independent problems | `dispatching-parallel-agents` |
| Create a new skill        | `writing-skills`             |

Everything else — TDD, worktrees, plans, execution, code review, branch finishing — gets pulled in by these four as needed.

---

## How the Skills Chain Together

### The Build Path

This is the most common workflow. You say "I want to build X" and prompt for `brainstorming`.

```
You prompt: brainstorming
  │
  │  Asks questions one at a time, explores approaches,
  │  presents design in sections for validation.
  │  Writes design doc to docs/plans/YYYY-MM-DD-*-design.md
  │
  ├─→ using-git-worktrees  (creates isolated workspace)
  │
  └─→ writing-plans  (turns design into bite-sized TDD tasks)
        │
        │  Each task = write failing test → run it → implement →
        │  run it → commit. Complete code, exact file paths,
        │  exact commands. Saved to docs/plans/YYYY-MM-DD-*-plan.md
        │
        │  Then asks: "Subagent-driven (this session) or
        │              Parallel session (executing-plans)?"
        │
        ├─→ Option A: subagent-driven-development
        │     │
        │     │  Per task:
        │     │  1. Dispatches implementer subagent
        │     │     └─ Subagent uses test-driven-development
        │     │  2. Dispatches spec-reviewer subagent
        │     │     └─ "Does code match the spec? Nothing missing, nothing extra?"
        │     │  3. Dispatches code-quality-reviewer subagent
        │     │     └─ Uses requesting-code-review template
        │     │  4. Marks task complete
        │     │
        │     │  After all tasks:
        │     │  - Dispatches final code reviewer (whole implementation)
        │     └─→ finishing-a-development-branch
        │           └─ Merge / PR / Keep / Discard
        │
        └─→ Option B: executing-plans  (separate session)
              │
              │  Reads plan, executes in batches of 2-4 tasks,
              │  stops at checkpoints for human review.
              │  Uses test-driven-development internally.
              │
              └─→ finishing-a-development-branch
```

**What this means in practice:** You prompt `brainstorming`, answer its questions, approve the design, approve the plan, pick "subagent-driven" or "parallel session", and the rest happens automatically with review checkpoints.

### The Debug Path

You say "this is broken" or "I'm seeing X error" and prompt for `systematic-debugging`.

```
You prompt: systematic-debugging
  │
  │  Phase 1: Root cause investigation
  │    Read errors → Reproduce → Check recent changes →
  │    Gather evidence → Trace data flow
  │    (uses root-cause-tracing technique internally)
  │
  │  Phase 2: Pattern analysis
  │    Find working examples → Compare → Identify differences
  │
  │  Phase 3: Hypothesis testing
  │    Single hypothesis → Minimal test → Verify or new hypothesis
  │    (if 3+ hypotheses fail: STOP, question architecture with you)
  │
  │  Phase 4: Implementation
  │    └─→ test-driven-development
  │          Write failing test that captures the bug →
  │          Implement fix → Verify test passes
  │
  └─→ verification-before-completion
        Run the actual commands, show the output,
        prove it's fixed before claiming success.
```

**What this means in practice:** You prompt `systematic-debugging`, it investigates before proposing fixes (no guessing), creates a test that captures the bug, fixes it, and proves the fix works.

### The Parallel Investigation Path

You have 2+ independent problems to investigate at once. Prompt for `dispatching-parallel-agents`.

```
You prompt: dispatching-parallel-agents
  │
  ├─→ Subagent A: investigates problem 1
  ├─→ Subagent B: investigates problem 2
  └─→ Subagent C: investigates problem 3
       (each may use systematic-debugging, TDD, etc.)
```

**When to use this vs subagent-driven-development:** Parallel agents is for investigation and independent tasks with no shared state. Subagent-driven is for sequential implementation of a plan where each task builds on the last.

### The Skill Creation Path

You want to create a new skill. Prompt for `writing-skills`.

```
You prompt: writing-skills
  │
  │  RED: Create pressure scenarios, run WITHOUT skill,
  │       document how Claude fails
  │
  │  GREEN: Write SKILL.md addressing specific failures,
  │         run WITH skill, verify improvement
  │
  │  REFACTOR: Find new rationalizations Claude might use,
  │            add explicit counters, re-test
  │
  └─→ Deploy checklist (30+ items)
```

---

## Skills You Never Prompt For Directly

These are always invoked by other skills in the chain:

| Skill | Invoked by | What it does |
|-------|-----------|--------------|
| `using-superpowers` | Hooks (automatically) | Reminds Claude to check skills on every message |
| `test-driven-development` | Implementer subagents, systematic-debugging | RED-GREEN-REFACTOR cycle |
| `using-git-worktrees` | brainstorming, subagent-driven, executing-plans | Creates isolated workspace |
| `writing-plans` | brainstorming | Turns design into step-by-step TDD tasks |
| `subagent-driven-development` | writing-plans (when you choose option A) | Fresh subagent per task + two-stage review |
| `executing-plans` | writing-plans (when you choose option B) | Batch execution in separate session |
| `requesting-code-review` | subagent-driven-development | Dispatches reviewer subagent with template |
| `receiving-code-review` | When review feedback arrives | Verify before implementing, push back if wrong |
| `finishing-a-development-branch` | subagent-driven, executing-plans | Merge/PR/Keep/Discard + worktree cleanup |
| `verification-before-completion` | All skills (implicitly) | No success claims without fresh evidence |

You *can* prompt for any of these directly if you want to skip the chain. For example, if you already have a plan written, you could prompt `executing-plans` directly. But normally you don't need to.

---

## The Question You Asked

> How do TDD, subagent-driven-development, and worktrees work together?

Here's the concrete flow:

1. **brainstorming** explores the idea with you, writes a design doc
2. **writing-plans** creates tasks like "write failing test for X, implement X, commit"
3. **using-git-worktrees** creates an isolated branch/directory
4. **subagent-driven-development** dispatches one implementer subagent per task
5. Each implementer subagent uses **test-driven-development** (write test first, watch fail, implement, watch pass)
6. After each task, a **spec-reviewer** subagent checks: does this match the plan?
7. Then a **code-quality-reviewer** subagent checks: is this well-built?
8. After all tasks, a final reviewer checks the whole thing
9. **finishing-a-development-branch** merges, creates PR, or cleans up

The key insight: **TDD happens inside the subagents**, not at the orchestration level. The orchestrator (subagent-driven-development) manages dispatch and review. The workers (implementer subagents) do TDD.

---

## The Three Execution Methods

There are three ways to get work done through subagents. They serve different purposes and are not interchangeable.

### Subagent-Driven Development (Option A)

**What it is:** The orchestrator stays in your current session. It dispatches one fresh subagent per task, sequentially. After each task, it dispatches a spec-reviewer subagent (does the code match the plan?) then a code-quality-reviewer subagent (is it well-built?). If either reviewer finds issues, the implementer fixes them and gets re-reviewed.

**Pros:**
- No context switch — everything happens in your conversation
- Fresh subagent per task — no context pollution between tasks
- Two-stage review is automatic — you don't have to remember to ask
- Subagent questions surface before work begins (the orchestrator can answer them)
- Fast iteration — no human-in-loop between tasks

**Cons:**
- Sequential only — tasks run one at a time (no parallelism for implementation)
- More expensive — each task dispatches 3 subagents (implementer + 2 reviewers), plus re-reviews
- Orchestrator accumulates context — the controller session grows over time
- If the orchestrator compacts, it may lose track of task state

**Best for:** 5-15 independent tasks where you want hands-off execution with quality gates.

### Executing Plans (Option B)

**What it is:** You open a new Claude session in the worktree and tell it to use `executing-plans`. It reads the plan file, executes tasks in batches of 2-4, and stops at checkpoints for you to review.

**Pros:**
- Human review between batches — you see intermediate results and can redirect
- Can handle coupled tasks — you control the ordering
- Fresh session — no prior context to interfere
- Simpler — fewer subagent dispatches, lower cost

**Cons:**
- Requires context switching (opening a new session)
- Human-in-loop slows things down — you wait for checkpoints
- Single session accumulates context across all tasks
- No automatic two-stage review (relies on the executor's own judgment)

**Best for:** Tightly coupled tasks, unfamiliar codebases, or when you want more control over execution order and intermediate results.

### Dispatching Parallel Agents

**What it is:** Multiple subagents run simultaneously on independent problems. Not for plan execution — for investigation, research, and tasks with no shared state.

**Pros:**
- True parallelism — 3 investigations run at the same time
- Fast for independent problems — total time = slowest agent, not sum
- Each agent gets full context window — no pollution

**Cons:**
- Tasks must be truly independent — shared files cause conflicts
- No ordering guarantees — agents don't know about each other
- Not suitable for implementation — two agents editing the same file will collide
- No review cycle built in

**Best for:** "We have 3 bugs in unrelated systems — investigate all of them." Or: "Research how X works, and separately research how Y works, and separately check if Z is feasible."

### When to Use Which

```
Need to implement a plan?
│
├─ Tasks are independent, want hands-off
│   └─ subagent-driven-development (Option A)
│
├─ Tasks are coupled, want control
│   └─ executing-plans (Option B)
│
└─ Not implementing — investigating/researching?
    │
    ├─ 2+ independent questions
    │   └─ dispatching-parallel-agents
    │
    └─ One focused question
        └─ Single subagent (Task tool directly)
```

**You might combine them.** For example: use `dispatching-parallel-agents` to investigate 3 potential approaches in parallel, then use the results to inform a `brainstorming` session, which produces a plan, which gets executed by `subagent-driven-development`.

---

## Decision Flowchart

```
What are you doing?
│
├─ Building something new
│   └─ Prompt: brainstorming
│      (chains: worktrees → plans → execution → review → finish)
│
├─ Fixing a bug
│   └─ Prompt: systematic-debugging
│      (chains: investigate → TDD → verify)
│
├─ Investigating 2+ independent problems
│   └─ Prompt: dispatching-parallel-agents
│
├─ Creating a skill
│   └─ Prompt: writing-skills
│      (chains: pressure-test → write → refine)
│
├─ Have a plan already, want to execute it
│   └─ Prompt: executing-plans (option B)
│      or: subagent-driven-development (option A)
│
├─ Just want a code review
│   └─ Prompt: requesting-code-review
│
└─ Want to wrap up a branch
    └─ Prompt: finishing-a-development-branch
```

---

## Iron Laws (Non-Negotiable Across All Skills)

These principles are enforced by multiple skills simultaneously:

1. **No code without a failing test first** (test-driven-development)
2. **No fixes without root cause investigation** (systematic-debugging)
3. **No success claims without fresh verification evidence** (verification-before-completion)
4. **No performative agreement with review feedback** (receiving-code-review)
5. **Check for applicable skills before any response** (using-superpowers)

---

## How This Relates to the Dashboard

The superdash dashboard monitors these skill chains in real-time:

- **Skills panel** — which skills have been invoked this session
- **Workflow panel** — chronological timeline of skills, overhead gaps, and subagent dispatches
- **Stats panel** — skill compliance (Skills: N | Tools: M), subagent metrics
- **Hooks panel** — the enforcement hooks that remind Claude to check skills
- **Activity log** — every skill invocation, subagent dispatch, compaction, and hook event

The "overhead gaps" in the workflow panel show periods where Claude was working without any skill active — these are the moments where the enforcement hooks should be catching missed skill invocations.
