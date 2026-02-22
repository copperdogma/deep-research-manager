# Check In

Review local changes and prepare a safe commit plan.

## Review Commands

Run and inspect:

- `git status --short`
- `git diff --stat`
- `git diff`

Include untracked files in review.

## Validate Change Set

- Verify no secrets/tokens/credentials are included.
- Confirm docs are updated when behavior or workflow changed.
- Confirm relevant tests were run for touched code.

## Version and Changelog (Required)

Every commit that changes code or behavior MUST include:

1. **CHANGELOG.md entry** — check if `CHANGELOG.md` appears in `git diff --stat` or `git status --short`.
   - If missing, write a new entry at the top using Keep a Changelog format.
   - Header format: `## [X.Y.Z] - YYYY-MM-DD - Short summary`
   - Use semver: bump MAJOR for breaking changes, MINOR for new features, PATCH for fixes.
   - Include only applicable subsections: `### Added`, `### Changed`, `### Fixed`.
   - End with `- Bumped package version to X.Y.Z.` under `### Changed`.
2. **Version bump** — version must be updated in BOTH:
   - `pyproject.toml` (`version = "X.Y.Z"`)
   - `src/deep_research/__init__.py` (`__version__ = "X.Y.Z"`)
   - These two values must match each other and the changelog header.
3. Skip version/changelog only for trivial non-code changes (typo in comment, whitespace).

## Commit Guidance

- Stage only intentional files.
- Craft commit message focused on _why_.
- Commit only when user explicitly asks.
- Push only when user explicitly asks.

## Output Format

Provide:

1. What changed (grouped by area)
2. Risks or missing checks
3. Suggested commit message
4. Ready-to-run commit command sequence
