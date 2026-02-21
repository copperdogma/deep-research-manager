import pytest
from unittest.mock import patch
from pathlib import Path
from deep_research.providers import MODEL_CONFIG

@pytest.fixture(scope="session", autouse=True)
def mock_user_config_path(tmp_path_factory):
    """Prevent tests from loading the real ~/.deep-research/config.json and reset MODEL_CONFIG to defaults."""
    tmp_dir = tmp_path_factory.mktemp("config")
    mock_file = tmp_dir / "config.json"
    
    # Hardcoded defaults from providers.py (as of v0.2.1)
    DEFAULTS = {
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

    # Manually reset MODEL_CONFIG to defaults to undo any local config effects
    for provider, config in DEFAULTS.items():
        if provider in MODEL_CONFIG:
            MODEL_CONFIG[provider].update(config)

    with patch("deep_research.providers.USER_CONFIG_DIR", tmp_dir), \
         patch("deep_research.providers.USER_CONFIG_FILE", mock_file):
        yield mock_file
