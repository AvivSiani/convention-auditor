# check_auth.py - verifies that the SDK and the authentication are working. 
import os
import anyio
from claude_agent_sdk import query


def report_env() -> None:
    """print out which authentication method is expected to win before the run."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        print(f"⚠️  ANTHROPIC_API_KEY exported ({api_key[:12]}…)he will win the - OAuth!")
        print("    Run with: env -u ANTHROPIC_API_KEY python auditor/check_auth.py")
    else:
        print("✓ ANTHROPIC_API_KEY not exported the authentiocation will run with - OAuth.")


async def main() -> None:
    report_env()
    print("\nsending qusetion to Claude…\n")

    async for message in query(prompt="Reply with exactly: subscription auth works"):
        for block in getattr(message, "content", []):
            text = getattr(block, "text", None)
            if text:
                print("Claude:", text)


if __name__ == "__main__":
    anyio.run(main)