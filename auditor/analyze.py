# analyze.py — Stage 2: the analysis component.
# Sends conventions + diff to Claude, returns structured findings.
import json

import anyio
from claude_agent_sdk import ClaudeAgentOptions, query

SYSTEM_PROMPT = """You are a code convention auditor.

You will be given a project's coding conventions and a git diff. Compare the
diff against the conventions and report any violations.

Respond with JSON only — no prose, no explanation, no code fences. The JSON
must be a list of objects, each with exactly these fields:
  - "file": the file path the finding applies to
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

    return findings


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
            print(f"[{finding.get('severity', '?')}] {finding.get('file', '?')}: {finding.get('description', '?')}")


if __name__ == "__main__":
    anyio.run(_main)
