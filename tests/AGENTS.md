# Tests AGENTS

This file scopes instructions for work under `tests/`.

- Prefer deterministic tests; mock networked AI calls by default.
- Keep unit tests isolated and fast.
- Use live AI tests only behind an explicit environment gate (e.g., `DEEP_RESEARCH_LIVE_TESTS`).
- Test file management commands (init, format, status) with real temp directories.
- Test API commands (run, final) with mocked provider responses.
