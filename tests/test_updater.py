import asyncio
import os
import re
import pytest
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

def test_extract_version():
    assert updater.extract_version("gpt-5.2") == [5, 2]
    assert updater.extract_version("claude-opus-4-6") == [4, 6]
    assert updater.extract_version("gemini-1.5-pro") == [1, 5]
    assert updater.extract_version("no-numbers") == [0]

def test_discover_new_models_openai():
    # Mock current config
    with patch.dict(providers.MODEL_CONFIG, {
        "openai": {"research_model": "gpt-5.2"}
    }):
        # Mock API response
        mock_data = MagicMock()
        mock_data.data = [MagicMock(id="gpt-5.2"), MagicMock(id="gpt-5.5")]
        
        with patch("openai.AsyncOpenAI") as mock_client:
            mock_inst = mock_client.return_value
            mock_inst.models.list = AsyncMock(return_value=mock_data)
            
            with patch("deep_research.providers.get_provider_api_key", return_value="fake-key"):
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
        mock_data = MagicMock()
        mock_data.data = [MagicMock(id="gpt-5.2"), MagicMock(id="gpt-5.5")]
        
        with patch("openai.AsyncOpenAI") as mock_client:
            mock_inst = mock_client.return_value
            mock_inst.models.list = AsyncMock(return_value=mock_data)
            
            with patch("deep_research.providers.get_provider_api_key", return_value="fake-key"):
                # Use a patch for other providers to return None to avoid noise
                with patch("deep_research.updater.fetch_latest_anthropic", return_value=None), \
                     patch("deep_research.updater.fetch_latest_google", return_value=None), \
                     patch("deep_research.updater.fetch_latest_xai", return_value=None):
                    updates = asyncio.run(updater.discover_new_models())
                    assert "openai" not in updates
