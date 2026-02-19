"""Tests for project folder management."""

import os
from pathlib import Path

import pytest

from deep_research import frontmatter, project


@pytest.fixture
def tmp_project(tmp_path):
    """Create a project in a temp directory and return the project dir."""
    return project.init_project("test-topic", agents=3, base_dir=tmp_path)


def test_slugify():
    assert project.slugify("Best UI Tools") == "best-ui-tools"
    assert project.slugify("  Hello World!  ") == "hello-world"
    assert project.slugify("already-good") == "already-good"


def test_init_creates_structure(tmp_path):
    d = project.init_project("my-research", agents=4, base_dir=tmp_path)
    assert d.name == "my-research"
    assert (d / "research-prompt.md").exists()
    assert (d / "synthesis-prompt.md").exists()
    assert (d / "final-synthesis.md").exists()
    assert (d / "ai-agent-01.md").exists()
    assert (d / "ai-agent-04.md").exists()
    assert not (d / "ai-agent-05.md").exists()


def test_init_frontmatter(tmp_path):
    d = project.init_project("test", base_dir=tmp_path)
    text = (d / "research-prompt.md").read_text()
    meta, _ = frontmatter.parse(text)
    assert meta["type"] == "research-prompt"
    assert meta["topic"] == "test"


def test_init_duplicate_raises(tmp_path):
    project.init_project("dup", base_dir=tmp_path)
    with pytest.raises(FileExistsError):
        project.init_project("dup", base_dir=tmp_path)


def test_find_project_dir(tmp_project):
    assert project.find_project_dir(tmp_project) == tmp_project


def test_find_project_dir_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        project.find_project_dir(tmp_path)


def test_is_prompt_empty(tmp_project):
    assert project.is_prompt_empty(tmp_project)


def test_is_prompt_filled(tmp_project):
    rp = tmp_project / "research-prompt.md"
    text = rp.read_text()
    rp.write_text(text + "\nWhat are the best UI tools for 2026?\n")
    assert not project.is_prompt_empty(tmp_project)


def test_get_report_files(tmp_project):
    reports = project.get_report_files(tmp_project)
    names = [r.name for r in reports]
    assert "ai-agent-01.md" in names
    assert "final-synthesis.md" not in names


def test_scan_finds_empty(tmp_project):
    scan = project.scan_agent_files(tmp_project)
    assert len(scan["empty"]) == 3
    assert len(scan["detected"]) == 0
    assert len(scan["unknown"]) == 0


def test_scan_detects_canonical(tmp_project):
    agent = tmp_project / "ai-agent-01.md"
    agent.write_text(
        '---\ntype: research-report\ntopic: "test"\ncanonical-model-name: ""\ncollected: ""\n---\n\n'
        '---\ncanonical-model-name: "gpt-5-2"\n---\n\n# Deep research output...\n\nSome content here.'
    )
    scan = project.scan_agent_files(tmp_project)
    assert ("ai-agent-01.md", "gpt-5-2") in scan["detected"]


def test_scan_unknown_content(tmp_project):
    agent = tmp_project / "ai-agent-01.md"
    agent.write_text(
        '---\ntype: research-report\ntopic: "test"\ncanonical-model-name: ""\ncollected: ""\n---\n\n'
        "Some content without any canonical name.\n"
    )
    scan = project.scan_agent_files(tmp_project)
    assert "ai-agent-01.md" in scan["unknown"]


def test_rename_agent_file(tmp_project):
    agent = tmp_project / "ai-agent-01.md"
    agent.write_text(
        '---\ntype: research-report\ntopic: "test"\ncanonical-model-name: ""\ncollected: ""\n---\n\n'
        "Some research content.\n"
    )
    new_name = project.rename_agent_file(tmp_project, "ai-agent-01.md", "gpt-5-2")
    assert new_name == "gpt-5-2-report.md"
    assert (tmp_project / "gpt-5-2-report.md").exists()
    assert not (tmp_project / "ai-agent-01.md").exists()


def test_delete_empty_agents(tmp_project):
    scan = project.scan_agent_files(tmp_project)
    project.delete_empty_agents(tmp_project, scan["empty"])
    assert not list(tmp_project.glob("ai-agent-*.md"))


def test_extract_canonical_from_frontmatter():
    text = '---\ncanonical-model-name: "claude-opus-4-6"\n---\n\nBody.'
    assert project.extract_canonical_name(text) == "claude-opus-4-6"


def test_extract_canonical_from_body():
    text = '---\ncanonical-model-name: ""\n---\n\n---\ncanonical-model-name: "gpt-5-2"\n---\n\nBody.'
    assert project.extract_canonical_name(text) == "gpt-5-2"


def test_extract_canonical_none():
    text = '---\ntype: report\n---\n\nNo model name here.'
    assert project.extract_canonical_name(text) is None


def test_project_status(tmp_project):
    info = project.project_status(tmp_project)
    assert info["topic"] == "test-topic"
    assert info["prompt_filled"] is False
    assert info["final_filled"] is False
    assert len(info["reports"]) == 3
    assert all(not r["filled"] for r in info["reports"])


def test_detect_api_keys_empty(monkeypatch):
    for var in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY"]:
        monkeypatch.delenv(var, raising=False)
    assert project.detect_api_keys() == {}


def test_detect_api_keys_partial(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    keys = project.detect_api_keys()
    assert "OpenAI" in keys
    assert "Anthropic" not in keys


def test_detect_api_keys_prefers_gemini_var(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gem-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "goog-test")
    keys = project.detect_api_keys()
    assert keys["Google"] == "GEMINI_API_KEY"
