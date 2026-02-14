"""YAML frontmatter parsing and writing for markdown files."""

from __future__ import annotations

import yaml


def parse(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown text.

    Returns (metadata_dict, body_text). If no frontmatter found, returns ({}, full_text).
    """
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    # parts[0] is empty (before first ---), parts[1] is YAML, parts[2] is body
    try:
        metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}, text

    body = parts[2]
    if body.startswith("\n"):
        body = body[1:]

    return metadata, body


def dump(metadata: dict, body: str) -> str:
    """Combine metadata dict and body text into a frontmatter markdown string."""
    fm = yaml.dump(metadata, default_flow_style=False, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{fm}\n---\n\n{body}"


def update_field(text: str, key: str, value) -> str:
    """Update a single frontmatter field in-place, preserving the rest of the document."""
    metadata, body = parse(text)
    metadata[key] = value
    return dump(metadata, body)
