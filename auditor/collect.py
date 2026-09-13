# collect.py — Stage 1: the collection component. Runs git diff and returns the change.
# No connection to Claude here — just git.
import subprocess


def collect_diff(base: str = "main") -> str:
    """
    Return the git diff of the current state against a comparison base.

    base: what to compare against. Defaults to 'main' (pre-PR review).
          Pass 'HEAD' for changes not yet committed.
    """
    result = subprocess.run(
        ["git", "diff", base],
        capture_output=True,   # capture stdout/stderr instead of printing
        text=True,             # return strings, not bytes
    )

    # git returns a non-zero exit code when something goes wrong (e.g. base missing)
    if result.returncode != 0:
        raise RuntimeError(
            f"git diff failed (code {result.returncode}):\n{result.stderr.strip()}"
        )

    return result.stdout


if __name__ == "__main__":
    # Direct run for testing — prints the diff against main
    diff = collect_diff()
    if diff.strip():
        print(diff)
    else:
        print("(no changes against the comparison base)")
