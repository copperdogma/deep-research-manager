"""Tests for synthesis prompt generation and payload assembly."""

import pytest

from deep_research import frontmatter, project, synthesis


@pytest.fixture
def research_project(tmp_path):
    """Create a project with a filled prompt and two reports."""
    d = project.init_project("synth-test", agents=2, base_dir=tmp_path)

    # Fill research prompt
    rp = d / "research-prompt.md"
    text = rp.read_text()
    rp.write_text(text + "\nWhat are the best tools for building UIs in 2026?\n")

    # Fill agent files with content
    (d / "ai-agent-01.md").write_text(
        '---\ntype: research-report\ntopic: "synth-test"\n'
        'canonical-model-name: "gpt-5-2"\ncollected: "2026-02-13"\n---\n\n'
        "# Report from GPT\n\nReact is still dominant. Svelte growing fast.\n"
    )
    (d / "ai-agent-02.md").write_text(
        '---\ntype: research-report\ntopic: "synth-test"\n'
        'canonical-model-name: "claude-opus-4-6"\ncollected: "2026-02-13"\n---\n\n'
        "# Report from Claude\n\nSolid and Vue gaining ground. React mature.\n"
    )
    return d


def test_regenerate_synthesis_prompt(research_project):
    result = synthesis.regenerate_synthesis_prompt(research_project)
    assert result is True
    text = (research_project / "synthesis-prompt.md").read_text()
    assert "2 research reports" in text
    assert "best tools for building UIs" in text


def test_regenerate_skips_manual_edits(research_project):
    sp = research_project / "synthesis-prompt.md"
    text = sp.read_text()
    text = text.replace("auto-generated: true", "auto-generated: false")
    sp.write_text(text)
    result = synthesis.regenerate_synthesis_prompt(research_project)
    assert result is False


def test_assemble_payload(research_project):
    synthesis.regenerate_synthesis_prompt(research_project)
    payload = synthesis.assemble_synthesis_payload(research_project)
    assert "Report 1:" in payload
    assert "Report 2:" in payload
    assert "React" in payload
    assert "Solid" in payload


def test_assemble_payload_no_reports(tmp_path):
    d = project.init_project("empty-test", agents=0, base_dir=tmp_path)
    with pytest.raises(ValueError, match="No reports found"):
        synthesis.assemble_synthesis_payload(d)
