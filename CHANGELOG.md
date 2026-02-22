## [0.3.2] - 2026-02-22 - Fix --provider silently dropping all but last value

### Fixed
- `deep-research run --provider openai --provider google` now correctly runs both providers. Previously, Click silently kept only the last `--provider` value when the flag was repeated, causing silent data loss (e.g. only Google ran, OpenAI was dropped with no error or warning).

### Changed
- `--provider` on `run` now uses `multiple=True` and accepts repeated flags: `--provider openai --provider google`.
- `run` command docstring now includes concrete usage examples visible in `--help`, including multi-provider syntax.
- `--provider` help text explicitly documents: repeat the flag for multiple providers, omit it for all providers, and lists known values.
- Bumped package version to `0.3.2`.

## [0.3.1] - 2026-02-22 - Add stub command for manual paste-in workflow

### Added
- `deep-research stub [PROVIDER...]` command creates blank report stubs with correct frontmatter (model name, topic, timestamp, research-mode) but empty body, ready for manual paste-in.
- `--all` flag on `stub` overwrites stubs even when a report already exists for that provider.
- `--mode [standard|deep]` flag on `stub` sets the `research-mode` frontmatter field.
- `project.write_stub()` helper writes a stub file for a given provider/model.
- `project.stub_exists()` helper checks if a report already exists for a provider.
- 16 new tests in `tests/test_stub.py`.

### Fixed
- `get_report_files()` now includes `ai-*-deep-research.md` files; they were previously excluded from synthesis payload assembly.

### Changed
- Bumped package version to `0.3.1`.

## [0.3.0] - 2026-02-22 - Add real deep research mode (OpenAI + Google)

### Added
- `--mode deep` flag on `run` command to use provider-native deep research APIs.
- OpenAI deep research via Responses API (`o4-mini-deep-research` default) with background polling and `web_search_preview`.
- Google deep research via Interactions API (`deep-research-pro-preview-12-2025` agent) with background polling.
- CLI flags: `--openai-dr-model`, `--google-dr-agent`, `--no-web`, `--poll-interval`, `--max-walltime`.
- Deep research output files use distinct naming: `ai-openai-deep-research.md`, `ai-google-deep-research.md`.
- Debug JSON payloads (`_debug-{provider}-dr.json`) written when `--debug` is used with deep mode.
- `research-mode` field in report frontmatter (`standard` or `deep`).
- 16 new unit tests for deep research routing, validation, CLI flags, and output filenames.
- Deep research spec document (`docs/proper-deep-research-spec.md`).

### Changed
- Google SDK dependency changed from `google-generativeai>=0.8` to `google-genai>=1.55.0` (required for Interactions API).
- `ProviderResult` dataclass now includes `mode` and `debug_payload` fields.
- `run_research()` accepts `mode` parameter; providers without deep support fall back to standard with a warning.
- AGENTS.md updated with architecture docs, conventions, pitfalls, and lessons learned from deep research work.
- Bumped package version to `0.3.0`.

## [2026-02-19] - Gemini preview model fix and live provider smoke tests

### Added
- Live provider smoke test suite (`tests/test_live_providers.py`) that runs real API calls for configured providers and skips only missing-key providers.

### Fixed
- Google default model updated to `gemini-3-pro-preview` to match available model IDs.
- Anthropic non-streaming calls now cap `max_tokens` to avoid long-request streaming errors.
- Provider error messages now include exception class names when the message string is empty.

### Changed
- Test guidance updated to include live provider tests for configured providers.
- Updated docs/examples to reference `gemini-3-pro-preview`.
- Bumped package version to `0.1.3`.

## [2026-02-19] - Gemini defaults/key fallback and install command refresh

### Added
- Provider key-resolution tests for Google Gemini env var precedence/fallback behavior.

### Fixed
- Google provider now checks `GEMINI_API_KEY` first and falls back to `GOOGLE_API_KEY`.

### Changed
- Google default model updated to `gemini-3-pro-preview` for both research and synthesis.
- CLI/project/spec messages now reference `GEMINI_API_KEY (or GOOGLE_API_KEY)` for Google.
- README install commands now use PEP 508 VCS syntax (`name[extra] @ git+...`) and include a pinned-commit example.
- Bumped package version to `0.1.2`.

## [2026-02-19] - Fix OpenAI/httpx proxies compatibility regression

### Added
- Packaging regression tests to enforce OpenAI-related `httpx<0.28` constraints in extras.
- `xai` optional dependency extra for explicit xAI/OpenAI-compatible installs.

### Fixed
- OpenAI provider startup failure with `AsyncClient.__init__() got an unexpected keyword argument 'proxies'` by constraining OpenAI/xAI installs to `httpx<0.28`.

### Changed
- Provider dependency docs now include the `xai` extra and a compatibility note for OpenAI/httpx versions.
- Agent memory notes updated with the new compatibility pitfall and mitigation pattern.
- Bumped package version to `0.1.1`.
