"""Logic for discovering new SOTA models and updating the local configuration."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from deep_research import providers

PROVIDERS_FILE = Path(__file__).parent / "providers.py"

# Simple versioning regex: looks for numbers and dots/dashes
VERSION_PATTERN = re.compile(r"(\d+(?:[.-]\d+)*)")

def extract_version(model_id: str) -> list[int]:
    """Extract numeric version parts from a model ID for comparison."""
    match = VERSION_PATTERN.search(model_id)
    if not match:
        return [0]
    # Replace dashes with dots for consistent splitting
    version_str = match.group(1).replace("-", ".")
    return [int(p) for p in version_str.split(".") if p.isdigit()]

async def fetch_latest_openai() -> str | None:
    """Fetch the latest GPT model ID from OpenAI."""
    try:
        from openai import AsyncOpenAI
        api_key = providers.get_provider_api_key("openai")
        if not api_key:
            return None
        client = AsyncOpenAI(api_key=api_key)
        response = await client.models.list()
        # Filter for gpt models, exclude 'vision', 'instruct', etc. unless they are the main line
        models = [m.id for m in response.data if m.id.startswith("gpt-") and "vision" not in m.id]
        if not models:
            return None
        return sorted(models, key=extract_version, reverse=True)[0]
    except Exception:
        return None

async def fetch_latest_anthropic() -> str | None:
    """Fetch the latest Claude model ID from Anthropic."""
    try:
        from anthropic import AsyncAnthropic
        api_key = providers.get_provider_api_key("anthropic")
        if not api_key:
            return None
        client = AsyncAnthropic(api_key=api_key)
        # Note: Anthropic's model listing API might require specific versions or be limited
        # For this implementation, we assume the SDK supports it as of 2026.
        response = await client.models.list()
        models = [m.id for m in response.data if "claude" in m.id and "opus" in m.id]
        if not models:
            # Fallback to any claude if no opus found
            models = [m.id for m in response.data if "claude" in m.id]
        if not models:
            return None
        return sorted(models, key=extract_version, reverse=True)[0]
    except Exception:
        return None

async def fetch_latest_google() -> str | None:
    """Fetch the latest Gemini model ID from Google."""
    try:
        import google.generativeai as genai
        api_key = providers.get_provider_api_key("google")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        models = [m.name.replace("models/", "") for m in genai.list_models()
                  if "gemini" in m.name and "pro" in m.name]
        if not models:
            return None
        return sorted(models, key=extract_version, reverse=True)[0]
    except Exception:
        return None

async def fetch_latest_xai() -> str | None:
    """Fetch the latest Grok model ID from xAI."""
    try:
        from openai import AsyncOpenAI
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            return None
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        response = await client.models.list()
        models = [m.id for m in response.data if "grok" in m.id]
        if not models:
            return None
        return sorted(models, key=extract_version, reverse=True)[0]
    except Exception:
        return None

async def discover_new_models() -> dict[str, str]:
    """Check all providers for newer models."""
    tasks = {
        "openai": fetch_latest_openai(),
        "anthropic": fetch_latest_anthropic(),
        "google": fetch_latest_google(),
        "xai": fetch_latest_xai(),
    }
    
    results = await asyncio.gather(*tasks.values())
    updates = {}
    
    for (provider_key, latest), current_config in zip(zip(tasks.keys(), results), providers.MODEL_CONFIG.values()):
        current = current_config["research_model"]
        if latest and latest != current:
            # Simple check: is the new version "higher"?
            if extract_version(latest) >= extract_version(current):
                updates[provider_key] = latest
                
    return updates

def update_providers_file(updates: dict[str, str]):
    """Surgically update providers.py with new model IDs."""
    if not updates:
        return

    content = PROVIDERS_FILE.read_text()
    
    for provider, new_model in updates.items():
        # Update MODEL_CONFIG
        # We look for the provider block and then the research_model/synthesis_model lines
        provider_pattern = rf'"{provider}": \{{[^}}]+?}}'
        match = re.search(provider_pattern, content, re.DOTALL)
        if match:
            block = match.group(0)
            new_block = re.sub(r'("research_model":\s*)"[^"]+"', rf'\1"{new_model}"', block)
            new_block = re.sub(r'("synthesis_model":\s*)"[^"]+"', rf'\1"{new_model}"', new_block)
            content = content.replace(block, new_block)

        # Update MODEL_ALIASES for specific shortcuts
        if provider == "anthropic" and "opus" in new_model:
            content = re.sub(r'("opus":\s*\("anthropic",\s*)"[^"]+"\)', rf'\1"{new_model}")', content)
        elif provider == "openai":
            # If we wanted to update a specific alias like 'chatgpt' if it had a hardcoded model
            pass

    PROVIDERS_FILE.write_text(content)
