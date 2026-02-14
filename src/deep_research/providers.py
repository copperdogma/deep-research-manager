"""API client wrappers for AI providers."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass


# Model configuration: provider -> (research_model, synthesis_model)
MODEL_CONFIG = {
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "display_name": "OpenAI",
        "research_model": "gpt-5.2",
        "synthesis_model": "gpt-5.2",
    },
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
        "display_name": "Anthropic",
        "research_model": "claude-opus-4-6",
        "synthesis_model": "claude-opus-4-6",
    },
    "google": {
        "env_var": "GOOGLE_API_KEY",
        "display_name": "Google",
        "research_model": "gemini-2.5-flash",
        "synthesis_model": "gemini-2.5-pro",
    },
    "xai": {
        "env_var": "XAI_API_KEY",
        "display_name": "xAI",
        "research_model": "grok-4.1",
        "synthesis_model": "grok-4.1",
    },
}

# Preferred model order for synthesis (best first)
SYNTHESIS_PREFERENCE = ["anthropic", "openai", "google", "xai"]

# Aliases for the `final` command
MODEL_ALIASES = {
    "opus": ("anthropic", "claude-opus-4-6"),
    "sonnet": ("anthropic", "claude-sonnet-4-5-20250929"),
    "chatgpt": ("openai", None),  # None = use default
    "gemini": ("google", None),
    "grok": ("xai", None),
}

DEFAULT_PARAMS = {
    "temperature": 0.0,
    "max_tokens": 128000,
}


@dataclass
class ProviderResult:
    provider: str
    model: str
    content: str
    tokens_used: int
    cost: float
    elapsed_seconds: float
    error: str | None = None


def get_available_providers() -> list[str]:
    """Return list of provider keys that have API keys set."""
    return [
        key for key, config in MODEL_CONFIG.items()
        if os.environ.get(config["env_var"])
    ]


def resolve_synthesis_model(alias: str | None) -> tuple[str, str]:
    """Resolve a model alias to (provider_key, model_id).

    If alias is None, returns the best available provider's synthesis model.
    """
    if alias:
        alias = alias.lower()
        if alias in MODEL_ALIASES:
            provider_key, model_override = MODEL_ALIASES[alias]
            config = MODEL_CONFIG[provider_key]
            if not os.environ.get(config["env_var"]):
                available = get_available_providers()
                raise ValueError(
                    f"No API key found for {alias}. "
                    f"Available: {', '.join(available) if available else 'none'}.\n"
                    f"Set {config['env_var']} or choose another model."
                )
            model = model_override or config["synthesis_model"]
            return provider_key, model
        elif alias in MODEL_CONFIG:
            provider_key = alias
            config = MODEL_CONFIG[provider_key]
            if not os.environ.get(config["env_var"]):
                raise ValueError(f"No API key found for {alias}. Set {config['env_var']}.")
            return provider_key, config["synthesis_model"]
        else:
            raise ValueError(f"Unknown model alias: {alias}")

    # No alias given — pick best available
    for provider_key in SYNTHESIS_PREFERENCE:
        config = MODEL_CONFIG[provider_key]
        if os.environ.get(config["env_var"]):
            return provider_key, config["synthesis_model"]

    raise ValueError(
        "No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, or XAI_API_KEY."
    )


async def call_openai(prompt: str, model: str, timeout: int) -> ProviderResult:
    """Send a research/synthesis prompt to OpenAI."""
    start = time.monotonic()
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=DEFAULT_PARAMS["temperature"],
                max_completion_tokens=DEFAULT_PARAMS["max_tokens"],
            ),
            timeout=timeout,
        )
        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        elapsed = time.monotonic() - start
        cost = tokens * 0.00003  # placeholder rate
        return ProviderResult("openai", model, content, tokens, cost, elapsed)
    except Exception as e:
        elapsed = time.monotonic() - start
        return ProviderResult("openai", model, "", 0, 0.0, elapsed, error=str(e))


async def call_anthropic(prompt: str, model: str, timeout: int) -> ProviderResult:
    """Send a research/synthesis prompt to Anthropic."""
    start = time.monotonic()
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic()
        response = await asyncio.wait_for(
            client.messages.create(
                model=model,
                max_tokens=DEFAULT_PARAMS["max_tokens"],
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=timeout,
        )
        content = response.content[0].text if response.content else ""
        tokens = (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0
        elapsed = time.monotonic() - start
        cost = tokens * 0.00006  # placeholder rate
        return ProviderResult("anthropic", model, content, tokens, cost, elapsed)
    except Exception as e:
        elapsed = time.monotonic() - start
        return ProviderResult("anthropic", model, "", 0, 0.0, elapsed, error=str(e))


async def call_google(prompt: str, model: str, timeout: int) -> ProviderResult:
    """Send a research/synthesis prompt to Google."""
    start = time.monotonic()
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        gen_model = genai.GenerativeModel(model)
        response = await asyncio.wait_for(
            asyncio.to_thread(gen_model.generate_content, prompt),
            timeout=timeout,
        )
        content = response.text or ""
        tokens = 0  # Google SDK doesn't always expose token counts easily
        elapsed = time.monotonic() - start
        cost = 0.0  # placeholder
        return ProviderResult("google", model, content, tokens, cost, elapsed)
    except Exception as e:
        elapsed = time.monotonic() - start
        return ProviderResult("google", model, "", 0, 0.0, elapsed, error=str(e))


async def call_xai(prompt: str, model: str, timeout: int) -> ProviderResult:
    """Send a research/synthesis prompt to xAI (OpenAI-compatible API)."""
    start = time.monotonic()
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=os.environ["XAI_API_KEY"],
            base_url="https://api.x.ai/v1",
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=DEFAULT_PARAMS["temperature"],
                max_completion_tokens=DEFAULT_PARAMS["max_tokens"],
            ),
            timeout=timeout,
        )
        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        elapsed = time.monotonic() - start
        cost = tokens * 0.00003  # placeholder rate
        return ProviderResult("xai", model, content, tokens, cost, elapsed)
    except Exception as e:
        elapsed = time.monotonic() - start
        return ProviderResult("xai", model, "", 0, 0.0, elapsed, error=str(e))


PROVIDER_CALLERS = {
    "openai": call_openai,
    "anthropic": call_anthropic,
    "google": call_google,
    "xai": call_xai,
}


async def run_research(prompt: str, providers: list[str] | None = None,
                       timeout: int = 600) -> list[ProviderResult]:
    """Run the research prompt against all available (or specified) providers in parallel."""
    if providers is None:
        providers = get_available_providers()

    if not providers:
        raise ValueError(
            "No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, etc. "
            "Or paste results manually into ai-agent-XX.md files."
        )

    tasks = []
    for provider_key in providers:
        config = MODEL_CONFIG[provider_key]
        caller = PROVIDER_CALLERS[provider_key]
        tasks.append(caller(prompt, config["research_model"], timeout))

    return await asyncio.gather(*tasks)


async def run_synthesis(prompt: str, provider_key: str, model: str,
                        timeout: int = 900) -> ProviderResult:
    """Run the synthesis prompt against a specific provider."""
    caller = PROVIDER_CALLERS[provider_key]
    return await caller(prompt, model, timeout)
