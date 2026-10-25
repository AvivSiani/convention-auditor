# Conventions — convention-auditor

> What the auditor checks diffs against. Kept short and concrete on purpose —
> see `ARCHITECTURE.md` for the reasoning behind the project itself.

1. **English only.** All code — comments, docstrings, printed/user-facing
   strings, commit messages — is in English. No exceptions.

2. **Every function has a one-line docstring stating its contract**
   (what it takes in, what it returns, or what it does), not a description of
   its internals. Trivial one-liners (e.g. `__main__` glue) are exempt.

3. **No bare `except`.** Catch specific exceptions or check conditions
   explicitly (e.g. `result.returncode != 0`), and raise a clear error message
   that includes the relevant context (what failed, what was returned).

4. **Defensive access to SDK response objects.** When reading fields off
   Claude Agent SDK message/content objects, use `getattr(obj, "field", None)`
   and check before use — do not assume a fixed shape, since it can vary
   between SDK versions. This applies only to objects whose shape the SDK
   controls. Data whose shape this project defines and validates at a stage
   boundary (e.g. findings after `_validate_finding`) is trusted downstream
   and accessed directly.

5. **Stages stay separated.** Each file/component does exactly one job in the
   pipeline (convention source, collection, analysis, action) and does not
   reach into another stage's responsibility. A component that talks to git
   does not also talk to Claude, and vice versa.

6. **Every component is directly runnable.** Each pipeline file has an
   `if __name__ == "__main__":` block that exercises it standalone, so it can
   be tested in isolation without wiring up the rest of the pipeline.
