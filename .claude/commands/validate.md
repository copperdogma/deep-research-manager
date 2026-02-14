# Validate

Validate implemented work against the spec and changed files.

## Change Review

Inspect the full local delta:

- `git status --short`
- `git diff --stat`
- `git diff`

Open changed files and validate behavior against `docs/spec-cli.md`.

## Validation Checklist

- Spec requirements met for the relevant commands.
- CLI entry points work and help text is accurate.
- File templates match what the spec defines.
- Error handling covers the edge cases listed in the spec.
- Tests exist and pass for new/changed behavior.
- Code quality and project conventions followed.

## Output Contract

Return:

1. Findings ordered by severity (bugs, spec deviations, risks first)
2. Requirement scorecard (Met / Partial / Unmet)
3. Concrete next-step plan if gaps exist
