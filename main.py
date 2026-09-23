# main.py — Stage 3: wires the four pipeline stages together.
# The only file that knows about all of them.
import argparse
import sys
from pathlib import Path

import anyio

from auditor.analyze import analyze
from auditor.collect import collect_diff

CONVENTIONS_PATH = Path(__file__).parent / "CONVENTIONS.md"


def parse_args() -> argparse.Namespace:
    """Parse CLI args, exposing collect_diff's comparison base as --base."""
    parser = argparse.ArgumentParser(description="Audit a git diff against CONVENTIONS.md.")
    parser.add_argument(
        "--base",
        default="main",
        help="comparison base for the diff (default: main). Pass HEAD for uncommitted changes.",
    )
    return parser.parse_args()


async def run(base: str) -> int:
    """Run the full pipeline once; return the process exit code."""
    conventions = CONVENTIONS_PATH.read_text()

    try:
        diff = collect_diff(base)
    except RuntimeError as e:
        print(f"Error collecting diff: {e}", file=sys.stderr)
        print(f"If '{base}' doesn't exist, try: python main.py --base HEAD", file=sys.stderr)
        return 2

    if not diff.strip():
        print("(no changes against the comparison base)")
        return 0

    findings = await analyze(conventions, diff)

    if not findings:
        print("No findings — the diff is clean.")
        return 0

    for finding in findings:
        print(f"[{finding.get('severity', '?')}] {finding.get('file', '?')}: {finding.get('description', '?')}")
    return 1


def main() -> None:
    """CLI entry point: parse args, run the pipeline, exit with its result code."""
    args = parse_args()
    exit_code = anyio.run(run, args.base)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
