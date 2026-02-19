# Tests AGENTS

This file scopes instructions for work under `tests/`.

- Prefer deterministic tests; mock networked AI calls by default.
- Keep unit tests isolated and fast.
- Include live AI tests for configured providers; skip only providers with no API key configured.
- Test file management commands (init, format, status) with real temp directories.
- Test API commands (run, final) with mocked provider responses.
