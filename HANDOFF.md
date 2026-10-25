# Session Handoff — convention-auditor

> Read this to resume work in a new session (including from Claude Code).
> For the reasoning behind the design, see `ARCHITECTURE.md`.

---

## Current status

The core pipeline is complete end to end and verified.

| Stage | What it is | Status |
|-------|-----------|--------|
| Stage 0 | Verify SDK works and auth is on the subscription | ✅ Done & verified |
| Stage 1 | Change collection — `git diff` component | ✅ Done & verified |
| Stage 2 | Analysis — prompt + structured findings | ✅ Done & verified |
| Stage 3 | Assembly — wire all components in `main.py` | ✅ Done & verified |

The repo is initialized, committed, and pushed to GitHub
(`git@github.com:AvivSiani/convention-auditor.git`).

---

## Repository structure

```
convention-auditor/
├── auditor/
│   ├── __init__.py       # marks auditor/ as an importable package
│   ├── check_auth.py     # Stage 0: subscription-auth sanity check
│   ├── collect.py        # Stage 1: runs git diff, returns the change
│   └── analyze.py        # Stage 2: sends conventions+diff to Claude, returns findings
├── main.py               # Stage 3: wires all four stages together, the CLI entry point
├── .gitignore
├── requirements.txt
├── CONVENTIONS.md        # conventions this project's own diffs are checked against
├── ARCHITECTURE.md       # design + decisions with rationale
└── HANDOFF.md            # this file
```

Planned additions (see ARCHITECTURE.md §3): `auditor/conventions.py` and
`auditor/report.py`, if/when convention-source and action outgrow being a few
inline lines in `main.py`.

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

**Stage 2 — analysis.**

```bash
env -u ANTHROPIC_API_KEY python -m auditor.analyze
```

Runs `analyze()` standalone against a small fixed sample conventions+diff pair
baked into `_main()` (deliberately not wired to `collect_diff` — see the Stage 2
recap below). Prints structured findings, or "no findings" if the sample is
clean. `analyze(conventions, diff)` is the contract other code should call.

**Stage 3 — full pipeline (the actual tool).**

```bash
env -u ANTHROPIC_API_KEY python main.py                # diff against main (default)
env -u ANTHROPIC_API_KEY python main.py --base HEAD    # uncommitted changes
```

Reads `CONVENTIONS.md`, diffs against `--base` (default `main`), sends both to
`analyze()`, and prints findings. Exit code: `0` clean or no changes, `1`
findings exist, `2` error (e.g. `--base` doesn't exist — the message tells you
to retry with `--base HEAD`).

---

## The one gotcha that will bite

`ANTHROPIC_API_KEY`, if exported in your shell, **silently overrides** the
subscription OAuth and bills you per token. Symptoms: unexpected billing, or an
`OAuth session expired` / `organization has been disabled` error.

- Always run Claude-facing scripts with `env -u ANTHROPIC_API_KEY ...`.
- If it recurs, check `~/.zshrc` for an `export ANTHROPIC_API_KEY=...` line.
- If auth genuinely expired: `claude logout && claude login`.

---

## Stage 2 recap — the analysis component

Built and verified in `auditor/analyze.py`. Contract:
`async analyze(conventions text, diff text) → structured findings list`.

Key points, per ARCHITECTURE.md §4.3:

1. Schema and JSON-only instruction live in a fixed `SYSTEM_PROMPT`, passed via
   `ClaudeAgentOptions(system_prompt=...)`; the per-call conventions+diff go in
   the user prompt. Per finding: `file`, `start_line`, `end_line` (new-file
   line numbers, both `null` if not line-specific), `severity`, `description`.
2. Parsing is lenient: strips a leading/trailing ` ``` ` code fence if present,
   then `json.loads`. Raises a `RuntimeError` with the raw text on real parse
   failure — validated, not assumed. Each finding is then checked by
   `_validate_finding` (required string fields, severity in `SEVERITIES`,
   valid line range). `main.py` catches that error and exits `2`.
3. Empty findings list (`[]`) is a valid "all clear" result, not an error.
4. Response text is pulled from message content blocks with
   `getattr(block, "text", None)`, following the defensive pattern from
   `check_auth.py` — the SDK message shape isn't assumed fixed.
5. `_main()` deliberately uses a **fixed sample** conventions+diff pair rather
   than calling `collect_diff()` from Stage 1 — real end-to-end testing (real
   `CONVENTIONS.md` + real `git diff`) was pulling the collection stage into the
   analysis component, violating convention 5 (stage separation) in this
   project's own `CONVENTIONS.md`. Wiring `collect_diff()` output into
   `analyze()` is Stage 3's job.

Verified by dogfooding: running `analyze()` against this repo's own staged diff
(when `analyze.py` + `CONVENTIONS.md` were new files) correctly flagged a
missing docstring and the stage-separation violation above — then came back
clean after the fix.

---

## Stage 3 recap — assembly (`main.py`)

Built and verified. `main.py` is the only file that knows about all four
stages; it reads `CONVENTIONS.md`, calls `collect_diff(base)`, calls
`analyze()`, and prints findings — the previously-open decisions are now
resolved this way:

1. `--base` is a CLI arg, default `main` (ARCHITECTURE.md §4.5).
2. If the requested base doesn't exist, `main.py` **fails with a clear error**
   pointing at `--base HEAD` — no silent fallback to a different base than the
   one requested.
3. Exit code reflects outcome: `0` clean/no changes, `1` findings exist, `2`
   error. Output itself stays report-only stdout printing (§4.2) — the exit
   code is just metadata a future script/hook caller could use; no hook or CI
   integration was added.

Verified against three real cases: a clean diff, a diff with real findings
(exit 1), and a nonexistent `--base` (exit 2, correct error message).

---

## Next: no fixed next step

The core pipeline (all four stages) is complete and dogfooding on this repo's
own diffs. From here, natural directions — not started, not committed to:

- Extract `auditor/conventions.py` / `auditor/report.py` out of `main.py` if
  those inline bits grow (see ARCHITECTURE.md §3 note).
- Either of the two planned extensions in ARCHITECTURE.md §5 (infer
  conventions from code; propose a patch to approve).
- Broaden `CONVENTIONS.md` itself now that there's a working loop to test
  changes against.

---

## Open decisions deferred to later stages

- Whether `check_auth.py` stays as a permanent sanity tool or is eventually removed
  (it was a Stage 0 utility, not a core component).
- Commit-message convention (plain vs. Conventional Commits) — revisit alongside
  introducing ADRs.
