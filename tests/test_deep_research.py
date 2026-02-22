"""Tests for deep research mode (CLI flags, provider routing, validation)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from deep_research import providers
from deep_research.cli import main

# ---------------------------------------------------------------------------
# Provider routing tests
# ---------------------------------------------------------------------------


class TestProviderRouting:
    """Verify run_research dispatches correctly based on mode."""

    @pytest.fixture(autouse=True)
    def _stub_keys(self, monkeypatch):
        """Ensure openai and google keys exist for routing tests."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def test_standard_mode_uses_standard_callers(self, monkeypatch):
        """Standard mode should call normal provider callers, not deep functions."""
        called_with = {}

        async def fake_openai(prompt, model, timeout):
            called_with["openai"] = model
            return providers.ProviderResult("openai", model, "ok", 0, 0.0, 1.0)

        async def fake_anthropic(prompt, model, timeout):
            called_with["anthropic"] = model
            return providers.ProviderResult("anthropic", model, "ok", 0, 0.0, 1.0)

        monkeypatch.setitem(providers.PROVIDER_CALLERS, "openai", fake_openai)
        monkeypatch.setitem(providers.PROVIDER_CALLERS, "anthropic", fake_anthropic)

        results = asyncio.run(
            providers.run_research("test", ["openai", "anthropic"], mode="standard")
        )
        assert len(results) == 2
        assert "openai" in called_with
        assert "anthropic" in called_with

    @patch("deep_research.providers.call_openai_deep_research")
    def test_deep_mode_routes_openai_to_deep_caller(self, mock_dr, monkeypatch):
        mock_dr.return_value = providers.ProviderResult(
            "openai", "o4-mini-deep-research", "deep report", 0, 0.0, 10.0, mode="deep"
        )
        results = asyncio.run(
            providers.run_research("test", ["openai"], mode="deep")
        )
        assert len(results) == 1
        assert results[0].mode == "deep"
        mock_dr.assert_called_once()

    @patch("deep_research.providers.call_google_deep_research")
    def test_deep_mode_routes_google_to_deep_caller(self, mock_dr, monkeypatch):
        mock_dr.return_value = providers.ProviderResult(
            "google", "deep-research-pro-preview-12-2025", "deep report", 0, 0.0, 20.0,
            mode="deep",
        )
        results = asyncio.run(
            providers.run_research("test", ["google"], mode="deep")
        )
        assert len(results) == 1
        assert results[0].mode == "deep"
        mock_dr.assert_called_once()

    def test_deep_mode_falls_back_for_anthropic(self, monkeypatch):
        """Providers without deep support should fall back to standard caller."""
        called_with = {}

        async def fake_anthropic(prompt, model, timeout):
            called_with["anthropic"] = model
            return providers.ProviderResult("anthropic", model, "ok", 0, 0.0, 1.0)

        monkeypatch.setitem(providers.PROVIDER_CALLERS, "anthropic", fake_anthropic)

        results = asyncio.run(
            providers.run_research("test", ["anthropic"], mode="deep")
        )
        assert len(results) == 1
        assert results[0].mode == "standard"
        assert "anthropic" in called_with


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestValidation:
    def test_no_web_with_openai_deep_raises(self):
        """--no-web with OpenAI deep research should raise ValueError."""
        with pytest.raises(ValueError, match="requires at least one data source"):
            asyncio.run(
                providers.call_openai_deep_research("test", web=False)
            )

    def test_deep_research_providers_set(self):
        """DEEP_RESEARCH_PROVIDERS should contain openai and google."""
        assert "openai" in providers.DEEP_RESEARCH_PROVIDERS
        assert "google" in providers.DEEP_RESEARCH_PROVIDERS
        assert "anthropic" not in providers.DEEP_RESEARCH_PROVIDERS
        assert "xai" not in providers.DEEP_RESEARCH_PROVIDERS

    def test_deep_research_defaults_have_expected_keys(self):
        assert "model" in providers.DEEP_RESEARCH_DEFAULTS["openai"]
        assert "agent" in providers.DEEP_RESEARCH_DEFAULTS["google"]


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLIFlags:
    """Verify CLI properly parses deep research flags."""

    @pytest.fixture()
    def runner(self):
        return CliRunner()

    @pytest.fixture()
    def _project(self, tmp_path, monkeypatch):
        """Create a minimal project directory for CLI tests."""
        from deep_research import frontmatter as fm

        monkeypatch.chdir(tmp_path)
        # Create research-prompt.md with content
        rp = tmp_path / "research-prompt.md"
        rp.write_text(fm.dump(
            {"type": "research-prompt", "topic": "test-topic", "created": "2026-01-01"},
            "What is the meaning of life?",
        ))
        # Create synthesis-prompt.md
        sp = tmp_path / "synthesis-prompt.md"
        sp.write_text(fm.dump(
            {"type": "synthesis-prompt", "topic": "test-topic", "auto-generated": True},
            "Synthesize.",
        ))
        return tmp_path

    def test_dry_run_deep_mode(self, runner, _project, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test")
        monkeypatch.setenv("GEMINI_API_KEY", "test")
        result = runner.invoke(main, ["run", "--mode", "deep", "--dry-run"])
        assert result.exit_code == 0
        assert "deep" in result.output.lower()
        assert "DEEP" in result.output

    def test_dry_run_standard_mode(self, runner, _project, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test")
        result = runner.invoke(main, ["run", "--mode", "standard", "--dry-run"])
        assert result.exit_code == 0
        assert "standard" in result.output.lower()

    def test_no_web_with_deep_openai_errors(self, runner, _project, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test")
        result = runner.invoke(main, ["run", "--mode", "deep", "--no-web", "--provider", "openai"])
        assert result.exit_code != 0
        assert "requires at least one data source" in result.output

    def test_mode_flag_accepts_deep(self, runner, _project, monkeypatch):
        """Verify --mode deep is accepted without error (dry-run)."""
        monkeypatch.setenv("OPENAI_API_KEY", "test")
        result = runner.invoke(main, ["run", "--mode", "deep", "--dry-run", "--provider", "openai"])
        assert result.exit_code == 0

    def test_poll_interval_flag(self, runner, _project, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test")
        result = runner.invoke(main, [
            "run", "--mode", "deep", "--poll-interval", "5",
            "--dry-run", "--provider", "openai",
        ])
        assert result.exit_code == 0

    def test_max_walltime_flag(self, runner, _project, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test")
        result = runner.invoke(main, [
            "run", "--mode", "deep", "--max-walltime", "3600",
            "--dry-run", "--provider", "openai",
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Output filename tests
# ---------------------------------------------------------------------------


class TestOutputFilename:
    def test_deep_result_filename(self):
        from deep_research.cli import _result_filename

        result = providers.ProviderResult(
            "openai", "o4-mini-deep-research", "content", 0, 0.0, 10.0, mode="deep"
        )
        assert _result_filename(result) == "ai-openai-deep-research.md"

    def test_deep_google_filename(self):
        from deep_research.cli import _result_filename

        result = providers.ProviderResult(
            "google", "deep-research-pro-preview-12-2025", "content", 0, 0.0, 20.0,
            mode="deep",
        )
        assert _result_filename(result) == "ai-google-deep-research.md"

    def test_standard_result_filename(self):
        from deep_research.cli import _result_filename

        result = providers.ProviderResult(
            "openai", "gpt-5.2", "content", 0, 0.0, 5.0, mode="standard"
        )
        assert _result_filename(result) == "gpt-5-2-report.md"
