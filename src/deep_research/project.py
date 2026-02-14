"""Folder and file management for research projects."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from deep_research import frontmatter, templates


def slugify(name: str) -> str:
    """Convert a topic name to a lowercase-hyphenated slug."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def detect_api_keys() -> dict[str, str]:
    """Return a dict of provider_name -> env_var for available API keys."""
    key_map = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Google": "GOOGLE_API_KEY",
        "xAI": "XAI_API_KEY",
    }
    found = {}
    for name, var in key_map.items():
        if os.environ.get(var):
            found[name] = var
    return found


def detect_missing_keys() -> dict[str, str]:
    """Return a dict of provider_name -> env_var for missing API keys."""
    key_map = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Google": "GOOGLE_API_KEY",
        "xAI": "XAI_API_KEY",
    }
    missing = {}
    for name, var in key_map.items():
        if not os.environ.get(var):
            missing[name] = var
    return missing


def init_project(topic: str, agents: int = 6, base_dir: Path | None = None) -> Path:
    """Create a new research project folder. Returns the path to the created folder."""
    slug = slugify(topic)
    base = base_dir or Path.cwd()
    project_dir = base / slug

    if project_dir.exists():
        raise FileExistsError(f"Folder already exists: {project_dir}")

    project_dir.mkdir(parents=True)

    # research-prompt.md
    (project_dir / "research-prompt.md").write_text(templates.research_prompt(slug))

    # synthesis-prompt.md
    (project_dir / "synthesis-prompt.md").write_text(
        templates.synthesis_prompt(slug, report_count=0)
    )

    # ai-agent placeholder files
    for i in range(1, agents + 1):
        filename = f"ai-agent-{i:02d}.md"
        (project_dir / filename).write_text(templates.agent_placeholder(slug))

    # final-synthesis.md
    (project_dir / "final-synthesis.md").write_text(templates.final_synthesis(slug))

    return project_dir


def find_project_dir(start: Path | None = None) -> Path:
    """Find the research project directory. Looks for research-prompt.md in the given dir."""
    d = start or Path.cwd()
    if (d / "research-prompt.md").exists():
        return d
    raise FileNotFoundError(
        "No research project found. Run from inside a folder created by 'deep-research init'."
    )


def get_research_prompt(project_dir: Path) -> str:
    """Read and return the research prompt content (without frontmatter)."""
    text = (project_dir / "research-prompt.md").read_text()
    _, body = frontmatter.parse(text)
    # Strip the template comment lines
    lines = body.strip().splitlines()
    content_lines = [
        line for line in lines
        if not line.strip().startswith("<!-- ") and line.strip() != "# Research Prompt"
    ]
    content = "\n".join(content_lines).strip()
    return content


def is_prompt_empty(project_dir: Path) -> bool:
    """Check if the research prompt is still empty/template-only."""
    return len(get_research_prompt(project_dir)) == 0


def get_report_files(project_dir: Path) -> list[Path]:
    """Return all report files in the project (ai-agent-*.md and *-report.md), excluding final."""
    reports = []
    for f in sorted(project_dir.iterdir()):
        if f.name == "final-synthesis.md":
            continue
        if f.name.endswith("-report.md") or re.match(r"ai-agent-\d+\.md", f.name):
            reports.append(f)
    return reports


def get_filled_reports(project_dir: Path) -> list[Path]:
    """Return report files that have actual content (not just the template)."""
    filled = []
    for f in get_report_files(project_dir):
        text = f.read_text()
        _, body = frontmatter.parse(text)
        # Strip comments and header
        lines = [
            line for line in body.strip().splitlines()
            if not line.strip().startswith("<!--") and line.strip() != "# Research Report"
        ]
        if any(line.strip() for line in lines):
            filled.append(f)
    return filled


def get_empty_reports(project_dir: Path) -> list[Path]:
    """Return report files that are still empty/template-only."""
    filled_set = set(get_filled_reports(project_dir))
    return [f for f in get_report_files(project_dir) if f not in filled_set]


def extract_canonical_name(text: str) -> str | None:
    """Try to extract a canonical-model-name from file content.

    Looks in the YAML frontmatter first, then in an embedded metadata block in the body.
    """
    metadata, body = frontmatter.parse(text)

    # Check frontmatter
    name = metadata.get("canonical-model-name", "")
    if name:
        return name

    # Check for an embedded metadata block in the body
    # Pattern: --- / canonical-model-name: "value" / ---
    embedded_match = re.search(
        r'canonical-model-name:\s*["\']?([^"\'\n]+)["\']?', body
    )
    if embedded_match:
        return embedded_match.group(1).strip()

    return None


def scan_agent_files(project_dir: Path) -> dict:
    """Scan agent files and categorize them as empty, detected (has a name), or unknown.

    Returns a dict with:
      'empty': list of filenames to delete
      'detected': list of (filename, suggested_name) tuples
      'unknown': list of filenames with content but no detected name
    """
    result = {"empty": [], "detected": [], "unknown": []}
    agent_files = sorted(
        f for f in project_dir.iterdir() if re.match(r"ai-agent-\d+\.md", f.name)
    )

    for f in agent_files:
        text = f.read_text()
        _, body = frontmatter.parse(text)

        # Check if empty/template-only
        lines = [
            line for line in body.strip().splitlines()
            if not line.strip().startswith("<!--") and line.strip() != "# Research Report"
        ]
        if not any(line.strip() for line in lines):
            result["empty"].append(f.name)
            continue

        canonical = extract_canonical_name(text)
        if canonical:
            result["detected"].append((f.name, canonical))
        else:
            result["unknown"].append(f.name)

    return result


def rename_agent_file(project_dir: Path, old_name: str, model_name: str) -> str:
    """Rename an agent file to {model_name}-report.md. Returns the new filename."""
    slug = slugify(model_name)
    new_name = f"{slug}-report.md"
    new_path = project_dir / new_name
    if new_path.exists():
        new_name = f"{slug}-manual-report.md"
        new_path = project_dir / new_name

    old_path = project_dir / old_name
    text = old_path.read_text()
    metadata, body = frontmatter.parse(text)
    metadata["canonical-model-name"] = model_name
    if not metadata.get("collected"):
        mtime = datetime.fromtimestamp(old_path.stat().st_mtime, tz=timezone.utc)
        metadata["collected"] = mtime.isoformat()

    old_path.rename(new_path)
    new_path.write_text(frontmatter.dump(metadata, body))
    return new_name


def delete_empty_agents(project_dir: Path, filenames: list[str]) -> None:
    """Delete the listed agent placeholder files."""
    for name in filenames:
        (project_dir / name).unlink()


def word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def project_status(project_dir: Path) -> dict:
    """Gather project status information."""
    topic_meta, _ = frontmatter.parse((project_dir / "research-prompt.md").read_text())
    topic = topic_meta.get("topic", project_dir.name)

    prompt_content = get_research_prompt(project_dir)
    prompt_filled = len(prompt_content) > 0
    prompt_words = word_count(prompt_content) if prompt_filled else 0

    synth_text = (project_dir / "synthesis-prompt.md").read_text()
    synth_meta, synth_body = frontmatter.parse(synth_text)
    synth_words = word_count(synth_body)
    synth_auto = synth_meta.get("auto-generated", True)

    reports = []
    for f in get_report_files(project_dir):
        text = f.read_text()
        _, body = frontmatter.parse(text)
        lines = [
            line for line in body.strip().splitlines()
            if not line.strip().startswith("<!--") and line.strip() != "# Research Report"
        ]
        has_content = any(line.strip() for line in lines)
        reports.append({
            "filename": f.name,
            "filled": has_content,
            "words": word_count(body) if has_content else 0,
        })

    final_text = (project_dir / "final-synthesis.md").read_text()
    _, final_body = frontmatter.parse(final_text)
    final_lines = [
        line for line in final_body.strip().splitlines()
        if not line.strip().startswith("<!--") and line.strip() != "# Final Synthesis"
    ]
    final_filled = any(line.strip() for line in final_lines)
    final_words = word_count(final_body) if final_filled else 0

    return {
        "topic": topic,
        "created": topic_meta.get("created", ""),
        "prompt_filled": prompt_filled,
        "prompt_words": prompt_words,
        "synthesis_words": synth_words,
        "synthesis_auto": synth_auto,
        "reports": reports,
        "final_filled": final_filled,
        "final_words": final_words,
    }
