"""Logic for discovering new SOTA models using AI to analyze provider model lists."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from deep_research import providers

PROVIDERS_FILE = Path(__file__).parent / "providers.py"

async def fetch_openai_models() -> list[str]:
    """Fetch all available model IDs from OpenAI."""
    try:
        from openai import AsyncOpenAI
        api_key = providers.get_provider_api_key("openai")
        if not api_key: return []
        client = AsyncOpenAI(api_key=api_key)
        response = await client.models.list()
        return [m.id for m in response.data]
    except Exception: return []

async def fetch_anthropic_models() -> list[str]:
    """Fetch all available model IDs from Anthropic."""
    try:
        from anthropic import AsyncAnthropic
        api_key = providers.get_provider_api_key("anthropic")
        if not api_key: return []
        client = AsyncAnthropic(api_key=api_key)
        response = await client.models.list()
        return [m.id for m in response.data]
    except Exception: return []

async def fetch_google_models() -> list[str]:
    """Fetch all available model IDs from Google using the new genai SDK."""
    try:
        from google import genai
        api_key = providers.get_provider_api_key("google")
        if not api_key: return []
        client = genai.Client(api_key=api_key)
        # Strip 'models/' prefix to match our internal config style
        return [m.name.split("/")[-1] for m in client.models.list()]
    except Exception: return []

async def fetch_xai_models() -> list[str]:
    """Fetch all available model IDs from xAI."""
    try:
        from openai import AsyncOpenAI
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key: return []
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        response = await client.models.list()
        return [m.id for m in response.data]
    except Exception: return []

SOTA_DECISION_PROMPT = """
You are an expert in LLM benchmarking and SOTA (State of the Art) model tracking.
I will provide you with a list of available model IDs from several AI providers, along with the current "SOTA" models I am using for deep research.

Your task is to identify if there is a newer, better flagship "SOTA" model available for each provider specifically for high-reasoning "deep research" tasks.

CRITICAL RULES:
1. Ignore "realtime", "mini", "flash", "lite", "vision", or specialized task models. 
2. Prefer "Flagship" reasoning models (e.g., Claude Opus over Sonnet, GPT-4o or o1 over GPT-4o-mini).
3. "preview" or "experimental" models are acceptable if they represent the current flagship reasoning model or a significant upgrade over the current non-preview flagship.
4. If the current model is already the best available flagship (or a version of it), do NOT suggest an "upgrade".
5. Only suggest an upgrade if a definitively better or newer version of the flagship reasoning model has been released.
5. Return your answer as a raw JSON object with provider keys and their new SOTA model ID. If no upgrade is needed for a provider, omit it from the JSON.

Current Configuration:
{current_config}

Available Models:
{available_models}

Response Format:
{{
  "openai": "gpt-...",
  "anthropic": "claude-..."
}}
"""

async def discover_new_models() -> dict[str, str]:
    """Check all providers for newer models using AI to decide."""
    
    # 1. Fetch all model lists in parallel
    lists_task = {
        "openai": fetch_openai_models(),
        "anthropic": fetch_anthropic_models(),
        "google": fetch_google_models(),
        "xai": fetch_xai_models(),
    }
    lists_results = await asyncio.gather(*lists_task.values())
    available_models = dict(zip(lists_task.keys(), lists_results))
    
    # Filter out providers with no models found
    available_models = {k: v for k, v in available_models.items() if v}
    if not available_models:
        return {}

    # 2. Prepare current config for prompt
    current_config = {
        k: v["research_model"] for k, v in providers.MODEL_CONFIG.items()
    }

    prompt = SOTA_DECISION_PROMPT.format(
        current_config=json.dumps(current_config, indent=2),
        available_models=json.dumps(available_models, indent=2)
    )

    if os.environ.get("DEEP_RESEARCH_DEBUG"):
        print(f"--- SOTA Decision Prompt ---\n{prompt}\n---")

    # 3. Use an available provider to make the decision
    # We prefer Anthropic or OpenAI for reasoning
    decision_provider = None
    for pref in ["anthropic", "openai", "google"]:
        if providers.has_provider_api_key(pref):
            decision_provider = pref
            break
    
    if not decision_provider:
        return {}

    # Resolve a model for synthesis to use for this decision
    _, model_id = providers.resolve_synthesis_model(decision_provider)
    
    try:
        result = await providers.run_synthesis(prompt, decision_provider, model_id)
        if result.error:
            if os.environ.get("DEEP_RESEARCH_DEBUG"):
                print(f"Error making SOTA decision: {result.error}")
            return {}
        
        if os.environ.get("DEEP_RESEARCH_DEBUG"):
            print(f"--- SOTA Decision Content ---\n{result.content}\n---")

        # Extract JSON from response
        match = re.search(r"\{.*\}", result.content, re.DOTALL)
        if not match:
            return {}
        
        updates = json.loads(match.group(0))
        # Validate that the suggested models actually exist in our lists
        validated_updates = {}
        for provider, new_model in updates.items():
            if provider in available_models and new_model in available_models[provider]:
                if new_model != current_config.get(provider):
                    validated_updates[provider] = new_model
                    
        return validated_updates
    except Exception:
        return {}

def update_providers_file(updates: dict[str, str]):
    """Surgically update providers.py with new model IDs."""
    if not updates:
        return

    content = PROVIDERS_FILE.read_text()
    
    for provider, new_model in updates.items():
        # Update MODEL_CONFIG
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
        elif provider == "anthropic" and "sonnet" in new_model:
             content = re.sub(r'("sonnet":\s*\("anthropic",\s*)"[^"]+"\)', rf'\1"{new_model}")', content)

    PROVIDERS_FILE.write_text(content)
