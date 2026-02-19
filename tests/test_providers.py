"""Tests for provider key resolution helpers."""

from deep_research import providers


def test_google_provider_prefers_gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "goog-key")
    assert providers.get_provider_api_key("google") == "gem-key"


def test_google_provider_falls_back_to_google_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "goog-key")
    assert providers.get_provider_api_key("google") == "goog-key"


def test_google_available_with_google_legacy_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "goog-key")
    assert "google" in providers.get_available_providers()
