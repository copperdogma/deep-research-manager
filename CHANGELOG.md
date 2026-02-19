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
