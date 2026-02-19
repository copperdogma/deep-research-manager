"""Live provider smoke tests.

These tests perform real API calls for any providers that have keys configured
in the environment. Providers without keys are skipped.
"""

from __future__ import annotations

import asyncio
import importlib.util
import time

import pytest

from deep_research import providers


def _run(coro):
    return asyncio.run(coro)


def _provider_sdk_available(provider_key: str) -> bool:
    module_map = {
        "openai": "openai",
        "anthropic": "anthropic",
        "google": "google.generativeai",
        "xai": "openai",
    }
    try:
        return importlib.util.find_spec(module_map[provider_key]) is not None
    except ModuleNotFoundError:
        return False


@pytest.mark.parametrize("provider_key", ["openai", "anthropic", "google", "xai"])
def test_live_provider_smoke(provider_key):
    if not providers.has_provider_api_key(provider_key):
        pytest.skip(f"{provider_key} API key not configured")
    if not _provider_sdk_available(provider_key):
        pytest.skip(f"{provider_key} SDK not installed")

    config = providers.MODEL_CONFIG[provider_key]
    caller = providers.PROVIDER_CALLERS[provider_key]
    prompt = (
        "Live smoke test. Respond with exactly LIVE_OK and nothing else. "
        "If this is impossible, include LIVE_OK in your first line."
    )
    result = None
    for attempt in range(2):
        result = _run(caller(prompt, config["research_model"], timeout=120))
        if result.error is None and result.content:
            break
        if attempt == 0:
            time.sleep(1)

    assert result is not None
    assert result.error is None, f"{provider_key} failed: {result.error}"
    assert result.content, f"{provider_key} returned empty content"
    assert "LIVE_OK" in result.content, f"{provider_key} did not include LIVE_OK: {result.content!r}"
