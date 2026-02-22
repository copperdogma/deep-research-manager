"""Tests for the stub command and related project helpers."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from deep_research import frontmatter, project
from deep_research.cli import main


@pytest.fixture()
def proj(tmp_path):
    """Minimal project with a filled research prompt."""
    d = project.init_project("stub-test", agents=2, base_dir=tmp_path)
    rp = d / "research-prompt.md"
    meta, _ = frontmatter.parse(rp.read_text())
    rp.write_text(frontmatter.dump(meta, "What is the capital of France?"))
    return d


# ---------------------------------------------------------------------------
# get_report_files includes deep-research files
# ---------------------------------------------------------------------------


def test_get_report_files_includes_deep_research(proj):
    """Files named ai-*-deep-research.md should appear in get_report_files."""
    dr_file = proj / "ai-openai-deep-research.md"
    dr_file.write_text(frontmatter.dump({"type": "research-report"}, "content"))
    names = [f.name for f in project.get_report_files(proj)]
    assert "ai-openai-deep-research.md" in names


def test_get_report_files_excludes_final(proj):
    names = [f.name for f in project.get_report_files(proj)]
    assert "final-synthesis.md" not in names


# ---------------------------------------------------------------------------
# write_stub
# ---------------------------------------------------------------------------


def test_write_stub_creates_file(proj):
    path = project.write_stub(proj, "xai", "grok-4.1", "stub-test")
    assert path.exists()
    assert path.name == "grok-4-1-report.md"


def test_write_stub_frontmatter(proj):
    path = project.write_stub(proj, "xai", "grok-4.1", "stub-test", mode="standard")
    meta, body = frontmatter.parse(path.read_text())
    assert meta["canonical-model-name"] == "grok-4.1"
    assert meta["research-mode"] == "standard"
    assert meta["topic"] == "stub-test"
    assert meta["type"] == "research-report"
    assert meta["collected"]  # timestamp is set


def test_write_stub_deep_mode_filename(proj):
    path = project.write_stub(proj, "openai", "o4-mini-deep-research", "stub-test", mode="deep")
    assert path.name == "ai-openai-deep-research.md"


def test_write_stub_body_is_comment_only(proj):
    """Stub body must be comment-only so it stays out of filled reports."""
    path = project.write_stub(proj, "xai", "grok-4.1", "stub-test")
    filled = project.get_filled_reports(proj)
    assert path not in filled


# ---------------------------------------------------------------------------
# stub_exists
# ---------------------------------------------------------------------------


def test_stub_exists_false_when_empty(proj):
    assert not project.stub_exists(proj, "xai", "grok-4.1")


def test_stub_exists_true_for_standard_report(proj):
    (proj / "grok-4-1-report.md").write_text("content")
    assert project.stub_exists(proj, "xai", "grok-4.1")


def test_stub_exists_true_for_deep_research_file(proj):
    (proj / "ai-openai-deep-research.md").write_text("content")
    assert project.stub_exists(proj, "openai", "o4-mini-deep-research")


# ---------------------------------------------------------------------------
# CLI: stub command
# ---------------------------------------------------------------------------


class TestStubCommand:
    @pytest.fixture()
    def runner(self):
        return CliRunner()

    def test_stub_specific_provider(self, runner, proj, monkeypatch):
        monkeypatch.chdir(proj)
        result = runner.invoke(main, ["stub", "xai"])
        assert result.exit_code == 0
        assert "grok-4-1-report.md" in result.output
        assert (proj / "grok-4-1-report.md").exists()

    def test_stub_multiple_providers(self, runner, proj, monkeypatch):
        monkeypatch.chdir(proj)
        result = runner.invoke(main, ["stub", "xai", "anthropic"])
        assert result.exit_code == 0
        assert (proj / "grok-4-1-report.md").exists()
        assert (proj / "claude-opus-4-6-report.md").exists()

    def test_stub_unknown_provider_errors(self, runner, proj, monkeypatch):
        monkeypatch.chdir(proj)
        result = runner.invoke(main, ["stub", "unknown-provider"])
        assert result.exit_code != 0

    def test_stub_skips_existing(self, runner, proj, monkeypatch):
        monkeypatch.chdir(proj)
        (proj / "grok-4-1-report.md").write_text("existing content")
        result = runner.invoke(main, ["stub", "xai"])
        assert result.exit_code == 0
        assert "Skipped" in result.output
        # File should not be overwritten
        assert (proj / "grok-4-1-report.md").read_text() == "existing content"

    def test_stub_all_overwrites_existing(self, runner, proj, monkeypatch):
        monkeypatch.chdir(proj)
        (proj / "grok-4-1-report.md").write_text("old content")
        result = runner.invoke(main, ["stub", "xai", "--all"])
        assert result.exit_code == 0
        assert "Skipped" not in result.output
        # File should now have frontmatter, not "old content"
        text = (proj / "grok-4-1-report.md").read_text()
        assert "old content" not in text
        assert "canonical-model-name" in text

    def test_stub_deep_mode(self, runner, proj, monkeypatch):
        monkeypatch.chdir(proj)
        result = runner.invoke(main, ["stub", "openai", "--mode", "deep"])
        assert result.exit_code == 0
        assert (proj / "ai-openai-deep-research.md").exists()

    def test_stub_no_args_creates_all_missing(self, runner, proj, monkeypatch, tmp_path):
        monkeypatch.chdir(proj)
        # Pre-create one report so it's skipped
        (proj / "grok-4-1-report.md").write_text("existing")
        result = runner.invoke(main, ["stub"])
        assert result.exit_code == 0
        # Others should be created
        assert "Created stubs" in result.output
        # xAI should be skipped
        assert "Skipped" in result.output
