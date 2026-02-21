import asyncio
import os
import re
import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from deep_research import updater, providers

# Use a temporary file for testing
@pytest.fixture
def mock_user_config(tmp_path):
    test_file = tmp_path / "config.json"
    with patch("deep_research.providers.USER_CONFIG_FILE", test_file), \
         patch("deep_research.providers.USER_CONFIG_DIR", tmp_path):
        yield test_file

def test_discover_new_models_openai():
    # Mock current config
    with patch.dict(providers.MODEL_CONFIG, {
        "openai": {"research_model": "gpt-5.2"}
    }):
        # Mock model lists
        with patch("deep_research.updater.fetch_openai_models", return_value=["gpt-5.2", "gpt-5.5"]), \
             patch("deep_research.updater.fetch_anthropic_models", return_value=[]), \
             patch("deep_research.updater.fetch_google_models", return_value=[]), \
             patch("deep_research.updater.fetch_xai_models", return_value=[]):
            
            # Mock synthesis call (the decision)
            mock_result = MagicMock()
            mock_result.error = None
            mock_result.content = '{"openai": "gpt-5.5"}'
            
            with patch("deep_research.providers.run_synthesis", return_value=mock_result), \
                 patch("deep_research.providers.has_provider_api_key", return_value=True), \
                 patch("deep_research.providers.resolve_synthesis_model", return_value=("openai", "gpt-5.2")):
                
                updates = asyncio.run(updater.discover_new_models())
                assert updates.get("openai") == "gpt-5.5"

def test_update_providers_file(mock_user_config):
    updates = {
        "openai": "gpt-6.0",
        "anthropic": "claude-opus-5-0"
    }
    
    updater.update_providers_file(updates)
    
    with open(mock_user_config) as f:
        config = json.load(f)
    
    # Check if config was updated
    assert config["openai"]["research_model"] == "gpt-6.0"
    assert config["openai"]["synthesis_model"] == "gpt-6.0"
    assert config["anthropic"]["research_model"] == "claude-opus-5-0"
    assert config["anthropic"]["synthesis_model"] == "claude-opus-5-0"

def test_discover_no_updates():
    with patch.dict(providers.MODEL_CONFIG, {
        "openai": {"research_model": "gpt-5.5"}
    }):
        # Mock model lists
        with patch("deep_research.updater.fetch_openai_models", return_value=["gpt-5.2", "gpt-5.5"]), \
             patch("deep_research.updater.fetch_anthropic_models", return_value=[]), \
             patch("deep_research.updater.fetch_google_models", return_value=[]), \
             patch("deep_research.updater.fetch_xai_models", return_value=[]):
            
            # Mock synthesis call (no update suggested)
            mock_result = MagicMock()
            mock_result.error = None
            mock_result.content = '{}'
            
            with patch("deep_research.providers.run_synthesis", return_value=mock_result), \
                 patch("deep_research.providers.has_provider_api_key", return_value=True), \
                 patch("deep_research.providers.resolve_synthesis_model", return_value=("openai", "gpt-5.5")):
                
                updates = asyncio.run(updater.discover_new_models())
                assert "openai" not in updates
