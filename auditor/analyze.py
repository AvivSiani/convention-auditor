# analyze.py — Stage 2: the analysis component.
# Sends conventions + diff to Claude, returns structured findings.
import json

import anyio
from claude_agent_sdk import ClaudeAgentOptions, query

SEVERITIES = ("low", "medium", "high")

SYSTEM_PROMPT = """You are a code convention auditor.

You will be given a project's coding conventions and a git diff. Compare the
diff against the conventions and report any violations.

Respond with JSON only — no prose, no explanation, no code fences. The JSON
must be a list of objects, each with exactly these fields:
  - "file": the file path the finding applies to
  - "start_line": the first line of the violation, as a line number in the new
    version of the file (the "+" side of the diff), or null if the finding is
    not tied to specific lines
  - "end_line": the last line of the violation (equal to start_line for a single
    line), or null when start_line is null
  - "severity": one of "low", "medium", "high"
  - "description": a short explanation of the violation and which convention it breaks

If the diff does not violate any convention, respond with an empty JSON list: []
"""


def _extract_text(message) -> str:
    """Return the concatenated text content of an SDK message, or '' if none."""
    text = ""
    for block in getattr(message, "content", []):
        block_text = getattr(block, "text", None)
        if block_text:
            text += block_text
    return text


def _parse_findings(raw_text: str) -> list[dict]:
    """Parse Claude's raw response text into a findings list, tolerating code fences."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

    try:
        findings = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Claude's response was not valid JSON: {e}\n\nRaw response:\n{raw_text}"
        ) from e

    if not isinstance(findings, list):
        raise RuntimeError(
            f"Expected a JSON list of findings, got {type(findings).__name__}: {findings}"
        )

    for index, finding in enumerate(findings):
        _validate_finding(index, finding)

    return findings


def _is_line_number(value) -> bool:
    """Return True if value is a positive int line number (bool excluded)."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _validate_finding(index: int, finding) -> None:
    """Raise RuntimeError if a single finding does not match the schema in SYSTEM_PROMPT."""
    if not isinstance(finding, dict):
        raise RuntimeError(
            f"Finding #{index} is not an object, got {type(finding).__name__}: {finding}"
        )

    for field in ("file", "description"):
        value = finding.get(field)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(
                f"Finding #{index} has a missing or empty '{field}': {finding}"
            )

    if finding.get("severity") not in SEVERITIES:
        raise RuntimeError(
            f"Finding #{index} has severity {finding.get('severity')!r}, "
            f"expected one of {SEVERITIES}: {finding}"
        )

    if "start_line" not in finding or "end_line" not in finding:
        raise RuntimeError(
            f"Finding #{index} is missing 'start_line' or 'end_line' (use null if not line-specific): {finding}"
        )

    start, end = finding["start_line"], finding["end_line"]
    if start is None and end is None:
        return
    if not (_is_line_number(start) and _is_line_number(end)) or start > end:
        raise RuntimeError(
            f"Finding #{index} has an invalid line range start_line={start!r}, end_line={end!r} "
            f"(expected positive ints with start_line <= end_line, or both null): {finding}"
        )


async def analyze(conventions: str, diff: str) -> list[dict]:
    """Compare a diff against a set of conventions and return structured findings."""
    user_prompt = f"CONVENTIONS:\n{conventions}\n\nDIFF:\n{diff}"
    options = ClaudeAgentOptions(system_prompt=SYSTEM_PROMPT)

    raw_text = ""
    async for message in query(prompt=user_prompt, options=options):
        raw_text += _extract_text(message)

    return _parse_findings(raw_text)


async def _main() -> None:
    """Exercise analyze() standalone with a fixed sample conventions+diff pair."""
    sample_conventions = "1. English only. All code, comments, and strings are in English."
    sample_diff = (
        "diff --git a/greet.py b/greet.py\n"
        "+def greet():\n"
        "+    print('שלום')  # hebrew comment\n"
    )

    findings = await analyze(sample_conventions, sample_diff)

    if not findings:
        print("No findings — the diff is clean.")
    else:
        for finding in findings:
            print(json.dumps(finding))


if __name__ == "__main__":
    anyio.run(_main)
