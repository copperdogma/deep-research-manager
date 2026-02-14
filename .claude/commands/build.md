# Build

Start or continue implementation of a specific task or feature.

## Resolve Target

- Accept a task description, file path, or spec section reference.
- If ambiguous, stop and ask for clarification.

## Required First Checks

1. Read the relevant spec section in `docs/spec-cli.md`.
2. Read existing source files that will be affected.
3. Verify understanding of acceptance criteria before writing code.

## Execution Flow

1. Implement scoped work for the task.
2. Run relevant checks (`pytest tests/` minimum).
3. Verify the CLI still works (`deep-research --help`).
4. Update `AGENTS.md` if new conventions, patterns, or pitfalls were discovered.

## Guardrails

- Do not mark work done unless tests pass.
- Do not run `git commit`/`push` unless explicitly requested by user.
- Do not over-engineer: implement what the spec says, nothing more.
