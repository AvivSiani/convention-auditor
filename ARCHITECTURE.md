# Architecture — convention-auditor

> A CLI agent that reviews git diffs against your defined conventions — runs on
> your Claude subscription, not per-token API billing.

This document explains **why** the project is built the way it is. It is meant to
be read before making changes, whether by a human or by an AI assistant picking
up the work in a new session. For current status and next steps, see
`HANDOFF.md`.

---

## 1. What the tool does

The agent reads a project's coding conventions, runs `git diff` to see what
changed, asks Claude to compare the change against those conventions, and reports
where the change deviates. Nothing more, on purpose — the scope is deliberately
narrow so the design stays clean and each part is understood before the next is
added.

---

## 2. The foundational choice: running on the subscription

The single most important decision is that the agent runs on a **Claude Pro/Max
subscription**, not on a per-token API key. This shapes everything downstream, so
it is worth understanding the mechanics.

### How it works

The agent does **not** talk to Claude directly. It uses the **Claude Agent SDK**
(`claude-agent-sdk`), which wraps the **Claude Code CLI** (`claude`) and runs it
as a subprocess. The chain is:

```
our Python code
   ↓  calls query()
claude-agent-sdk           (a Python library — the "remote control")
   ↓  spawns a subprocess
claude CLI                 (the tool that actually authenticates and calls the server)
   ↓  reads local OAuth credentials, sends an HTTPS request
Anthropic server           (runs the model)
```

The CLI understands both API-key auth **and** subscription OAuth. When you run
`claude login`, OAuth credentials are stored at `~/.claude/.credentials.json` and
every call counts against the subscription's usage limits instead of a
pay-per-token account.

### The critical gotcha

The CLI's auth precedence puts `ANTHROPIC_API_KEY` **above** the OAuth token. If
that variable is exported in your environment (from another project — and it often
is), it silently wins, and you are billed per token without noticing. This is
documented behavior, not a bug.

**Mitigation:** always run with a clean environment:

```bash
env -u ANTHROPIC_API_KEY python auditor/check_auth.py
```

### The trade-off this locks in

Running on the subscription means being coupled to Claude. The Agent SDK is built
around the Claude Code CLI; there is no provider-agnostic abstraction underneath.
Swapping to another LLM provider would mean replacing the SDK and the code that
uses it — not changing a setting. This is an accepted trade-off: the subscription
was the whole point, and we gain simplicity in exchange for portability we do not
need here.

### The regular SDK, for contrast

The standard `anthropic` SDK talks to the server **directly** and only knows about
API-key billing — there is no way to route the subscription through it. That is
precisely why the Agent SDK (which wraps the CLI) is required to run on the
subscription.

---

## 3. The core architecture: a four-stage pipeline

The agent is a chain of four independent stages, each a component with a clear
**contract** (defined input → defined output). The whole design rests on keeping
these stages genuinely separate.

```
Convention source → Change collection → Analysis → Action
```

| Stage | Contract (in → out) | Current implementation | File |
|-------|--------------------|-----------------------|------|
| Convention source | () → convention text | reads `CONVENTIONS.md` | `auditor/conventions.py` (planned) |
| Change collection | base → diff text | `git diff` via subprocess | `auditor/collect.py` |
| Analysis | (conventions, diff) → findings | calls Claude via Agent SDK | `auditor/analyze.py` (planned) |
| Action | findings → result | prints to stdout | `auditor/report.py` (planned) |

`main.py` (planned) is the only piece that knows about all four; it wires them
together.

### Why separation is the whole point

Two future extensions are explicitly planned (see §5). Each touches **exactly one
stage**:

| Future extension | Stage replaced | Stages untouched |
|-----------------|----------------|-----------------|
| Infer conventions from code | Convention source only | collection, analysis, action |
| Propose a patch to approve | Action only | source, collection, analysis |

If the four stages are truly independent, each extension is a one-component change.
If the pipeline were one big function, each extension would require pulling the
whole thing apart. **Simplicity lives in the behavior, not in the structure** —
the structure is deliberately modular so the narrow behavior can grow without a
rewrite.

Note that the analysis stage — the one that is "worth the subscription" (heavy
token use reading a large diff plus conventions) — is the **only** stage that does
not change under either extension. Investment in tuning its prompt pays off across
the whole life of the project.

---

## 4. Key decisions and their rationale

### 4.1 Convention source: manual `CONVENTIONS.md` (for now)

Chosen over ADRs or inference-from-code because a manual file is explicit, gives
full control over what is checked, and is the simplest thing to start with. The
downside — it must be maintained and can drift from the code — is acceptable at
this stage. Inference-from-code is the planned upgrade (§5), and the pipeline is
built so it slots into the convention-source stage alone.

### 4.2 Action: report-only to stdout (for now)

Chosen over writing report files or proposing patches so that during the learning
phase the **only variable being tuned is the prompt and the agent's behavior** —
not file management, and not any risk to code. A manual comparison base plus
stdout gives a seconds-long iteration loop. Patch proposal is the planned upgrade
(§5), isolated to the action stage.

### 4.3 Findings format: structured, minimal-first

Findings come back from Claude as a **structured** list (per finding: file,
severity, description), not free text. The reason is forward-looking: the future
patch stage needs to know file and location, which free text cannot reliably
provide. We start with a minimal structure and add a "suggested fix" field only
when we reach the patch stage — paying up front only for what is useful today
(clean stdout output) while preparing the ground for tomorrow.

**Risk to handle explicitly:** asking an LLM for consistent structure means
relying on valid JSON every time. This is the most common failure point in agents
like this. The analysis stage must **validate** what comes back (attempt to parse,
handle failure) rather than assume success.

**Empty findings are a valid result, not a failure.** The agent must distinguish
"checked, all clear" from "something went wrong."

### 4.4 Invocation: manual from the terminal

Chosen over git hooks or CI. During development you want to run repeatedly, see a
result, tune, run again — a fast iteration loop that a commit-triggered hook would
interrupt. Manual invocation also keeps you in explicit control of when the
subscription quota is spent (a hook on every commit could drain it unnoticed). The
invocation layer sits **above** the four components — `main.py` is the entry point,
and whatever calls it (you now, a hook later) does not matter to the components. A
hook can wrap the existing `main.py` later without changing anything underneath.

### 4.5 Comparison base: `main` by default, parameterized

`git diff` runs against `main` by default (the pre-PR review scenario, the most
common use), but the base is a parameter, not hard-coded — so `HEAD` (changes not
yet committed) or a staged-only view can be requested at any time. This mirrors
the manual-invocation philosophy: explicit control in the user's hands.

### 4.6 Project structure: modular from the start

The components live in an `auditor/` Python package rather than flat in the root.
Chosen because the destination is already known (planned together), so starting
structured avoids a later reorganization — and reorganizing after there is git
history means messy "moved files" commits. The `auditor/__init__.py` marks the
directory as an importable package so `main.py` can do `from auditor.collect
import ...`.

### 4.7 Code language: English only

All code — comments, docstrings, printed strings, commit messages — is in English,
for a professional, publicly shareable repo and better use as context for AI
tooling. (Conversation about the project happens in Hebrew; only file contents are
English.)

---

## 5. Planned extensions (designed for, not yet built)

Both were required up front, and the architecture exists to make them
one-component changes rather than rewrites:

1. **Infer conventions from code** — replace the convention-source stage with an
   agent that derives conventions from the codebase instead of reading a manual
   file. Risk to watch: the agent may enshrine existing bad patterns as if they
   were intent.

2. **Propose a patch to approve** — replace the action stage so that, instead of
   only reporting, the agent proposes a fix the user approves. This is the point
   where the agent crosses from read-only to write, which is exactly why the action
   stage is a fully separate component: when write is added, it is controlled in one
   measured place. The structured findings format (§4.3) already anticipates this
   by keeping file/location per finding.

---

## 6. Relationship to the broader goal

This project is also a narrow prototype of a larger idea (a project-knowledge
layer where defined knowledge is the source of truth and is compared against
actual code). The convention-source-vs-actual-code comparison here is the smallest,
simplest version of that idea — built to learn what is genuinely hard about it
before it becomes a larger specification.
