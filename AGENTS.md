# AGENTS.md

This file is the project-wide source of truth for agent behavior in deep-research-manager.

## Prime Directives

- Do not run `git commit`, `git push`, or modify remotes unless the user explicitly asks.
- Do not add, modify, or rely on GitHub Actions CI workflows unless the user explicitly requests it.
- The folder is the state. No database, no config server, no hidden state.
- Every step the CLI automates can also be done by hand. The CLI just makes it faster.
- API keys are optional. Zero keys = a structured folder manager. More keys = more automation.

## Definition of Done

A task is not complete until all applicable items are true:

1. Relevant tests pass (`pytest tests/` at minimum).
2. The CLI entry point still works (`deep-research --help`).
3. Any new commands or flags are documented.
4. If file templates changed, the spec and code agree.

## AI Self-Improvement Protocol (Critical)

Treat this file as a living memory. Update it when you learn.

- When you stumble, add an entry under `## Lessons Learned`.
- When you find a reliable technique, add it under `## Effective Patterns`.
- When you make a mistake, add it under `## Known Pitfalls` with symptom and correction.
- When a new repo convention emerges, document it under `## Project Conventions`.

Entry format:

- `YYYY-MM-DD — short title`: one-line summary plus a short explanation including file paths.

## Project Context

- deep-research-manager is a CLI tool that manages the lifecycle of multi-model deep research cycles.
- Core stack: Python 3.10+, Click, PyYAML, asyncio, provider SDKs (openai, anthropic, google-generativeai).
- Product specification: `docs/spec-cli.md`

## Architecture Overview

- `cli.py` — Click command definitions (init, run, format, final, prepare-final, status)
- `project.py` — Folder/file management (init, format, status)
- `providers.py` — API client wrappers (OpenAI, Anthropic, Google, xAI)
- `synthesis.py` — Synthesis prompt generation, payload assembly
- `frontmatter.py` — YAML frontmatter parsing/writing
- `templates.py` — File templates (research-prompt, ai-agent, synthesis, etc.)

## Repo Map

- `src/deep_research/` — main package
- `tests/` — unit and integration tests
- `tests/fixtures/` — sample research folders for testing
- `docs/` — specs and documentation

## Development Workflow

- Use TDD where practical; at minimum, add/adjust tests with implementation.
- Prefer small, focused modules with explicit contracts.
- Run `pytest tests/` before declaring completion.
- Keep the CLI output user-friendly with clear next-step guidance.

## Cross-Agent Notes

- Root `AGENTS.md` is the shared behavior contract across agents.
- Subdirectory `AGENTS.md` files can be used for scoped guidance (e.g., `tests/AGENTS.md`).
- Claude Code loads this file through `CLAUDE.md` using `@AGENTS.md`.
- `.cursor/rules/` may be used only for Cursor-specific activation behavior not expressible here.

## Project Conventions

_(Add entries as conventions emerge)_

## Effective Patterns

- 2026-02-19 — Guard provider extras with compatibility constraints: when provider SDKs depend on fast-moving HTTP stacks, pin known-safe ranges in optional extras and add tests that assert those constraints in `pyproject.toml`. (`pyproject.toml`, `tests/test_dependency_constraints.py`)

## Known Pitfalls

- 2026-02-13 — OpenAI max_tokens vs max_completion_tokens: newer OpenAI models (gpt-5.2+) reject `max_tokens` and require `max_completion_tokens`. The xAI client uses the same OpenAI SDK so needs the same parameter. (`src/deep_research/providers.py`)
- 2026-02-19 — OpenAI SDK 1.52.2 with httpx 0.28.x: `httpx` removed `proxies` in 0.28, which triggers `AsyncClient.__init__() got an unexpected keyword argument 'proxies'` before API calls. Keep OpenAI/xAI installs on `httpx<0.28` unless upgrading to a confirmed-compatible OpenAI SDK. (`pyproject.toml`, `README.md`)

## Lessons Learned

- 2026-02-13 — Don't trust model self-reported identity: LLMs can misidentify their own model variant (e.g., opus saying it's sonnet). For API calls where we know the model, use the requested model ID for filenames/metadata. Only rely on self-reported `canonical-model-name` for manual pastes via `format`. (`src/deep_research/cli.py`, `src/deep_research/project.py`)
