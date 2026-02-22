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
- Core stack: Python 3.9+, Click, PyYAML, asyncio, provider SDKs (openai, anthropic, google-genai).
- Product specification: `docs/spec-cli.md`
- Deep research spec: `docs/proper-deep-research-spec.md` (treat as guidance, not gospel — some details are wrong)

## Architecture Overview

- `cli.py` — Click command definitions (init, run, format, final, prepare-final, status, check-providers)
- `project.py` — Folder/file management (init, format, status, slugify)
- `providers.py` — API client wrappers (OpenAI, Anthropic, Google, xAI) + deep research callers
- `synthesis.py` — Synthesis prompt generation, payload assembly
- `frontmatter.py` — YAML frontmatter parsing/writing
- `templates.py` — File templates (research-prompt, ai-agent, synthesis, etc.)
- `updater.py` — SOTA model discovery via provider APIs + LLM-based upgrade decisions

### Two research modes

- **Standard** (`--mode standard`, default): one-shot `chat.completions` / `generate_content` per provider, all run in parallel.
- **Deep** (`--mode deep`): uses provider-native deep research APIs. Only OpenAI and Google have these today; Anthropic/xAI fall back to standard with a warning.
  - OpenAI: Responses API (`client.responses.create`) with `background=True` + polling via `client.responses.retrieve`. Requires `web_search_preview` tool.
  - Google: Interactions API (`client.interactions.create`) with `background=True` + polling via `client.interactions.get`. Agent: `deep-research-pro-preview-12-2025`.

### Key data structures

- `MODEL_CONFIG` — per-provider config (env_var, display_name, research_model, synthesis_model)
- `DEEP_RESEARCH_DEFAULTS` — per-provider deep research model/agent defaults
- `DEEP_RESEARCH_PROVIDERS` — set of provider keys that support deep mode (currently `{"openai", "google"}`)
- `ProviderResult` — dataclass returned by all callers (provider, model, content, tokens, cost, elapsed, error, mode, debug_payload)
- User config: `~/.deep-research/config.json` — persistent model overrides loaded on import

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

- **Output file naming**: standard reports → `{slugify(model)}-report.md`; deep research reports → `ai-{provider}-deep-research.md`. Debug payloads → `_debug-{provider}-dr.json`.
- **Frontmatter `research-mode` field**: all reports written by `run` include `research-mode: standard` or `research-mode: deep` in frontmatter.
- **Google SDK**: the project uses `google-genai` (the `google.genai` namespace), NOT the older `google-generativeai`. The pyproject.toml extra is `google-genai>=1.55.0`.
- **Deep mode fallback**: when `--mode deep` is used with a provider that lacks deep support, warn and fall back to standard — never hard-error.

## Effective Patterns

- 2026-02-19 — Guard provider extras with compatibility constraints: when provider SDKs depend on fast-moving HTTP stacks, pin known-safe ranges in optional extras and add tests that assert those constraints in `pyproject.toml`. (`pyproject.toml`, `tests/test_dependency_constraints.py`)
- 2026-02-22 — Background polling for long-running API calls: both OpenAI and Google deep research take 2–10 minutes. Use `background=True` with periodic polling and a wall-clock deadline rather than blocking with a large timeout. Pass `poll_interval` and `max_walltime` as user-configurable params. (`src/deep_research/providers.py`)
- 2026-02-22 — Verify API docs against specs before implementing: the deep research spec (`docs/proper-deep-research-spec.md`) had several inaccuracies vs actual API behavior. Always check official docs and test locally before trusting a spec. (`docs/proper-deep-research-spec.md`)

## Known Pitfalls

- 2026-02-13 — OpenAI max_tokens vs max_completion_tokens: newer OpenAI models (gpt-5.2+) reject `max_tokens` and require `max_completion_tokens`. The xAI client uses the same OpenAI SDK so needs the same parameter. (`src/deep_research/providers.py`)
- 2026-02-19 — OpenAI SDK 1.52.2 with httpx 0.28.x: `httpx` removed `proxies` in 0.28, which triggers `AsyncClient.__init__() got an unexpected keyword argument 'proxies'` before API calls. Keep OpenAI/xAI installs on `httpx<0.28` unless upgrading to a confirmed-compatible OpenAI SDK. (`pyproject.toml`, `README.md`)
- 2026-02-22 — OpenAI deep research tool type is `web_search_preview`, NOT `web_search`: the spec says `web_search` but the actual Responses API requires `{"type": "web_search_preview"}`. Using the wrong name silently fails or errors. (`src/deep_research/providers.py`)
- 2026-02-22 — OpenAI Responses API needs `openai>=1.68` (approx): older versions of the SDK (e.g. 1.52.2) don't have `client.responses`. The deep research feature requires upgrading. (`pyproject.toml`)
- 2026-02-22 — Google Interactions API is marked "experimental": `client.interactions.create()` emits a `UserWarning: Interactions usage is experimental`. This is cosmetic and the feature works, but be aware it may change in future `google-genai` releases. (`src/deep_research/providers.py`)
- 2026-02-22 — Google deep research requires `background=True`: calling the deep research agent without background mode will fail. The `store=True` parameter is implied by `background=True`. (`src/deep_research/providers.py`)

## Lessons Learned

- 2026-02-13 — Don't trust model self-reported identity: LLMs can misidentify their own model variant (e.g., opus saying it's sonnet). For API calls where we know the model, use the requested model ID for filenames/metadata. Only rely on self-reported `canonical-model-name` for manual pastes via `format`. (`src/deep_research/cli.py`, `src/deep_research/project.py`)
- 2026-02-22 — Deep research APIs are async-by-nature: both OpenAI and Google deep research run as background jobs that take minutes. The synchronous `asyncio.to_thread` wrapper works fine for Google since the SDK is synchronous. OpenAI's SDK supports sync `client.responses.create` + `client.responses.retrieve` so no thread wrapper needed. Polling is done with `asyncio.sleep` in both cases. (`src/deep_research/providers.py`)
- 2026-02-22 — OpenAI deep research citations are in annotations: the final output message's `content[0].annotations` contains citation objects with `url` and `title`. Extract and append as a Sources section for the report. (`src/deep_research/providers.py`)
