# Session Handoff — convention-auditor

> Read this to resume work in a new session (including from Claude Code).
> For the reasoning behind the design, see `ARCHITECTURE.md`.

---

## Current status

The foundation and the first pipeline component are complete and verified.

| Stage | What it is | Status |
|-------|-----------|--------|
| Stage 0 | Verify SDK works and auth is on the subscription | ✅ Done & verified |
| Stage 1 | Change collection — `git diff` component | ✅ Done & verified |
| Stage 2 | Analysis — prompt + structured findings | ⬜ **Next** |
| Stage 3 | Assembly — wire all components in `main.py` | ⬜ Not started |

The repo is initialized, committed, and pushed to GitHub
(`git@github.com:AvivSiani/convention-auditor.git`).

---

## Repository structure

```
convention-auditor/
├── auditor/
│   ├── __init__.py       # marks auditor/ as an importable package
│   ├── check_auth.py     # Stage 0: subscription-auth sanity check
│   └── collect.py        # Stage 1: runs git diff, returns the change
├── .gitignore
├── requirements.txt
├── ARCHITECTURE.md       # design + decisions with rationale
└── HANDOFF.md            # this file
```

Planned additions (see ARCHITECTURE.md §3):
`auditor/conventions.py`, `auditor/analyze.py`, `auditor/report.py`, `main.py`,
and a `CONVENTIONS.md` at the root.

---

## Environment setup (every new terminal)

```bash
cd ~/Projects/convention-auditor
source .venv/bin/activate            # enter the virtual environment
```

If starting on a fresh machine (no `.venv` yet):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The Claude Code CLI must also be installed and logged in:

```bash
npm install -g @anthropic-ai/claude-code   # if not installed
claude login                                # if OAuth session expired
```

---

## How to run what exists

**Stage 0 — auth check.** Always run with a clean environment so the subscription
OAuth is used, not a stray API key:

```bash
env -u ANTHROPIC_API_KEY python auditor/check_auth.py
```

Expected output ends with: `Claude: subscription auth works`

**Stage 1 — diff collection.**

```bash
python auditor/collect.py            # diff against main (default)
```

With no uncommitted changes it prints `(no changes against the comparison base)`;
with changes it prints a real git diff. `collect_diff(base=...)` accepts `HEAD`,
`main`, etc.

---

## The one gotcha that will bite

`ANTHROPIC_API_KEY`, if exported in your shell, **silently overrides** the
subscription OAuth and bills you per token. Symptoms: unexpected billing, or an
`OAuth session expired` / `organization has been disabled` error.

- Always run Claude-facing scripts with `env -u ANTHROPIC_API_KEY ...`.
- If it recurs, check `~/.zshrc` for an `export ANTHROPIC_API_KEY=...` line.
- If auth genuinely expired: `claude logout && claude login`.

---

## Next step: Stage 2 — the analysis component

This is the heart of the agent and the only stage that will not change under
either planned extension, so it deserves the most care.

**Contract:** `(conventions text, diff text) → structured findings list`

**Build it in `auditor/analyze.py`.** Key points to honor (from ARCHITECTURE.md
§4.3):

1. Send Claude two inputs: the convention text and the diff.
2. Define an explicit schema in the system prompt — per finding: `file`,
   `severity`, `description` — and instruct the model to return **JSON only**, no
   wrapping text.
3. **Validate** the response: attempt to parse; handle parse failure gracefully.
   Do not assume valid JSON every time — this is the main failure point.
4. Treat an **empty findings list** as a valid "all clear" result, distinct from
   an error.
5. Keep the structure minimal for now; the `suggested fix` field is added later,
   when the patch stage arrives.

The SDK message shape (`query()`, message/content blocks) can vary between SDK
versions. When wiring the call, inspect the actual message objects
(`print(type(message), message)`) rather than assuming a fixed structure — the
`getattr(block, "text", None)` pattern in `check_auth.py` is the defensive
reference.

---

## Open decisions deferred to later stages

- What to do when `main` does not exist (fall back to `HEAD`, or fail with a clear
  message) — decide when assembling `main.py`.
- Whether `check_auth.py` stays as a permanent sanity tool or is eventually removed
  (it was a Stage 0 utility, not a core component).
- Commit-message convention (plain vs. Conventional Commits) — revisit alongside
  introducing ADRs.
