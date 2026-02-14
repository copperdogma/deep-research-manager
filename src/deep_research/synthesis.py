"""Synthesis prompt generation and payload assembly."""

from __future__ import annotations

from pathlib import Path

from deep_research import frontmatter, templates
from deep_research.project import get_filled_reports, get_research_prompt


def regenerate_synthesis_prompt(project_dir: Path) -> bool:
    """Regenerate synthesis-prompt.md with current research context and report count.

    Returns False if the file has manual edits (auto-generated: false) — skips regeneration.
    Returns True if regenerated successfully.
    """
    synth_path = project_dir / "synthesis-prompt.md"
    if synth_path.exists():
        existing = synth_path.read_text()
        meta, _ = frontmatter.parse(existing)
        if meta.get("auto-generated") is False:
            return False

    topic_meta, _ = frontmatter.parse((project_dir / "research-prompt.md").read_text())
    topic = topic_meta.get("topic", project_dir.name)

    research_context = get_research_prompt(project_dir)
    report_count = len(get_filled_reports(project_dir))

    synth_path.write_text(
        templates.synthesis_prompt(topic, report_count=report_count, research_context=research_context)
    )
    return True


def assemble_synthesis_payload(project_dir: Path) -> str:
    """Assemble the full synthesis payload: synthesis prompt + all reports.

    Returns the assembled markdown string ready to send to an AI model.
    """
    synth_text = (project_dir / "synthesis-prompt.md").read_text()
    _, synth_body = frontmatter.parse(synth_text)

    reports = get_filled_reports(project_dir)
    if not reports:
        raise ValueError(
            "No reports found. Run 'deep-research run' or paste results into ai-agent-XX.md files first."
        )

    parts = [synth_body.strip()]
    parts.append("\n\n---\n\n## Source Reports\n")

    for i, report_path in enumerate(reports, 1):
        text = report_path.read_text()
        _, body = frontmatter.parse(text)
        model_name = report_path.stem.replace("-report", "").replace("-", " ").title()
        parts.append(f"\n### Report {i}: {model_name}\n")
        parts.append(body.strip())
        parts.append("\n\n---\n")

    return "\n".join(parts)
