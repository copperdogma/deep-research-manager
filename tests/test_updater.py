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
def mock_providers_file(tmp_path):
    orig_path = Path(providers.__file__)
    content = orig_path.read_text()
    test_file = tmp_path / "providers_test.py"
    test_file.write_text(content)
    
    with patch("deep_research.updater.PROVIDERS_FILE", test_file):
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

def test_update_providers_file(mock_providers_file):
    updates = {
        "openai": "gpt-6.0",
        "anthropic": "claude-opus-5-0"
    }
    
    updater.update_providers_file(updates)
    
    new_content = mock_providers_file.read_text()
    
    # Check if MODEL_CONFIG was updated
    assert '"openai": {' in new_content
    assert '"research_model": "gpt-6.0"' in new_content
    assert '"synthesis_model": "gpt-6.0"' in new_content
    
    assert '"anthropic": {' in new_content
    assert '"research_model": "claude-opus-5-0"' in new_content
    assert '"synthesis_model": "claude-opus-5-0"' in new_content
    
    # Check if MODEL_ALIASES was updated for opus
    assert '"opus": ("anthropic", "claude-opus-5-0")' in new_content

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
