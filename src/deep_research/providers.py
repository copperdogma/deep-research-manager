"""API client wrappers for AI providers."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

USER_CONFIG_DIR = Path.home() / ".deep-research"
USER_CONFIG_FILE = USER_CONFIG_DIR / "config.json"


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
        "env_var": "GEMINI_API_KEY",
        "env_fallbacks": ["GOOGLE_API_KEY"],
        "display_name": "Google",
        "research_model": "gemini-3-pro-preview",
        "synthesis_model": "gemini-3-pro-preview",
    },
    "xai": {
        "env_var": "XAI_API_KEY",
        "display_name": "xAI",
        "research_model": "grok-4.1",
        "synthesis_model": "grok-4.1",
    },
}

# Deep research model / agent defaults per provider.
# Only openai and google have real deep-research endpoints today.
DEEP_RESEARCH_DEFAULTS = {
    "openai": {
        "model": "o4-mini-deep-research",
        "tool_type": "web_search_preview",
    },
    "google": {
        "agent": "deep-research-pro-preview-12-2025",
    },
}

# Providers that support real deep-research mode.
DEEP_RESEARCH_PROVIDERS = set(DEEP_RESEARCH_DEFAULTS.keys())


def load_user_overrides():
    """Merge overrides from ~/.deep-research/config.json into MODEL_CONFIG."""
    if not USER_CONFIG_FILE.exists():
        return
    
    try:
        with open(USER_CONFIG_FILE) as f:
            overrides = json.load(f)
            
        for provider, models in overrides.items():
            if provider in MODEL_CONFIG:
                if "research_model" in models:
                    MODEL_CONFIG[provider]["research_model"] = models["research_model"]
                if "synthesis_model" in models:
                    MODEL_CONFIG[provider]["synthesis_model"] = models["synthesis_model"]
            
            # Also update ALIASES if they match the provider
            if provider == "anthropic":
                if "research_model" in models and "opus" in models["research_model"]:
                    MODEL_ALIASES["opus"] = ("anthropic", models["research_model"])
                if "synthesis_model" in models and "sonnet" in models["synthesis_model"]:
                    MODEL_ALIASES["sonnet"] = ("anthropic", models["synthesis_model"])
    except (json.JSONDecodeError, IOError):
        pass

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

# Load overrides immediately on import
load_user_overrides()

DEFAULT_PARAMS = {
    "temperature": 0.0,
    "max_tokens": 128000,
}


def _error_text(exc: Exception) -> str:
    """Return a useful error string even when exception message is empty."""
    return str(exc) or exc.__class__.__name__


@dataclass
class ProviderResult:
    provider: str
    model: str
    content: str
    tokens_used: int
    cost: float
    elapsed_seconds: float
    error: str | None = None
    mode: str = "standard"  # "standard" or "deep"
    debug_payload: object = field(default=None, repr=False)


def get_available_providers() -> list[str]:
    """Return list of provider keys that have API keys set."""
    return [
        key for key, config in MODEL_CONFIG.items()
        if get_provider_api_key(key)
    ]


def get_provider_api_key(provider_key: str) -> str | None:
    """Return provider API key using primary env var then any fallbacks."""
    config = MODEL_CONFIG[provider_key]
    vars_to_check = [config["env_var"], *config.get("env_fallbacks", [])]
    for var in vars_to_check:
        value = os.environ.get(var)
        if value:
            return value
    return None


def has_provider_api_key(provider_key: str) -> bool:
    """Return whether any configured API key env var exists for provider."""
    return bool(get_provider_api_key(provider_key))


def provider_env_hint(provider_key: str) -> str:
    """Return display text for provider API env vars."""
    config = MODEL_CONFIG[provider_key]
    vars_to_check = [config["env_var"], *config.get("env_fallbacks", [])]
    return " or ".join(vars_to_check)


def resolve_synthesis_model(alias: str | None) -> tuple[str, str]:
    """Resolve a model alias to (provider_key, model_id).

    If alias is None, returns the best available provider's synthesis model.
    """
    if alias:
        alias = alias.lower()
        if alias in MODEL_ALIASES:
            provider_key, model_override = MODEL_ALIASES[alias]
            config = MODEL_CONFIG[provider_key]
            if not has_provider_api_key(provider_key):
                available = get_available_providers()
                raise ValueError(
                    f"No API key found for {alias}. "
                    f"Available: {', '.join(available) if available else 'none'}.\n"
                    f"Set {provider_env_hint(provider_key)} or choose another model."
                )
            model = model_override or config["synthesis_model"]
            return provider_key, model
        elif alias in MODEL_CONFIG:
            provider_key = alias
            config = MODEL_CONFIG[provider_key]
            if not has_provider_api_key(provider_key):
                raise ValueError(f"No API key found for {alias}. Set {provider_env_hint(provider_key)}.")
            return provider_key, config["synthesis_model"]
        else:
            raise ValueError(f"Unknown model alias: {alias}")

    # No alias given — pick best available
    for provider_key in SYNTHESIS_PREFERENCE:
        config = MODEL_CONFIG[provider_key]
        if os.environ.get(config["env_var"]):
            return provider_key, config["synthesis_model"]

    raise ValueError(
        "No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, "
        "GEMINI_API_KEY (or GOOGLE_API_KEY), or XAI_API_KEY."
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
        return ProviderResult("openai", model, "", 0, 0.0, elapsed, error=_error_text(e))


async def call_anthropic(prompt: str, model: str, timeout: int) -> ProviderResult:
    """Send a research/synthesis prompt to Anthropic."""
    start = time.monotonic()
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic()
        # Anthropic rejects very large non-streaming requests; keep this below
        # their long-request streaming threshold.
        max_tokens = min(DEFAULT_PARAMS["max_tokens"], 8192)
        response = await asyncio.wait_for(
            client.messages.create(
                model=model,
                max_tokens=max_tokens,
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
        return ProviderResult("anthropic", model, "", 0, 0.0, elapsed, error=_error_text(e))


async def call_google(prompt: str, model: str, timeout: int) -> ProviderResult:
    """Send a research/synthesis prompt to Google using the new genai SDK."""
    start = time.monotonic()
    try:
        from google import genai
        api_key = get_provider_api_key("google")
        if not api_key:
            raise ValueError(f"{provider_env_hint('google')} not set.")
        
        client = genai.Client(api_key=api_key)
        # The new SDK's models.generate_content is synchronous or async
        # For simplicity in this caller, we use the synchronous one wrapped in to_thread
        # if the async one is not preferred.
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=prompt,
            config={
                'temperature': DEFAULT_PARAMS["temperature"],
                'max_output_tokens': 8192, # limit for stability
            }
        )
        content = response.text or ""
        tokens = 0  
        elapsed = time.monotonic() - start
        cost = 0.0  # placeholder
        return ProviderResult("google", model, content, tokens, cost, elapsed)
    except Exception as e:
        elapsed = time.monotonic() - start
        return ProviderResult("google", model, "", 0, 0.0, elapsed, error=_error_text(e))


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
        return ProviderResult("xai", model, "", 0, 0.0, elapsed, error=_error_text(e))


PROVIDER_CALLERS = {
    "openai": call_openai,
    "anthropic": call_anthropic,
    "google": call_google,
    "xai": call_xai,
}


# ---------------------------------------------------------------------------
# Deep research callers
# ---------------------------------------------------------------------------

async def call_openai_deep_research(
    prompt: str,
    model: str | None = None,
    timeout: int = 3600,
    *,
    web: bool = True,
    poll_interval: int = 5,
    debug_callback=None,
) -> ProviderResult:
    """Run an OpenAI deep-research query via the Responses API (background mode).

    Parameters
    ----------
    prompt : str
        Fully-formed research prompt.
    model : str | None
        Override model; defaults to DEEP_RESEARCH_DEFAULTS["openai"]["model"].
    timeout : int
        Max wall-clock seconds to wait for the result.
    web : bool
        Include web_search_preview tool. Must be True — OpenAI deep research
        requires at least one data source.
    poll_interval : int
        Seconds between status polls.
    debug_callback : callable | None
        If provided, called with the raw response object on completion.
    """
    if not web:
        raise ValueError(
            "OpenAI deep research requires at least one data source. "
            "Cannot use --no-web with OpenAI deep research mode."
        )

    model = model or DEEP_RESEARCH_DEFAULTS["openai"]["model"]
    start = time.monotonic()

    try:
        from openai import OpenAI

        client = OpenAI()
        tools = [{"type": "web_search_preview"}]

        log.info("Starting OpenAI deep research (model=%s, background=True)", model)
        resp = client.responses.create(
            model=model,
            input=prompt,
            tools=tools,
            background=True,
        )

        # Poll until terminal state
        deadline = start + timeout
        while resp.status in ("queued", "in_progress"):
            if time.monotonic() > deadline:
                try:
                    client.responses.cancel(resp.id)
                except Exception:
                    pass
                raise TimeoutError(
                    f"OpenAI deep research timed out after {timeout}s. "
                    f"Last status: {resp.status}"
                )
            log.debug("OpenAI DR status: %s (%.0fs elapsed)", resp.status, time.monotonic() - start)
            await asyncio.sleep(poll_interval)
            resp = client.responses.retrieve(resp.id)

        if resp.status != "completed":
            error_detail = getattr(resp, "error", None) or resp.status
            raise RuntimeError(f"OpenAI deep research failed: {error_detail}")

        content = resp.output_text or ""

        # Extract citations if available
        citations = []
        try:
            last_msg = resp.output[-1]
            if hasattr(last_msg, "content") and last_msg.content:
                annotations = getattr(last_msg.content[0], "annotations", []) or []
                for ann in annotations:
                    if hasattr(ann, "url"):
                        citations.append({"title": getattr(ann, "title", ""), "url": ann.url})
        except (IndexError, AttributeError):
            pass

        if citations:
            content += "\n\n## Sources\n\n"
            for c in citations:
                title = c.get("title") or c["url"]
                content += f"- [{title}]({c['url']})\n"

        tokens = 0
        if hasattr(resp, "usage") and resp.usage:
            tokens = getattr(resp.usage, "total_tokens", 0)

        elapsed = time.monotonic() - start
        cost = tokens * 0.00004  # rough placeholder for DR pricing

        if debug_callback:
            debug_callback(resp)

        return ProviderResult(
            provider="openai",
            model=model,
            content=content,
            tokens_used=tokens,
            cost=cost,
            elapsed_seconds=elapsed,
            mode="deep",
        )
    except Exception as e:
        elapsed = time.monotonic() - start
        return ProviderResult(
            "openai", model or "o4-mini-deep-research", "", 0, 0.0, elapsed,
            error=_error_text(e), mode="deep",
        )


async def call_google_deep_research(
    prompt: str,
    agent: str | None = None,
    poll_interval: int = 10,
    max_walltime: int = 1800,
    *,
    debug_callback=None,
) -> ProviderResult:
    """Run a Google Gemini deep-research query via the Interactions API.

    Parameters
    ----------
    prompt : str
        Fully-formed research prompt.
    agent : str | None
        Override agent id; defaults to DEEP_RESEARCH_DEFAULTS["google"]["agent"].
    poll_interval : int
        Seconds between status polls.
    max_walltime : int
        Max wall-clock seconds to wait.
    debug_callback : callable | None
        If provided, called with the raw interaction object on completion.
    """
    agent = agent or DEEP_RESEARCH_DEFAULTS["google"]["agent"]
    start = time.monotonic()

    try:
        from google import genai

        api_key = get_provider_api_key("google")
        if not api_key:
            raise ValueError(f"{provider_env_hint('google')} not set.")

        client = genai.Client(api_key=api_key)

        log.info("Starting Google deep research (agent=%s, background=True)", agent)
        interaction = await asyncio.to_thread(
            client.interactions.create,
            input=prompt,
            agent=agent,
            background=True,
        )

        # Poll until terminal state
        deadline = start + max_walltime
        while True:
            interaction = await asyncio.to_thread(
                client.interactions.get, interaction.id
            )
            status = interaction.status
            log.debug(
                "Google DR status: %s (%.0fs elapsed)", status, time.monotonic() - start
            )

            if status == "completed":
                break
            elif status in ("failed", "cancelled"):
                error_detail = getattr(interaction, "error", None) or status
                raise RuntimeError(f"Google deep research {status}: {error_detail}")

            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"Google deep research timed out after {max_walltime}s. "
                    f"Last status: {status}. "
                    f"Re-run with higher --max-walltime or a narrower prompt."
                )
            await asyncio.sleep(poll_interval)

        content = ""
        if interaction.outputs:
            content = interaction.outputs[-1].text or ""

        elapsed = time.monotonic() - start
        tokens = 0
        cost = 0.0  # Google doesn't expose token count for DR

        if debug_callback:
            debug_callback(interaction)

        return ProviderResult(
            provider="google",
            model=agent,
            content=content,
            tokens_used=tokens,
            cost=cost,
            elapsed_seconds=elapsed,
            mode="deep",
        )
    except Exception as e:
        elapsed = time.monotonic() - start
        return ProviderResult(
            "google", agent or "deep-research-pro-preview-12-2025", "", 0, 0.0, elapsed,
            error=_error_text(e), mode="deep",
        )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

async def run_research(
    prompt: str,
    providers: list[str] | None = None,
    timeout: int = 600,
    *,
    mode: str = "standard",
    openai_dr_model: str | None = None,
    google_dr_agent: str | None = None,
    no_web: bool = False,
    poll_interval: int = 10,
    max_walltime: int = 1800,
    debug: bool = False,
) -> list[ProviderResult]:
    """Run the research prompt against all available (or specified) providers.

    Parameters
    ----------
    mode : "standard" | "deep"
        In "deep" mode, providers with deep-research endpoints use them.
        Providers without deep support fall back to standard.
    """
    if providers is None:
        providers = get_available_providers()

    if not providers:
        raise ValueError(
            "No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, "
            "GEMINI_API_KEY (or GOOGLE_API_KEY), etc. "
            "Or paste results manually into ai-agent-XX.md files."
        )

    debug_payloads: dict[str, object] = {}

    def _make_debug_cb(provider_key):
        if not debug:
            return None
        def cb(raw):
            debug_payloads[provider_key] = raw
        return cb

    tasks = []
    for provider_key in providers:
        config = MODEL_CONFIG[provider_key]
        if mode == "deep" and provider_key in DEEP_RESEARCH_PROVIDERS:
            if provider_key == "openai":
                tasks.append(
                    call_openai_deep_research(
                        prompt,
                        model=openai_dr_model,
                        timeout=timeout,
                        web=not no_web,
                        poll_interval=poll_interval,
                        debug_callback=_make_debug_cb("openai"),
                    )
                )
            elif provider_key == "google":
                tasks.append(
                    call_google_deep_research(
                        prompt,
                        agent=google_dr_agent,
                        poll_interval=poll_interval,
                        max_walltime=max_walltime,
                        debug_callback=_make_debug_cb("google"),
                    )
                )
        else:
            # Standard call (also serves as fallback for providers without deep support)
            if mode == "deep" and provider_key not in DEEP_RESEARCH_PROVIDERS:
                log.warning(
                    "%s does not support deep research mode — falling back to standard.",
                    config["display_name"],
                )
            caller = PROVIDER_CALLERS[provider_key]
            tasks.append(caller(prompt, config["research_model"], timeout))

    results = await asyncio.gather(*tasks)
    # Attach debug payloads so the CLI can write them out
    for r in results:
        if r.provider in debug_payloads:
            r.debug_payload = debug_payloads[r.provider]
    return results


async def run_synthesis(prompt: str, provider_key: str, model: str,
                        timeout: int = 900) -> ProviderResult:
    """Run the synthesis prompt against a specific provider."""
    caller = PROVIDER_CALLERS[provider_key]
    return await caller(prompt, model, timeout)
