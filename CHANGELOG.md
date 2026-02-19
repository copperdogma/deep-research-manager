## [2026-02-19] - Fix OpenAI/httpx proxies compatibility regression

### Added
- Packaging regression tests to enforce OpenAI-related `httpx<0.28` constraints in extras.
- `xai` optional dependency extra for explicit xAI/OpenAI-compatible installs.

### Fixed
- OpenAI provider startup failure with `AsyncClient.__init__() got an unexpected keyword argument 'proxies'` by constraining OpenAI/xAI installs to `httpx<0.28`.

### Changed
- Provider dependency docs now include the `xai` extra and a compatibility note for OpenAI/httpx versions.
- Agent memory notes updated with the new compatibility pitfall and mitigation pattern.
